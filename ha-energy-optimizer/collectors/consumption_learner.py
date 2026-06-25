# name:          consumption_learner.py
# part of:       ha-energy-optimizer
# location:      /ha-energy-optimizer/ha-energy-optimizer/collectors/consumption_learner.py
# part version:  p_v0.4
# altered:       2026-06-26
#
# Leert het typische huisverbruik per uur, dag van de week en maand.
# Gebruikt rollend gewogen gemiddelde met bootstrap vanuit vorige vergelijkbare slot.
# Wordt aangeroepen na elke meting in ha_collector.py.
#
# Learns typical household consumption per hour, day of week and month.
# Uses rolling weighted average with bootstrap from previous comparable slot.
# Called after each measurement in ha_collector.py.

import logging
import math
from datetime import datetime
from decimal import Decimal

from database.connection import DatabaseConnection

log = logging.getLogger(__name__)

# Gauss-curve fallback parameters — gebruikt als er geen enkel vergelijkbaar
# slot beschikbaar is (bijv. bij eerste installatie).
# Aanpasbaar zonder code-wijziging via optimizer_defaults.json (toekomstig).
#
# Gauss curve fallback parameters — used when no comparable slot is available
# (e.g. on first installation). Adjustable without code changes via
# optimizer_defaults.json (future).
_GAUSS_PEAK_KWH   = 0.60    # piek verbruik per uur / peak consumption per hour
_GAUSS_PEAK_HOUR  = 12      # uur van de piek / hour of peak
_GAUSS_SIGMA      = 5.0     # breedte van de curve / width of curve
_GAUSS_NIGHT_KWH  = 0.05    # basisverbruik 's nachts / base consumption at night
_BOOTSTRAP_WEIGHT = 3       # gewicht van vorig slot bij bootstrap / weight of previous slot


def _gauss_fallback(hour: int) -> float:
    """
    Gauss-curve voor initiële verbruiksschatting per uur.
    Gauss curve for initial consumption estimate per hour.
    """
    x = hour - _GAUSS_PEAK_HOUR
    return _GAUSS_NIGHT_KWH + (_GAUSS_PEAK_KWH - _GAUSS_NIGHT_KWH) * math.exp(
        -(x ** 2) / (2 * _GAUSS_SIGMA ** 2)
    )


