import requests
from datetime import datetime
from decimal import Decimal
from .base import BaseCollector, CollectorTemporaryError, CollectorConfigError, validate_reading
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
        """
        Fetch all mapped sensors, validate each reading, and apply fallback
        to the last known value when a reading is missing or out of bounds.

        Lees alle gekoppelde sensoren, valideer elke waarde, en gebruik de
        laatste bekende waarde als fallback bij ontbrekende of ongeldige data.
        """
        import logging
        log = logging.getLogger(__name__)
        readings: dict[str, Decimal | None] = {}

        for internal_name, entity_id in entity_map.items():
            raw = self._fetch_entity(entity_id)
            validated = validate_reading(internal_name, raw, log)

            if validated is None and raw is not None:
                # Value was out of bounds — already logged by validate_reading
                # Waarde buiten bereik — al gelogd door validate_reading
                readings[internal_name] = self._get_last_known(internal_name)

            elif validated is None:
                # Sensor unavailable — try fallback
                # Sensor niet beschikbaar — probeer fallback
                fallback = self._get_last_known(internal_name)
                if fallback is not None:
                    log.info(
                        f"[ha_collector] {internal_name} unavailable — "
                        f"using last known value {fallback} / "
                        f"niet beschikbaar — laatste bekende waarde {fallback} gebruikt"
                    )
                readings[internal_name] = fallback

            else:
                readings[internal_name] = validated

        # Derive battery_power from charge/discharge if not directly available
        # battery_power berekenen uit laden/ontladen als niet direct beschikbaar
        if readings.get("battery_power") is None:
            charge    = readings.get("battery_charge_kw")
            discharge = readings.get("battery_discharge_kw")
            if charge is not None and discharge is not None:
                # Positive = charging, negative = discharging
                # Positief = laden, negatief = ontladen
                readings["battery_power"] = charge - discharge
                import logging as _log
                _log.getLogger(__name__).debug(
                    f"[ha_collector] battery_power derived: "
                    f"charge {charge} - discharge {discharge} = {readings['battery_power']}"
                )

        return readings

    def _get_last_known(self, internal_name: str) -> "Decimal | None":
        """
        Retrieve the most recent stored value for a sensor from the database.
        Used as fallback when live reading is unavailable or invalid.

        Haal de meest recente opgeslagen waarde op voor een sensor uit de database.
        Gebruikt als fallback als de live waarde niet beschikbaar of ongeldig is.
        """
        column_map = {
            "solar_power":             ("solar_production",  "power_kw"),
            "solar_energy_total":      ("solar_production",  "energy_kwh"),
            "grid_import_power":       ("home_consumption",  "grid_import_kw"),
            "grid_export_power":       ("home_consumption",  "grid_export_kw"),
            "total_consumption_power": ("home_consumption",  "total_consumption_kw"),
            "battery_soc":             ("battery_status",    "soc_pct"),
            "battery_power":           ("battery_status",    "power_kw"),
            "battery_temperature":     ("battery_status",    "temperature_c"),
            "battery_voltage":         ("battery_status",    "voltage_v"),
        }
        mapping = column_map.get(internal_name)
        if not mapping:
            return None

        table, column = mapping
        try:
            with self._db.cursor() as cur:
                cur.execute(
                    f"SELECT {column} AS val FROM {table} "
                    f"ORDER BY measured_at DESC LIMIT 1"
                )
                row = cur.fetchone()
                if row and row["val"] is not None:
                    return Decimal(str(row["val"]))
        except Exception as e:
            import logging
            logging.getLogger(__name__).debug(
                f"[ha_collector] Fallback lookup failed for {internal_name}: {e}"
            )
        return None

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

        # Convert solar energy total from Wh to kWh if available
        # Omzetten zonne-energieteller van Wh naar kWh indien beschikbaar
        energy_wh = readings.get("solar_energy_total")
        energy_kwh = None
        if energy_wh is not None:
            energy_kwh = energy_wh / Decimal("1000")

        self._solar_repo.save(SolarProduction(
            measured_at=datetime.now(),
            power_kw=power,
            energy_kwh=energy_kwh,
        ))

    def _store_consumption(self, readings: dict) -> None:
        grid_import = readings.get("grid_import_power")
        grid_export = readings.get("grid_export_power")
        total       = readings.get("total_consumption_power")
        solar       = readings.get("solar_power")
        gas         = readings.get("gas_consumption")
        bat_charge  = readings.get("battery_charge_kw")
        bat_disch   = readings.get("battery_discharge_kw")

        if all(v is None for v in [grid_import, grid_export, total, gas]):
            return

        # Calculate actual household consumption from the full energy balance:
        # consumption = solar + battery_discharge - battery_charge
        #               - grid_export + grid_import
        #
        # This is preferred over an inverter-reported "load power" value,
        # which is itself a calculated estimate and can show small negative
        # readings due to measurement timing between separate CT sensors
        # (PV micro-inverters feed the grid directly and are not visible
        # to the main inverter).
        #
        # Bereken werkelijk huishoudverbruik uit de volledige energiebalans:
        # verbruik = zon + batterij_ontladen - batterij_laden
        #            - net_export + net_import
        #
        # Dit heeft de voorkeur boven een door de inverter gerapporteerde
        # "load power" waarde, die zelf een schatting is en licht negatief
        # kan uitvallen door timingverschillen tussen losse CT-sensoren
        # (PV-micro-omvormers leveren direct aan het net, onzichtbaar voor
        # de hoofdinverter).
        if grid_import is not None and grid_export is not None:
            from decimal import Decimal
            calculated = (
                Decimal(str(solar or 0))
                + Decimal(str(bat_disch or 0))
                - Decimal(str(bat_charge or 0))
                - Decimal(str(grid_export))
                + Decimal(str(grid_import))
            )
            # Clamp small negative results to 0 — consumption can't be
            # negative; tiny negatives come from sensor timing differences.
            # Clamp kleine negatieve resultaten naar 0 — verbruik kan niet
            # negatief zijn; kleine negatieve waarden komen door sensortiming.
            if Decimal("-0.5") <= calculated < 0:
                calculated = Decimal("0")
            total = calculated
        elif total is None and grid_import is not None:
            # Fallback if battery sensors not available
            # Terugval als batterijsensoren niet beschikbaar zijn
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


