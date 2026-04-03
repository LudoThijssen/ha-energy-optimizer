# database/setup.py
#
# Database migration runner.
# Database-migratiebeheerder.

import re
import logging
from pathlib import Path
from .connection import DatabaseConnection

logger = logging.getLogger(__name__)
MIGRATIONS_DIR = Path(__file__).parent / "migrations"


def run_migrations(db: DatabaseConnection) -> None:
    """
    Apply all pending migrations in order.
    Pas alle openstaande migraties op volgorde toe.
    """
    _execute(db, """
        CREATE TABLE IF NOT EXISTS `_migrations` (
            `version`    INT      NOT NULL,
            `applied_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (`version`)
        ) ENGINE=InnoDB
    """)

    _apply(db, 1, MIGRATIONS_DIR / "001_initial.sql")
    _apply(db, 2, MIGRATIONS_DIR / "002_add_indexes.sql")
    _apply(db, 3, MIGRATIONS_DIR / "003_strategy_fields.sql")
    _apply(db, 4, MIGRATIONS_DIR / "004_extended_strategy_fields.sql")


def _apply(db: DatabaseConnection, version: int, sql_file: Path) -> None:
    """Apply one migration file if not already applied."""
    with db.cursor() as cur:
        cur.execute(
            "SELECT version FROM _migrations WHERE version = %s", (version,)
        )
        if cur.fetchone():
            return

    logger.info(f"Applying migration {version}: {sql_file.name}")
    sql_text = sql_file.read_text(encoding="utf-8")

    for statement in _split_sql(sql_text):
        _execute(db, statement)

    with db.cursor() as cur:
        cur.execute(
            "INSERT INTO _migrations (version) VALUES (%s)", (version,)
        )
    logger.info(f"Migration {version} done")


def _split_sql(sql_text: str) -> list[str]:
    """Split SQL file into individual statements."""
    # Remove comments
    sql_text = re.sub(r'--[^\n]*', '', sql_text)
    sql_text = re.sub(r'/\*.*?\*/', '', sql_text, flags=re.DOTALL)
    return [s.strip() for s in sql_text.split(';') if s.strip()]


def _execute(db: DatabaseConnection, sql: str) -> None:
    """Execute one SQL statement, ignoring 'already exists' errors."""
    try:
        with db.cursor() as cur:
            cur.execute(sql)
    except Exception as e:
        msg = str(e).lower()
        if any(x in msg for x in ["already exists", "duplicate", "1060", "1061", "1062"]):
            logger.debug(f"Skipping (already exists): {str(e)[:80]}")
        else:
            logger.error(f"SQL failed: {e}\nSQL: {sql[:120]}")
            raise
