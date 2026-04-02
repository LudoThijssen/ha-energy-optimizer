from .base import BaseInverterDriver


def get_driver(driver_name: str, driver_config: dict) -> BaseInverterDriver:
    """
    Factory — geeft de juiste inverter-driver terug op basis van de naam.
    """
    registry = {
        "modbus": lambda: _load("inverter.modbus", "ModbusDriver", driver_config),
    }

    if driver_name not in registry:
        raise RuntimeError(
            f"Onbekende inverter-driver '{driver_name}'. "
            f"Beschikbaar: {', '.join(registry.keys())}"
        )

    return registry[driver_name]()


def _load(module_path: str, class_name: str, cfg: dict):
    import importlib
    module = importlib.import_module(module_path)
    return getattr(module, class_name)(cfg)


__all__ = ["BaseInverterDriver", "get_driver"]
