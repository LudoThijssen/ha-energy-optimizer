from abc import ABC, abstractmethod
from datetime import date
from database.models import EnergyPrice


class BaseEnergyProvider(ABC):
    energy_type: str = "electricity"

    @abstractmethod
    def get_hourly_prices(self, target_date: date) -> list[EnergyPrice]: ...
