#
# name:          setup.py
# part of:       ha-energy-optimizer
# location:      /ha-energy-optimizer/ha-energy-optimizer/database/setup.py
# part version:  p_v0.13
# altered:       2026-09-13
#
# p_v0.13: Logging toegevoegd aan _apply() — elke migratiepoging (toegepast/
# overgeslagen/fout) is nu zichtbaar in het add-on log via de standaard
# 'database.setup'-logger. Reden: na het uitrollen van p_v0.12 bleef
# solar_reserve_strategy ontbreken zonder ENIGE foutmelding in het log,
# ook na een verse Docker-rebuild vanaf GitHub — zonder logging was niet
# vast te stellen of migratie 22 wel/niet geprobeerd werd. Dit maakt het
# probleem voortaan zichtbaar i.p.v. dat we op aannames moeten gokken.
#
# p_v0.13: Logging added to _apply() — every migration attempt (applied/
# skipped/failed) is now visible in the add-on log via the standard
# 'database.setup' logger. Reason: after rolling out p_v0.12,
# solar_reserve_strategy kept missing with NO error in the log at all,
# even after a fresh Docker rebuild from GitHub — without logging there
# was no way to establish whether migration 22 was even attempted. This
# makes the problem visible going forward instead of guessing.
#
# p_v0.12: 22 toegevoegd aan ALL_VERSIONS en de stapsgewijze route
# (solar_reserve_strategy op system_config, zie decision_engine.py p_v0.14).
# 21 is BEWUST NIET toegevoegd aan de stapsgewijze route: die kolom
# (grid_consume_kw op optimizer_schedule) bleek al aanwezig op bestaande
# installaties via een eerdere handmatige toepassing van
# 000_consolidated.sql, terwijl _migrations geen rij voor versie 21 had.
# _apply(db, 21, ...) zou daardoor een Duplicate column-fout geven. 21 is
# wel opgenomen in ALL_VERSIONS, zodat een verse installatie 'm correct
# als toegepast registreert.
# Root cause van deze sessie: 21 en 22 werden als bestand aangemaakt maar
# nooit aan setup.py toegevoegd, waardoor bestaande installaties de
# migratie nooit draaiden (ProgrammingError: Unknown column
# 'solar_reserve_strategy').
#
# p_v0.12: added 22 to ALL_VERSIONS and the step-by-step route
# (solar_reserve_strategy on system_config, see decision_engine.py p_v0.14).
# 21 is DELIBERATELY NOT added to the step-by-step route: that column
# (grid_consume_kw on optimizer_schedule) turned out to already be present
# on existing installations via an earlier manual application of
# 000_consolidated.sql, while _migrations had no row for version 21.
# _apply(db, 21, ...) would therefore raise a Duplicate column error. 21 is
# still included in ALL_VERSIONS so a fresh install registers it correctly
# as applied.
# Root cause this session: 21 and 22 were created as files but never added
# to setup.py, so existing installations never ran the migration
# (ProgrammingError: Unknown column 'solar_reserve_strategy').
#
# p_v0.11: 20 toegevoegd (off-grid uitvaldetectie-instellingen, zie
# collectors/offgrid_monitor.py, decision_engine.py p_v0.12).
#
# p_v0.10: 18 en 19 toegevoegd aan ALL_VERSIONS en de stapsgewijze route.
# 018 (price_sell_per_kwh) is idempotent (IF NOT EXISTS/WHERE IS NULL),
# dus veilig om opnieuw te draaien ook al was die al handmatig toegepast —
# geen "markeer als toegepast"-stap nodig zoals destijds bij 015/016.
# 000_consolidated.sql (p_v0.3) bijgewerkt t/m 019, inclusief het eerder
# gemiste price_sell_per_kwh uit migratie 018.
#
# p_v0.9: 15/16/17 alsnog toegevoegd aan ALL_VERSIONS — 000_consolidated.sql
# is bijgewerkt (p_v0.2) met het kwartier-schema en zonder price_profile,
# dus een verse installatie krijgt nu direct het juiste eindschema. De
# eerdere waarschuwing hierover (p_v0.7) is hiermee vervallen.
#
# LET OP: dit is nog een handmatige aanvulling per migratie, GEEN volledige
# samenvoeging van alle losse ALTER-statements uit 001-014 in de
# CREATE TABLE-definities — die grotere opschoning van database + migraties
# samen staat gepland voor v0.14.
#
# p_v0.9: 15/16/17 added to ALL_VERSIONS after all — 000_consolidated.sql
# has been updated (p_v0.2) with the quarter-hour schema and without
# price_profile, so a fresh install now gets the correct end-state schema
# directly. The earlier warning about this (p_v0.7) is now resolved.
#
# NOTE: this is still a manual per-migration addition, NOT a full merge of
# all the separate ALTER statements from 001-014 into the CREATE TABLE
# definitions — that larger cleanup of database + migrations together is
# planned for v0.14.
#
import logging
from pathlib import Path
from .connection import DatabaseConnection

