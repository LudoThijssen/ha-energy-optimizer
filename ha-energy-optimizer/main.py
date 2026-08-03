# name:          main.py
# part of:       ha-energy-optimizer
# location:      /ha-energy-optimizer/ha-energy-optimizer/main.py
# part version:  p_v0.5
# altered:       2026-07-30
#
# p_v0.5: OffgridMonitor geregistreerd — off-grid uitvaldetectie, zelfde
# ritme als ha_collector. Zie collectors/offgrid_monitor.py,
# decision_engine.py p_v0.12.
#
# Entry point for the HA Energy Optimizer add-on.
# Startpunt voor de HA Energy Optimizer add-on.
#
# Initializes all modules and starts the task scheduler.
# Initialiseert alle modules en start de taakplanner.
#
# p_v0.4: hardcoded 3600s (1 uur) heroptimalisatie-interval vervangen door
# config.optimizer.rerun_interval_seconds (default 900s = 15 min) — zie
# config/config.py p_v0.4. Consistent met de kwartier-schema-tijdstap
# (config.timeslot.SLOT_MINUTES), zodat elk kwartier daadwerkelijk een
# nieuwe beslissing kan krijgen i.p.v. maar 1 op de 4.
#
# p_v0.4: hardcoded 3600s (1 hour) re-optimization interval replaced by
# config.optimizer.rerun_interval_seconds (default 900s = 15 min) — see
# config/config.py p_v0.4. Consistent with the quarter-hour schedule step
# (config.timeslot.SLOT_MINUTES), so every quarter can actually get a fresh
# decision instead of only 1 in 4.

import asyncio
import logging
from config.config import AppConfig
from database.connection import DatabaseConnection
from database.setup import run_migrations
from reporter.reporter import Reporter
from collectors import HaCollector, PriceCollector, WeatherCollector
from collectors.offgrid_monitor import OffgridMonitor
from collectors.profile_updater import ProfileUpdater
from optimizer.engine import OptimizerEngine
from scheduler.scheduler import TaskScheduler

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

def _sync_system_config(db: DatabaseConnection, config: AppConfig) -> None:
    """
    On first start after reinstall, restore system_config from options.json.
    Bij eerste start na herinstallatie, herstel system_config vanuit options.json.
    """
    try:
        with db.cursor() as cur:
            cur.execute("SELECT COUNT(*) AS c FROM system_config")
            if cur.fetchone()["c"] > 0:
                return

            import json as _json
            from pathlib import Path as _Path
            opts_path = _Path("/data/options.json")
            opts = {}
            if opts_path.exists():
                with open(opts_path) as f:
                    opts = _json.load(f)

            sys_opts = opts.get("system", {})
            loc_opts = opts.get("location", {})

            cur.execute("""
                INSERT INTO system_config
                    (latitude, longitude, has_grid_connection,
                     has_solar_panels, has_battery, has_gas,
                     has_district_heating, language,
                     battery_efficiency_pct,
                     hard_min_discharge_price_excl)
                VALUES (%(lat)s, %(lng)s, %(grid)s, %(solar)s,
                        %(battery)s, %(gas)s, %(heating)s,
                        %(lang)s, 83.00, 0.05000)
            """, {
                "lat":     loc_opts.get("latitude",  52.1551),
                "lng":     loc_opts.get("longitude", 5.3872),
                "grid":    1 if sys_opts.get("has_grid_connection", True)  else 0,
                "solar":   1 if sys_opts.get("has_solar_panels",    False) else 0,
                "battery": 1 if sys_opts.get("has_battery",         False) else 0,
                "gas":     1 if sys_opts.get("has_gas",             False) else 0,
                "heating": 1 if sys_opts.get("has_district_heating",False) else 0,
                "lang":    opts.get("language", "nl"),
            })
            logger.info("system_config restored from options.json after reinstall")
    except Exception as e:
        logger.warning(f"Could not sync system_config: {e}")
        
async def main() -> None:
    logger.info("HA Energy Optimizer opstarten...")

    # 1. Configuratie laden en valideren
    config = AppConfig.load()
    logger.info(f"Configuratie geladen — taal: {config.language}")

    # 2. Database initialiseren en migrations uitvoeren
    db = DatabaseConnection(config.database)
    run_migrations(db)
    logger.info("Database klaar")

    # 2b. Sync system_config from options if empty
    # Synchroniseer system_config vanuit options als leeg
    _sync_system_config(db, config)
    
    # 3. Reporter
    reporter = Reporter(db, config)

    # 4. Collectors
    ha_collector      = HaCollector(db, reporter, config)
    price_collector   = PriceCollector(db, reporter, config)
    weather_collector = WeatherCollector(db, reporter, config)
    # p_v0.5: off-grid uitvaldetectie — draait op hetzelfde ritme als
    # ha_collector, los van de 15-minuten optimizer-cyclus (zie
    # collectors/offgrid_monitor.py). Doet niets als
    # system_config.has_offgrid_switch uit staat.
    # p_v0.5: off-grid outage detection — runs on the same cadence as
    # ha_collector, separate from the 15-minute optimizer cycle (see
    # collectors/offgrid_monitor.py). Does nothing if
    # system_config.has_offgrid_switch is off.
    offgrid_monitor   = OffgridMonitor(db, reporter, config)

    # 5. Optimizer
    optimizer = OptimizerEngine(db, reporter, config)

    # 5b. Profile updater
    profile_updater = ProfileUpdater(db)
    
    # 6. Scheduler — alle tijden en intervallen uit config
    scheduler = TaskScheduler(config)

    scheduler.every(config.collectors.ha_interval_seconds,
                    ha_collector.run_safe)
    scheduler.every(config.collectors.ha_interval_seconds,
                    offgrid_monitor.run_safe)
    scheduler.every(config.collectors.weather_interval_seconds,
                    weather_collector.run_safe)

    scheduler.daily(config.collectors.price_fetch_time_today,
                    price_collector.run_safe)
    scheduler.daily(config.collectors.price_fetch_time_tomorrow,
                    price_collector.run_safe)
    scheduler.daily(config.optimizer.run_time,
                    optimizer.run)
    # Rolling re-optimization / Rolling heroptimalisatie
    scheduler.every(config.optimizer.rerun_interval_seconds, optimizer.run)
    # Evening planning: calculate day balance for tomorrow.
    # Avondplanning: bereken dagbalans voor morgen.
    scheduler.daily(config.optimizer.evening_planning_time,
                    optimizer.plan_evening)
    scheduler.daily(config.reporting.daily_report_time,
                    reporter.daily_summary)
    scheduler.daily(config.optimizer.profile_update_time,
                    profile_updater.run)
                    
    reporter.info("Add-on gestart", category="system")
    logger.info("Scheduler gestart — add-on actief")

    await scheduler.run_forever()


if __name__ == "__main__":
    asyncio.run(main())
