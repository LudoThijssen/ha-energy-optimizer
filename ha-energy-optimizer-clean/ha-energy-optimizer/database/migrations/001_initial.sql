CREATE TABLE IF NOT EXISTS `system_config` (
    `id`                    INT          NOT NULL AUTO_INCREMENT,
    `created_at`            DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    `updated_at`            DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    `latitude`              DECIMAL(10,7) NOT NULL,
    `longitude`             DECIMAL(10,7) NOT NULL,
    `has_grid_connection`   TINYINT(1)   NOT NULL DEFAULT 1,
    `has_solar_panels`      TINYINT(1)   NOT NULL DEFAULT 0,
    `has_gas`               TINYINT(1)   NOT NULL DEFAULT 0,
    `has_district_heating`  TINYINT(1)   NOT NULL DEFAULT 0,
    `has_battery`           TINYINT(1)   NOT NULL DEFAULT 0,
    `battery_efficiency_pct` DECIMAL(5,2) DEFAULT 90.00,
    `min_price_to_discharge` DECIMAL(8,5) DEFAULT NULL,
    `max_price_to_charge`   DECIMAL(8,5)  DEFAULT NULL,
    `price_incl_tax`        TINYINT(1)   NOT NULL DEFAULT 1,
    `language`              CHAR(2)      NOT NULL DEFAULT 'nl',
    PRIMARY KEY (`id`)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS `inverter_info` (
    `id`              INT         NOT NULL AUTO_INCREMENT,
    `created_at`      DATETIME    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    `updated_at`      DATETIME    NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    `brand`           VARCHAR(50),
    `model`           VARCHAR(50),
    `supplier`        VARCHAR(50),
    `driver`          VARCHAR(50) NOT NULL,
    `driver_config`   JSON,
    `installed_on`    DATE,
    `max_charge_kw`   DECIMAL(8,3),
    `max_discharge_kw` DECIMAL(8,3),
    `warranty_years`  INT,
    PRIMARY KEY (`id`)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS `solar_info` (
    `id`                    INT          NOT NULL AUTO_INCREMENT,
    `created_at`            DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    `updated_at`            DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    `panel_brand`           VARCHAR(50),
    `panel_model`           VARCHAR(50),
    `panel_supplier`        VARCHAR(50),
    `number_of_panels`      INT,
    `panel_max_power_wp`    DECIMAL(8,2),
    `total_max_power_kw`    DECIMAL(8,3),
    `installed_on`          DATE,
    `degradation_pct_per_year` DECIMAL(5,2),
    `orientation_degrees`   INT,
    `tilt_degrees`          INT,
    PRIMARY KEY (`id`)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS `battery_info` (
    `id`                INT         NOT NULL AUTO_INCREMENT,
    `created_at`        DATETIME    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    `updated_at`        DATETIME    NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    `brand`             VARCHAR(50),
    `model`             VARCHAR(50),
    `supplier`          VARCHAR(50),
    `installed_on`      DATE,
    `capacity_kwh`      DECIMAL(8,3),
    `usable_capacity_kwh` DECIMAL(8,3),
    `max_charge_kw`     DECIMAL(8,3),
    `max_discharge_kw`  DECIMAL(8,3),
    `min_soc_pct`       DECIMAL(5,2) DEFAULT 10.00,
    `max_soc_pct`       DECIMAL(5,2) DEFAULT 95.00,
    `warranty_years`    INT,
    `cycle_count_at_install` INT     DEFAULT 0,
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
    `id`            INT           NOT NULL AUTO_INCREMENT,
    `created_at`    DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP,
    `price_hour`    DATETIME      NOT NULL,
    `energy_type`   ENUM('electricity','gas') NOT NULL,
    `price_per_kwh` DECIMAL(10,5) NOT NULL,
    `price_incl_tax` TINYINT(1)  NOT NULL DEFAULT 1,
    `source`        VARCHAR(50),
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
    `id`                  INT          NOT NULL AUTO_INCREMENT,
    `created_at`          DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    `measured_at`         DATETIME     NOT NULL,
    `grid_import_kw`      DECIMAL(8,3),
    `grid_export_kw`      DECIMAL(8,3),
    `total_consumption_kw` DECIMAL(8,3),
    `gas_m3`              DECIMAL(8,4),
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
    `id`                    INT           NOT NULL AUTO_INCREMENT,
    `created_at`            DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP,
    `forecast_for`          DATETIME      NOT NULL,
    `sun_rise`              TIME,
    `sun_set`               TIME,
    `sunshine_pct`          DECIMAL(5,2),
    `cloud_cover_pct`       DECIMAL(5,2),
    `rain_mm`               DECIMAL(6,2),
    `wind_speed_ms`         DECIMAL(6,2),
    `wind_direction_deg`    INT,
    `temperature_c`         DECIMAL(5,2),
    `solar_irradiance_wm2`  DECIMAL(8,2),
    `source`                VARCHAR(50),
    PRIMARY KEY (`id`),
    UNIQUE KEY `unique_forecast_hour` (`forecast_for`)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS `optimizer_schedule` (
    `id`                     INT           NOT NULL AUTO_INCREMENT,
    `created_at`             DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP,
    `schedule_for`           DATETIME      NOT NULL,
    `action`                 ENUM('charge','discharge','idle','self_consume') NOT NULL,
    `target_power_kw`        DECIMAL(8,3),
    `target_soc_pct`         DECIMAL(5,2),
    `expected_price`         DECIMAL(10,5),
    `expected_solar_kw`      DECIMAL(8,3),
    `expected_consumption_kw` DECIMAL(8,3),
    `expected_saving`        DECIMAL(8,5),
    `reason`                 VARCHAR(255),
    `executed`               TINYINT(1)   NOT NULL DEFAULT 0,
    `executed_at`            DATETIME,
    PRIMARY KEY (`id`)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS `report_log` (
    `id`           INT      NOT NULL AUTO_INCREMENT,
    `created_at`   DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    `report_type`  ENUM('info','daily','warning','error') NOT NULL DEFAULT 'info',
    `category`     VARCHAR(50),
    `message`      TEXT     NOT NULL,
    `notified`     TINYINT(1) NOT NULL DEFAULT 0,
    `notified_at`  DATETIME,
    PRIMARY KEY (`id`)
) ENGINE=InnoDB;
