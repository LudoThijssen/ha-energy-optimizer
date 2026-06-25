-- name:          011_solar_learning.sql
-- part of:       ha-energy-optimizer
-- location:      /ha-energy-optimizer/ha-energy-optimizer/database/migrations/011_solar_learning.sql
-- part version:  p_v0.4
-- altered:       2026-06-26
--
-- Leersysteem voor zon-efficiëntie.
-- Slaat de relatie op tussen instraling (W/m²) en werkelijke opbrengst (kWh)
-- per uur van de dag en per blok van 2 weken (26 blokken per jaar).
-- Het systeem leert automatisch wat jouw installatie produceert bij een
-- gegeven instraling — zonder paneeloppervlak of rendement in te voeren.
--
-- Learning system for solar efficiency.
-- Stores the relationship between irradiance (W/m²) and actual yield (kWh)
-- per hour of day and per 2-week block (26 blocks per year).
-- The system automatically learns what your installation produces at a
-- given irradiance — without entering panel area or efficiency.

CREATE TABLE IF NOT EXISTS `solar_learning` (
    `hour_of_day`     TINYINT      NOT NULL COMMENT 'Uur van de dag (0..23) / Hour of day (0..23)',
    `week_block`      TINYINT      NOT NULL COMMENT 'Blok van 2 weken (1..26) / 2-week block (1..26)',
    `irradiance_low`  DECIMAL(8,3) NOT NULL DEFAULT 0 COMMENT 'Laagste gemeten instraling W/m² / Lowest measured irradiance W/m²',
    `irradiance_high` DECIMAL(8,3) NOT NULL DEFAULT 0 COMMENT 'Hoogste gemeten instraling W/m² / Highest measured irradiance W/m²',
    `solar_kwh_low`   DECIMAL(8,4) NOT NULL DEFAULT 0 COMMENT 'Laagste gemeten opbrengst kWh / Lowest measured yield kWh',
    `solar_kwh_high`  DECIMAL(8,4) NOT NULL DEFAULT 0 COMMENT 'Hoogste gemeten opbrengst kWh / Highest measured yield kWh',
    `sample_count`    INT          NOT NULL DEFAULT 0  COMMENT 'Aantal metingen / Number of measurements',
    `updated_at`      DATETIME     DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (`hour_of_day`, `week_block`)
) ENGINE=InnoDB COMMENT='Zon-efficiëntie leermodel / Solar efficiency learning model';
