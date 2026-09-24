#
# name:          setup.py
# part of:       ha-energy-optimizer
# location:      /ha-energy-optimizer/ha-energy-optimizer/database/setup.py
# part version:  p_v0.16
# altered:       2026-09-22
#
# p_v0.16: p_v0.15's execute(..., multi=True) vervangen door een eigen
# statement-splitter (_split_sql_statements()) + losse execute()-
# aanroepen per statement — zie de docstring bij run_migrations() voor
# de aanleiding (multi=True crashte op het testsysteem: driverversie
# ondersteunde die parameter niet).
#
# p_v0.16: replaced p_v0.15's execute(..., multi=True) with a custom
# statement splitter (_split_sql_statements()) + separate execute()
# calls per statement — see run_migrations()'s docstring for the
# background (multi=True crashed on the test system: the driver version
# didn't support that parameter). Also added a defensive skip for any
# statement that turns out empty after stripping -- comment lines.
#
# p_v0.15: run_migrations() gebruikt nu cur.execute(..., multi=True) met
# expliciete iteratie over de deelresultaten, i.p.v. een kale execute()
# op de volledige scripttekst. Zie de docstring bij run_migrations()
# voor de aanleiding (race op een traag testsysteem: "succesvol
# toegepast" gelogd terwijl een tabel nog niet echt bestond).
#
# p_v0.15: run_migrations() now uses cur.execute(..., multi=True) with
# explicit iteration over the partial results, instead of a plain
# execute() on the full script text. See run_migrations()'s docstring
# for the background (a race on a slow test system: "applied
# successfully" logged while a table didn't actually exist yet).
#
# p_v0.14: GROTE VEREENVOUDIGING — het hele stelsel van genummerde
# migraties (ALL_VERSIONS, _apply(), _is_fresh_install(), de _migrations-
# tabel) is vervangen door één aanroep die schema.sql uitvoert. Dat
# bestand is zelf volledig idempotent (CREATE TABLE IF NOT EXISTS, ADD
# COLUMN IF NOT EXISTS, CREATE INDEX IF NOT EXISTS) en beschrijft de
# actuele gewenste eindstaat — zie schema.sql p_v1.0 voor de volledige
# toelichting en de regels voor toekomstige wijzigingen.
#
# Aanleiding: de vorige structuur (losse migratiebestanden + ALL_VERSIONS-
# lijst + _migrations-tabel als poortwachter) bleek deze sessie meermaals
# foutgevoelig — migraties 21/22 waren als bestand aangemaakt maar nooit
# aan ALL_VERSIONS/de stapsgewijze route toegevoegd, waardoor ze op een
# bestaande installatie nooit draaiden zonder enige foutmelding tot het
# moment dat de ontbrekende kolom daadwerkelijk werd aangesproken. Bij
# expliciete wens van Ludo: één bestand, bij elke opstart gedraaid,
# volledig idempotent, geen aparte boekhouding meer nodig.
#
# De _migrations-tabel wordt niet langer gevuld of gecontroleerd (bewuste
# keuze — dient nu geen doel meer als poortwachter, en Ludo gaf aan er
# geen audit-log-waarde aan te hechten). Bestaat de tabel nog van een
# oudere installatie, dan blijft hij gewoon ongebruikt staan; hij wordt
# niet actief opgeruimd.
#
# LET OP — eenmalige, niet-idempotente datacorrecties (zoals de voormalige
# migratie 007, een UTC->lokale-tijd-correctie) passen NIET in dit model:
# alles in schema.sql draait bij elke opstart opnieuw. Komt zoiets ooit
# weer voor, dan moet daar een apart mechanisme voor bedacht worden
# (bijvoorbeeld een voorwaarde op de data zelf) — niet zomaar hier
# toevoegen. Voor nu gaan we ervan uit dat dit zich niet meer voordoet.
#
# p_v0.14: MAJOR SIMPLIFICATION — the entire numbered-migrations system
# (ALL_VERSIONS, _apply(), _is_fresh_install(), the _migrations table) has
# been replaced by a single call that runs schema.sql. That file is
# itself fully idempotent (CREATE TABLE IF NOT EXISTS, ADD COLUMN IF NOT
# EXISTS, CREATE INDEX IF NOT EXISTS) and describes the current desired
# end state — see schema.sql p_v1.0 for full explanation and the rules
# for future changes.
#
# Reason: the previous structure (separate migration files + ALL_VERSIONS
# list + _migrations table as gatekeeper) repeatedly proved error-prone
# this session — migrations 21/22 were created as files but never added
# to ALL_VERSIONS/the step-by-step route, so on an existing installation
# they silently never ran until the missing column was actually accessed.
# At Ludo's explicit request: one file, run on every startup, fully
# idempotent, no more separate bookkeeping needed.
#
# The _migrations table is no longer populated or checked (deliberate
# choice — it no longer serves a purpose as a gatekeeper, and Ludo
# indicated no audit-log value is attached to it). If the table still
# exists from an older installation, it's simply left unused; it is not
# actively cleaned up.
#
# NOTE — one-time, non-idempotent data corrections (like the former
# migration 007, a UTC-to-local-time fix) do NOT fit this model: everything
# in schema.sql re-runs on every startup. Should something like that ever
# be needed again, a separate mechanism must be designed for it (e.g. a
# condition on the data itself) — don't just add it here. For now we
# assume this won't recur.
#
import logging
import re
from pathlib import Path
from .connection import DatabaseConnection

