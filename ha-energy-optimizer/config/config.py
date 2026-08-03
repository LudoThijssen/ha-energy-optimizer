# name:          config.py
# part of:       ha-energy-optimizer
# location:      /ha-energy-optimizer/ha-energy-optimizer/config/config.py
# part version:  p_v0.4
# altered:       2026-07-25
#
# p_v0.4: rerun_interval_seconds toegevoegd aan OptimizerConfig (default 900
# = 15 min). Was voorheen hardcoded als 3600 in main.py; nu instelbaar en
# consistent met de kwartier-tijdstap (config.timeslot.SLOT_MINUTES).
# p_v0.4: rerun_interval_seconds added to OptimizerConfig (default 900 =
# 15 min). Was previously hardcoded as 3600 in main.py; now configurable
# and consistent with the quarter-hour schedule step
# (config.timeslot.SLOT_MINUTES).

import json
from pathlib import Path
from dataclasses import dataclass
from .validators import validate_time, validate_positive_int

OPTIONS_PATH = Path("/data/options.json")


@dataclass
class DatabaseConfig:
    host: str
    port: int
    name: str
    user: str
    password: str


@dataclass
class HaConfig:
    host: str
    port: int
    token: str


@dataclass
class CollectorConfig:
    ha_interval_seconds: int       = 300
    weather_interval_seconds: int  = 3600
    price_fetch_time_today: str    = "13:00"
    price_fetch_time_tomorrow: str = "14:15"
    price_fetch_max_retries: int   = 3
    price_fetch_retry_minutes: int = 30


@dataclass
class OptimizerConfig:
    run_time: str              = "14:30"
    evening_planning_time: str = "21:00"
    rerun_on_price_update: bool = True
    profile_update_time: str    = "03:00"
    # p_v0.4: hoe vaak de rolling-horizon optimizer herrekent, los van de
    # dagelijkse run_time. Default 900s = 15 min, gelijk aan de schema-
    # tijdstap (SLOT_MINUTES in config/timeslot.py).
    # p_v0.4: how often the rolling-horizon optimizer recalculates,
    # separate from the daily run_time. Default 900s = 15 min, matching the
    # schedule time step (SLOT_MINUTES in config/timeslot.py).
    rerun_interval_seconds: int = 900


@dataclass
class ReportingConfig:
    daily_report_time: str  = "07:00"
    notify_on_warning: bool = True
    notify_on_error: bool   = True
    dashboard_refresh_seconds: int = 300


@dataclass
class LocationConfig:
    latitude: float  = 52.1551
    longitude: float = 5.3872
    timezone: str    = "Europe/Amsterdam"


@dataclass
class AppConfig:
    database: DatabaseConfig
    ha: HaConfig
    collectors: CollectorConfig
    optimizer: OptimizerConfig
    reporting: ReportingConfig
    location: LocationConfig
    language: str = "nl"

    @classmethod
    def load(cls) -> "AppConfig":
        with open(OPTIONS_PATH) as f:
            raw = json.load(f)
        config = cls(
            database=DatabaseConfig(**raw["database"]),
            ha=HaConfig(**raw["homeassistant"]),
            collectors=CollectorConfig(**raw.get("collectors", {})),
            optimizer=OptimizerConfig(**raw.get("optimizer", {})),
            reporting=ReportingConfig(**raw.get("reporting", {})),
            location=LocationConfig(**raw.get("location", {})),
            language=raw.get("language", "nl"),
        )
        config.validate()
        return config

    def validate(self) -> None:
        validate_time(self.collectors.price_fetch_time_today,
                      "collectors.price_fetch_time_today")
        validate_time(self.collectors.price_fetch_time_tomorrow,
                      "collectors.price_fetch_time_tomorrow")
        validate_time(self.optimizer.run_time,
                      "optimizer.run_time")
        validate_time(self.reporting.daily_report_time,
                      "reporting.daily_report_time")
        validate_positive_int(self.collectors.ha_interval_seconds,
                              "collectors.ha_interval_seconds")
        validate_positive_int(self.collectors.weather_interval_seconds,
                              "collectors.weather_interval_seconds")
        validate_positive_int(self.optimizer.rerun_interval_seconds,
                              "optimizer.rerun_interval_seconds")
        if self.optimizer.run_time <= self.collectors.price_fetch_time_tomorrow:
            raise ValueError(
                f"optimizer.run_time ({self.optimizer.run_time}) moet later zijn dan "
                f"collectors.price_fetch_time_tomorrow "
                f"({self.collectors.price_fetch_time_tomorrow})"
            )
