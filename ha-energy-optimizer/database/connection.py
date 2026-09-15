#
# name:          connection.py
# part of:       ha-energy-optimizer
# location:      /ha-energy-optimizer/ha-energy-optimizer/database/connection.py
# part version:  p_v0.5
# altered:       2026-09-15
#
# p_v0.5: _warm_up_pool() toegevoegd — direct na het aanmaken van de pool
# wordt elke connectie één keer gebruikt, zodat de mysql-connector
# sql_mode-fetch-fout (p_v0.4) al bij het opstarten wegwerkt i.p.v. bij
# de eerste echte collector-query. Puur voor een schoon log — de fout was
# met p_v0.4 al onschadelijk, dit voorkomt alleen dat 'm nog zichtbaar is.
#
# p_v0.5: _warm_up_pool() added — right after the pool is created, every
# connection is used once, so the mysql-connector sql_mode-fetch bug
# (p_v0.4) is worked through during startup instead of on a collector's
# first real query. Purely for a clean log — the error was already
# harmless as of p_v0.4, this just stops it from being visible at all.
#
# p_v0.4: cursor() forceert nu een reconnect op de onderliggende connectie
# als er tijdens het gebruik een fout optreedt, vóórdat de connectie
# teruggegeven wordt aan de pool. Zie de docstring bij cursor() voor de
# volledige toelichting — root cause van herhaalde "NoneType object is
# not subscriptable" / "MySQL Connection not available"-fouten bij
# ConsumptionLearner/SolarLearner.predict().
#
# p_v0.4: cursor() now forces a reconnect on the underlying connection if
# an error occurs while it's in use, before returning the connection to
# the pool. See the cursor() docstring for the full explanation — root
# cause of repeated "NoneType object is not subscriptable" / "MySQL
# Connection not available" errors in
# ConsumptionLearner/SolarLearner.predict().
#
# MySQL connection pool — works with local HA MariaDB and external databases.
# MySQL-verbindingspool — werkt met lokale HA MariaDB en externe databases.

import logging
import mysql.connector
from mysql.connector import pooling
from contextlib import contextmanager
from config.config import DatabaseConfig
from datetime import datetime, timezone as _tz
import zoneinfo

logger = logging.getLogger(__name__)

_POOL_SIZE = 10  # Increased from 5 / Verhoogd van 5