class ConsumptionLearner:
    """
    Leersysteem voor huisverbruik.
    2.016 slots: 12 maanden × 7 dagen × 24 uur.
    Rollend gewogen gemiddelde met gewogen bootstrap vanuit vorig vergelijkbaar slot.

    Household consumption learning system.
    2,016 slots: 12 months × 7 days × 24 hours.
    Rolling weighted average with weighted bootstrap from previous comparable slot.
    """

    def __init__(self, db: DatabaseConnection):
        self._db = db

    def update(self, dt: datetime, consumption_kwh: Decimal) -> None:
        """
        Verwerk een nieuwe verbruiksmeting in het leermodel.
        Process a new consumption measurement into the learning model.

        Args:
            dt:              tijdstip van de meting / measurement timestamp
            consumption_kwh: gemeten huisverbruik dit interval (kWh) / measured household
                             consumption this interval (kWh)
        """
        # Nulwaarden negeren — niet informatief voor het gemiddelde
        # Ignore zero values — not informative for the average
        if consumption_kwh <= 0:
            return

        month   = dt.month                      # 1..12
        dow     = dt.weekday()                  # 0=ma..6=zo / 0=Mon..6=Sun
        hour    = dt.hour                       # 0..23
        kwh     = float(consumption_kwh)

        try:
            with self._db.cursor() as cur:
                cur.execute(
                    "SELECT kwh_avg, kwh_min, kwh_max, sample_count "
                    "FROM consumption_learning "
                    "WHERE month_of_year = %(m)s AND day_of_week = %(d)s "
                    "AND hour_of_day = %(h)s",
                    {"m": month, "d": dow, "h": hour}
                )
                row = cur.fetchone()

            if row is None or row["sample_count"] == 0:
                # Eerste meting — bootstrap vanuit vorige maand of Gauss-fallback
                # First measurement — bootstrap from previous month or Gauss fallback
                bootstrap_avg, bootstrap_count = self._get_bootstrap(month, dow, hour)

                # Gewogen startwaarde: bootstrap × _BOOTSTRAP_WEIGHT + eerste meting
                # Weighted starting value: bootstrap × _BOOTSTRAP_WEIGHT + first measurement
                total_weight = bootstrap_count * _BOOTSTRAP_WEIGHT
                new_avg   = (bootstrap_avg * total_weight + kwh) / (total_weight + 1)
                new_min   = min(bootstrap_avg, kwh)
                new_max   = max(bootstrap_avg, kwh)
                new_count = 1

            else:
                # Bestaand slot bijwerken met rollend gewogen gemiddelde
                # Update existing slot with rolling weighted average
                old_avg   = float(row["kwh_avg"])
                old_count = row["sample_count"]
                new_avg   = (old_avg * old_count + kwh) / (old_count + 1)
                new_min   = min(float(row["kwh_min"]), kwh)
                new_max   = max(float(row["kwh_max"]), kwh)
                new_count = old_count + 1

            with self._db.cursor() as cur:
                cur.execute(
                    "INSERT INTO consumption_learning "
                    "(month_of_year, day_of_week, hour_of_day, "
                    "kwh_avg, kwh_min, kwh_max, sample_count) "
                    "VALUES (%(m)s, %(d)s, %(h)s, %(avg)s, %(mn)s, %(mx)s, %(c)s) "
                    "ON DUPLICATE KEY UPDATE "
                    "kwh_avg = %(avg)s, kwh_min = %(mn)s, "
                    "kwh_max = %(mx)s, sample_count = %(c)s",
                    {"m": month, "d": dow, "h": hour,
                     "avg": round(new_avg, 4),
                     "mn":  round(new_min, 4),
                     "mx":  round(new_max, 4),
                     "c":   new_count}
                )

            log.debug(
                f"[consumption_learner] {month}/{dow}/{hour}h "
                f"kwh={kwh:.4f} avg={new_avg:.4f} n={new_count}"
            )

        except Exception as e:
            log.warning(f"[consumption_learner] Update mislukt / Update failed: {e}")

    def predict(self, dt: datetime) -> float:
        """
        Voorspel het huisverbruik (kWh) voor een gegeven tijdstip.
        Predict household consumption (kWh) for a given timestamp.

        Returns de Gauss-fallback als er nog geen data beschikbaar is.
        Returns the Gauss fallback if no data is available yet.
        """
        month = dt.month
        dow   = dt.weekday()
        hour  = dt.hour

        try:
            with self._db.cursor() as cur:
                cur.execute(
                    "SELECT kwh_avg, sample_count FROM consumption_learning "
                    "WHERE month_of_year = %(m)s AND day_of_week = %(d)s "
                    "AND hour_of_day = %(h)s",
                    {"m": month, "d": dow, "h": hour}
                )
                row = cur.fetchone()

            if row and row["sample_count"] > 0:
                return float(row["kwh_avg"])

            # Geen data — bootstrap of Gauss-fallback
            # No data — bootstrap or Gauss fallback
            bootstrap_avg, _ = self._get_bootstrap(month, dow, hour)
            return bootstrap_avg

        except Exception as e:
            log.warning(f"[consumption_learner] Voorspelling mislukt / Prediction failed: {e}")
            return _gauss_fallback(hour)

    def _get_bootstrap(self, month: int, dow: int, hour: int) -> tuple[float, int]:
        """
        Haal het vorige vergelijkbare slot op (vorige maand, zelfde dag/uur).
        Als dat ook leeg is: gebruik de Gauss-curve als initiële waarde.

        Fetch the previous comparable slot (previous month, same day/hour).
        If that is also empty: use the Gauss curve as initial value.

        Returns (gemiddelde, sample_count) / Returns (average, sample_count).
        """
        prev_month = 12 if month == 1 else month - 1
        try:
            with self._db.cursor() as cur:
                cur.execute(
                    "SELECT kwh_avg, sample_count FROM consumption_learning "
                    "WHERE month_of_year = %(m)s AND day_of_week = %(d)s "
                    "AND hour_of_day = %(h)s AND sample_count > 0",
                    {"m": prev_month, "d": dow, "h": hour}
                )
                row = cur.fetchone()

            if row and row["sample_count"] > 0:
                return float(row["kwh_avg"]), row["sample_count"]

        except Exception:
            pass

        # Gauss-fallback als er helemaal geen historische data is
        # Gauss fallback if there is no historical data at all
        return _gauss_fallback(hour), 0
