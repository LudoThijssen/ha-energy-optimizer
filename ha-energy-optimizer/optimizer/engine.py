# optimizer/engine.py
#
# Optimization engine — orchestrates the full planning cycle.
# Optimalisatie-engine — orkestreert de volledige planningscyclus.
#
# Two phases / Twee fasen:
#   1. Evening planning (plan_evening): day balance calculation for tomorrow.
#      Avondplanning (plan_evening): dagbalansberekening voor morgen.
#   2. Hourly execution (run): real-time decision per hour.
#      Uurlijkse uitvoering (run): real-time beslissing per uur.

import logging
from datetime import datetime, timedelta, date
from decimal import Decimal

from database.connection import DatabaseConnection
from database.models import OptimizerSlot
from database.repository import (
    PriceRepository, WeatherRepository,
    BatteryRepository, OptimizerRepository,
)
from config.config import AppConfig
from reporter.reporter import Reporter
from .models import HourForecast, ScheduleSlot
from .strategy import (
    Strategy, DayPriceStats, SolarOutlook, DayBalancePlan,
    build_strategy_from_db,
)

logger = logging.getLogger(__name__)

# Fallback hourly consumption when no historical data is available.
# Terugvalwaarde voor uurverbruik als er geen historische gegevens zijn.
_FALLBACK_CONSUMPTION_KW = Decimal("0.5")

# Irradiance (W/m²) → estimated panel output (kW) conversion factor.
# Omrekeningsfactor straling (W/m²) → geschatte paneelopbrengst (kW).
_WM2_TO_KW_FACTOR = Decimal("0.0008")


