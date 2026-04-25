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
        logger.info(f"Database pool created — {config.host}:{config.port}/{config.name}")

    @contextmanager
    def cursor(self, dictionary=True):
        conn = None
        cur = None
        try:
            conn = self._pool.get_connection()
            cur = conn.cursor(dictionary=dictionary)
            yield cur
        except mysql.connector.errors.PoolError:
            import time
            time.sleep(0.5)
            conn = self._pool.get_connection()
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
