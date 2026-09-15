#
# name:          backup.py
# part of:       ha-energy-optimizer
# location:      /ha-energy-optimizer/ha-energy-optimizer/database/backup.py
# part version:  p_v0.1
# altered:       2026-09-14
#
# p_v0.1: NIEUW. Back-up (export) en herstel (restore) van de database.
#
# Ontwerp — het geëxporteerde SQL-bestand is ALTIJD veilig om te draaien,
# ook los in phpMyAdmin, ongeacht hoe vaak: het voegt alleen toe wat er
# nog niet is, en raakt bestaande data nooit aan. Er zit geen "vervang
# alles"-optie IN het bestand zelf — dat zou gevaarlijk zijn als iemand
# het script zonder nadenken plakt. "Vervangen" bestaat alleen als aparte
# stap binnen de app zelf (alle tabellen eerst leegmaken, dan hetzelfde
# script draaien tegen een lege database — daar is "aanvullen"
# vanzelfsprekend gelijk aan "alles invoegen").
#
# Per tabel wordt een passende manier gebruikt om te bepalen of een rij
# "al bestaat", zonder dat daar schema-wijzigingen (nieuwe UNIQUE-
# sleutels) voor nodig zijn:
#   - NATIVE_UNIQUE: tabel heeft al een werkende PRIMARY/UNIQUE-sleutel
#     op de relevante kolommen -> gewone INSERT IGNORE.
#   - TIMESTAMP_DEDUP: tabel heeft alleen een surrogaat-`id` maar wel een
#     natuurlijk tijdstip -> vergelijken op dat tijdstip via een
#     tijdelijke tabel + anti-join (snel, ook bij veel rijen, geen
#     schema-wijziging nodig).
#   - EMPTY_ONLY: configuratietabel zonder natuurlijke sleutel (meestal
#     precies 1 rij) -> alleen invoegen als de tabel nog helemaal leeg
#     is. Vult een verse installatie, raakt een bestaande nooit aan.
#
# Bijvangst tijdens het ontwerpen hiervan (apart gemeld, hier NIET
# gefixt): optimizer_schedule heeft geen echte UNIQUE-sleutel op
# schedule_for, terwijl repository.py::save_slot() een
# ON DUPLICATE KEY UPDATE gebruikt die daarvan uitgaat — die update-tak
# triggert vermoedelijk nooit. Voor déze module gebruiken we daarom de
# TIMESTAMP_DEDUP-strategie op schedule_for (heeft geen echte UNIQUE-
# sleutel nodig, werkt via anti-join).
#
# p_v0.1: NEW. Backup (export) and restore of the database.
#
# Design — the exported SQL file is ALWAYS safe to run, even standalone
# in phpMyAdmin, no matter how often: it only adds what isn't already
# there, and never touches existing data. There is no "replace
# everything" option IN the file itself — that would be dangerous if
# someone pastes it without thinking. "Replace" only exists as a separate
# step within the app itself (empty all tables first, then run the same
# script against an empty database — there, "add missing" is naturally
# equivalent to "insert everything").
#
# Each table uses a suitable way to determine whether a row "already
# exists", without requiring schema changes (new UNIQUE keys):
#   - NATIVE_UNIQUE: table already has a working PRIMARY/UNIQUE key on
#     the relevant columns -> plain INSERT IGNORE.
#   - TIMESTAMP_DEDUP: table only has a surrogate `id` but does have a
#     natural timestamp -> compare on that timestamp via a temporary
#     table + anti-join (fast even with many rows, no schema change
#     needed).
#   - EMPTY_ONLY: config table with no natural key (usually exactly 1
#     row) -> only insert if the table is currently completely empty.
#     Fills a fresh installation, never touches an existing one.
#
# Incidental finding while designing this (reported separately, NOT
# fixed here): optimizer_schedule has no real UNIQUE key on schedule_for,
# while repository.py::save_slot() uses an ON DUPLICATE KEY UPDATE that
# assumes one exists — that update branch presumably never triggers. For
# this module we therefore use the TIMESTAMP_DEDUP strategy on
# schedule_for (doesn't need a real UNIQUE key, works via anti-join).
#
import json
import logging
from datetime import datetime, date, time
from decimal import Decimal

