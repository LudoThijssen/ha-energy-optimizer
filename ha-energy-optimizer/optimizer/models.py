# name:          models.py
# part of:       ha-energy-optimizer
# location:      /ha-energy-optimizer/ha-energy-optimizer/optimizer/models.py
# part version:  p_v0.5
# altered:       2026-07-24
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
class HourForecast:
    """Gecombineerde voorspelling voor één uur — input voor de optimizer."""
    hour: datetime
    price_per_kwh: Decimal
    solar_kw: Decimal
    consumption_kw: Decimal
    soc_pct: Decimal


@dataclass
class ScheduleSlot:
    """Beslissing van de optimizer voor één slot."""
    hour: datetime
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

