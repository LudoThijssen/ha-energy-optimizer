--
-- name:          019_offgrid_dynamic_reserve.sql
-- part of:       ha-energy-optimizer
-- location:      /ha-energy-optimizer/ha-energy-optimizer/database/migrations/019_offgrid_dynamic_reserve.sql
-- part version:  p_v0.1
-- altered:       2026-07-30
--
-- Instellingen voor de dynamische off-grid reserve: een SoC-ondergrens die
-- schuift tussen een hoge (dag) en lage (nacht) waarde, gekoppeld aan
-- zonsopkomst en het geleerde nachtverbruikpatroon. Alleen actief als
-- has_offgrid_switch aan staat (vinkje op de Systeem-pagina bij
-- "Geïnstalleerde componenten") — staat het uit, dan verandert er niets
-- aan het bestaande gedrag (de vaste min_soc_pct/off_grid_reserve_kwh
-- blijven van kracht). Zie decision_engine.py p_v0.11.
--
-- Settings for the dynamic off-grid reserve: a SoC floor that shifts
-- between a high (day) and low (night) value, tied to sunrise and the
-- learned night-consumption pattern. Only active if has_offgrid_switch is
-- on (checkbox on the System page under "Installed components") — if
-- off, nothing changes about existing behaviour (the fixed
-- min_soc_pct/off_grid_reserve_kwh remain in effect). See
-- decision_engine.py p_v0.11.

ALTER TABLE `system_config`
    ADD COLUMN IF NOT EXISTS `has_offgrid_switch` TINYINT(1) NOT NULL DEFAULT 0
        COMMENT 'Off-grid schakeling aanwezig / Off-grid switching present',
    ADD COLUMN IF NOT EXISTS `offgrid_reserve_high_pct` DECIMAL(5,2) NOT NULL DEFAULT 10.00
        COMMENT 'SoC-ondergrens overdag (%) / SoC floor during the day (%)',
    ADD COLUMN IF NOT EXISTS `offgrid_reserve_low_pct` DECIMAL(5,2) NOT NULL DEFAULT 5.00
        COMMENT 'SoC-ondergrens s nachts (%) / SoC floor during the night (%)',
    ADD COLUMN IF NOT EXISTS `offgrid_night_threshold_pct` DECIMAL(5,2) NOT NULL DEFAULT 50.00
        COMMENT 'Drempel voor "nacht"-verbruik, als % van het daggemiddelde / Threshold for "night" consumption, as % of daily average',
    ADD COLUMN IF NOT EXISTS `offgrid_night_confirm_slots` SMALLINT NOT NULL DEFAULT 8
        COMMENT 'Aantal opeenvolgende kwartier-slots onder de drempel om "begin nacht" te bevestigen / Number of consecutive quarter slots below threshold to confirm "start of night"';
