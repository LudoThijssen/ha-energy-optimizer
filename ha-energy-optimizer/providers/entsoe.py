# name:          entsoe.py
# part of:       ha-energy-optimizer
# location:      /ha-energy-optimizer/ha-energy-optimizer/providers/entsoe.py
# part version:  p_v0.4
# altered:       2026-07-28
#
# p_v0.4: twee tijdzone-problemen gevonden en gefixt, tijdens het
# controleren van alle providers op hetzelfde soort probleem als bij
# Tibber:
#   1. super().__init__(cfg) ontbrak — self._local_tz bestond niet.
#   2. hour_dt werd opgebouwd door een UTC-tijdstip domweg de tzinfo af te
#      pakken (`start_dt.replace(tzinfo=None)`) ZONDER om te rekenen naar
#      lokale tijd — in tegenstelling tot elke andere provider. ENTSO-E
#      levert tijden in UTC; bij gebruik zouden de opgeslagen prijzen 1-2
#      uur verschoven hebben gestaan (CET/CEST-afhankelijk). Nu via de
#      gedeelde self._to_local_naive() helper, zelfde aanpak als overal.
#   3. Bijvangst: een lelijke `__import__("datetime").timedelta(...)`
#      workaround opgeruimd — timedelta stond simpelweg niet in de imports.
#
# p_v0.4: two timezone problems found and fixed, while checking all
# providers for the same kind of issue found in Tibber:
#   1. super().__init__(cfg) was missing — self._local_tz never existed.
#   2. hour_dt was built by simply stripping tzinfo from a UTC timestamp
#      (`start_dt.replace(tzinfo=None)`) WITHOUT converting to local time
#      — unlike every other provider. ENTSO-E returns times in UTC; if
#      used, stored prices would have been off by 1-2 hours (CET/CEST
#      dependent). Now uses the shared self._to_local_naive() helper, same
#      approach as everywhere else.
#   3. Bonus: cleaned up an ugly `__import__("datetime").timedelta(...)`
#      workaround — timedelta simply wasn't in the imports.
#
import requests
from datetime import date, datetime, timedelta, timezone
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
        super().__init__(cfg)
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

                # p_v0.4: self._to_local_naive() i.p.v. start_dt.replace(
                # tzinfo=None) — start_dt is een UTC-tijdstip; die kaal
                # de tzinfo afpakken liet de UTC-kloktijd staan alsof het
                # al lokale tijd was. Ook de lelijke __import__("datetime")
                # workaround weg nu timedelta gewoon geïmporteerd is.
                # p_v0.4: self._to_local_naive() instead of start_dt.replace(
                # tzinfo=None) — start_dt is a UTC timestamp; bare-stripping
                # its tzinfo left the UTC clock time in place as if it were
                # already local time. Also removed the ugly
                # __import__("datetime") workaround now that timedelta is
                # simply imported.
                hour_dt = self._to_local_naive(start_dt + timedelta(hours=pos - 1))

                prices.append(EnergyPrice(
                    price_hour=hour_dt,
                    energy_type="electricity",
                    price_per_kwh=price_incl.quantize(Decimal("0.00001")),
                    price_incl_tax=True,
                    source="entsoe",
                ))

        return sorted(prices, key=lambda p: p.price_hour)

#
