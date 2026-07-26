--
-- name:          017_drop_price_profile.sql
-- part of:       ha-energy-optimizer
-- location:      /ha-energy-optimizer/ha-energy-optimizer/database/migrations/017_drop_price_profile.sql
-- part version:  p_v0.1
-- altered:       2026-07-25
--
-- Verwijdert price_profile — bevestigd ongebruikt: werd elke nacht gevuld
-- door profile_updater.py maar nergens gelezen (engine.py gebruikt alleen
-- solar_profile/consumption_profile als terugval). Zie ook profile_updater.py
-- p_v0.5, waar de vulling is verwijderd.
--
-- Removes price_profile — confirmed unused: was filled nightly by
-- profile_updater.py but never read anywhere (engine.py only uses
-- solar_profile/consumption_profile as fallback). See also
-- profile_updater.py p_v0.5, where the population logic was removed.

DROP TABLE IF EXISTS `price_profile`;
