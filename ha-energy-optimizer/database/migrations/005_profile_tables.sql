-- database/migrations/005_profile_tables.sql
-- /ha-energy-optimizer/ha-energy-optimizer/database/migrations/005_profile_tables.sql
-- v0.2.9 — 2026-04-24
--
-- Historical profile tables for consumption, solar and price predictions.
-- Historische profieltabellen voor verbruik-, zon- en prijsvoorspellingen.
--
-- These tables are populated automatically by the profile_updater scheduler task.
-- Deze tabellen worden automatisch gevuld door de profile_updater scheduler-taak.
-- After a few weeks of data, the optimizer uses these for better hourly predictions.
-- Na enkele weken data gebruikt de optimizer deze voor betere uurvoorspellingen.

CREATE TABLE IF NOT EXISTS `consumption_profile` (
    `id`           INT          NOT NULL AUTO_INCREMENT,
    `updated_at`   DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP
                                ON UPDATE CURRENT_TIMESTAMP,
    `day_of_week`  TINYINT      NOT NULL COMMENT '0=Monday/maandag, 6=Sunday/zondag',
    `hour_of_day`  TINYINT      NOT NULL COMMENT '0-23 local time / lokale tijd',
    `avg_kw`       DECIMAL(6,3) NOT NULL DEFAULT 0.000
                                COMMENT 'Average consumption kW / Gemiddeld verbruik kW',
    `min_kw`       DECIMAL(6,3) NOT NULL DEFAULT 0.000,
    `max_kw`       DECIMAL(6,3) NOT NULL DEFAULT 0.000,
    `samples`      INT          NOT NULL DEFAULT 0
                                COMMENT 'Number of measurements / Aantal metingen',
    PRIMARY KEY (`id`),
    UNIQUE KEY `unique_day_hour` (`day_of_week`, `hour_of_day`)
) ENGINE=InnoDB
  COMMENT='Average energy consumption per weekday/hour / Gemiddeld verbruik per weekdag/uur';

CREATE TABLE IF NOT EXISTS `solar_profile` (
    `id`               INT          NOT NULL AUTO_INCREMENT,
    `updated_at`       DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP
                                    ON UPDATE CURRENT_TIMESTAMP,
    `month`            TINYINT      NOT NULL COMMENT '1=January/januari, 12=December/december',
    `hour_of_day`      TINYINT      NOT NULL COMMENT '0-23 local time / lokale tijd',
    `avg_kw`           DECIMAL(6,3) NOT NULL DEFAULT 0.000
                                    COMMENT 'Average solar output kW / Gemiddelde zonne-opbrengst kW',
    `max_kw`           DECIMAL(6,3) NOT NULL DEFAULT 0.000,
    `avg_sunshine_pct` DECIMAL(5,2)          DEFAULT NULL
                                    COMMENT 'Average sunshine percentage / Gemiddeld zonpercentage',
    `samples`          INT          NOT NULL DEFAULT 0,
    PRIMARY KEY (`id`),
    UNIQUE KEY `unique_month_hour` (`month`, `hour_of_day`)
) ENGINE=InnoDB
  COMMENT='Expected solar output per month/hour / Verwachte zonne-opbrengst per maand/uur';

CREATE TABLE IF NOT EXISTS `price_profile` (
    `id`           INT           NOT NULL AUTO_INCREMENT,
    `updated_at`   DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP
                                 ON UPDATE CURRENT_TIMESTAMP,
    `month`        TINYINT       NOT NULL COMMENT '1=January, 12=December',
    `day_of_week`  TINYINT       NOT NULL COMMENT '0=Monday, 6=Sunday',
    `hour_of_day`  TINYINT       NOT NULL COMMENT '0-23 local time',
    `avg_price`    DECIMAL(8,5)  NOT NULL DEFAULT 0.00000
                                 COMMENT 'Average price €/kWh / Gemiddelde prijs €/kWh',
    `min_price`    DECIMAL(8,5)  NOT NULL DEFAULT 0.00000,
    `max_price`    DECIMAL(8,5)  NOT NULL DEFAULT 0.00000,
    `samples`      INT           NOT NULL DEFAULT 0,
    PRIMARY KEY (`id`),
    UNIQUE KEY `unique_month_dow_hour` (`month`, `day_of_week`, `hour_of_day`)
) ENGINE=InnoDB
  COMMENT='Average price patterns per month/weekday/hour / Gemiddelde prijspatronen per maand/weekdag/uur';