from database.connection import DatabaseConnection

logger = logging.getLogger(__name__)

# Strategie per tabel. Volgorde is ook de uitvoeringsvolgorde (en de
# omgekeerde volgorde voor TRUNCATE bij "vervangen") — geen onderlinge
# FOREIGN KEY-afhankelijkheden in dit schema, dus de volgorde is voor de
# leesbaarheid gegroepeerd, niet functioneel vereist.
# Strategy per table. Order is also the execution order (and the reverse
# order for TRUNCATE on "replace") — no FOREIGN KEY dependencies between
# tables in this schema, so the order is grouped for readability, not
# functionally required.

NATIVE_UNIQUE = "native_unique"
TIMESTAMP_DEDUP = "timestamp_dedup"
EMPTY_ONLY = "empty_only"

TABLES = [
    # (tabelnaam, strategie, dedup-kolom of None)
    ("system_config",        EMPTY_ONLY,      None),
    ("inverter_info",        EMPTY_ONLY,      None),
    ("solar_info",           EMPTY_ONLY,      None),
    ("battery_info",         EMPTY_ONLY,      None),
    ("provider_config",      EMPTY_ONLY,      None),
    ("ha_entity_map",        NATIVE_UNIQUE,   None),
    ("energy_prices",        NATIVE_UNIQUE,   None),
    ("solar_production",     TIMESTAMP_DEDUP, "measured_at"),
    ("home_consumption",     TIMESTAMP_DEDUP, "measured_at"),
    ("battery_status",       TIMESTAMP_DEDUP, "measured_at"),
    ("weather_forecast",     NATIVE_UNIQUE,   None),
    ("optimizer_schedule",   TIMESTAMP_DEDUP, "schedule_for"),
    ("report_log",           TIMESTAMP_DEDUP, "created_at"),
    ("consumption_profile",  NATIVE_UNIQUE,   None),
    ("solar_profile",        NATIVE_UNIQUE,   None),
    ("solar_learning",       NATIVE_UNIQUE,   None),
    ("consumption_learning", NATIVE_UNIQUE,   None),
    ("translation_strings",  NATIVE_UNIQUE,   None),
]

TABLE_MARKER = "-- ===== TABLE: {table} ====="

# Rijen per bulk-statement — voorkomt één enorme regel bij grote tabellen.
# Rows per bulk statement — avoids one giant line for large tables.
CHUNK_SIZE = 500


def _sql_literal(value) -> str:
    """
    Zet een Python-waarde om naar een SQL-literal voor gebruik in een
    handgegenereerd INSERT-statement.

    Converts a Python value to a SQL literal for use in a hand-generated
    INSERT statement.
    """
    if value is None:
        return "NULL"
    if isinstance(value, bool):
        return "1" if value else "0"
    if isinstance(value, (int, float, Decimal)):
        return str(value)
    if isinstance(value, (dict, list)):
        # JSON-kolommen (driver_config, reason_params, dashboard_colors)
        # JSON columns (driver_config, reason_params, dashboard_colors)
        text = json.dumps(value)
        escaped = text.replace("\\", "\\\\").replace("'", "\\'")
        return f"'{escaped}'"
    if isinstance(value, (datetime, date, time)):
        return f"'{value.isoformat(sep=' ') if isinstance(value, datetime) else value.isoformat()}'"
    # Strings en alles wat verder als tekst behandeld moet worden
    # Strings and anything else that should be treated as text
    text = str(value)
    escaped = text.replace("\\", "\\\\").replace("'", "\\'")
    return f"'{escaped}'"


def _fetch_all_rows(db: DatabaseConnection, table: str) -> list[dict]:
    with db.cursor() as cur:
        cur.execute(f"SELECT * FROM `{table}`")
        return cur.fetchall()


def _quote_cols(cols: list[str]) -> str:
    return ", ".join(f"`{c}`" for c in cols)


def _chunked(items: list, size: int):
    for i in range(0, len(items), size):
        yield items[i:i + size]


