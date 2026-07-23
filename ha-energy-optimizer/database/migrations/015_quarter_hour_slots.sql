--
-- name:          015_quarter_hour_slots.sql
-- part of:       ha-energy-optimizer
-- location:      /ha-energy-optimizer/ha-energy-optimizer/database/migrations/015_quarter_hour_slots.sql
-- part version:  p_v0.1
-- altered:       2026-07-22
--
-- Migreert de leer- en profieltabellen van hour_of_day (0-23) naar
-- slot_of_day (0-95, kwartier-resolutie). Bestaande data wordt niet
-- weggegooid: elke uurwaarde wordt gekopieerd naar de 4 bijbehorende
-- kwartier-slots van dat uur (bootstrap), zodat er niet weer vanaf nul
-- geleerd hoeft te worden. Nieuwe metingen verfijnen daarna elk kwartier
-- apart.
--
-- Migrates the learning/profile tables from hour_of_day (0-23) to
-- slot_of_day (0-95, quarter-hour resolution). Existing data is not
-- discarded: each hourly value is copied into the 4 corresponding
-- quarter slots of that hour (bootstrap), so learning doesn't have to
-- start from zero again. New measurements then refine each quarter
-- separately.
--
-- energy_prices en optimizer_schedule zijn NIET aangepast: die gebruiken
-- al DATETIME-kolommen zonder uur-beperking, kwartier-rijen passen daar
-- vanzelf in.
-- energy_prices and optimizer_schedule are NOT changed: they already use
-- DATETIME columns without an hourly restriction, quarter rows fit there
-- automatically.

-- ── solar_learning ──────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS `solar_learning_new` (
    `slot_of_day`     TINYINT      NOT NULL COMMENT 'Kwartier-slot van de dag (0..95) / Quarter slot of day (0..95)',
    `week_block`      TINYINT      NOT NULL COMMENT 'Blok van 2 weken (1..26) / 2-week block (1..26)',
    `irradiance_low`  DECIMAL(8,3) NOT NULL DEFAULT 0 COMMENT 'Laagste gemeten instraling W/m² / Lowest measured irradiance W/m²',
    `irradiance_high` DECIMAL(8,3) NOT NULL DEFAULT 0 COMMENT 'Hoogste gemeten instraling W/m² / Highest measured irradiance W/m²',
    `solar_kwh_low`   DECIMAL(8,4) NOT NULL DEFAULT 0 COMMENT 'Laagste gemeten opbrengst kWh / Lowest measured yield kWh',
    `solar_kwh_high`  DECIMAL(8,4) NOT NULL DEFAULT 0 COMMENT 'Hoogste gemeten opbrengst kWh / Highest measured yield kWh',
    `sample_count`    INT          NOT NULL DEFAULT 0 COMMENT 'Aantal metingen / Number of measurements',
    `updated_at`      DATETIME     DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (`slot_of_day`, `week_block`)
) ENGINE=InnoDB COMMENT='Zon-efficiëntie leermodel (kwartier) / Solar efficiency learning model (quarter hour)';

INSERT INTO `solar_learning_new`
    (slot_of_day, week_block, irradiance_low, irradiance_high,
     solar_kwh_low, solar_kwh_high, sample_count, updated_at)
SELECT
    old.hour_of_day * 4 + q.quarter AS slot_of_day,
    old.week_block,
    old.irradiance_low, old.irradiance_high,
    old.solar_kwh_low, old.solar_kwh_high,
    old.sample_count, old.updated_at
FROM `solar_learning` old
CROSS JOIN (SELECT 0 AS quarter UNION SELECT 1 UNION SELECT 2 UNION SELECT 3) q;

RENAME TABLE `solar_learning` TO `solar_learning_old_015`,
             `solar_learning_new` TO `solar_learning`;

DROP TABLE `solar_learning_old_015`;

