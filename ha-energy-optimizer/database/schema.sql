--
-- name:          schema.sql
-- part of:       ha-energy-optimizer
-- location:      /ha-energy-optimizer/ha-energy-optimizer/database/schema.sql
-- part version:  p_v1.1
-- altered:       2026-09-13
--
-- p_v1.0: NIEUW — vervangt het hele stelsel van genummerde migraties
-- (001-022, database/migrations/000_consolidated.sql) en de _migrations-
-- tabel. Dit ene bestand beschrijft de gewenste eindstaat van het schema
-- en wordt bij ELKE opstart volledig uitgevoerd (zie setup.py p_v0.14).
-- Alle statements zijn idempotent (CREATE TABLE IF NOT EXISTS, ADD COLUMN
-- IF NOT EXISTS, CREATE INDEX IF NOT EXISTS) — op een up-to-date
-- installatie zijn dit allemaal no-ops, op een oudere installatie vullen
-- ze precies de ontbrekende kolommen aan, op een verse installatie
-- bouwen ze het complete schema in één keer op. Geen aparte routes meer
-- voor "vers" vs "bestaand" — één bestand dekt alle gevallen.
--
-- Samengesteld uit database/migrations/000_consolidated.sql p_v0.6
-- (bijgewerkt t/m migratie 022). De ADD COLUMN-regels zijn programmatisch
-- gegenereerd uit de CREATE TABLE-definities, niet met de hand overgetypt.
--
-- BELANGRIJK VOOR TOEKOMSTIGE WIJZIGINGEN — lees dit voor je een kolom
-- toevoegt:
-- 1. Een NIEUWE kolom met NOT NULL zonder DEFAULT breekt op een tabel die
--    al rijen bevat (ALTER TABLE kan geen waarde verzinnen). Geef nieuwe
--    kolommen altijd een DEFAULT, of maak ze NULLable.
-- 2. AFTER-clausules zijn bewust NIET gebruikt bij de ADD COLUMN-regels
--    (nieuwe kolommen komen aan het eind) — dat voorkomt afhankelijkheden
--    tussen de volgorde van statements in dit bestand.
-- 3. Voeg een nieuwe kolom toe door 'm zowel in de betreffende CREATE
--    TABLE hierboven te zetten (voor verse installaties) ALS als losse
--    ADD COLUMN IF NOT EXISTS-regel hieronder (voor bestaande
--    installaties) — beide zijn nodig, ze dekken elkaar niet automatisch.
-- 4. Voor eenmalige, niet-idempotente datacorrecties (zoals de
--    UTC->lokale-tijd-correctie van de voormalige migratie 007) is dit
--    bestand NIET geschikt — zulke correcties mogen nooit bij elke
--    opstart opnieuw draaien. Bedenk in dat geval een apart mechanisme
--    (bv. een voorwaarde op de data zelf) vóórdat je zoiets hier toevoegt.
--
-- p_v1.0: NEW — replaces the entire numbered-migrations system (001-022,
-- database/migrations/000_consolidated.sql) and the _migrations table.
-- This single file describes the desired end state of the schema and is
-- run in full on EVERY startup (see setup.py p_v0.14). All statements are
-- idempotent (CREATE TABLE IF NOT EXISTS, ADD COLUMN IF NOT EXISTS,
-- CREATE INDEX IF NOT EXISTS) — on an up-to-date installation these are
-- all no-ops, on an older installation they backfill exactly the missing
-- columns, on a fresh installation they build the complete schema in one
-- go. No more separate "fresh" vs "existing" paths — one file covers
-- every case.
--
-- Assembled from database/migrations/000_consolidated.sql p_v0.6 (updated
-- through migration 022). The ADD COLUMN lines were generated
-- programmatically from the CREATE TABLE definitions, not typed by hand.
--
-- IMPORTANT FOR FUTURE CHANGES — read this before adding a column:
-- 1. A NEW column with NOT NULL and no DEFAULT breaks on a table that
--    already has rows (ALTER TABLE can't invent a value). Always give new
--    columns a DEFAULT, or make them NULLable.
-- 2. AFTER clauses are deliberately NOT used on the ADD COLUMN lines (new
--    columns land at the end) — this avoids ordering dependencies between
--    statements in this file.
-- 3. Add a new column by putting it BOTH in the relevant CREATE TABLE
--    above (for fresh installs) AND as a separate ADD COLUMN IF NOT
--    EXISTS line below (for existing installs) — both are needed, they
--    don't cover each other automatically.
-- 4. This file is NOT suitable for one-time, non-idempotent data
--    corrections (like the former migration 007's UTC-to-local-time
--    fix) — such corrections must never re-run on every startup. In that
--    case, design a separate mechanism (e.g. a condition on the data
--    itself) before adding anything like that here.
--

-- p_v1.1: Correcties na controle tegen de daadwerkelijke historische
-- migratiebestanden (001-022, die Ludo alsnog aanleverde). Twee
-- concrete gaten in de p_v1.0 ADD-COLUMN-only-aanpak zijn gedicht:
-- 1. `battery_efficiency_pct` kreeg zijn default ooit via migratie 003
--    met MODIFY COLUMN, niet ADD COLUMN — een ADD COLUMN IF NOT EXISTS
--    is dan een no-op op een database die de kolom al met de oude
--    default (90.00) heeft. Toegevoegd: één gerichte MODIFY COLUMN.
-- 2. `price_profile` werd in migratie 017 verwijderd (DROP TABLE) — een
--    installatie die 'm nog heeft, hield 'm anders als ongebruikte
--    rommel. Toegevoegd: DROP TABLE IF EXISTS.
--
-- BEWUSTE KEUZE: geen blanket MODIFY COLUMN voor alle 211 kolommen. Dat
-- zou elke startup ~211 extra ALTER-statements uitvoeren op tabellen die
-- na maanden/jaren duizenden rijen kunnen bevatten (optimizer_schedule,
-- energy_prices, solar_production) — een reëel lock/performance-risico
-- voor iets dat vrijwel altijd een no-op is. In plaats daarvan: voeg een
-- gerichte MODIFY COLUMN toe zodra je bewust een DEFAULT/type van een
-- BESTAANDE kolom wijzigt (niet bij het toevoegen van een nieuwe kolom —
-- daar volstaat ADD COLUMN IF NOT EXISTS).
--
-- BEKENDE, BEWUST GEACCEPTEERDE GRENS van dit hele bestand: het gaat
-- ervan uit dat elke installatie al minstens op het niveau van de
-- voormalige migratie 017 staat (kwartier-slots i.p.v. hele uren,
-- price_profile al verwijderd). Twee dingen kan een declaratief
-- schema-bestand namelijk principieel niet reconstrueren:
--   - De volledige tabel-hernoeming + datamigratie van migratie 015
--     (hour_of_day -> slot_of_day, met kwartier-verviervoudiging van
--     bestaande rijen) — dat vereist SELECT+INSERT+RENAME+DROP, geen
--     kolom-bestaan-check.
--   - De exacte backfill-betekenis van migratie 018
--     (price_sell_per_kwh = price_per_kwh voor bestaande rijen). Dit
--     bestand voegt de kolom toe met DEFAULT 0.00000 — geen crash, maar
--     op een hypothetische installatie van vóór migratie 018 zou dat een
--     stille datafout zijn (verkoopprijs 0 i.p.v. gelijk aan de
--     koopprijs).
-- Voor Ludo's eigen, huidige installatie (al ver voorbij beide punten)
-- verandert dit niets. Dit is puur relevant mocht ooit een zeer oude
-- back-up (van vóór eind juli 2026) teruggezet worden — dat kan dan niet
-- via dit bestand alleen correct bijgewerkt worden.
--
-- p_v1.1: Corrections after checking against the actual historical
-- migration files (001-022, which Ludo supplied afterwards). Two
-- concrete gaps in the p_v1.0 ADD-COLUMN-only approach have been closed:
-- 1. `battery_efficiency_pct` originally got its default via migration
--    003's MODIFY COLUMN, not ADD COLUMN — an ADD COLUMN IF NOT EXISTS
--    is a no-op on a database that already has the column with the old
--    default (90.00). Added: one targeted MODIFY COLUMN.
-- 2. `price_profile` was removed (DROP TABLE) in migration 017 — an
--    installation that still has it would otherwise keep it as unused
--    clutter. Added: DROP TABLE IF EXISTS.
--
-- DELIBERATE CHOICE: no blanket MODIFY COLUMN for all 211 columns. That
-- would run ~211 extra ALTER statements on every startup against tables
-- that can hold thousands of rows after months/years
-- (optimizer_schedule, energy_prices, solar_production) — a real lock/
-- performance risk for something that's almost always a no-op. Instead:
-- add a targeted MODIFY COLUMN whenever you deliberately change an
-- EXISTING column's DEFAULT/type (not when adding a new column — ADD
-- COLUMN IF NOT EXISTS is sufficient for that).
--
-- KNOWN, DELIBERATELY ACCEPTED LIMIT of this entire file: it assumes
-- every installation is already at least at the level of the former
-- migration 017 (quarter-hour slots instead of whole hours,
-- price_profile already removed). A declarative schema file cannot, in
-- principle, reconstruct two things:
--   - Migration 015's full table rename + data migration (hour_of_day ->
--     slot_of_day, quadrupling existing rows into quarters) — that
--     requires SELECT+INSERT+RENAME+DROP, not a column-existence check.
--   - Migration 018's exact backfill semantics (price_sell_per_kwh =
--     price_per_kwh for existing rows). This file adds the column with
--     DEFAULT 0.00000 instead — no crash, but on a hypothetical
--     installation from before migration 018 that would be a silent
--     data error (sell price 0 instead of equal to the buy price).
-- For Ludo's own, current installation (well past both points) this
-- changes nothing. This only matters if a very old backup (from before
-- late July 2026) were ever restored — that could not be correctly
-- brought up to date via this file alone.
--


