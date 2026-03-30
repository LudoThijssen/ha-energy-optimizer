import time
from abc import ABC, abstractmethod
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class CollectorTemporaryError(Exception):
    """Tijdelijke fout — netwerk, timeout, API onbereikbaar."""
    pass


class CollectorConfigError(Exception):
    """Configuratiefout — ontbrekende sleutel, ongeldige instelling."""
    pass


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
