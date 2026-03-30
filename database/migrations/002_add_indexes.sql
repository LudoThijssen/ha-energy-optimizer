CREATE INDEX IF NOT EXISTS idx_energy_prices_hour     ON energy_prices    (price_hour);
CREATE INDEX IF NOT EXISTS idx_energy_prices_type     ON energy_prices    (energy_type, price_hour);
CREATE INDEX IF NOT EXISTS idx_solar_measured         ON solar_production (measured_at);
CREATE INDEX IF NOT EXISTS idx_consumption_measured   ON home_consumption (measured_at);
CREATE INDEX IF NOT EXISTS idx_battery_measured       ON battery_status   (measured_at);
CREATE INDEX IF NOT EXISTS idx_weather_forecast       ON weather_forecast (forecast_for);
CREATE INDEX IF NOT EXISTS idx_optimizer_schedule     ON optimizer_schedule (schedule_for);
CREATE INDEX IF NOT EXISTS idx_report_type            ON report_log       (report_type);
CREATE INDEX IF NOT EXISTS idx_report_notified        ON report_log       (notified, created_at);
