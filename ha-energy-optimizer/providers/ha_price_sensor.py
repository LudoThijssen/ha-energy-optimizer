# providers/ha_price_sensor.py
# /ha-energy-optimizer/ha-energy-optimizer/providers/ha_price_sensor.py
# v0.3.0 — 2026-06-08
#
# Generic Home Assistant price sensor provider.
# Reads hourly energy prices from any HA sensor that follows the standard
# price sensor format (list of {timestamp, price} entries).
#
# Generieke Home Assistant prijssensor provider.
# Leest uurlijkse energieprijzen uit elke HA sensor die het standaard
# prijssensorformaat volgt (lijst van {timestamp, price} vermeldingen).
#
# ── Required sensor format / Vereist sensorformaat ───────────────────────────
#
# The HA sensor must expose a 'prices' attribute with this structure:
# De HA sensor moet een 'prices' attribuut hebben met deze structuur:
#
#   prices:
#     - timestamp: "2026-06-07T21:00:00+00:00"   # UTC with offset (recommended)
#       price: 0.172                               # Price in €/kWh excl. or incl. VAT
#     - timestamp: "2026-06-07T22:00:00+00:00"
#       price: 0.168
#     ...
#
# Supported timestamp formats / Ondersteunde tijdstempelformaten:
#   "2026-06-07T21:00:00+00:00"  — UTC with offset (EnergyZero add-on)
#   "2026-06-07T21:00:00Z"       — UTC with Z suffix
#   "2026-06-07T23:00:00+02:00"  — Local time with offset
#   "2026-06-07 21:00:00+00:00"  — Space separator (some integrations)
#   "2026-06-07T23:00:00"        — Naive — assumed to be local time
#
# ── driver_config ─────────────────────────────────────────────────────────────
#
#   entity_id: str   — HA sensor entity ID (e.g. sensor.energy_prices_today)
#   ha_host:   str   — HA host (default: homeassistant)
#   ha_port:   int   — HA port (default: 8123)
#   ha_token:  str   — Long-lived access token
#   price_attr:str   — Attribute name containing price list (default: prices)
#   ts_key:    str   — Key for timestamp in each entry (default: timestamp)
#   price_key: str   — Key for price in each entry (default: price)
#   incl_tax:  bool  — True if prices already include VAT (default: True)
#   vat_pct:   float — VAT to add if incl_tax=False (default: 21.0)
#   timezone:  str   — Local timezone (default: Europe/Amsterdam)
#
# ─────────────────────────────────────────────────────────────────────────────

import requests
import logging
from datetime import date, datetime
from decimal import Decimal
from .base import BaseEnergyProvider
from database.models import EnergyPrice
from collectors.base import CollectorTemporaryError

logger = logging.getLogger(__name__)


class HaPriceSensorProvider(BaseEnergyProvider):
    """
    Generic provider that reads prices from any HA sensor with a 'prices' attribute.
    Generieke provider die prijzen leest uit elke HA sensor met een 'prices' attribuut.
    """

    energy_type = "electricity"

    def __init__(self, cfg: dict):
        super().__init__(cfg)  # Sets self._local_tz
        self._ha_url    = f"http://{cfg.get('ha_host', 'homeassistant')}:{cfg.get('ha_port', 8123)}"
        self._token     = cfg.get("ha_token", "")
        self._entity    = cfg.get("entity_id", "")
        self._price_attr= cfg.get("price_attr", "prices")
        self._ts_key    = cfg.get("ts_key", "timestamp")
        self._price_key = cfg.get("price_key", "price")
        self._incl_tax  = cfg.get("incl_tax", True)
        self._vat       = Decimal(str(cfg.get("vat_pct", 21.0))) / 100

    def get_hourly_prices(self, target_date: date) -> list[EnergyPrice]:
        """
        Fetch all prices from the HA sensor. The target_date parameter is
        accepted for interface compatibility but not used for filtering —
        the sensor returns all available prices and all are stored.

        Haalt alle prijzen op uit de HA sensor. De target_date parameter wordt
        geaccepteerd voor interface-compatibiliteit maar niet gebruikt voor filtering —
        de sensor geeft alle beschikbare prijzen terug en alle worden opgeslagen.
        """
        raw_prices = self._fetch_from_ha()
        return self._parse(raw_prices, target_date)

    def _fetch_from_ha(self) -> list:
        """Fetch sensor state and attributes from HA API."""
        url = f"{self._ha_url}/api/states/{self._entity}"
        try:
            resp = requests.get(
                url,
                headers={
                    "Authorization": f"Bearer {self._token}",
                    "Content-Type":  "application/json",
                },
                timeout=10,
            )
            if resp.status_code == 404:
                raise CollectorTemporaryError(
                    f"HA sensor niet gevonden: {self._entity} / "
                    f"HA sensor not found: {self._entity}"
                )
            resp.raise_for_status()
            data = resp.json()
            prices = data.get("attributes", {}).get(self._price_attr, [])
            if not prices:
                raise CollectorTemporaryError(
                    f"Geen prijsdata in attribuut '{self._price_attr}' "
                    f"van sensor {self._entity} / "
                    f"No price data in attribute '{self._price_attr}' "
                    f"of sensor {self._entity}"
                )
            return prices
        except requests.Timeout:
            raise CollectorTemporaryError(f"HA timeout bij ophalen {self._entity}")
        except requests.ConnectionError:
            raise CollectorTemporaryError(f"HA niet bereikbaar op {self._ha_url}")

    def _parse(self, raw_prices: list, target_date: date) -> list[EnergyPrice]:
        results = []
        for entry in raw_prices:
            ts_str = str(entry.get(self._ts_key, "")).strip()
            price  = entry.get(self._price_key)

            if not ts_str or price is None:
                continue

            # Parse timestamp — support all common formats
            # Parseer tijdstempel — ondersteun alle gangbare formaten
            try:
                ts_str_clean = ts_str.replace("Z", "+00:00").replace(" ", "T")
                parsed = datetime.fromisoformat(ts_str_clean)
                ts_local = self._to_local_naive(parsed)
            except ValueError:
                logger.warning(f"[ha_price_sensor] Ongeldig tijdstempel: {ts_str}")
                continue

            price_dec = Decimal(str(price)).quantize(Decimal("0.00001"))
            if not self._incl_tax:
                price_dec = (price_dec * (1 + self._vat)).quantize(Decimal("0.00001"))

            results.append(EnergyPrice(
                price_hour     = ts_local,
                energy_type    = "electricity",
                price_per_kwh  = price_dec,
                price_incl_tax = True,
                source         = f"ha_sensor:{self._entity}",
            ))

        if not results:
            raise CollectorTemporaryError(
                f"Geen geldige prijzen gevonden in {self._entity}"
            )

        return sorted(results, key=lambda p: p.price_hour)
