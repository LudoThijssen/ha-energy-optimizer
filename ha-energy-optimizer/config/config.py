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


@dataclass
class ReportingConfig:
    daily_report_time: str  = "07:00"
    notify_on_warning: bool = True
    notify_on_error: bool   = True


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
        if self.optimizer.run_time <= self.collectors.price_fetch_time_tomorrow:
            raise ValueError(
                f"optimizer.run_time ({self.optimizer.run_time}) moet later zijn dan "
                f"collectors.price_fetch_time_tomorrow "
                f"({self.collectors.price_fetch_time_tomorrow})"
            )
