# name:          models.py
# part of:       ha-energy-optimizer
# location:      /ha-energy-optimizer/ha-energy-optimizer/optimizer/models.py
# part version:  p_v0.8
# altered:       2026-08-11
#
# p_v0.8: grid_consume_kw toegevoegd aan ScheduleSlot — zie migratie 021
# en decision_engine.py p_v0.13. Zelfde patroon als grid_charge_kw
# (p_v0.5 hieronder): zonder dit veld zou het netverbruik dat
# decision_engine.py nu berekent (huisverbruik dat de batterij niet meer
# kan leveren omdat de SoC-vloer bereikt is) verloren gaan zodra het naar
# een ScheduleSlot wordt omgezet.
#
# p_v0.8: grid_consume_kw added to ScheduleSlot — see migration 021 and
# decision_engine.py p_v0.13. Same pattern as grid_charge_kw (p_v0.5
# below): without this field, the grid consumption that decision_engine.py
# now calculates (household consumption the battery can no longer supply
# because the SoC floor is reached) would be lost as soon as it gets
# converted to a ScheduleSlot.
#
# p_v0.7: HourForecast -> ForecastSlot, WindowHour -> WindowSlot (in
# decision_engine.py), en het veld `hour` -> `slot_start` op ForecastSlot
# en ScheduleSlot. Puur een naamswijziging — geen functionele verandering.
# Deze namen dateerden nog van vóór de kwartier-migratie en suggereerden
# dat de voorspelling nog per heel uur werkt, wat sinds p_v0.8 (engine.py)
# niet meer klopt: het zijn allang kwartier-slots. `slot_start` sluit aan
# bij de bestaande config.timeslot.slot_start() functie.
#
# p_v0.7: HourForecast -> ForecastSlot, WindowHour -> WindowSlot (in
# decision_engine.py), and the field `hour` -> `slot_start` on ForecastSlot
# and ScheduleSlot. Purely a naming change — no functional change. These
# names dated from before the quarter-hour migration and suggested the
# forecast still works per whole hour, which hasn't been true since p_v0.8
# (engine.py): they've been quarter slots for a while. `slot_start`
# matches the existing config.timeslot.slot_start() function.
#
# p_v0.6: price_sell_per_kwh toegevoegd aan HourForecast — start van het
# daadwerkelijk gebruiken van de in/verkoopprijs-splitsing (zie migratie
# 018, database/models.py p_v0.6). __post_init__ dupliceert automatisch
# vanuit price_per_kwh als engine.py het niet expliciet meegeeft.
#
# p_v0.6: price_sell_per_kwh added to HourForecast — start of actually
# using the buy/sell price split (see migration 018, database/models.py
# p_v0.6). __post_init__ automatically duplicates from price_per_kwh if
# engine.py doesn't pass it explicitly.
#
# p_v0.5: is_solar_charge / grid_charge_kw toegevoegd aan ScheduleSlot —
# zie migratie 016. Zonder dit veld ging de zon/net-opsplitsing die
# decision_engine.py al berekent verloren zodra het naar een ScheduleSlot
# werd omgezet, waardoor de GUI "laden van het net" nooit apart kon tonen.
#
# p_v0.5: is_solar_charge / grid_charge_kw added to ScheduleSlot — see
# migration 016. Without this field, the solar/grid split that
# decision_engine.py already calculates was lost as soon as it got
# converted to a ScheduleSlot, so the GUI could never show "charging from
# the grid" separately.

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal


@dataclass
class ForecastSlot:
    """Gecombineerde voorspelling voor één kwartier-slot — input voor de optimizer."""
    slot_start: datetime
    price_per_kwh: Decimal
    solar_kw: Decimal
    consumption_kw: Decimal
    soc_pct: Decimal
    # p_v0.6: verkoopprijs (teruglevering) — None laten om automatisch te
    # dupliceren van price_per_kwh.
    # p_v0.6: sell (feed-in) price — leave None to auto-duplicate from
    # price_per_kwh.
    price_sell_per_kwh: Decimal | None = None

    def __post_init__(self):
        if self.price_sell_per_kwh is None:
            self.price_sell_per_kwh = self.price_per_kwh


@dataclass
class ScheduleSlot:
    """Beslissing van de optimizer voor één slot."""
    slot_start: datetime
    action: str               # 'charge', 'discharge', 'idle', 'self_consume'
    target_power_kw: Decimal
    target_soc_pct: Decimal
    expected_saving: Decimal
    reason: str
    expected_cost: Decimal           = Decimal("0")
    expected_solar_kw: Decimal       = Decimal("0")
    expected_consumption_kw: Decimal = Decimal("0")
    expected_price: Decimal          = Decimal("0")
    reason_key:     str              = ""
    reason_params:  dict             = None
    # p_v0.5: zon/net-opsplitsing bij een laadactie / solar/grid split for a charge action
    is_solar_charge: bool  = False
    grid_charge_kw:  Decimal = Decimal("0")
    # p_v0.8: netverbruik tijdens rust dat de batterij niet meer kon
    # leveren (SoC-vloer bereikt) — zie migratie 021.
    # p_v0.8: grid consumption during idle that the battery could no
    # longer supply (SoC floor reached) — see migration 021.
    grid_consume_kw: Decimal = Decimal("0")

