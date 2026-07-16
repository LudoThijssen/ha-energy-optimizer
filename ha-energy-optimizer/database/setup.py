#
# name:          setup.py
# part of:       ha-energy-optimizer
# location:      /ha-energy-optimizer/ha-energy-optimizer/database/setup.py
# part version:  p_v0.6
# altered:       2026-07-16
#
from pathlib import Path
from .connection import DatabaseConnection

MIGRATIONS_DIR = Path(__file__).parent / "migrations"

# Alle reguliere migratieversies (007 is een eenmalige datacorrectie en
# hoort hier bewust niet bij — zie onderstaande toelichting).
# All regular migration versions (007 is a one-time data correction and
# is deliberately excluded here — see note below).
ALL_VERSIONS = [1, 2, 3, 4, 5, 6, 8, 9, 10, 11, 12, 13, 14]


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
            return
    with db.cursor() as cur:
        cur.execute(sql_file.read_text())
    with db.cursor() as cur:
        cur.execute("INSERT INTO _migrations (version) VALUES (%s)", (version,))
