--
-- name:          021_grid_consume_field.sql
-- part of:       ha-energy-optimizer
-- location:      /ha-energy-optimizer/ha-energy-optimizer/database/migrations/021_grid_consume_field.sql
-- part version:  p_v0.1
-- altered:       2026-08-11
--
-- p_v0.1: grid_consume_kw toegevoegd aan optimizer_schedule. Dekt een tot
-- nu toe onzichtbaar gat in de voorspelling: tijdens een "rust"-slot trok
-- decision_engine.py het niet door zon gedekte huisverbruik altijd van de
-- batterij af, geclampt op min_soc_pct — het deel dat na die klem overbleef
-- verdween stilzwijgend uit het model. In werkelijkheid komt dat deel
-- rechtstreeks van het net (de batterij kan niet verder leeglopen). Dit
-- veld maakt dat deel expliciet, zodat het in de schema-tabel getoond kan
-- worden en meetelt in expected_cost. Zelfde kolomstijl als grid_charge_kw
-- (migratie 016). Geen wijziging aan de grafieken — alleen tabel/kosten.
--
-- p_v0.1: grid_consume_kw added to optimizer_schedule. Covers a previously
-- invisible gap in the forecast: during an "idle" slot, decision_engine.py
-- always drew household consumption not covered by solar from the battery,
-- clamped at min_soc_pct — the portion left over after that clamp
-- silently vanished from the model. In reality that portion comes straight
-- from the grid (the battery can't drain further). This field makes that
-- portion explicit, so it can be shown in the schedule table and counted
-- in expected_cost. Same column style as grid_charge_kw (migration 016).
-- No change to the graphs — table/cost only.
--

ALTER TABLE `optimizer_schedule`
    ADD COLUMN `grid_consume_kw` DECIMAL(6,3) NOT NULL DEFAULT 0.000
        COMMENT 'Vermogen (kW) rechtstreeks van het net voor huisverbruik, buiten de batterij om (SoC-vloer bereikt) / Power (kW) drawn directly from the grid for household use, bypassing the battery (SoC floor reached)'
        AFTER `grid_charge_kw`;
