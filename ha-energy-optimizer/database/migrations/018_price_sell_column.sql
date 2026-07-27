--
-- name:          018_price_sell_column.sql
-- part of:       ha-energy-optimizer
-- location:      /ha-energy-optimizer/ha-energy-optimizer/database/migrations/018_price_sell_column.sql
-- part version:  p_v0.1
-- altered:       2026-07-26
--
-- Start van de in/verkoopprijs-splitsing. Voegt price_sell_per_kwh toe aan
-- energy_prices — één rij per tijdstip, twee prijskolommen (i.p.v. twee
-- rijen met een type-veld), zoals besproken.
--
-- Bestaande rijen: price_sell_per_kwh wordt gevuld met dezelfde waarde als
-- price_per_kwh (duplicaat), zodat niets stuk gaat voor providers die nog
-- geen aparte verkoopprijs leveren — precies zoals nieuwe rijen dat ook
-- doen via EnergyPrice.__post_init__ in database/models.py.
--
-- Start of the buy/sell price split. Adds price_sell_per_kwh to
-- energy_prices — one row per timestamp, two price columns (instead of two
-- rows with a type field), as discussed.
--
-- Existing rows: price_sell_per_kwh is filled with the same value as
-- price_per_kwh (duplicate), so nothing breaks for providers that don't
-- yet supply a distinct sell price — exactly like new rows do via
-- EnergyPrice.__post_init__ in database/models.py.

ALTER TABLE `energy_prices`
    ADD COLUMN IF NOT EXISTS `price_sell_per_kwh` DECIMAL(10,5) NULL
        COMMENT 'Verkoopprijs (teruglevering) €/kWh — duplicaat van price_per_kwh tot een provider een eigen verkoopprijs levert / Sell (feed-in) price €/kWh — duplicate of price_per_kwh until a provider supplies its own sell price';

UPDATE `energy_prices`
    SET `price_sell_per_kwh` = `price_per_kwh`
    WHERE `price_sell_per_kwh` IS NULL;

ALTER TABLE `energy_prices`
    MODIFY COLUMN `price_sell_per_kwh` DECIMAL(10,5) NOT NULL;
