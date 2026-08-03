#
# name:          decision_engine.py
# part of:       ha-energy-optimizer
# location:      /ha-energy-optimizer/ha-energy-optimizer/optimizer/decision_engine.py
# part version:  p_v0.12
# altered:       2026-07-30
#
# p_v0.12: off-grid uitvaldetectie daadwerkelijk functioneel gemaakt.
# _read_off_grid() (las een live HA-entiteit uit via een parameter die
# engine.py nooit meegaf — dus altijd False) vervangen door
# _read_offgrid_active(), die de door collectors/offgrid_monitor.py
# bijgehouden system_config.offgrid_active leest. Nieuwe methode
# _idle_schedule(): zolang off-grid actief is, wordt de hele beslisboom
# overgeslagen en gaat elk slot op "rust" — laden/ontladen op basis van
# marktprijs is zinloos/onwenselijk zonder netverbinding.
#
# p_v0.12: off-grid outage detection made actually functional.
# _read_off_grid() (read a live HA entity via a parameter engine.py never
# passed — so always False) replaced by _read_offgrid_active(), which
# reads system_config.offgrid_active kept up to date by
# collectors/offgrid_monitor.py. New method _idle_schedule(): while
# off-grid is active, the entire decision tree is skipped and every slot
# goes to "idle" — charging/discharging based on market price is
# meaningless/undesirable without a grid connection.
#
# p_v0.11: dynamische off-grid reserve toegevoegd — schuift tussen een
# hoge (dag) en lage (nacht) SoC-ondergrens. Omslagpunten: zonsopkomst+1u
# naar hoog, begin geleerd nachtverbruik+1u naar laag (gedetecteerd als
# eerste kwartier-slot waarna N opeenvolgende slots onder X% van het
# daggemiddelde blijven, X en N instelbaar). Alleen actief als
# system_config.has_offgrid_switch aan staat; anders exact het oude
# gedrag (statische self._reserve_soc()). Nieuwe klasse OffGridConfig,
# nieuwe methodes _dynamic_reserve_soc/_get_sunrise/_get_night_start.
#
# p_v0.11: dynamic off-grid reserve added — shifts between a high (day)
# and low (night) SoC floor. Transition points: sunrise+1h to high, start
# of learned night consumption+1h to low (detected as the first quarter
# slot after which N consecutive slots stay below X% of the daily
# average, X and N configurable). Only active if
# system_config.has_offgrid_switch is on; otherwise exactly the old
# behaviour (static self._reserve_soc()). New OffGridConfig class, new
# _dynamic_reserve_soc/_get_sunrise/_get_night_start methods.
#
# p_v0.10: HourForecast -> ForecastSlot, WindowHour -> WindowSlot, veld
# `hour` -> `slot_start` — puur een naamswijziging, zie optimizer/models.py
# p_v0.7 voor de volledige toelichting. Daarnaast: price_sell_excl
# toegevoegd aan WindowSlot en daadwerkelijk gebruikt in de
# negatieve-exportprijs-check (run()) en _reserve_for_future_negative_export
# — deze vergeleken voorheen de INKOOPprijs met de export-drempel, wat een
# verkeerde koppeling was zolang er geen aparte verkoopprijs bestond. Zie
# migratie 018.
#
# p_v0.10: HourForecast -> ForecastSlot, WindowHour -> WindowSlot, field
# `hour` -> `slot_start` — purely a naming change, see optimizer/models.py
# p_v0.7 for the full explanation. Also: price_sell_excl added to
# WindowSlot and actually used in the negative-export-price check (run())
# and _reserve_for_future_negative_export — these previously compared the
# BUY price against the export threshold, which was a mismatch for as long
# as no separate sell price existed. See migration 018.
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
from datetime import datetime, timedelta, time
from decimal import Decimal, ROUND_HALF_UP
from typing import Optional

