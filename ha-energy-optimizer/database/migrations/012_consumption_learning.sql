--
-- name:          012_consumption_learning.sql
-- part of:       ha-energy-optimizer
-- location:      /ha-energy-optimizer/ha-energy-optimizer/database/migrations/012_consumption_learning.sql
-- part version:  p_v0.4
-- altered:       2026-06-26
--
-- Leersysteem voor huisverbruik.
-- Slaat het gemiddelde, minimum en maximum huisverbruik op per combinatie
-- van maand × dag van de week × uur van de dag.
-- Totaal: 12 × 7 × 24 = 2.016 records.
-- Dekt zowel seizoensvariatie als weekpatronen.
--
-- Learning system for household consumption.
-- Stores average, minimum and maximum household consumption per combination
-- of month × day of week × hour of day.
-- Total: 12 × 7 × 24 = 2,016 records.
-- Covers both seasonal variation and weekly patterns.

CREATE TABLE IF NOT EXISTS `consumption_learning` (
    `month_of_year`  TINYINT      NOT NULL COMMENT 'Maand (1..12) / Month (1..12)',
    `day_of_week`    TINYINT      NOT NULL COMMENT 'Dag van de week (0=ma..6=zo) / Day of week (0=Mon..6=Sun)',
    `hour_of_day`    TINYINT      NOT NULL COMMENT 'Uur van de dag (0..23) / Hour of day (0..23)',
    `kwh_avg`        DECIMAL(8,4) NOT NULL DEFAULT 0 COMMENT 'Rollend gewogen gemiddelde kWh / Rolling weighted average kWh',
    `kwh_min`        DECIMAL(8,4) NOT NULL DEFAULT 0 COMMENT 'Laagste gemeten kWh / Lowest measured kWh',
    `kwh_max`        DECIMAL(8,4) NOT NULL DEFAULT 0 COMMENT 'Hoogste gemeten kWh / Highest measured kWh',
    `sample_count`   INT          NOT NULL DEFAULT 0  COMMENT 'Aantal metingen (de deler) / Number of measurements (the divisor)',
    `updated_at`     DATETIME     DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (`month_of_year`, `day_of_week`, `hour_of_day`)
) ENGINE=InnoDB COMMENT='Huisverbruik leermodel / Household consumption learning model';