-- Tabellen aanmaken indien ze nog niet bestaan (verse installatie in één keer)
-- Create tables if they don't exist yet (fresh install in one go)

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
    `schedule_interval_minutes`       SMALLINT      NOT NULL DEFAULT 15
        COMMENT 'Schema-tijdstap in minuten / Schedule time step in minutes',
    `has_offgrid_switch`              TINYINT(1)    NOT NULL DEFAULT 0
        COMMENT 'Off-grid schakeling aanwezig / Off-grid switching present',
    `solar_reserve_strategy`          ENUM('block', 'throttle') NOT NULL DEFAULT 'throttle'
        COMMENT 'Strategie voor batterijruimte-reservering vóór negatief exportprijsvenster: block (A) of throttle (B) / Strategy for reserving battery capacity ahead of a negative export price window: block (A) or throttle (B)',
    `offgrid_reserve_high_pct`        DECIMAL(5,2)  NOT NULL DEFAULT 10.00
        COMMENT 'SoC-ondergrens overdag (%) / SoC floor during the day (%)',
    `offgrid_reserve_low_pct`         DECIMAL(5,2)  NOT NULL DEFAULT 5.00
        COMMENT 'SoC-ondergrens s nachts (%) / SoC floor during the night (%)',
    `offgrid_night_threshold_pct`     DECIMAL(5,2)  NOT NULL DEFAULT 50.00
        COMMENT 'Drempel nachtverbruik als % van daggemiddelde / Night consumption threshold as % of daily average',
    `offgrid_night_confirm_slots`     SMALLINT      NOT NULL DEFAULT 8
        COMMENT 'Aantal opeenvolgende slots onder drempel voor "begin nacht" / Consecutive slots below threshold to confirm "start of night"',
    `offgrid_primary_entity_id`       VARCHAR(256)  DEFAULT NULL
        COMMENT 'Primaire detectie-entiteit / Primary detection entity',
    `offgrid_primary_off_value`       VARCHAR(64)   NOT NULL DEFAULT 'off'
        COMMENT 'Waarde die "off-grid" betekent / Value meaning "off-grid"',
    `offgrid_fallback_entity_id`      VARCHAR(256)  DEFAULT NULL
        COMMENT 'Terugval-entiteit (bijv. P1-meter) / Fallback entity (e.g. P1 meter)',
    `offgrid_alarm_entity_id`         VARCHAR(256)  NOT NULL DEFAULT 'binary_sensor.ha_energy_optimizer_offgrid'
        COMMENT 'Terug te schrijven alarm-entiteit / Alarm entity written back to HA',
    `offgrid_active`                  TINYINT(1)    NOT NULL DEFAULT 0
        COMMENT 'Huidige gedetecteerde off-grid status / Current detected off-grid status',
    `offgrid_last_checked_at`         DATETIME      DEFAULT NULL
        COMMENT 'Tijdstip laatste detectie-controle / Timestamp of last detection check',
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
    `price_sell_per_kwh` DECIMAL(10,5) NOT NULL DEFAULT 0.00000
        COMMENT 'Verkoopprijs (teruglevering) €/kWh / Sell (feed-in) price €/kWh',
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
    `is_solar_charge`         TINYINT(1)    NOT NULL DEFAULT 0
        COMMENT 'Laadactie (deels) uit zon-overschot / Charge action (partly) from solar surplus',
    `grid_charge_kw`          DECIMAL(6,3)  NOT NULL DEFAULT 0.000
        COMMENT 'Vermogen (kW) dat specifiek uit het net wordt geladen / Power (kW) specifically charged from the grid',
    `grid_consume_kw`         DECIMAL(6,3)  NOT NULL DEFAULT 0.000
        COMMENT 'Vermogen (kW) rechtstreeks van het net voor huisverbruik, buiten de batterij om (SoC-vloer bereikt) / Power (kW) drawn directly from the grid for household use, bypassing the battery (SoC floor reached)',
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
    `slot_of_day` TINYINT      NOT NULL COMMENT 'Kwartier-slot van de dag (0..95) / Quarter slot of day (0..95)',
    `avg_kw`      DECIMAL(6,3) NOT NULL DEFAULT 0.000 COMMENT 'Average consumption kW / Gemiddeld verbruik kW',
    `min_kw`      DECIMAL(6,3) NOT NULL DEFAULT 0.000,
    `max_kw`      DECIMAL(6,3) NOT NULL DEFAULT 0.000,
    `samples`     INT          NOT NULL DEFAULT 0 COMMENT 'Number of measurements / Aantal metingen',
    PRIMARY KEY (`id`),
    UNIQUE KEY `unique_day_slot` (`day_of_week`, `slot_of_day`)
) ENGINE=InnoDB
  COMMENT='Average energy consumption per weekday/quarter-slot / Gemiddeld verbruik per weekdag/kwartier-slot';

