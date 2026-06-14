-- database/migrations/006_solar_charge_threshold.sql
-- /ha-energy-optimizer/ha-energy-optimizer/database/migrations/006_solar_charge_threshold.sql
-- v0.3.0 — 2026-05-29
--
-- Adds solar_charge_threshold to system_config.
-- This field was read by strategy.py since v0.2.9 but never formally migrated.
-- The GUI optimizer thresholds page already saves/reads this value.
--
-- Voegt solar_charge_threshold toe aan system_config.
-- Dit veld werd al gelezen door strategy.py sinds v0.2.9 maar was nooit formeel gemigreerd.
-- De GUI optimizer-drempelwaardenpagina slaat deze waarde al op en leest hem.

ALTER TABLE system_config
    ADD COLUMN IF NOT EXISTS `solar_charge_threshold` DECIMAL(4,2) NOT NULL DEFAULT 0.80
        COMMENT 'Block grid charging when expected solar >= this fraction of usable capacity. 0.80 = block when solar >= 80% of usable kWh. Blokkeer nettoladen als verwachte zon >= deze fractie van bruikbare capaciteit.';

-- Update existing rows to default value if NULL (should not happen, but safe).
-- Bestaande rijen bijwerken naar standaardwaarde als NULL (zou niet voor moeten komen, maar veilig).
UPDATE system_config
SET solar_charge_threshold = 0.80
WHERE solar_charge_threshold IS NULL;
