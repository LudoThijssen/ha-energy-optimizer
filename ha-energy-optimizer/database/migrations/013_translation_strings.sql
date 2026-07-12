--
-- name:          013_translation_strings.sql
-- part of:       ha-energy-optimizer
-- location:      /ha-energy-optimizer/ha-energy-optimizer/database/migrations/013_translation_strings.sql
-- part version:  p_v0.4
-- altered:       2026-07-01
--
-- Vertalingstabel voor operationele teksten (reason strings, log berichten,
-- notificaties). Keys zijn 4 tekens: 2 letters (groep) + 2 cijfers (volgnummer).
--
-- Groepen:
--   RS = Reason strings (optimizer beslissingen)
--   LG = Log berichten (collectors, learners)
--   NT = Notificaties (HA push berichten)
--   SY = Systeem berichten (dagrapport, status)
--   ER = Foutmeldingen
--
-- Translation table for operational texts (reason strings, log messages,
-- notifications). Keys are 4 chars: 2 letters (group) + 2 digits (sequence).

CREATE TABLE IF NOT EXISTS `translation_strings` (
    `string_key`  VARCHAR(8)   NOT NULL COMMENT 'Sleutel bijv. RS01 / Key e.g. RS01',
    `language`    CHAR(2)      NOT NULL COMMENT 'Taalcode bijv. nl, en / Language code',
    `text`        TEXT         NOT NULL COMMENT 'Vertaalde tekst met {variabelen} / Translated text with {variables}',
    `updated_at`  DATETIME     DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (`string_key`, `language`)
) ENGINE=InnoDB COMMENT='Operationele vertalingen / Operational translations';