CREATE TABLE IF NOT EXISTS `solar_profile` (
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

CREATE TABLE IF NOT EXISTS `solar_learning` (
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

CREATE TABLE IF NOT EXISTS `consumption_learning` (
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

CREATE TABLE IF NOT EXISTS `translation_strings` (
    `string_key` VARCHAR(8)   NOT NULL COMMENT 'Sleutel bijv. RS01 / Key e.g. RS01',
    `language`   CHAR(2)      NOT NULL COMMENT 'Taalcode bijv. nl, en / Language code',
    `text`       TEXT         NOT NULL COMMENT 'Vertaalde tekst met {variabelen} / Translated text with {variables}',
    `updated_at` DATETIME     DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (`string_key`, `language`)
) ENGINE=InnoDB COMMENT='Operationele vertalingen / Operational translations';

-- Ontbrekende kolommen toevoegen op bestaande installaties (elke kolom ooit
-- toegevoegd, idempotent — op een verse installatie zijn dit allemaal no-ops
-- want de kolom bestaat al via de CREATE TABLE hierboven)
-- Add missing columns on existing installations (every column ever added,
-- idempotent — on a fresh installation these are all no-ops since the column
-- already exists via the CREATE TABLE above)

ALTER TABLE `system_config` ADD COLUMN IF NOT EXISTS `id` INT           NOT NULL AUTO_INCREMENT;
ALTER TABLE `system_config` ADD COLUMN IF NOT EXISTS `created_at` DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP;
ALTER TABLE `system_config` ADD COLUMN IF NOT EXISTS `updated_at` DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP;
ALTER TABLE `system_config` ADD COLUMN IF NOT EXISTS `latitude` DECIMAL(10,7) NOT NULL;
ALTER TABLE `system_config` ADD COLUMN IF NOT EXISTS `longitude` DECIMAL(10,7) NOT NULL;
ALTER TABLE `system_config` ADD COLUMN IF NOT EXISTS `has_grid_connection` TINYINT(1)    NOT NULL DEFAULT 1;
ALTER TABLE `system_config` ADD COLUMN IF NOT EXISTS `has_solar_panels` TINYINT(1)    NOT NULL DEFAULT 0;
ALTER TABLE `system_config` ADD COLUMN IF NOT EXISTS `has_gas` TINYINT(1)    NOT NULL DEFAULT 0;
ALTER TABLE `system_config` ADD COLUMN IF NOT EXISTS `has_district_heating` TINYINT(1)    NOT NULL DEFAULT 0;
ALTER TABLE `system_config` ADD COLUMN IF NOT EXISTS `has_battery` TINYINT(1)    NOT NULL DEFAULT 0;
ALTER TABLE `system_config` ADD COLUMN IF NOT EXISTS `battery_efficiency_pct` DECIMAL(5,2)  DEFAULT 75.00;
ALTER TABLE `system_config` ADD COLUMN IF NOT EXISTS `min_price_to_discharge` DECIMAL(8,5)  DEFAULT NULL;
ALTER TABLE `system_config` ADD COLUMN IF NOT EXISTS `max_price_to_charge` DECIMAL(8,5)  DEFAULT NULL;
ALTER TABLE `system_config` ADD COLUMN IF NOT EXISTS `price_incl_tax` TINYINT(1)    NOT NULL DEFAULT 1;
ALTER TABLE `system_config` ADD COLUMN IF NOT EXISTS `language` CHAR(2)       NOT NULL DEFAULT 'nl';
ALTER TABLE `system_config` ADD COLUMN IF NOT EXISTS `hard_min_discharge_price_excl` DECIMAL(8,5)  DEFAULT 0.05000
        COMMENT 'Harde minimale ontlaadprijs excl. BTW / Hard minimum discharge price excl. VAT';
ALTER TABLE `system_config` ADD COLUMN IF NOT EXISTS `temp_derating_threshold_c` DECIMAL(5,2)  DEFAULT 35.00
        COMMENT 'Battery temp above which power is derated / Batterijtemperatuur waarboven vermogen wordt verlaagd';
ALTER TABLE `system_config` ADD COLUMN IF NOT EXISTS `temp_derating_factor` DECIMAL(4,2)  DEFAULT 0.70
        COMMENT 'Power reduction factor when temp exceeded / Vermogensfactor bij te hoge temperatuur';
ALTER TABLE `system_config` ADD COLUMN IF NOT EXISTS `min_spread_ratio_for_discharge` DECIMAL(4,2)  DEFAULT 2.00
        COMMENT 'Min price spread ratio to trigger discharge / Min prijsspreiding voor ontladen';
ALTER TABLE `system_config` ADD COLUMN IF NOT EXISTS `discharge_near_peak_fraction` DECIMAL(4,2)  DEFAULT 0.85
        COMMENT 'Price must be within this fraction of peak / Prijs moet binnen deze fractie van piek liggen';
ALTER TABLE `system_config` ADD COLUMN IF NOT EXISTS `extreme_price_multiplier` DECIMAL(4,2)  DEFAULT 2.50
        COMMENT 'Multiple of avg price considered extreme / Veelvoud van gem. prijs dat extreem is';
ALTER TABLE `system_config` ADD COLUMN IF NOT EXISTS `negative_export_threshold_excl` DECIMAL(8,5)  DEFAULT 0.00000
        COMMENT 'Export price below which to limit export (excl. VAT) / Terugleverprijs waaronder export beperkt wordt';
ALTER TABLE `system_config` ADD COLUMN IF NOT EXISTS `notify_export_threshold_excl` DECIMAL(8,5)  DEFAULT 0.02000
        COMMENT 'Notify user when export price below this / Gebruiker melden bij lage terugleverprijs';
ALTER TABLE `system_config` ADD COLUMN IF NOT EXISTS `charge_near_cheapest_fraction` DECIMAL(4,2)  DEFAULT 1.05
        COMMENT 'Price must be within this fraction of cheapest / Prijs moet binnen deze fractie van minimum liggen';
ALTER TABLE `system_config` ADD COLUMN IF NOT EXISTS `min_sunshine_pct_for_refill` DECIMAL(5,2)  DEFAULT 40.00
        COMMENT 'Min sunshine % tomorrow to allow discharge / Min zonpercentage morgen voor ontladen';
ALTER TABLE `system_config` ADD COLUMN IF NOT EXISTS `avg_consumption_kwh` DECIMAL(6,3)  DEFAULT 0.500
        COMMENT 'Expected average hourly consumption / Verwacht gemiddeld uurverbruik';
ALTER TABLE `system_config` ADD COLUMN IF NOT EXISTS `sunrise_buffer_pct` DECIMAL(5,2)  DEFAULT 10.00
        COMMENT 'SoC buffer to keep at sunrise / SoC-buffer te bewaren bij zonsopgang';
ALTER TABLE `system_config` ADD COLUMN IF NOT EXISTS `evening_planning_time` TIME          DEFAULT '21:00:00'
        COMMENT 'Time to run evening day balance planning / Tijd voor avond dagbalansplanning';
ALTER TABLE `system_config` ADD COLUMN IF NOT EXISTS `solar_charge_threshold` DECIMAL(4,2)  NOT NULL DEFAULT 0.80
        COMMENT 'Block grid charging when expected solar >= this fraction of usable capacity / Blokkeer nettoladen als verwachte zon >= deze fractie van bruikbare capaciteit';
ALTER TABLE `system_config` ADD COLUMN IF NOT EXISTS `dashboard_colors` JSON          DEFAULT NULL
        COMMENT 'Custom chart colors as JSON / Aangepaste grafiekkleuren als JSON';
ALTER TABLE `system_config` ADD COLUMN IF NOT EXISTS `gas_price_eur_m3` DECIMAL(8,5)  DEFAULT NULL
        COMMENT 'Fixed gas price in €/m³ incl. VAT / Vaste gasprijs in €/m³ incl. BTW';
ALTER TABLE `system_config` ADD COLUMN IF NOT EXISTS `gas_price_entity_id` VARCHAR(256)  DEFAULT NULL
        COMMENT 'Optional HA entity for dynamic gas price / Optionele HA-entiteit voor dynamische gasprijs';
ALTER TABLE `system_config` ADD COLUMN IF NOT EXISTS `heating_price_eur_gj` DECIMAL(8,5)  DEFAULT NULL
        COMMENT 'Fixed district heating price in €/GJ incl. VAT / Vaste stadsverwarmingprijs in €/GJ incl. BTW';
ALTER TABLE `system_config` ADD COLUMN IF NOT EXISTS `heating_price_entity_id` VARCHAR(256)  DEFAULT NULL
        COMMENT 'Optional HA entity for dynamic heating price / Optionele HA-entiteit voor dynamische stadsverwarmingprijs';
ALTER TABLE `system_config` ADD COLUMN IF NOT EXISTS `schedule_interval_minutes` SMALLINT      NOT NULL DEFAULT 15
        COMMENT 'Schema-tijdstap in minuten / Schedule time step in minutes';
ALTER TABLE `system_config` ADD COLUMN IF NOT EXISTS `has_offgrid_switch` TINYINT(1)    NOT NULL DEFAULT 0
        COMMENT 'Off-grid schakeling aanwezig / Off-grid switching present';
ALTER TABLE `system_config` ADD COLUMN IF NOT EXISTS `solar_reserve_strategy` ENUM('block', 'throttle') NOT NULL DEFAULT 'throttle'
        COMMENT 'Strategie voor batterijruimte-reservering vóór negatief exportprijsvenster: block (A) of throttle (B) / Strategy for reserving battery capacity ahead of a negative export price window: block (A) or throttle (B)';
ALTER TABLE `system_config` ADD COLUMN IF NOT EXISTS `offgrid_reserve_high_pct` DECIMAL(5,2)  NOT NULL DEFAULT 10.00
        COMMENT 'SoC-ondergrens overdag (%) / SoC floor during the day (%)';
ALTER TABLE `system_config` ADD COLUMN IF NOT EXISTS `offgrid_reserve_low_pct` DECIMAL(5,2)  NOT NULL DEFAULT 5.00
        COMMENT 'SoC-ondergrens s nachts (%) / SoC floor during the night (%)';
ALTER TABLE `system_config` ADD COLUMN IF NOT EXISTS `offgrid_night_threshold_pct` DECIMAL(5,2)  NOT NULL DEFAULT 50.00
        COMMENT 'Drempel nachtverbruik als % van daggemiddelde / Night consumption threshold as % of daily average';
ALTER TABLE `system_config` ADD COLUMN IF NOT EXISTS `offgrid_night_confirm_slots` SMALLINT      NOT NULL DEFAULT 8
        COMMENT 'Aantal opeenvolgende slots onder drempel voor "begin nacht" / Consecutive slots below threshold to confirm "start of night"';
ALTER TABLE `system_config` ADD COLUMN IF NOT EXISTS `offgrid_primary_entity_id` VARCHAR(256)  DEFAULT NULL
        COMMENT 'Primaire detectie-entiteit / Primary detection entity';
ALTER TABLE `system_config` ADD COLUMN IF NOT EXISTS `offgrid_primary_off_value` VARCHAR(64)   NOT NULL DEFAULT 'off'
        COMMENT 'Waarde die "off-grid" betekent / Value meaning "off-grid"';
ALTER TABLE `system_config` ADD COLUMN IF NOT EXISTS `offgrid_fallback_entity_id` VARCHAR(256)  DEFAULT NULL
        COMMENT 'Terugval-entiteit (bijv. P1-meter) / Fallback entity (e.g. P1 meter)';
ALTER TABLE `system_config` ADD COLUMN IF NOT EXISTS `offgrid_alarm_entity_id` VARCHAR(256)  NOT NULL DEFAULT 'binary_sensor.ha_energy_optimizer_offgrid'
        COMMENT 'Terug te schrijven alarm-entiteit / Alarm entity written back to HA';
ALTER TABLE `system_config` ADD COLUMN IF NOT EXISTS `offgrid_active` TINYINT(1)    NOT NULL DEFAULT 0
        COMMENT 'Huidige gedetecteerde off-grid status / Current detected off-grid status';
ALTER TABLE `system_config` ADD COLUMN IF NOT EXISTS `offgrid_last_checked_at` DATETIME      DEFAULT NULL
        COMMENT 'Tijdstip laatste detectie-controle / Timestamp of last detection check';
ALTER TABLE `inverter_info` ADD COLUMN IF NOT EXISTS `id` INT         NOT NULL AUTO_INCREMENT;
ALTER TABLE `inverter_info` ADD COLUMN IF NOT EXISTS `created_at` DATETIME    NOT NULL DEFAULT CURRENT_TIMESTAMP;
ALTER TABLE `inverter_info` ADD COLUMN IF NOT EXISTS `updated_at` DATETIME    NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP;
ALTER TABLE `inverter_info` ADD COLUMN IF NOT EXISTS `brand` VARCHAR(50);
ALTER TABLE `inverter_info` ADD COLUMN IF NOT EXISTS `model` VARCHAR(50);
ALTER TABLE `inverter_info` ADD COLUMN IF NOT EXISTS `supplier` VARCHAR(50);
ALTER TABLE `inverter_info` ADD COLUMN IF NOT EXISTS `driver` VARCHAR(50) NOT NULL;
ALTER TABLE `inverter_info` ADD COLUMN IF NOT EXISTS `driver_config` JSON;
ALTER TABLE `inverter_info` ADD COLUMN IF NOT EXISTS `installed_on` DATE;
ALTER TABLE `inverter_info` ADD COLUMN IF NOT EXISTS `max_charge_kw` DECIMAL(8,3);
ALTER TABLE `inverter_info` ADD COLUMN IF NOT EXISTS `max_discharge_kw` DECIMAL(8,3);
ALTER TABLE `inverter_info` ADD COLUMN IF NOT EXISTS `warranty_years` INT;
ALTER TABLE `solar_info` ADD COLUMN IF NOT EXISTS `id` INT          NOT NULL AUTO_INCREMENT;
ALTER TABLE `solar_info` ADD COLUMN IF NOT EXISTS `created_at` DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP;
ALTER TABLE `solar_info` ADD COLUMN IF NOT EXISTS `updated_at` DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP;
ALTER TABLE `solar_info` ADD COLUMN IF NOT EXISTS `panel_brand` VARCHAR(50);
ALTER TABLE `solar_info` ADD COLUMN IF NOT EXISTS `panel_model` VARCHAR(50);
ALTER TABLE `solar_info` ADD COLUMN IF NOT EXISTS `panel_supplier` VARCHAR(50);
ALTER TABLE `solar_info` ADD COLUMN IF NOT EXISTS `number_of_panels` INT;
ALTER TABLE `solar_info` ADD COLUMN IF NOT EXISTS `panel_max_power_wp` DECIMAL(8,2);
ALTER TABLE `solar_info` ADD COLUMN IF NOT EXISTS `total_max_power_kw` DECIMAL(8,3);
ALTER TABLE `solar_info` ADD COLUMN IF NOT EXISTS `installed_on` DATE;
ALTER TABLE `solar_info` ADD COLUMN IF NOT EXISTS `degradation_pct_per_year` DECIMAL(5,2);
ALTER TABLE `solar_info` ADD COLUMN IF NOT EXISTS `orientation_degrees` INT;
ALTER TABLE `solar_info` ADD COLUMN IF NOT EXISTS `tilt_degrees` INT;
ALTER TABLE `battery_info` ADD COLUMN IF NOT EXISTS `id` INT         NOT NULL AUTO_INCREMENT;
ALTER TABLE `battery_info` ADD COLUMN IF NOT EXISTS `created_at` DATETIME    NOT NULL DEFAULT CURRENT_TIMESTAMP;
ALTER TABLE `battery_info` ADD COLUMN IF NOT EXISTS `updated_at` DATETIME    NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP;
ALTER TABLE `battery_info` ADD COLUMN IF NOT EXISTS `brand` VARCHAR(50);
ALTER TABLE `battery_info` ADD COLUMN IF NOT EXISTS `model` VARCHAR(50);
ALTER TABLE `battery_info` ADD COLUMN IF NOT EXISTS `supplier` VARCHAR(50);
ALTER TABLE `battery_info` ADD COLUMN IF NOT EXISTS `installed_on` DATE;
ALTER TABLE `battery_info` ADD COLUMN IF NOT EXISTS `capacity_kwh` DECIMAL(8,3);
ALTER TABLE `battery_info` ADD COLUMN IF NOT EXISTS `usable_capacity_kwh` DECIMAL(8,3);
ALTER TABLE `battery_info` ADD COLUMN IF NOT EXISTS `max_charge_kw` DECIMAL(8,3);
ALTER TABLE `battery_info` ADD COLUMN IF NOT EXISTS `max_discharge_kw` DECIMAL(8,3);
ALTER TABLE `battery_info` ADD COLUMN IF NOT EXISTS `min_soc_pct` DECIMAL(5,2) DEFAULT 10.00;
ALTER TABLE `battery_info` ADD COLUMN IF NOT EXISTS `max_soc_pct` DECIMAL(5,2) DEFAULT 95.00;
ALTER TABLE `battery_info` ADD COLUMN IF NOT EXISTS `warranty_years` INT;
ALTER TABLE `battery_info` ADD COLUMN IF NOT EXISTS `cycle_count_at_install` INT          DEFAULT 0;
ALTER TABLE `battery_info` ADD COLUMN IF NOT EXISTS `cost_eur` DECIMAL(10,2) DEFAULT NULL
        COMMENT 'Purchase price of battery / Aanschafprijs batterij';
ALTER TABLE `battery_info` ADD COLUMN IF NOT EXISTS `expected_cycles` INT           DEFAULT NULL
        COMMENT 'Expected lifetime charge cycles / Verwachte levensduur laadcycli';
ALTER TABLE `battery_info` ADD COLUMN IF NOT EXISTS `working_charge_kw` DECIMAL(8,3)  DEFAULT NULL
        COMMENT 'Preferred charge power (< max for battery health) / Voorkeurslaadvermogen';
ALTER TABLE `battery_info` ADD COLUMN IF NOT EXISTS `working_discharge_kw` DECIMAL(8,3)  DEFAULT NULL
        COMMENT 'Preferred discharge power (< max for battery health) / Voorkeursontlaadvermogen';
ALTER TABLE `provider_config` ADD COLUMN IF NOT EXISTS `id` INT         NOT NULL AUTO_INCREMENT;
ALTER TABLE `provider_config` ADD COLUMN IF NOT EXISTS `created_at` DATETIME    NOT NULL DEFAULT CURRENT_TIMESTAMP;
ALTER TABLE `provider_config` ADD COLUMN IF NOT EXISTS `updated_at` DATETIME    NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP;
ALTER TABLE `provider_config` ADD COLUMN IF NOT EXISTS `energy_type` ENUM('electricity','gas') NOT NULL;
ALTER TABLE `provider_config` ADD COLUMN IF NOT EXISTS `provider_driver` VARCHAR(50) NOT NULL;
ALTER TABLE `provider_config` ADD COLUMN IF NOT EXISTS `driver_config` JSON;
ALTER TABLE `provider_config` ADD COLUMN IF NOT EXISTS `is_active` TINYINT(1)  NOT NULL DEFAULT 1;
ALTER TABLE `ha_entity_map` ADD COLUMN IF NOT EXISTS `id` INT          NOT NULL AUTO_INCREMENT;
ALTER TABLE `ha_entity_map` ADD COLUMN IF NOT EXISTS `created_at` DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP;
ALTER TABLE `ha_entity_map` ADD COLUMN IF NOT EXISTS `updated_at` DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP;
ALTER TABLE `ha_entity_map` ADD COLUMN IF NOT EXISTS `internal_name` VARCHAR(100) NOT NULL UNIQUE;
ALTER TABLE `ha_entity_map` ADD COLUMN IF NOT EXISTS `entity_id` VARCHAR(256) NOT NULL;
ALTER TABLE `ha_entity_map` ADD COLUMN IF NOT EXISTS `source` VARCHAR(50);
ALTER TABLE `ha_entity_map` ADD COLUMN IF NOT EXISTS `unit` VARCHAR(20);
ALTER TABLE `ha_entity_map` ADD COLUMN IF NOT EXISTS `description` VARCHAR(255);
ALTER TABLE `energy_prices` ADD COLUMN IF NOT EXISTS `id` INT           NOT NULL AUTO_INCREMENT;
ALTER TABLE `energy_prices` ADD COLUMN IF NOT EXISTS `created_at` DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP;
ALTER TABLE `energy_prices` ADD COLUMN IF NOT EXISTS `price_hour` DATETIME      NOT NULL;
ALTER TABLE `energy_prices` ADD COLUMN IF NOT EXISTS `energy_type` ENUM('electricity','gas') NOT NULL;
ALTER TABLE `energy_prices` ADD COLUMN IF NOT EXISTS `price_per_kwh` DECIMAL(10,5) NOT NULL;
ALTER TABLE `energy_prices` ADD COLUMN IF NOT EXISTS `price_sell_per_kwh` DECIMAL(10,5) NOT NULL DEFAULT 0.00000
        COMMENT 'Verkoopprijs (teruglevering) €/kWh / Sell (feed-in) price €/kWh';
ALTER TABLE `energy_prices` ADD COLUMN IF NOT EXISTS `price_incl_tax` TINYINT(1)    NOT NULL DEFAULT 1;
ALTER TABLE `energy_prices` ADD COLUMN IF NOT EXISTS `source` VARCHAR(50);
ALTER TABLE `solar_production` ADD COLUMN IF NOT EXISTS `id` INT          NOT NULL AUTO_INCREMENT;
ALTER TABLE `solar_production` ADD COLUMN IF NOT EXISTS `created_at` DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP;
ALTER TABLE `solar_production` ADD COLUMN IF NOT EXISTS `measured_at` DATETIME     NOT NULL;
ALTER TABLE `solar_production` ADD COLUMN IF NOT EXISTS `power_kw` DECIMAL(8,3) NOT NULL;
ALTER TABLE `solar_production` ADD COLUMN IF NOT EXISTS `energy_kwh` DECIMAL(8,3);
ALTER TABLE `home_consumption` ADD COLUMN IF NOT EXISTS `id` INT          NOT NULL AUTO_INCREMENT;
ALTER TABLE `home_consumption` ADD COLUMN IF NOT EXISTS `created_at` DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP;
ALTER TABLE `home_consumption` ADD COLUMN IF NOT EXISTS `measured_at` DATETIME     NOT NULL;
ALTER TABLE `home_consumption` ADD COLUMN IF NOT EXISTS `grid_import_kw` DECIMAL(8,3);
ALTER TABLE `home_consumption` ADD COLUMN IF NOT EXISTS `grid_export_kw` DECIMAL(8,3);
ALTER TABLE `home_consumption` ADD COLUMN IF NOT EXISTS `total_consumption_kw` DECIMAL(8,3);
ALTER TABLE `home_consumption` ADD COLUMN IF NOT EXISTS `gas_m3` DECIMAL(8,4);
ALTER TABLE `battery_status` ADD COLUMN IF NOT EXISTS `id` INT          NOT NULL AUTO_INCREMENT;
ALTER TABLE `battery_status` ADD COLUMN IF NOT EXISTS `created_at` DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP;
ALTER TABLE `battery_status` ADD COLUMN IF NOT EXISTS `measured_at` DATETIME     NOT NULL;
ALTER TABLE `battery_status` ADD COLUMN IF NOT EXISTS `soc_pct` DECIMAL(5,2);
ALTER TABLE `battery_status` ADD COLUMN IF NOT EXISTS `power_kw` DECIMAL(8,3);
ALTER TABLE `battery_status` ADD COLUMN IF NOT EXISTS `voltage_v` DECIMAL(8,2);
ALTER TABLE `battery_status` ADD COLUMN IF NOT EXISTS `temperature_c` DECIMAL(5,2);
ALTER TABLE `battery_status` ADD COLUMN IF NOT EXISTS `energy_charged_kwh` DECIMAL(8,3);
ALTER TABLE `battery_status` ADD COLUMN IF NOT EXISTS `energy_discharged_kwh` DECIMAL(8,3);
ALTER TABLE `battery_status` ADD COLUMN IF NOT EXISTS `cycle_count` INT;
ALTER TABLE `weather_forecast` ADD COLUMN IF NOT EXISTS `id` INT           NOT NULL AUTO_INCREMENT;
ALTER TABLE `weather_forecast` ADD COLUMN IF NOT EXISTS `created_at` DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP;
ALTER TABLE `weather_forecast` ADD COLUMN IF NOT EXISTS `forecast_for` DATETIME      NOT NULL;
ALTER TABLE `weather_forecast` ADD COLUMN IF NOT EXISTS `sun_rise` TIME;
ALTER TABLE `weather_forecast` ADD COLUMN IF NOT EXISTS `sun_set` TIME;
ALTER TABLE `weather_forecast` ADD COLUMN IF NOT EXISTS `sunshine_pct` DECIMAL(5,2);
ALTER TABLE `weather_forecast` ADD COLUMN IF NOT EXISTS `cloud_cover_pct` DECIMAL(5,2);
ALTER TABLE `weather_forecast` ADD COLUMN IF NOT EXISTS `rain_mm` DECIMAL(6,2);
ALTER TABLE `weather_forecast` ADD COLUMN IF NOT EXISTS `wind_speed_ms` DECIMAL(6,2);
ALTER TABLE `weather_forecast` ADD COLUMN IF NOT EXISTS `wind_direction_deg` INT;
ALTER TABLE `weather_forecast` ADD COLUMN IF NOT EXISTS `temperature_c` DECIMAL(5,2);
ALTER TABLE `weather_forecast` ADD COLUMN IF NOT EXISTS `solar_irradiance_wm2` DECIMAL(8,2);
ALTER TABLE `weather_forecast` ADD COLUMN IF NOT EXISTS `source` VARCHAR(50);
ALTER TABLE `optimizer_schedule` ADD COLUMN IF NOT EXISTS `id` INT           NOT NULL AUTO_INCREMENT;
ALTER TABLE `optimizer_schedule` ADD COLUMN IF NOT EXISTS `created_at` DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP;
ALTER TABLE `optimizer_schedule` ADD COLUMN IF NOT EXISTS `schedule_for` DATETIME      NOT NULL;
ALTER TABLE `optimizer_schedule` ADD COLUMN IF NOT EXISTS `action` ENUM('charge','discharge','idle','self_consume') NOT NULL;
ALTER TABLE `optimizer_schedule` ADD COLUMN IF NOT EXISTS `target_power_kw` DECIMAL(8,3);
ALTER TABLE `optimizer_schedule` ADD COLUMN IF NOT EXISTS `target_soc_pct` DECIMAL(5,2);
ALTER TABLE `optimizer_schedule` ADD COLUMN IF NOT EXISTS `expected_price` DECIMAL(10,5);
ALTER TABLE `optimizer_schedule` ADD COLUMN IF NOT EXISTS `expected_solar_kw` DECIMAL(8,3);
ALTER TABLE `optimizer_schedule` ADD COLUMN IF NOT EXISTS `expected_consumption_kw` DECIMAL(8,3);
ALTER TABLE `optimizer_schedule` ADD COLUMN IF NOT EXISTS `expected_saving` DECIMAL(8,5);
ALTER TABLE `optimizer_schedule` ADD COLUMN IF NOT EXISTS `expected_cost` DECIMAL(10,5) DEFAULT 0
        COMMENT 'Cost of grid charging this hour, excl. VAT / Kosten van netladen dit uur, excl. BTW';
ALTER TABLE `optimizer_schedule` ADD COLUMN IF NOT EXISTS `reason` VARCHAR(255);
ALTER TABLE `optimizer_schedule` ADD COLUMN IF NOT EXISTS `reason_key` VARCHAR(8)    DEFAULT NULL
        COMMENT 'Vertaalsleutel bijv. RS01 / Translation key e.g. RS01';
ALTER TABLE `optimizer_schedule` ADD COLUMN IF NOT EXISTS `reason_params` JSON          DEFAULT NULL
        COMMENT 'Parameters voor vertaling bijv. {"price": 0.12} / Translation params';
ALTER TABLE `optimizer_schedule` ADD COLUMN IF NOT EXISTS `executed` TINYINT(1)    NOT NULL DEFAULT 0;
ALTER TABLE `optimizer_schedule` ADD COLUMN IF NOT EXISTS `executed_at` DATETIME;
ALTER TABLE `optimizer_schedule` ADD COLUMN IF NOT EXISTS `is_solar_charge` TINYINT(1)    NOT NULL DEFAULT 0
        COMMENT 'Laadactie (deels) uit zon-overschot / Charge action (partly) from solar surplus';
ALTER TABLE `optimizer_schedule` ADD COLUMN IF NOT EXISTS `grid_charge_kw` DECIMAL(6,3)  NOT NULL DEFAULT 0.000
        COMMENT 'Vermogen (kW) dat specifiek uit het net wordt geladen / Power (kW) specifically charged from the grid';
ALTER TABLE `optimizer_schedule` ADD COLUMN IF NOT EXISTS `grid_consume_kw` DECIMAL(6,3)  NOT NULL DEFAULT 0.000
        COMMENT 'Vermogen (kW) rechtstreeks van het net voor huisverbruik, buiten de batterij om (SoC-vloer bereikt) / Power (kW) drawn directly from the grid for household use, bypassing the battery (SoC floor reached)';
ALTER TABLE `report_log` ADD COLUMN IF NOT EXISTS `id` INT      NOT NULL AUTO_INCREMENT;
ALTER TABLE `report_log` ADD COLUMN IF NOT EXISTS `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP;
ALTER TABLE `report_log` ADD COLUMN IF NOT EXISTS `report_type` ENUM('info','daily','warning','error') NOT NULL DEFAULT 'info';
ALTER TABLE `report_log` ADD COLUMN IF NOT EXISTS `category` VARCHAR(50);
ALTER TABLE `report_log` ADD COLUMN IF NOT EXISTS `message` TEXT     NOT NULL;
ALTER TABLE `report_log` ADD COLUMN IF NOT EXISTS `notified` TINYINT(1) NOT NULL DEFAULT 0;
ALTER TABLE `report_log` ADD COLUMN IF NOT EXISTS `notified_at` DATETIME;
ALTER TABLE `consumption_profile` ADD COLUMN IF NOT EXISTS `id` INT          NOT NULL AUTO_INCREMENT;
ALTER TABLE `consumption_profile` ADD COLUMN IF NOT EXISTS `updated_at` DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP;
ALTER TABLE `consumption_profile` ADD COLUMN IF NOT EXISTS `day_of_week` TINYINT      NOT NULL COMMENT '0=Monday/maandag, 6=Sunday/zondag';
ALTER TABLE `consumption_profile` ADD COLUMN IF NOT EXISTS `slot_of_day` TINYINT      NOT NULL COMMENT 'Kwartier-slot van de dag (0..95) / Quarter slot of day (0..95)';
ALTER TABLE `consumption_profile` ADD COLUMN IF NOT EXISTS `avg_kw` DECIMAL(6,3) NOT NULL DEFAULT 0.000 COMMENT 'Average consumption kW / Gemiddeld verbruik kW';
ALTER TABLE `consumption_profile` ADD COLUMN IF NOT EXISTS `min_kw` DECIMAL(6,3) NOT NULL DEFAULT 0.000;
ALTER TABLE `consumption_profile` ADD COLUMN IF NOT EXISTS `max_kw` DECIMAL(6,3) NOT NULL DEFAULT 0.000;
ALTER TABLE `consumption_profile` ADD COLUMN IF NOT EXISTS `samples` INT          NOT NULL DEFAULT 0 COMMENT 'Number of measurements / Aantal metingen';
ALTER TABLE `solar_profile` ADD COLUMN IF NOT EXISTS `id` INT          NOT NULL AUTO_INCREMENT;
ALTER TABLE `solar_profile` ADD COLUMN IF NOT EXISTS `updated_at` DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP;
ALTER TABLE `solar_profile` ADD COLUMN IF NOT EXISTS `month` TINYINT      NOT NULL COMMENT '1=January/januari, 12=December/december';
ALTER TABLE `solar_profile` ADD COLUMN IF NOT EXISTS `slot_of_day` TINYINT      NOT NULL COMMENT 'Kwartier-slot van de dag (0..95) / Quarter slot of day (0..95)';
ALTER TABLE `solar_profile` ADD COLUMN IF NOT EXISTS `avg_kw` DECIMAL(6,3) NOT NULL DEFAULT 0.000 COMMENT 'Average solar output kW / Gemiddelde zonne-opbrengst kW';
ALTER TABLE `solar_profile` ADD COLUMN IF NOT EXISTS `max_kw` DECIMAL(6,3) NOT NULL DEFAULT 0.000;
ALTER TABLE `solar_profile` ADD COLUMN IF NOT EXISTS `avg_sunshine_pct` DECIMAL(5,2)          DEFAULT NULL COMMENT 'Average sunshine percentage / Gemiddeld zonpercentage';
ALTER TABLE `solar_profile` ADD COLUMN IF NOT EXISTS `samples` INT          NOT NULL DEFAULT 0;
ALTER TABLE `solar_learning` ADD COLUMN IF NOT EXISTS `slot_of_day` TINYINT      NOT NULL COMMENT 'Kwartier-slot van de dag (0..95) / Quarter slot of day (0..95)';
ALTER TABLE `solar_learning` ADD COLUMN IF NOT EXISTS `week_block` TINYINT      NOT NULL COMMENT 'Blok van 2 weken (1..26) / 2-week block (1..26)';
ALTER TABLE `solar_learning` ADD COLUMN IF NOT EXISTS `irradiance_low` DECIMAL(8,3) NOT NULL DEFAULT 0 COMMENT 'Laagste gemeten instraling W/m² / Lowest measured irradiance W/m²';
ALTER TABLE `solar_learning` ADD COLUMN IF NOT EXISTS `irradiance_high` DECIMAL(8,3) NOT NULL DEFAULT 0 COMMENT 'Hoogste gemeten instraling W/m² / Highest measured irradiance W/m²';
ALTER TABLE `solar_learning` ADD COLUMN IF NOT EXISTS `solar_kwh_low` DECIMAL(8,4) NOT NULL DEFAULT 0 COMMENT 'Laagste gemeten opbrengst kWh / Lowest measured yield kWh';
ALTER TABLE `solar_learning` ADD COLUMN IF NOT EXISTS `solar_kwh_high` DECIMAL(8,4) NOT NULL DEFAULT 0 COMMENT 'Hoogste gemeten opbrengst kWh / Highest measured yield kWh';
ALTER TABLE `solar_learning` ADD COLUMN IF NOT EXISTS `sample_count` INT          NOT NULL DEFAULT 0 COMMENT 'Aantal metingen / Number of measurements';
ALTER TABLE `solar_learning` ADD COLUMN IF NOT EXISTS `updated_at` DATETIME     DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP;
ALTER TABLE `consumption_learning` ADD COLUMN IF NOT EXISTS `month_of_year` TINYINT      NOT NULL COMMENT 'Maand (1..12) / Month (1..12)';
ALTER TABLE `consumption_learning` ADD COLUMN IF NOT EXISTS `day_of_week` TINYINT      NOT NULL COMMENT 'Dag van de week (0=ma..6=zo) / Day of week (0=Mon..6=Sun)';
ALTER TABLE `consumption_learning` ADD COLUMN IF NOT EXISTS `slot_of_day` TINYINT      NOT NULL COMMENT 'Kwartier-slot van de dag (0..95) / Quarter slot of day (0..95)';
ALTER TABLE `consumption_learning` ADD COLUMN IF NOT EXISTS `kwh_avg` DECIMAL(8,4) NOT NULL DEFAULT 0 COMMENT 'Rollend gewogen gemiddelde kWh / Rolling weighted average kWh';
ALTER TABLE `consumption_learning` ADD COLUMN IF NOT EXISTS `kwh_min` DECIMAL(8,4) NOT NULL DEFAULT 0 COMMENT 'Laagste gemeten kWh / Lowest measured kWh';
ALTER TABLE `consumption_learning` ADD COLUMN IF NOT EXISTS `kwh_max` DECIMAL(8,4) NOT NULL DEFAULT 0 COMMENT 'Hoogste gemeten kWh / Highest measured kWh';
ALTER TABLE `consumption_learning` ADD COLUMN IF NOT EXISTS `sample_count` INT          NOT NULL DEFAULT 0 COMMENT 'Aantal metingen (de deler) / Number of measurements (the divisor)';
ALTER TABLE `consumption_learning` ADD COLUMN IF NOT EXISTS `updated_at` DATETIME     DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP;
ALTER TABLE `translation_strings` ADD COLUMN IF NOT EXISTS `string_key` VARCHAR(8)   NOT NULL COMMENT 'Sleutel bijv. RS01 / Key e.g. RS01';
ALTER TABLE `translation_strings` ADD COLUMN IF NOT EXISTS `language` CHAR(2)      NOT NULL COMMENT 'Taalcode bijv. nl, en / Language code';
ALTER TABLE `translation_strings` ADD COLUMN IF NOT EXISTS `text` TEXT         NOT NULL COMMENT 'Vertaalde tekst met {variabelen} / Translated text with {variables}';
ALTER TABLE `translation_strings` ADD COLUMN IF NOT EXISTS `updated_at` DATETIME     DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP;


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

-- Gerichte reparaties voor kolommen/tabellen die ooit via MODIFY/DROP zijn
-- gewijzigd i.p.v. via ADD COLUMN — zie header (p_v1.1) voor de uitleg
-- waarom dit gericht blijft i.p.v. blanket op alle kolommen toegepast.
-- Targeted repairs for columns/tables that were once changed via
-- MODIFY/DROP instead of ADD COLUMN — see header (p_v1.1) for why this
-- stays targeted instead of being applied blanket to every column.

ALTER TABLE `system_config` MODIFY COLUMN `battery_efficiency_pct` DECIMAL(5,2) DEFAULT 75.00;

DROP TABLE IF EXISTS `price_profile`;