logger = logging.getLogger(__name__)

SCHEMA_FILE = Path(__file__).parent / "schema.sql"


def _split_sql_statements(sql_text: str) -> list[str]:
    """
    Splitst een SQL-scripttekst in losse statements, op top-level
    puntkomma's (buiten quoted strings). Nodig omdat cur.execute()
    slechts één statement per aanroep verwerkt — een kale execute() op
    de volledige tekst gaf geen garantie dat elk statement daadwerkelijk
    voltooid was voordat de aanroep terugkeerde (zie p_v0.16-changelog).
    De eerder geprobeerde execute(..., multi=True) bleek niet
    driverversie-onafhankelijk (TypeError: unexpected keyword argument
    'multi' op de daadwerkelijk geïnstalleerde mysql-connector-python-
    versie) — deze aanpak gebruikt alleen de altijd-beschikbare kale
    execute() per statement.

    Splits a SQL script text into individual statements, on top-level
    semicolons (outside quoted strings). Needed because cur.execute()
    only handles one statement per call — a plain execute() on the full
    text gave no guarantee each statement had actually completed before
    the call returned (see the p_v0.16 changelog). The previously tried
    execute(..., multi=True) turned out not to be driver-version-
    independent (TypeError: unexpected keyword argument 'multi' on the
    actually installed mysql-connector-python version) — this approach
    only uses the always-available plain execute() per statement.
    """
    statements = []
    current = []
    in_string = False
    i = 0
    n = len(sql_text)
    while i < n:
        ch = sql_text[i]
        if in_string:
            current.append(ch)
            if ch == "'":
                if i + 1 < n and sql_text[i + 1] == "'":
                    current.append(sql_text[i + 1])
                    i += 1
                else:
                    in_string = False
            i += 1
            continue
        if ch == "'":
            in_string = True
            current.append(ch)
            i += 1
            continue
        if ch == ";":
            stmt = "".join(current).strip()
            if stmt:
                statements.append(stmt)
            current = []
            i += 1
            continue
        current.append(ch)
        i += 1
    tail = "".join(current).strip()
    if tail:
        statements.append(tail)
    return statements


def run_migrations(db: DatabaseConnection) -> None:
    """
    Voert schema.sql uit — één idempotent bestand dat de gewenste
    eindstaat van het database-schema beschrijft. Veilig om bij elke
    opstart te draaien, op elke installatie (vers of bestaand).

    p_v0.16: schema.sql wordt nu zelf in losse statements gesplitst
    (_split_sql_statements()) en één voor één met gewone execute()-
    aanroepen uitgevoerd, i.p.v. de hele tekst in één keer. Vervangt
    p_v0.15's execute(..., multi=True), dat op het testsysteem crashte
    met "TypeError: MySQLCursor.execute() got an unexpected keyword
    argument 'multi'" — die parameter bleek niet betrouwbaar aanwezig
    over mysql-connector-python-versies heen. Deze aanpak geeft dezelfde
    garantie (elk statement voltooid vóór het volgende start) zonder
    van een driverversie-specifieke flag afhankelijk te zijn.

    Runs schema.sql — a single idempotent file describing the desired
    end state of the database schema. Safe to run on every startup, on
    any installation (fresh or existing).

    p_v0.16: schema.sql is now split into individual statements itself
    (_split_sql_statements()) and run one by one with plain execute()
    calls, instead of the whole text at once. Replaces p_v0.15's
    execute(..., multi=True), which crashed on the test system with
    "TypeError: MySQLCursor.execute() got an unexpected keyword argument
    'multi'" — that parameter turned out not to be reliably present
    across mysql-connector-python versions. This approach gives the same
    guarantee (each statement completes before the next starts) without
    depending on a driver-version-specific flag.
    """
    logger.info(f"Schema wordt toegepast vanuit {SCHEMA_FILE.name} "
                f"/ applying schema from {SCHEMA_FILE.name}")
    try:
        schema_sql = SCHEMA_FILE.read_text()
        statements = _split_sql_statements(schema_sql)
        with db.cursor() as cur:
            for stmt in statements:
                # Defensief vangnet: sla statements over die na het
                # verwijderen van --commentaarregels leeg blijken te zijn
                # (voorkomt een execute() op pure commentaartekst, mocht
                # een commentaarregel ooit per ongeluk een ; bevatten).
                # Defensive safety net: skip statements that turn out
                # empty once --comment lines are stripped (prevents an
                # execute() on pure comment text, should a comment line
                # ever accidentally contain a ;).
                code_only = re.sub(r'(?m)^\s*--.*$', '', stmt).strip()
                if not code_only:
                    continue
                cur.execute(stmt)
        logger.info(f"Schema succesvol toegepast ({len(statements)} statements) "
                    f"/ schema applied successfully ({len(statements)} statements)")
    except Exception:
        logger.exception("Toepassen van schema.sql is MISLUKT "
                          "/ applying schema.sql FAILED")
        raise

    # Vul vertalingstabel met standaardteksten (INSERT IGNORE — overschrijft geen aanpassingen)
    # Fill translation table with default texts (INSERT IGNORE — does not overwrite customisations)
    from translations.seed_translations import run_seed
    run_seed(db)
