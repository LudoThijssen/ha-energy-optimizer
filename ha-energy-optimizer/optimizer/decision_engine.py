#
# name:          decision_engine.py
# part of:       ha-energy-optimizer
# location:      /ha-energy-optimizer/ha-energy-optimizer/optimizer/decision_engine.py
# part version:  p_v0.9
# altered:       2026-07-23
#
# Vervangt de combinatie van strategy.py decide() + engine._calculate().
# Implementeert de 5-stappen beslislogica uit het technisch ontwerp v0.3:
#   1. Initialisatie — prijsstatistieken, dynamische SoC drempels
#   2. Off-grid check — entiteit uitlezen, nettoladen blokkeren indien actief
#   3. Beslisboom per kwartier-slot — A(hoge prijs) B(zon) C(nacht) D(dag) E(lage prijs)
#   4. Anti-cycling — ontladen blokkeren als net geladen tegen vergelijkbare prijs
#   5. Opslaan — via save_slot met IF(executed=0) bescherming
#
# p_v0.9: overstap van uur- naar kwartier-slots. De vorige `_INTERVAL_H`
# constante (5 min als fractie van een uur) was gedefinieerd maar nergens
# gebruikt — dat bleek de plek waar de eerdere kwartier-poging is blijven
# steken. Vervangen door config.timeslot.SLOT_HOURS, die overal wordt
# toegepast waar een vermogen (kW) werd omgerekend naar energie (kWh) VOOR
# ÉÉN SLOT — dat ging voorheen impliciet uit van 1 uur per slot. Plekken die
# al langer dan 1 slot iets optellen (zoals _nacht_soc) gebruiken juist
# config.timeslot.SLOT_TO_MEASUREMENT_FACTOR, die NIET verandert — dat hangt
# af van het 5-minuten meetinterval van ha_collector, niet van de schema-
# tijdstap. Zie config/timeslot.py voor de volledige toelichting.
#
# p_v0.9: switch from hourly to quarter-hour slots. The previous
# `_INTERVAL_H` constant (5 min as a fraction of an hour) was defined but
# never used — that turned out to be where an earlier quarter-hour attempt
# had stalled. Replaced by config.timeslot.SLOT_HOURS, applied everywhere a
# power (kW) was converted to energy (kWh) FOR ONE SLOT — that previously
# implicitly assumed 1 hour per slot. Places that sum something across more
# than 1 slot (like _nacht_soc) instead use config.timeslot.
# SLOT_TO_MEASUREMENT_FACTOR, which does NOT change — that depends on
# ha_collector's 5-minute measurement interval, not the schedule time step.
# See config/timeslot.py for the full explanation.

import logging
import math
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP
from typing import Optional

from database.connection import DatabaseConnection
from collectors.consumption_learner import ConsumptionLearner
from .models import HourForecast, ScheduleSlot
from translations.translator import build_translator
from config.timeslot import SLOT_MINUTES, SLOT_HOURS, SLOT_TO_MEASUREMENT_FACTOR

logger = logging.getLogger(__name__)


# ── Hulpdataklassen / Helper dataclasses ──────────────────────────────────────

@dataclass
class BatteryConfig:
    """
    Batterijconfiguratie geladen uit de database.
    Battery configuration loaded from the database.
    """
    usable_kwh:        Decimal = Decimal("10")
    min_soc_pct:       Decimal = Decimal("10")
    max_soc_pct:       Decimal = Decimal("95")
    efficiency:        Decimal = Decimal("0.83")
    max_charge_kw:     Decimal = Decimal("4.0")
    max_discharge_kw:  Decimal = Decimal("4.0")
    depreciation_kwh:  Decimal = Decimal("0")
    temp_threshold_c:  Decimal = Decimal("35")
    temp_factor:       Decimal = Decimal("0.7")
    off_grid_reserve_kwh: Decimal = Decimal("0")   # 0 = niet actief / not active


@dataclass
class PriceConfig:
    """
    Prijsconfiguratie: BTW, drempels.
    Price configuration: VAT, thresholds.
    """
    price_incl_tax: bool    = False
    vat_pct:        Decimal = Decimal("21")
    hard_min_excl:  Decimal = Decimal("0.05")   # nooit ontladen onder deze prijs
    max_charge_excl: Decimal = Decimal("0.10")  # maximale laadprijs excl. BTW
    negative_export_threshold_excl: Decimal = Decimal("0")  # exportprijs waaronder net-bijladen i.p.v. exporteren


@dataclass
class WindowHour:
    """
    Eén uur in het beslissingsvenster met alle relevante data.
    One hour in the decision window with all relevant data.
    """
    forecast:       HourForecast
    price_excl:     Decimal
    surplus_kwh:    Decimal          # zon - verbruik (positief = overschot)
    tekort_kwh:     Decimal          # verbruik - zon (positief = tekort)
    action:         str   = "idle"
    power_kw:       Decimal = Decimal("0")
    is_solar_charge: bool  = False
    grid_top_up_kwh: Decimal = Decimal("0")  # net-bijladen bovenop zonoverschot (bij negatieve exportprijs)
    executed:       bool   = False
    reason:         str    = ""
    reason_key:     str    = ""
    reason_params:  dict   = None


# ── DecisionEngine ────────────────────────────────────────────────────────────

