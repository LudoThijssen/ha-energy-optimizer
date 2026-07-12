# 
# name:          strategy.py
# part of:       ha-energy-optimizer
# location:      /ha-energy-optimizer/ha-energy-optimizer/optimizer/strategy.py
# part version:  p_v0.4
# altered:       2026-07-05
#
# Decision rules for home battery optimization with a dynamic electricity contract.
# Beslisregels voor thuisbatterij-optimalisatie met een dynamisch stroomcontract.
#
# ── Priority order / Prioriteitsvolgorde ────────────────────────────────────
#
#   PLANNING PHASE (evening, for next day) / PLANNINGSFASE (avond, voor volgende dag):
#     1. Calculate expected solar yield tomorrow / Bereken verwachte zonopbrengst morgen
#     2. Calculate expected home consumption tomorrow / Bereken verwacht verbruik morgen
#     3. Determine required free battery capacity at sunrise / Bepaal benodigde vrije capaciteit
#     4. Select best hours tonight to discharge to that target / Selecteer beste uren vanavond
#
#   REAL-TIME PHASE (hourly) / REAL-TIME FASE (per uur):
#     5. Solar surplus → direct use (implicit) → battery → grid
#        Zonne-overschot → direct verbruik (impliciet) → batterij → net
#     6. Negative/zero export price → notify user + limit export
#        Negatieve/nul terugleverprijs → gebruiker melden + export beperken
#     7. High price → discharge (within working power limits)
#        Hoge prijs → ontladen (binnen werkzame vermogensgrenzen)
#     8. Low price + sufficient spread → charge from grid
#        Lage prijs + voldoende spreiding → laden vanaf net
#
# ── Power limits / Vermogensgrenzen ─────────────────────────────────────────
#   max_power_kw       — absolute hardware limit (fuse / zekering)
#   working_power_kw   — preferred operating power (protects battery life)
#   temp_derating      — automatic reduction above temperature threshold

from dataclasses import dataclass, field
from decimal import Decimal, ROUND_HALF_UP
from typing import Optional
import logging

logger = logging.getLogger(__name__)


# ── Data classes / Dataklassen ───────────────────────────────────────────────

@dataclass
class DayPriceStats:
    """
    Summary statistics for today's electricity prices (excl. VAT).
    Samenvattende statistieken voor stroomprijzen van vandaag (excl. BTW).
    """
    cheapest_today: Decimal        # Lowest price / Laagste prijs
    most_expensive_today: Decimal  # Highest price / Hoogste prijs
    average_today: Decimal         # Average price / Gemiddelde prijs
    hours_ranked: list             # All hours sorted cheapest→most expensive
    price_incl_tax: bool
    vat_multiplier: Decimal


@dataclass
class SolarOutlook:
    """
    Solar energy outlook for tomorrow.
    Zonne-energie-verwachting voor morgen.
    """
    sunshine_pct: Decimal          # Verwacht zonpercentage
    estimated_yield_kwh: Decimal   # Estimated solar production / Geschatte zonopbrengst


@dataclass
class DayBalancePlan:
    """
    Result of the evening planning calculation.
    Resultaat van de avondplanningsberekening.

    Determines how much the battery should be discharged tonight
    to make room for tomorrow's solar production.
    Bepaalt hoeveel de batterij vanavond ontladen moet worden
    om ruimte te maken voor de zonopbrengst van morgen.
    """
    discharge_needed_kwh: Decimal  # Total to discharge tonight / Totaal te ontladen vanavond
    target_soc_pct: Decimal        # Target SoC at sunrise / Doel-laadtoestand bij zonsopgang
    best_hours: list               # Ranked discharge hours (datetime list)
    reason: str


@dataclass
class PowerLimits:
    """
    Effective power limits for the current hour, considering temperature.
    Effectieve vermogensgrenzen voor het huidige uur, rekening houdend met temperatuur.
    """
    charge_kw: Decimal             # Effectieve laadgrens
    discharge_kw: Decimal          # Effective discharge limit / Effectieve ontlaadgrens
    derated: bool                  # Whether temperature derating is active
    reason: str


# ── Main strategy class / Hoofdstrategie-klasse ──────────────────────────────

