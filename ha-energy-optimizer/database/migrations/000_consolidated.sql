--
-- name:          000_consolidated.sql
-- part of:       ha-energy-optimizer
-- location:      /ha-energy-optimizer/ha-energy-optimizer/database/migrations/000_consolidated.sql
-- part version:  p_v0.1
-- altered:       2026-07-16
--
-- Volledig eindschema (resultaat van migraties 001 t/m 014) in één keer.
-- Wordt UITSLUITEND gebruikt door setup.py bij een verse installatie
-- (lege database, geen _migrations tabel). Bestaande installaties blijven
-- de incrementele migraties 001-014 doorlopen zoals voorheen.
--
-- Full end-state schema (result of migrations 001 through 014) in one go.
-- Used ONLY by setup.py on a fresh installation (empty database, no
-- _migrations table). Existing installations keep running the incremental
-- migrations 001-014 as before.
--
-- LET OP: als dit bestand wordt gebruikt, moet setup.py de _migrations
-- tabel vullen met de versienummers 1,2,3,4,5,6,8,9,10,11,12,13,14 zodat
-- geen enkele incrementele migratie later opnieuw geprobeerd wordt.
--
-- NOTE: if this file is used, setup.py must fill the _migrations table
-- with version numbers 1,2,3,4,5,6,8,9,10,11,12,13,14 so no incremental
-- migration is ever attempted afterwards.