-- ── consumption_learning ────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS `consumption_learning_new` (
    `month_of_year` TINYINT      NOT NULL COMMENT 'Maand (1..12) / Month (1..12)',
    `day_of_week`   TINYINT      NOT NULL COMMENT 'Dag van de week (0=ma..6=zo) / Day of week (0=Mon..6=Sun)',
    `slot_of_day`   TINYINT      NOT NULL COMMENT 'Kwartier-slot van de dag (0..95) / Quarter slot of day (0..95)',
    `kwh_avg`       DECIMAL(8,4) NOT NULL DEFAULT 0 COMMENT 'Rollend gewogen gemiddelde kWh / Rolling weighted average kWh',
    `kwh_min`       DECIMAL(8,4) NOT NULL DEFAULT 0 COMMENT 'Laagste gemeten kWh / Lowest measured kWh',
    `kwh_max`       DECIMAL(8,4) NOT NULL DEFAULT 0 COMMENT 'Hoogste gemeten kWh / Highest measured kWh',
    `sample_count`  INT          NOT NULL DEFAULT 0 COMMENT 'Aantal metingen (de deler) / Number of measurements (the divisor)',
    `updated_at`    DATETIME     DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (`month_of_year`, `day_of_week`, `slot_of_day`)
) ENGINE=InnoDB COMMENT='Huisverbruik leermodel (kwartier) / Household consumption learning model (quarter hour)';

INSERT INTO `consumption_learning_new`
    (month_of_year, day_of_week, slot_of_day,
     kwh_avg, kwh_min, kwh_max, sample_count, updated_at)
SELECT
    old.month_of_year, old.day_of_week,
    old.hour_of_day * 4 + q.quarter AS slot_of_day,
    old.kwh_avg, old.kwh_min, old.kwh_max,
    old.sample_count, old.updated_at
FROM `consumption_learning` old
CROSS JOIN (SELECT 0 AS quarter UNION SELECT 1 UNION SELECT 2 UNION SELECT 3) q;

RENAME TABLE `consumption_learning` TO `consumption_learning_old_015`,
             `consumption_learning_new` TO `consumption_learning`;

DROP TABLE `consumption_learning_old_015`;

-- ── solar_profile (legacy fallback, gebruikt in engine.py._build_forecasts) ──

CREATE TABLE IF NOT EXISTS `solar_profile_new` (
    `id`               INT          NOT NULL AUTO_INCREMENT,
    `updated_at`       DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    `month`            TINYINT      NOT NULL COMMENT '1=January/januari, 12=December/december',
    `slot_of_day`      TINYINT      NOT NULL COMMENT 'Kwartier-slot van de dag (0..95) / Quarter slot of day (0..95)',
    `avg_kw`           DECIMAL(6,3) NOT NULL DEFAULT 0.000 COMMENT 'Average solar output kW / Gemiddelde zonne-opbrengst kW',
    `max_kw`           DECIMAL(6,3) NOT NULL DEFAULT 0.000,
    `avg_sunshine_pct` DECIMAL(5,2)          DEFAULT NULL COMMENT 'Average sunshine percentage / Gemiddeld zonpercentage',
    `samples`          INT          NOT NULL DEFAULT 0,
    PRIMARY KEY (`id`),
    UNIQUE KEY `unique_month_slot` (`month`, `slot_of_day`)
) ENGINE=InnoDB
  COMMENT='Expected solar output per month/quarter-slot / Verwachte zonne-opbrengst per maand/kwartier-slot';

INSERT INTO `solar_profile_new`
    (month, slot_of_day, avg_kw, max_kw, avg_sunshine_pct, samples, updated_at)
SELECT
    old.month,
    old.hour_of_day * 4 + q.quarter AS slot_of_day,
    old.avg_kw, old.max_kw, old.avg_sunshine_pct, old.samples, old.updated_at
FROM `solar_profile` old
CROSS JOIN (SELECT 0 AS quarter UNION SELECT 1 UNION SELECT 2 UNION SELECT 3) q;

RENAME TABLE `solar_profile` TO `solar_profile_old_015`,
             `solar_profile_new` TO `solar_profile`;

DROP TABLE `solar_profile_old_015`;

-- ── consumption_profile (legacy fallback, gebruikt in engine.py._build_forecasts) ──

CREATE TABLE IF NOT EXISTS `consumption_profile_new` (
    `id`          INT          NOT NULL AUTO_INCREMENT,
    `updated_at`  DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    `day_of_week` TINYINT      NOT NULL COMMENT '0=Monday/maandag, 6=Sunday/zondag',
    `slot_of_day` TINYINT      NOT NULL COMMENT 'Kwartier-slot van de dag (0..95) / Quarter slot of day (0..95)',
    `avg_kw`      DECIMAL(6,3) NOT NULL DEFAULT 0.000 COMMENT 'Average consumption kW / Gemiddeld verbruik kW',
    `min_kw`      DECIMAL(6,3) NOT NULL DEFAULT 0.000,
    `max_kw`      DECIMAL(6,3) NOT NULL DEFAULT 0.000,
    `samples`     INT          NOT NULL DEFAULT 0 COMMENT 'Number of measurements / Aantal metingen',
    PRIMARY KEY (`id`),
    UNIQUE KEY `unique_day_slot` (`day_of_week`, `slot_of_day`)
) ENGINE=InnoDB
  COMMENT='Average energy consumption per weekday/quarter-slot / Gemiddeld verbruik per weekdag/kwartier-slot';

