# name:          solar_learner.py
# part of:       ha-energy-optimizer
# location:      /ha-energy-optimizer/ha-energy-optimizer/collectors/solar_learner.py
# part version:  p_v0.4
# altered:       2026-06-26
#
# Leert de relatie tussen instraling (W/m²) en werkelijke zonopbrengst (kWh)
# voor deze specifieke installatie. Wordt aangeroepen na elke meting.
# Gebruikt de solar_learning tabel als persistente opslag.
#
# Learns the relationship between irradiance (W/m²) and actual solar yield (kWh)
# for this specific installation. Called after each measurement.
# Uses the solar_learning table as persistent storage.

import logging
from datetime import datetime
from decimal import Decimal

from database.connection import DatabaseConnection

log = logging.getLogger(__name__)


class SolarLearner:
    """
    Leersysteem voor zon-efficiëntie.
    Slaat laagste en hoogste instraling/opbrengst-paren op per uur × week-blok.
    Na voldoende metingen kan lineaire interpolatie de verwachte opbrengst
    bepalen bij een gegeven instraling-voorspelling.

    Solar efficiency learning system.
    Stores lowest and highest irradiance/yield pairs per hour × week block.
    After sufficient measurements, linear interpolation can determine the
    expected yield for a given irradiance forecast.
    """

    def __init__(self, db: DatabaseConnection):
        self._db = db

    @staticmethod
    def week_block(dt: datetime) -> int:
        """
        Zet een datum om naar een blok van 2 weken (1..26).
        Converts a date to a 2-week block (1..26).
        """
        week = dt.isocalendar()[1]          # ISO weeknummer 1..53
        block = min(((week - 1) // 2) + 1, 26)
        return block

    def update(self, dt: datetime, solar_kwh: Decimal, irradiance_wm2: Decimal) -> None:
        """
        Verwerk een nieuwe meting in het leermodel.
        Process a new measurement into the learning model.

        Args:
            dt:             tijdstip van de meting / measurement timestamp
            solar_kwh:      gemeten zonopbrengst dit uur (kWh) / measured solar yield this hour (kWh)
            irradiance_wm2: gemeten instraling (W/m²) / measured irradiance (W/m²)
        """
        # Nulwaarden negeren — nacht of volledig bewolkt
        # Ignore zero values — night or fully overcast
        if solar_kwh <= 0 or irradiance_wm2 <= 0:
            return

        hour  = dt.hour
        block = self.week_block(dt)

        try:
            with self._db.cursor() as cur:
                # Huidige waarden ophalen / Fetch current values
                cur.execute(
                    "SELECT irradiance_low, irradiance_high, "
                    "solar_kwh_low, solar_kwh_high, sample_count "
                    "FROM solar_learning "
                    "WHERE hour_of_day = %(h)s AND week_block = %(b)s",
                    {"h": hour, "b": block}
                )
                row = cur.fetchone()

                if row is None or row["sample_count"] == 0:
                    # Eerste meting voor dit slot — bootstrap vanuit vorig blok
                    # First measurement for this slot — bootstrap from previous block
                    bootstrap = self._get_bootstrap(hour, block)

                    if bootstrap:
                        # Voeg bootstrap-gewicht toe (3×) zodat nieuw slot
                        # direct zinvolle startwaarden heeft.
                        # Add bootstrap weight (3×) so new slot has meaningful
                        # starting values immediately.
                        irr_low  = min(bootstrap["irradiance_low"],  float(irradiance_wm2))
                        irr_high = max(bootstrap["irradiance_high"], float(irradiance_wm2))
                        kwh_low  = min(bootstrap["solar_kwh_low"],   float(solar_kwh))
                        kwh_high = max(bootstrap["solar_kwh_high"],  float(solar_kwh))
                        count    = bootstrap["sample_count"] * 3 + 1
                    else:
                        # Geen bootstrap beschikbaar — Gauss-fallback via forecast_builder
                        # No bootstrap available — Gauss fallback via forecast_builder
                        irr_low  = float(irradiance_wm2)
                        irr_high = float(irradiance_wm2)
                        kwh_low  = float(solar_kwh)
                        kwh_high = float(solar_kwh)
                        count    = 1

                    cur.execute(
                        "INSERT INTO solar_learning "
                        "(hour_of_day, week_block, irradiance_low, irradiance_high, "
                        "solar_kwh_low, solar_kwh_high, sample_count) "
                        "VALUES (%(h)s, %(b)s, %(il)s, %(ih)s, %(kl)s, %(kh)s, %(c)s) "
                        "ON DUPLICATE KEY UPDATE "
                        "irradiance_low  = %(il)s, irradiance_high = %(ih)s, "
                        "solar_kwh_low   = %(kl)s, solar_kwh_high  = %(kh)s, "
                        "sample_count    = %(c)s",
                        {"h": hour, "b": block,
                         "il": irr_low, "ih": irr_high,
                         "kl": kwh_low, "kh": kwh_high,
                         "c": count}
                    )
                else:
                    # Bestaand slot bijwerken — min/max uitbreiden
                    # Update existing slot — extend min/max range
                    new_irr_low  = min(float(row["irradiance_low"]),  float(irradiance_wm2))
                    new_irr_high = max(float(row["irradiance_high"]), float(irradiance_wm2))
                    new_kwh_low  = min(float(row["solar_kwh_low"]),   float(solar_kwh))
                    new_kwh_high = max(float(row["solar_kwh_high"]),  float(solar_kwh))
                    new_count    = row["sample_count"] + 1

                    cur.execute(
                        "UPDATE solar_learning SET "
                        "irradiance_low = %(il)s, irradiance_high = %(ih)s, "
                        "solar_kwh_low  = %(kl)s, solar_kwh_high  = %(kh)s, "
                        "sample_count   = %(c)s "
                        "WHERE hour_of_day = %(h)s AND week_block = %(b)s",
                        {"il": new_irr_low, "ih": new_irr_high,
                         "kl": new_kwh_low, "kh": new_kwh_high,
                         "c": new_count,
                         "h": hour, "b": block}
                    )

                log.debug(
                    f"[solar_learner] uur={hour} blok={block} "
                    f"irr={irradiance_wm2:.1f}W/m² kwh={solar_kwh:.4f} "
                    f"count={row['sample_count'] + 1 if row else 1}"
                )

        except Exception as e:
            log.warning(f"[solar_learner] Update mislukt / Update failed: {e}")

    def predict(self, dt: datetime, irradiance_wm2: float) -> float:
        """
        Voorspel de zonopbrengst (kWh) voor een gegeven instraling en tijdstip.
        Predict solar yield (kWh) for a given irradiance and timestamp.

        Returns 0.0 als er nog geen data beschikbaar is.
        Returns 0.0 if no data is available yet.
        """
        hour  = dt.hour
        block = self.week_block(dt)

        try:
            with self._db.cursor() as cur:
                cur.execute(
                    "SELECT irradiance_low, irradiance_high, "
                    "solar_kwh_low, solar_kwh_high, sample_count "
                    "FROM solar_learning "
                    "WHERE hour_of_day = %(h)s AND week_block = %(b)s",
                    {"h": hour, "b": block}
                )
                row = cur.fetchone()

            if not row or row["sample_count"] == 0:
                return 0.0

            irr_low  = float(row["irradiance_low"])
            irr_high = float(row["irradiance_high"])
            kwh_low  = float(row["solar_kwh_low"])
            kwh_high = float(row["solar_kwh_high"])

            if irr_high <= irr_low:
                # Enkel datapunt — gebruik de bekende waarde
                # Single data point — use the known value
                return kwh_low

            # Lineaire interpolatie, geclamped op [0, 1]
            # Linear interpolation, clamped to [0, 1]
            factor = (irradiance_wm2 - irr_low) / (irr_high - irr_low)
            factor = max(0.0, min(1.0, factor))
            return kwh_low + factor * (kwh_high - kwh_low)

        except Exception as e:
            log.warning(f"[solar_learner] Voorspelling mislukt / Prediction failed: {e}")
            return 0.0

    def _get_bootstrap(self, hour: int, block: int) -> dict | None:
        """
        Haal het vorige vergelijkbare slot op als bootstrap-startwaarde.
        Fetch the previous comparable slot as bootstrap starting value.
        Vorig blok = block - 1, met wrap-around van 1 naar 26.
        Previous block = block - 1, with wrap-around from 1 to 26.
        """
        prev_block = 26 if block == 1 else block - 1
        try:
            with self._db.cursor() as cur:
                cur.execute(
                    "SELECT irradiance_low, irradiance_high, "
                    "solar_kwh_low, solar_kwh_high, sample_count "
                    "FROM solar_learning "
                    "WHERE hour_of_day = %(h)s AND week_block = %(b)s "
                    "AND sample_count > 0",
                    {"h": hour, "b": prev_block}
                )
                return cur.fetchone()
        except Exception:
            return None