class DecisionEngine:
    """
    Nieuwe 5-stappen beslislogica voor de battery optimizer.
    New 5-step decision logic for the battery optimizer.

    Vervangt de strategy.py/engine._calculate() combinatie.
    Replaces the strategy.py/engine._calculate() combination.
    """

    def __init__(self, db: DatabaseConnection, bat: BatteryConfig, price: PriceConfig):
        self._db    = db
        self._bat   = bat
        self._price = price
        self._consumption_learner = ConsumptionLearner(db)
        self._tr    = build_translator(db)

    # ── Publieke interface / Public interface ─────────────────────────────────

    def run(
        self,
        forecasts: list[HourForecast],
        battery_temp_c: Optional[Decimal] = None,
        off_grid_entity_id: Optional[str] = None,
    ) -> list[ScheduleSlot]:
        """
        Verwerk de prognoses en bepaal de optimale actie per uur.
        Process the forecasts and determine the optimal action per hour.

        Args:
            forecasts:          lijst van HourForecast objecten (48 uur aan
                                 kwartier-slots, dus 192 objecten)
            battery_temp_c:     huidige batterijtemperatuur voor vermogensbeperking
            off_grid_entity_id: HA entity_id van de off-grid sensor (optioneel)

        Returns:
            Lijst van ScheduleSlot objecten klaar voor opslaan.
        """
        if not forecasts:
            return []

        # ── Stap 1: Initialisatie ─────────────────────────────────────────────
        off_grid = self._read_off_grid(off_grid_entity_id)
        eff_charge_kw, eff_discharge_kw = self._effective_power(battery_temp_c)
        price_factor_high, price_factor_low = self._price_factors(forecasts)
        reserve_soc = self._reserve_soc()

        window = self._build_window(forecasts)

        # Markeer al uitgevoerde uren (rolling horizon bescherming)
        # Mark already executed hours (rolling horizon protection)
        self._mark_executed(window)

        # ── Stap 2: Off-grid check ────────────────────────────────────────────
        if off_grid:
            logger.info(f"[decision_engine] {self._tr.get("RS11")}")

        # Startende SoC voor de simulatie
        # Starting SoC for the simulation
        soc = forecasts[0].soc_pct

        # ── Stap 3: Beslisboom per uur ────────────────────────────────────────
        for idx, wh in enumerate(window):
            if wh.executed:
                # Al uitgevoerd — SoC bijwerken en doorgaan
                idle_power = wh.tekort_kwh if wh.action == "idle" else wh.power_kw
                soc = self._update_soc(soc, wh.action, idle_power, eff_charge_kw)
                continue

            wh.forecast.soc_pct = soc
            price = wh.price_excl

            # Bereken dynamische SoC drempels voor dit uur
            nacht_soc = self._nacht_soc(wh.forecast.hour, reserve_soc)
            dag_soc   = self._dag_soc(wh.forecast.hour, reserve_soc)

            # Hoge prijs? → probeer te ontladen
            if price >= price_factor_high and not off_grid:
                if self._mogelijk_ontladen(wh, window, soc, reserve_soc,
                                           nacht_soc, dag_soc, eff_discharge_kw):
                    soc = self._update_soc(soc, wh.action, wh.power_kw, eff_discharge_kw)
                    continue

            # Zon-overschot? → laden van zon (evt. aangevuld met net bij negatieve prijs)
            if wh.surplus_kwh > Decimal("0.05"):
                grid_top_up = Decimal("0")

                if price < self._price.negative_export_threshold_excl and soc < self._bat.max_soc_pct:
                    # Exporteren zou hier geld kosten. Kijk hoeveel ruimte er
                    # NODIG is voor toekomstige uren die ook negatief geprijsd
                    # zijn met eigen zonoverschot — die ruimte laten we vrij,
                    # de rest mag nu extra vanaf het net bijgeladen worden
                    # (ook tegen deze gunstige/negatieve prijs).
                    #
                    # Exporting here would cost money. Check how much room is
                    # NEEDED for future hours that are also negatively priced
                    # with their own solar surplus — that room stays free,
                    # the rest may be topped up from the grid now (also at
                    # this favourable/negative price).
                    reserve_kwh  = self._reserve_for_future_negative_export(window, idx)
                    headroom_kwh = (
                        (self._bat.max_soc_pct - soc) * self._bat.usable_kwh
                        / 100 / self._bat.efficiency
                    )
                    extra_room = max(Decimal("0"), headroom_kwh - reserve_kwh)
                    # extra_room is een totale energie-marge (kWh), geen
                    # vermogen — begrens het vermogen dit SLOT zo dat
                    # power_kw × SLOT_HOURS niet meer is dan die marge.
                    # Bij uur-slots was extra_room toevallig al een geldige
                    # vermogens-cap (kWh/1u = kW); bij kwartier-slots moet
                    # dat expliciet omgerekend worden.
                    # extra_room is a total energy margin (kWh), not a
                    # power — cap this slot's power so that
                    # power_kw × SLOT_HOURS doesn't exceed that margin. At
                    # hourly slots extra_room happened to already be a valid
                    # power cap (kWh/1h = kW); at quarter slots this must be
                    # converted explicitly.
                    grid_top_up = min(extra_room / SLOT_HOURS, eff_charge_kw - wh.surplus_kwh)
                    grid_top_up = max(Decimal("0"), grid_top_up)

                charge_kw = min(wh.surplus_kwh + grid_top_up, eff_charge_kw)
                if soc < self._bat.max_soc_pct:
                    wh.action          = "charge"
                    wh.power_kw        = charge_kw
                    wh.is_solar_charge = True
                    wh.grid_top_up_kwh = grid_top_up
                    if grid_top_up > Decimal("0.05"):
                        self._set_reason(wh, "RS16", {
                            "surplus_kw": wh.surplus_kwh,
                            "grid_kw":    grid_top_up,
                            "price":      price
                        })
                    else:
                        self._set_reason(wh, "RS01", {"surplus_kw": wh.surplus_kwh})
                    soc = self._update_soc(soc, "charge", charge_kw, eff_charge_kw)
                    continue
                else:
                    wh.action = "self_consume"
                    self._set_reason(wh, "RS02")
                    continue

            # Onvoldoende voor nacht? → probeer te laden
            soc_einde_dag = self._soc_einde_dag(window, soc)
            if soc_einde_dag < nacht_soc:
                if self._mogelijk_laden(wh, window, soc, nacht_soc,
                                        off_grid, eff_charge_kw,
                                        reden="RS18",
                                        reden_params={"soc": soc_einde_dag, "min_soc": nacht_soc}):
                    soc = self._update_soc(soc, wh.action, wh.power_kw, eff_charge_kw)
                    continue

            # Onvoldoende voor volgende dag? → probeer te laden
            soc_zonsopgang = self._soc_zonsopgang(window, soc)
            if soc_zonsopgang < dag_soc:
                if self._mogelijk_laden(wh, window, soc, dag_soc,
                                        off_grid, eff_charge_kw,
                                        reden="RS19",
                                        reden_params={"soc": soc_zonsopgang, "min_soc": dag_soc}):
                    soc = self._update_soc(soc, wh.action, wh.power_kw, eff_charge_kw)
                    continue

            # Lage prijs? → probeer te laden (opportunistisch)
            if price <= price_factor_low and not off_grid:
                if soc < self._bat.max_soc_pct:
                    self._laden(wh, window, soc, self._bat.max_soc_pct,
                                off_grid, eff_charge_kw, reden="RS20")
                    soc = self._update_soc(soc, wh.action, wh.power_kw, eff_charge_kw)
                    continue

            # Geen actie — rust (maar batterij levert eventueel passief bij)
            wh.action = "idle"
            self._set_reason(wh, "RS10")
            soc = self._update_soc(soc, "idle", wh.tekort_kwh, eff_charge_kw)

        # ── Stap 4: Anti-cycling ──────────────────────────────────────────────
        self._anti_cycling(window)

        # ── Stap 5: Omzetten naar ScheduleSlot objecten ───────────────────────
        return self._to_slots(window)

    # ── Stap 1 helpers / Step 1 helpers ──────────────────────────────────────

    def _read_off_grid(self, entity_id: Optional[str]) -> bool:
        """
        Lees de off-grid sensor entiteit uit HA.
        Read the off-grid sensor entity from HA.
        Geeft False als entity_id None is of als de entiteit niet bereikbaar is.
        Returns False if entity_id is None or entity is not reachable.
        """
        if not entity_id:
            return False
        try:
            with self._db.cursor() as cur:
                cur.execute(
                    "SELECT entity_id FROM ha_entity_map "
                    "WHERE internal_name = 'off_grid_active' LIMIT 1"
                )
                row = cur.fetchone()
            if not row:
                return False
            import requests as _req
            from config.config import AppConfig
            config = AppConfig.load()
            url = f"http://{config.ha.host}:{config.ha.port}/api/states/{row['entity_id']}"
            resp = _req.get(
                url,
                headers={"Authorization": f"Bearer {config.ha.token}"},
                timeout=3
            )
            state = resp.json().get("state", "off")
            return state in ("on", "true", "1", "aan")
        except Exception as e:
            logger.debug(f"[decision_engine] Off-grid entiteit niet bereikbaar: {e}")
            return False

    def _effective_power(
        self, temp_c: Optional[Decimal]
    ) -> tuple[Decimal, Decimal]:
        """
        Bereken effectief laad- en ontlaadvermogen met temperatuurcorrectie.
        Calculate effective charge and discharge power with temperature correction.
        """
        charge_kw    = self._bat.max_charge_kw
        discharge_kw = self._bat.max_discharge_kw

        if temp_c is not None and temp_c > self._bat.temp_threshold_c:
            charge_kw    = (charge_kw    * self._bat.temp_factor).quantize(Decimal("0.01"))
            discharge_kw = (discharge_kw * self._bat.temp_factor).quantize(Decimal("0.01"))
            logger.info(
                f"[decision_engine] Temperatuurverlaging actief: {temp_c}°C — "
                f"vermogen begrensd / Temperature derating active: power limited"
            )
        return charge_kw, discharge_kw

    def _price_factors(
        self, forecasts: list[HourForecast]
    ) -> tuple[Decimal, Decimal]:
        """
        Bepaal drempelwaarden voor hoge en lage prijzen op basis van het venster.
        Determine high and low price thresholds based on the window.
        """
        prices = [self._to_excl(f.price_per_kwh) for f in forecasts]
        if not prices:
            return Decimal("0.20"), Decimal("0.05")

        avg = sum(prices) / len(prices)

        # Hoog: gemiddelde × 1.5, maar minimaal hard_min + 0.05
        # High: average × 1.5, but at least hard_min + 0.05
        high = max(avg * Decimal("1.5"), self._price.hard_min_excl + Decimal("0.05"))

        # Laag: gemiddelde × 0.6, maar maximaal max_charge_excl
        # Low: average × 0.6, but at most max_charge_excl
        low  = min(avg * Decimal("0.6"), self._price.max_charge_excl)

        return high.quantize(Decimal("0.00001")), low.quantize(Decimal("0.00001"))

    def _reserve_soc(self) -> Decimal:
        """
        Bereken off-grid reserve SoC%.
        Calculate off-grid reserve SoC%.
        """
        if self._bat.off_grid_reserve_kwh <= 0:
            return self._bat.min_soc_pct
        reserve = (
            self._bat.off_grid_reserve_kwh / self._bat.usable_kwh * 100
        ).quantize(Decimal("0.1"))
        return max(reserve, self._bat.min_soc_pct)

    def _build_window(self, forecasts: list[HourForecast]) -> list[WindowHour]:
        """
        Bouw het beslissingsvenster op vanuit de prognoses.
        Build the decision window from the forecasts.
        """
        window = []
        for f in forecasts:
            price_excl  = self._to_excl(f.price_per_kwh)
            surplus     = max(Decimal("0"), f.solar_kw - f.consumption_kw)
            tekort      = max(Decimal("0"), f.consumption_kw - f.solar_kw)
            window.append(WindowHour(
                forecast=f,
                price_excl=price_excl,
                surplus_kwh=surplus,
                tekort_kwh=tekort,
            ))
        return window

    def _mark_executed(self, window: list[WindowHour]) -> None:
        """
        Markeer uren die al uitgevoerd zijn (rolling horizon bescherming).
        Mark hours that are already executed (rolling horizon protection).
        """
        hours = [wh.forecast.hour for wh in window]
        if not hours:
            return
        try:
            with self._db.cursor() as cur:
                cur.execute(
                    "SELECT schedule_for, action, target_power_kw "
                    "FROM optimizer_schedule "
                    "WHERE executed = 1 AND schedule_for >= %(from_h)s",
                    {"from_h": hours[0]}
                )
                executed_rows = {
                    row["schedule_for"]: row for row in cur.fetchall()
                }
            for wh in window:
                row = executed_rows.get(wh.forecast.hour)
                if row is not None:
                    wh.executed = True
                    wh.action   = row["action"]
                    wh.power_kw = Decimal(str(row["target_power_kw"]))
        except Exception as e:
            logger.debug(f"[decision_engine] Executed uren ophalen mislukt: {e}")

    # ── Stap 2-3 helpers / Step 2-3 helpers ──────────────────────────────────

    def _period_kwh(self, hours: range, base_dt: datetime) -> Decimal:
        """
        Som van het voorspelde verbruik (kWh) over de gegeven uren, opgeteld
        per kwartier-slot voor precisie (i.p.v. één schatting per heel uur).

        Sum of predicted consumption (kWh) over the given hours, summed per
        quarter-hour slot for precision (instead of one estimate per whole
        hour).

        Let op: base_dt.replace(hour=h, minute=m) verandert alleen uur/minuut
        en behoudt de datum van base_dt — dit is bewust, hetzelfde patroon
        als de oorspronkelijke uur-versie. ConsumptionLearner kijkt toch
        alleen naar maand/weekdag/kwartier-slot, niet naar de exacte datum.

        Note: base_dt.replace(hour=h, minute=m) only changes hour/minute and
        keeps base_dt's date — this is intentional, same pattern as the
        original hourly version. ConsumptionLearner only looks at month/
        day-of-week/quarter-slot anyway, not the exact date.
        """
        total_kwh = Decimal("0")
        for h in hours:
            for m in range(0, 60, SLOT_MINUTES):
                total_kwh += Decimal(str(
                    self._consumption_learner.predict(base_dt.replace(hour=h, minute=m))
                    * SLOT_TO_MEASUREMENT_FACTOR
                ))
        return total_kwh

    def _nacht_soc(self, dt: datetime, reserve_soc: Decimal) -> Decimal:
        """
        Bereken minimale SoC voor de nacht op basis van verwacht verbruik.
        Calculate minimum SoC for the night based on expected consumption.
        """
        nacht_kwh = self._period_kwh(range(22, 24), dt) + self._period_kwh(range(0, 7), dt)

        soc_nodig = (nacht_kwh / (self._bat.usable_kwh * self._bat.efficiency) * 100)
        return max(soc_nodig, reserve_soc).quantize(Decimal("0.1"))

    def _dag_soc(self, dt: datetime, reserve_soc: Decimal) -> Decimal:
        """
        Bereken minimale SoC bij zonsopgang morgen.
        Calculate minimum SoC at tomorrow's sunrise.
        Vroeg-ochtend verbruik (06:00-09:00) voor zon opkomt.
        Early morning consumption (06:00-09:00) before sun rises.
        """
        morgen = dt + timedelta(days=1)
        vroeg_kwh = self._period_kwh(range(6, 9), morgen)

        soc_nodig = (vroeg_kwh / (self._bat.usable_kwh * self._bat.efficiency) * 100)
        return max(soc_nodig, reserve_soc).quantize(Decimal("0.1"))

    def _soc_einde_dag(self, window: list[WindowHour], soc_nu: Decimal) -> Decimal:
        """
        Schat de SoC aan het einde van de dag op basis van huidige acties en surplus.
        Estimate SoC at end of day based on current actions and surplus.

        p_v0.9: × SLOT_HOURS toegevoegd — power_kw is een vermogen, geen
        energie voor de hele periode. Bij uur-slots was dit toevallig
        hetzelfde getal (× 1), bij kwartier-slots niet meer.
        p_v0.9: × SLOT_HOURS added — power_kw is a power rating, not the
        energy for the whole period. At hourly slots this happened to be
        the same number (× 1), at quarter slots it no longer is.
        """
        soc = soc_nu
        now_date = datetime.now().date()
        for wh in window:
            if wh.forecast.hour.date() != now_date:
                break
            if wh.action == "charge":
                soc = min(soc + wh.power_kw * self._bat.efficiency * SLOT_HOURS
                          / self._bat.usable_kwh * 100, self._bat.max_soc_pct)
            elif wh.action in ("discharge",):
                soc = max(soc - wh.power_kw / self._bat.efficiency * SLOT_HOURS
                          / self._bat.usable_kwh * 100, self._bat.min_soc_pct)
        return soc

    def _soc_zonsopgang(self, window: list[WindowHour], soc_nu: Decimal) -> Decimal:
        """
        Schat de SoC bij zonsopgang morgen (06:00).
        Estimate SoC at tomorrow's sunrise (06:00).

        p_v0.9: × SLOT_HOURS toegevoegd, zie _soc_einde_dag hierboven.
        p_v0.9: × SLOT_HOURS added, see _soc_einde_dag above.
        """
        soc = soc_nu
        target_hour = (datetime.now() + timedelta(days=1)).replace(hour=6, minute=0, second=0)
        for wh in window:
            if wh.forecast.hour >= target_hour:
                break
            if wh.action == "charge":
                soc = min(soc + wh.power_kw * self._bat.efficiency * SLOT_HOURS
                          / self._bat.usable_kwh * 100, self._bat.max_soc_pct)
            elif wh.action == "discharge":
                soc = max(soc - wh.power_kw / self._bat.efficiency * SLOT_HOURS
                          / self._bat.usable_kwh * 100, self._bat.min_soc_pct)
        return soc

    def _mogelijk_ontladen(
        self,
        wh: WindowHour,
        window: list[WindowHour],
        soc: Decimal,
        reserve_soc: Decimal,
        nacht_soc: Decimal,
        dag_soc: Decimal,
        eff_discharge_kw: Decimal,
    ) -> bool:
        """
        Bepaal of ontladen zinvol is en koppel de duurste uren via sortering.
        Determine if discharging is worthwhile and assign the most expensive
        hours via sorting.
        """
        if wh.price_excl < self._price.hard_min_excl:
            return False

        self._ontladen(wh, window, soc, reserve_soc, nacht_soc, dag_soc, eff_discharge_kw)
        return wh.action == "discharge"

    def _ontladen(
        self,
        wh: WindowHour,
        window: list[WindowHour],
        soc: Decimal,
        reserve_soc: Decimal,
        nacht_soc: Decimal,
        dag_soc: Decimal,
        eff_discharge_kw: Decimal,
    ) -> None:
        """
        Koppel ontlaadacties aan de duurste beschikbare uren in het venster
        (sorteermethode — Ludo's voorkeur, zie overdracht):
          1. Array van alle idle uren met prijs
          2. Sorteer aflopend (duurste eerst)
          3. Kies uren tot beschikbare kWh op is
          4. Rendementscheck: duurste ontlaadprijs > goedkoopste laadprijs / rendement,
             anders is ontladen op dit moment financieel niet zinvol.

        Assign discharge actions to the most expensive available hours in
        the window (sort method — Ludo's preference, see handover):
          1. Array of all idle hours with price
          2. Sort descending (most expensive first)
          3. Select hours until available kWh is used up
          4. Efficiency check: most expensive discharge price > cheapest
             charge price / efficiency, otherwise discharging now is not
             financially worthwhile.
        """
        gereserveerd = max(nacht_soc, dag_soc, reserve_soc)
        beschikbaar  = max(Decimal("0"), soc - gereserveerd)
        beschikbaar_kwh = beschikbaar * self._bat.usable_kwh / 100 * self._bat.efficiency

        if beschikbaar_kwh < Decimal("0.5"):
            self._set_reason(wh, "RS06", {"available": beschikbaar, "reserve": gereserveerd})
            return

        # Verwijder bestaande niet-uitgevoerde ontlaadacties, zodat elke
        # aanroep vers herberekent (zelfde patroon als _laden()) — voorkomt
        # verouderde/dubbele reserveringen als de uur-loop een eerder
        # toegewezen uur later opnieuw tegenkomt.
        # Remove existing non-executed discharge actions, so every call
        # recomputes fresh (same pattern as _laden()) — prevents stale/
        # duplicate reservations if the hourly loop later re-encounters an
        # hour that was already assigned.
        for w in window:
            if w.action == "discharge" and not w.executed:
                w.action   = "idle"
                w.power_kw = Decimal("0")
                w.reason   = ""

        # Sorteer beschikbare uren op prijs (duurste eerst) / oplopend voor laden
        # Sort available hours by price (most expensive first) / ascending for charging
        idle_uren = [w for w in window if w.action == "idle" and not w.executed]
        ontlaad_kandidaten = sorted(
            [w for w in idle_uren if w.price_excl >= self._price.hard_min_excl],
            key=lambda w: w.price_excl,
            reverse=True
        )
        if not ontlaad_kandidaten:
            self._set_reason(wh, "RS06", {"available": beschikbaar, "reserve": gereserveerd})
            return

        # Rendementscheck: duurste ontlaadprijs moet de goedkoopste beschikbare
        # laadprijs (gedeeld door rendement) overtreffen, anders is het
        # voordeliger om (straks) te laden dan nu te ontladen.
        # Efficiency check: most expensive discharge price must exceed the
        # cheapest available charge price (divided by efficiency), otherwise
        # it's more advantageous to charge (later) than discharge now.
        laad_kandidaten = sorted(
            (w.price_excl for w in idle_uren
             if w.price_excl <= self._price.max_charge_excl),
            reverse=False
        )
        if laad_kandidaten:
            goedkoopste_laadprijs = laad_kandidaten[0]
            duurste_ontlaadprijs  = ontlaad_kandidaten[0].price_excl
            if duurste_ontlaadprijs <= goedkoopste_laadprijs / self._bat.efficiency:
                self._set_reason(wh, "RS06", {"available": beschikbaar, "reserve": gereserveerd})
                return

        ontladen_kwh = Decimal("0")
        for kandidaat in ontlaad_kandidaten:
            if ontladen_kwh >= beschikbaar_kwh:
                break
            # beschikbaar_kwh is een energiebudget (kWh); begrens het
            # vermogen dit slot zodat power_kw × SLOT_HOURS niet meer
            # oplevert dan wat er nog over is. Bij uur-slots was dat
            # toevallig hetzelfde getal als het resterende budget zelf.
            # beschikbaar_kwh is an energy budget (kWh); cap this slot's
            # power so power_kw × SLOT_HOURS doesn't yield more than what's
            # left. At hourly slots this happened to be the same number as
            # the remaining budget itself.
            resterend_kwh = beschikbaar_kwh - ontladen_kwh
            discharge_kw  = min(eff_discharge_kw, resterend_kwh / SLOT_HOURS)
            kandidaat.action   = "discharge"
            kandidaat.power_kw = discharge_kw.quantize(Decimal("0.01"))
            self._set_reason(kandidaat, "RS05", {"price": kandidaat.price_excl})
            ontladen_kwh += discharge_kw * SLOT_HOURS

    def _mogelijk_laden(
        self,
        wh: WindowHour,
        window: list[WindowHour],
        soc: Decimal,
        doel_soc: Decimal,
        off_grid: bool,
        eff_charge_kw: Decimal,
        reden: str = "",
        reden_params: dict | None = None,
    ) -> bool:
        """
        Bepaal of laden zinvol is en koppel de goedkoopste uren.
        Determine if charging is worthwhile and assign the cheapest hours.
        """
        # Bereken tekort
        tekort_kwh = max(Decimal("0"),
                         (doel_soc - soc) * self._bat.usable_kwh / 100)

        # Trek al geplande laadenergie af — elk gepland slot draagt
        # power_kw × SLOT_HOURS energie bij, niet power_kw zelf.
        # Subtract already-planned charge energy — each planned slot
        # contributes power_kw × SLOT_HOURS energy, not power_kw itself.
        al_gepland = sum(
            w.power_kw * SLOT_HOURS for w in window
            if w.action == "charge" and not w.executed and w != wh
        )
        nog_nodig = max(Decimal("0"), tekort_kwh - al_gepland)

        if nog_nodig < Decimal("0.1"):
            return False

        self._laden(wh, window, soc, doel_soc, off_grid, eff_charge_kw, reden, reden_params)
        return wh.action == "charge"

    def _laden(
        self,
        wh: WindowHour,
        window: list[WindowHour],
        soc: Decimal,
        doel_soc: Decimal,
        off_grid: bool,
        eff_charge_kw: Decimal,
        reden: str = "",
        reden_params: dict | None = None,
    ) -> None:
        """
        Koppel laadacties aan de goedkoopste beschikbare uren in het venster.
        Assign charging actions to the cheapest available hours in the window.
        """
        reden_params = reden_params or {}

        # Verwijder bestaande niet-uitgevoerde laadacties
        for w in window:
            if w.action == "charge" and not w.executed and not w.is_solar_charge:
                w.action  = "idle"
                w.power_kw = Decimal("0")
                w.reason  = ""

        # Sorteer beschikbare uren op prijs (goedkoopste eerst)
        kandidaten = sorted(
            [w for w in window if w.action == "idle" and not w.executed],
            key=lambda w: w.price_excl
        )

        tekort_kwh = max(Decimal("0"),
                         (doel_soc - soc) * self._bat.usable_kwh / 100)
        geladen_kwh = Decimal("0")

        for kandidaat in kandidaten:
            # Nettoladen geblokkeerd bij off-grid
            if off_grid and not kandidaat.is_solar_charge:
                continue

            # Negatieve prijs altijd laden
            if kandidaat.price_excl < 0:
                pass
            # Prijs boven maximum laadgrens — stop
            elif kandidaat.price_excl > self._price.max_charge_excl:
                break

            kandidaat.action    = "charge"
            kandidaat.power_kw  = eff_charge_kw
            kandidaat.is_solar_charge = False

            # Reden bepalen: negatieve prijs > opgegeven reden-sleutel (RS18
            # nacht / RS19 dag / RS20 opportunistisch) > generieke RS07.
            # Determine reason: negative price > given reason key (RS18
            # night / RS19 day / RS20 opportunistic) > generic RS07.
            if kandidaat.price_excl < 0:
                self._set_reason(kandidaat, "RS16", {"price": kandidaat.price_excl})
            elif reden:
                self._set_reason(kandidaat, reden, {"price": kandidaat.price_excl, **reden_params})
            else:
                self._set_reason(kandidaat, "RS07", {"price": kandidaat.price_excl})
            # × SLOT_HOURS: eff_charge_kw is een vermogen, tekort_kwh is een
            # energiebudget — bij uur-slots was dit toevallig hetzelfde getal.
            # × SLOT_HOURS: eff_charge_kw is a power, tekort_kwh is an
            # energy budget — at hourly slots this happened to be the same
            # number.
            geladen_kwh += eff_charge_kw * self._bat.efficiency * SLOT_HOURS
            if geladen_kwh >= tekort_kwh:
                break

    # ── Stap 4: Anti-cycling ──────────────────────────────────────────────────

    def _set_reason(self, wh: "WindowHour", key: str, params: dict | None = None) -> None:
        """
        Zet reason tekst en sla key+params op voor hervertaling.
        Set reason text and store key+params for re-translation.
        """
        wh.reason_key    = key
        wh.reason_params = params or {}
        wh.reason        = self._tr.get(key, params)

    def _anti_cycling(self, window: list[WindowHour]) -> None:
        """
        Blokkeer ontladen als de prijs te dicht bij een recente laadprijs ligt.
        Block discharging if the price is too close to a recent charge price.
        Break-even = laadprijs / rendement + afschrijving.
        Break-even = charge price / efficiency + depreciation.
        Minimale marge: 10% boven break-even.
        Minimum margin: 10% above break-even.
        """
        laatste_laadprijs = None
        for wh in window:
            if wh.executed:
                continue
            if wh.action == "charge" and not wh.is_solar_charge:
                laatste_laadprijs = wh.price_excl
            elif wh.action == "discharge" and laatste_laadprijs is not None:
                break_even = (
                    laatste_laadprijs / self._bat.efficiency
                    + self._bat.depreciation_kwh
                )
                min_worthwhile = break_even * Decimal("1.10")
                if wh.price_excl < min_worthwhile:
                    wh.action   = "idle"
                    wh.power_kw = Decimal("0")
                    self._set_reason(wh, "RS09", {"price": wh.price_excl, "charge_price": laatste_laadprijs, "break_even": break_even})
                else:
                    laatste_laadprijs = None

    # ── Stap 5: Omzetten naar slots / Step 5: Convert to slots ───────────────

    def _to_slots(self, window: list[WindowHour]) -> list[ScheduleSlot]:
        """
        Zet WindowHour objecten om naar ScheduleSlot objecten.
        Convert WindowHour objects to ScheduleSlot objects.
        """
        slots = []
        soc = window[0].forecast.soc_pct if window else Decimal("50")

        for wh in window:
            price_excl = wh.price_excl
            saving = self._calc_saving(wh.action, wh.power_kw, price_excl, wh.is_solar_charge)
            cost   = self._calc_cost(wh.action, wh.power_kw, price_excl, wh.is_solar_charge, wh.grid_top_up_kwh)

            slots.append(ScheduleSlot(
                hour                   = wh.forecast.hour,
                action                 = wh.action,
                target_power_kw        = wh.power_kw,
                target_soc_pct         = soc,
                expected_saving        = saving,
                expected_cost          = cost,
                reason                 = wh.reason,
                reason_key             = wh.reason_key,
                reason_params          = wh.reason_params,
                expected_solar_kw      = wh.forecast.solar_kw,
                expected_consumption_kw= wh.forecast.consumption_kw,
                expected_price         = wh.forecast.price_per_kwh,
            ))

            # SoC bijwerken voor volgend uur (idle-uren nemen ook het
            # niet door zon gedekte huisverbruik mee, anders klopt de
            # getoonde SoC-trajectorie niet)
            # Update SoC for next hour (idle hours also account for
            # household consumption not covered by solar, otherwise the
            # displayed SoC trajectory is wrong)
            idle_power = wh.tekort_kwh if wh.action == "idle" else wh.power_kw
            soc = self._update_soc(soc, wh.action, idle_power, self._bat.max_charge_kw)

        return slots

    def _reserve_for_future_negative_export(
        self, window: list["WindowHour"], current_index: int
    ) -> Decimal:
        """
        Som van het verwachte zonoverschot in latere uren die ook onder de
        negative_export_threshold_excl geprijsd zijn. Deze ruimte houden we
        nu vrij in de batterij, zodat dat toekomstige overschot niet alsnog
        gedwongen tegen een negatieve prijs geëxporteerd hoeft te worden.

        Sum of expected solar surplus in later hours that are also priced
        below negative_export_threshold_excl. We keep this room free in the
        battery now, so that future surplus doesn't end up being forced to
        export at a negative price after all.
        """
        reserve = Decimal("0")
        for w in window[current_index + 1:]:
            if w.executed:
                continue
            if (w.price_excl < self._price.negative_export_threshold_excl
                    and w.surplus_kwh > Decimal("0")):
                # w.surplus_kwh is (ondanks de naam) een vermogen (kW) —
                # × SLOT_HOURS om de werkelijke energie van dát slot te
                # krijgen. Bij uur-slots was dit toevallig hetzelfde getal.
                # w.surplus_kwh is (despite the name) a power (kW) —
                # × SLOT_HOURS to get that slot's actual energy. At hourly
                # slots this happened to be the same number.
                reserve += w.surplus_kwh * SLOT_HOURS
        return reserve

    # ── Financiële berekeningen / Financial calculations ──────────────────────

    def _calc_saving(
        self, action: str, power_kw: Decimal,
        price_excl: Decimal, is_solar_charge: bool
    ) -> Decimal:
        """
        p_v0.9: × SLOT_HOURS toegevoegd — power_kw is een vermogen, de
        besparing moet berekend worden over de energie van dit ene slot
        (power_kw × SLOT_HOURS), niet over power_kw alsof dat al kWh is.
        p_v0.9: × SLOT_HOURS added — power_kw is a power rating, the
        saving must be calculated over this one slot's energy
        (power_kw × SLOT_HOURS), not over power_kw as if it were already kWh.
        """
        if action == "discharge":
            energy_out = power_kw * self._bat.efficiency * SLOT_HOURS
            saving = (energy_out * price_excl) - (self._bat.depreciation_kwh * power_kw * SLOT_HOURS)
        else:
            saving = Decimal("0")
        return saving.quantize(Decimal("0.00001"), rounding=ROUND_HALF_UP)

    def _calc_cost(
        self, action: str, power_kw: Decimal,
        price_excl: Decimal, is_solar_charge: bool,
        grid_top_up_kwh: Decimal = Decimal("0"),
    ) -> Decimal:
        """
        p_v0.9: × SLOT_HOURS toegevoegd, zie _calc_saving hierboven.
        grid_top_up_kwh is (ondanks de naam) ook een vermogen, geen kWh —
        zelfde correctie van toepassing.
        p_v0.9: × SLOT_HOURS added, see _calc_saving above. grid_top_up_kwh
        is (despite the name) also a power, not kWh — same correction applies.
        """
        if action == "charge" and not is_solar_charge:
            cost = power_kw * price_excl * SLOT_HOURS
        elif action == "charge" and is_solar_charge and grid_top_up_kwh > Decimal("0"):
            # Gemengd slot: alleen het net-bijgeladen deel telt mee (kan bij
            # een negatieve prijs een negatieve "kost" zijn = opbrengst).
            # Het zon-deel (power_kw - grid_top_up_kwh) blijft gratis.
            # Mixed slot: only the grid-topped-up portion counts (can be a
            # negative "cost" = revenue at a negative price). The solar
            # portion (power_kw - grid_top_up_kwh) remains free.
            cost = grid_top_up_kwh * price_excl * SLOT_HOURS
        else:
            cost = Decimal("0")
        return cost.quantize(Decimal("0.00001"), rounding=ROUND_HALF_UP)

    # ── SoC simulatie / SoC simulation ───────────────────────────────────────

    def _update_soc(
        self, soc: Decimal, action: str,
        power_kw: Decimal, eff_charge_kw: Decimal
    ) -> Decimal:
        """
        Bereken de SoC na één schema-slot (SLOT_MINUTES) met de gegeven actie.
        Calculate SoC after one schedule slot (SLOT_MINUTES) with the given action.

        p_v0.9: × SLOT_HOURS toegevoegd op alle drie de takken — power_kw is
        een vermogen, de SoC-verandering moet berekend worden over de
        energie van dit ene slot (power_kw × SLOT_HOURS). Bij uur-slots was
        SLOT_HOURS toevallig 1, dus onzichtbaar in de formule.
        p_v0.9: × SLOT_HOURS added on all three branches — power_kw is a
        power rating, the SoC change must be calculated over this one
        slot's energy (power_kw × SLOT_HOURS). At hourly slots SLOT_HOURS
        happened to be 1, so invisible in the formula.
        """
        if action == "charge":
            delta = power_kw * self._bat.efficiency * SLOT_HOURS / self._bat.usable_kwh * 100
            return min(soc + delta, self._bat.max_soc_pct)
        elif action == "discharge":
            delta = power_kw / self._bat.efficiency * SLOT_HOURS / self._bat.usable_kwh * 100
            return max(soc - delta, self._bat.min_soc_pct)
        elif action == "idle" and power_kw > Decimal("0"):
            # Passief huisverbruik dat niet door zon wordt gedekt, trekt de
            # batterij ook tijdens rust-slots leeg (bv. 's nachts).
            # Passive household consumption not covered by solar also drains
            # the battery during idle slots (e.g. at night).
            delta = power_kw / self._bat.efficiency * SLOT_HOURS / self._bat.usable_kwh * 100
            return max(soc - delta, self._bat.min_soc_pct)
        return soc

    # ── Hulpfuncties / Utility functions ──────────────────────────────────────

    def _to_excl(self, price: Decimal) -> Decimal:
        """Prijs excl. BTW berekenen indien nodig / Calculate price excl. VAT if needed."""
        if self._price.price_incl_tax:
            return (price / (Decimal("1") + self._price.vat_pct / 100)).quantize(
                Decimal("0.00001"), rounding=ROUND_HALF_UP
            )
        return price