logger = logging.getLogger(__name__)

MIGRATIONS_DIR = Path(__file__).parent / "migrations"

# Alle reguliere migratieversies (007 is een eenmalige datacorrectie en
# hoort hier bewust niet bij — zie onderstaande toelichting).
# All regular migration versions (007 is a one-time data correction and
# is deliberately excluded here — see note below).
ALL_VERSIONS = [1, 2, 3, 4, 5, 6, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22]


def run_migrations(db: DatabaseConnection) -> None:
    with db.cursor() as cur:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS _migrations (
                version    INT PRIMARY KEY,
                applied_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)

    if _is_fresh_install(db):
        # Verse database: complete eindschema in één keer neerzetten i.p.v.
        # 12 losse ALTER-stappen. Beperkt de kans op fouten bij een nieuwe
        # installatie aanzienlijk (dit was letterlijk hoe migratie 001 tot
        # voor kort faalde op een schone database).
        # Fresh database: lay down the complete end-state schema in one go
        # instead of 12 separate ALTER steps. Significantly reduces the
        # chance of errors on a new installation (this was literally how
        # migration 001 used to fail on a clean database until recently).
        with db.cursor() as cur:
            cur.execute((MIGRATIONS_DIR / "000_consolidated.sql").read_text())
        with db.cursor() as cur:
            cur.executemany(
                "INSERT IGNORE INTO _migrations (version) VALUES (%s)",
                [(v,) for v in ALL_VERSIONS]
            )
    else:
        # Bestaande installatie: stapsgewijs bijwerken zoals voorheen, zodat
        # alleen ontbrekende migraties worden toegepast.
        # Existing installation: upgrade step by step as before, so only
        # missing migrations get applied.
        _apply(db, 1, MIGRATIONS_DIR / "001_initial.sql")
        _apply(db, 2, MIGRATIONS_DIR / "002_add_indexes.sql")
        _apply(db, 3, MIGRATIONS_DIR / "003_strategy_fields.sql")
        _apply(db, 4, MIGRATIONS_DIR / "004_extended_strategy_fields.sql")
        _apply(db, 5, MIGRATIONS_DIR / "005_profile_tables.sql")
        _apply(db, 6, MIGRATIONS_DIR / "006_solar_charge_threshold.sql")
        # 007 is a one-time UTC->local data correction — NOT in regular sequence
        # 007 is een eenmalige UTC->lokaal datacorrectie — NIET in reguliere reeks
        _apply(db, 8, MIGRATIONS_DIR / "008_dashboard_colors.sql")
        _apply(db, 9, MIGRATIONS_DIR / "009_expected_cost.sql")
        _apply(db, 10, MIGRATIONS_DIR / "010_energy_prices_config.sql")
        _apply(db, 11, MIGRATIONS_DIR / "011_solar_learning.sql")
        _apply(db, 12, MIGRATIONS_DIR / "012_consumption_learning.sql")
        _apply(db, 13, MIGRATIONS_DIR / "013_translation_strings.sql")
        _apply(db, 14, MIGRATIONS_DIR / "014_reason_key.sql")
        _apply(db, 15, MIGRATIONS_DIR / "015_quarter_hour_slots.sql")
        _apply(db, 16, MIGRATIONS_DIR / "016_grid_solar_charge_split.sql")
        _apply(db, 17, MIGRATIONS_DIR / "017_drop_price_profile.sql")
        _apply(db, 18, MIGRATIONS_DIR / "018_price_sell_column.sql")
        _apply(db, 19, MIGRATIONS_DIR / "019_offgrid_dynamic_reserve.sql")
        _apply(db, 20, MIGRATIONS_DIR / "020_offgrid_detection.sql")
        # 21 is bewust NIET hier toegevoegd — grid_consume_kw bleek al
        # aanwezig op bestaande installaties (zie header p_v0.12), dus
        # _apply zou hier een Duplicate column-fout geven. Wel opgenomen
        # in ALL_VERSIONS voor verse installaties.
        # 21 is deliberately NOT added here — grid_consume_kw turned out
        # to already be present on existing installations (see header
        # p_v0.12), so _apply would raise a Duplicate column error here.
        # It IS included in ALL_VERSIONS for fresh installations.
        _apply(db, 22, MIGRATIONS_DIR / "022_solar_reserve_strategy.sql")

    # Vul vertalingstabel met standaardteksten (INSERT IGNORE — overschrijft geen aanpassingen)
    # Fill translation table with default texts (INSERT IGNORE — does not overwrite customisations)
    from translations.seed_translations import run_seed
    run_seed(db)