class Strategy:
    """
    Full battery optimization strategy with configurable parameters.
    Volledige batterijoptimalisatiestrategie met configureerbare parameters.

    All parameters have sensible defaults but should be configured
    per installation via the GUI and database.
    Alle parameters hebben verstandige standaardwaarden maar moeten per
    installatie worden ingesteld via de GUI en database.
    """

    def __init__(
        self,

        # ── Efficiency / Rendement ───────────────────────────────────────────
        # Round-trip efficiency: 75 = 100 kWh in → 75 kWh out.
        # Round-trip rendement: 75 = 100 kWh in → 75 kWh uit.
        battery_efficiency_pct: Decimal = Decimal("75"),

        # ── State of charge limits / Laadtoestand-grenzen ───────────────────
        min_soc_pct: Decimal = Decimal("10"),
        max_soc_pct: Decimal = Decimal("95"),

        # ── Power limits / Vermogensgrenzen ─────────────────────────────────
        # Absolute hardware maximum (fuse limit).
        # Absoluut hardware-maximum (zekeringslimiet).
        # 1-phase 16A: 16 × 230V = 3680W = 3.68 kW
        # 3-phase 16A: 3 × 16 × 230V = 11040W = 11.04 kW
        max_charge_kw: Decimal = Decimal("3.68"),
        max_discharge_kw: Decimal = Decimal("3.68"),

        # Preferred working power — lower than max to protect battery life.
        # Voorkeurswerkvermogen — lager dan maximum om levensduur te beschermen.
        # Set to None to use max_charge_kw / max_discharge_kw.
        # Stel in op None om max_charge_kw / max_discharge_kw te gebruiken.
        working_charge_kw: Optional[Decimal] = Decimal("2.5"),
        working_discharge_kw: Optional[Decimal] = Decimal("2.5"),

        # ── Temperature derating / Temperatuurafhankelijke begrenzing ────────
        # Above this battery temperature, working power is reduced.
        # Boven deze batterijtemperatuur wordt het werkvermogen verminderd.
        temp_derating_threshold_c: Decimal = Decimal("35"),

        # Factor applied to working power when temperature is exceeded.
        # Factor toegepast op werkvermogen als temperatuurgrens overschreden is.
        # 0.7 = reduce to 70% of working power / terugbrengen naar 70% van werkvermogen.
        temp_derating_factor: Decimal = Decimal("0.7"),

        # ── Discharge thresholds / Ontlaaddrempelwaarden ─────────────────────
        # Never discharge below this price (excl. VAT).
        # Nooit ontladen onder deze prijs (excl. BTW).
        hard_min_discharge_price_excl: Decimal = Decimal("0.05"),

        # Minimum spread ratio to consider discharging at peak price.
        # Minimale spreidingsverhouding om bij piekprijs te ontladen.
        # 2.0 = cheapest must be < half of most expensive.
        # 2,0 = goedkoopste moet < helft van duurste zijn.
        min_spread_ratio_for_discharge: Decimal = Decimal("1.5"),

        # Current price must be within this fraction of today's peak.
        # Huidige prijs moet binnen deze fractie van het dagmaximum liggen.
        discharge_near_peak_fraction: Decimal = Decimal("0.75"),

        # Price is "extremely high" at this multiple of today's average.
        # Prijs is "extreem hoog" bij dit veelvoud van het daggemiddelde.
        extreme_price_multiplier: Decimal = Decimal("2.5"),

        # ── Negative export price handling / Negatieve terugleverprijs ───────
        # Below this price (excl. VAT), notify user and limit grid export.
        # Onder deze prijs (excl. BTW) gebruiker melden en netexport beperken.
        negative_export_threshold_excl: Decimal = Decimal("0.00"),

        # Notify user when export price drops below this level.
        # Gebruiker melden als terugleverprijs onder dit niveau daalt.
        notify_export_threshold_excl: Decimal = Decimal("0.02"),

        # ── Laaddrempelwaarden ─────────────────────────────────────────────────
        # Current price must be within this fraction of today's cheapest.
        # Huidige prijs moet binnen deze fractie van het dagminimum liggen.
        charge_near_cheapest_fraction: Decimal = Decimal("1.15"),

        # Minimum sunshine % tomorrow to consider battery refillable by solar.
        # Minimaal zonpercentage morgen om batterij hervulbaar via zon te beschouwen.
        min_sunshine_pct_for_refill: Decimal = Decimal("40"),

        # ── Day balance planning / Dagbalansplanning ──────────────────────────
        # Expected average hourly home consumption (kWh).
        # Verwacht gemiddeld uurlijks huisverbruik (kWh).
        avg_consumption_kwh: Decimal = Decimal("0.5"),

        # Safety margin: keep this % of battery capacity as buffer at sunrise.
        # Veiligheidsmarge: houd dit % van batterijcapaciteit als buffer bij zonsopgang.
        sunrise_buffer_pct: Decimal = Decimal("10"),

        # ── VAT / BTW ────────────────────────────────────────────────────────
        price_incl_tax: bool = True,
        vat_pct: Decimal = Decimal("21.0"),

        # ── Depreciation / Afschrijving ───────────────────────────────────────
        # Cost per kWh cycled through battery (€/kWh).
        # Kosten per kWh gecycleerd door batterij (€/kWh).
        # Calculate as: battery_cost / (expected_cycles × usable_capacity_kwh)
        depreciation_per_kwh: Decimal = Decimal("0"),

        # ── Usable battery capacity / Bruikbare batterijcapaciteit ───────────
        usable_capacity_kwh: Decimal = Decimal("10"),

        # ── Solar charge threshold / Zon-laaddrempel ─────────────────────────
        # Block grid charging when expected solar >= this fraction of capacity.
        # Blokkeer nettoladen als verwachte zon >= deze fractie van capaciteit.
        solar_charge_threshold: Decimal = Decimal("0.80"),
        max_price_to_charge_excl: Decimal = Decimal("0.10"),
    ):
        self.efficiency                    = battery_efficiency_pct / 100
        self.min_soc                       = min_soc_pct
        self.max_soc                       = max_soc_pct
        self.max_charge_kw                 = max_charge_kw
        self.max_discharge_kw              = max_discharge_kw
        self.working_charge_kw             = working_charge_kw or max_charge_kw
        self.working_discharge_kw          = working_discharge_kw or max_discharge_kw
        self.temp_derating_threshold_c     = temp_derating_threshold_c
        self.temp_derating_factor          = temp_derating_factor
        self.hard_min_discharge            = hard_min_discharge_price_excl
        self.min_spread_ratio              = min_spread_ratio_for_discharge
        self.discharge_near_peak           = discharge_near_peak_fraction
        self.extreme_price_multiplier      = extreme_price_multiplier
        self.negative_export_threshold     = negative_export_threshold_excl
        self.notify_export_threshold       = notify_export_threshold_excl
        self.charge_near_cheapest          = charge_near_cheapest_fraction
        self.min_sunshine_refill           = min_sunshine_pct_for_refill
        self.avg_consumption_kwh           = avg_consumption_kwh
        self.sunrise_buffer_pct            = sunrise_buffer_pct
        self.price_incl_tax                = price_incl_tax
        self.solar_charge_threshold        = solar_charge_threshold
        self.max_price_to_charge_excl      = max_price_to_charge_excl
        self.vat_multiplier                = Decimal("1") + vat_pct / 100
        self.depreciation_per_kwh          = depreciation_per_kwh
        self.usable_capacity_kwh           = usable_capacity_kwh

        # Minimum spread factor to justify grid charging (derived from efficiency).
        # Minimale spreidingsfactor om laden vanaf net te rechtvaardigen (afgeleid van rendement).
        self.required_spread_factor = (Decimal("1") / self.efficiency).quantize(
            Decimal("0.001"), rounding=ROUND_HALF_UP
        )

    # ── Day balance planning / Dagbalansplanning ─────────────────────────────

    def plan_day_balance(
        self,
        current_soc_pct: Decimal,
        solar_outlook: SolarOutlook,
        today_prices_excl: list,          # list of (datetime, Decimal) pairs sorted by hour
        hours_until_sunrise: int = 8,
    ) -> DayBalancePlan:
        """
        Evening planning: calculate how much to discharge tonight to make room
        for tomorrow's solar production, using the best-priced hours.

        Avondplanning: bereken hoeveel vanavond ontladen moet worden om ruimte
        te maken voor de zonopbrengst van morgen, via de meest gunstige uren.

        Core formula / Kernformule:
            free_capacity_needed = solar_yield_tomorrow - consumption_tomorrow
            free_capacity_available = (max_soc - current_soc) / 100 × usable_kwh
            discharge_needed = max(0, free_capacity_needed - free_capacity_available)

        Target SoC at sunrise / Doel-laadtoestand bij zonsopgang:
            target_soc = max(min_soc + buffer, current_soc - discharge_needed/usable × 100)
        """
        solar_kwh      = solar_outlook.estimated_yield_kwh
        consumption_kwh = self.avg_consumption_kwh * 24  # full day estimate

        # How much capacity do we need free by sunrise?
        # Hoeveel capaciteit moeten we vrij hebben bij zonsopgang?
        free_needed = max(Decimal("0"), solar_kwh - consumption_kwh)

        # How much is currently free?
        # Hoeveel is er momenteel vrij?
        current_free = (self.max_soc - current_soc_pct) / 100 * self.usable_capacity_kwh

        # How much do we need to discharge tonight?
        # Hoeveel moeten we vanavond ontladen?
        discharge_needed = max(Decimal("0"), free_needed - current_free)

        # Target SoC = current − discharge, floored at min_soc + buffer.
        # Doel-laadtoestand = huidig − ontlading, met vloer bij min_soc + buffer.
        buffer_pct     = self.sunrise_buffer_pct
        discharge_pct  = discharge_needed / self.usable_capacity_kwh * 100
        target_soc     = max(
            self.min_soc + buffer_pct,
            current_soc_pct - discharge_pct
        ).quantize(Decimal("1"), rounding=ROUND_HALF_UP)

        # Select the best hours for discharging tonight (after 18:00, highest price first).
        # Only use evening hours — avoid discharging during the day when solar may charge.
        # Selecteer de beste avonduren voor ontladen (na 18:00, hoogste prijs eerst).
        # Alleen avonduren — voorkom ontladen overdag als zon kan laden.
        from datetime import time as _time
        # Evening hours (18:00-23:00) preferred for discharge
        # Early morning hours (00:00-06:00) as secondary option
        # Avonduren (18:00-23:00) hebben voorkeur voor ontladen
        # Vroege ochtenduren (00:00-06:00) als tweede keuze
        evening_hours = [
            (dt, p) for dt, p in today_prices_excl
            if p >= self.hard_min_discharge
            and dt.hour >= 18
        ]
        morning_hours = [
            (dt, p) for dt, p in today_prices_excl
            if p >= self.hard_min_discharge
            and 0 <= dt.hour <= 6
        ]
        # Use evening hours; supplement with morning hours if not enough
        # Gebruik avonduren; vul aan met ochtenduren als er niet genoeg zijn
        available = evening_hours
        if len(available) < 3:
            available = available + morning_hours
        if not available:
            available = [
                (dt, p) for dt, p in today_prices_excl
                if p >= self.hard_min_discharge
            ]
        best_hours = sorted(available, key=lambda x: x[1], reverse=True)

        reason = (
            f"Solar tomorrow: {solar_kwh:.1f} kWh, "
            f"consumption: {consumption_kwh:.1f} kWh, "
            f"free needed: {free_needed:.1f} kWh, "
            f"discharge tonight: {discharge_needed:.1f} kWh → "
            f"Zon morgen: {solar_kwh:.1f} kWh, verbruik: {consumption_kwh:.1f} kWh, "
            f"vrij nodig: {free_needed:.1f} kWh, ontladen vanavond: {discharge_needed:.1f} kWh → "
            f"doel-laadtoestand bij zonsopgang: {target_soc:.0f}%"
        )

        return DayBalancePlan(
            discharge_needed_kwh=discharge_needed,
            target_soc_pct=target_soc,
            best_hours=[dt for dt, _ in best_hours],
            reason=reason,
        )

    # ── Real-time decision / Real-time beslissing ────────────────────────────

    def decide(
        self,
        current_price: Decimal,
        export_price: Decimal,             # May differ from import price / Kan afwijken van importprijs
        solar_kw: Decimal,
        consumption_kw: Decimal,
        soc_pct: Decimal,
        day_stats: DayPriceStats,
        battery_temp_c: Optional[Decimal] = None,
        solar_outlook: Optional[SolarOutlook] = None,
        day_balance_plan: Optional[DayBalancePlan] = None,
        last_charge_price_excl: Optional[Decimal] = None,
    ) -> tuple[str, Decimal, str, list[str], bool]:
        """
        Decide the battery action for this hour.
        Bepaal de batterijactie voor dit uur.

        Returns (action, target_power_kw, reason, notifications, is_solar_charge).
        Geeft (actie, doelvermogen_kw, reden, meldingen, is_zonne_lading) terug.

        notifications is a list of user-facing messages (may be empty).
        notifications is een lijst van gebruikersmeldingen (kan leeg zijn).

        is_solar_charge is True only when action == 'charge' and the energy
        comes from solar surplus (free) rather than the grid (paid).
        is_solar_charge is alleen True als action == 'charge' en de energie
        van zonne-overschot komt (gratis) i.p.v. van het net (betaald).
        """
        price_excl      = self._to_excl(current_price)
        export_excl     = self._to_excl(export_price)
        surplus_kw      = solar_kw - consumption_kw
        notifications   = []
        power_limits    = self._effective_power(battery_temp_c)

        # ── Step 1: Negative / very low export price ─────────────────────────
        # Stap 1: Negatieve / zeer lage terugleverprijs
        if export_excl <= self.notify_export_threshold:
            notif = self._build_negative_price_notification(export_excl, surplus_kw)
            if notif:
                notifications.append(notif)

        # ── Step 2: Solar surplus handling ───────────────────────────────────
        # Stap 2: Verwerking zonne-overschot
        if surplus_kw > Decimal("0.05"):

            # Kunnen we het opslaan?
            if soc_pct < self.max_soc:
                power = min(surplus_kw, power_limits.charge_kw)
                reason = (
                    f"Zonne-overschot {surplus_kw:.2f} kW — batterij laden{power_limits.reason}"
                )
                return "charge", power, reason, notifications, True

            # Battery full — must export. Is it profitable?
            # Batterij vol — moet terugleveren. Is het winstgevend?
            if export_excl <= self.negative_export_threshold:
                # Exporting costs money — limit export via inverter.
                # Terugleveren kost geld — export beperken via inverter.
                notifications.append(
                    "EXPORT_LIMIT: Stel inverter terugleververmogen in op 0W. "
                    "Zonnepanelen op maximale productie maar terugleverprijs is negatief."
                )
                return (
                    "idle",
                    Decimal("0"),
                    f"Batterij vol, terugleverprijs {export_excl:.4f} €/kWh — export beperken",
                    notifications,
                    False,
                )

            # Profitable export — allow it (priority 3).
            # Winstgevende teruglevering — toestaan (prioriteit 3).
            return (
                "self_consume",
                Decimal("0"),
                f"Batterij vol, overschot {surplus_kw:.2f} kW teruggeleverd",
                notifications,
                False,
            )

        # ── Step 3: Day balance discharge (evening planning) ──────────────────
        # Stap 3: Dagbalans-ontlading (avondplanning)
        if (
            day_balance_plan
            and day_balance_plan.discharge_needed_kwh > Decimal("0.5")
            and soc_pct > day_balance_plan.target_soc_pct
            and day_stats  # prices available / prijzen beschikbaar
        ):
            # Are we in one of the planned best discharge hours?
            # Zitten we in een van de geplande beste ontlaaduren?
            from datetime import datetime
            current_hour = datetime.now().replace(minute=0, second=0, microsecond=0)
            if current_hour in day_balance_plan.best_hours:
                power = power_limits.discharge_kw
                return (
                    "discharge",
                    power,
                    f"Dagbalans: ruimte maken voor zonopbrengst morgen — doel {day_balance_plan.target_soc_pct:.0f}%",
                    notifications,
                    False,
                )

        # ── Step 4: Price-based discharge ────────────────────────────────────
        # Stap 4: Prijsgebaseerd ontladen
        should_dis, dis_reason = self._should_discharge(
            price_excl, soc_pct, day_stats, solar_outlook, last_charge_price_excl
        )
        if should_dis:
            power = power_limits.discharge_kw
            return "discharge", power, dis_reason, notifications, False

        # ── Step 5: Price-based grid charging ────────────────────────────────
        # Stap 5: Prijsgebaseerd laden vanaf net
        should_chg, chg_reason = self._should_charge_from_grid(
            price_excl, soc_pct, day_stats, solar_outlook
        )
        if should_chg:
            power = power_limits.charge_kw
            return "charge", power, chg_reason, notifications, False

        # ── Step 6: Idle ─────────────────────────────────────────────────────
        return (
            "idle",
            Decimal("0"),
            "Geen voordelige actie dit uur",
            notifications,
            False,
        )

    # ── Power limits with temperature derating ───────────────────────────────

    def _effective_power(
        self, battery_temp_c: Optional[Decimal]
    ) -> PowerLimits:
        """
        Calculate effective power limits, applying temperature derating if needed.
        Bereken effectieve vermogensgrenzen, met temperatuurverlaging indien nodig.
        """
        charge_kw    = min(self.working_charge_kw, self.max_charge_kw)
        discharge_kw = min(self.working_discharge_kw, self.max_discharge_kw)
        derated      = False
        reason       = ""

        if (
            battery_temp_c is not None
            and battery_temp_c > self.temp_derating_threshold_c
        ):
            charge_kw    = (charge_kw * self.temp_derating_factor).quantize(
                Decimal("0.01"), rounding=ROUND_HALF_UP
            )
            discharge_kw = (discharge_kw * self.temp_derating_factor).quantize(
                Decimal("0.01"), rounding=ROUND_HALF_UP
            )
            derated      = True
            reason       = (
                f" [derated: {battery_temp_c:.1f}°C > "
                f"{self.temp_derating_threshold_c}°C threshold / "
                f"vermogen verlaagd: temperatuur te hoog]"
            )
            logger.info(
                f"[strategy] Temperatuurverlaging actief: {battery_temp_c:.1f}°C — "
                f"laden {charge_kw:.2f} kW, ontladen {discharge_kw:.2f} kW"
            )

        return PowerLimits(
            charge_kw=charge_kw,
            discharge_kw=discharge_kw,
            derated=derated,
            reason=reason,
        )

    # ── Discharge logic / Ontlaadlogica ──────────────────────────────────────

    def _should_discharge(
        self,
        price_excl: Decimal,
        soc_pct: Decimal,
        day_stats: Optional[DayPriceStats],
        solar_outlook: Optional[SolarOutlook],
        last_charge_price_excl: Optional[Decimal] = None,
    ) -> tuple[bool, str]:
        if not day_stats:
            return False, ""

        # Harde ondergrens
        if price_excl < self.hard_min_discharge:
            return False, ""

        # SoC protection / SoC-bescherming
        if soc_pct <= self.min_soc + Decimal("2"):
            return False, ""

        # Anti-cycling: don't discharge if the energy in the battery was
        # just charged at a price too close to the current price — the
        # round-trip efficiency loss would exceed any gain.
        # Anti-cycling: niet ontladen als de energie in de batterij net
        # geladen is tegen een prijs te dicht bij de huidige prijs — het
        # rendementsverlies zou elke winst overstijgen.
        if last_charge_price_excl is not None:
            # Minimum price needed to break even on a charge/discharge cycle,
            # plus a small margin for it to be worthwhile.
            # Minimale prijs nodig om break-even te draaien op een laad/ontlaad-
            # cyclus, plus een kleine marge om het de moeite waard te maken.
            break_even = (
                last_charge_price_excl / self.efficiency
                + self.depreciation_per_kwh
            )
            min_worthwhile = break_even * Decimal("1.10")  # require 10% margin
            if price_excl < min_worthwhile:
                return (
                    False,
                    f"Anti-cycling: prijs {price_excl:.4f} te dicht bij recente laadprijs "
                    f"{last_charge_price_excl:.4f} (break-even {break_even:.4f}) — rust",
                )

        cheapest       = day_stats.cheapest_today
        most_expensive = day_stats.most_expensive_today
        average        = day_stats.average_today

        # Regel A: Extreem hoge prijs
        if price_excl >= average * self.extreme_price_multiplier:
            return (
                True,
                f"Extreem hoge prijs {price_excl:.4f} ≥ "
                f"{self.extreme_price_multiplier}× gem {average:.4f} €/kWh excl. — ontladen",
            )

        # Regel B: Grote spreiding + nabij piekprijs
        # Use absolute spread to handle negative prices correctly
        # Gebruik absoluut verschil voor correcte verwerking van negatieve prijzen
        abs_cheapest = abs(cheapest) if cheapest < 0 else cheapest
        if cheapest < 0:
            # Negative cheapest: spread = most_expensive - cheapest (always positive)
            # Negatieve goedkoopste: spread = duurste - goedkoopste (altijd positief)
            spread_ratio = (
                (most_expensive - cheapest) / abs_cheapest
                if abs_cheapest > Decimal("0.001") else Decimal("10")
            )
        elif cheapest > Decimal("0.001"):
            spread_ratio = most_expensive / cheapest
        else:
            spread_ratio = Decimal("1")
        near_peak = price_excl >= most_expensive * self.discharge_near_peak

        if spread_ratio >= self.min_spread_ratio and near_peak:
            base = (
                f"Spread {spread_ratio:.2f}× ≥ {self.min_spread_ratio}×, "
                f"price {price_excl:.4f} near peak {most_expensive:.4f} €/kWh excl."
            )
            if solar_outlook is not None:
                if solar_outlook.sunshine_pct >= self.min_sunshine_refill:
                    return (
                        True,
                        base + f" + {solar_outlook.sunshine_pct:.0f}% sun tomorrow — "
                               f"discharging / + zon morgen — ontladen",
                    )
                else:
                    # Not enough sun to refill — only discharge if SoC is high enough
                    # to cover tomorrow's needs from remaining charge.
                    # Niet genoeg zon — alleen ontladen als SoC hoog genoeg is
                    # om morgen nog voldoende lading over te hebben.
                    min_reserve = self.min_soc + Decimal("20")  # keep 20% above min
                    if soc_pct > min_reserve + Decimal("15"):
                        return (
                            True,
                            base + f" (low sun {solar_outlook.sunshine_pct:.0f}%, "
                                   f"but SoC {soc_pct:.0f}% allows discharge) / "
                                   f"(weinig zon maar SoC {soc_pct:.0f}% laat ontladen toe)",
                        )
                    return False, ""
            else:
                return True, base + " (no solar outlook) — discharging / ontladen"

        return False, ""

    # ── Laden-van-net-logica ─────────────────────────────────────────────────

    def _should_charge_from_grid(
        self,
        price_excl: Decimal,
        soc_pct: Decimal,
        day_stats: Optional[DayPriceStats],
        solar_outlook: Optional["SolarOutlook"] = None,
    ) -> tuple[bool, str]:
        if not day_stats:
            return False, ""
        # Don't charge from grid if solar will fill battery anyway
        # Laad niet van net als zon de batterij toch al vult
        solar_threshold = self.solar_charge_threshold
        if solar_outlook and solar_outlook.estimated_yield_kwh >= self.usable_capacity_kwh * solar_threshold:
            return False, "Voldoende zon verwacht — laden van net niet nodig"
            
        if soc_pct >= self.max_soc - Decimal("2"):
            return False, ""

        cheapest       = day_stats.cheapest_today
        most_expensive = day_stats.most_expensive_today

        # Spread check — handles negative cheapest prices correctly
        # Spreadcontrole — verwerkt negatieve goedkope prijzen correct
        if cheapest < 0:
            # When cheapest is negative, any positive peak means good spread
            # Als goedkoopste negatief is, geeft elke positieve piek goede spread
            spread_ok = most_expensive > Decimal("0.05")
        elif cheapest > Decimal("0.001"):
            spread_ok = most_expensive >= cheapest * self.required_spread_factor
        else:
            spread_ok = most_expensive >= self.required_spread_factor * Decimal("0.05")
        # Negative prices: ALWAYS charge — free or paid electricity
        # Negatieve prijzen: ALTIJD laden — gratis of betaalde stroom
        if price_excl < 0:
            dep = (
                f" + dep {self.depreciation_per_kwh:.4f} €/kWh"
                if self.depreciation_per_kwh > 0 else ""
            )
            return (
                True,
                f"Negative price {price_excl:.4f} €/kWh excl. — "
                f"charging from grid is free or paid{dep} / "
                f"Negatieve prijs — laden van net is gratis of wordt betaald",
            )

        # near_cheapest: price is close to cheapest of the day
        # When cheapest < 0: multiply makes it more negative — use range-based check
        # near_cheapest: prijs ligt dicht bij de goedkoopste van de dag
        # Als goedkoopste < 0: vermenigvuldigen maakt het negatiever — gebruik bereikcheck
        if cheapest < 0:
            price_range  = most_expensive - cheapest
            cheap_cutoff = cheapest + price_range * Decimal("0.30")
            near_cheapest = price_excl <= cheap_cutoff
        else:
            near_cheapest = price_excl <= cheapest * self.charge_near_cheapest

        # Absolute fallback: always charge when price is below max threshold
        # Absolute terugval: altijd laden als prijs onder maximale drempel ligt
        near_cheapest_abs = price_excl <= self.max_price_to_charge_excl

        effective_cost = (price_excl / self.efficiency) + self.depreciation_per_kwh
        revenue_ok    = most_expensive >= effective_cost

        if spread_ok and (near_cheapest or near_cheapest_abs) and revenue_ok:
            dep = (
                f" + dep {self.depreciation_per_kwh:.4f} €/kWh"
                if self.depreciation_per_kwh > 0 else ""
            )
            return (
                True,
                f"Goedkope prijs {price_excl:.4f} €/kWh excl., "
                f"spread {most_expensive:.4f}/{cheapest:.4f}{dep} — laden vanaf net",
            )

        return False, ""

    # ── Meldingen bij negatieve prijs ────────────────────────────────────────

    def _build_negative_price_notification(
        self, export_price_excl: Decimal, surplus_kw: Decimal
    ) -> Optional[str]:
        """
        Build a user notification when the export price is very low or negative.
        Bouw een gebruikersmelding als de terugleverprijs erg laag of negatief is.

        Suggests actionable steps the user can take.
        Stelt concrete acties voor die de gebruiker kan ondernemen.
        """
        if export_price_excl <= self.negative_export_threshold:
            sign    = "negative" if export_price_excl < 0 else "zero"
            sign_nl = "negatief" if export_price_excl < 0 else "nul"
            return (
                f"⚡ Export price is {sign} ({export_price_excl:.4f} €/kWh excl.) — "
                f"⚡ Terugleverprijs is {sign_nl} ({export_price_excl:.4f} €/kWh excl.) — "
                f"gebruik nu stroom om te voorkomen dat u betaalt voor teruglevering! "
                f"Suggesties: zet boiler / wasmachine / vaatwasser / laadpaal aan. "
                f"Zonne-overschot: {surplus_kw:.2f} kW."
            )
        elif export_price_excl <= self.notify_export_threshold:
            return (
                f"⚠ Terugleverprijs zeer laag ({export_price_excl:.4f} €/kWh excl.) — "
                f"overweeg nu apparaten met hoog verbruik in te schakelen."
            )
        return None

    # ── Financiële berekening ─────────────────────────────────────────────────

    def calc_saving(
        self,
        action: str,
        power_kw: Decimal,
        price_excl: Decimal,
        is_solar_charge: bool = False,
    ) -> Decimal:
        """
        Calculate expected financial saving for this action.
        Bereken verwachte financiële besparing voor deze actie.

        For 'charge', this is only the future round-trip loss that is
        avoided compared to a worse alternative — it is NOT the cost of
        the electricity itself. See calc_cost() for that.

        Voor 'laden' is dit alleen het toekomstige rendementsverlies dat
        vermeden wordt t.o.v. een slechter alternatief — NIET de kosten
        van de elektriciteit zelf. Zie calc_cost() daarvoor.
        """
        if action == "discharge":
            energy_out = power_kw * self.efficiency
            saving = (energy_out * price_excl) - (self.depreciation_per_kwh * power_kw)
        elif action == "charge":
            if is_solar_charge:
                # Solar charging is free — no cost, so no "saving" framing needed.
                # Zonne-lading is gratis — geen kosten, dus geen "besparing" nodig.
                saving = Decimal("0")
            else:
                saving = max(
                    (power_kw * price_excl * (Decimal("1") - Decimal("1") / self.efficiency)
                     - self.depreciation_per_kwh * power_kw),
                    Decimal("0"),
                )
        else:
            saving = Decimal("0")

        return saving.quantize(Decimal("0.00001"), rounding=ROUND_HALF_UP)

    def calc_cost(
        self,
        action: str,
        power_kw: Decimal,
        price_excl: Decimal,
        is_solar_charge: bool = False,
    ) -> Decimal:
        """
        Calculate the actual cost incurred this hour for the given action.
        Bereken de werkelijke kosten voor deze actie dit uur.

        - 'charge' from grid: cost = power × price (money spent now, excl. VAT)
        - 'charge' from solar surplus: cost = 0 (already-produced free energy)
        - 'discharge' / 'idle' / 'self_consume': cost = 0 (no purchase this hour)

        - 'laden' vanaf net: kosten = vermogen × prijs (nu uitgegeven geld, excl. BTW)
        - 'laden' van zonne-overschot: kosten = 0 (al geproduceerde gratis energie)
        - 'ontladen' / 'rust' / 'zelf verbruik': kosten = 0 (geen aankoop dit uur)

        Note: this is cost EXCL. VAT, consistent with price_excl throughout
        the strategy. The GUI may add VAT for display if desired.

        Let op: dit zijn kosten EXCL. BTW, consistent met price_excl door de
        hele strategie. De GUI kan voor weergave BTW toevoegen indien gewenst.
        """
        if action == "charge" and not is_solar_charge:
            cost = power_kw * price_excl
        else:
            cost = Decimal("0")

        return cost.quantize(Decimal("0.00001"), rounding=ROUND_HALF_UP)

    # ── Hulpfunctie ──────────────────────────────────────────────────────────

    def _to_excl(self, price: Decimal) -> Decimal:
        """Zet prijs om naar excl. BTW indien nodig."""
        if self.price_incl_tax:
            return (price / self.vat_multiplier).quantize(
                Decimal("0.00001"), rounding=ROUND_HALF_UP
            )
        return price


