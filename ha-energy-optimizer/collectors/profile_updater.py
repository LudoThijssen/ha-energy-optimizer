# collectors/profile_updater.py
# /ha-energy-optimizer/ha-energy-optimizer/collectors/profile_updater.py
# v0.2.10 — 2026-04-30
#
# Nightly profile updater — recalculates historical averages from measured data.
# Nachtelijke profielupdater — herberekent historische gemiddelden uit gemeten data.
#
# Runs daily at 03:00 to update:
# Draait dagelijks om 03:00 om bij te werken:
#   - consumption_profile  — average consumption per weekday/hour
#   - solar_profile        — average solar output per month/hour
#   - price_profile        — average prices per month/weekday/hour

import logging
from database.connection import DatabaseConnection

logger = logging.getLogger(__name__)


class ProfileUpdater:
    """
    Updates historical profile tables from measured data.
    Werkt historische profieltabellen bij vanuit gemeten data.
    """

    def __init__(self, db: DatabaseConnection):
        self._db = db

    def run(self) -> None:
        """Run all profile updates / Voer alle profielupdates uit."""
        logger.info("[profile_updater] Starting profile update / Profielupdate starten...")
        try:
            self._update_consumption_profile()
            self._update_solar_profile()
            self._update_price_profile()
            logger.info("[profile_updater] Profile update complete / Profielupdate voltooid")
        except Exception as e:
            logger.error(f"[profile_updater] Profile update failed: {e}")
            raise

    def _update_consumption_profile(self) -> None:
        """
        Recalculate consumption averages per weekday/hour.
        Herbereken verbruiksgemiddelden per weekdag/uur.
        """
        with self._db.cursor() as cur:
            cur.execute("""
                INSERT INTO consumption_profile
                    (day_of_week, hour_of_day, avg_kw, min_kw, max_kw, samples)
                SELECT
                    WEEKDAY(measured_at)                 AS day_of_week,
                    HOUR(measured_at)                    AS hour_of_day,
                    ROUND(AVG(total_consumption_kw), 3) AS avg_kw,
                    ROUND(MIN(total_consumption_kw), 3) AS min_kw,
                    ROUND(MAX(total_consumption_kw), 3) AS max_kw,
                    COUNT(*)                             AS samples
                FROM home_consumption
                WHERE total_consumption_kw IS NOT NULL
                  AND total_consumption_kw >= 0
                GROUP BY WEEKDAY(measured_at), HOUR(measured_at)
                ON DUPLICATE KEY UPDATE
                    avg_kw  = VALUES(avg_kw),
                    min_kw  = VALUES(min_kw),
                    max_kw  = VALUES(max_kw),
                    samples = VALUES(samples)
            """)
        logger.info("[profile_updater] Consumption profile updated / Verbruiksprofiel bijgewerkt")

    def _update_solar_profile(self) -> None:
        """
        Recalculate solar output averages per month/hour.
        Herbereken zonne-opbrengstgemiddelden per maand/uur.
        """
        with self._db.cursor() as cur:
            cur.execute("""
                INSERT INTO solar_profile
                    (month, hour_of_day, avg_kw, max_kw, samples)
                SELECT
                    MONTH(measured_at)          AS month,
                    HOUR(measured_at)           AS hour_of_day,
                    ROUND(AVG(power_kw), 3)    AS avg_kw,
                    ROUND(MAX(power_kw), 3)    AS max_kw,
                    COUNT(*)                    AS samples
                FROM solar_production
                WHERE power_kw IS NOT NULL
                GROUP BY MONTH(measured_at), HOUR(measured_at)
                ON DUPLICATE KEY UPDATE
                    avg_kw  = VALUES(avg_kw),
                    max_kw  = VALUES(max_kw),
                    samples = VALUES(samples)
            """)
        logger.info("[profile_updater] Solar profile updated / Zonneprofiel bijgewerkt")

    def _update_price_profile(self) -> None:
        """
        Recalculate price averages per month/weekday/hour.
        Herbereken prijsgemiddelden per maand/weekdag/uur.
        """
        with self._db.cursor() as cur:
            cur.execute("""
                INSERT INTO price_profile
                    (month, day_of_week, hour_of_day,
                     avg_price, min_price, max_price, samples)
                SELECT
                    MONTH(price_hour)                AS month,
                    WEEKDAY(price_hour)              AS day_of_week,
                    HOUR(price_hour)                 AS hour_of_day,
                    ROUND(AVG(price_per_kwh), 5)    AS avg_price,
                    ROUND(MIN(price_per_kwh), 5)    AS min_price,
                    ROUND(MAX(price_per_kwh), 5)    AS max_price,
                    COUNT(*)                         AS samples
                FROM energy_prices
                WHERE energy_type = 'electricity'
                GROUP BY MONTH(price_hour), WEEKDAY(price_hour), HOUR(price_hour)
                ON DUPLICATE KEY UPDATE
                    avg_price = VALUES(avg_price),
                    min_price = VALUES(min_price),
                    max_price = VALUES(max_price),
                    samples   = VALUES(samples)
            """)
        logger.info("[profile_updater] Price profile updated / Prijsprofiel bijgewerkt")
