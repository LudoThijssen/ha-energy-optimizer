# name:          models.py
# part of:       ha-energy-optimizer
# location:      /ha-energy-optimizer/ha-energy-optimizer/optimizer/models.py
# part version:  p_v0.4
# altered:       2026-07-01

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
    """Beslissing van de optimizer voor één uur."""
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
