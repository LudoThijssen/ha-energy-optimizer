#
# name:          decision_engine.py
# part of:       ha-energy-optimizer
# location:      /ha-energy-optimizer/ha-energy-optimizer/optimizer/decision_engine.py
# part version:  p_v0.6
# altered:       2026-07-16
#
# Vervangt de combinatie van strategy.py decide() + engine._calculate().
# Implementeert de 5-stappen beslislogica uit het technisch ontwerp v0.3:
#   1. Initialisatie — prijsstatistieken, dynamische SoC drempels
#   2. Off-grid check — entiteit uitlezen, nettoladen blokkeren indien actief
#   3. Beslisboom per uur — A(hoge prijs) B(zon) C(nacht) D(dag) E(lage prijs)
#   4. Anti-cycling — ontladen blokkeren als net geladen tegen vergelijkbare prijs
#   5. Opslaan — via save_slot met IF(executed=0) bescherming
#
# Replaces the combination of strategy.py decide() + engine._calculate().
# Implements the 5-step decision logic from technical design v0.3:
#   1. Initialisation — price statistics, dynamic SoC thresholds
#   2. Off-grid check — read entity, block grid charging if active
#   3. Decision tree per hour — A(high) B(solar) C(night) D(day) E(low)
#   4. Anti-cycling — block discharge if recently charged at similar price
#   5. Save — via save_slot with IF(executed=0) protection

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

logger = logging.getLogger(__name__)

# ── Constanten / Constants ────────────────────────────────────────────────────

