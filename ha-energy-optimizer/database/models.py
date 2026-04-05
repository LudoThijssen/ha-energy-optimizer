from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal


@dataclass
class EnergyPrice:
    price_hour: datetime
    energy_type: str
    price_per_kwh: Decimal
    price_incl_tax: bool
    source: str
    id: int | None = None


@dataclass
class BatteryStatus:
    measured_at: datetime
    soc_pct: Decimal
    power_kw: Decimal
    voltage_v: Decimal | None = None
    temperature_c: Decimal | None = None
    energy_charged_kwh: Decimal | None = None
    energy_discharged_kwh: Decimal | None = None
    cycle_count: int | None = None
    id: int | None = None


@dataclass
class SolarProduction:
    measured_at: datetime
    power_kw: Decimal
    energy_kwh: Decimal | None = None
    id: int | None = None


@dataclass
class HomeConsumption:
    measured_at: datetime
    grid_import_kw: Decimal | None = None
    grid_export_kw: Decimal | None = None
    total_consumption_kw: Decimal | None = None
    gas_m3: Decimal | None = None
    id: int | None = None


@dataclass
class WeatherForecast:
    forecast_for: datetime
    sunshine_pct: Decimal | None = None
    cloud_cover_pct: Decimal | None = None
    solar_irradiance_wm2: Decimal | None = None
    temperature_c: Decimal | None = None
    rain_mm: Decimal | None = None
    wind_speed_ms: Decimal | None = None
    wind_direction_deg: int | None = None
    sun_rise: str | None = None
    sun_set: str | None = None
    source: str | None = None
    id: int | None = None


@dataclass
class OptimizerSlot:
    schedule_for: datetime
    action: str
    target_power_kw: Decimal | None = None
    target_soc_pct: Decimal | None = None
    expected_price: Decimal | None = None
    expected_solar_kw: Decimal | None = None
    expected_consumption_kw: Decimal | None = None
    expected_saving: Decimal | None = None
    reason: str | None = None
    executed: bool = False
    executed_at: datetime | None = None
    id: int | None = None


@dataclass
class ReportEntry:
    report_type: str
    message: str
    category: str | None = None
    notified: bool = False
    notified_at: datetime | None = None
    id: int | None = None
