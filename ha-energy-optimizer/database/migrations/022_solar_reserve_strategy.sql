--
-- name:          022_solar_reserve_strategy.sql
-- part of:       ha-energy-optimizer
-- location:      /ha-energy-optimizer/ha-energy-optimizer/database/migrations/022_solar_reserve_strategy.sql
-- part version:  p_v0.1
-- altered:       2026-09-09
--
-- p_v0.1: solar_reserve_strategy toegevoegd aan system_config. Instelling
-- (Systeempagina) om te kiezen hoe de optimizer omgaat met batterijruimte
-- reserveren vóór een verwacht NEGATIEF exportprijsvenster:
--   'block'    (A) — helemaal niet van het net laden zolang de verwachte
--               zon vóór dat venster genoeg is om de batterij te vullen.
--   'throttle' (B) — wel van het net laden zoals nu, maar het vermogen
--               begrenzen zodat er ruimte overblijft voor de verwachte zon.
-- Standaard 'throttle' (B) — zie gesprek met Ludo: prijsgedreven laden
-- tegen een lage/negatieve prijs bleek in de praktijk (week van
-- 1 augustus) per saldo winstgevend, ook als dat later ten koste ging van
-- ruimte voor zon. 'block' (A) blijft als optie beschikbaar voor wie dat
-- liever strikter wil.
--
-- p_v0.1: solar_reserve_strategy added to system_config. Setting (System
-- page) to choose how the optimizer handles reserving battery capacity
-- ahead of an expected NEGATIVE export price window:
--   'block'    (A) — don't charge from the grid at all as long as the
--               forecasted solar before that window is enough to fill
--               the battery.
--   'throttle' (B) — still charge from the grid as now, but cap the
--               power so room remains for the forecasted solar.
-- Default 'throttle' (B) — see conversation with Ludo: price-driven
-- charging at a low/negative price turned out net profitable in practice
-- (week of August 1st), even when it later cost some room for solar.
-- 'block' (A) remains available as an option for those who prefer it
-- stricter.
--

ALTER TABLE `system_config`
    ADD COLUMN `solar_reserve_strategy` ENUM('block', 'throttle') NOT NULL DEFAULT 'throttle'
        COMMENT 'Strategie voor batterijruimte-reservering vóór negatief exportprijsvenster: block (A) of throttle (B) / Strategy for reserving battery capacity ahead of a negative export price window: block (A) or throttle (B)'
        AFTER `has_offgrid_switch`;
