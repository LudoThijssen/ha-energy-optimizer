-- database/migrations/010_energy_prices_config.sql
-- /ha-energy-optimizer/ha-energy-optimizer/database/migrations/010_energy_prices_config.sql
-- v0.2.13 — 2026-06-16
--
-- Adds fixed price columns for gas and district heating to system_config.
-- These are used in the Energy Costs overview to calculate actual costs.
-- Later extensible to HA sensor-based dynamic pricing.
--
-- Voegt vaste prijskolommen toe voor gas en stadsverwarming aan system_config.
-- Worden gebruikt in het Energie Kosten-overzicht voor kostenberekening.
-- Later uit te breiden met HA-sensor-gebaseerde dynamische prijzen.

ALTER TABLE system_config
    ADD COLUMN IF NOT EXISTS `gas_price_eur_m3` DECIMAL(8,5) DEFAULT NULL
        COMMENT 'Fixed gas price in €/m³ incl. VAT / Vaste gasprijs in €/m³ incl. BTW',

    ADD COLUMN IF NOT EXISTS `gas_price_entity_id` VARCHAR(256) DEFAULT NULL
        COMMENT 'Optional HA entity for dynamic gas price / Optionele HA-entiteit voor dynamische gasprijs',

    ADD COLUMN IF NOT EXISTS `heating_price_eur_gj` DECIMAL(8,5) DEFAULT NULL
        COMMENT 'Fixed district heating price in €/GJ incl. VAT / Vaste stadsverwarmingprijs in €/GJ incl. BTW',

    ADD COLUMN IF NOT EXISTS `heating_price_entity_id` VARCHAR(256) DEFAULT NULL
        COMMENT 'Optional HA entity for dynamic heating price / Optionele HA-entiteit voor dynamische stadsverwarmingprijs';
