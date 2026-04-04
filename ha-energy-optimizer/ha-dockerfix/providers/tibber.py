import requests
from datetime import date, datetime
from decimal import Decimal
from .base import BaseEnergyProvider
from database.models import EnergyPrice
from collectors.base import CollectorTemporaryError, CollectorConfigError

_GRAPHQL_URL = "https://api.tibber.com/v1-beta/gql"

_QUERY = """
{
  viewer {
    homes {
      currentSubscription {
        priceInfo {
          today { total startsAt }
          tomorrow { total startsAt }
        }
      }
    }
  }
}
"""


class TibberProvider(BaseEnergyProvider):
    """
    Haalt uurprijzen op via de Tibber GraphQL API.
    Vereist een persoonlijk Tibber API-token.

    driver_config verwacht:
        token: str    — Tibber developer token
    """

    energy_type = "electricity"

    def __init__(self, cfg: dict):
        self._token = cfg.get("token", "")
        if not self._token:
            raise CollectorConfigError(
                "Tibber token ontbreekt in provider_config.driver_config"
            )

    def get_hourly_prices(self, target_date: date) -> list[EnergyPrice]:
        raw = self._fetch()
        return self._parse(raw, target_date)

    def _fetch(self) -> dict:
        try:
            resp = requests.post(
                _GRAPHQL_URL,
                json={"query": _QUERY},
                headers={"Authorization": f"Bearer {self._token}"},
                timeout=10,
            )
            if resp.status_code == 401:
                raise CollectorConfigError("Tibber token ongeldig")
            resp.raise_for_status()
            return resp.json()
        except requests.Timeout:
            raise CollectorTemporaryError("Tibber API timeout")
        except requests.ConnectionError:
            raise CollectorTemporaryError("Tibber API niet bereikbaar")

    def _parse(self, raw: dict, target_date: date) -> list[EnergyPrice]:
        try:
            home = raw["data"]["viewer"]["homes"][0]
            price_info = home["currentSubscription"]["priceInfo"]
        except (KeyError, IndexError, TypeError):
            raise CollectorTemporaryError("Onverwacht Tibber API-formaat")

        today    = date.today()
        tomorrow = date.today().__class__.fromordinal(today.toordinal() + 1)

        if target_date == today:
            entries = price_info.get("today", [])
        elif target_date == tomorrow:
            entries = price_info.get("tomorrow", [])
            if not entries:
                raise CollectorTemporaryError(
                    "Tibber: morgen-prijzen nog niet beschikbaar"
                )
        else:
            return []

        prices = []
        for entry in entries:
            prices.append(EnergyPrice(
                price_hour=datetime.fromisoformat(entry["startsAt"]).replace(tzinfo=None),
                energy_type="electricity",
                price_per_kwh=Decimal(str(entry["total"])).quantize(Decimal("0.00001")),
                price_incl_tax=True,
                source="tibber",
            ))
        return sorted(prices, key=lambda p: p.price_hour)
