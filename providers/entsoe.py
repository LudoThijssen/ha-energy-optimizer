import requests
from datetime import date, datetime, timezone
from decimal import Decimal
from xml.etree import ElementTree as ET
from .base import BaseEnergyProvider
from database.models import EnergyPrice
from collectors.base import CollectorTemporaryError, CollectorConfigError

# ENTSO-E Transparency Platform REST API
_BASE_URL = "https://web-api.tp.entsoe.eu/api"
_NS = {"ns": "urn:iec62325.351:tc57wg16:451-3:publicationdocument:7:3"}


class EntsoEProvider(BaseEnergyProvider):
    """
    Haalt day-ahead elektriciteitsprijzen op via de ENTSO-E Transparency API.
    Gratis, maar vereist een API-token (aanvragen via transparency.entsoe.eu).

    driver_config verwacht:
        token: str         — persoonlijk API-token
        area_code: str     — bidding zone, bijv. '10YNL----------L' voor Nederland
        vat_pct: float     — BTW-percentage om toe te voegen (bijv. 21.0)
    """

    energy_type = "electricity"

    def __init__(self, cfg: dict):
        self._token     = cfg.get("token", "")
        self._area      = cfg.get("area_code", "10YNL----------L")
        self._vat       = Decimal(str(cfg.get("vat_pct", 21.0))) / 100

        if not self._token:
            raise CollectorConfigError(
                "ENTSO-E token ontbreekt in provider_config.driver_config"
            )

    def get_hourly_prices(self, target_date: date) -> list[EnergyPrice]:
        xml_text = self._fetch(target_date)
        return self._parse(xml_text, target_date)

    def _fetch(self, target_date: date) -> str:
        # ENTSO-E verwacht UTC-tijden in formaat YYYYMMDDhhmm
        start = datetime(target_date.year, target_date.month, target_date.day,
                         0, 0, tzinfo=timezone.utc)
        end   = datetime(target_date.year, target_date.month, target_date.day,
                         23, 0, tzinfo=timezone.utc)

        params = {
            "securityToken":         self._token,
            "documentType":          "A44",        # Day-ahead prijzen
            "in_Domain":             self._area,
            "out_Domain":            self._area,
            "periodStart":           start.strftime("%Y%m%d%H%M"),
            "periodEnd":             end.strftime("%Y%m%d%H%M"),
        }
        try:
            resp = requests.get(_BASE_URL, params=params, timeout=15)
            if resp.status_code == 401:
                raise CollectorConfigError("ENTSO-E token ongeldig")
            if resp.status_code == 400:
                raise CollectorTemporaryError(
                    f"ENTSO-E: geen data voor {target_date} "
                    f"(mogelijk nog niet gepubliceerd)"
                )
            resp.raise_for_status()
            return resp.text
        except requests.Timeout:
            raise CollectorTemporaryError("ENTSO-E timeout")
        except requests.ConnectionError:
            raise CollectorTemporaryError("ENTSO-E niet bereikbaar")

    def _parse(self, xml_text: str, target_date: date) -> list[EnergyPrice]:
        root = ET.fromstring(xml_text)
        prices = []

        for ts in root.findall(".//ns:TimeSeries", _NS):
            resolution = ts.findtext(".//ns:resolution", namespaces=_NS)
            if resolution != "PT60M":
                continue  # Alleen uurprijzen

            start_str = ts.findtext(
                ".//ns:timeInterval/ns:start", namespaces=_NS
            )
            if not start_str:
                continue

            start_dt = datetime.fromisoformat(start_str.replace("Z", "+00:00"))

            for point in ts.findall(".//ns:Point", _NS):
                pos   = int(point.findtext("ns:position", namespaces=_NS))
                price = Decimal(point.findtext("ns:price.amount", namespaces=_NS))

                # ENTSO-E levert prijzen in €/MWh — omrekenen naar €/kWh
                price_kwh = price / 1000

                # BTW toevoegen
                price_incl = price_kwh * (1 + self._vat)

                hour_dt = start_dt.replace(tzinfo=None) + __import__(
                    "datetime"
                ).timedelta(hours=pos - 1)

                prices.append(EnergyPrice(
                    price_hour=hour_dt,
                    energy_type="electricity",
                    price_per_kwh=price_incl.quantize(Decimal("0.00001")),
                    price_incl_tax=True,
                    source="entsoe",
                ))

        return sorted(prices, key=lambda p: p.price_hour)
