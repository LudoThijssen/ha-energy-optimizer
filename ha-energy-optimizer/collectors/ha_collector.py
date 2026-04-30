import requests
from datetime import datetime
from decimal import Decimal
from .base import BaseCollector, CollectorTemporaryError, CollectorConfigError
from database.connection import DatabaseConnection
from database.models import HomeConsumption, BatteryStatus, SolarProduction
from database.repository import BatteryRepository, SolarRepository, HomeConsumptionRepository
from config.config import AppConfig


class HaCollector(BaseCollector):
    name = "ha_collector"

    def __init__(self, db: DatabaseConnection, reporter, config: AppConfig):
        super().__init__(reporter)
        self._db = db
        self._config = config
        self._battery_repo = BatteryRepository(db)
        self._solar_repo = SolarRepository(db)
        self._consumption_repo = HomeConsumptionRepository(db)
        self._base_url = f"http://{config.ha.host}:{config.ha.port}"
        self._headers = {
            "Authorization": f"Bearer {config.ha.token}",
            "Content-Type": "application/json",
        }

    def collect(self) -> None:
        entity_map = self._load_entity_map()
        readings = self._fetch_all(entity_map)
        self._store_battery(readings)
        self._store_solar(readings)
        self._store_consumption(readings)

    def _load_entity_map(self) -> dict[str, str]:
        with self._db.cursor() as cur:
            cur.execute("SELECT internal_name, entity_id FROM ha_entity_map")
            return {row["internal_name"]: row["entity_id"] for row in cur.fetchall()}

    def _fetch_all(self, entity_map: dict[str, str]) -> dict[str, Decimal | None]:
        readings: dict[str, Decimal | None] = {}
        for internal_name, entity_id in entity_map.items():
            readings[internal_name] = self._fetch_entity(entity_id)
        return readings

    def _fetch_entity(self, entity_id: str) -> Decimal | None:
        url = f"{self._base_url}/api/states/{entity_id}"
        try:
            response = requests.get(url, headers=self._headers, timeout=5)
            response.raise_for_status()
            state = response.json().get("state")
            if state in (None, "unavailable", "unknown"):
                return None
            return Decimal(str(state))
        except requests.Timeout:
            raise CollectorTemporaryError(f"Timeout bij ophalen {entity_id}")
        except requests.ConnectionError:
            raise CollectorTemporaryError(f"HA niet bereikbaar ({self._base_url})")
        except requests.HTTPError as e:
            if e.response.status_code == 401:
                raise CollectorConfigError("HA token ongeldig — controleer de instellingen")
            raise CollectorTemporaryError(f"HTTP fout bij {entity_id}: {e}")
        except (ValueError, TypeError):
            return None

    def _store_battery(self, readings: dict) -> None:
        soc = readings.get("battery_soc")
        power = readings.get("battery_power")
        if soc is None and power is None:
            return
        self._battery_repo.save(BatteryStatus(
            measured_at=datetime.now(),
            soc_pct=soc,
            power_kw=power,
            temperature_c=readings.get("battery_temperature"),
            voltage_v=readings.get("battery_voltage"),
        ))

    def _store_solar(self, readings: dict) -> None:
        power = readings.get("solar_power")
        if power is None:
            return
        self._solar_repo.save(SolarProduction(
            measured_at=datetime.now(),
            power_kw=power,
        ))

    def _store_consumption(self, readings: dict) -> None:
        grid_import = readings.get("grid_import_power")
        grid_export = readings.get("grid_export_power")
        total = readings.get("total_consumption_power")
        solar = readings.get("solar_power")
        gas = readings.get("gas_consumption")

        if all(v is None for v in [grid_import, grid_export, total, gas]):
            return

        # Calculate total consumption if not directly measured
        # Bereken totaal verbruik als het niet direct gemeten wordt
        if total is None and grid_import is not None:
            from decimal import Decimal
            total = (
                Decimal(str(grid_import))
                - Decimal(str(grid_export or 0))
                + Decimal(str(solar or 0))
            )

        self._consumption_repo.save(HomeConsumption(
            measured_at=datetime.now(),
            grid_import_kw=grid_import,
            grid_export_kw=grid_export,
            total_consumption_kw=total,
            gas_m3=gas,
        ))
