# version 0.2.9
# 2026-04-24
# ha-energy-optimizer/ha-energy-optimizer/reporter/reporte.py

import logging
import requests
from datetime import datetime
from database.connection import DatabaseConnection
from database.models import ReportEntry
from database.repository import ReportRepository, BatteryRepository, SolarRepository, HomeConsumptionRepository
from config.config import AppConfig

logger = logging.getLogger(__name__)


class Reporter:
    """
    Centrale logger en notificatie-module.
    Schrijft naar de database en stuurt berichten naar Home Assistant.
    """

    def __init__(self, db: DatabaseConnection, config: AppConfig):
        self._repo        = ReportRepository(db)
        self._battery     = BatteryRepository(db)
        self._solar       = SolarRepository(db)
        self._consumption = HomeConsumptionRepository(db)
        self._config      = config
        self._ha_url  = f"http://{config.ha.host}:{config.ha.port}"
        self._headers = {
            "Authorization": f"Bearer {config.ha.token}",
            "Content-Type":  "application/json",
        }

    def info(self, message: str, category: str | None = None) -> None:
        self._log("info", message, category)

    def warning(self, message: str, category: str | None = None) -> None:
        self._log("warning", message, category)
        if self._config.reporting.notify_on_warning:
            self._notify(f"Waarschuwing: {message}")

    def error(self, message: str, category: str | None = None) -> None:
        self._log("error", message, category)
        if self._config.reporting.notify_on_error:
            self._notify(f"Fout: {message}", title="HA Energy Optimizer — Fout")

    def daily_summary(self) -> None:
        """Stel een dagrapport samen en stuur het als notificatie."""
        battery     = self._battery.get_today_summary()
        solar       = self._solar.get_today_total()
        consumption = self._consumption.get_today_summary()

        lines = ["Dagrapport energie-optimizer"]

        # Solar / Zon
        solar_ok = solar > 0
        lines.append(f"Zonopbrengst:     {solar:.2f} kWh"
                     + ("" if solar_ok else " ⚠ (geen data)"))

        # Grid / Net
        import_kwh  = consumption.get("import_kwh")  or 0
        export_kwh  = consumption.get("export_kwh")  or 0
        verbruik    = consumption.get("verbruik_kwh") or 0

        if import_kwh > 0 or export_kwh > 0:
            lines.append(f"Netafname:        {float(import_kwh):.2f} kWh")
            lines.append(f"Teruglevering:    {float(export_kwh):.2f} kWh")
            if verbruik > 0:
                lines.append(f"Totaal verbruik:  {float(verbruik):.2f} kWh")
        else:
            lines.append("Netdata:          ⚠ geen data beschikbaar")

        # Battery / Batterij
        if battery and (battery.get("min_soc") is not None):
            lines += [
                f"Batterij SoC:     {battery['min_soc'] or 0:.0f}% — {battery['max_soc'] or 0:.0f}%",
                f"Opgeladen:        {(battery['total_charged'] or 0):.2f} kWh",
                f"Ontladen:         {(battery['total_discharged'] or 0):.2f} kWh",
            ]

        message = "\n".join(lines)
        self._log("daily", message, category="daily_report")
        self._notify(message, title="Dagrapport energie")

    def _log(self, report_type: str, message: str, category: str | None) -> None:
        logger.info(f"[{category or report_type}] {message}")
        try:
            self._repo.save(ReportEntry(
                report_type=report_type,
                message=message,
                category=category,
            ))
        except Exception as e:
            logger.error(f"Kon rapport niet opslaan: {e}")

    def _notify(self, message: str, title: str = "HA Energy Optimizer") -> None:
        try:
            resp = requests.post(
                f"{self._ha_url}/api/services/notify/notify",
                json={"title": title, "message": message},
                headers=self._headers,
                timeout=15,
            )
            if resp.status_code not in (200, 201):
                logger.debug(f"HA notification returned {resp.status_code}")
        except requests.exceptions.ConnectionError:
            logger.debug("HA not reachable — notification skipped")
        except requests.exceptions.Timeout:
            logger.warning("HA notification timeout — check HA host and token in settings / Controleer HA host en token in instellingen")
        except Exception as e:
            logger.warning(f"HA-notificatie mislukt: {e}")
