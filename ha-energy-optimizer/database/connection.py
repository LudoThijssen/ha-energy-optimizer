#
# name:          connection.py
# part of:       ha-energy-optimizer
# location:      /ha-energy-optimizer/ha-energy-optimizer/database/connection.py
# part version:  p_v0.3
# altered:       2026-06-21
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


class DatabaseConnection:
    def __init__(self, config: DatabaseConfig):
        # Compute timezone offset before creating pool
        # Tijdzone-offset berekenen voor aanmaken van de pool
        tz_name = getattr(config, "timezone", "Europe/Amsterdam")
        self._tz_offset = self._compute_utc_offset(tz_name)

        self._pool = pooling.MySQLConnectionPool(
            pool_name="energy_pool",
            pool_size=10,           # Increased from 5 / Verhoogd van 5
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

        Geeft een cursor terug uit de pool.
        De sessietijdzone wordt ingesteld via init_command op elke nieuwe verbinding.
        Verbindingen worden gepingd en hersteld indien verouderd (bijv. gesloten
        door MariaDB's wait_timeout terwijl ze idle in de pool stonden).
        """
        conn = None
        cur  = None
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
        finally:
            try:
                if cur:
                    cur.close()
            except Exception:
                pass
            try:
                if conn:
                    conn.close()
            except Exception:
                pass