CREATE TABLE IF NOT EXISTS `system_config` (
    `id`                              INT           NOT NULL AUTO_INCREMENT,
    `created_at`                      DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP,
    `updated_at`                      DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    `latitude`                        DECIMAL(10,7) NOT NULL,
    `longitude`                       DECIMAL(10,7) NOT NULL,
    `has_grid_connection`             TINYINT(1)    NOT NULL DEFAULT 1,
    `has_solar_panels`                TINYINT(1)    NOT NULL DEFAULT 0,
    `has_gas`                         TINYINT(1)    NOT NULL DEFAULT 0,
    `has_district_heating`            TINYINT(1)    NOT NULL DEFAULT 0,
    `has_battery`                     TINYINT(1)    NOT NULL DEFAULT 0,
    `battery_efficiency_pct`          DECIMAL(5,2)  DEFAULT 75.00,
    `min_price_to_discharge`          DECIMAL(8,5)  DEFAULT NULL,
    `max_price_to_charge`             DECIMAL(8,5)  DEFAULT NULL,
    `price_incl_tax`                  TINYINT(1)    NOT NULL DEFAULT 1,
    `language`                        CHAR(2)       NOT NULL DEFAULT 'nl',
    `hard_min_discharge_price_excl`   DECIMAL(8,5)  DEFAULT 0.05000
        COMMENT 'Harde minimale ontlaadprijs excl. BTW / Hard minimum discharge price excl. VAT',
    `temp_derating_threshold_c`       DECIMAL(5,2)  DEFAULT 35.00
        COMMENT 'Battery temp above which power is derated / Batterijtemperatuur waarboven vermogen wordt verlaagd',
    `temp_derating_factor`            DECIMAL(4,2)  DEFAULT 0.70
        COMMENT 'Power reduction factor when temp exceeded / Vermogensfactor bij te hoge temperatuur',
    `min_spread_ratio_for_discharge`  DECIMAL(4,2)  DEFAULT 2.00
        COMMENT 'Min price spread ratio to trigger discharge / Min prijsspreiding voor ontladen',
    `discharge_near_peak_fraction`    DECIMAL(4,2)  DEFAULT 0.85
        COMMENT 'Price must be within this fraction of peak / Prijs moet binnen deze fractie van piek liggen',
    `extreme_price_multiplier`        DECIMAL(4,2)  DEFAULT 2.50
        COMMENT 'Multiple of avg price considered extreme / Veelvoud van gem. prijs dat extreem is',
    `negative_export_threshold_excl`  DECIMAL(8,5)  DEFAULT 0.00000
        COMMENT 'Export price below which to limit export (excl. VAT) / Terugleverprijs waaronder export beperkt wordt',
    `notify_export_threshold_excl`    DECIMAL(8,5)  DEFAULT 0.02000
        COMMENT 'Notify user when export price below this / Gebruiker melden bij lage terugleverprijs',
    `charge_near_cheapest_fraction`   DECIMAL(4,2)  DEFAULT 1.05
        COMMENT 'Price must be within this fraction of cheapest / Prijs moet binnen deze fractie van minimum liggen',
    `min_sunshine_pct_for_refill`     DECIMAL(5,2)  DEFAULT 40.00
        COMMENT 'Min sunshine % tomorrow to allow discharge / Min zonpercentage morgen voor ontladen',
    `avg_consumption_kwh`             DECIMAL(6,3)  DEFAULT 0.500
        COMMENT 'Expected average hourly consumption / Verwacht gemiddeld uurverbruik',
    `sunrise_buffer_pct`              DECIMAL(5,2)  DEFAULT 10.00
        COMMENT 'SoC buffer to keep at sunrise / SoC-buffer te bewaren bij zonsopgang',
    `evening_planning_time`           TIME          DEFAULT '21:00:00'
        COMMENT 'Time to run evening day balance planning / Tijd voor avond dagbalansplanning',
    `solar_charge_threshold`          DECIMAL(4,2)  NOT NULL DEFAULT 0.80
        COMMENT 'Block grid charging when expected solar >= this fraction of usable capacity / Blokkeer nettoladen als verwachte zon >= deze fractie van bruikbare capaciteit',
    `dashboard_colors`                JSON          DEFAULT NULL
        COMMENT 'Custom chart colors as JSON / Aangepaste grafiekkleuren als JSON',
    `gas_price_eur_m3`                DECIMAL(8,5)  DEFAULT NULL
        COMMENT 'Fixed gas price in €/m³ incl. VAT / Vaste gasprijs in €/m³ incl. BTW',
    `gas_price_entity_id`             VARCHAR(256)  DEFAULT NULL
        COMMENT 'Optional HA entity for dynamic gas price / Optionele HA-entiteit voor dynamische gasprijs',
    `heating_price_eur_gj`            DECIMAL(8,5)  DEFAULT NULL
        COMMENT 'Fixed district heating price in €/GJ incl. VAT / Vaste stadsverwarmingprijs in €/GJ incl. BTW',
    `heating_price_entity_id`         VARCHAR(256)  DEFAULT NULL
        COMMENT 'Optional HA entity for dynamic heating price / Optionele HA-entiteit voor dynamische stadsverwarmingprijs',
    PRIMARY KEY (`id`)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS `inverter_info` (
    `id`               INT         NOT NULL AUTO_INCREMENT,
    `created_at`       DATETIME    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    `updated_at`       DATETIME    NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    `brand`            VARCHAR(50),
    `model`            VARCHAR(50),
    `supplier`         VARCHAR(50),
    `driver`           VARCHAR(50) NOT NULL,
    `driver_config`    JSON,
    `installed_on`     DATE,
    `max_charge_kw`    DECIMAL(8,3),
    `max_discharge_kw` DECIMAL(8,3),
    `warranty_years`   INT,
    PRIMARY KEY (`id`)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS `solar_info` (
    `id`                       INT          NOT NULL AUTO_INCREMENT,
    `created_at`               DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    `updated_at`               DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    `panel_brand`              VARCHAR(50),
    `panel_model`              VARCHAR(50),
    `panel_supplier`           VARCHAR(50),
    `number_of_panels`         INT,
    `panel_max_power_wp`       DECIMAL(8,2),
    `total_max_power_kw`       DECIMAL(8,3),
    `installed_on`             DATE,
    `degradation_pct_per_year` DECIMAL(5,2),
    `orientation_degrees`      INT,
    `tilt_degrees`             INT,
    PRIMARY KEY (`id`)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS `battery_info` (
    `id`                     INT         NOT NULL AUTO_INCREMENT,
    `created_at`             DATETIME    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    `updated_at`             DATETIME    NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    `brand`                  VARCHAR(50),
    `model`                  VARCHAR(50),
    `supplier`               VARCHAR(50),
    `installed_on`           DATE,
    `capacity_kwh`           DECIMAL(8,3),
    `usable_capacity_kwh`    DECIMAL(8,3),
    `max_charge_kw`          DECIMAL(8,3),
    `max_discharge_kw`       DECIMAL(8,3),
    `min_soc_pct`            DECIMAL(5,2) DEFAULT 10.00,
    `max_soc_pct`            DECIMAL(5,2) DEFAULT 95.00,
    `warranty_years`         INT,
    `cycle_count_at_install` INT          DEFAULT 0,
    `cost_eur`               DECIMAL(10,2) DEFAULT NULL
        COMMENT 'Purchase price of battery / Aanschafprijs batterij',
    `expected_cycles`        INT           DEFAULT NULL
        COMMENT 'Expected lifetime charge cycles / Verwachte levensduur laadcycli',
    `working_charge_kw`      DECIMAL(8,3)  DEFAULT NULL
        COMMENT 'Preferred charge power (< max for battery health) / Voorkeurslaadvermogen',
    `working_discharge_kw`   DECIMAL(8,3)  DEFAULT NULL
        COMMENT 'Preferred discharge power (< max for battery health) / Voorkeursontlaadvermogen',
    PRIMARY KEY (`id`)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS `provider_config` (
    `id`              INT         NOT NULL AUTO_INCREMENT,
    `created_at`      DATETIME    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    `updated_at`      DATETIME    NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    `energy_type`     ENUM('electricity','gas') NOT NULL,
    `provider_driver` VARCHAR(50) NOT NULL,
    `driver_config`   JSON,
    `is_active`       TINYINT(1)  NOT NULL DEFAULT 1,
    PRIMARY KEY (`id`)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS `ha_entity_map` (
    `id`            INT          NOT NULL AUTO_INCREMENT,
    `created_at`    DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    `updated_at`    DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    `internal_name` VARCHAR(100) NOT NULL UNIQUE,
    `entity_id`     VARCHAR(256) NOT NULL,
    `source`        VARCHAR(50),
    `unit`          VARCHAR(20),
    `description`   VARCHAR(255),
    PRIMARY KEY (`id`)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS `energy_prices` (
    `id`             INT           NOT NULL AUTO_INCREMENT,
    `created_at`     DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP,
    `price_hour`     DATETIME      NOT NULL,
    `energy_type`    ENUM('electricity','gas') NOT NULL,
    `price_per_kwh`  DECIMAL(10,5) NOT NULL,
    `price_incl_tax` TINYINT(1)    NOT NULL DEFAULT 1,
    `source`         VARCHAR(50),
    PRIMARY KEY (`id`),
    UNIQUE KEY `unique_price_hour` (`price_hour`, `energy_type`)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS `solar_production` (
    `id`          INT          NOT NULL AUTO_INCREMENT,
    `created_at`  DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    `measured_at` DATETIME     NOT NULL,
    `power_kw`    DECIMAL(8,3) NOT NULL,
    `energy_kwh`  DECIMAL(8,3),
    PRIMARY KEY (`id`)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS `home_consumption` (
    `id`                   INT          NOT NULL AUTO_INCREMENT,
    `created_at`           DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    `measured_at`          DATETIME     NOT NULL,
    `grid_import_kw`       DECIMAL(8,3),
    `grid_export_kw`       DECIMAL(8,3),
    `total_consumption_kw` DECIMAL(8,3),
    `gas_m3`               DECIMAL(8,4),
    PRIMARY KEY (`id`)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS `battery_status` (
    `id`                    INT          NOT NULL AUTO_INCREMENT,
    `created_at`            DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    `measured_at`           DATETIME     NOT NULL,
    `soc_pct`               DECIMAL(5,2),
    `power_kw`              DECIMAL(8,3),
    `voltage_v`             DECIMAL(8,2),
    `temperature_c`         DECIMAL(5,2),
    `energy_charged_kwh`    DECIMAL(8,3),
    `energy_discharged_kwh` DECIMAL(8,3),
    `cycle_count`           INT,
    PRIMARY KEY (`id`)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS `weather_forecast` (
    `id`                   INT           NOT NULL AUTO_INCREMENT,
    `created_at`           DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP,
    `forecast_for`         DATETIME      NOT NULL,
    `sun_rise`             TIME,
    `sun_set`              TIME,
    `sunshine_pct`         DECIMAL(5,2),
    `cloud_cover_pct`      DECIMAL(5,2),
    `rain_mm`              DECIMAL(6,2),
    `wind_speed_ms`        DECIMAL(6,2),
    `wind_direction_deg`   INT,
    `temperature_c`        DECIMAL(5,2),
    `solar_irradiance_wm2` DECIMAL(8,2),
    `source`               VARCHAR(50),
    PRIMARY KEY (`id`),
    UNIQUE KEY `unique_forecast_hour` (`forecast_for`)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS `optimizer_schedule` (
    `id`                      INT           NOT NULL AUTO_INCREMENT,
    `created_at`              DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP,
    `schedule_for`            DATETIME      NOT NULL,
    `action`                  ENUM('charge','discharge','idle','self_consume') NOT NULL,
    `target_power_kw`         DECIMAL(8,3),
    `target_soc_pct`          DECIMAL(5,2),
    `expected_price`          DECIMAL(10,5),
    `expected_solar_kw`       DECIMAL(8,3),
    `expected_consumption_kw` DECIMAL(8,3),
    `expected_saving`         DECIMAL(8,5),
    `expected_cost`           DECIMAL(10,5) DEFAULT 0
        COMMENT 'Cost of grid charging this hour, excl. VAT / Kosten van netladen dit uur, excl. BTW',
    `reason`                  VARCHAR(255),
    `reason_key`              VARCHAR(8)    DEFAULT NULL
        COMMENT 'Vertaalsleutel bijv. RS01 / Translation key e.g. RS01',
    `reason_params`           JSON          DEFAULT NULL
        COMMENT 'Parameters voor vertaling bijv. {"price": 0.12} / Translation params',
    `executed`                TINYINT(1)    NOT NULL DEFAULT 0,
    `executed_at`             DATETIME,
    PRIMARY KEY (`id`)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS `report_log` (
    `id`          INT      NOT NULL AUTO_INCREMENT,
    `created_at`  DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    `report_type` ENUM('info','daily','warning','error') NOT NULL DEFAULT 'info',
    `category`    VARCHAR(50),
    `message`     TEXT     NOT NULL,
    `notified`    TINYINT(1) NOT NULL DEFAULT 0,
    `notified_at` DATETIME,
    PRIMARY KEY (`id`)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS `consumption_profile` (
    `id`          INT          NOT NULL AUTO_INCREMENT,
    `updated_at`  DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    `day_of_week` TINYINT      NOT NULL COMMENT '0=Monday/maandag, 6=Sunday/zondag',
    `hour_of_day` TINYINT      NOT NULL COMMENT '0-23 local time / lokale tijd',
    `avg_kw`      DECIMAL(6,3) NOT NULL DEFAULT 0.000 COMMENT 'Average consumption kW / Gemiddeld verbruik kW',
    `min_kw`      DECIMAL(6,3) NOT NULL DEFAULT 0.000,
    `max_kw`      DECIMAL(6,3) NOT NULL DEFAULT 0.000,
    `samples`     INT          NOT NULL DEFAULT 0 COMMENT 'Number of measurements / Aantal metingen',
    PRIMARY KEY (`id`),
    UNIQUE KEY `unique_day_hour` (`day_of_week`, `hour_of_day`)
) ENGINE=InnoDB
  COMMENT='Average energy consumption per weekday/hour / Gemiddeld verbruik per weekdag/uur';

CREATE TABLE IF NOT EXISTS `solar_profile` (
    `id`               INT          NOT NULL AUTO_INCREMENT,
    `updated_at`       DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    `month`            TINYINT      NOT NULL COMMENT '1=January/januari, 12=December/december',
    `hour_of_day`      TINYINT      NOT NULL COMMENT '0-23 local time / lokale tijd',
    `avg_kw`           DECIMAL(6,3) NOT NULL DEFAULT 0.000 COMMENT 'Average solar output kW / Gemiddelde zonne-opbrengst kW',
    `max_kw`           DECIMAL(6,3) NOT NULL DEFAULT 0.000,
    `avg_sunshine_pct` DECIMAL(5,2)          DEFAULT NULL COMMENT 'Average sunshine percentage / Gemiddeld zonpercentage',
    `samples`          INT          NOT NULL DEFAULT 0,
    PRIMARY KEY (`id`),
    UNIQUE KEY `unique_month_hour` (`month`, `hour_of_day`)
) ENGINE=InnoDB
  COMMENT='Expected solar output per month/hour / Verwachte zonne-opbrengst per maand/uur';

CREATE TABLE IF NOT EXISTS `price_profile` (
    `id`          INT          NOT NULL AUTO_INCREMENT,
    `updated_at`  DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    `month`       TINYINT      NOT NULL COMMENT '1=January, 12=December',
    `day_of_week` TINYINT      NOT NULL COMMENT '0=Monday, 6=Sunday',
    `hour_of_day` TINYINT      NOT NULL COMMENT '0-23 local time',
    `avg_price`   DECIMAL(8,5) NOT NULL DEFAULT 0.00000 COMMENT 'Average price €/kWh / Gemiddelde prijs €/kWh',
    `min_price`   DECIMAL(8,5) NOT NULL DEFAULT 0.00000,
    `max_price`   DECIMAL(8,5) NOT NULL DEFAULT 0.00000,
    `samples`     INT          NOT NULL DEFAULT 0,
    PRIMARY KEY (`id`),
    UNIQUE KEY `unique_month_dow_hour` (`month`, `day_of_week`, `hour_of_day`)
) ENGINE=InnoDB
  COMMENT='Average price patterns per month/weekday/hour / Gemiddelde prijspatronen per maand/weekdag/uur';

CREATE TABLE IF NOT EXISTS `solar_learning` (
    `hour_of_day`     TINYINT      NOT NULL COMMENT 'Uur van de dag (0..23) / Hour of day (0..23)',
    `week_block`      TINYINT      NOT NULL COMMENT 'Blok van 2 weken (1..26) / 2-week block (1..26)',
    `irradiance_low`  DECIMAL(8,3) NOT NULL DEFAULT 0 COMMENT 'Laagste gemeten instraling W/m² / Lowest measured irradiance W/m²',
    `irradiance_high` DECIMAL(8,3) NOT NULL DEFAULT 0 COMMENT 'Hoogste gemeten instraling W/m² / Highest measured irradiance W/m²',
    `solar_kwh_low`   DECIMAL(8,4) NOT NULL DEFAULT 0 COMMENT 'Laagste gemeten opbrengst kWh / Lowest measured yield kWh',
    `solar_kwh_high`  DECIMAL(8,4) NOT NULL DEFAULT 0 COMMENT 'Hoogste gemeten opbrengst kWh / Highest measured yield kWh',
    `sample_count`    INT          NOT NULL DEFAULT 0 COMMENT 'Aantal metingen / Number of measurements',
    `updated_at`      DATETIME     DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (`hour_of_day`, `week_block`)
) ENGINE=InnoDB COMMENT='Zon-efficiëntie leermodel / Solar efficiency learning model';

CREATE TABLE IF NOT EXISTS `consumption_learning` (
    `month_of_year` TINYINT      NOT NULL COMMENT 'Maand (1..12) / Month (1..12)',
    `day_of_week`   TINYINT      NOT NULL COMMENT 'Dag van de week (0=ma..6=zo) / Day of week (0=Mon..6=Sun)',
    `hour_of_day`   TINYINT      NOT NULL COMMENT 'Uur van de dag (0..23) / Hour of day (0..23)',
    `kwh_avg`       DECIMAL(8,4) NOT NULL DEFAULT 0 COMMENT 'Rollend gewogen gemiddelde kWh / Rolling weighted average kWh',
    `kwh_min`       DECIMAL(8,4) NOT NULL DEFAULT 0 COMMENT 'Laagste gemeten kWh / Lowest measured kWh',
    `kwh_max`       DECIMAL(8,4) NOT NULL DEFAULT 0 COMMENT 'Hoogste gemeten kWh / Highest measured kWh',
    `sample_count`  INT          NOT NULL DEFAULT 0 COMMENT 'Aantal metingen (de deler) / Number of measurements (the divisor)',
    `updated_at`    DATETIME     DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (`month_of_year`, `day_of_week`, `hour_of_day`)
) ENGINE=InnoDB COMMENT='Huisverbruik leermodel / Household consumption learning model';

CREATE TABLE IF NOT EXISTS `translation_strings` (
    `string_key` VARCHAR(8)   NOT NULL COMMENT 'Sleutel bijv. RS01 / Key e.g. RS01',
    `language`   CHAR(2)      NOT NULL COMMENT 'Taalcode bijv. nl, en / Language code',
    `text`       TEXT         NOT NULL COMMENT 'Vertaalde tekst met {variabelen} / Translated text with {variables}',
    `updated_at` DATETIME     DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (`string_key`, `language`)
) ENGINE=InnoDB COMMENT='Operationele vertalingen / Operational translations';

-- Indexen (migratie 002) / Indexes (migration 002)
CREATE INDEX IF NOT EXISTS idx_energy_prices_hour   ON energy_prices    (price_hour);
CREATE INDEX IF NOT EXISTS idx_energy_prices_type   ON energy_prices    (energy_type, price_hour);
CREATE INDEX IF NOT EXISTS idx_solar_measured       ON solar_production (measured_at);
CREATE INDEX IF NOT EXISTS idx_consumption_measured ON home_consumption (measured_at);
CREATE INDEX IF NOT EXISTS idx_battery_measured     ON battery_status   (measured_at);
CREATE INDEX IF NOT EXISTS idx_weather_forecast     ON weather_forecast (forecast_for);
CREATE INDEX IF NOT EXISTS idx_optimizer_schedule   ON optimizer_schedule (schedule_for);
CREATE INDEX IF NOT EXISTS idx_report_type          ON report_log       (report_type);
CREATE INDEX IF NOT EXISTS idx_report_notified      ON report_log       (notified, created_at);

-- Standaard systeemconfiguratie / Default system configuration
INSERT IGNORE INTO system_config
    (latitude, longitude, has_grid_connection, has_battery,
     battery_efficiency_pct,
     min_price_to_discharge, max_price_to_charge,
     price_incl_tax, language)
VALUES
    (52.1551, 5.3872, 1, 1,
     75.00,
     0.22000, 0.10000,
     1, 'nl');
