# test_local.py
#
# Local development test script for Windows.
# Lokaal ontwikkelingstestscript voor Windows.
#
# Run with venv active / Uitvoeren met actieve venv:
#   cd C:\Users\Ludo\Documents\ha-energy-optimizer\ha-energy-optimizer
#   venv\Scripts\activate
#   python test_local.py

import sys
from pathlib import Path
from decimal import Decimal
from datetime import datetime, date, timedelta

# Patch options.json path before any imports
import config.config as _cfg
_cfg.OPTIONS_PATH = Path(__file__).parent / "options.json"

def ok(msg):   print(f"  [OK]   {msg}")
def warn(msg): print(f"  [WARN] {msg}")
def fail(msg): print(f"  [FAIL] {msg}"); sys.exit(1)
def header(t): print(f"\n{'='*60}\n  {t}\n{'='*60}")

# ── Test 1: Config ────────────────────────────────────────────
header("Test 1 — Configuration / Configuratie")
try:
    from config.config import AppConfig
    config = AppConfig.load()
    ok(f"Config loaded — db: {config.database.host}:{config.database.port}/{config.database.name}")
    ok(f"Language: {config.language} | Location: {config.location.latitude}, {config.location.longitude}")
except Exception as e:
    fail(f"Config load failed: {e}")

# ── Test 2: Database connection ───────────────────────────────
header("Test 2 — Database connection / Databaseverbinding")
try:
    from database.connection import DatabaseConnection
    db = DatabaseConnection(config.database)
    with db.cursor() as cur:
        cur.execute("SELECT 1 AS test")
        assert cur.fetchone()["test"] == 1
    ok("Connection successful / Verbinding geslaagd")
except Exception as e:
    fail(f"Connection failed: {e}")

# ── Test 3: Migrations ────────────────────────────────────────
header("Test 3 — Database migrations / Databasemigraties")
try:
    from database.setup import run_migrations
    run_migrations(db)
    ok("Migrations applied / Migraties toegepast")

    with db.cursor() as cur:
        cur.execute("SHOW TABLES")
        tables = [list(r.values())[0] for r in cur.fetchall()]

    required = [
        "system_config", "battery_info", "energy_prices", "battery_status",
        "solar_production", "home_consumption", "weather_forecast",
        "optimizer_schedule", "report_log",
    ]
    missing = [t for t in required if t not in tables]
    if missing:
        fail(f"Missing tables: {missing}")
    ok(f"All {len(required)} required tables present / aanwezig")
    print(f"  All tables: {', '.join(sorted(tables))}")
except Exception as e:
    fail(f"Migration failed: {e}")

