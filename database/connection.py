# database/connection.py
#
# MySQL connection pool — works with both local and NAS-hosted databases.
# MySQL-verbindingspool — werkt zowel met lokale als NAS-gehoste databases.
#
# Uses a pool of 5 connections so multiple modules can read/write simultaneously.
# Gebruikt een pool van 5 verbindingen zodat meerdere modules tegelijk kunnen lezen/schrijven.

import mysql.connector
from mysql.connector import pooling
from contextlib import contextmanager
from config.config import DatabaseConfig


class DatabaseConnection:
    def __init__(self, config: DatabaseConfig):
        self._pool = pooling.MySQLConnectionPool(
            pool_name="energy_pool",
            pool_size=5,
            host=config.host,
            port=config.port,
            database=config.name,
            user=config.user,
            password=config.password,
            charset="utf8mb4",
            autocommit=False,
            connection_timeout=10,
        )

    @contextmanager
    def cursor(self, dictionary=True):
        conn = self._pool.get_connection()
        cur = conn.cursor(dictionary=dictionary)
        try:
            yield cur
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            cur.close()
            conn.close()
