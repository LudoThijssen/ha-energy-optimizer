-- insert_simulate_inverter.sql
--
-- Run this in phpMyAdmin to configure the simulate driver for testing.
-- Voer dit uit in phpMyAdmin om de simulatiediver in te stellen voor testen.
--
-- After testing with real hardware, update driver to 'modbus' and
-- fill in host, port and slave_id in driver_config.
-- Na testen met echte hardware, zet driver op 'modbus' en vul
-- host, port en slave_id in in driver_config.

DELETE FROM inverter_info;

INSERT INTO inverter_info (
    brand, model, driver, driver_config,
    max_charge_kw, max_discharge_kw
) VALUES (
    'Simulated', 'Test Battery 10kWh',
    'simulate',
    '{"initial_soc_pct": 65.0, "capacity_kwh": 10.0, "temperature_c": 22.0}',
    3.68, 3.68
);