# ── Test 4: Test data ─────────────────────────────────────────
header("Test 4 — Test data / Testdata invoegen")
try:
    today    = date.today()
    tomorrow = today + timedelta(days=1)

    with db.cursor() as cur:
        cur.execute("DELETE FROM system_config")
        cur.execute("""
            INSERT INTO system_config (
                latitude, longitude, has_solar_panels, has_battery,
                battery_efficiency_pct, hard_min_discharge_price_excl,
                min_spread_ratio_for_discharge, extreme_price_multiplier,
                negative_export_threshold_excl, notify_export_threshold_excl,
                avg_consumption_kwh, price_incl_tax, language
            ) VALUES (52.1551, 5.3872, 1, 1, 75.00, 0.05, 2.00, 2.50, 0.00, 0.02, 0.5, 1, 'nl')
        """)
    ok("System config inserted")

    with db.cursor() as cur:
        cur.execute("DELETE FROM battery_info")
        cur.execute("""
            INSERT INTO battery_info (
                brand, model, capacity_kwh, usable_capacity_kwh,
                max_charge_kw, max_discharge_kw,
                working_charge_kw, working_discharge_kw,
                min_soc_pct, max_soc_pct
            ) VALUES ('Test','TestBat 10kWh',10.0,9.5,3.68,3.68,2.5,2.5,10.0,95.0)
        """)
    ok("Battery info inserted")

    with db.cursor() as cur:
        cur.execute("DELETE FROM provider_config")
        cur.execute("""
            INSERT INTO provider_config (energy_type, provider_driver, driver_config, is_active)
            VALUES ('electricity','anwb','{"vat_pct":21.0,"incl_tax":false}',1)
        """)
    ok("Provider config inserted")

    # 24 hourly prices (excl. VAT × 1.21 stored incl. VAT)
    prices_excl = [
        0.0821,0.0756,0.0698,0.0634,0.0589,0.0612,0.0834,0.1123,
        0.1456,0.1678,0.1534,0.1289,0.1098,0.0934,0.0878,0.0956,
        0.1234,0.1789,0.2134,0.2456,0.2123,0.1678,0.1234,0.0934,
    ]
    with db.cursor() as cur:
        cur.execute("DELETE FROM energy_prices WHERE DATE(price_hour) = %s", (today,))
        for h, p in enumerate(prices_excl):
            cur.execute("""
                INSERT INTO energy_prices (price_hour, energy_type, price_per_kwh, price_incl_tax, source)
                VALUES (%s, 'electricity', %s, 1, 'test')
            """, (datetime(today.year, today.month, today.day, h), round(p * 1.21, 5)))
    ok(f"24 hourly prices inserted (min {min(prices_excl):.4f}, max {max(prices_excl):.4f} €/kWh excl.)")

    # Weather for today + tomorrow
    with db.cursor() as cur:
        cur.execute("DELETE FROM weather_forecast WHERE DATE(forecast_for) IN (%s,%s)", (today,tomorrow))
        for offset, sun, irr in [(0, 65.0, 450.0), (1, 72.0, 520.0)]:
            target = today + timedelta(days=offset)
            for h in range(6, 20):
                dt   = datetime(target.year, target.month, target.day, h)
                peak = max(0, irr * (1 - abs(h - 13) / 10))
                cur.execute("""
                    INSERT INTO weather_forecast
                        (forecast_for, sunshine_pct, cloud_cover_pct, solar_irradiance_wm2, temperature_c, source)
                    VALUES (%s,%s,%s,%s,%s,'test')
                    ON DUPLICATE KEY UPDATE sunshine_pct=VALUES(sunshine_pct), solar_irradiance_wm2=VALUES(solar_irradiance_wm2)
                """, (dt, sun, 100-sun, peak, 18.5))
    ok("Weather forecast inserted for today + tomorrow")

    with db.cursor() as cur:
        cur.execute("INSERT INTO battery_status (measured_at, soc_pct, power_kw, temperature_c) VALUES (NOW(),65.0,0.0,22.5)")
    ok("Battery status inserted (SoC 65%, temp 22.5°C)")

except Exception as e:
    fail(f"Test data failed: {e}")

