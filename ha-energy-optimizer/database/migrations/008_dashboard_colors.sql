-- name:          008_dashboard_colors.sql
-- part of:       ha-energy-optimizer
-- location:      /ha-energy-optimizer/ha-energy-optimizer/database/migrations/008_dashboard_colors.sql
-- part version:  p_v0.3
-- altered:       2026-06-21
--
-- Adds dashboard_colors JSON column to system_config so chart colors
-- persist across reinstalls (options.json does not survive reinstall,
-- but system_config does and is already restored on startup).
--
-- Voegt dashboard_colors JSON-kolom toe aan system_config zodat
-- grafiekkleuren behouden blijven na herinstallatie (options.json
-- overleeft herinstallatie niet, maar system_config wel en wordt
-- al herstelt bij opstarten).

ALTER TABLE system_config
    ADD COLUMN IF NOT EXISTS `dashboard_colors` JSON DEFAULT NULL
        COMMENT 'Custom chart colors as JSON: {solar, consume, import_kw, export_kw, soc, discharge, solar_charge} / Aangepaste grafiekkleuren als JSON';
