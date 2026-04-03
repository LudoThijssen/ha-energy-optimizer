#!/usr/bin/env python3
# apply_fix3.py
#
# Fixes repository.py — replaces SELECT * with explicit field lists
# so that dataclass constructors receive only the fields they expect.
#
# Fix repository.py — vervangt SELECT * door expliciete veldlijsten
# zodat dataklasse-constructors alleen de verwachte velden ontvangen.
#
# Run from the ha-energy-optimizer subfolder:
#   python apply_fix3.py

from pathlib import Path

BASE      = Path(__file__).parent
repo_path = BASE / "database" / "repository.py"

print("Applying Fix 3: repository.py — explicit field lists...")
content = repo_path.read_text(encoding="utf-8")
original = content

# ── Helper ────────────────────────────────────────────────────────────────────
def patch(name, old, new):
    global content
    if old in content:
        content = content.replace(old, new)
        print(f"  [OK]   {name} patched")
    elif new in content:
        print(f"  [SKIP] {name} already patched")
    else:
        print(f"  [WARN] {name} — target text not found, skipping")

# ── 1. WeatherRepository.get_forecast ─────────────────────────────────────────
patch(
    "WeatherRepository.get_forecast",
    '''    def get_forecast(self, from_dt: datetime, hours: int = 24) -> list[WeatherForecast]:
        with self._db.cursor() as cur:
            cur.execute("""
                SELECT * FROM weather_forecast
                WHERE forecast_for >= %(from_dt)s
                ORDER BY forecast_for
                LIMIT %(hours)s
            """, {"from_dt": from_dt, "hours": hours})
            return [WeatherForecast(**row) for row in cur.fetchall()]''',
    '''    def get_forecast(self, from_dt: datetime, hours: int = 24) -> list[WeatherForecast]:
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
            return [WeatherForecast(**row) for row in cur.fetchall()]'''
)

# ── 2. BatteryRepository.get_latest ───────────────────────────────────────────
patch(
    "BatteryRepository.get_latest",
    '''    def get_latest(self) -> BatteryStatus | None:
        with self._db.cursor() as cur:
            cur.execute(
                "SELECT * FROM battery_status ORDER BY measured_at DESC LIMIT 1"
            )
            row = cur.fetchone()
            return BatteryStatus(**row) if row else None''',
    '''    def get_latest(self) -> BatteryStatus | None:
        with self._db.cursor() as cur:
            cur.execute("""
                SELECT id, measured_at, soc_pct, power_kw, voltage_v,
                       temperature_c, energy_charged_kwh,
                       energy_discharged_kwh, cycle_count
                FROM battery_status
                ORDER BY measured_at DESC LIMIT 1
            """)
            row = cur.fetchone()
            return BatteryStatus(**row) if row else None'''
)

# ── 3. OptimizerRepository.get_current_slot ───────────────────────────────────
patch(
    "OptimizerRepository.get_current_slot",
    '''    def get_current_slot(self) -> OptimizerSlot | None:
        with self._db.cursor() as cur:
            cur.execute("""
                SELECT * FROM optimizer_schedule
                WHERE schedule_for <= NOW() AND executed = 0
                ORDER BY schedule_for DESC LIMIT 1
            """)
            row = cur.fetchone()
            return OptimizerSlot(**row) if row else None''',
    '''    def get_current_slot(self) -> OptimizerSlot | None:
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
            return OptimizerSlot(**row) if row else None'''
)

# ── 4. ReportRepository.get_unnotified ────────────────────────────────────────
patch(
    "ReportRepository.get_unnotified",
    '''    def get_unnotified(self) -> list[ReportEntry]:
        with self._db.cursor() as cur:
            cur.execute(
                "SELECT * FROM report_log WHERE notified=0 ORDER BY created_at"
            )
            return [ReportEntry(**row) for row in cur.fetchall()]''',
    '''    def get_unnotified(self) -> list[ReportEntry]:
        with self._db.cursor() as cur:
            cur.execute("""
                SELECT id, report_type, category, message,
                       notified, notified_at
                FROM report_log
                WHERE notified = 0
                ORDER BY created_at
            """)
            return [ReportEntry(**row) for row in cur.fetchall()]'''
)

# ── Write result ───────────────────────────────────────────────────────────────
if content != original:
    repo_path.write_text(content, encoding="utf-8")
    print("\n  repository.py saved / opgeslagen")
else:
    print("\n  No changes needed / Geen wijzigingen nodig")

print("\nFix 3 complete. Run: python test_local.py")
print("Fix 3 voltooid. Voer uit: python test_local.py")
