from datetime import datetime, date
from .connection import DatabaseConnection
from .models import (
    EnergyPrice, BatteryStatus, SolarProduction,
    HomeConsumption, WeatherForecast, OptimizerSlot, ReportEntry,
)


class PriceRepository:
    def __init__(self, db: DatabaseConnection):
        self._db = db

    def save(self, price: EnergyPrice) -> None:
        sql = """
            INSERT INTO energy_prices
                (price_hour, energy_type, price_per_kwh, price_incl_tax, source)
            VALUES (%(price_hour)s, %(energy_type)s, %(price_per_kwh)s,
                    %(price_incl_tax)s, %(source)s)
            ON DUPLICATE KEY UPDATE
                price_per_kwh = VALUES(price_per_kwh),
                source = VALUES(source)
        """
        with self._db.cursor() as cur:
            cur.execute(sql, {
                "price_hour":    price.price_hour,
                "energy_type":   price.energy_type,
                "price_per_kwh": price.price_per_kwh,
                "price_incl_tax": price.price_incl_tax,
                "source":        price.source,
            })

    def get_today(self, energy_type: str = "electricity") -> list[EnergyPrice]:
        with self._db.cursor() as cur:
            cur.execute("""
                SELECT * FROM energy_prices
                WHERE DATE(price_hour) = CURDATE() AND energy_type = %(t)s
                ORDER BY price_hour
            """, {"t": energy_type})
            return [EnergyPrice(**row) for row in cur.fetchall()]

    def get_cheapest_hours(self, target_date: date, n: int = 4,
                           energy_type: str = "electricity") -> list[EnergyPrice]:
        with self._db.cursor() as cur:
            cur.execute("""
                SELECT * FROM energy_prices
                WHERE DATE(price_hour) = %(date)s AND energy_type = %(t)s
                ORDER BY price_per_kwh ASC LIMIT %(n)s
            """, {"date": target_date, "t": energy_type, "n": n})
            return [EnergyPrice(**row) for row in cur.fetchall()]