# Interval van de ha_collector meting in uren / ha_collector measurement interval in hours
_INTERVAL_H = Decimal("1") / Decimal("12")   # 5 minuten / 5 minutes


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
            forecasts:          lijst van HourForecast objecten (48 uur)
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
        for wh in window:
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

            # Zon-overschot? → laden van zon
            if wh.surplus_kwh > Decimal("0.05"):
                charge_kw = min(wh.surplus_kwh, eff_charge_kw)
                if soc < self._bat.max_soc_pct:
                    wh.action         = "charge"
                    wh.power_kw       = charge_kw
                    wh.is_solar_charge = True
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
                                        off_grid, eff_charge_kw):
                    soc = self._update_soc(soc, wh.action, wh.power_kw, eff_charge_kw)
                    continue

            # Onvoldoende voor volgende dag? → probeer te laden
            soc_zonsopgang = self._soc_zonsopgang(window, soc)
            if soc_zonsopgang < dag_soc:
                if self._mogelijk_laden(wh, window, soc, dag_soc,
                                        off_grid, eff_charge_kw):
                    soc = self._update_soc(soc, wh.action, wh.power_kw, eff_charge_kw)
                    continue

            # Lage prijs? → probeer te laden (opportunistisch)
            if price <= price_factor_low and not off_grid:
                if soc < self._bat.max_soc_pct:
                    self._laden(wh, window, soc, self._bat.max_soc_pct,
                                off_grid, eff_charge_kw, reden="opportunistisch / opportunistic")
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

    def _nacht_soc(self, dt: datetime, reserve_soc: Decimal) -> Decimal:
        """
        Bereken minimale SoC voor de nacht op basis van verwacht verbruik.
        Calculate minimum SoC for the night based on expected consumption.
        """
        nacht_kwh = Decimal("0")
        for h in range(22, 24):
            nacht_kwh += Decimal(str(
                self._consumption_learner.predict(dt.replace(hour=h)) * 12
            ))
        for h in range(0, 7):
            nacht_kwh += Decimal(str(
                self._consumption_learner.predict(dt.replace(hour=h)) * 12
            ))

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
        vroeg_kwh = Decimal("0")
        for h in range(6, 9):
            vroeg_kwh += Decimal(str(
                self._consumption_learner.predict(morgen.replace(hour=h)) * 12
            ))

        soc_nodig = (vroeg_kwh / (self._bat.usable_kwh * self._bat.efficiency) * 100)
        return max(soc_nodig, reserve_soc).quantize(Decimal("0.1"))

    def _soc_einde_dag(self, window: list[WindowHour], soc_nu: Decimal) -> Decimal:
        """
        Schat de SoC aan het einde van de dag op basis van huidige acties en surplus.
        Estimate SoC at end of day based on current actions and surplus.
        """
        soc = soc_nu
        now_date = datetime.now().date()
        for wh in window:
            if wh.forecast.hour.date() != now_date:
                break
            if wh.action == "charge":
                soc = min(soc + wh.power_kw * self._bat.efficiency
                          / self._bat.usable_kwh * 100, self._bat.max_soc_pct)
            elif wh.action in ("discharge",):
                soc = max(soc - wh.power_kw / self._bat.efficiency
                          / self._bat.usable_kwh * 100, self._bat.min_soc_pct)
        return soc

    def _soc_zonsopgang(self, window: list[WindowHour], soc_nu: Decimal) -> Decimal:
        """
        Schat de SoC bij zonsopgang morgen (06:00).
        Estimate SoC at tomorrow's sunrise (06:00).
        """
        soc = soc_nu
        target_hour = (datetime.now() + timedelta(days=1)).replace(hour=6, minute=0, second=0)
        for wh in window:
            if wh.forecast.hour >= target_hour:
                break
            if wh.action == "charge":
                soc = min(soc + wh.power_kw * self._bat.efficiency
                          / self._bat.usable_kwh * 100, self._bat.max_soc_pct)
            elif wh.action == "discharge":
                soc = max(soc - wh.power_kw / self._bat.efficiency
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
        Bepaal of ontladen zinvol is en voer het uit.
        Determine if discharging is worthwhile and execute it.
        """
        if wh.price_excl < self._price.hard_min_excl:
            return False

        gereserveerd = max(nacht_soc, dag_soc, reserve_soc)
        beschikbaar  = max(Decimal("0"), soc - gereserveerd)
        beschikbaar_kwh = beschikbaar * self._bat.usable_kwh / 100 * self._bat.efficiency

        if beschikbaar_kwh < Decimal("0.5"):
            self._set_reason(wh, "RS06", {"available": beschikbaar, "reserve": gereserveerd})
            return False

        discharge_kw = min(eff_discharge_kw, beschikbaar_kwh)
        wh.action    = "discharge"
        wh.power_kw  = discharge_kw.quantize(Decimal("0.01"))
        self._set_reason(wh, "RS05", {"price": wh.price_excl})
        return True

    def _mogelijk_laden(
        self,
        wh: WindowHour,
        window: list[WindowHour],
        soc: Decimal,
        doel_soc: Decimal,
        off_grid: bool,
        eff_charge_kw: Decimal,
        reden: str = "",
    ) -> bool:
        """
        Bepaal of laden zinvol is en koppel de goedkoopste uren.
        Determine if charging is worthwhile and assign the cheapest hours.
        """
        # Bereken tekort
        tekort_kwh = max(Decimal("0"),
                         (doel_soc - soc) * self._bat.usable_kwh / 100)

        # Trek al geplande laadenergie af
        al_gepland = sum(
            w.power_kw for w in window
            if w.action == "charge" and not w.executed and w != wh
        )
        nog_nodig = max(Decimal("0"), tekort_kwh - al_gepland)

        if nog_nodig < Decimal("0.1"):
            return False

        self._laden(wh, window, soc, doel_soc, off_grid, eff_charge_kw, reden)
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
    ) -> None:
        """
        Koppel laadacties aan de goedkoopste beschikbare uren in het venster.
        Assign charging actions to the cheapest available hours in the window.
        """
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
            kandidaat.reason    = (
                self._tr.get("RS08" if reden else "RS07",
                             {"price": kandidaat.price_excl, "reason": reden})
            )
            geladen_kwh += eff_charge_kw * self._bat.efficiency
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
            cost   = self._calc_cost(wh.action, wh.power_kw, price_excl, wh.is_solar_charge)

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

    # ── Financiële berekeningen / Financial calculations ──────────────────────

    def _calc_saving(
        self, action: str, power_kw: Decimal,
        price_excl: Decimal, is_solar_charge: bool
    ) -> Decimal:
        if action == "discharge":
            energy_out = power_kw * self._bat.efficiency
            saving = (energy_out * price_excl) - (self._bat.depreciation_kwh * power_kw)
        else:
            saving = Decimal("0")
        return saving.quantize(Decimal("0.00001"), rounding=ROUND_HALF_UP)

    def _calc_cost(
        self, action: str, power_kw: Decimal,
        price_excl: Decimal, is_solar_charge: bool
    ) -> Decimal:
        if action == "charge" and not is_solar_charge:
            cost = power_kw * price_excl
        else:
            cost = Decimal("0")
        return cost.quantize(Decimal("0.00001"), rounding=ROUND_HALF_UP)

    # ── SoC simulatie / SoC simulation ───────────────────────────────────────

    def _update_soc(
        self, soc: Decimal, action: str,
        power_kw: Decimal, eff_charge_kw: Decimal
    ) -> Decimal:
        """
        Bereken de SoC na één uur met de gegeven actie.
        Calculate SoC after one hour with the given action.
        """
        if action == "charge":
            delta = power_kw * self._bat.efficiency / self._bat.usable_kwh * 100
            return min(soc + delta, self._bat.max_soc_pct)
        elif action == "discharge":
            delta = power_kw / self._bat.efficiency / self._bat.usable_kwh * 100
            return max(soc - delta, self._bat.min_soc_pct)
        elif action == "idle" and power_kw > Decimal("0"):
            # Passief huisverbruik dat niet door zon wordt gedekt, trekt de
            # batterij ook tijdens rust-uren leeg (bv. 's nachts).
            # Passive household consumption not covered by solar also drains
            # the battery during idle hours (e.g. at night).
            delta = power_kw / self._bat.efficiency / self._bat.usable_kwh * 100
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
    )

    return DecisionEngine(db, bat_config, price_config)
