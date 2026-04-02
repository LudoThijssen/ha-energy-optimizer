# main.py
#
# Entry point for the HA Energy Optimizer add-on.
# Startpunt voor de HA Energy Optimizer add-on.
#
# Initializes all modules and starts the task scheduler.
# Initialiseert alle modules en start de taakplanner.

import asyncio
import logging
from config.config import AppConfig
from database.connection import DatabaseConnection
from database.setup import run_migrations
from reporter.reporter import Reporter
from collectors import HaCollector, PriceCollector, WeatherCollector
from optimizer.engine import OptimizerEngine
from scheduler.scheduler import TaskScheduler

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


async def main() -> None:
    logger.info("HA Energy Optimizer opstarten...")

    # 1. Configuratie laden en valideren
    config = AppConfig.load()
    logger.info(f"Configuratie geladen — taal: {config.language}")

    # 2. Database initialiseren en migrations uitvoeren
    db = DatabaseConnection(config.database)
    run_migrations(db)
    logger.info("Database klaar")

    # 3. Reporter
    reporter = Reporter(db, config)

    # 4. Collectors
    ha_collector      = HaCollector(db, reporter, config)
    price_collector   = PriceCollector(db, reporter, config)
    weather_collector = WeatherCollector(db, reporter, config)

    # 5. Optimizer
    optimizer = OptimizerEngine(db, reporter, config)

    # 6. Scheduler — alle tijden en intervallen uit config
    scheduler = TaskScheduler(config)

    scheduler.every(config.collectors.ha_interval_seconds,
                    ha_collector.run_safe)
    scheduler.every(config.collectors.weather_interval_seconds,
                    weather_collector.run_safe)

    scheduler.daily(config.collectors.price_fetch_time_today,
                    price_collector.run_safe)
    scheduler.daily(config.collectors.price_fetch_time_tomorrow,
                    price_collector.run_safe)
    scheduler.daily(config.optimizer.run_time,
                    optimizer.run)
    # Evening planning: calculate day balance for tomorrow.
    # Avondplanning: bereken dagbalans voor morgen.
    scheduler.daily(config.optimizer.evening_planning_time,
                    optimizer.plan_evening)
    scheduler.daily(config.reporting.daily_report_time,
                    reporter.daily_summary)

    reporter.info("Add-on gestart", category="system")
    logger.info("Scheduler gestart — add-on actief")

    await scheduler.run_forever()


if __name__ == "__main__":
    asyncio.run(main())