def _is_fresh_install(db: DatabaseConnection) -> bool:
    """
    Een database is 'vers' als de kerntabel system_config nog niet bestaat.
    Bewust NIET gebaseerd op een lege _migrations tabel: als system_config
    al bestaat (bv. handmatig aangemaakt, zoals bij herstel vanuit een
    export) maar _migrations leeg is, moet de stapsgewijze route draaien
    zodat ontbrekende kolommen alsnog via ALTER TABLE worden toegevoegd —
    de geconsolideerde CREATE TABLE IF NOT EXISTS zou die dan overslaan.

    A database is 'fresh' if the core table system_config doesn't exist
    yet. Deliberately NOT based on an empty _migrations table: if
    system_config already exists (e.g. manually created, such as when
    restoring from an export) but _migrations is empty, the step-by-step
    path must run so missing columns still get added via ALTER TABLE —
    the consolidated CREATE TABLE IF NOT EXISTS would otherwise skip them.
    """
    with db.cursor() as cur:
        cur.execute("SHOW TABLES LIKE 'system_config'")
        return cur.fetchone() is None


def _apply(db: DatabaseConnection, version: int, sql_file: Path) -> None:
    with db.cursor() as cur:
        cur.execute("SELECT version FROM _migrations WHERE version=%s", (version,))
        if cur.fetchone():
            logger.info(f"Migratie {version} ({sql_file.name}) al toegepast, overgeslagen "
                        f"/ migration {version} ({sql_file.name}) already applied, skipped")
            return
    logger.info(f"Migratie {version} ({sql_file.name}) wordt toegepast "
                f"/ applying migration {version} ({sql_file.name})")
    try:
        with db.cursor() as cur:
            cur.execute(sql_file.read_text())
        with db.cursor() as cur:
            cur.execute("INSERT INTO _migrations (version) VALUES (%s)", (version,))
        logger.info(f"Migratie {version} succesvol toegepast en geregistreerd "
                    f"/ migration {version} applied and registered successfully")
    except Exception:
        logger.exception(f"Migratie {version} ({sql_file.name}) is MISLUKT "
                          f"/ migration {version} ({sql_file.name}) FAILED")
        raise
