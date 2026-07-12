#
# name:          __init__.py
# part of:       ha-energy-optimizer
# location:      /ha-energy-optimizer/ha-energy-optimizer/providers/__init__.py
# part version:  p_v0.3
# altered:       2026-06-21
#
# Provider factory — returns the active energy price driver.
# Provider factory — geeft de actieve energieprijsdriver terug.
#
# To add a new provider / Om een nieuwe provider toe te voegen:
#   1. Create providers/myprovider.py extending BaseEnergyProvider
#   2. Add an entry to the registry below / Voeg een regel toe aan het register
#   3. Set provider_driver = 'myprovider' in the provider_config table

from .base import BaseEnergyProvider
from config.config import AppConfig


def get_provider(config: AppConfig) -> BaseEnergyProvider:
    """
    Factory — geeft de actieve provider-driver terug op basis van de database-config.
    Voeg nieuwe providers toe door ze hier te registreren.
    """

    from database.connection import DatabaseConnection
    from database.connection import DatabaseConnection as _DC

    db = DatabaseConnection(config.database)
    with db.cursor() as cur:
        cur.execute("""
            SELECT provider_driver, driver_config FROM provider_config
            WHERE energy_type = 'electricity' AND is_active = 1
            LIMIT 1
        """)
        row = cur.fetchone()

    if not row:
        raise RuntimeError(
            "Geen actieve energieprovider gevonden in provider_config. "
            "Voeg een rij toe via de instellingen."
        )

    driver_name = row["provider_driver"]
    import json as _json
    _raw_cfg = row["driver_config"] or {}
    if isinstance(_raw_cfg, str):
         try:
             driver_cfg = _json.loads(_raw_cfg)
         except Exception:
             driver_cfg = {}
    else:
         driver_cfg = _raw_cfg

    # Inject timezone into driver_cfg so providers don't need to hardcode it
    # Tijdzone injecteren in driver_cfg zodat providers die niet hardcoded hoeven
    tz_name = getattr(getattr(config, "location", None), "timezone", "Europe/Amsterdam")
    driver_cfg.setdefault("timezone", tz_name)

    # Inject HA connection settings for ha_energyzero provider if not already set
    # HA-verbindingsinstellingen injecteren voor ha_energyzero provider indien niet aanwezig
    try:
        ha_cfg = config.homeassistant
        driver_cfg.setdefault("ha_host",  getattr(ha_cfg, "host",  "homeassistant"))
        driver_cfg.setdefault("ha_port",  getattr(ha_cfg, "port",  8123))
        driver_cfg.setdefault("ha_token", getattr(ha_cfg, "token", ""))
    except AttributeError:
        pass

    registry = {
        "anwb":             lambda: _load("providers.anwb",             "AnwbProvider",           driver_cfg),
        "energyzero":       lambda: _load("providers.energyzero",       "EnergyZeroProvider",     driver_cfg),
        "ha_energyzero":    lambda: _load("providers.ha_energyzero",    "HaEnergyZeroProvider",   driver_cfg),
        "ha_price_sensor":  lambda: _load("providers.ha_price_sensor",  "HaPriceSensorProvider",  driver_cfg),
        "entsoe":           lambda: _load("providers.entsoe",           "EntsoEProvider",         driver_cfg),
        "tibber":           lambda: _load("providers.tibber",           "TibberProvider",         driver_cfg),
        "frank":            lambda: _load("providers.frank",            "FrankProvider",          driver_cfg),
    }

    if driver_name not in registry:
        raise RuntimeError(
            f"Onbekende provider-driver '{driver_name}'. "
            f"Beschikbaar: {', '.join(registry.keys())}"
        )

    return registry[driver_name]()


def _load(module_path: str, class_name: str, cfg: dict):
    import importlib
    module = importlib.import_module(module_path)
    cls = getattr(module, class_name)
    return cls(cfg)


__all__ = ["BaseEnergyProvider", "get_provider"]