from database.connection import DatabaseConnection
from collectors.consumption_learner import ConsumptionLearner
from .models import ForecastSlot, ScheduleSlot
from translations.translator import build_translator
from config.timeslot import SLOT_MINUTES, SLOT_HOURS, SLOT_TO_MEASUREMENT_FACTOR, SLOTS_PER_HOUR, SLOTS_PER_DAY
from config.localtime import now_local

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
class OffGridConfig:
    """
    Dynamische off-grid reserve — schuift tussen een hoge (dag) en lage
    (nacht) ondergrens, gekoppeld aan zonsopkomst en het geleerde
    nachtverbruikpatroon. Vervangt het vaste min_soc_pct als ondergrens
    zolang enabled=True; als enabled=False verandert er niets aan het
    bestaande gedrag (self._bat.min_soc_pct blijft de vaste ondergrens).

    Dynamic off-grid reserve — shifts between a high (day) and low (night)
    floor, tied to sunrise and the learned night-consumption pattern.
    Replaces the fixed min_soc_pct as the floor as long as enabled=True;
    if enabled=False, nothing changes about existing behaviour
    (self._bat.min_soc_pct stays the fixed floor).

    Alleen actief als het "Off-grid schakeling"-vinkje op de Systeem-pagina
    aan staat (system_config.has_offgrid_switch).
    Only active if the "Off-grid switching" checkbox on the System page is
    on (system_config.has_offgrid_switch).
    """
    enabled:             bool    = False
    reserve_high_pct:    Decimal = Decimal("10")
    reserve_low_pct:     Decimal = Decimal("5")
    night_threshold_pct: Decimal = Decimal("50")
    night_confirm_slots: int     = 8


