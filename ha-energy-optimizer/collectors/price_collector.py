from datetime import date, timedelta, datetime, timezone
from zoneinfo import ZoneInfo

_LOCAL_TZ = ZoneInfo("Europe/Amsterdam")
from .base import BaseCollector, CollectorTemporaryError
from database.connection import DatabaseConnection
from database.repository import PriceRepository
from config.config import AppConfig


class PriceCollector(BaseCollector):
    name = "price_collector"

    def __init__(self, db: DatabaseConnection, reporter, config: AppConfig):
        super().__init__(reporter)
        self._repo = PriceRepository(db)
        self._config = config
        self.max_retries        = config.collectors.price_fetch_max_retries
        self.retry_base_seconds = config.collectors.price_fetch_retry_minutes * 60

    def collect(self) -> None:
        from providers import get_provider
        provider = get_provider(self._config)
        # Use local date — container may run in UTC
        # Lokale datum gebruiken — container kan in UTC draaien
        today    = datetime.now(tz=_LOCAL_TZ).date()
        tomorrow = today + timedelta(days=1)

        for target_date in [today, tomorrow]:
            try:
                prices = provider.get_hourly_prices(target_date)
                for price in prices:
                    self._repo.save(price)
            except CollectorTemporaryError:
                if target_date == tomorrow:
                    pass  # Morgen nog niet beschikbaar — normaal voor ochtendrun
                else:
                    raise