class DatabaseConnection:
    def __init__(self, config: DatabaseConfig):
        # Compute timezone offset before creating pool
        # Tijdzone-offset berekenen voor aanmaken van de pool
        tz_name = getattr(config, "timezone", "Europe/Amsterdam")
        self._tz_offset = self._compute_utc_offset(tz_name)

        self._pool = pooling.MySQLConnectionPool(
            pool_name="energy_pool",
            pool_size=_POOL_SIZE,
            pool_reset_session=False,  # True would reset SET time_zone — keep False / True wist SET time_zone — False houden
            host=config.host,
            port=config.port,
            database=config.name,
            user=config.user,
            password=config.password,
            charset="utf8mb4",
            autocommit=True,        # Simpler — each statement commits immediately
            connection_timeout=10,
            connect_timeout=10,
            init_command=f"SET time_zone = '{self._compute_utc_offset(tz_name)}'",
        )
        logger.info(
            f"Database pool created — {config.host}:{config.port}/{config.name} "
            f"(timezone: {tz_name}, offset: {self._tz_offset})"
        )
        self._warm_up_pool()

    def _warm_up_pool(self) -> None:
        """
        Warmt alle pool-connecties direct na aanmaak op door er een kleine
        dict-parameter-query op te draaien. Voorkomt de eenmalige
        mysql-connector sql_mode-fetch-fout (zie cursor() p_v0.4) bij de
        allereerste echte query van een collector na opstarten — dat
        foutje was al onschadelijk (afgevangen door run_safe()), maar
        rommel in het log verstoort het zoeken naar echte problemen.

        Sequentieel lenen-en-teruggeven, precies _POOL_SIZE keer: de pool
        geeft zijn vooraf aangemaakte connecties in FIFO-volgorde uit, dus
        dit raakt elke onderliggende connectie exact één keer, zonder dat
        er iets over hun interne volgorde aangenomen hoeft te worden
        anders dan "eerst geleend, eerst teruggegeven, eerst weer
        uitgegeven".

        Warms up all pool connections right after creation by running a
        small dict-parameter query on each. Prevents the one-time
        mysql-connector sql_mode-fetch bug (see cursor() p_v0.4) on a
        collector's very first real query after startup — that glitch was
        already harmless (caught by run_safe()), but log clutter makes it
        harder to spot real problems.

        Sequential borrow-and-return, exactly _POOL_SIZE times: the pool
        hands out its pre-created connections in FIFO order, so this
        touches every underlying connection exactly once, without
        assuming anything about their internal order beyond "first
        borrowed, first returned, first handed out again".
        """
        warmed = 0
        for _ in range(_POOL_SIZE):
            try:
                with self.cursor() as cur:
                    cur.execute("SELECT %(one)s AS one", {"one": 1})
                    cur.fetchone()
                warmed += 1
            except Exception:
                logger.warning(
                    "Kon een pool-connectie niet opwarmen (niet kritiek, "
                    "wordt later alsnog automatisch hersteld) / "
                    "Could not warm up a pool connection (non-critical, "
                    "will still self-heal automatically later)"
                )
        logger.info(
            f"Pool opgewarmd — {warmed}/{_POOL_SIZE} connecties klaar / "
            f"pool warmed up — {warmed}/{_POOL_SIZE} connections ready"
        )

    @staticmethod
    def _compute_utc_offset(tz_name: str) -> str:
        """
        Convert a timezone name to a MariaDB-compatible UTC offset string.
        Uses Python's zoneinfo — no MariaDB timezone tables needed.
        Example: 'Europe/Amsterdam' in summer → '+02:00', winter → '+01:00'

        Converteert een tijdzonenaam naar een MariaDB-compatibele UTC-offsetstring.
        Gebruikt Python's zoneinfo — geen MariaDB tijdzonetabellen nodig.
        """
        try:
            zi = zoneinfo.ZoneInfo(tz_name)
            now = datetime.now(_tz.utc).astimezone(zi)
            offset = now.utcoffset()
            total_seconds = int(offset.total_seconds())
            sign = "+" if total_seconds >= 0 else "-"
            total_seconds = abs(total_seconds)
            hours, remainder = divmod(total_seconds, 3600)
            minutes = remainder // 60
            return f"{sign}{hours:02d}:{minutes:02d}"
        except Exception:
            logger.warning(
                f"Could not determine UTC offset for '{tz_name}' — "
                f"falling back to +00:00 / Kan UTC-offset niet bepalen — terugval op +00:00"
            )
            return "+00:00"

    @contextmanager
    def cursor(self, dictionary=True):
        """
        Yield a cursor from the pool.
        The session timezone is set via init_command on every new connection.
        Connections are pinged and reconnected if stale (e.g. closed by
        MariaDB's wait_timeout while idle in the pool).

        p_v0.4: als er tijdens het gebruik van de cursor een fout optreedt
        (bv. de mysql-connector sql_mode-bug bij het allereerste gebruik
        van een verse pool-connectie), wordt de connectie vóór teruggave
        aan de pool geforceerd opnieuw verbonden (reconnect). Zonder dit
        kwam een connectie die middenin een mislukte query zat — met
        pool_reset_session=False blijft de sessie tussen leningen namelijk
        bewust ongereset (voor de tijdzone-instelling) — in diezelfde
        beschadigde staat terug in de pool, en faalde de volgende lener
        die toevallig dezelfde connectie trof opnieuw. Zichtbaar geworden
        bij ConsumptionLearner/SolarLearner.predict(), die honderden keren
        na elkaar een cursor lenen tijdens de rolling-horizon-opbouw in
        optimizer/engine.py.

        Geeft een cursor terug uit de pool.
        De sessietijdzone wordt ingesteld via init_command op elke nieuwe verbinding.
        Verbindingen worden gepingd en hersteld indien verouderd (bijv. gesloten
        door MariaDB's wait_timeout terwijl ze idle in de pool stonden).

        p_v0.4: if an error occurs while the cursor is in use (e.g. the
        mysql-connector sql_mode bug on the very first use of a fresh pool
        connection), the connection is forced to reconnect before being
        returned to the pool. Without this, a connection that was mid-
        query when it failed — since pool_reset_session=False deliberately
        leaves the session unreset between borrows (for the timezone
        setting) — would go back into the pool in that same damaged state,
        and the next borrower unlucky enough to get the same connection
        would fail again too. This became visible via
        ConsumptionLearner/SolarLearner.predict(), which borrow a cursor
        hundreds of times in a row while building the rolling horizon in
        optimizer/engine.py.
        """
        conn = None
        cur  = None
        had_error = False
        try:
            try:
                conn = self._pool.get_connection()
            except mysql.connector.errors.PoolError:
                import time
                time.sleep(0.5)
                conn = self._pool.get_connection()

            # Detect and recover from stale connections
            # Verouderde verbindingen detecteren en herstellen
            try:
                conn.ping(reconnect=True, attempts=2, delay=0.5)
            except mysql.connector.errors.Error:
                # Connection beyond recovery — release and get a fresh one
                # Verbinding niet meer te herstellen — vrijgeven en nieuwe ophalen
                try:
                    conn.close()
                except Exception:
                    pass
                conn = self._pool.get_connection()
                conn.ping(reconnect=True, attempts=2, delay=0.5)

            cur = conn.cursor(dictionary=dictionary)
            yield cur
        except Exception:
            had_error = True
            raise
        finally:
            try:
                if cur:
                    cur.close()
            except Exception:
                pass
            if conn is not None and had_error:
                try:
                    conn.reconnect(attempts=1, delay=0)
                except Exception:
                    logger.warning(
                        "Kon beschadigde connectie niet herstellen na fout — "
                        "wordt alsnog teruggegeven aan de pool / "
                        "Could not repair damaged connection after error — "
                        "returning to pool anyway"
                    )
            try:
                if conn:
                    conn.close()
            except Exception:
                pass
