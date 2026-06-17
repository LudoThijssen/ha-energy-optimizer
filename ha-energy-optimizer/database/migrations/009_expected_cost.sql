-- database/migrations/009_expected_cost.sql
-- /ha-energy-optimizer/ha-energy-optimizer/database/migrations/009_expected_cost.sql
-- v0.2.13 — 2026-06-16
--
-- Adds expected_cost to optimizer_schedule, alongside the existing
-- expected_saving. This makes grid-charging costs visible in the
-- schedule, rather than only showing savings — avoiding a misleading
-- one-sided view of the financial picture.
--
-- Voegt expected_cost toe aan optimizer_schedule, naast de bestaande
-- expected_saving. Dit maakt de kosten van netladen zichtbaar in het
-- schema, in plaats van alleen besparingen te tonen — voorkomt een
-- misleidend eenzijdig beeld van de financiële situatie.
--
-- expected_cost is the amount paid this hour for grid charging
-- (excl. VAT, consistent with all other price fields). It is 0 for
-- solar charging (free), discharge, idle, and self_consume.
--
-- expected_cost is het bedrag betaald dit uur voor netladen
-- (excl. BTW, consistent met alle andere prijsvelden). Het is 0 voor
-- zonne-lading (gratis), ontladen, rust en zelf-verbruik.

ALTER TABLE optimizer_schedule
    ADD COLUMN IF NOT EXISTS `expected_cost` DECIMAL(10,5) DEFAULT 0
        COMMENT 'Cost of grid charging this hour, excl. VAT / Kosten van netladen dit uur, excl. BTW';