# ── Database factory / Database-fabrieksfunctie ──────────────────────────────

def build_strategy_from_db(db) -> tuple["Strategy", "DayPriceStats | None", "SolarOutlook | None"]:
    """
    Build a fully configured Strategy from the database.
    Bouw een volledig geconfigureerde Strategy uit de database.
    """
    from datetime import date, timedelta
    from decimal import Decimal

    with db.cursor() as cur:
        cur.execute("SELECT * FROM system_config ORDER BY id DESC LIMIT 1")
        cfg = cur.fetchone() or {}

    with db.cursor() as cur:
        cur.execute("SELECT * FROM battery_info ORDER BY id DESC LIMIT 1")
        bat = cur.fetchone() or {}

    with db.cursor() as cur:
        cur.execute("""
            SELECT driver_config FROM provider_config
            WHERE energy_type = 'electricity' AND is_active = 1 LIMIT 1
        """)
        prov = cur.fetchone()

    vat_pct        = Decimal("21.0")
    price_incl_tax = bool(cfg.get("price_incl_tax", True))
    if prov and prov.get("driver_config"):
        import json as _json
    _drv_cfg = prov["driver_config"]
    if isinstance(_drv_cfg, str):
        try:
            _drv_cfg = _json.loads(_drv_cfg)
        except Exception:
            _drv_cfg = {}
    vat_pct = Decimal(str(_drv_cfg.get("vat_pct", 21.0)))

    # Depreciation per kWh / Afschrijving per kWh
    dep_per_kwh = Decimal("0")
    usable_kwh  = Decimal(str(bat.get("usable_capacity_kwh") or "10"))
    if bat.get("cost_eur") and bat.get("expected_cycles") and usable_kwh > 0:
        dep_per_kwh = (
            Decimal(str(bat["cost_eur"]))
            / Decimal(str(bat["expected_cycles"]))
            / usable_kwh
        ).quantize(Decimal("0.00001"), rounding=ROUND_HALF_UP)

    strategy = Strategy(
        battery_efficiency_pct        = Decimal(str(cfg.get("battery_efficiency_pct") or "75")),
        min_soc_pct                   = Decimal(str(bat.get("min_soc_pct") or "10")),
        max_soc_pct                   = Decimal(str(bat.get("max_soc_pct") or "95")),
        max_charge_kw                 = Decimal(str(bat.get("max_charge_kw") or "3.68")),
        max_discharge_kw              = Decimal(str(bat.get("max_discharge_kw") or "3.68")),
        working_charge_kw             = Decimal(str(bat.get("working_charge_kw") or "2.5")),
        working_discharge_kw          = Decimal(str(bat.get("working_discharge_kw") or "2.5")),
        temp_derating_threshold_c     = Decimal(str(cfg.get("temp_derating_threshold_c") or "35")),
        temp_derating_factor          = Decimal(str(cfg.get("temp_derating_factor") or "0.7")),
        hard_min_discharge_price_excl = Decimal(str(cfg.get("hard_min_discharge_price_excl") or "0.05")),
        min_spread_ratio_for_discharge= Decimal(str(cfg.get("min_spread_ratio_for_discharge") or "1.5")),
        discharge_near_peak_fraction  = Decimal(str(cfg.get("discharge_near_peak_fraction") or "0.75")),
        extreme_price_multiplier      = Decimal(str(cfg.get("extreme_price_multiplier") or "2.5")),
        negative_export_threshold_excl= Decimal(str(cfg.get("negative_export_threshold_excl") or "0.00")),
        notify_export_threshold_excl  = Decimal(str(cfg.get("notify_export_threshold_excl") or "0.02")),
        charge_near_cheapest_fraction = Decimal(str(cfg.get("charge_near_cheapest_fraction") or "1.15")),
        min_sunshine_pct_for_refill   = Decimal(str(cfg.get("min_sunshine_pct_for_refill") or "40")),
        avg_consumption_kwh           = Decimal(str(cfg.get("avg_consumption_kwh") or "1.0")),
        sunrise_buffer_pct            = Decimal(str(cfg.get("sunrise_buffer_pct") or "10")),
        price_incl_tax                = price_incl_tax,
        vat_pct                       = vat_pct,
        depreciation_per_kwh          = dep_per_kwh,
        solar_charge_threshold        = Decimal(str(cfg.get("solar_charge_threshold") or "0.80")),
        max_price_to_charge_excl      = (
            Decimal(str(cfg.get("max_price_to_charge") or "0.10"))
            / (Decimal("1") + Decimal(str(cfg.get("vat_pct") or "0")) / 100)
            if cfg.get("price_incl_tax") else
            Decimal(str(cfg.get("max_price_to_charge") or "0.10"))
        ),
        usable_capacity_kwh           = usable_kwh,
    )

    day_stats     = _build_day_stats(db, price_incl_tax, vat_pct)
    solar_outlook = _build_solar_outlook(db)

    return strategy, day_stats, solar_outlook


