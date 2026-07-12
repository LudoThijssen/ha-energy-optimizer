#
# name:          price_collector.py
# part of:       ha-energy-optimizer
# location:      /ha-energy-optimizer/ha-energy-optimizer/collectors/price_collector.py
# part version:  p_v0.3
# altered:       2026-06-21
#
from datetime import date, timedelta, datetime, timezone
from zoneinfo import ZoneInfo
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
        # Use local date from config — container may run in UTC
        # Lokale datum uit config gebruiken — container kan in UTC draaien
        tz_name  = getattr(self._config.location, "timezone", "Europe/Amsterdam")
        local_tz = ZoneInfo(tz_name)
        today    = datetime.now(tz=local_tz).date()
        tomorrow = today + timedelta(days=1)

        # Fetch all prices in one call — ha_energyzero returns all available days
        # Alle prijzen in één aanroep — ha_energyzero geeft alle beschikbare dagen terug
        # target_date is passed for API-based providers that need a date parameter
        # target_date wordt meegegeven voor API-providers die een datum nodig hebben
        try:
            prices = provider.get_hourly_prices(today)
            for price in prices:
                self._repo.save(price)
        except CollectorTemporaryError:
            raise

        # Try tomorrow separately for API providers that paginate by date
        # Morgen apart proberen voor API-providers die per datum pagineren
        try:
            prices_tomorrow = provider.get_hourly_prices(tomorrow)
            for price in prices_tomorrow:
                self._repo.save(price)
        except CollectorTemporaryError:
            pass  # Morgen nog niet beschikbaar — normaal voor ochtendrun
