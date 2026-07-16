--
-- name:          003_strategy_fields.sql
-- part of:       ha-energy-optimizer
-- location:      /ha-energy-optimizer/ha-energy-optimizer/database/migrations/003_strategy_fields.sql
-- part version:  p_v0.4
-- altered:       2026-07-16
--
-- Migration 003: Add fields needed by the new strategy rules.
-- Migratie 003: Voeg velden toe die nodig zijn voor de nieuwe strategieregels.

-- Hard minimum discharge price (excl. VAT) / Harde minimale ontlaadprijs (excl. BTW)
ALTER TABLE system_config
    ADD COLUMN IF NOT EXISTS `hard_min_discharge_price_excl` DECIMAL(8,5) DEFAULT 0.05000;

-- battery_efficiency_pct bestaat al sinds migratie 001 (default 90.00).
-- MODIFY i.p.v. ADD COLUMN IF NOT EXISTS, anders is dit een no-op op een
-- database waar de kolom al bestaat en verandert de default nooit.
-- battery_efficiency_pct already exists since migration 001 (default 90.00).
-- MODIFY instead of ADD COLUMN IF NOT EXISTS, otherwise this is a no-op on
-- a database where the column already exists and the default never changes.
ALTER TABLE system_config
    MODIFY COLUMN `battery_efficiency_pct` DECIMAL(5,2) DEFAULT 75.00;

-- Battery cost and lifecycle for depreciation calculation.
-- Batterijkosten en levensduur voor afschrijvingsberekening.
ALTER TABLE battery_info
    ADD COLUMN IF NOT EXISTS `cost_eur`         DECIMAL(10,2) DEFAULT NULL
        COMMENT 'Purchase price of battery / Aanschafprijs batterij',
    ADD COLUMN IF NOT EXISTS `expected_cycles`  INT           DEFAULT NULL
        COMMENT 'Expected lifetime charge cycles / Verwachte levensduur laadcycli';

-- Example: €3000 battery, 3000 cycles, 10 kWh usable = €0.10/kWh depreciation.
-- Voorbeeld: €3000 batterij, 3000 cycli, 10 kWh bruikbaar = €0,10/kWh afschrijving.
