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
