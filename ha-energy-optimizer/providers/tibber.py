#
# name:          tibber.py
# part of:       ha-energy-optimizer
# location:      /ha-energy-optimizer/ha-energy-optimizer/providers/tibber.py
# part version:  p_v0.5
# altered:       2026-07-28
#
# p_v0.4: kwartierprijzen aangevraagd via resolution: QUARTER_HOURLY op het
# priceInfo-veld (sinds 1 okt. 2025 door Tibber ondersteund/vereist —
# https://developer.tibber.com/docs/changelog). Levert nu 96 in plaats van
# 24 entries per dag. _parse() hoefde niet aangepast: die loopt al generiek
# over `entries` zonder aanname over de lengte, dus dit werkt door tot in
# de database (energy_prices.price_hour is een kale DATETIME, geen
# uur-beperking) zonder verdere wijziging.
#
# p_v0.4: quarter-hour prices now requested via resolution: QUARTER_HOURLY
# on the priceInfo field (supported/required by Tibber since Oct 1, 2025 —
# https://developer.tibber.com/docs/changelog). Now yields 96 instead of 24
# entries per day. _parse() didn't need changes: it already loops over
# `entries` generically with no assumption about length, so this flows
# through to the database (energy_prices.price_hour is a plain DATETIME,
# no hourly restriction) without further changes.
#
# p_v0.5: date.today() -> now_local().date() in _parse() — zie
# config/localtime.py voor de reden (bekend HA Supervisor tijdzone-
# probleem). Deze today/tomorrow-vergelijking bepaalt of Tibber's
# "today"- of "tomorrow"-array wordt gebruikt; met de containerklok kon
# dat rond middernacht de verkeerde dag kiezen.
#
# p_v0.5: date.today() -> now_local().date() in _parse() — see
# config/localtime.py for the reason (known HA Supervisor timezone
# issue). This today/tomorrow comparison decides whether Tibber's
# "today" or "tomorrow" array is used; with the container clock this
# could pick the wrong day around midnight.
#
import requests
from datetime import date, datetime, timedelta
from config.localtime import now_local
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
        priceInfo(resolution: QUARTER_HOURLY) {
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
    Haalt kwartierprijzen op via de Tibber GraphQL API.
    Vereist een persoonlijk Tibber API-token.

    p_v0.4: voorheen uurprijzen — Tibber vereist sinds 1 okt. 2025
    resolution: QUARTER_HOURLY op priceInfo (het oude ongeparametriseerde
    priceInfo-veld blijft technisch werken maar levert dan alsnog impliciet
    de nieuwe kwartier-brondata terug via een ander pad; expliciet vragen
    om QUARTER_HOURLY is de door Tibber gedocumenteerde weg).

    Previously hourly prices — Tibber has required resolution:
    QUARTER_HOURLY on priceInfo since Oct 1, 2025 (the old unparametrized
    priceInfo field technically still works but then implicitly returns the
    new quarter-hour source data via a different path; explicitly
    requesting QUARTER_HOURLY is Tibber's documented way).

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
        """
        Ondanks de naam (interface-contract, gedeeld met andere providers
        die wél uurprijzen leveren): geeft nu kwartierprijzen terug (96 per
        dag) voor Tibber.
        Despite the name (interface contract, shared with other providers
        that do give hourly prices): now returns quarter-hour prices
        (96 per day) for Tibber.
        """
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

        # p_v0.5: now_local() i.p.v. date.today() — anders kan deze
        # today/tomorrow-vergelijking de verkeerde dag kiezen als de
        # container-klok verkeerd staat (zie config/localtime.py).
        # p_v0.5: now_local() instead of date.today() — otherwise this
        # today/tomorrow comparison can pick the wrong day if the
        # container clock is wrong (see config/localtime.py).
        today    = now_local().date()
        tomorrow = today + timedelta(days=1)

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