class OptimizerEngine:
    """
    Orchestrates the full optimization cycle.
    Orkestreert de volledige optimalisatiecyclus.
    """

    def __init__(self, db: DatabaseConnection, reporter: Reporter, config: AppConfig):
        self._db             = db
        self._reporter       = reporter
        self._config         = config
        self._price_repo     = PriceRepository(db)
        self._weather_repo   = WeatherRepository(db)
        self._battery_repo   = BatteryRepository(db)
        self._optimizer_repo = OptimizerRepository(db)

        # Day balance plan is calculated in the evening and held in memory
        # until the next evening. It is also persisted to the schedule table.
        # Dagbalansplan wordt 's avonds berekend en in geheugen gehouden
        # tot de volgende avond. Het wordt ook opgeslagen in de schedule-tabel.
        self._day_balance_plan: DayBalancePlan | None = None

    # ── Evening planning / Avondplanning ─────────────────────────────────────

    def plan_evening(self) -> None:
        """
        Evening planning run — called once per day (configurable time).
        Avondplanningsrun — eenmaal per dag aangeroepen (instelbaar tijdstip).

        Calculates the day balance for tomorrow and selects the best hours
        tonight for discharging to make room for solar production.
        Berekent de dagbalans voor morgen en selecteert de beste uren
        vanavond voor ontladen om ruimte te maken voor de zonopbrengst.
        """
        logger.info("[optimizer] Evening planning started / Avondplanning gestart")
        try:
            strategy, day_stats, solar_outlook = build_strategy_from_db(self._db)

            if not solar_outlook:
                self._reporter.warning(
                    "No solar outlook available for evening planning — skipped. / "
                    "Geen zonnerverwachting beschikbaar voor avondplanning — overgeslagen.",
                    category="optimizer",
                )
                return

            battery = self._battery_repo.get_latest()
            current_soc = battery.soc_pct if battery else Decimal("50")

            # Build list of tonight's prices for selecting best discharge hours.
            # Bouw lijst van prijzen vanavond voor selectie beste ontlaaduren.
            tonight_prices = self._get_tonight_prices_excl(strategy)

            self._day_balance_plan = strategy.plan_day_balance(
                current_soc_pct=current_soc,
                solar_outlook=solar_outlook,
                today_prices_excl=tonight_prices,
            )

            logger.info(f"[optimizer] Day balance plan: {self._day_balance_plan.reason}")
            self._reporter.info(
                self._day_balance_plan.reason,
                category="optimizer",
            )

        except Exception as e:
            self._reporter.error(
                f"Evening planning error: {e} / Avondplanning fout: {e}",
                category="optimizer",
            )
            logger.exception("[optimizer] Evening planning failed / Avondplanning mislukt")

    # ── Hourly optimization run / Uurlijkse optimalisatierun ─────────────────

    def run(self) -> None:
        """
        Hourly run — calculates and saves the 24-hour schedule.
        Uurlijkse run — berekent en slaat het 24-uurs schema op.
        """
        logger.info("[optimizer] Starting optimization run / Optimalisatierun gestart")
        try:
            strategy, day_stats, solar_outlook = build_strategy_from_db(self._db)

            if not day_stats:
                self._reporter.warning(
                    "No price data available — optimizer skipped. / "
                    "Geen prijsdata beschikbaar — optimizer overgeslagen.",
                    category="optimizer",
                )
                return

            self._log_day_stats(day_stats, strategy)

            forecasts = self._build_forecasts()
            if not forecasts:
                self._reporter.warning(
                    "No hourly forecasts available — optimizer skipped. / "
                    "Geen uurprognoses beschikbaar — optimizer overgeslagen.",
                    category="optimizer",
                )
                return

            slots, all_notifications = self._calculate(
                forecasts, strategy, day_stats, solar_outlook
            )

            # Save schedule to database / Sla schema op in database
            self._optimizer_repo.save_schedule(self._to_db_slots(slots))

            # Send any notifications to Home Assistant / Stuur meldingen naar HA
            self._send_notifications(all_notifications)

            self._report_summary(slots)

        except Exception as e:
            self._reporter.error(
                f"Optimizer error: {e} / Optimizer fout: {e}",
                category="optimizer",
            )
            logger.exception("[optimizer] Unexpected error / Onverwachte fout")

    # ── Forecast building / Prognose-opbouw ──────────────────────────────────

    def _build_forecasts(self) -> list[HourForecast]:
        """
        Build 24-hour forecasts combining price, weather and battery data.
        Bouw 24-uurs prognoses op basis van prijs-, weer- en batterijgegevens.
        """
        now = datetime.now().replace(minute=0, second=0, microsecond=0)

        # Load prices for today and tomorrow / Laad prijzen voor vandaag en morgen
        prices = {}
        for target_date in [date.today(), date.today() + timedelta(days=1)]:
            with self._db.cursor() as cur:
                cur.execute("""
                    SELECT price_hour, price_per_kwh FROM energy_prices
                    WHERE DATE(price_hour) = %(d)s AND energy_type = 'electricity'
                    ORDER BY price_hour
                """, {"d": target_date})
                for row in cur.fetchall():
                    prices[row["price_hour"]] = Decimal(str(row["price_per_kwh"]))

        # Load weather forecasts / Laad weersvoorspellingen
        weather = {
            w.forecast_for: w
            for w in self._weather_repo.get_forecast(now, hours=24)
        }

        # Current battery state / Huidige batterijstatus
        battery = self._battery_repo.get_latest()
        current_soc = battery.soc_pct if battery else Decimal("50")

        forecasts = []
        for offset in range(24):
            hour      = now + timedelta(hours=offset)
            price     = prices.get(hour)
            weather_h = weather.get(hour)

            if not price:
                continue  # Skip hours without price data / Sla uren zonder prijs over

            solar_kw = Decimal("0")
            if weather_h and weather_h.solar_irradiance_wm2:
                solar_kw = (
                    weather_h.solar_irradiance_wm2 * _WM2_TO_KW_FACTOR
                ).quantize(Decimal("0.001"))

            forecasts.append(HourForecast(
                hour=hour,
                price_per_kwh=price,
                solar_kw=solar_kw,
                consumption_kw=_FALLBACK_CONSUMPTION_KW,
                soc_pct=current_soc,
            ))

        return forecasts

    def _get_tonight_prices_excl(self, strategy: Strategy) -> list:
        """
        Get remaining hours' prices for tonight (for day balance planning).
        Haal resterende uurprijzen van vanavond op (voor dagbalansplanning).
        """
        now = datetime.now().replace(minute=0, second=0, microsecond=0)
        midnight = now.replace(hour=23, minute=59)

        with self._db.cursor() as cur:
            cur.execute("""
                SELECT price_hour, price_per_kwh FROM energy_prices
                WHERE price_hour >= %(now)s
                  AND price_hour <= %(midnight)s
                  AND energy_type = 'electricity'
                ORDER BY price_hour
            """, {"now": now, "midnight": midnight})
            rows = cur.fetchall()

        return [
            (row["price_hour"], strategy._to_excl(Decimal(str(row["price_per_kwh"]))))
            for row in rows
        ]

    # ── Optimization loop / Optimalisatielus ─────────────────────────────────

    def _calculate(
        self,
        forecasts: list[HourForecast],
        strategy: Strategy,
        day_stats: DayPriceStats,
        solar_outlook: SolarOutlook | None,
    ) -> tuple[list[ScheduleSlot], list[str]]:
        """
        Apply strategy to each forecast hour, tracking SoC.
        Pas strategie toe op elk prognose-uur, met bijhouden van laadtoestand.
        """
        slots             = []
        all_notifications = []
        soc               = forecasts[0].soc_pct if forecasts else Decimal("50")

        # Get latest battery temperature for derating.
        # Haal laatste batterijtemperatuur op voor vermogensverlaging.
        battery = self._battery_repo.get_latest()
        battery_temp = battery.temperature_c if battery else None

        for forecast in forecasts:
            forecast.soc_pct = soc

            action, power, reason, notifications = strategy.decide(
                current_price=forecast.price_per_kwh,
                export_price=forecast.price_per_kwh,   # TODO: separate export price feed
                solar_kw=forecast.solar_kw,
                consumption_kw=forecast.consumption_kw,
                soc_pct=soc,
                day_stats=day_stats,
                battery_temp_c=battery_temp,
                solar_outlook=solar_outlook,
                day_balance_plan=self._day_balance_plan,
            )

            saving = strategy.calc_saving(
                action, power, strategy._to_excl(forecast.price_per_kwh)
            )

            slots.append(ScheduleSlot(
                hour=forecast.hour,
                action=action,
                target_power_kw=power,
                target_soc_pct=soc,
                expected_saving=saving,
                reason=reason,
            ))

            all_notifications.extend(notifications)

            # Update SoC for next hour / Werk laadtoestand bij voor volgend uur
            soc = self._estimate_next_soc(soc, action, power, strategy)

        return slots, all_notifications

    def _estimate_next_soc(
        self,
        current_soc: Decimal,
        action: str,
        power_kw: Decimal,
        strategy: Strategy,
    ) -> Decimal:
        """
        Estimate SoC after one hour of the given action.
        Schat laadtoestand na één uur van de opgegeven actie.
        """
        kwh = strategy.usable_capacity_kwh
        if action == "charge":
            delta = power_kw * strategy.efficiency / kwh * 100
            return min(current_soc + delta, strategy.max_soc)
        elif action == "discharge":
            delta = power_kw / strategy.efficiency / kwh * 100
            return max(current_soc - delta, strategy.min_soc)
        return current_soc

    # ── Persistence / Persistentie ────────────────────────────────────────────

    def _to_db_slots(self, slots: list[ScheduleSlot]) -> list[OptimizerSlot]:
        return [
            OptimizerSlot(
                schedule_for=s.hour,
                action=s.action,
                target_power_kw=s.target_power_kw,
                target_soc_pct=s.target_soc_pct,
                expected_saving=s.expected_saving,
                reason=s.reason,
            )
            for s in slots
        ]

    # ── Notifications / Meldingen ─────────────────────────────────────────────

    def _send_notifications(self, notifications: list[str]) -> None:
        """
        Group negative price notifications into one summary message.
        Groepeer negatieve prijsmeldingen in één samenvattend bericht.
        """
        if not notifications:
            return

        # Separate negative price notifications from others
        # Scheid negatieve prijsmeldingen van overige meldingen
        negative_hours = []
        other_msgs = []
        solar_surplus_values = []

        for msg in notifications:
            if "negative" in msg.lower() or "negatief" in msg.lower():
                # Extract price and hour info from message
                # Extraheer prijs- en uurinformatie uit het bericht
                import re
                price_match = re.search(r'\((-?\d+\.\d+)\s*€/kWh', msg)
                solar_match = re.search(r'Solar surplus[:\s]+(-?\d+\.?\d*)\s*kW', msg, re.IGNORECASE)
                if price_match:
                    negative_hours.append(float(price_match.group(1)))
                if solar_match:
                    solar_surplus_values.append(float(solar_match.group(1)))
            elif "very low" in msg.lower() or "zeer laag" in msg.lower():
                # Low price warning — include once
                if not any("very low" in m.lower() for m in other_msgs):
                    other_msgs.append(msg)
            else:
                other_msgs.append(msg)

        # Build summary for negative prices
        # Bouw samenvatting voor negatieve prijzen
        if negative_hours:
            prices_str = " | ".join(
                f"{i+1}e uur: {p*100:.2f}ct"
                for i, p in enumerate(negative_hours)
            )
            avg_solar = sum(solar_surplus_values) / len(solar_surplus_values) if solar_surplus_values else 0
            summary = (
                f"⚡ {len(negative_hours)} uur negatieve exportprijs: {prices_str} (ct/kWh)\n"
                f"Zet nu aan: boiler / wasmachine / vaatwasser / laadpaal."
            )
            if avg_solar > 0:
                summary += f" Zonne-overschot: gem. {avg_solar:.2f} kW."
            self._reporter.warning(summary, category="solar_export")
            logger.warning(f"[optimizer] Notification: {summary[:120]}")

        # Send remaining unique notifications
        # Stuur overige unieke meldingen
        seen = set()
        for msg in other_msgs:
            key = msg[:60]
            if key not in seen:
                seen.add(key)
                self._reporter.warning(msg, category="solar_export")
                logger.warning(f"[optimizer] Notification: {msg[:120]}")

    # ── Reporting / Rapportage ────────────────────────────────────────────────

    def _log_day_stats(self, day_stats: DayPriceStats, strategy: Strategy) -> None:
        spread = (
            day_stats.most_expensive_today / day_stats.cheapest_today
            if day_stats.cheapest_today > 0 else Decimal("1")
        )
        charge_ok = spread >= strategy.required_spread_factor
        logger.info(
            f"[optimizer] Today excl. VAT: "
            f"min {day_stats.cheapest_today:.4f} / "
            f"max {day_stats.most_expensive_today:.4f} / "
            f"avg {day_stats.average_today:.4f} €/kWh | "
            f"spread {spread:.2f}× (grid charge requires ≥{strategy.required_spread_factor}×) | "
            f"grid charging: {'yes / ja' if charge_ok else 'no / nee'}"
        )

    def _report_summary(self, slots: list[ScheduleSlot]) -> None:
        charges    = sum(1 for s in slots if s.action == "charge")
        discharges = sum(1 for s in slots if s.action == "discharge")
        idles      = sum(1 for s in slots if s.action == "idle")
        saving     = sum(s.expected_saving for s in slots)
        msg = (
            f"Schedule: {len(slots)}h — "
            f"{charges} charge/laden, {discharges} discharge/ontladen, {idles} idle. "
            f"Expected saving / Verwachte besparing: €{saving:.2f}"
        )
        self._reporter.info(msg, category="optimizer")
        logger.info(f"[optimizer] {msg}")