def _generate_table_block(db: DatabaseConnection, table: str, strategy: str, dedup_col: str | None) -> str:
    rows = _fetch_all_rows(db, table)
    lines = [TABLE_MARKER.format(table=table)]

    if not rows:
        lines.append(f"-- (geen rijen / no rows)")
        return "\n".join(lines) + "\n"

    # `id` nooit meenemen — laat de doeldatabase een eigen, verse
    # AUTO_INCREMENT-waarde toekennen (id's tussen twee databases hebben
    # geen onderlinge betekenis).
    # Never carry over `id` — let the target database assign its own,
    # fresh AUTO_INCREMENT value (id's have no meaning across databases).
    cols = [c for c in rows[0].keys() if c != "id"]

    if strategy == NATIVE_UNIQUE:
        for chunk in _chunked(rows, CHUNK_SIZE):
            values_sql = ",\n    ".join(
                "(" + ", ".join(_sql_literal(row[c]) for c in cols) + ")"
                for row in chunk
            )
            lines.append(
                f"INSERT IGNORE INTO `{table}` ({_quote_cols(cols)}) VALUES\n    {values_sql};"
            )

    elif strategy == TIMESTAMP_DEDUP:
        tmp = f"_import_{table}"
        lines.append(f"DROP TEMPORARY TABLE IF EXISTS `{tmp}`;")
        lines.append(f"CREATE TEMPORARY TABLE `{tmp}` LIKE `{table}`;")
        lines.append(f"ALTER TABLE `{tmp}` DROP COLUMN `id`;")
        for chunk in _chunked(rows, CHUNK_SIZE):
            values_sql = ",\n    ".join(
                "(" + ", ".join(_sql_literal(row[c]) for c in cols) + ")"
                for row in chunk
            )
            lines.append(
                f"INSERT INTO `{tmp}` ({_quote_cols(cols)}) VALUES\n    {values_sql};"
            )
        lines.append(
            f"INSERT INTO `{table}` ({_quote_cols(cols)})\n"
            f"    SELECT {', '.join(f't.`{c}`' for c in cols)}\n"
            f"    FROM `{tmp}` t\n"
            f"    LEFT JOIN `{table}` existing ON existing.`{dedup_col}` = t.`{dedup_col}`\n"
            f"    WHERE existing.`id` IS NULL;"
        )
        lines.append(f"DROP TEMPORARY TABLE `{tmp}`;")

    elif strategy == EMPTY_ONLY:
        # Alleen de EERSTE rij uit de back-up — deze tabellen horen
        # hooguit 1 actieve rij te hebben.
        # Only the FIRST row from the backup — these tables should have
        # at most 1 active row.
        row = rows[0]
        select_sql = ", ".join(_sql_literal(row[c]) + f" AS `{c}`" for c in cols)
        lines.append(
            f"INSERT INTO `{table}` ({_quote_cols(cols)})\n"
            f"    SELECT {select_sql}\n"
            f"    FROM DUAL\n"
            f"    WHERE NOT EXISTS (SELECT 1 FROM `{table}`);"
        )

    return "\n".join(lines) + "\n"


def generate_backup_sql(db: DatabaseConnection, app_version: str = "") -> str:
    """
    Bouwt het volledige, veilige back-up-script op (alleen aanvullen,
    nooit vervangen/verwijderen). Kan zowel via de app als los in
    phpMyAdmin gedraaid worden.

    Builds the complete, safe backup script (add-only, never replaces/
    deletes). Can be run either through the app or standalone in
    phpMyAdmin.
    """
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    header = f"""--
-- HA Energy Optimizer — database-back-up / database backup
-- Gegenereerd op / generated on: {now}
-- App-versie / app version: {app_version or "onbekend/unknown"}
--
-- Dit script is ALTIJD veilig om te draaien: het voegt alleen rijen toe
-- die nog niet bestaan en raakt bestaande data nooit aan. Zonder gevaar
-- meerdere keren te draaien, ook los in phpMyAdmin. Voor een volledige
-- "vervang alles"-restore: gebruik de restore-functie in de app zelf
-- (Database-pagina) — dat leegt eerst alle tabellen en draait dan
-- ditzelfde script tegen een lege database.
--
-- This script is ALWAYS safe to run: it only adds rows that don't
-- already exist and never touches existing data. Safe to run multiple
-- times, including standalone in phpMyAdmin. For a full "replace
-- everything" restore: use the restore function in the app itself
-- (Database page) — that empties all tables first, then runs this same
-- script against an empty database.
--

"""
    blocks = [header]
    for table, strategy, dedup_col in TABLES:
        try:
            blocks.append(_generate_table_block(db, table, strategy, dedup_col))
        except Exception:
            logger.exception(f"Kon back-up-blok voor tabel {table} niet genereren "
                              f"/ could not generate backup block for table {table}")
            blocks.append(f"{TABLE_MARKER.format(table=table)}\n"
                           f"-- FOUT bij genereren van deze tabel, overgeslagen "
                           f"/ ERROR generating this table, skipped\n")
    return "\n".join(blocks)


