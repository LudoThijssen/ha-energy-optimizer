ALTER TABLE energy_prices
    ADD INDEX idx_energy_prices_hour (price_hour),
    ADD INDEX idx_energy_prices_type (energy_type, price_hour);

ALTER TABLE solar_production
    ADD INDEX idx_solar_measured (measured_at);

ALTER TABLE home_consumption
    ADD INDEX idx_consumption_measured (measured_at);

ALTER TABLE battery_status
    ADD INDEX idx_battery_measured (measured_at);

ALTER TABLE weather_forecast
    ADD INDEX idx_weather_forecast (forecast_for);

ALTER TABLE optimizer_schedule
    ADD INDEX idx_optimizer_schedule (schedule_for);

ALTER TABLE report_log
    ADD INDEX idx_report_type (report_type),
    ADD INDEX idx_report_notified (notified, created_at)
