#
# name:          profile_updater.py
# part of:       ha-energy-optimizer
# location:      /ha-energy-optimizer/ha-energy-optimizer/collectors/profile_updater.py
# part version:  p_v0.4
# altered:       2026-07-22
#
# Nightly profile updater — recalculates historical averages from measured data.
# Nachtelijke profielupdater — herberekent historische gemiddelden uit gemeten data.
#
# Runs daily at 03:00 to update:
# Draait dagelijks om 03:00 om bij te werken:
#   - consumption_profile  — average consumption per weekday/quarter-slot
#   - solar_profile        — average solar output per month/quarter-slot
#   - price_profile        — average prices per month/weekday/quarter-slot
#
# p_v0.4: hour_of_day (0-23) vervangen door slot_of_day (0-95, kwartier-
# resolutie) — zie migratie 015. De GROUP BY-expressie
# HOUR(x)*4 + FLOOR(MINUTE(x)/15) rekent elk tijdstip om naar zijn
# kwartier-slot; dit is de generieke vorm van dezelfde formule als in
# config/timeslot.py (slot_of_day()), maar dan als SQL-expressie omdat dit
# in de database wordt berekend i.p.v. in Python.
#
# p_v0.4: hour_of_day (0-23) replaced by slot_of_day (0-95, quarter-hour
# resolution) — see migration 015. The GROUP BY expression
# HOUR(x)*4 + FLOOR(MINUTE(x)/15) converts each timestamp to its quarter
# slot; this is the SQL-expression equivalent of the same formula in
# config/timeslot.py (slot_of_day()), computed in the database instead of
# in Python here.

import logging
from database.connection import DatabaseConnection

logger = logging.getLogger(__name__)

# SQL-expressie voor het kwartier-slot van een DATETIME-kolom (0..95).
# SQL expression for the quarter slot of a DATETIME column (0..95).
_SLOT_OF_DAY_SQL = "(HOUR({col}) * 4 + FLOOR(MINUTE({col}) / 15))"


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
        Recalculate consumption averages per weekday/quarter-slot.
        Herbereken verbruiksgemiddelden per weekdag/kwartier-slot.
        """
        slot_expr = _SLOT_OF_DAY_SQL.format(col="measured_at")
        with self._db.cursor() as cur:
            cur.execute(f"""
                INSERT INTO consumption_profile
                    (day_of_week, slot_of_day, avg_kw, min_kw, max_kw, samples)
                SELECT
                    WEEKDAY(measured_at)                 AS day_of_week,
                    {slot_expr}                          AS slot_of_day,
                    ROUND(AVG(total_consumption_kw), 3) AS avg_kw,
                    ROUND(MIN(total_consumption_kw), 3) AS min_kw,
                    ROUND(MAX(total_consumption_kw), 3) AS max_kw,
                    COUNT(*)                             AS samples
                FROM home_consumption
                WHERE total_consumption_kw IS NOT NULL
                  AND total_consumption_kw >= 0
                GROUP BY WEEKDAY(measured_at), {slot_expr}
                ON DUPLICATE KEY UPDATE
                    avg_kw  = VALUES(avg_kw),
                    min_kw  = VALUES(min_kw),
                    max_kw  = VALUES(max_kw),
                    samples = VALUES(samples)
            """)
        logger.info("[profile_updater] Consumption profile updated / Verbruiksprofiel bijgewerkt")

    def _update_solar_profile(self) -> None:
        """
        Recalculate solar output averages per month/quarter-slot.
        Herbereken zonne-opbrengstgemiddelden per maand/kwartier-slot.
        """
        slot_expr = _SLOT_OF_DAY_SQL.format(col="measured_at")
        with self._db.cursor() as cur:
            cur.execute(f"""
                INSERT INTO solar_profile
                    (month, slot_of_day, avg_kw, max_kw, samples)
                SELECT
                    MONTH(measured_at)          AS month,
                    {slot_expr}                 AS slot_of_day,
                    ROUND(AVG(power_kw), 3)    AS avg_kw,
                    ROUND(MAX(power_kw), 3)    AS max_kw,
                    COUNT(*)                    AS samples
                FROM solar_production
                WHERE power_kw IS NOT NULL
                GROUP BY MONTH(measured_at), {slot_expr}
                ON DUPLICATE KEY UPDATE
                    avg_kw  = VALUES(avg_kw),
                    max_kw  = VALUES(max_kw),
                    samples = VALUES(samples)
            """)
        logger.info("[profile_updater] Solar profile updated / Zonneprofiel bijgewerkt")

    def _update_price_profile(self) -> None:
        """
        Recalculate price averages per month/weekday/quarter-slot.
        Herbereken prijsgemiddelden per maand/weekdag/kwartier-slot.

        Let op: kon niet bevestigen dat price_profile ergens gelezen wordt
        door de rest van de add-on (engine.py/decision_engine.py gebruiken
        alleen solar_profile/consumption_profile als fallback). Blijft voor
        nu bijgewerkt voor consistentie.
        Note: could not confirm price_profile is read anywhere else in the
        add-on (engine.py/decision_engine.py only use solar_profile/
        consumption_profile as fallback). Kept updated for now for
        consistency.
        """
        slot_expr = _SLOT_OF_DAY_SQL.format(col="price_hour")
        with self._db.cursor() as cur:
            cur.execute(f"""
                INSERT INTO price_profile
                    (month, day_of_week, slot_of_day,
                     avg_price, min_price, max_price, samples)
                SELECT
                    MONTH(price_hour)                AS month,
                    WEEKDAY(price_hour)              AS day_of_week,
                    {slot_expr}                      AS slot_of_day,
                    ROUND(AVG(price_per_kwh), 5)    AS avg_price,
                    ROUND(MIN(price_per_kwh), 5)    AS min_price,
                    ROUND(MAX(price_per_kwh), 5)    AS max_price,
                    COUNT(*)                         AS samples
                FROM energy_prices
                WHERE energy_type = 'electricity'
                GROUP BY MONTH(price_hour), WEEKDAY(price_hour), {slot_expr}
                ON DUPLICATE KEY UPDATE
                    avg_price = VALUES(avg_price),
                    min_price = VALUES(min_price),
                    max_price = VALUES(max_price),
                    samples   = VALUES(samples)
            """)
        logger.info("[profile_updater] Price profile updated / Prijsprofiel bijgewerkt")
# collectors/profile_updater.py
# /ha-energy-optimizer/ha-energy-optimizer/collectors/profile_updater.py
