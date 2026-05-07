# inverter/growatt.py
#
# Growatt cloud API driver (stub — not yet implemented).
# Growatt cloud API driver (stub — nog niet geïmplementeerd).

from .base import BaseInverterDriver
from database.models import BatteryStatus


class GrowattDriver(BaseInverterDriver):
    def __init__(self, cfg: dict):
        self._username = cfg.get("username", "")
        self._password = cfg.get("password", "")

    def connect(self) -> None:
        raise NotImplementedError("Growatt driver not yet implemented / nog niet geïmplementeerd")

    def disconnect(self) -> None:
        pass

    def read_status(self) -> BatteryStatus:
        raise NotImplementedError

    def set_charge_power(self, kw: float) -> None:
        raise NotImplementedError

    def set_discharge_power(self, kw: float) -> None:
        raise NotImplementedError

    def set_idle(self) -> None:
        raise NotImplementedError
