-- Migration 004: Extended strategy configuration fields.
-- Migratie 004: Uitgebreide strategieconfiguratie-velden.

ALTER TABLE system_config
    ADD COLUMN IF NOT EXISTS `temp_derating_threshold_c`      DECIMAL(5,2)  DEFAULT 35.00
        COMMENT 'Battery temp above which power is derated / Batterijtemperatuur waarboven vermogen wordt verlaagd',
    ADD COLUMN IF NOT EXISTS `temp_derating_factor`           DECIMAL(4,2)  DEFAULT 0.70
        COMMENT 'Power reduction factor when temp exceeded / Vermogensfactor bij te hoge temperatuur',
    ADD COLUMN IF NOT EXISTS `min_spread_ratio_for_discharge` DECIMAL(4,2)  DEFAULT 2.00
        COMMENT 'Min price spread ratio to trigger discharge / Min prijsspreiding voor ontladen',
    ADD COLUMN IF NOT EXISTS `discharge_near_peak_fraction`   DECIMAL(4,2)  DEFAULT 0.85
        COMMENT 'Price must be within this fraction of peak / Prijs moet binnen deze fractie van piek liggen',
    ADD COLUMN IF NOT EXISTS `extreme_price_multiplier`       DECIMAL(4,2)  DEFAULT 2.50
        COMMENT 'Multiple of avg price considered extreme / Veelvoud van gem. prijs dat extreem is',
    ADD COLUMN IF NOT EXISTS `negative_export_threshold_excl` DECIMAL(8,5)  DEFAULT 0.00000
        COMMENT 'Export price below which to limit export (excl. VAT) / Terugleverprijs waaronder export beperkt wordt',
    ADD COLUMN IF NOT EXISTS `notify_export_threshold_excl`   DECIMAL(8,5)  DEFAULT 0.02000
        COMMENT 'Notify user when export price below this / Gebruiker melden bij lage terugleverprijs',
    ADD COLUMN IF NOT EXISTS `charge_near_cheapest_fraction`  DECIMAL(4,2)  DEFAULT 1.05
        COMMENT 'Price must be within this fraction of cheapest / Prijs moet binnen deze fractie van minimum liggen',
    ADD COLUMN IF NOT EXISTS `min_sunshine_pct_for_refill`    DECIMAL(5,2)  DEFAULT 40.00
        COMMENT 'Min sunshine % tomorrow to allow discharge / Min zonpercentage morgen voor ontladen',
    ADD COLUMN IF NOT EXISTS `avg_consumption_kwh`            DECIMAL(6,3)  DEFAULT 0.500
        COMMENT 'Expected average hourly consumption / Verwacht gemiddeld uurverbruik',
    ADD COLUMN IF NOT EXISTS `sunrise_buffer_pct`             DECIMAL(5,2)  DEFAULT 10.00
        COMMENT 'SoC buffer to keep at sunrise / SoC-buffer te bewaren bij zonsopgang',
    ADD COLUMN IF NOT EXISTS `evening_planning_time`          TIME          DEFAULT '21:00:00'
        COMMENT 'Time to run evening day balance planning / Tijd voor avond dagbalansplanning';

ALTER TABLE battery_info
    ADD COLUMN IF NOT EXISTS `working_charge_kw`    DECIMAL(8,3) DEFAULT NULL
        COMMENT 'Preferred charge power (< max for battery health) / Voorkeurslaadvermogen',
    ADD COLUMN IF NOT EXISTS `working_discharge_kw` DECIMAL(8,3) DEFAULT NULL
        COMMENT 'Preferred discharge power (< max for battery health) / Voorkeursontlaadvermogen';
