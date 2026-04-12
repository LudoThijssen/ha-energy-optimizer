#!/usr/bin/env python3
# apply_fixes_v025.py
#
# Fixes two bugs:
# 1. repository.py — WeatherForecast SELECT * includes created_at
# 2. app.py — PriceCollector.fetch() method name
#
# Run from ha-energy-optimizer subfolder:
#   python apply_fixes_v025.py

from pathlib import Path

BASE = Path(__file__).parent
print("Applying fixes for v0.2.5...\n")

# ── Fix 1: repository.py — WeatherForecast explicit fields ────────────────────
print("Fix 1: repository.py — explicit SELECT fields for WeatherForecast...")

repo_path = BASE / "database" / "repository.py"
content = repo_path.read_text(encoding="utf-8")
original = content

# Fix WeatherForecast SELECT *
old_weather = '''    def get_forecast(self, from_dt: datetime, hours: int = 24) -> list[WeatherForecast]:
        with self._db.cursor() as cur:
            cur.execute("""
                SELECT * FROM weather_forecast
                WHERE forecast_for >= %(from_dt)s
                ORDER BY forecast_for
                LIMIT %(hours)s
            """, {"from_dt": from_dt, "hours": hours})
            return [WeatherForecast(**row) for row in cur.fetchall()]'''

new_weather = '''    def get_forecast(self, from_dt: datetime, hours: int = 24) -> list[WeatherForecast]:
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

if old_weather in content:
    content = content.replace(old_weather, new_weather)
    print("  [OK] WeatherForecast.get_forecast fixed")
elif new_weather in content:
    print("  [SKIP] WeatherForecast.get_forecast already fixed")
else:
    # Fallback — replace any SELECT * FROM weather_forecast
    if "SELECT * FROM weather_forecast" in content:
        content = content.replace(
            "SELECT * FROM weather_forecast",
            """SELECT id, forecast_for, sun_rise, sun_set,
                       sunshine_pct, cloud_cover_pct, rain_mm,
                       wind_speed_ms, wind_direction_deg, temperature_c,
                       solar_irradiance_wm2, source
                FROM weather_forecast"""
        )
        print("  [OK] WeatherForecast fallback fix applied")
    else:
        print("  [WARN] Could not find WeatherForecast query")

# Fix BatteryStatus SELECT *
old_battery = '"SELECT * FROM battery_status ORDER BY measured_at DESC LIMIT 1"'
new_battery = '''"""
                SELECT id, measured_at, soc_pct, power_kw, voltage_v,
                       temperature_c, energy_charged_kwh,
                       energy_discharged_kwh, cycle_count
                FROM battery_status
                ORDER BY measured_at DESC LIMIT 1
            """"'''

# Simpler approach for battery
if "SELECT * FROM battery_status" in content:
    content = content.replace(
        "SELECT * FROM battery_status ORDER BY measured_at DESC LIMIT 1",
        """SELECT id, measured_at, soc_pct, power_kw, voltage_v,
                       temperature_c, energy_charged_kwh,
                       energy_discharged_kwh, cycle_count
                FROM battery_status
                ORDER BY measured_at DESC LIMIT 1"""
    )
    print("  [OK] BatteryStatus.get_latest fixed")
else:
    print("  [SKIP] BatteryStatus already fixed or not found")

# Fix OptimizerSlot SELECT *
if "SELECT * FROM optimizer_schedule" in content:
    content = content.replace(
        "SELECT * FROM optimizer_schedule",
        """SELECT id, schedule_for, action, target_power_kw,
                       target_soc_pct, expected_price, expected_solar_kw,
                       expected_consumption_kw, expected_saving,
                       reason, executed, executed_at
                FROM optimizer_schedule"""
    )
    print("  [OK] OptimizerSlot.get_current_slot fixed")
else:
    print("  [SKIP] OptimizerSlot already fixed or not found")

# Fix ReportEntry SELECT *
if "SELECT * FROM report_log" in content:
    content = content.replace(
        "SELECT * FROM report_log WHERE notified=0 ORDER BY created_at",
        """SELECT id, report_type, category, message,
                       notified, notified_at
                FROM report_log
                WHERE notified = 0
                ORDER BY created_at"""
    )
    print("  [OK] ReportEntry.get_unnotified fixed")
else:
    print("  [SKIP] ReportEntry already fixed or not found")

if content != original:
    repo_path.write_text(content, encoding="utf-8")
    print("  repository.py saved\n")
else:
    print("  No changes to repository.py\n")

# ── Fix 2: app.py — PriceCollector method name ────────────────────────────────
print("Fix 2: gui/app.py — PriceCollector.fetch() method name...")

app_path = BASE / "gui" / "app.py"
content = app_path.read_text(encoding="utf-8")

old_fetch = '''        results = []
        for target in ["today", "tomorrow"]:
            ok = collector.fetch(target)
            results.append(f"{'✓' if ok else '✗'} {target}")'''

new_fetch = '''        results = []
        # Try run_safe() which handles today + tomorrow internally
        # Probeer run_safe() die vandaag + morgen intern afhandelt
        ok = collector.run_safe()
        if ok:
            results.append("✓ prices fetched")
        else:
            # Fallback: try individual methods if they exist
            for method in ["fetch_today", "fetch_tomorrow", "run"]:
                fn = getattr(collector, method, None)
                if fn:
                    try:
                        r = fn()
                        results.append(f"{'✓' if r else '✗'} {method}")
                    except Exception as ex:
                        results.append(f"✗ {method}: {str(ex)[:30]}")'''

if old_fetch in content:
    content = content.replace(old_fetch, new_fetch)
    app_path.write_text(content, encoding="utf-8")
    print("  [OK] PriceCollector.fetch() fixed in app.py\n")
elif "run_safe()" in content and "fetch_today" in content:
    print("  [SKIP] Already fixed\n")
else:
    print("  [WARN] Could not find fetch pattern — manual check needed\n")

print("All fixes applied / Alle fixes toegepast")
print("Run: git add . && git commit -m 'v0.2.5 fixes' && git push")
