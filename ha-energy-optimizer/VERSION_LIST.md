# HA Energy Optimizer — Version list
# name:          VERSION_LIST.md
# part of:       ha-energy-optimizer
# location:      /ha-energy-optimizer/VERSION_LIST.md
# part version:  p_v2.8
# altered:       2026-07-23

| Bestand | Pad in repository | Versie | Datum |
| :--- | :--- | :--- | :--- |
| .gitattributes | /.gitattributes | p_v0.1 | 2026-06-26 |
| .gitignore | /.gitignore | p_v0.1 | 2026-06-26 |
| make_VERSIONS_LIST.py | /ha-energy-optimizer/make_VERSIONS_LIST.py | p_v2.8 | 2026-07-23 |
| README.md | /README.md | v0.2.13-alpha | 2026-06-26 |
| repository.yaml | /repository.yaml | p_v0.1 | 2026-06-26 |
# ha-energy-optimizer
| build.yaml | /ha-energy-optimizer/build.yaml | p_v0.3 | 2026-06-21 |
| config.yaml | /ha-energy-optimizer/config.yaml | v0.2.13 | 2026-06-21 |
| Dockerfile | /ha-energy-optimizer/Dockerfile | p_v0.3 | 2026-06-21 |
| main.py | /ha-energy-optimizer/main.py | p_v0.3 | 2026-06-21 |
| requirements.txt | /ha-energy-optimizer/requirements.txt | p_v0.3 | 2026-06-21 |
| uninstall.py | /ha-energy-optimizer/uninstall.py | p_v0.3 | 2026-06-21 |
| VERSION_LIST.md | /ha-energy-optimizer/VERSION_LIST.md | p_v2.8 | 2026-07-23 |
# ha-energy-optimizer/collectors
| __init__.py | /ha-energy-optimizer/collectors/__init__.py | p_v0.3 | 2026-06-21 |
| base.py | /ha-energy-optimizer/collectors/base.py | p_v0.3 | 2026-06-21 |
| consumption_learner.py | /ha-energy-optimizer/collectors/consumption_learner.py | p_v0.6 | 2026-07-22 |
| ha_collector.py | /ha-energy-optimizer/collectors/ha_collector.py | p_v0.5 | 2026-07-05 |
| price_collector.py | /ha-energy-optimizer/collectors/price_collector.py | p_v0.3 | 2026-06-21 |
| profile_updater.py | /ha-energy-optimizer/collectors/profile_updater.py | p_v0.4 | 2026-07-22 |
| solar_learner.py | /ha-energy-optimizer/collectors/solar_learner.py | p_v0.7 | 2026-07-22 |
| weather_collector.py | /ha-energy-optimizer/collectors/weather_collector.py | p_v0.3 | 2026-06-21 |
# ha-energy-optimizer/config
| __init__.py | /ha-energy-optimizer/config/__init__.py | p_v0.3 | 2026-06-21 |
| config.py | /ha-energy-optimizer/config/config.py | p_v0.3 | 2026-06-21 |
| internal_sensors.json | /ha-energy-optimizer/config/internal_sensors.json | p_v0.3 | 2026-06-21 |
| timeslot.py | /ha-energy-optimizer/config/timeslot.py | p_v0.1 | 2026-07-22 |
| validators.py | /ha-energy-optimizer/config/validators.py | p_v0.3 | 2026-06-21 |
# ha-energy-optimizer/database
| __init__.py | /ha-energy-optimizer/database/__init__.py | p_v0.3 | 2026-06-21 |
| connection.py | /ha-energy-optimizer/database/connection.py | p_v0.3 | 2026-06-21 |
| models.py | /ha-energy-optimizer/database/models.py | p_v0.4 | 2026-07-01 |
| repository.py | /ha-energy-optimizer/database/repository.py | p_v0.4 | 2026-07-01 |
| setup.py | /ha-energy-optimizer/database/setup.py | p_v0.6 | 2026-07-16 |
# ha-energy-optimizer/database/migrations
| 000_consolidated.sql | /ha-energy-optimizer/database/migrations/000_consolidated.sql | p_v0.1 | 2026-07-16 |
| 001_initial.sql | /ha-energy-optimizer/database/migrations/001_initial.sql | p_v0.4 | 2026-07-16 |
| 002_add_indexes.sql | /ha-energy-optimizer/database/migrations/002_add_indexes.sql | p_v0.3 | 2026-06-21 |
| 003_strategy_fields.sql | /ha-energy-optimizer/database/migrations/003_strategy_fields.sql | p_v0.4 | 2026-07-16 |
| 004_extended_strategy_fields.sql | /ha-energy-optimizer/database/migrations/004_extended_strategy_fields.sql | p_v0.3 | 2026-06-21 |
| 005_profile_tables.sql | /ha-energy-optimizer/database/migrations/005_profile_tables.sql | p_v0.3 | 2026-06-21 |
| 006_solar_charge_threshold.sql | /ha-energy-optimizer/database/migrations/006_solar_charge_threshold.sql | p_v0.3 | 2026-06-21 |
| 008_dashboard_colors.sql | /ha-energy-optimizer/database/migrations/008_dashboard_colors.sql | p_v0.3 | 2026-06-21 |
| 009_expected_cost.sql | /ha-energy-optimizer/database/migrations/009_expected_cost.sql | p_v0.3 | 2026-06-21 |
| 010_energy_prices_config.sql | /ha-energy-optimizer/database/migrations/010_energy_prices_config.sql | p_v0.3 | 2026-06-21 |
| 011_solar_learning.sql | /ha-energy-optimizer/database/migrations/011_solar_learning.sql | p_v0.4 | 2026-06-26 |
| 012_consumption_learning.sql | /ha-energy-optimizer/database/migrations/012_consumption_learning.sql | p_v0.4 | 2026-06-26 |
| 013_translation_strings.sql | /ha-energy-optimizer/database/migrations/013_translation_strings.sql | p_v0.4 | 2026-07-01 |
| 014_reason_key.sql | /ha-energy-optimizer/database/migrations/014_reason_key.sql | p_v0.4 | 2026-07-01 |
| 015_quarter_hour_slots.sql | /ha-energy-optimizer/database/migrations/015_quarter_hour_slots.sql | p_v0.1 | 2026-07-22 |
| README.md | /ha-energy-optimizer/database/migrations/README.md | p_v2.0 | 2026-07-16 |
# ha-energy-optimizer/gui
| __init__.py | /ha-energy-optimizer/gui/__init__.py | p_v0.3 | 2026-06-21 |
| app.py | /ha-energy-optimizer/gui/app.py | p_v0.16 | 2026-07-05 |
# ha-energy-optimizer/gui/templates
| base.html | /ha-energy-optimizer/gui/templates/base.html | p_v0.5 | 2026-07-05 |
| colors.html | /ha-energy-optimizer/gui/templates/colors.html | p_v0.4 | 2026-06-30 |
| dashboard.html | /ha-energy-optimizer/gui/templates/dashboard.html | p_v1.1 | 2026-07-05 |
| database.html | /ha-energy-optimizer/gui/templates/database.html | p_v0.4 | 2026-06-30 |
| energy_costs.html | /ha-energy-optimizer/gui/templates/energy_costs.html | p_v0.4 | 2026-06-30 |
| entities.html | /ha-energy-optimizer/gui/templates/entities.html | p_v0.4 | 2026-06-30 |
| history.html | /ha-energy-optimizer/gui/templates/history.html | p_v0.3 | 2026-06-21 |
| homeassistant.html | /ha-energy-optimizer/gui/templates/homeassistant.html | p_v0.4 | 2026-06-30 |
| index.html | /ha-energy-optimizer/gui/templates/index.html | p_v0.4 | 2026-06-29 |
| inverter.html | /ha-energy-optimizer/gui/templates/inverter.html | p_v0.2 | 2026-06-30 |
| optimizer.html | /ha-energy-optimizer/gui/templates/optimizer.html | p_v0.13 | 2026-06-29 |
| prices.html | /ha-energy-optimizer/gui/templates/prices.html | p_v0.4 | 2026-06-30 |
| provider.html | /ha-energy-optimizer/gui/templates/provider.html | p_v0.2 | 2026-06-29 |
| reportlog.html | /ha-energy-optimizer/gui/templates/reportlog.html | p_v0.4 | 2026-06-30 |
| schedule.html | /ha-energy-optimizer/gui/templates/schedule.html | p_v0.2 | 2026-06-30 |
| system.html | /ha-energy-optimizer/gui/templates/system.html | p_v0.3 | 2026-07-05 |
| translations.html | /ha-energy-optimizer/gui/templates/translations.html | p_v0.4 | 2026-07-05 |
# ha-energy-optimizer/inverter
| __init__.py | /ha-energy-optimizer/inverter/__init__.py | p_v0.3 | 2026-06-21 |
| base.py | /ha-energy-optimizer/inverter/base.py | p_v0.3 | 2026-06-21 |
| growatt.py | /ha-energy-optimizer/inverter/growatt.py | p_v0.3 | 2026-06-21 |
| modbus.py | /ha-energy-optimizer/inverter/modbus.py | p_v0.3 | 2026-06-21 |
| solaredge.py | /ha-energy-optimizer/inverter/solaredge.py | p_v0.3 | 2026-06-21 |
# ha-energy-optimizer/optimizer
| __init__.py | /ha-energy-optimizer/optimizer/__init__.py | p_v0.3 | 2026-06-21 |
| decision_engine.py | /ha-energy-optimizer/optimizer/decision_engine.py | p_v0.9 | 2026-07-23 |
| engine.py | /ha-energy-optimizer/optimizer/engine.py | p_v0.8 | 2026-07-23 |
| forecast.py | /ha-energy-optimizer/optimizer/forecast.py | p_v0.3 | 2026-06-21 |
| models.py | /ha-energy-optimizer/optimizer/models.py | p_v0.4 | 2026-07-01 |
| strategy.py | /ha-energy-optimizer/optimizer/strategy.py | p_v0.4 | 2026-07-05 |
# ha-energy-optimizer/providers
| __init__.py | /ha-energy-optimizer/providers/__init__.py | p_v0.3 | 2026-06-21 |
| anwb.py | /ha-energy-optimizer/providers/anwb.py | p_v0.3 | 2026-06-21 |
| base.py | /ha-energy-optimizer/providers/base.py | p_v0.3 | 2026-06-21 |
| energyzero.py | /ha-energy-optimizer/providers/energyzero.py | p_v0.3 | 2026-06-21 |
| entsoe.py | /ha-energy-optimizer/providers/entsoe.py | p_v0.3 | 2026-06-21 |
| frank.py | /ha-energy-optimizer/providers/frank.py | p_v0.3 | 2026-06-21 |
| ha_energyzero.py | /ha-energy-optimizer/providers/ha_energyzero.py | p_v0.3 | 2026-06-21 |
| ha_price_sensor.py | /ha-energy-optimizer/providers/ha_price_sensor.py | p_v0.3 | 2026-06-21 |
| tibber.py | /ha-energy-optimizer/providers/tibber.py | p_v0.3 | 2026-06-21 |
# ha-energy-optimizer/reporter
| __init__.py | /ha-energy-optimizer/reporter/__init__.py | p_v0.3 | 2026-06-21 |
| reporter.py | /ha-energy-optimizer/reporter/reporter.py | p_v0.4 | 2026-07-01 |
# ha-energy-optimizer/rootfs/etc/services.d/energy-optimizer
| run | /ha-energy-optimizer/rootfs/etc/services.d/energy-optimizer/run | p_v0.3 | 2026-06-21 |
# ha-energy-optimizer/scheduler
| __init__.py | /ha-energy-optimizer/scheduler/__init__.py | p_v0.3 | 2026-06-21 |
| scheduler.py | /ha-energy-optimizer/scheduler/scheduler.py | p_v0.3 | 2026-06-21 |
# ha-energy-optimizer/translations
| _context.json | /ha-energy-optimizer/translations/_context.json | p_v0.1 | 2026-06-21 |
| de.json | /ha-energy-optimizer/translations/de.json | p_v0.1 | 2026-06-21 |
| en.json | /ha-energy-optimizer/translations/en.json | p_v0.1 | 2026-06-21 |
| es.json | /ha-energy-optimizer/translations/es.json | p_v0.1 | 2026-06-21 |
| fr.json | /ha-energy-optimizer/translations/fr.json | p_v0.1 | 2026-06-21 |
| nl.json | /ha-energy-optimizer/translations/nl.json | p_v0.1 | 2026-06-21 |
| seed_translations.py | /ha-energy-optimizer/translations/seed_translations.py | p_v0.4 | 2026-07-01 |
| translator.py | /ha-energy-optimizer/translations/translator.py | p_v0.4 | 2026-07-01 |