def truncate_all_tables(db: DatabaseConnection) -> list[dict]:
    """
    Maakt alle 18 tabellen leeg, voor "vervangen"-modus. Rapporteert per
    tabel of het lukte, in plaats van bij de eerste fout te stoppen.

    Empties all 18 tables, for "replace" mode. Reports success per table
    instead of stopping at the first failure.
    """
    results = []
    # Omgekeerde volgorde is hier niet functioneel nodig (geen FOREIGN
    # KEY's in dit schema), maar wel zo gekozen voor symmetrie met de
    # opbouwvolgorde.
    # Reverse order isn't functionally required here (no FOREIGN KEYs in
    # this schema), but chosen for symmetry with the build order.
    for table, _strategy, _col in reversed(TABLES):
        try:
            with db.cursor() as cur:
                cur.execute(f"TRUNCATE TABLE `{table}`")
            results.append({"table": table, "ok": True, "error": None})
        except Exception as e:
            logger.exception(f"Kon tabel {table} niet leegmaken / could not truncate table {table}")
            results.append({"table": table, "ok": False, "error": str(e)})
    return results


def restore_from_sql(db: DatabaseConnection, sql_text: str, replace: bool) -> list[dict]:
    """
    Voert een back-up-script uit, per tabel apart zodat een fout in één
    tabel de rest niet blokkeert. Retourneert een lijst met resultaten
    per tabel voor weergave in de GUI.

    Runs a backup script, per table separately so a failure in one table
    doesn't block the rest. Returns a list of per-table results for
    display in the GUI.
    """
    results = []

    if replace:
        results.extend(truncate_all_tables(db))

    # Splits het script op de tabel-markers, zodat elke tabel apart en
    # met eigen foutafhandeling gedraaid kan worden.
    # Split the script on the table markers, so each table can be run
    # separately with its own error handling.
    marker_prefix = "-- ===== TABLE: "
    blocks: dict[str, list[str]] = {}
    current_table = None
    for line in sql_text.splitlines():
        if line.startswith(marker_prefix):
            current_table = line[len(marker_prefix):].rstrip(" =").strip()
            blocks[current_table] = []
        elif current_table is not None:
            blocks[current_table].append(line)

    for table, _strategy, _col in TABLES:
        block_lines = blocks.get(table)
        if not block_lines:
            results.append({"table": table, "ok": True, "error": None, "note": "niet in bestand / not in file"})
            continue
        block_sql = "\n".join(block_lines).strip()
        if not block_sql or block_sql.startswith("-- (geen rijen"):
            results.append({"table": table, "ok": True, "error": None, "note": "leeg / empty"})
            continue
        try:
            with db.cursor() as cur:
                # Meerdere statements in één keer — zelfde patroon als
                # setup.py's schema.sql-uitvoering.
                # Multiple statements at once — same pattern as
                # setup.py's schema.sql execution.
                cur.execute(block_sql)
            results.append({"table": table, "ok": True, "error": None})
        except Exception as e:
            logger.exception(f"Restore van tabel {table} mislukt / restore of table {table} failed")
            results.append({"table": table, "ok": False, "error": str(e)})

    return results
