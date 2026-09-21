#
# name:          setup.py
# part of:       ha-energy-optimizer
# location:      /ha-energy-optimizer/ha-energy-optimizer/database/setup.py
# part version:  p_v0.15
# altered:       2026-09-17
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
from pathlib import Path
from .connection import DatabaseConnection

logger = logging.getLogger(__name__)

SCHEMA_FILE = Path(__file__).parent / "schema.sql"


def run_migrations(db: DatabaseConnection) -> None:
    """
    Voert schema.sql uit — één idempotent bestand dat de gewenste
    eindstaat van het database-schema beschrijft. Veilig om bij elke
    opstart te draaien, op elke installatie (vers of bestaand).

    p_v0.15: cur.execute(..., multi=True) i.p.v. een kale execute() op de
    volledige (240-statements-)tekst. Zonder multi=True is er geen harde
    garantie dat de driver écht op voltooiing van elk afzonderlijk
    statement wacht voordat execute() teruggeeft — op een trager
    testsysteem gaf dit één keer een race: "Schema succesvol toegepast"
    verscheen in het log, maar de eerstvolgende query
    (translation_strings vullen) faalde met "Table ... doesn't exist"
    omdat de CREATE TABLE ervoor kennelijk nog niet volledig was
    doorgevoerd. Bij een tweede, losse pogingen (herstart) ging het
    zonder problemen. multi=True + expliciet door de deelresultaten
    itereren dwingt af dat elk statement daadwerkelijk voltooid is
    voordat de functie verdergaat.

    Runs schema.sql — a single idempotent file describing the desired
    end state of the database schema. Safe to run on every startup, on
    any installation (fresh or existing).

    p_v0.15: cur.execute(..., multi=True) instead of a plain execute() on
    the full (240-statement) text. Without multi=True there's no hard
    guarantee the driver actually waits for each individual statement to
    finish before execute() returns — on a slower test system this once
    produced a race: "Schema applied successfully" appeared in the log,
    but the very next query (populating translation_strings) failed with
    "Table ... doesn't exist" because the CREATE TABLE before it hadn't
    apparently fully landed yet. A second, separate attempt (restart)
    worked fine. multi=True plus explicitly iterating the partial results
    forces each statement to actually complete before the function
    continues.
    """
    logger.info(f"Schema wordt toegepast vanuit {SCHEMA_FILE.name} "
                f"/ applying schema from {SCHEMA_FILE.name}")
    try:
        schema_sql = SCHEMA_FILE.read_text()
        with db.cursor() as cur:
            for _ in cur.execute(schema_sql, multi=True):
                pass  # doorlopen dwingt voltooiing van elk statement af / iterating forces each statement to complete
        logger.info("Schema succesvol toegepast / schema applied successfully")
    except Exception:
        logger.exception("Toepassen van schema.sql is MISLUKT "
                          "/ applying schema.sql FAILED")
        raise

    # Vul vertalingstabel met standaardteksten (INSERT IGNORE — overschrijft geen aanpassingen)
    # Fill translation table with default texts (INSERT IGNORE — does not overwrite customisations)
    from translations.seed_translations import run_seed
    run_seed(db)
