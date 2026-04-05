import logging
import requests
from datetime import datetime
from database.connection import DatabaseConnection
from database.models import ReportEntry
from database.repository import ReportRepository, BatteryRepository, SolarRepository
from config.config import AppConfig

logger = logging.getLogger(__name__)


class Reporter:
    """
    Centrale logger en notificatie-module.
    Schrijft naar de database en stuurt berichten naar Home Assistant.
    """

    def __init__(self, db: DatabaseConnection, config: AppConfig):
        self._repo    = ReportRepository(db)
        self._battery = BatteryRepository(db)
        self._solar   = SolarRepository(db)
        self._config  = config
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
        battery  = self._battery.get_today_summary()
        solar    = self._solar.get_today_total()

        lines = [
            "Dagrapport energie-optimizer",
            f"Zonopbrengst vandaag:  {solar:.2f} kWh",
        ]

        if battery:
            lines += [
                f"Batterij min/max SoC:  {battery['min_soc']:.0f}% / {battery['max_soc']:.0f}%",
                f"Totaal opgeladen:      {(battery['total_charged'] or 0):.2f} kWh",
                f"Totaal ontladen:       {(battery['total_discharged'] or 0):.2f} kWh",
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
            requests.post(
                f"{self._ha_url}/api/services/notify/notify",
                json={"title": title, "message": message},
                headers=self._headers,
                timeout=5,
            )
        except Exception as e:
            logger.warning(f"HA-notificatie mislukt: {e}")
