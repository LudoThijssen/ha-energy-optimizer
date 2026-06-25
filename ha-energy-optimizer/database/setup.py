# name:          setup.py
# part of:       ha-energy-optimizer
# location:      /ha-energy-optimizer/ha-energy-optimizer/database/setup.py
# part version:  p_v0.4
# altered:       2026-06-26
#
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
    # 007 is a one-time UTC->local data correction — NOT in regular sequence
    # 007 is een eenmalige UTC->lokaal datacorrectie — NIET in reguliere reeks
    _apply(db, 8, MIGRATIONS_DIR / "008_dashboard_colors.sql")
    _apply(db, 9, MIGRATIONS_DIR / "009_expected_cost.sql")
    _apply(db, 10, MIGRATIONS_DIR / "010_energy_prices_config.sql")
    _apply(db, 11, MIGRATIONS_DIR / "011_solar_learning.sql")
    _apply(db, 12, MIGRATIONS_DIR / "012_consumption_learning.sql")


def _apply(db: DatabaseConnection, version: int, sql_file: Path) -> None:
    with db.cursor() as cur:
        cur.execute("SELECT version FROM _migrations WHERE version=%s", (version,))
        if cur.fetchone():
            return
    with db.cursor() as cur:
        cur.execute(sql_file.read_text())
    with db.cursor() as cur:
        cur.execute("INSERT INTO _migrations (version) VALUES (%s)", (version,))
