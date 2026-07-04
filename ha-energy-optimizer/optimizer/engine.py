# name:          engine.py
# part of:       ha-energy-optimizer
# location:      /ha-energy-optimizer/ha-energy-optimizer/optimizer/engine.py
# part version:  p_v0.7
# altered:       2026-07-03
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
from .decision_engine import build_decision_engine
from translations.translator import build_translator

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
        self._tr             = build_translator(db)

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
        logger.info("[optimizer] Avondplanning gestart")
        try:
            strategy, day_stats, solar_outlook = build_strategy_from_db(self._db)

            if not solar_outlook:
                self._reporter.warning(
                    "Geen zonverwachting beschikbaar voor avondplanning — overgeslagen.",
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
                f"Avondplanning fout: {e}",
                category="optimizer",
            )
            logger.exception("[optimizer] Avondplanning mislukt")

    # ── Hourly optimization run / Uurlijkse optimalisatierun ─────────────────

    def run(self) -> None:
        """
        Hourly run — rolling horizon recalculation using actual battery SoC.
        Uurlijkse run — rolling horizon herberekening met werkelijke batterij-SoC.

        Each run reads the current actual SoC from battery_status and uses it
        as the starting point, correcting for any deviation from the previous
        plan. Already-executed slots are preserved in the database.

        Elke run leest de actuele SoC uit battery_status en gebruikt die als
        startpunt, waarmee afwijkingen van het vorige plan worden gecorrigeerd.
        Al uitgevoerde slots blijven bewaard in de database.
        """
        logger.info("[optimizer] Rolling-horizon run gestart")
        try:
            strategy, day_stats, solar_outlook = build_strategy_from_db(self._db)

            if not day_stats:
                self._reporter.warning(
                    "Geen prijsdata beschikbaar — optimizer overgeslagen.",
                    category="optimizer",
                )
                return

            self._log_day_stats(day_stats, strategy)

            # ── Rolling horizon: read actual SoC ─────────────────────────────
            # Lees werkelijke SoC als startpunt voor herberekening
            battery = self._battery_repo.get_latest()
            actual_soc = battery.soc_pct if battery else None

            # Compare actual vs planned SoC and log if significant deviation
            # Vergelijk werkelijk vs gepland SoC en log bij grote afwijking
            if actual_soc is not None:
                self._check_soc_deviation(actual_soc, strategy)

            # Compare last hour's forecast vs measured reality
            # Vergelijk prognose vorig uur met gemeten werkelijkheid
            self._check_forecast_deviation(strategy)

            forecasts = self._build_forecasts(actual_soc=actual_soc)
            if not forecasts:
                self._reporter.warning(
                    "Geen uurprognoses beschikbaar — optimizer overgeslagen.",
                    category="optimizer",
                )
                return

            # ── Nieuwe beslislogica / New decision logic ──────────────────────
            # Gebruik DecisionEngine (fase 3) als primaire beslisser.
            # Valt terug op de oude strategy._calculate() als er een fout optreedt.
            # Use DecisionEngine (phase 3) as primary decision maker.
            # Falls back to old strategy._calculate() if an error occurs.
            try:
                decision_engine = build_decision_engine(self._db)
                battery_temp = (
                    self._battery_repo.get_latest().temperature_c
                    if self._battery_repo.get_latest() else None
                )
                slots = decision_engine.run(
                    forecasts=forecasts,
                    battery_temp_c=battery_temp,
                )
                all_notifications = []
                logger.info("[optimizer] DecisionEngine fase 3 actief")
            except Exception as de_err:
                logger.warning(
                    f"[optimizer] DecisionEngine mislukt, terugval op strategie: {de_err}"
                )
                slots, all_notifications = self._calculate(
                    forecasts, strategy, day_stats, solar_outlook
                )

            # Save only future (unexecuted) slots — preserve executed history
            # Sla alleen toekomstige (niet-uitgevoerde) slots op — bewaar uitgevoerde geschiedenis
            self._optimizer_repo.save_schedule(self._to_db_slots(slots))

            # Send any notifications to Home Assistant / Stuur meldingen naar HA
            self._send_notifications(all_notifications)

            self._report_summary(slots)

        except Exception as e:
            self._reporter.error(
                f"Optimizer fout: {e}",
                category="optimizer",
            )
            logger.exception("[optimizer] Onverwachte fout")

    # ── Forecast building / Prognose-opbouw ──────────────────────────────────

    def _build_forecasts(
        self, actual_soc: Decimal | None = None
    ) -> list[HourForecast]:
        """
        Build 48-hour forecasts combining price, weather and learning model data.
        Uses SolarLearner and ConsumptionLearner when data is available,
        falls back to profile/irradiance/Gauss when not.

        Bouw 48-uurs prognoses op basis van prijs-, weer- en leermodelgegevens.
        Gebruikt SolarLearner en ConsumptionLearner als data beschikbaar is,
        valt terug op profiel/straling/Gauss als dat niet het geval is.
        """
        from collectors.solar_learner import SolarLearner
        from collectors.consumption_learner import ConsumptionLearner

        solar_learner       = SolarLearner(self._db)
        consumption_learner = ConsumptionLearner(self._db)

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
            for w in self._weather_repo.get_forecast(now, hours=48)
        }

        # Rolling horizon: use actual SoC if available, otherwise fall back to DB
        # Rolling horizon: gebruik werkelijke SoC indien beschikbaar, anders DB
        if actual_soc is not None:
            current_soc = actual_soc
            logger.debug(
                f"[optimizer] Rolling horizon: werkelijke SoC {current_soc:.1f}% als startpunt gebruikt"
            )
        else:
            battery = self._battery_repo.get_latest()
            current_soc = battery.soc_pct if battery else Decimal("50")
            logger.debug(
                f"[optimizer] Geen werkelijke SoC beschikbaar, DB-waarde {current_soc:.1f}% gebruikt"
            )

        # Load legacy solar/consumption profiles as fallback
        # Laad legacy zon/verbruiksprofielen als terugval
        solar_profile = {}
        consumption_profile = {}
        with self._db.cursor() as cur:
            cur.execute("""
                SELECT hour_of_day, avg_kw
                FROM solar_profile
                WHERE month = %(month)s
            """, {"month": now.month})
            for row in cur.fetchall():
                solar_profile[row["hour_of_day"]] = Decimal(str(row["avg_kw"]))

            cur.execute("""
                SELECT hour_of_day, avg_kw
                FROM consumption_profile
                WHERE day_of_week = %(dow)s
            """, {"dow": now.weekday()})
            for row in cur.fetchall():
                consumption_profile[row["hour_of_day"]] = Decimal(str(row["avg_kw"]))

        forecasts = []
        for offset in range(48):
            hour      = now + timedelta(hours=offset)
            price     = prices.get(hour)
            weather_h = weather.get(hour)
            if not price:
                continue

            # ── Solar forecast / Zonverwachting ─────────────────────────────
            # Prioriteit: 1) SolarLearner 2) legacy profiel 3) irradiance 4) 0
            # Priority:   1) SolarLearner 2) legacy profile 3) irradiance 4) 0
            solar_kw = Decimal("0")

            if weather_h and weather_h.solar_irradiance_wm2:
                irr = float(weather_h.solar_irradiance_wm2)
                learned_kwh = solar_learner.predict(hour, irr)
                if learned_kwh > 0:
                    # Leermodel geeft kWh per uur — direct bruikbaar
                    # Learning model gives kWh per hour — directly usable
                    solar_kw = Decimal(str(learned_kwh)).quantize(Decimal("0.001"))
                    logger.debug(
                        f"[optimizer] {hour.strftime('%H:%M')} solar from learner: "
                        f"{solar_kw} kW (irr={irr:.0f} W/m²)"
                    )
                else:
                    # Leermodel heeft nog geen data — terugval op irradiance factor
                    # Learning model has no data yet — fall back to irradiance factor
                    solar_kw = (
                        weather_h.solar_irradiance_wm2 * _WM2_TO_KW_FACTOR
                    ).quantize(Decimal("0.001"))

            elif solar_profile.get(hour.hour, Decimal("0")) > 0:
                # Geen weerdata — gebruik legacy profiel met bewolkingscorrectie
                # No weather data — use legacy profile with cloud correction
                profile_kw = solar_profile[hour.hour]
                if weather_h and weather_h.cloud_cover_pct is not None:
                    cloud_factor = max(
                        Decimal("0.15"),
                        Decimal("1") - weather_h.cloud_cover_pct / Decimal("100")
                    )
                    solar_kw = (profile_kw * cloud_factor).quantize(Decimal("0.001"))
                else:
                    solar_kw = profile_kw

            # ── Consumption forecast / Verbruiksverwachting ─────────────────
            # Prioriteit: 1) ConsumptionLearner 2) legacy profiel 3) fallback
            # Priority:   1) ConsumptionLearner 2) legacy profile 3) fallback
            learned_cons = consumption_learner.predict(hour)
            if learned_cons > 0:
                # Leermodel geeft kWh per 5-min interval — omrekenen naar kW (× 12)
                # Learning model gives kWh per 5-min interval — convert to kW (× 12)
                # kWh/interval × 12 intervals/uur = kWh/uur = kW
                consumption_kw = Decimal(str(learned_cons * 12)).quantize(
                    Decimal("0.001")
                )
                logger.debug(
                    f"[optimizer] {hour.strftime('%H:%M')} consumption from learner: "
                    f"{consumption_kw} kW"
                )
            else:
                consumption_kw = consumption_profile.get(
                    hour.hour, _FALLBACK_CONSUMPTION_KW
                )

            forecasts.append(HourForecast(
                hour=hour,
                price_per_kwh=price,
                solar_kw=solar_kw,
                consumption_kw=consumption_kw,
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

    def _check_soc_deviation(
        self, actual_soc: Decimal, strategy: Strategy
    ) -> None:
        """
        Compare actual SoC with the planned SoC for this hour.
        Log a warning if the deviation exceeds the threshold.

        Vergelijk werkelijke SoC met de geplande SoC voor dit uur.
        Log een waarschuwing als de afwijking de drempel overschrijdt.
        """
        _DEVIATION_THRESHOLD_PCT = Decimal("10")  # warn above 10% deviation

        try:
            now = datetime.now().replace(minute=0, second=0, microsecond=0)
            with self._db.cursor() as cur:
                cur.execute("""
                    SELECT target_soc_pct FROM optimizer_schedule
                    WHERE schedule_for = %(hour)s
                    LIMIT 1
                """, {"hour": now})
                row = cur.fetchone()

            if row and row["target_soc_pct"] is not None:
                planned_soc = Decimal(str(row["target_soc_pct"]))
                deviation = abs(actual_soc - planned_soc)
                logger.info(
                    f"[optimizer] Rolling horizon: werkelijke SoC {actual_soc:.1f}% vs gepland {planned_soc:.1f}% (afwijking {deviation:.1f}%)"
                )
                if deviation >= _DEVIATION_THRESHOLD_PCT:
                    self._reporter.warning(
                        f"Rolling horizon: SoC-afwijking {deviation:.1f}% — "
                        f"werkelijk {actual_soc:.1f}% vs gepland {planned_soc:.1f}%. "
                        f"Schema herberekend vanuit werkelijke SoC.",
                        category="optimizer",
                    )
            else:
                logger.debug(
                    f"[optimizer] No planned SoC for {now} — "
                    f"eerste run of nieuwe installatie"
                )
        except Exception as e:
            logger.debug(f"[optimizer] SoC deviation check failed (non-critical): {e}")

    def _check_forecast_deviation(self, strategy: Strategy) -> None:
        """
        Compare last hour planned values with actual measured values.
        Send warning if solar or consumption deviates significantly.

        Vergelijk geplande waarden vorig uur met werkelijk gemeten waarden.
        Stuur waarschuwing als zon of verbruik significant afwijkt.
        """
        _SOLAR_DEVIATION_KW       = Decimal("0.5")
        _CONSUMPTION_DEVIATION_KW = Decimal("0.5")

        try:
            from datetime import timedelta
            last_hour = datetime.now().replace(
                minute=0, second=0, microsecond=0
            ) - timedelta(hours=1)

            with self._db.cursor() as cur:
                cur.execute(
                    "SELECT expected_solar_kw, expected_consumption_kw "
                    "FROM optimizer_schedule "
                    "WHERE schedule_for = %(hour)s LIMIT 1",
                    {"hour": last_hour}
                )
                planned = cur.fetchone()

            if not planned:
                return

            planned_solar = Decimal(str(planned["expected_solar_kw"] or 0))
            planned_cons  = Decimal(str(planned["expected_consumption_kw"] or 0))

            solar_actual = self._solar_repo.get_average_power_for_hour(last_hour)
            cons_actual  = self._consumption_repo.get_average_power_for_hour(last_hour)

            deviations = []

            if solar_actual is not None and planned_solar > Decimal("0.1"):
                solar_dev = abs(solar_actual - planned_solar)
                if solar_dev >= _SOLAR_DEVIATION_KW:
                    pct = (solar_dev / planned_solar * 100).quantize(Decimal("1"))
                    dir_nl = "lager" if solar_actual < planned_solar else "hoger"
                    dir_en = "lower" if solar_actual < planned_solar else "higher"
                    deviations.append(
                        f"Zonopbrengst {last_hour.strftime('%H:%M')}: "
                        f"verwacht {planned_solar:.2f} kW, "
                        f"gemeten {solar_actual:.2f} kW ({pct}% {dir_nl}). "
                        f"Solar: expected {planned_solar:.2f} kW, "
                        f"actual {solar_actual:.2f} kW ({pct}% {dir_en})."
                    )

            if cons_actual is not None and planned_cons > Decimal("0.1"):
                cons_dev = abs(cons_actual - planned_cons)
                if cons_dev >= _CONSUMPTION_DEVIATION_KW:
                    pct = (cons_dev / planned_cons * 100).quantize(Decimal("1"))
                    dir_nl = "lager" if cons_actual < planned_cons else "hoger"
                    dir_en = "lower" if cons_actual < planned_cons else "higher"
                    deviations.append(
                        f"Verbruik {last_hour.strftime('%H:%M')}: "
                        f"verwacht {planned_cons:.2f} kW, "
                        f"gemeten {cons_actual:.2f} kW ({pct}% {dir_nl}). "
                        f"Consumption: expected {planned_cons:.2f} kW, "
                        f"actual {cons_actual:.2f} kW ({pct}% {dir_en})."
                    )

            if deviations:
                msg = (
                    "Afwijking verwachting vs werkelijkheid:\n"
                    + "\n".join(deviations)
                )
                self._reporter.warning(msg, category="deviation")
                logger.info(f"[optimizer] Forecast deviation: {msg}")
            else:
                logger.debug(
                    f"[optimizer] Forecast check {last_hour.strftime('%H:%M')}: "
                    "no significant deviation / geen significante afwijking"
                )

        except Exception as e:
            logger.debug(f"[optimizer] Forecast deviation check failed (non-critical): {e}")

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

        # Track the price of the most recent charge action, so the
        # anti-cycling check can avoid discharging energy that was
        # just charged at a similar price.
        # Houd de prijs van de meest recente laadactie bij, zodat de
        # anti-cycling-check vermijdt dat energie wordt ontladen die
        # net tegen een vergelijkbare prijs geladen is.
        last_charge_price_excl = None

        # Get latest battery temperature for derating.
        # Haal laatste batterijtemperatuur op voor vermogensverlaging.
        battery = self._battery_repo.get_latest()
        battery_temp = battery.temperature_c if battery else None

        for forecast in forecasts:
            forecast.soc_pct = soc

            action, power, reason, notifications, is_solar_charge = strategy.decide(
                current_price=forecast.price_per_kwh,
                export_price=forecast.price_per_kwh,   # TODO: separate export price feed
                solar_kw=forecast.solar_kw,
                consumption_kw=forecast.consumption_kw,
                soc_pct=soc,
                day_stats=day_stats,
                battery_temp_c=battery_temp,
                solar_outlook=solar_outlook,
                day_balance_plan=self._day_balance_plan,
                last_charge_price_excl=last_charge_price_excl,
            )

            price_excl_now = strategy._to_excl(forecast.price_per_kwh)
            saving = strategy.calc_saving(action, power, price_excl_now, is_solar_charge)
            cost   = strategy.calc_cost(action, power, price_excl_now, is_solar_charge)

            slots.append(ScheduleSlot(
                hour=forecast.hour,
                action=action,
                target_power_kw=power,
                target_soc_pct=soc,
                expected_saving=saving,
                expected_cost=cost,
                reason=reason,
                expected_solar_kw=forecast.solar_kw,
                expected_consumption_kw=forecast.consumption_kw,
                expected_price=forecast.price_per_kwh,
            ))

            all_notifications.extend(
                (forecast.hour, msg) for msg in notifications
            )

            # Track last charge price for anti-cycling check
            # Laatste laadprijs bijhouden voor anti-cycling-check
            if action == "charge":
                last_charge_price_excl = strategy._to_excl(forecast.price_per_kwh)
            elif action == "discharge":
                # After discharging, the battery is no longer holding
                # energy from that charge — reset so future hours can
                # discharge based on their own merits.
                # Na ontladen bevat de batterij niet meer de energie van
                # die lading — resetten zodat toekomstige uren op eigen
                # merites kunnen ontladen.
                last_charge_price_excl = None

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
        # self_consume = battery full, surplus exported — SoC unchanged
        # self_consume = batterij vol, overschot teruggeleverd — SoC ongewijzigd
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
                expected_cost=s.expected_cost,
                reason=s.reason,
                expected_solar_kw=s.expected_solar_kw,
                expected_consumption_kw=s.expected_consumption_kw,
                expected_price=s.expected_price,
            )
            for s in slots
        ]

    # ── Notifications / Meldingen ─────────────────────────────────────────────

    def _send_notifications(self, notifications: list) -> None:
        """
        Group negative price notifications into one summary message.
        Groepeer negatieve prijsmeldingen in één samenvattend bericht.
        """
        if not notifications:
            return

        # Separate negative price notifications from others
        # Scheid negatieve prijsmeldingen van overige meldingen
        negative_hours = []
        negative_times = []
        other_msgs = []
        solar_surplus_values = []

        for item in notifications:
            # Support both (hour, msg) tuples and plain strings
            if isinstance(item, tuple):
                hour, msg = item
            else:
                hour, msg = None, item

            if "negative" in msg.lower() or "negatief" in msg.lower():
                import re
                price_match = re.search(r'\((-?\d+\.\d+)\s*€/kWh', msg)
                solar_match = re.search(r'Solar surplus[:\s]+(-?\d+\.?\d*)\s*kW', msg, re.IGNORECASE)
                if price_match:
                    negative_hours.append(float(price_match.group(1)))
                    negative_times.append(hour)
                if solar_match:
                    solar_surplus_values.append(float(solar_match.group(1)))
            elif "very low" in msg.lower() or "zeer laag" in msg.lower():
                if not any("very low" in m.lower() for m in other_msgs):
                    other_msgs.append(msg)
            else:
                other_msgs.append(msg)

        # Build summary for negative prices
        # Bouw samenvatting voor negatieve prijzen
        if negative_hours:
            from datetime import datetime as _dt
            combined = sorted(
                zip(negative_times, negative_hours),
                key=lambda x: x[0] if x[0] else _dt.min
            )
            prices_str = " | ".join(
                f"{t.strftime('%H:%M') if t else '??:??'}: {p*100:.2f}ct"
                for t, p in combined
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
        for item in other_msgs:
            msg = item[1] if isinstance(item, tuple) else item
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
        charges       = sum(1 for s in slots if s.action == "charge")
        discharges    = sum(1 for s in slots if s.action == "discharge")
        idles         = sum(1 for s in slots if s.action == "idle")
        self_consumes = sum(1 for s in slots if s.action == "self_consume")
        saving        = sum(s.expected_saving for s in slots)
        sc_part = f", {self_consumes} {tr.get('LG09', {'slots': 'zelf-verbruik'})}" if self_consumes else ""
        msg = self._tr.get("LG09", {
            "slots": (
                f"{len(slots)}h — "
                f"{charges} laden"
            )
        })
        # Bouw de melding op uit vertaalde onderdelen
        # Build the message from translated parts
        msg = (
            f"Schema: {len(slots)}u — "
            f"{charges} laden, {discharges} ontladen, {idles} rust"
            + sc_part
            + f". Verwachte besparing: €{saving:.2f}"
        )
        self._reporter.info(msg, category="optimizer")
        logger.info(f"[optimizer] {msg}")
