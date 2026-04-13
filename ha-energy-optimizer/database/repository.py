# database/repository.py — v0.2.5
#
# Repository classes for all database operations.
# Repository-klassen voor alle databasebewerkingen.

from datetime import datetime, date
from decimal import Decimal
from database.connection import DatabaseConnection
from database.models import (
    BatteryStatus, SolarProduction, HomeConsumption,
    WeatherForecast, OptimizerSlot, ReportEntry,
)
import logging

logger = logging.getLogger(__name__)


# ── Battery ──────────────────────────────────────────────────────────────────

class BatteryRepository:

    def __init__(self, db: DatabaseConnection):
        self._db = db

    def save(self, status: BatteryStatus) -> None:
        with self._db.cursor() as cur:
            cur.execute("""
                INSERT INTO battery_status
                    (measured_at, soc_pct, power_kw, voltage_v,
                     temperature_c, energy_charged_kwh,
                     energy_discharged_kwh, cycle_count)
                VALUES (%(measured_at)s, %(soc_pct)s, %(power_kw)s, %(voltage_v)s,
                        %(temperature_c)s, %(energy_charged_kwh)s,
                        %(energy_discharged_kwh)s, %(cycle_count)s)
            """, {
                "measured_at":           status.measured_at,
                "soc_pct":               status.soc_pct,
                "power_kw":              status.power_kw,
                "voltage_v":             status.voltage_v,
                "temperature_c":         status.temperature_c,
                "energy_charged_kwh":    status.energy_charged_kwh,
                "energy_discharged_kwh": status.energy_discharged_kwh,
                "cycle_count":           status.cycle_count,
            })

    def get_latest(self) -> BatteryStatus | None:
        with self._db.cursor() as cur:
            cur.execute("""
                SELECT id, measured_at, soc_pct, power_kw, voltage_v,
                       temperature_c, energy_charged_kwh,
                       energy_discharged_kwh, cycle_count
                FROM battery_status
                ORDER BY measured_at DESC LIMIT 1
            """)
            row = cur.fetchone()
            return BatteryStatus(**row) if row else None

    def get_today_summary(self) -> dict:
        with self._db.cursor() as cur:
            cur.execute("""
                SELECT
                    MIN(soc_pct)               AS min_soc,
                    MAX(soc_pct)               AS max_soc,
                    SUM(energy_charged_kwh)    AS total_charged,
                    SUM(energy_discharged_kwh) AS total_discharged
                FROM battery_status
                WHERE DATE(measured_at) = CURDATE()
            """)
            return cur.fetchone() or {}


# ── Solar ─────────────────────────────────────────────────────────────────────

class SolarRepository:

    def __init__(self, db: DatabaseConnection):
        self._db = db

    def save(self, production: SolarProduction) -> None:
        with self._db.cursor() as cur:
            cur.execute("""
                INSERT INTO solar_production
                    (measured_at, power_kw, energy_kwh, source)
                VALUES (%(measured_at)s, %(power_kw)s,
                        %(energy_kwh)s, %(source)s)
            """, {
                "measured_at":      production.measured_at,
                "power_kw":         production.power_kw,
                "energy_kwh": production.energy_kwh,
                "source":           production.source,
            })

    def get_today_total(self) -> Decimal:
        with self._db.cursor() as cur:
            cur.execute("""
                SELECT COALESCE(MAX(energy_kwh), 0) AS total
                FROM solar_production
                WHERE DATE(measured_at) = CURDATE()
            """)
            row = cur.fetchone()
            return Decimal(str(row["total"])) if row else Decimal("0")


# ── Home consumption ──────────────────────────────────────────────────────────

class HomeConsumptionRepository:

    def __init__(self, db: DatabaseConnection):
        self._db = db

    def save(self, consumption: HomeConsumption) -> None:
        with self._db.cursor() as cur:
            cur.execute("""
                INSERT INTO home_consumption
                    (measured_at, power_kw, grid_import_kw,
                     grid_export_kw, source)
                VALUES (%(measured_at)s, %(power_kw)s, %(grid_import_kw)s,
                        %(grid_export_kw)s, %(source)s)
            """, {
                "measured_at":    consumption.measured_at,
                "power_kw":       consumption.power_kw,
                "grid_import_kw": consumption.grid_import_kw,
                "grid_export_kw": consumption.grid_export_kw,
                "source":         consumption.source,
            })

    def get_average_hourly_kwh(self) -> Decimal:
        """Return average hourly consumption based on last 30 days."""
        with self._db.cursor() as cur:
            cur.execute("""
                SELECT COALESCE(AVG(power_kw), 0.5) AS avg_kw
                FROM home_consumption
                WHERE measured_at >= DATE_SUB(NOW(), INTERVAL 30 DAY)
            """)
            row = cur.fetchone()
            return Decimal(str(row["avg_kw"])) if row else Decimal("0.5")


