import time
from abc import ABC, abstractmethod
from datetime import datetime
from decimal import Decimal
import logging

logger = logging.getLogger(__name__)


class CollectorTemporaryError(Exception):
    """Tijdelijke fout — netwerk, timeout, API onbereikbaar."""
    pass


class CollectorConfigError(Exception):
    """Configuratiefout — ontbrekende sleutel, ongeldige instelling."""
    pass


# Sensor validation bounds per internal name.
# Validatiebereiken per interne sensornaam.
# Format: internal_name -> (min_value, max_value, allow_negative)
SENSOR_BOUNDS: dict[str, tuple[float, float]] = {
    "solar_power":          (0.0,    20.0),   # kW
    "solar_energy_total":   (0.0,    999999.0),
    "grid_import_power":    (0.0,    25.0),    # kW
    "grid_export_power":    (0.0,    25.0),    # kW
    "total_consumption_power": (0.0, 25.0),   # kW
    "battery_soc":          (0.0,    100.0),   # %
    "battery_power":        (-20.0,  20.0),   # kW, can be negative (discharge)
    "battery_charge_kw":    (0.0,    20.0),   # kW, always positive
    "battery_discharge_kw": (0.0,    20.0),   # kW, always positive
    "battery_temperature":  (-20.0,  80.0),   # °C
    "battery_voltage":      (0.0,    1000.0),  # V
    "gas_consumption":      (0.0,    100.0),   # m³/h
}

# Sensors where small negative readings should be clamped to 0 instead of
# rejected — caused by measurement timing differences between separate
# CT sensors (e.g. FoxESS calculated Load Power can dip slightly negative
# near zero-consumption moments). Physically these values cannot be negative.
#
# Sensoren waarbij kleine negatieve waarden naar 0 geclamped worden in plaats
# van verworpen — veroorzaakt door timingverschillen tussen losse CT-sensoren
# (bijv. FoxESS berekend Load Power kan licht negatief worden rond
# bijna-nul-verbruik). Fysiek kunnen deze waarden niet negatief zijn.
CLAMP_TO_ZERO = {
    "total_consumption_power",
    "solar_power",
    "grid_import_power",
    "grid_export_power",
}

# Maximum magnitude of negative value that gets clamped — larger negative
# values are still considered invalid (real sensor error) and rejected.
# Maximale grootte van negatieve waarde die geclamped wordt — grotere
# negatieve waarden worden nog steeds als ongeldig (echte sensorfout) verworpen.
CLAMP_TOLERANCE_KW = 0.5


def validate_reading(
    internal_name: str,
    value: Decimal | None,
    logger: logging.Logger,
) -> Decimal | None:
    """
    Validate a sensor reading against known bounds.
    Returns None (with a warning) if the value is out of range or suspicious.

    Valideer een sensorwaarde tegen bekende grenzen.
    Geeft None terug (met waarschuwing) als de waarde buiten bereik of verdacht is.
    """
    if value is None:
        return None

    bounds = SENSOR_BOUNDS.get(internal_name)
    if bounds is None:
        return value  # Unknown sensor — pass through / Onbekende sensor — doorlaten

    min_val, max_val = bounds
    fval = float(value)

    # Clamp small negative readings to 0 for sensors that can't physically
    # be negative — measurement timing artifact, not an error.
    # Clamp kleine negatieve waarden naar 0 voor sensoren die fysiek niet
    # negatief kunnen zijn — meettimingartefact, geen fout.
    if (
        internal_name in CLAMP_TO_ZERO
        and min_val == 0.0
        and -CLAMP_TOLERANCE_KW <= fval < 0.0
    ):
        logger.debug(
            f"[sensor_validation] {internal_name} value {fval} "
            f"clamped to 0 (measurement timing artifact) / "
            f"naar 0 geclamped (meettimingartefact)"
        )
        return Decimal("0")

    if fval < min_val or fval > max_val:
        logger.warning(
            f"[sensor_validation] {internal_name} value {fval} "
            f"out of bounds [{min_val}, {max_val}] — discarded / buiten bereik — verworpen"
        )
        return None

    return value


class BaseCollector(ABC):
    max_retries: int        = 3
    retry_base_seconds: int = 60
    retry_multiplier: float = 2.0

    def __init__(self, reporter):
        self._reporter = reporter
        self.last_run: datetime | None = None
        self.last_error: str | None = None

    @abstractmethod
    def collect(self) -> None: ...

    @property
    @abstractmethod
    def name(self) -> str: ...

    def run_safe(self) -> bool:
        for attempt in range(1, self.max_retries + 2):
            try:
                if attempt > 1:
                    wait = self.retry_base_seconds * (
                        self.retry_multiplier ** (attempt - 2)
                    )
                    logger.info(f"[{self.name}] Poging {attempt} over {wait:.0f}s")
                    time.sleep(wait)

                self.collect()
                self.last_run = datetime.now()
                self.last_error = None

                if attempt > 1:
                    self._reporter.info(
                        f"Gelukt na {attempt} pogingen", category=self.name
                    )
                return True

            except CollectorTemporaryError as e:
                logger.warning(f"[{self.name}] Tijdelijke fout (poging {attempt}): {e}")
                if attempt == self.max_retries + 1:
                    self.last_error = str(e)
                    self._reporter.error(
                        f"Ophalen mislukt na {self.max_retries + 1} pogingen: {e}",
                        category=self.name,
                    )
                    return False

            except CollectorConfigError as e:
                self.last_error = str(e)
                self._reporter.error(str(e), category=self.name)
                logger.error(f"[{self.name}] Configuratiefout: {e}")
                return False

            except Exception as e:
                self.last_error = str(e)
                self._reporter.error(f"Onverwachte fout: {e}", category=self.name)
                logger.exception(f"[{self.name}] Onverwachte fout")
                return False

        return False
