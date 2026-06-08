# providers/energyzero.py
# /ha-energy-optimizer/ha-energy-optimizer/providers/energyzero.py
# v0.3.0 — 2026-06-08

import requests
from datetime import date, datetime
from decimal import Decimal
from .base import BaseEnergyProvider
from database.models import EnergyPrice
from collectors.base import CollectorTemporaryError

_BASE_URL = "https://api.energyzero.nl/v1/energyprices"


class EnergyZeroProvider(BaseEnergyProvider):
    """
    Haalt uurprijzen op via de EnergyZero API.
    Geen API-token nodig — publieke API.
    Prijzen worden doorgaans rond 14:00 gepubliceerd voor de volgende dag.

    Fetches hourly prices via the EnergyZero API.
    No API token needed — public API.
    Prices are typically published around 14:00 for the next day.

    driver_config verwacht / expects:
        vat_pct:  float — BTW-percentage (bijv. 21.0), standaard 21.0
        incl_tax: bool  — True als de API al BTW-inclusief levert
        timezone: str   — Lokale tijdzone (bijv. Europe/Amsterdam)
    """

    energy_type = "electricity"

    def __init__(self, cfg: dict):
        super().__init__(cfg)  # Sets self._local_tz / Zet self._local_tz
        self._vat      = Decimal(str(cfg.get("vat_pct", 21.0))) / 100
        self._incl_tax = cfg.get("incl_tax", False)

    def get_hourly_prices(self, target_date: date) -> list[EnergyPrice]:
        raw = self._fetch(target_date)
        return self._parse(raw)

    def _fetch(self, target_date: date) -> dict:
        date_str = target_date.isoformat()
        try:
            resp = requests.get(
                _BASE_URL,
                params={
                    "fromDate":  f"{date_str}T00:00:00.000Z",
                    "tillDate":  f"{date_str}T23:59:59.999Z",
                    "interval":  4,
                    "usageType": 1,
                    "inclBtw":   "true" if self._incl_tax else "false",
                },
                timeout=10,
            )
            if resp.status_code == 404:
                raise CollectorTemporaryError(
                    f"EnergyZero: geen prijzen beschikbaar voor {target_date}"
                )
            resp.raise_for_status()
            return resp.json()
        except requests.Timeout:
            raise CollectorTemporaryError("EnergyZero timeout")
        except requests.ConnectionError:
            raise CollectorTemporaryError("EnergyZero niet bereikbaar")

    def _parse(self, raw: dict) -> list[EnergyPrice]:
        prices = []
        for entry in raw.get("Prices", []):
            ts_str = entry.get("readingDate", "")
            price  = Decimal(str(entry.get("price", 0)))

            if not ts_str:
                continue

            if not self._incl_tax:
                price = price * (1 + self._vat)

            # Parse timestamp — EnergyZero API returns UTC (with or without Z)
            # Parseer tijdstempel — EnergyZero API geeft UTC terug (met of zonder Z)
            try:
                ts_parsed = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
                # Convert UTC to local naive via base class helper
                # Omzetten UTC naar lokaal naive via basisklasse helper
                ts_local = self._to_local_naive(ts_parsed)
            except ValueError:
                continue

            prices.append(EnergyPrice(
                price_hour    = ts_local,
                energy_type   = "electricity",
                price_per_kwh = price.quantize(Decimal("0.00001")),
                price_incl_tax= True,
                source        = "energyzero",
            ))
        return sorted(prices, key=lambda p: p.price_hour)