# ── Energy prices ─────────────────────────────────────────────────────────────

class PriceRepository:

    def __init__(self, db: DatabaseConnection):
        self._db = db

    def save_many(self, prices: list[dict]) -> int:
        """Save a list of hourly prices, skip duplicates."""
        count = 0
        with self._db.cursor() as cur:
            for p in prices:
                cur.execute("""
                    INSERT INTO energy_prices
                        (price_hour, energy_type, price_per_kwh,
                         price_incl_tax, source)
                    VALUES (%(hour)s, %(type)s, %(price)s, %(incl)s, %(source)s)
                    ON DUPLICATE KEY UPDATE
                        price_per_kwh  = VALUES(price_per_kwh),
                        price_incl_tax = VALUES(price_incl_tax),
                        source         = VALUES(source)
                """, {
                    "hour":   p["price_hour"],
                    "type":   p.get("energy_type", "electricity"),
                    "price":  p["price_per_kwh"],
                    "incl":   1 if p.get("price_incl_tax") else 0,
                    "source": p.get("source", "api"),
                })
                count += 1
        return count

    def get_for_date(self, target_date: date) -> list[dict]:
        with self._db.cursor() as cur:
            cur.execute("""
                SELECT price_hour, energy_type, price_per_kwh, price_incl_tax
                FROM energy_prices
                WHERE DATE(price_hour) = %(d)s
                  AND energy_type = 'electricity'
                ORDER BY price_hour
            """, {"d": target_date})
            return cur.fetchall()

    def has_prices_for_date(self, target_date: date) -> bool:
        with self._db.cursor() as cur:
            cur.execute("""
                SELECT COUNT(*) AS c FROM energy_prices
                WHERE DATE(price_hour) = %(d)s AND energy_type = 'electricity'
            """, {"d": target_date})
            return cur.fetchone()["c"] > 0


# ── Weather ───────────────────────────────────────────────────────────────────

class WeatherRepository:

    def __init__(self, db: DatabaseConnection):
        self._db = db

    def save(self, forecast) -> None:
        self.save_many([forecast.__dict__ if hasattr(forecast, "__dict__") else forecast])

    def save_many(self, forecasts: list[dict]) -> None:
        with self._db.cursor() as cur:
            for f in forecasts:
                cur.execute("""
                    INSERT INTO weather_forecast
                        (forecast_for, sun_rise, sun_set,
                         sunshine_pct, cloud_cover_pct, rain_mm,
                         wind_speed_ms, wind_direction_deg,
                         temperature_c, solar_irradiance_wm2, source)
                    VALUES
                        (%(forecast_for)s, %(sun_rise)s, %(sun_set)s,
                         %(sunshine_pct)s, %(cloud_cover_pct)s, %(rain_mm)s,
                         %(wind_speed_ms)s, %(wind_direction_deg)s,
                         %(temperature_c)s, %(solar_irradiance_wm2)s, %(source)s)
                    ON DUPLICATE KEY UPDATE
                        sunshine_pct       = VALUES(sunshine_pct),
                        cloud_cover_pct    = VALUES(cloud_cover_pct),
                        rain_mm            = VALUES(rain_mm),
                        temperature_c      = VALUES(temperature_c),
                        solar_irradiance_wm2 = VALUES(solar_irradiance_wm2),
                        source             = VALUES(source)
                """, f)

    def get_forecast(self, from_dt: datetime, hours: int = 24) -> list[WeatherForecast]:
        with self._db.cursor() as cur:
            cur.execute("""
                SELECT id, forecast_for, sun_rise, sun_set,
                       sunshine_pct, cloud_cover_pct, rain_mm,
                       wind_speed_ms, wind_direction_deg, temperature_c,
                       solar_irradiance_wm2, source
                FROM weather_forecast
                WHERE forecast_for >= %(from_dt)s
                ORDER BY forecast_for
                LIMIT %(hours)s
            """, {"from_dt": from_dt, "hours": hours})
            return [WeatherForecast(**row) for row in cur.fetchall()]

    def get_tomorrow_summary(self) -> dict:
        with self._db.cursor() as cur:
            cur.execute("""
                SELECT
                    AVG(sunshine_pct)        AS avg_sunshine,
                    AVG(solar_irradiance_wm2) AS avg_irradiance,
                    AVG(temperature_c)       AS avg_temp
                FROM weather_forecast
                WHERE DATE(forecast_for) = DATE_ADD(CURDATE(), INTERVAL 1 DAY)
            """)
            return cur.fetchone() or {}


