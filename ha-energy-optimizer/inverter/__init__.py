# inverter/__init__.py
#
# Inverter driver factory — returns the correct driver based on configuration.
# Inverterdiver-fabriek — geeft de juiste driver terug op basis van configuratie.
#
# To add a new driver / Om een nieuwe driver toe te voegen:
#   1. Create inverter/yourbrand.py extending BaseInverterDriver
#   2. Add an entry to the registry below
#   3. Set driver = 'yourbrand' in inverter_info table via the GUI

from .base import BaseInverterDriver


def get_driver(driver_name: str, driver_config: dict) -> BaseInverterDriver:
    """
    Return an inverter driver instance by name.
    Geef een inverterdiver-instantie terug op basis van naam.

    Available drivers / Beschikbare drivers:
        simulate  — safe simulation, no real hardware needed (recommended for testing)
        modbus    — Modbus TCP/RTU (production use)
        solaredge — SolarEdge cloud API (planned / gepland)
        growatt   — Growatt cloud API (planned / gepland)
    """
    registry = {
        "simulate": lambda: _load("inverter.simulate", "SimulateDriver",  driver_config),
        "modbus":   lambda: _load("inverter.modbus",   "ModbusDriver",    driver_config),
        "solaredge":lambda: _load("inverter.solaredge","SolarEdgeDriver", driver_config),
        "growatt":  lambda: _load("inverter.growatt",  "GrowattDriver",   driver_config),
    }

    if driver_name not in registry:
        available = ", ".join(registry.keys())
        raise RuntimeError(
            f"Unknown inverter driver '{driver_name}'. "
            f"Available / Beschikbaar: {available}"
        )

    return registry[driver_name]()


def _load(module_path: str, class_name: str, cfg: dict) -> BaseInverterDriver:
    import importlib
    module = importlib.import_module(module_path)
    return getattr(module, class_name)(cfg)


__all__ = ["BaseInverterDriver", "get_driver"]
