#
# name:          models.py
# part of:       ha-energy-optimizer
# location:      /ha-energy-optimizer/ha-energy-optimizer/database/models.py
# part version:  p_v0.5
# altered:       2026-07-24
#
# p_v0.5: is_solar_charge / grid_charge_kw toegevoegd aan OptimizerSlot —
# zie migratie 016 en optimizer/models.py p_v0.5 (ScheduleSlot). Maakt het
# mogelijk om in de GUI "laden van het net" te tonen los van "laden vanuit
# zon-overschot" binnen dezelfde laadactie.
#
# p_v0.5: is_solar_charge / grid_charge_kw added to OptimizerSlot — see
# migration 016 and optimizer/models.py p_v0.5 (ScheduleSlot). Enables the
# GUI to show "charging from the grid" separately from "charging from solar
# surplus" within the same charge action.

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
    expected_cost: Decimal | None = None
    reason: str | None = None
    reason_key: str | None = None
    reason_params: dict | None = None
    executed: bool = False
    executed_at: datetime | None = None
    # p_v0.5: zon/net-opsplitsing bij een laadactie / solar/grid split for a charge action
    is_solar_charge: bool = False
    grid_charge_kw: Decimal | None = None
    id: int | None = None


@dataclass
class ReportEntry:
    report_type: str
    message: str
    category: str | None = None
    notified: bool = False
    notified_at: datetime | None = None
    id: int | None = None