# ── Test 5: Strategy logic ────────────────────────────────────
header("Test 5 — Strategy logic / Strategielogica")
try:
    from optimizer.strategy import Strategy, DayPriceStats, SolarOutlook

    s = Strategy(
        battery_efficiency_pct=Decimal("75"),
        hard_min_discharge_price_excl=Decimal("0.05"),
        min_soc_pct=Decimal("10"), max_soc_pct=Decimal("95"),
        max_charge_kw=Decimal("3.68"), max_discharge_kw=Decimal("3.68"),
        working_charge_kw=Decimal("2.5"), working_discharge_kw=Decimal("2.5"),
        price_incl_tax=False, vat_pct=Decimal("21.0"),
    )
    ds = DayPriceStats(
        cheapest_today=Decimal("0.0589"), most_expensive_today=Decimal("0.2456"),
        average_today=Decimal("0.1234"), hours_ranked=[],
        price_incl_tax=False, vat_multiplier=Decimal("1.21"),
    )
    sol = SolarOutlook(sunshine_pct=Decimal("72"), estimated_yield_kwh=Decimal("18.5"))

    def decide(price, solar=Decimal("0"), soc=Decimal("60"), export=None):
        return s.decide(price, export or price, solar, Decimal("0.5"), soc, ds, None, sol)

    a,pw,_,notifs = decide(Decimal("0.10"), solar=Decimal("3.0"))
    assert a == "charge";  ok(f"A: Solar surplus → charge {pw:.2f} kW ✓")

    a,pw,_,_ = decide(Decimal("0.2456"), soc=Decimal("80"))
    assert a == "discharge"; ok(f"B: High price → discharge {pw:.2f} kW ✓")

    a,pw,_,_ = decide(Decimal("0.0589"), soc=Decimal("30"))
    assert a == "charge";  ok(f"C: Low price → charge from grid {pw:.2f} kW ✓")

    a,_,_,_ = decide(Decimal("0.03"), soc=Decimal("80"))
    assert a != "discharge"; ok(f"D: Price < 5ct → no discharge (action={a}) ✓")

    a,_,_,notifs = decide(Decimal("-0.02"), solar=Decimal("4.0"), soc=Decimal("95"))
    assert len(notifs) > 0; ok(f"E: Negative price → notification ✓")
    print(f"     → {notifs[0][:80]}...")

    assert abs(s.required_spread_factor - Decimal("1.333")) < Decimal("0.001")
    ok(f"F: Spread factor at 75% efficiency = {s.required_spread_factor}× ✓")

    n = s._effective_power(Decimal("30"))
    h = s._effective_power(Decimal("40"))
    assert h.charge_kw < n.charge_kw and h.derated
    ok(f"G: Temp derating: {n.charge_kw:.2f} kW → {h.charge_kw:.2f} kW at 40°C ✓")

except AssertionError as e:
    fail(f"Strategy assertion: {e}")
except Exception as e:
    fail(f"Strategy error: {e}")

# ── Test 6: Optimizer engine ──────────────────────────────────
header("Test 6 — Optimizer engine dry run")
try:
    from reporter.reporter import Reporter
    from optimizer.engine import OptimizerEngine

    reporter = Reporter(db, config)
    engine   = OptimizerEngine(db, reporter, config)
    engine.run()
    ok("Optimizer run completed")

    with db.cursor() as cur:
        cur.execute("SELECT COUNT(*) AS c FROM optimizer_schedule")
        count = cur.fetchone()["c"]
    if count == 0:
        fail("No schedule slots written")
    ok(f"Schedule: {count} slots written")

    with db.cursor() as cur:
        cur.execute("SELECT schedule_for, action, target_power_kw, expected_saving FROM optimizer_schedule ORDER BY schedule_for")
        rows = cur.fetchall()

    print(f"\n  {'Hour':<6} {'Action':<16} {'kW':<8} {'Saving €'}")
    print(f"  {'-'*42}")
    for r in rows:
        print(f"  {r['schedule_for'].strftime('%H:%M'):<6} {r['action']:<16} "
              f"{(r['target_power_kw'] or 0):<8.2f} {(r['expected_saving'] or 0):.4f}")

except Exception as e:
    fail(f"Optimizer engine error: {e}")

# ── Test 7: Weather collector ─────────────────────────────────
header("Test 7 — Weather collector (live Open-Meteo)")
try:
    from reporter.reporter import Reporter
    from collectors.weather_collector import WeatherCollector

    col = WeatherCollector(db, Reporter(db, config), config)
    if col.run_safe():
        with db.cursor() as cur:
            cur.execute("SELECT COUNT(*) AS c FROM weather_forecast WHERE source='open-meteo'")
        ok(f"Live weather fetched and stored")
    else:
        warn("Weather collector returned False — check internet connection")
except Exception as e:
    warn(f"Weather test skipped: {e}")

# ── Done ──────────────────────────────────────────────────────
print(f"\n{'='*60}")
print("  All tests passed! / Alle tests geslaagd!")
print(f"{'='*60}\n")
