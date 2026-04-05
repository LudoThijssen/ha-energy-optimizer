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


def _apply(db: DatabaseConnection, version: int, sql_file: Path) -> None:
    with db.cursor() as cur:
        cur.execute("SELECT version FROM _migrations WHERE version=%s", (version,))
        if cur.fetchone():
            return
    with db.cursor() as cur:
        cur.execute(sql_file.read_text())
    with db.cursor() as cur:
        cur.execute("INSERT INTO _migrations (version) VALUES (%s)", (version,))
