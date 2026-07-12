--
-- name:          014_reason_key.sql
-- part of:       ha-energy-optimizer
-- location:      /ha-energy-optimizer/ha-energy-optimizer/database/migrations/014_reason_key.sql
-- part version:  p_v0.4
-- altered:       2026-07-01
--
-- Voegt reason_key en reason_params toe aan optimizer_schedule.
-- De bestaande reason kolom blijft voor achterwaartse compatibiliteit
-- en wordt gevuld met de vertaalde tekst in de actieve taal.
--
-- Adds reason_key and reason_params to optimizer_schedule.
-- The existing reason column remains for backward compatibility
-- and is filled with the translated text in the active language.

ALTER TABLE `optimizer_schedule`
    ADD COLUMN IF NOT EXISTS `reason_key`    VARCHAR(8)  DEFAULT NULL
        COMMENT 'Vertaalsleutel bijv. RS01 / Translation key e.g. RS01',
    ADD COLUMN IF NOT EXISTS `reason_params` JSON        DEFAULT NULL
        COMMENT 'Parameters voor vertaling bijv. {"price": 0.12} / Translation params';
