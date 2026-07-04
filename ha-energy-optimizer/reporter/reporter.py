# name:          reporter.py
# part of:       ha-energy-optimizer
# location:      /ha-energy-optimizer/ha-energy-optimizer/reporter/reporter.py
# part version:  p_v0.4
# altered:       2026-07-01

import logging
import requests
from datetime import datetime
from database.connection import DatabaseConnection
from database.models import ReportEntry
from database.repository import ReportRepository, BatteryRepository, SolarRepository, HomeConsumptionRepository
from config.config import AppConfig
from translations.translator import build_translator

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
        self._tr      = build_translator(db)
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
            self._notify(self._tr.get("NT01", {"message": message}))

    def error(self, message: str, category: str | None = None) -> None:
        self._log("error", message, category)
        if self._config.reporting.notify_on_error:
            self._notify(self._tr.get("NT02", {"message": message}), title=self._tr.get("NT03"))

    def daily_summary(self) -> None:
        """Stel een dagrapport samen en stuur het als notificatie."""
        battery     = self._battery.get_today_summary()
        solar       = self._solar.get_today_total()
        consumption = self._consumption.get_today_summary()

        tr = self._tr
        lines = [tr.get("SY01")]

        # Zon
        solar_ok = solar > 0
        key = "SY02" if solar_ok else "SY03"
        lines.append(tr.get(key, {"solar": solar}))

        # Net
        import_kwh  = consumption.get("import_kwh")  or 0
        export_kwh  = consumption.get("export_kwh")  or 0
        verbruik    = consumption.get("verbruik_kwh") or 0

        if import_kwh > 0 or export_kwh > 0:
            lines.append(tr.get("SY04", {"import_kwh": float(import_kwh)}))
            lines.append(tr.get("SY05", {"export_kwh": float(export_kwh)}))
            if verbruik > 0:
                lines.append(tr.get("SY06", {"consumption": float(verbruik)}))
        else:
            lines.append(tr.get("SY07"))

        # Batterij
        if battery and (battery.get("min_soc") is not None):
            lines += [
                tr.get("SY08", {"min_soc": battery["min_soc"] or 0, "max_soc": battery["max_soc"] or 0}),
                tr.get("SY09", {"charged":    battery["total_charged"]    or 0}),
                tr.get("SY10", {"discharged": battery["total_discharged"] or 0}),
            ]

        message = "\n".join(lines)
        self._log("daily", message, category="daily_report")
        self._notify(message, title=tr.get("NT04"))

    def _log(self, report_type: str, message: str, category: str | None) -> None:
        logger.info(f"[{category or report_type}] {message}")
        try:
            self._repo.save(ReportEntry(
                report_type=report_type,
                message=message,
                category=category,
            ))
        except Exception as e:
            logger.error(self._tr.get("ER04", {"error": str(e)}))

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
            logger.warning(self._tr.get("LG06", {"attempt": 1, "max": 1, "error": "timeout"}))
        except Exception as e:
            logger.warning(self._tr.get("ER05", {"error": str(e)}))