# ── Factory functie / Factory function ───────────────────────────────────────

def build_decision_engine(db: DatabaseConnection) -> DecisionEngine:
    """
    Bouw een volledig geconfigureerde DecisionEngine vanuit de database.
    Build a fully configured DecisionEngine from the database.
    """
    from decimal import Decimal, ROUND_HALF_UP

    with db.cursor() as cur:
        cur.execute("SELECT * FROM system_config ORDER BY id DESC LIMIT 1")
        cfg = cur.fetchone() or {}

    with db.cursor() as cur:
        cur.execute("SELECT * FROM battery_info ORDER BY id DESC LIMIT 1")
        bat = cur.fetchone() or {}

    with db.cursor() as cur:
        cur.execute(
            "SELECT driver_config FROM provider_config "
            "WHERE energy_type = 'electricity' AND is_active = 1 LIMIT 1"
        )
        prov = cur.fetchone()

    # BTW configuratie / VAT configuration
    vat_pct        = Decimal("21.0")
    price_incl_tax = bool(cfg.get("price_incl_tax", False))
    if prov and prov.get("driver_config"):
        import json as _json
        drv = prov["driver_config"]
        if isinstance(drv, str):
            try:
                drv = _json.loads(drv)
            except Exception:
                drv = {}
        vat_pct = Decimal(str(drv.get("vat_pct", 21.0)))

    # Afschrijving per kWh / Depreciation per kWh
    dep_per_kwh = Decimal("0")
    usable_kwh  = Decimal(str(bat.get("usable_capacity_kwh") or "10"))
    if bat.get("cost_eur") and bat.get("expected_cycles") and usable_kwh > 0:
        dep_per_kwh = (
            Decimal(str(bat["cost_eur"]))
            / Decimal(str(bat["expected_cycles"]))
            / usable_kwh
        ).quantize(Decimal("0.00001"), rounding=ROUND_HALF_UP)

    bat_config = BatteryConfig(
        usable_kwh       = usable_kwh,
        min_soc_pct      = Decimal(str(bat.get("min_soc_pct") or "10")),
        max_soc_pct      = Decimal(str(bat.get("max_soc_pct") or "95")),
        efficiency       = Decimal(str(cfg.get("battery_efficiency_pct") or "83")) / 100,
        max_charge_kw    = Decimal(str(bat.get("max_charge_kw") or "4.0")),
        max_discharge_kw = Decimal(str(bat.get("max_discharge_kw") or "4.0")),
        depreciation_kwh = dep_per_kwh,
        temp_threshold_c = Decimal(str(cfg.get("temp_derating_threshold_c") or "35")),
        temp_factor      = Decimal(str(cfg.get("temp_derating_factor") or "0.7")),
        off_grid_reserve_kwh = Decimal(str(cfg.get("off_grid_reserve_kwh") or "0")),
    )

    # Max laadprijs excl. BTW / Max charge price excl. VAT
    max_charge_raw = Decimal(str(cfg.get("max_price_to_charge") or "0.10"))
    if price_incl_tax:
        max_charge_excl = (max_charge_raw / (Decimal("1") + vat_pct / 100)).quantize(
            Decimal("0.00001"), rounding=ROUND_HALF_UP
        )
    else:
        max_charge_excl = max_charge_raw

    price_config = PriceConfig(
        price_incl_tax = price_incl_tax,
        vat_pct        = vat_pct,
        hard_min_excl  = Decimal(str(cfg.get("hard_min_discharge_price_excl") or "0.05")),
        max_charge_excl = max_charge_excl,
        negative_export_threshold_excl = Decimal(str(cfg.get("negative_export_threshold_excl") or "0")),
    )

    return DecisionEngine(db, bat_config, price_config)