INSERT INTO `consumption_profile_new`
    (day_of_week, slot_of_day, avg_kw, min_kw, max_kw, samples, updated_at)
SELECT
    old.day_of_week,
    old.hour_of_day * 4 + q.quarter AS slot_of_day,
    old.avg_kw, old.min_kw, old.max_kw, old.samples, old.updated_at
FROM `consumption_profile` old
CROSS JOIN (SELECT 0 AS quarter UNION SELECT 1 UNION SELECT 2 UNION SELECT 3) q;

RENAME TABLE `consumption_profile` TO `consumption_profile_old_015`,
             `consumption_profile_new` TO `consumption_profile`;

DROP TABLE `consumption_profile_old_015`;

-- ── price_profile ────────────────────────────────────────────────────────────
-- LET OP: dit bestand kon niet bevestigen dat price_profile ergens gelezen
-- wordt (alleen CREATE + vermoedelijk gevuld door profile_updater.py, dat
-- ik nog niet heb gezien). Voor consistentie toch meegemigreerd; laat het
-- weten als dit ongebruikte legacy is en veilig verwijderd kan worden i.p.v.
-- gemigreerd.
-- NOTE: this migration could not confirm price_profile is read anywhere
-- (only CREATE + presumably filled by profile_updater.py, which I haven't
-- seen yet). Migrated for consistency anyway; let me know if this is
-- unused legacy that can safely be dropped instead of migrated.

CREATE TABLE IF NOT EXISTS `price_profile_new` (
    `id`          INT          NOT NULL AUTO_INCREMENT,
    `updated_at`  DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    `month`       TINYINT      NOT NULL COMMENT '1=January, 12=December',
    `day_of_week` TINYINT      NOT NULL COMMENT '0=Monday, 6=Sunday',
    `slot_of_day` TINYINT      NOT NULL COMMENT 'Kwartier-slot van de dag (0..95) / Quarter slot of day (0..95)',
    `avg_price`   DECIMAL(8,5) NOT NULL DEFAULT 0.00000 COMMENT 'Average price €/kWh / Gemiddelde prijs €/kWh',
    `min_price`   DECIMAL(8,5) NOT NULL DEFAULT 0.00000,
    `max_price`   DECIMAL(8,5) NOT NULL DEFAULT 0.00000,
    `samples`     INT          NOT NULL DEFAULT 0,
    PRIMARY KEY (`id`),
    UNIQUE KEY `unique_month_dow_slot` (`month`, `day_of_week`, `slot_of_day`)
) ENGINE=InnoDB
  COMMENT='Average price patterns per month/weekday/quarter-slot / Gemiddelde prijspatronen per maand/weekdag/kwartier-slot';

INSERT INTO `price_profile_new`
    (month, day_of_week, slot_of_day, avg_price, min_price, max_price, samples, updated_at)
SELECT
    old.month, old.day_of_week,
    old.hour_of_day * 4 + q.quarter AS slot_of_day,
    old.avg_price, old.min_price, old.max_price, old.samples, old.updated_at
FROM `price_profile` old
CROSS JOIN (SELECT 0 AS quarter UNION SELECT 1 UNION SELECT 2 UNION SELECT 3) q;

RENAME TABLE `price_profile` TO `price_profile_old_015`,
             `price_profile_new` TO `price_profile`;

DROP TABLE `price_profile_old_015`;

-- ── system_config: vastleggen dat dit een kwartier-installatie is ──────────
-- Puur informatief/toekomstbestendig — de huidige Python-code leest
-- config.timeslot.SLOT_MINUTES (code-constante), niet deze kolom. Mocht
-- runtime-omschakelbaarheid ooit gewenst zijn, ligt de kolom er al.
-- Purely informational/future-proofing — the current Python code reads
-- config.timeslot.SLOT_MINUTES (code constant), not this column. Should
-- runtime switching ever be wanted, the column is already there.

ALTER TABLE `system_config`
    ADD COLUMN IF NOT EXISTS `schedule_interval_minutes` SMALLINT NOT NULL DEFAULT 15
        COMMENT 'Schema-tijdstap in minuten / Schedule time step in minutes';
