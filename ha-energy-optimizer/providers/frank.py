# providers/frank.py
#
# Frank Energie — dynamic electricity prices (Netherlands).
# Frank Energie — dynamische stroomprijzen (Nederland).
#
# STATUS: Stub — not yet implemented / Nog niet geïmplementeerd.
# Implement get_hourly_prices() using the Frank Energie GraphQL API.
# Implementeer get_hourly_prices() via de Frank Energie GraphQL API.
# API documentation: https://frank-energie.com/api

from datetime import date
from .base import BaseEnergyProvider
from database.models import EnergyPrice
from collectors.base import CollectorConfigError


class FrankProvider(BaseEnergyProvider):
    """
    Frank Energie dynamic pricing provider (stub).
    Frank Energie dynamische prijzen provider (stub).

    driver_config expects / driver_config verwacht:
        token:   str   — Frank Energie API token
        vat_pct: float — VAT percentage / BTW-percentage
    """

    energy_type = "electricity"

    def __init__(self, cfg: dict):
        self._token   = cfg.get("token", "")
        if not self._token:
            raise CollectorConfigError(
                "Frank Energie token missing in provider_config.driver_config / "
                "Frank Energie token ontbreekt in provider_config.driver_config"
            )

    def get_hourly_prices(self, target_date: date) -> list[EnergyPrice]:
        raise NotImplementedError(
            "Frank Energie provider is not yet implemented. "
            "Frank Energie provider is nog niet geïmplementeerd. "
            "Contributions welcome / Bijdragen welkom: "
            "https://github.com/YOUR_USERNAME/ha-energy-optimizer"
        )
