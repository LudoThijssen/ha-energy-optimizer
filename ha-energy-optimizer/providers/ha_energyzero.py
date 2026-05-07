# providers/ha_energyzero.py
# /ha-energy-optimizer/ha-energy-optimizer/providers/ha_energyzero.py
# v0.2.9 — 2026-04-22
#
# Reads energy prices from the HA EnergyZero sensor.
# Leest energieprijzen uit de HA EnergyZero sensor.
# Prices are already incl. VAT in € — no conversion needed.
# Prijzen zijn al incl. BTW in € — geen omrekening nodig.

from datetime import datetime, date
from decimal import Decimal
from zoneinfo import ZoneInfo
import requests

from .base import BaseEnergyProvider
from database.models import EnergyPrice
from collectors.base import CollectorTemporaryError

_LOCAL_TZ = ZoneInfo("Europe/Amsterdam")
_UTC_TZ   = ZoneInfo("UTC")


class HaEnergyZeroProvider(BaseEnergyProvider):
    """
    Reads prices from sensor.energy_prices_today via HA API.
    Leest prijzen uit sensor.energy_prices_today via de HA API.

    driver_config expects / driver_config verwacht:
        ha_host:   str  — HA host (default: homeassistant)
        ha_port:   int  — HA port (default: 8123)
        ha_token:  str  — Long-lived access token
        entity_id: str  — Sensor entity ID
                          (default: sensor.energy_prices_today)
    """

    energy_type = "electricity"

    def __init__(self, cfg: dict):
        self._ha_url   = f"http://{cfg.get('ha_host', 'homeassistant')}:{cfg.get('ha_port', 8123)}"
        self._token    = cfg.get("ha_token", "")
        self._entity   = cfg.get("entity_id", "sensor.energy_prices_today")

    def get_hourly_prices(self, target_date: date) -> list[EnergyPrice]:
        """
        Fetch prices for target_date from HA sensor.
        Haal prijzen op voor target_date uit de HA sensor.
        """
        try:
            resp = requests.get(
                f"{self._ha_url}/api/states/{self._entity}",
                headers={"Authorization": f"Bearer {self._token}"},
                timeout=10,
            )
            if resp.status_code != 200:
                raise CollectorTemporaryError(
                    f"HA sensor niet bereikbaar: HTTP {resp.status_code}"
                )
            data = resp.json()
            prices_raw = data.get("attributes", {}).get("prices", [])

        except requests.Timeout:
            raise CollectorTemporaryError("HA sensor timeout")
        except requests.ConnectionError:
            raise CollectorTemporaryError("HA niet bereikbaar")

        results = []
        for entry in prices_raw:
            ts_str = entry.get("timestamp", "")
            price  = entry.get("price")

            if price is None or not ts_str:
                continue

            # Parse UTC timestamp / Parseer UTC tijdstempel
            try:
                if ts_str.endswith("+00:00"):
                    ts_utc = datetime.fromisoformat(ts_str)
                else:
                    ts_utc = datetime.fromisoformat(ts_str).replace(tzinfo=_UTC_TZ)

                # Convert to local time / Omzetten naar lokale tijd
                ts_local = ts_utc.astimezone(_LOCAL_TZ)
                ts_naive = ts_local.replace(tzinfo=None)

            except ValueError:
                continue

            # Only keep prices for target_date in local time
            # Bewaar alleen prijzen voor target_date in lokale tijd
            if ts_naive.date() != target_date:
                continue

            results.append(EnergyPrice(
                price_hour    = ts_naive,
                energy_type   = "electricity",
                price_per_kwh = Decimal(str(price)).quantize(Decimal("0.00001")),
                price_incl_tax= False,
                source        = "ha_energyzero",
            ))

        if not results:
            raise CollectorTemporaryError(
                f"Geen prijzen gevonden voor {target_date} in HA sensor"
            )

        return sorted(results, key=lambda p: p.price_hour)