# ── Optimizer schedule ────────────────────────────────────────────────────────

class OptimizerRepository:

    def __init__(self, db: DatabaseConnection):
        self._db = db

    def save_slot(self, slot: OptimizerSlot) -> None:
        with self._db.cursor() as cur:
            cur.execute("""
                INSERT INTO optimizer_schedule
                    (schedule_for, action, target_power_kw, target_soc_pct,
                     expected_price, expected_solar_kw, expected_consumption_kw,
                     expected_saving, reason)
                VALUES
                    (%(schedule_for)s, %(action)s, %(target_power_kw)s,
                     %(target_soc_pct)s, %(expected_price)s, %(expected_solar_kw)s,
                     %(expected_consumption_kw)s, %(expected_saving)s, %(reason)s)
                ON DUPLICATE KEY UPDATE
                    action               = VALUES(action),
                    target_power_kw      = VALUES(target_power_kw),
                    target_soc_pct       = VALUES(target_soc_pct),
                    expected_price       = VALUES(expected_price),
                    expected_solar_kw    = VALUES(expected_solar_kw),
                    expected_consumption_kw = VALUES(expected_consumption_kw),
                    expected_saving      = VALUES(expected_saving),
                    reason               = VALUES(reason),
                    executed             = 0,
                    executed_at          = NULL
            """, {
                "schedule_for":          slot.schedule_for,
                "action":                slot.action,
                "target_power_kw":       slot.target_power_kw,
                "target_soc_pct":        slot.target_soc_pct,
                "expected_price":        slot.expected_price,
                "expected_solar_kw":     slot.expected_solar_kw,
                "expected_consumption_kw": slot.expected_consumption_kw,
                "expected_saving":       slot.expected_saving,
                "reason":                slot.reason,
            })

    def get_current_slot(self) -> OptimizerSlot | None:
        with self._db.cursor() as cur:
            cur.execute("""
                SELECT id, schedule_for, action, target_power_kw,
                       target_soc_pct, expected_price, expected_solar_kw,
                       expected_consumption_kw, expected_saving,
                       reason, executed, executed_at
                FROM optimizer_schedule
                WHERE schedule_for <= NOW() AND executed = 0
                ORDER BY schedule_for DESC LIMIT 1
            """)
            row = cur.fetchone()
            return OptimizerSlot(**row) if row else None

    def mark_executed(self, slot_id: int) -> None:
        with self._db.cursor() as cur:
            cur.execute(
                "UPDATE optimizer_schedule SET executed=1, executed_at=NOW() WHERE id=%(id)s",
                {"id": slot_id}
            )

    def get_schedule_for_date(self, target_date: date) -> list[dict]:
        with self._db.cursor() as cur:
            cur.execute("""
                SELECT schedule_for, action, target_power_kw,
                       expected_saving, reason, executed
                FROM optimizer_schedule
                WHERE DATE(schedule_for) = %(d)s
                ORDER BY schedule_for
            """, {"d": target_date})
            return cur.fetchall()


# ── HA entity map ─────────────────────────────────────────────────────────────

class EntityMapRepository:

    def __init__(self, db: DatabaseConnection):
        self._db = db

    def get_all(self) -> dict[str, str]:
        """Return {internal_name: entity_id} mapping."""
        with self._db.cursor() as cur:
            cur.execute("SELECT internal_name, entity_id FROM ha_entity_map")
            return {row["internal_name"]: row["entity_id"]
                    for row in cur.fetchall()}


# ── Report log ────────────────────────────────────────────────────────────────

class ReportRepository:

    def __init__(self, db: DatabaseConnection):
        self._db = db

    def save(self, entry: ReportEntry) -> None:
        with self._db.cursor() as cur:
            cur.execute("""
                INSERT INTO report_log
                    (report_type, category, message, notified)
                VALUES (%(report_type)s, %(category)s, %(message)s, 0)
            """, {
                "report_type": entry.report_type,
                "category":    entry.category,
                "message":     entry.message,
            })

    def get_unnotified(self) -> list[ReportEntry]:
        with self._db.cursor() as cur:
            cur.execute("""
                SELECT id, report_type, category, message,
                       notified, notified_at
                FROM report_log
                WHERE notified = 0
                ORDER BY created_at
            """)
            return [ReportEntry(**row) for row in cur.fetchall()]

    def mark_notified(self, entry_id: int) -> None:
        with self._db.cursor() as cur:
            cur.execute(
                "UPDATE report_log SET notified=1, notified_at=NOW() WHERE id=%(id)s",
                {"id": entry_id}
            )

