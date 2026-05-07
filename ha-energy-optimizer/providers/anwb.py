# providers/anwb.py
#
# ANWB Energie uses the EnergyZero platform for dynamic pricing.
# This wrapper is identical to EnergyZero but identifies itself as 'anwb'.
# Wanneer EnergyZero de API wijzigt, volstaat het om energyzero.py bij te werken.
# When EnergyZero changes their API, updating energyzero.py is sufficient.

from datetime import date
from database.models import EnergyPrice
from .energyzero import EnergyZeroProvider


class AnwbProvider(EnergyZeroProvider):
    """
    ANWB Energie — dynamic electricity prices via EnergyZero platform.
    ANWB Energie — dynamische stroomprijzen via het EnergyZero platform.

    driver_config expects / driver_config verwacht:
        vat_pct:  float  — VAT percentage / BTW-percentage (default 21.0)
        incl_tax: bool   — Whether API returns prices incl. VAT / Of API BTW-inclusief levert
    """

    energy_type = "electricity"

    def get_hourly_prices(self, target_date: date) -> list[EnergyPrice]:
        # Fetch via EnergyZero, then relabel source to 'anwb'
        # Ophalen via EnergyZero, daarna bron herschrijven naar 'anwb'
        prices = super().get_hourly_prices(target_date)
        for price in prices:
            price.source = "anwb"
        return prices
