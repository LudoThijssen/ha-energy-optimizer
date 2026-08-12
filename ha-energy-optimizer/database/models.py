#
# name:          models.py
# part of:       ha-energy-optimizer
# location:      /ha-energy-optimizer/ha-energy-optimizer/database/models.py
# part version:  p_v0.7
# altered:       2026-08-11
#
# p_v0.7: grid_consume_kw toegevoegd aan OptimizerSlot — zie migratie 021
# en optimizer/models.py p_v0.8 (ScheduleSlot). Zonder dit veld crasht
# repository.py::get_current_slot() (OptimizerSlot(**row)) zodra een rij
# de nieuwe kolom bevat — precies hetzelfde patroon als is_solar_charge/
# grid_charge_kw hieronder (p_v0.5).
# p_v0.7: grid_consume_kw added to OptimizerSlot — see migration 021 and
# optimizer/models.py p_v0.8 (ScheduleSlot). Without this field,
# repository.py::get_current_slot() (OptimizerSlot(**row)) crashes as
# soon as a row contains the new column — exact same pattern as
# is_solar_charge/grid_charge_kw below (p_v0.5).
#
# p_v0.5: is_solar_charge / grid_charge_kw toegevoegd aan OptimizerSlot —
# zie migratie 016 en optimizer/models.py p_v0.5 (ScheduleSlot).
# p_v0.5: is_solar_charge / grid_charge_kw added to OptimizerSlot — see
# migration 016 and optimizer/models.py p_v0.5 (ScheduleSlot).
#
# p_v0.6: price_sell_per_kwh toegevoegd aan EnergyPrice — start van de
# in/verkoopprijs-splitsing (zie migratie 018). __post_init__ dupliceert
# automatisch price_per_kwh naar price_sell_per_kwh als een provider die
# niet expliciet meegeeft — bestaande providers (tibber.py, energyzero.py,
# etc.) hoeven dus NIET aangepast te worden om te blijven werken. Zodra een
# provider wél een eigen verkoopprijs kan leveren, geeft die 'm gewoon mee
# aan de constructor en overschrijft dat de duplicatie.
#
# p_v0.6: price_sell_per_kwh added to EnergyPrice — start of the buy/sell
# price split (see migration 018). __post_init__ automatically duplicates
# price_per_kwh into price_sell_per_kwh for any provider that doesn't pass
# it explicitly — existing providers (tibber.py, energyzero.py, etc.) do
# NOT need to be changed to keep working. Once a provider can supply its
# own sell price, it simply passes it to the constructor and that
# overrides the duplication.

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
    # p_v0.6: verkoopprijs (teruglevering) — None laten om automatisch te
    # dupliceren van price_per_kwh, of expliciet meegeven zodra een
    # provider een eigen verkoopprijs levert.
    # p_v0.6: sell (feed-in) price — leave None to auto-duplicate from
    # price_per_kwh, or pass explicitly once a provider supplies its own
    # sell price.
    price_sell_per_kwh: Decimal | None = None
    id: int | None = None

    def __post_init__(self):
        if self.price_sell_per_kwh is None:
            self.price_sell_per_kwh = self.price_per_kwh


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
    # p_v0.7: netverbruik tijdens rust dat de batterij niet meer kon
    # leveren (SoC-vloer bereikt) — zie migratie 021.
    # p_v0.7: grid consumption during idle the battery could no longer
    # supply (SoC floor reached) — see migration 021.
    grid_consume_kw: Decimal | None = None
    id: int | None = None


@dataclass
class ReportEntry:
    report_type: str
    message: str
    category: str | None = None
    notified: bool = False
    notified_at: datetime | None = None
    id: int | None = None
