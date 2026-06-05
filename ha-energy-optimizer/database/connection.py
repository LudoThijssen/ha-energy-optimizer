# database/connection.py
#
# MySQL connection pool — works with local HA MariaDB and external databases.
# MySQL-verbindingspool — werkt met lokale HA MariaDB en externe databases.

import logging
import mysql.connector
from mysql.connector import pooling
from contextlib import contextmanager
from config.config import DatabaseConfig

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
        # Read timezone from config — default Europe/Amsterdam
        # Tijdzone uit config lezen — standaard Europe/Amsterdam
        self._timezone = getattr(config, "timezone", "Europe/Amsterdam")
        logger.info(
            f"Database pool created — {config.host}:{config.port}/{config.name} "
            f"(timezone: {self._timezone})"
        )

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
                tz_cur.execute(f"SET time_zone = '{self._timezone}'")
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
                tz_cur.execute(f"SET time_zone = '{self._timezone}'")
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
