# database/connection.py
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
        self._pool = pooling.MySQLConnectionPool(
            pool_name="energy_pool",
            pool_size=10,           # Increased from 5 / Verhoogd van 5
            pool_reset_session=True,
            host=config.host,
            port=config.port,
            database=config.name,
            user=config.user,
            password=config.password,
            charset="utf8mb4",
            autocommit=True,        # Simpler — each statement commits immediately
            connection_timeout=10,
            connect_timeout=10,
        )
        # Compute UTC offset for session timezone (avoids missing tzinfo tables)
        # UTC-offset berekenen voor sessietijdzone (vermijdt ontbrekende tzinfo-tabellen)
        tz_name = getattr(config, "timezone", "Europe/Amsterdam")
        self._tz_offset = self._compute_utc_offset(tz_name)
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
        Yield a cursor with the session timezone set to the configured local timezone.
        This ensures NOW(), CURDATE() and all datetime comparisons use local time,
        regardless of the MariaDB server timezone setting.

        Geeft een cursor terug met de sessietijdzone ingesteld op de geconfigureerde
        lokale tijdzone. Dit zorgt ervoor dat NOW(), CURDATE() en alle
        datetime-vergelijkingen lokale tijd gebruiken, ongeacht de MariaDB-servertijdzone.
        """
        conn = None
        cur = None
        try:
            conn = self._pool.get_connection()
            # Set session timezone before yielding cursor
            # Sessietijdzone instellen vóór het teruggeven van de cursor
            tz_cur = conn.cursor()
            try:
                tz_cur.execute(f"SET time_zone = '{self._tz_offset}'")
            finally:
                tz_cur.close()
            cur = conn.cursor(dictionary=dictionary)
            yield cur
        except mysql.connector.errors.PoolError:
            import time
            time.sleep(0.5)
            conn = self._pool.get_connection()
            tz_cur = conn.cursor()
            try:
                tz_cur.execute(f"SET time_zone = '{self._tz_offset}'")
            finally:
                tz_cur.close()
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
