--
-- name:          020_offgrid_detection.sql
-- part of:       ha-energy-optimizer
-- location:      /ha-energy-optimizer/ha-energy-optimizer/database/migrations/020_offgrid_detection.sql
-- part version:  p_v0.1
-- altered:       2026-07-30
--
-- Instellingen + status voor de off-grid uitvaldetectie (offgrid_monitor.py).
-- offgrid_active is het door de monitor bijgewerkte resultaat, gelezen
-- door decision_engine.py om optimizer-beslissingen te pauzeren zolang
-- off-grid actief is. De rest zijn configuratievelden voor de twee
-- detectie-entiteiten en de terug te schrijven alarm-entiteit.
--
-- Settings + status for off-grid outage detection (offgrid_monitor.py).
-- offgrid_active is the result kept up to date by the monitor, read by
-- decision_engine.py to pause optimizer decisions while off-grid is
-- active. The rest are configuration fields for the two detection
-- entities and the alarm entity to write back.

ALTER TABLE `system_config`
    ADD COLUMN IF NOT EXISTS `offgrid_primary_entity_id` VARCHAR(256) DEFAULT NULL
        COMMENT 'Primaire detectie-entiteit, bijv. status off-grid schakelaar / Primary detection entity, e.g. off-grid switch status',
    ADD COLUMN IF NOT EXISTS `offgrid_primary_off_value` VARCHAR(64) NOT NULL DEFAULT 'off'
        COMMENT 'Waarde van de primaire entiteit die "off-grid" betekent / Value of the primary entity that means "off-grid"',
    ADD COLUMN IF NOT EXISTS `offgrid_fallback_entity_id` VARCHAR(256) DEFAULT NULL
        COMMENT 'Terugval-entiteit, bijv. P1-meter sensor (unavailable = signaal) / Fallback entity, e.g. P1 meter sensor (unavailable = signal)',
    ADD COLUMN IF NOT EXISTS `offgrid_alarm_entity_id` VARCHAR(256) NOT NULL DEFAULT 'binary_sensor.ha_energy_optimizer_offgrid'
        COMMENT 'Entiteit die de add-on terugschrijft naar HA voor automations / Entity the add-on writes back to HA for automations',
    ADD COLUMN IF NOT EXISTS `offgrid_active` TINYINT(1) NOT NULL DEFAULT 0
        COMMENT 'Huidige gedetecteerde off-grid status, bijgewerkt door offgrid_monitor.py / Current detected off-grid status, kept up to date by offgrid_monitor.py',
    ADD COLUMN IF NOT EXISTS `offgrid_last_checked_at` DATETIME DEFAULT NULL
        COMMENT 'Tijdstip laatste detectie-controle / Timestamp of last detection check';
