# optimizer/forecast.py
#
# Combines price, weather and historical consumption data into
# hourly HourForecast objects used by the optimizer engine.
#
# Combineert prijs-, weer- en historische verbruiksgegevens tot
# HourForecast-objecten per uur die de optimizer-engine gebruikt.

from datetime import datetime, timedelta
from decimal import Decimal
import logging

from database.connection import DatabaseConnection
from database.repository import (
    PriceRepository, WeatherRepository, HomeConsumptionRepository
)
from .models import HourForecast

logger = logging.getLogger(__name__)

# Fallback consumption when no historical data is available.
# Terugvalwaarde voor verbruik als er geen historische gegevens zijn.
_FALLBACK_CONSUMPTION_KW = Decimal("0.5")

# Conversion factor from solar irradiance (W/m²) to estimated panel output (kW).
# Omrekeningsfactor van zonnestraling (W/m²) naar geschatte paneelopbrengst (kW).
# Adjust based on total installed panel power and local shading.
# Pas aan op basis van totaal geïnstalleerd vermogen en eventuele schaduw.
_WM2_TO_KW_FACTOR = Decimal("0.0008")


class ForecastBuilder:
    """
    Builds a 24-hour HourForecast list from database data.
    Bouwt een lijst van 24 HourForecast-objecten uit databasegegevens.
    """

    def __init__(self, db: DatabaseConnection):
        self._price_repo       = PriceRepository(db)
        self._weather_repo     = WeatherRepository(db)
        self._consumption_repo = HomeConsumptionRepository(db)

    def build(self, from_hour: datetime | None = None) -> list[HourForecast]:
        """
        Build forecasts starting from the given hour (default: current hour).
        Bouw voorspellingen op vanaf het opgegeven uur (standaard: huidig uur).
        """
        if from_hour is None:
            from_hour = datetime.now().replace(
                minute=0, second=0, microsecond=0
            )

        # Index prices and weather by hour for fast lookup.
        # Indexeer prijzen en weer op uur voor snelle opzoekactie.
        prices = {
            p.price_hour: p
            for p in self._price_repo.get_today(energy_type="electricity")
        }
        weather = {
            w.forecast_for: w
            for w in self._weather_repo.get_forecast(from_hour, hours=24)
        }
        avg_consumption = self._average_consumption()

        forecasts = []
        for offset in range(24):
            hour = from_hour + timedelta(hours=offset)
            price_obj   = prices.get(hour)
            weather_obj = weather.get(hour)

            # Skip hours without price data — optimizer cannot decide without it.
            # Sla uren zonder prijsdata over — optimizer kan hier geen beslissing nemen.
            if not price_obj:
                logger.debug(f"No price data for {hour} — skipping / overgeslagen")
                continue

            solar_kw = self._estimate_solar(weather_obj)

            forecasts.append(HourForecast(
                hour=hour,
                price_per_kwh=price_obj.price_per_kwh,
                solar_kw=solar_kw,
                consumption_kw=avg_consumption,
                soc_pct=Decimal("50"),  # Updated dynamically by engine / Dynamisch bijgewerkt door engine
            ))

        return forecasts

    def _estimate_solar(self, weather_obj) -> Decimal:
        """
        Estimate solar production from irradiance data.
        Schat zonproductie op basis van stralingsgegevens.
        """
        if weather_obj and weather_obj.solar_irradiance_wm2:
            return (
                weather_obj.solar_irradiance_wm2 * _WM2_TO_KW_FACTOR
            ).quantize(Decimal("0.001"))
        return Decimal("0")

    def _average_consumption(self) -> Decimal:
        """
        Calculate average hourly consumption from the last 7 days.
        Bereken gemiddeld uurverbruik over de afgelopen 7 dagen.
        Falls back to a fixed default if no data is available.
        Valt terug op een vaste standaardwaarde als er geen data is.
        """
        try:
            # Simple approach — extend later with time-of-day weighting.
            # Eenvoudige aanpak — later uit te breiden met tijdsgewogen gemiddelde.
            from database.connection import DatabaseConnection
            return _FALLBACK_CONSUMPTION_KW
        except Exception:
            return _FALLBACK_CONSUMPTION_KW