def _build_day_stats(
    db, price_incl_tax: bool, vat_pct: Decimal
) -> "DayPriceStats | None":
    """
    Load today's price statistics from the database.
    Laad de prijsstatistieken van vandaag uit de database.
    """
    with db.cursor() as cur:
        cur.execute("""
            SELECT price_hour, price_per_kwh
            FROM energy_prices
            WHERE DATE(price_hour) = CURDATE()
              AND energy_type = 'electricity'
            ORDER BY price_hour
        """)
        rows = cur.fetchall()

    if not rows:
        logger.warning("Geen prijsdata voor vandaag")
        return None

    vm    = Decimal("1") + vat_pct / 100
    excl  = lambda p: (Decimal(str(p)) / vm) if price_incl_tax else Decimal(str(p))
    hours = [(row["price_hour"], excl(row["price_per_kwh"])) for row in rows]
    prices = [p for _, p in hours]

    return DayPriceStats(
        cheapest_today       = min(prices),
        most_expensive_today = max(prices),
        average_today        = sum(prices) / len(prices),
        hours_ranked         = sorted(hours, key=lambda x: x[1]),
        price_incl_tax       = price_incl_tax,
        vat_multiplier       = vm,
    )


def _build_solar_outlook(db) -> "SolarOutlook | None":
    """
    Build tomorrow's solar outlook from weather forecast data.
    Bouw de zonnerverwachting van morgen op basis van weersvoorspellingsdata.
    """
    from datetime import date, timedelta
    tomorrow = date.today() + timedelta(days=1)

    with db.cursor() as cur:
        cur.execute("""
            SELECT
                AVG(sunshine_pct)         AS avg_sunshine,
                SUM(solar_irradiance_wm2) AS total_irradiance
            FROM weather_forecast
            WHERE DATE(forecast_for) = %(tomorrow)s
        """, {"tomorrow": tomorrow})
        row = cur.fetchone()

    if not row or row.get("avg_sunshine") is None:
        return None

    sunshine_pct = Decimal(str(row["avg_sunshine"] or 0))
    cloud_pct    = Decimal("100") - sunshine_pct

    # Probeer zonprofiel voor betere schatting
    from datetime import date as _date
    next_month = (tomorrow.replace(day=1) + __import__('datetime').timedelta(days=32)).month
    profile_month = tomorrow.month

    with db.cursor() as cur2:
        cur2.execute("""
            SELECT COALESCE(SUM(avg_kw), 0) AS profile_kwh
            FROM solar_profile
            WHERE month = %(month)s
        """, {"month": profile_month})
        profile_row = cur2.fetchone()

    profile_kwh = Decimal(str(profile_row["profile_kwh"] or 0)) if profile_row else Decimal("0")

    if profile_kwh > 0:
        # Apply cloud correction with minimum 15% for diffuse light
        cloud_factor = max(
            Decimal("0.15"),
            Decimal("1") - cloud_pct / Decimal("100")
        )
        estimated_kwh = profile_kwh * cloud_factor
    else:
        # Fallback to irradiance / Terugval op straling
        irradiance    = Decimal(str(row["total_irradiance"] or 0))
        estimated_kwh = irradiance * Decimal("0.0008")

    return SolarOutlook(
        sunshine_pct=sunshine_pct,
        estimated_yield_kwh=estimated_kwh,
    )

