--
-- name:          016_grid_solar_charge_split.sql
-- part of:       ha-energy-optimizer
-- location:      /ha-energy-optimizer/ha-energy-optimizer/database/migrations/016_grid_solar_charge_split.sql
-- part version:  p_v0.1
-- altered:       2026-07-24
--
-- Voegt de opsplitsing tussen zon-laden en net-laden toe aan
-- optimizer_schedule. Deze opsplitsing werd al berekend in
-- decision_engine.py (is_solar_charge / grid_top_up_kwh) maar ging
-- verloren zodra het naar een ScheduleSlot/OptimizerSlot werd omgezet —
-- hierdoor kon de GUI "laden van het net" nooit apart tonen van
-- "laden vanuit zon-overschot".
--
-- Adds the solar-charge vs grid-charge split to optimizer_schedule. This
-- split was already calculated in decision_engine.py (is_solar_charge /
-- grid_top_up_kwh) but was lost as soon as it got converted to a
-- ScheduleSlot/OptimizerSlot — as a result the GUI could never show
-- "charging from the grid" separately from "charging from solar surplus".

ALTER TABLE `optimizer_schedule`
    ADD COLUMN IF NOT EXISTS `is_solar_charge` TINYINT(1) NOT NULL DEFAULT 0
        COMMENT 'Laadactie (deels) uit zon-overschot / Charge action (partly) from solar surplus',
    ADD COLUMN IF NOT EXISTS `grid_charge_kw` DECIMAL(6,3) NOT NULL DEFAULT 0.000
        COMMENT 'Vermogen (kW) dat specifiek uit het net wordt geladen — bij een puur net-laadslot (is_solar_charge=0) is dit gelijk aan target_power_kw / Power (kW) specifically charged from the grid — for a pure grid-charge slot (is_solar_charge=0) this equals target_power_kw';
