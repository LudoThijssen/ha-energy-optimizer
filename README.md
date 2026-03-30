# HA Energy Optimizer

A Home Assistant add-on for smart home battery optimization using solar production forecasts, dynamic energy prices, and household consumption patterns.

## Features

- Collects energy data from Home Assistant sensors
- Fetches dynamic electricity and gas prices from multiple providers
- Retrieves hourly weather and solar irradiance forecasts
- Calculates an optimal 24-hour battery charge/discharge schedule
- Controls the inverter/battery via Modbus or cloud API
- Reports daily summaries and sends notifications to Home Assistant
- Supports multiple languages with AI-powered translation fallback

## Supported inverter protocols

- Modbus TCP/RTU (built-in)
- SolarEdge cloud API (planned)
- Growatt cloud API (planned)
- MQTT (planned)

## Supported energy providers

- ENTSO-E (European day-ahead prices, free)
- Tibber (token required)
- EnergyZero (NL)
- Frank Energie (NL)
- Easily extensible via `providers/base.py`

## Supported weather sources

- Open-Meteo (default, free, no API key required)
- Extensible via `collectors/weather_collector.py`

## Requirements

- Home Assistant with a long-lived access token
- MySQL database (local or on NAS)
- Python 3.11+

## Installation

1. Add this repository to your Home Assistant add-on store
2. Install the **HA Energy Optimizer** add-on
3. Configure via the add-on configuration panel (see Configuration below)
4. Start the add-on

## Configuration

```yaml
database:
  host: "192.168.1.100"
  port: 3306
  name: "energy"
  user: "energy"
  password: "yourpassword"

homeassistant:
  host: "homeassistant.local"
  port: 8123
  token: "your_long_lived_token"

collectors:
  ha_interval_seconds: 300
  weather_interval_seconds: 3600
  price_fetch_time_today: "13:00"
  price_fetch_time_tomorrow: "14:15"
  price_fetch_max_retries: 3
  price_fetch_retry_minutes: 30

optimizer:
  run_time: "14:30"
  rerun_on_price_update: true

reporting:
  daily_report_time: "07:00"
  notify_on_warning: true
  notify_on_error: true

location:
  latitude: 52.1551
  longitude: 5.3872
  timezone: "Europe/Amsterdam"

language: "nl"
```

## Contributing translations

Translations live in `translations/` as JSON files named by ISO 639-1 language code (e.g. `nl.json`, `de.json`).
`en.json` is the master file. To add a new language, copy `en.json`, translate the values, and submit a pull request.

## License

MIT