class BatteryRepository:
    def __init__(self, db: DatabaseConnection):
        self._db = db

    def save(self, status: BatteryStatus) -> None:
        with self._db.cursor() as cur:
            cur.execute("""
                INSERT INTO battery_status
                    (measured_at, soc_pct, power_kw, voltage_v, temperature_c,
                     energy_charged_kwh, energy_discharged_kwh, cycle_count)
                VALUES
                    (%(measured_at)s, %(soc_pct)s, %(power_kw)s, %(voltage_v)s,
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
            cur.execute(
                "SELECT * FROM battery_status ORDER BY measured_at DESC LIMIT 1"
            )
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
            return cur.fetchone()


class SolarRepository:
    def __init__(self, db: DatabaseConnection):
        self._db = db

    def save(self, production: SolarProduction) -> None:
        with self._db.cursor() as cur:
            cur.execute("""
                INSERT INTO solar_production (measured_at, power_kw, energy_kwh)
                VALUES (%(measured_at)s, %(power_kw)s, %(energy_kwh)s)
            """, {
                "measured_at": production.measured_at,
                "power_kw":    production.power_kw,
                "energy_kwh":  production.energy_kwh,
            })

    def get_today_total(self) -> float:
        with self._db.cursor() as cur:
            cur.execute("""
                SELECT COALESCE(SUM(energy_kwh), 0) AS total
                FROM solar_production
                WHERE DATE(measured_at) = CURDATE()
            """)
            return cur.fetchone()["total"]


class HomeConsumptionRepository:
    def __init__(self, db: DatabaseConnection):
        self._db = db

    def save(self, consumption: HomeConsumption) -> None:
        with self._db.cursor() as cur:
            cur.execute("""
                INSERT INTO home_consumption
                    (measured_at, grid_import_kw, grid_export_kw,
                     total_consumption_kw, gas_m3)
                VALUES
                    (%(measured_at)s, %(grid_import_kw)s, %(grid_export_kw)s,
                     %(total_consumption_kw)s, %(gas_m3)s)
            """, {
                "measured_at":        consumption.measured_at,
                "grid_import_kw":     consumption.grid_import_kw,
                "grid_export_kw":     consumption.grid_export_kw,
                "total_consumption_kw": consumption.total_consumption_kw,
                "gas_m3":             consumption.gas_m3,
            })


class WeatherRepository:
    def __init__(self, db: DatabaseConnection):
        self._db = db

    def save(self, forecast: WeatherForecast) -> None:
        with self._db.cursor() as cur:
            cur.execute("""
                INSERT INTO weather_forecast
                    (forecast_for, sunshine_pct, cloud_cover_pct,
                     solar_irradiance_wm2, temperature_c, rain_mm,
                     wind_speed_ms, wind_direction_deg, source)
                VALUES
                    (%(forecast_for)s, %(sunshine_pct)s, %(cloud_cover_pct)s,
                     %(solar_irradiance_wm2)s, %(temperature_c)s, %(rain_mm)s,
                     %(wind_speed_ms)s, %(wind_direction_deg)s, %(source)s)
                ON DUPLICATE KEY UPDATE
                    sunshine_pct        = VALUES(sunshine_pct),
                    cloud_cover_pct     = VALUES(cloud_cover_pct),
                    solar_irradiance_wm2= VALUES(solar_irradiance_wm2),
                    temperature_c       = VALUES(temperature_c),
                    rain_mm             = VALUES(rain_mm),
                    wind_speed_ms       = VALUES(wind_speed_ms),
                    wind_direction_deg  = VALUES(wind_direction_deg),
                    source              = VALUES(source)
            """, {
                "forecast_for":        forecast.forecast_for,
                "sunshine_pct":        forecast.sunshine_pct,
                "cloud_cover_pct":     forecast.cloud_cover_pct,
                "solar_irradiance_wm2":forecast.solar_irradiance_wm2,
                "temperature_c":       forecast.temperature_c,
                "rain_mm":             forecast.rain_mm,
                "wind_speed_ms":       forecast.wind_speed_ms,
                "wind_direction_deg":  forecast.wind_direction_deg,
                "source":              forecast.source,
            })

    def get_forecast(self, from_dt: datetime, hours: int = 24) -> list[WeatherForecast]:
        with self._db.cursor() as cur:
            cur.execute("""
                SELECT * FROM weather_forecast
                WHERE forecast_for >= %(from_dt)s
                ORDER BY forecast_for
                LIMIT %(hours)s
            """, {"from_dt": from_dt, "hours": hours})
            return [WeatherForecast(**row) for row in cur.fetchall()]


class OptimizerRepository:
    def __init__(self, db: DatabaseConnection):
        self._db = db

    def save_schedule(self, slots: list[OptimizerSlot]) -> None:
        with self._db.cursor() as cur:
            cur.execute(
                "DELETE FROM optimizer_schedule WHERE schedule_for >= NOW() AND executed = 0"
            )
            for slot in slots:
                cur.execute("""
                    INSERT INTO optimizer_schedule
                        (schedule_for, action, target_power_kw, target_soc_pct,
                         expected_price, expected_solar_kw, expected_consumption_kw,
                         expected_saving, reason)
                    VALUES
                        (%(schedule_for)s, %(action)s, %(target_power_kw)s,
                         %(target_soc_pct)s, %(expected_price)s, %(expected_solar_kw)s,
                         %(expected_consumption_kw)s, %(expected_saving)s, %(reason)s)
                """, {
                    "schedule_for":           slot.schedule_for,
                    "action":                 slot.action,
                    "target_power_kw":        slot.target_power_kw,
                    "target_soc_pct":         slot.target_soc_pct,
                    "expected_price":         slot.expected_price,
                    "expected_solar_kw":      slot.expected_solar_kw,
                    "expected_consumption_kw":slot.expected_consumption_kw,
                    "expected_saving":        slot.expected_saving,
                    "reason":                 slot.reason,
                })

    def get_current_slot(self) -> OptimizerSlot | None:
        with self._db.cursor() as cur:
            cur.execute("""
                SELECT * FROM optimizer_schedule
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


class ReportRepository:
    def __init__(self, db: DatabaseConnection):
        self._db = db

    def save(self, entry: ReportEntry) -> None:
        with self._db.cursor() as cur:
            cur.execute("""
                INSERT INTO report_log (report_type, category, message)
                VALUES (%(report_type)s, %(category)s, %(message)s)
            """, {
                "report_type": entry.report_type,
                "category":    entry.category,
                "message":     entry.message,
            })

    def get_unnotified(self) -> list[ReportEntry]:
        with self._db.cursor() as cur:
            cur.execute(
                "SELECT * FROM report_log WHERE notified=0 ORDER BY created_at"
            )
            return [ReportEntry(**row) for row in cur.fetchall()]

    def mark_notified(self, ids: list[int]) -> None:
        placeholders = ",".join(str(i) for i in ids)
        with self._db.cursor() as cur:
            cur.execute(
                f"UPDATE report_log SET notified=1, notified_at=NOW() WHERE id IN ({placeholders})"
            )
