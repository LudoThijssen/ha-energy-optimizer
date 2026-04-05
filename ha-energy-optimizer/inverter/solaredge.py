# inverter/solaredge.py
#
# SolarEdge cloud API driver (stub — not yet implemented).
# SolarEdge cloud API driver (stub — nog niet geïmplementeerd).
#
# Contributions welcome / Bijdragen welkom:
# https://github.com/YOUR_USERNAME/ha-energy-optimizer
#
# driver_config expects / driver_config verwacht:
#   api_key:  str  — SolarEdge API key (developer.solaredge.com)
#   site_id:  str  — SolarEdge site ID

from .base import BaseInverterDriver
from database.models import BatteryStatus


class SolarEdgeDriver(BaseInverterDriver):
    def __init__(self, cfg: dict):
        self._api_key = cfg.get("api_key", "")
        self._site_id = cfg.get("site_id", "")

    def connect(self) -> None:
        raise NotImplementedError("SolarEdge driver not yet implemented / nog niet geïmplementeerd")

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
