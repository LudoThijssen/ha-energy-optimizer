from pathlib import Path
from .connection import DatabaseConnection

MIGRATIONS_DIR = Path(__file__).parent / "migrations"


def run_migrations(db: DatabaseConnection) -> None:
    with db.cursor() as cur:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS _migrations (
                version    INT PRIMARY KEY,
                applied_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
    _apply(db, 1, MIGRATIONS_DIR / "001_initial.sql")
    _apply(db, 2, MIGRATIONS_DIR / "002_add_indexes.sql")
    _apply(db, 3, MIGRATIONS_DIR / "003_strategy_fields.sql")
    _apply(db, 4, MIGRATIONS_DIR / "004_extended_strategy_fields.sql")
    _apply(db, 5, MIGRATIONS_DIR / "005_profile_tables.sql")
    _apply(db, 6, MIGRATIONS_DIR / "006_solar_charge_threshold.sql")
    # Note: 007 is a one-time UTC->local data correction for existing
    # installations affected by the timezone bug fixed in v0.2.12.
    # It is NOT part of the regular migration sequence — it was applied
    # manually once and must not run on fresh installs (it would shift
    # already-correct timestamps).
    #
    # Opmerking: 007 is een eenmalige UTC->lokaal datacorrectie voor
    # bestaande installaties die te maken hadden met de tijdzonebug
    # opgelost in v0.2.12. Dit is GEEN onderdeel van de reguliere
    # migratiereeks — eenmalig handmatig toegepast, mag niet draaien
    # bij nieuwe installaties (zou correcte tijdstempels verschuiven).
    _apply(db, 8, MIGRATIONS_DIR / "008_dashboard_colors.sql")


def _apply(db: DatabaseConnection, version: int, sql_file: Path) -> None:
    with db.cursor() as cur:
        cur.execute("SELECT version FROM _migrations WHERE version=%s", (version,))
        if cur.fetchone():
            return
    with db.cursor() as cur:
        cur.execute(sql_file.read_text())
    with db.cursor() as cur:
        cur.execute("INSERT INTO _migrations (version) VALUES (%s)", (version,))
