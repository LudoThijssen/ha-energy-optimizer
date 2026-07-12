#
# name:          base.py
# part of:       ha-energy-optimizer
# location:      /ha-energy-optimizer/ha-energy-optimizer/providers/base.py
# part version:  p_v0.3
# altered:       2026-06-21
#
# Base class for all energy price providers.
# Basisklasse voor alle energieprijsproviders.

from abc import ABC, abstractmethod
from datetime import date, datetime
from zoneinfo import ZoneInfo
import logging

logger = logging.getLogger(__name__)

_UTC_TZ = ZoneInfo("UTC")


class BaseEnergyProvider(ABC):
    """
    Base class for all energy price providers.
    Basisklasse voor alle energieprijsproviders.

    All providers receive the local timezone via cfg['timezone'].
    This base class provides a helper to convert UTC datetimes to
    naive local datetimes for consistent database storage.

    Alle providers ontvangen de lokale tijdzone via cfg['timezone'].
    Deze basisklasse biedt een helper om UTC datetimes om te zetten naar
    naive lokale datetimes voor consistente databaseopslag.
    """

    energy_type: str = "electricity"

    def __init__(self, cfg: dict):
        tz_name = cfg.get("timezone", "Europe/Amsterdam")
        self._local_tz = ZoneInfo(tz_name)

    def _to_local_naive(self, ts: datetime) -> datetime:
        """
        Convert any datetime to a naive local datetime for database storage.
        Handles both aware (UTC or other offset) and naive datetimes.

        Converteert elke datetime naar een naive lokale datetime voor databaseopslag.
        Verwerkt zowel aware (UTC of andere offset) als naive datetimes.

        Aware datetime  → convert to local → strip tzinfo
        Naive datetime  → assume UTC → convert to local → strip tzinfo
        """
        if ts.tzinfo is not None:
            # Aware — convert to local regardless of source offset
            # Aware — omzetten naar lokaal ongeacht bronoffset
            return ts.astimezone(self._local_tz).replace(tzinfo=None)
        else:
            # Naive — assume UTC (most APIs return UTC without offset)
            # Naive — aannemen UTC (de meeste APIs geven UTC zonder offset terug)
            logger.debug(
                f"[provider] Naive datetime {ts} assumed UTC, converting to local / "
                f"Naive datetime {ts} aangenomen als UTC, omgezet naar lokaal"
            )
            return ts.replace(tzinfo=_UTC_TZ).astimezone(self._local_tz).replace(tzinfo=None)

    @abstractmethod
    def get_hourly_prices(self, target_date: date) -> list: ...
