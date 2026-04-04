import requests
from datetime import datetime
from decimal import Decimal
from .base import BaseCollector, CollectorTemporaryError
from database.connection import DatabaseConnection
from database.repository import WeatherRepository
from database.models import WeatherForecast
from config.config import AppConfig

_VARIABLES = ",".join([
    "sunshine_duration",
    "cloud_cover",
    "precipitation",
    "wind_speed_10m",
    "wind_direction_10m",
    "temperature_2m",
    "direct_normal_irradiance",
    "diffuse_radiation",
])


class WeatherCollector(BaseCollector):
    name = "weather_collector"

    def __init__(self, db: DatabaseConnection, reporter, config: AppConfig):
        super().__init__(reporter)
        self._repo = WeatherRepository(db)
        self._lat = config.location.latitude
        self._lon = config.location.longitude
        self._tz = config.location.timezone

    def collect(self) -> None:
        raw = self._fetch_forecast()
        for forecast in self._parse(raw):
            self._repo.save(forecast)

    def _fetch_forecast(self) -> dict:
        try:
            response = requests.get(
                "https://api.open-meteo.com/v1/forecast",
                params={
                    "latitude":     self._lat,
                    "longitude":    self._lon,
                    "hourly":       _VARIABLES,
                    "forecast_days": 2,
                    "timezone":     self._tz,
                },
                timeout=10,
            )
            response.raise_for_status()
            return response.json()
        except requests.Timeout:
            raise CollectorTemporaryError("Open-Meteo timeout")
        except requests.ConnectionError:
            raise CollectorTemporaryError("Open-Meteo niet bereikbaar")

    def _parse(self, raw: dict) -> list[WeatherForecast]:
        hourly = raw.get("hourly", {})
        times = hourly.get("time", [])
        dni = hourly.get("direct_normal_irradiance", [None] * len(times))
        dhi = hourly.get("diffuse_radiation", [None] * len(times))
        forecasts = []

        for i, time_str in enumerate(times):
            def val(key, idx=i):
                v = hourly.get(key, [None] * len(times))[idx]
                return Decimal(str(v)) if v is not None else None

            irradiance = None
            if dni[i] is not None and dhi[i] is not None:
                irradiance = Decimal(str(dni[i])) + Decimal(str(dhi[i]))

            sunshine_pct = None
            sunshine_s = hourly.get("sunshine_duration", [None] * len(times))[i]
            if sunshine_s is not None:
                sunshine_pct = Decimal(str(min(sunshine_s / 36, 100)))

            wd = hourly.get("wind_direction_10m", [None] * len(times))[i]

            forecasts.append(WeatherForecast(
                forecast_for=datetime.fromisoformat(time_str),
                sunshine_pct=sunshine_pct,
                cloud_cover_pct=val("cloud_cover"),
                solar_irradiance_wm2=irradiance,
                temperature_c=val("temperature_2m"),
                rain_mm=val("precipitation"),
                wind_speed_ms=val("wind_speed_10m"),
                wind_direction_deg=int(wd) if wd is not None else None,
                source="open-meteo",
            ))

        return forecasts