@dataclass
class WindowSlot:
    """
    Eén uur in het beslissingsvenster met alle relevante data.
    One hour in the decision window with all relevant data.
    """
    forecast:       ForecastSlot
    price_excl:     Decimal
    # p_v0.9: verkoopprijs (excl. BTW) — apart van price_excl (inkoop). Start
    # van het daadwerkelijk gebruiken van de in/verkoopprijs-splitsing, zie
    # migratie 018 en optimizer/models.py p_v0.6 (ForecastSlot).
    # p_v0.9: sell price (excl. VAT) — separate from price_excl (buy).
    # Start of actually using the buy/sell price split, see migration 018
    # and optimizer/models.py p_v0.6 (ForecastSlot).
    price_sell_excl: Decimal
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

    def __init__(
        self, db: DatabaseConnection, bat: BatteryConfig, price: PriceConfig,
        offgrid: "OffGridConfig | None" = None,
    ):
        self._db      = db
        self._bat     = bat
        self._price   = price
        self._offgrid = offgrid or OffGridConfig()
        self._consumption_learner = ConsumptionLearner(db)
        self._tr    = build_translator(db)
        # p_v0.11: caches voor de dynamische off-grid reserve, geleegd bij
        # elke run() — voorkomt herhaalde DB-queries per kwartier-slot voor
        # dezelfde datum/weekdag binnen één rekencyclus.
        # p_v0.11: caches for the dynamic off-grid reserve, cleared on each
        # run() — avoids repeated DB queries per quarter slot for the same
        # date/weekday within one calculation cycle.
        self._sunrise_cache: dict = {}
        self._night_start_cache: dict = {}

    # ── Publieke interface / Public interface ─────────────────────────────────

    def run(
        self,
        forecasts: list[ForecastSlot],
        battery_temp_c: Optional[Decimal] = None,
    ) -> list[ScheduleSlot]:
        """
        Verwerk de prognoses en bepaal de optimale actie per uur.
        Process the forecasts and determine the optimal action per hour.

        Args:
            forecasts:          lijst van ForecastSlot objecten (48 uur aan
                                 kwartier-slots, dus 192 objecten)
            battery_temp_c:     huidige batterijtemperatuur voor vermogensbeperking

        Returns:
            Lijst van ScheduleSlot objecten klaar voor opslaan.
        """
        if not forecasts:
            return []

        # ── Stap 1: Initialisatie ─────────────────────────────────────────────
        # p_v0.12: off_grid komt nu uit system_config.offgrid_active,
        # bijgehouden door collectors/offgrid_monitor.py (leest elke paar
        # minuten een primaire + terugval-entiteit uit HA). Voorheen las
        # _read_off_grid() hier zelf live een entiteit uit via een
        # off_grid_entity_id-parameter die door engine.py nooit werd
        # meegegeven — dus off_grid was in de praktijk altijd False. Nu
        # daadwerkelijk functioneel, én sneller (DB-read i.p.v. live
        # HTTP-call per beslisronde).
        # p_v0.12: off_grid now comes from system_config.offgrid_active,
        # kept up to date by collectors/offgrid_monitor.py (reads a
        # primary + fallback entity from HA every few minutes). Previously
        # _read_off_grid() itself did a live entity read here via an
        # off_grid_entity_id parameter that engine.py never actually
        # passed — so off_grid was always False in practice. Now actually
        # functional, and faster (DB read instead of a live HTTP call per
        # decision round).
        off_grid = self._read_offgrid_active()
        eff_charge_kw, eff_discharge_kw = self._effective_power(battery_temp_c)
        price_factor_high, price_factor_low = self._price_factors(forecasts)
        # p_v0.11: caches legen voor de dynamische off-grid reserve — zie
        # __init__. reserve_soc wordt nu per slot berekend (in de lus
        # hieronder) i.p.v. hier één keer statisch, omdat de dynamische
        # reserve per tijdstip kan verschillen (hoog overdag, laag 's nachts).
        # p_v0.11: clear caches for the dynamic off-grid reserve — see
        # __init__. reserve_soc is now computed per slot (in the loop below)
        # instead of once statically here, because the dynamic reserve can
        # differ by time of day (high during the day, low at night).
        self._sunrise_cache.clear()
        self._night_start_cache.clear()

        window = self._build_window(forecasts)

        # Markeer al uitgevoerde uren (rolling horizon bescherming)
        # Mark already executed hours (rolling horizon protection)
        self._mark_executed(window)

        # ── Stap 2: Off-grid check ────────────────────────────────────────────
        # p_v0.12: pauzeer alle prijs-gestuurde beslissingen zolang
        # off-grid actief is — laden/ontladen op basis van marktprijs is
        # zinloos of zelfs onwenselijk zonder netverbinding. Alles op
        # "rust" totdat een volgende run (over enkele minuten, via
        # offgrid_monitor.py) meldt dat het net terug is.
        # p_v0.12: pause all price-driven decisions while off-grid is
        # active — charging/discharging based on market price is
        # meaningless or even undesirable without a grid connection.
        # Everything goes to "idle" until a next run (within a few
        # minutes, via offgrid_monitor.py) reports the grid is back.
        if off_grid:
            logger.warning(f"[decision_engine] {self._tr.get('RS11')}")
            return self._idle_schedule(window)

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

            # p_v0.11: dynamische off-grid reserve voor dít slot — zie
            # _dynamic_reserve_soc(). Als de off-grid schakeling uit staat
            # (self._offgrid.enabled=False), gedraagt dit zich exact als de
            # oude statische self._reserve_soc() — geen gedragsverandering.
            # p_v0.11: dynamic off-grid reserve for this slot — see
            # _dynamic_reserve_soc(). If off-grid switching is disabled
            # (self._offgrid.enabled=False), this behaves exactly like the
            # old static self._reserve_soc() — no behaviour change.
            reserve_soc = self._dynamic_reserve_soc(wh.forecast.slot_start)

            # Bereken dynamische SoC drempels voor dit uur
            nacht_soc = self._nacht_soc(wh.forecast.slot_start, reserve_soc)
            dag_soc   = self._dag_soc(wh.forecast.slot_start, reserve_soc)

            # Hoge prijs? → probeer te ontladen
            if price >= price_factor_high and not off_grid:
                if self._mogelijk_ontladen(wh, window, soc, reserve_soc,
                                           nacht_soc, dag_soc, eff_discharge_kw):
                    soc = self._update_soc(soc, wh.action, wh.power_kw, eff_discharge_kw)
                    continue

            # Zon-overschot? → laden van zon (evt. aangevuld met net bij negatieve prijs)
            if wh.surplus_kwh > Decimal("0.05"):
                grid_top_up = Decimal("0")

                # p_v0.9: price_sell_excl i.p.v. price (inkoop) — dit gaat
                # over de vraag of EXPORTEREN geld kost, dus de verkoopprijs
                # is hier de relevante prijs, niet de inkoopprijs. Zie
                # migratie 018 / ForecastSlot.price_sell_per_kwh.
                # p_v0.9: price_sell_excl instead of price (buy) — this is
                # about whether EXPORTING costs money, so the sell price is
                # the relevant price here, not the buy price. See migration
                # 018 / ForecastSlot.price_sell_per_kwh.
                if wh.price_sell_excl < self._price.negative_export_threshold_excl and soc < self._bat.max_soc_pct:
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
                        # p_v0.9: verkoopprijs in de melding — dát was de
                        # prijs die de net-bijlaad-beslissing triggerde.
                        # p_v0.9: sell price in the notification — that was
                        # the price that triggered the grid top-up decision.
                        self._set_reason(wh, "RS16", {
                            "surplus_kw": wh.surplus_kwh,
                            "grid_kw":    grid_top_up,
                            "price":      wh.price_sell_excl
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

    def _read_offgrid_active(self) -> bool:
        """
        Lees de door offgrid_monitor.py bijgehouden off-grid status uit
        system_config. Simpele, snelle DB-read i.p.v. een live HTTP-call
        naar HA — de daadwerkelijke detectie (primair + terugval-entiteit)
        gebeurt in collectors/offgrid_monitor.py, elke paar minuten.

        Read the off-grid status kept up to date by offgrid_monitor.py
        from system_config. A simple, fast DB read instead of a live HTTP
        call to HA — the actual detection (primary + fallback entity)
        happens in collectors/offgrid_monitor.py, every few minutes.

        Geeft False als has_offgrid_switch uit staat of bij een DB-fout —
        veilig terugvallen op "gewoon normaal doorgaan".
        Returns False if has_offgrid_switch is off or on a DB error —
        safely falls back to "just continue normally".
        """
        try:
            with self._db.cursor() as cur:
                cur.execute(
                    "SELECT has_offgrid_switch, offgrid_active "
                    "FROM system_config ORDER BY id DESC LIMIT 1"
                )
                row = cur.fetchone()
            if not row or not row.get("has_offgrid_switch"):
                return False
            return bool(row.get("offgrid_active"))
        except Exception as e:
            logger.debug(f"[decision_engine] Off-grid status niet leesbaar: {e}")
            return False

    def _idle_schedule(self, window: "list[WindowSlot]") -> list[ScheduleSlot]:
        """
        Bouw een schema van uitsluitend "rust"-slots — gebruikt zolang
        off-grid actief is. Geen enkele prijs-gestuurde laad/ontlaad-actie,
        SoC blijft op de startwaarde staan (we kunnen tijdens een
        stroomstoring toch niet voorspellen wat het eiland-systeem
        zelfstandig doet).

        Build a schedule of nothing but "idle" slots — used while off-grid
        is active. No price-driven charge/discharge action at all, SoC
        stays at the starting value (we can't predict what the island
        system does on its own during an outage anyway).
        """
        soc = window[0].forecast.soc_pct if window else Decimal("50")
        slots = []
        for wh in window:
            slots.append(ScheduleSlot(
                slot_start              = wh.forecast.slot_start,
                action                  = "idle",
                target_power_kw         = Decimal("0"),
                target_soc_pct          = soc,
                expected_saving         = Decimal("0"),
                expected_cost           = Decimal("0"),
                reason                  = self._tr.get("RS11"),
                reason_key              = "RS11",
                reason_params           = None,
                expected_solar_kw       = wh.forecast.solar_kw,
                expected_consumption_kw = wh.forecast.consumption_kw,
                expected_price          = wh.forecast.price_per_kwh,
                is_solar_charge         = False,
                grid_charge_kw          = Decimal("0"),
            ))
        return slots

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
        self, forecasts: list[ForecastSlot]
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

    def _dynamic_reserve_soc(self, dt: datetime) -> Decimal:
        """
        Dynamische off-grid ondergrens voor het gegeven tijdstip — schuift
        tussen reserve_high_pct (dag) en reserve_low_pct (nacht).

        Dynamic off-grid floor for the given timestamp — shifts between
        reserve_high_pct (day) and reserve_low_pct (night).

        Omslagpunten / Transition points:
          - naar hoog / to high: zonsopkomst + 1 uur / sunrise + 1 hour
          - naar laag / to low:  begin geleerd nachtverbruik + 1 uur /
                                  start of learned night consumption + 1 hour

        Als self._offgrid.enabled False is, of een van beide omslagpunten
        kan niet bepaald worden (bijv. nog te weinig geleerde data), valt
        dit terug op de oude statische self._reserve_soc() — precies het
        gedrag van vóór deze functie bestond.

        If self._offgrid.enabled is False, or either transition point
        cannot be determined (e.g. not enough learned data yet), this
        falls back to the old static self._reserve_soc() — exactly the
        behaviour from before this function existed.
        """
        if not self._offgrid.enabled:
            return self._reserve_soc()

        sunrise = self._get_sunrise(dt.date())
        night_start = self._get_night_start(dt.month, dt.weekday())

        if sunrise is None or night_start is None:
            logger.debug(
                "[decision_engine] Dynamische off-grid reserve: "
                "onvoldoende data (zonsopkomst of nachtpatroon ontbreekt), "
                "terugval op statische reserve"
            )
            return self._reserve_soc()

        to_high = (datetime.combine(dt.date(), sunrise) + timedelta(hours=1)).time()
        to_low  = (datetime.combine(dt.date(), night_start) + timedelta(hours=1)).time()

        is_high_period = to_high <= dt.time() < to_low
        pct = self._offgrid.reserve_high_pct if is_high_period else self._offgrid.reserve_low_pct
        return pct.quantize(Decimal("0.1"))

    def _get_sunrise(self, d) -> "time | None":
        """
        Haal zonsopkomsttijd op voor de gegeven datum uit weather_forecast,
        met caching voor de duur van één run().
        Fetch sunrise time for the given date from weather_forecast, cached
        for the duration of one run().
        """
        if d in self._sunrise_cache:
            return self._sunrise_cache[d]

        result = None
        try:
            with self._db.cursor() as cur:
                cur.execute(
                    "SELECT sun_rise FROM weather_forecast "
                    "WHERE DATE(forecast_for) = %(d)s AND sun_rise IS NOT NULL "
                    "ORDER BY forecast_for LIMIT 1",
                    {"d": d}
                )
                row = cur.fetchone()
            if row and row["sun_rise"]:
                raw = row["sun_rise"]
                if isinstance(raw, str):
                    h, m = raw.split(":")[:2]
                    result = time(int(h), int(m))
                else:
                    result = raw
        except Exception as e:
            logger.warning(f"[decision_engine] Zonsopkomst ophalen mislukt: {e}")

        self._sunrise_cache[d] = result
        return result

    def _get_night_start(self, month: int, dow: int) -> "time | None":
        """
        Detecteer het kwartier-slot waarop het geleerde gemiddelde
        nachtverbruik begint, voor de gegeven maand + weekdag, met caching
        voor de duur van één run().

        Detect the quarter slot at which the learned average night
        consumption begins, for the given month + weekday, cached for the
        duration of one run().

        Methode: eerste kwartier-slot (vanaf 16:00, doorlopend over
        middernacht) waarna night_confirm_slots opeenvolgende slots allemaal
        onder night_threshold_pct% van het daggemiddelde blijven.

        Method: first quarter slot (starting from 16:00, wrapping past
        midnight) after which night_confirm_slots consecutive slots all
        stay below night_threshold_pct% of the daily average.

        Returns None als er onvoldoende geleerde data is (nog geen volle
        dag aan slots met sample_count > 0).
        Returns None if there isn't enough learned data yet (no full day
        of slots with sample_count > 0).
        """
        cache_key = (month, dow)
        if cache_key in self._night_start_cache:
            return self._night_start_cache[cache_key]

        result = None
        try:
            with self._db.cursor() as cur:
                cur.execute(
                    "SELECT slot_of_day, kwh_avg FROM consumption_learning "
                    "WHERE month_of_year = %(m)s AND day_of_week = %(d)s "
                    "AND sample_count > 0 ORDER BY slot_of_day",
                    {"m": month, "d": dow}
                )
                rows = cur.fetchall()

            if len(rows) >= SLOTS_PER_DAY:
                values = {r["slot_of_day"]: Decimal(str(r["kwh_avg"])) for r in rows}
                if len(values) == SLOTS_PER_DAY:
                    daily_avg = sum(values.values()) / SLOTS_PER_DAY
                    threshold = daily_avg * self._offgrid.night_threshold_pct / 100
                    confirm_n = self._offgrid.night_confirm_slots

                    # Scan vanaf 16:00 (slot 64), doorlopend over middernacht
                    # Scan from 16:00 (slot 64), wrapping past midnight
                    start_scan = 16 * SLOTS_PER_HOUR
                    order = [(start_scan + i) % SLOTS_PER_DAY for i in range(SLOTS_PER_DAY)]
                    for pos, slot in enumerate(order):
                        window_slots = [order[(pos + k) % SLOTS_PER_DAY] for k in range(confirm_n)]
                        if all(values[s] < threshold for s in window_slots):
                            hour = slot // SLOTS_PER_HOUR
                            minute = (slot % SLOTS_PER_HOUR) * SLOT_MINUTES
                            result = time(hour, minute)
                            break
        except Exception as e:
            logger.warning(f"[decision_engine] Nachtstart-detectie mislukt: {e}")

        self._night_start_cache[cache_key] = result
        return result

    def _build_window(self, forecasts: list[ForecastSlot]) -> list[WindowSlot]:
        """
        Bouw het beslissingsvenster op vanuit de prognoses.
        Build the decision window from the forecasts.
        """
        window = []
        for f in forecasts:
            price_excl      = self._to_excl(f.price_per_kwh)
            price_sell_excl = self._to_excl(f.price_sell_per_kwh)
            surplus     = max(Decimal("0"), f.solar_kw - f.consumption_kw)
            tekort      = max(Decimal("0"), f.consumption_kw - f.solar_kw)
            window.append(WindowSlot(
                forecast=f,
                price_excl=price_excl,
                price_sell_excl=price_sell_excl,
                surplus_kwh=surplus,
                tekort_kwh=tekort,
            ))
        return window

    def _mark_executed(self, window: list[WindowSlot]) -> None:
        """
        Markeer uren die al uitgevoerd zijn (rolling horizon bescherming).
        Mark hours that are already executed (rolling horizon protection).
        """
        hours = [wh.forecast.slot_start for wh in window]
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
                row = executed_rows.get(wh.forecast.slot_start)
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

    def _soc_einde_dag(self, window: list[WindowSlot], soc_nu: Decimal) -> Decimal:
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
        now_date = now_local().date()
        for wh in window:
            if wh.forecast.slot_start.date() != now_date:
                break
            if wh.action == "charge":
                soc = min(soc + wh.power_kw * self._bat.efficiency * SLOT_HOURS
                          / self._bat.usable_kwh * 100, self._bat.max_soc_pct)
            elif wh.action in ("discharge",):
                soc = max(soc - wh.power_kw / self._bat.efficiency * SLOT_HOURS
                          / self._bat.usable_kwh * 100, self._bat.min_soc_pct)
        return soc

    def _soc_zonsopgang(self, window: list[WindowSlot], soc_nu: Decimal) -> Decimal:
        """
        Schat de SoC bij zonsopgang morgen (06:00).
        Estimate SoC at tomorrow's sunrise (06:00).

        p_v0.9: × SLOT_HOURS toegevoegd, zie _soc_einde_dag hierboven.
        p_v0.9: × SLOT_HOURS added, see _soc_einde_dag above.
        """
        soc = soc_nu
        target_hour = (now_local() + timedelta(days=1)).replace(hour=6, minute=0, second=0)
        for wh in window:
            if wh.forecast.slot_start >= target_hour:
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
        wh: WindowSlot,
        window: list[WindowSlot],
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
        wh: WindowSlot,
        window: list[WindowSlot],
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
        wh: WindowSlot,
        window: list[WindowSlot],
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
        wh: WindowSlot,
        window: list[WindowSlot],
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

    def _set_reason(self, wh: "WindowSlot", key: str, params: dict | None = None) -> None:
        """
        Zet reason tekst en sla key+params op voor hervertaling.
        Set reason text and store key+params for re-translation.
        """
        wh.reason_key    = key
        wh.reason_params = params or {}
        wh.reason        = self._tr.get(key, params)

    def _anti_cycling(self, window: list[WindowSlot]) -> None:
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

    def _to_slots(self, window: list[WindowSlot]) -> list[ScheduleSlot]:
        """
        Zet WindowSlot objecten om naar ScheduleSlot objecten.
        Convert WindowSlot objects to ScheduleSlot objects.
        """
        slots = []
        soc = window[0].forecast.soc_pct if window else Decimal("50")

        for wh in window:
            price_excl = wh.price_excl
            saving = self._calc_saving(wh.action, wh.power_kw, price_excl, wh.is_solar_charge)
            cost   = self._calc_cost(wh.action, wh.power_kw, price_excl, wh.is_solar_charge, wh.grid_top_up_kwh)

            # Vermogen dat specifiek uit het net wordt geladen: bij een
            # gemengd (zon+net) slot is dat alleen de top-up bovenop het
            # zon-overschot; bij een puur net-slot is dat het volledige
            # laadvermogen. grid_top_up_kwh (ondanks de naam, een vermogen)
            # is bij een puur net-slot altijd 0 gebleven — daarom hier
            # expliciet uitgesplitst i.p.v. rechtstreeks doorgegeven.
            # Power specifically charged from the grid: for a mixed
            # (solar+grid) slot that's only the top-up on top of the solar
            # surplus; for a pure grid slot that's the full charge power.
            # grid_top_up_kwh (despite the name, a power) stays 0 for a pure
            # grid slot — hence explicitly split out here rather than
            # passed straight through.
            if wh.action == "charge":
                grid_charge_kw = wh.grid_top_up_kwh if wh.is_solar_charge else wh.power_kw
            else:
                grid_charge_kw = Decimal("0")

            slots.append(ScheduleSlot(
                slot_start             = wh.forecast.slot_start,
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
                # p_v0.9: zon/net-opsplitsing bewaren i.p.v. verloren laten
                # gaan — zie migratie 016.
                # p_v0.9: preserve solar/grid split instead of letting it
                # get lost — see migration 016.
                is_solar_charge        = wh.is_solar_charge,
                grid_charge_kw         = grid_charge_kw,
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
        self, window: list["WindowSlot"], current_index: int
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
            # p_v0.9: price_sell_excl i.p.v. price_excl (inkoop) — zelfde
            # reden als bij de hoofdcheck in run(): dit gaat over export.
            # p_v0.9: price_sell_excl instead of price_excl (buy) — same
            # reason as the main check in run(): this is about export.
            if (w.price_sell_excl < self._price.negative_export_threshold_excl
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

    # p_v0.11: dynamische off-grid reserve — alleen actief als het vinkje
    # op de Systeem-pagina aan staat (has_offgrid_switch). Staat het uit,
    # dan verandert er niets aan het bestaande gedrag.
    # p_v0.11: dynamic off-grid reserve — only active if the checkbox on
    # the System page is on (has_offgrid_switch). If off, nothing changes
    # about existing behaviour.
    offgrid_config = OffGridConfig(
        enabled              = bool(cfg.get("has_offgrid_switch", False)),
        reserve_high_pct     = Decimal(str(cfg.get("offgrid_reserve_high_pct") or "10")),
        reserve_low_pct      = Decimal(str(cfg.get("offgrid_reserve_low_pct") or "5")),
        night_threshold_pct  = Decimal(str(cfg.get("offgrid_night_threshold_pct") or "50")),
        night_confirm_slots  = int(cfg.get("offgrid_night_confirm_slots") or 8),
    )

    return DecisionEngine(db, bat_config, price_config, offgrid_config)

