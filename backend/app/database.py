import os
import threading
from contextlib import contextmanager

import psycopg2
from psycopg2 import pool as pg_pool  # NOT set up by a bare `import psycopg2`
from dotenv import load_dotenv


# Load environment variables from backend/.env
load_dotenv()


DB_CONFIG = {
    "host": os.getenv("DB_HOST", "localhost"),
    "port": os.getenv("DB_PORT", "5432"),
    "database": os.getenv("DB_NAME", "ai_travel_planner"),
    "user": os.getenv("DB_USER", "postgres"),
    "password": os.getenv("DB_PASSWORD"),
}


# Starlette runs sync `def` endpoints in anyio's worker threadpool, whose
# default CapacityLimiter is 40. psycopg2's pool raises PoolError the instant
# maxconn is reached -- it never waits -- so POOL_MAX must cover that many
# concurrent requests. POOL_MIN is what actually stays warm: psycopg2
# physically closes anything returned above POOL_MIN.
POOL_MIN = int(os.getenv("DB_POOL_MIN", "2"))
POOL_MAX = int(os.getenv("DB_POOL_MAX", "40"))


_pool = None
_pool_lock = threading.Lock()


def get_pool():
    """Return the process-wide pool, creating it on first use.

    Built lazily because ThreadedConnectionPool opens POOL_MIN connections in
    its constructor and so raises if Postgres is down. Lazy creation means a
    down database never stops the app from booting.
    """
    global _pool

    if _pool is None:
        with _pool_lock:
            if _pool is None:
                _pool = pg_pool.ThreadedConnectionPool(
                    POOL_MIN,
                    POOL_MAX,
                    **DB_CONFIG,
                )

    return _pool


def close_pool():
    """Close every pooled connection. Called once on app shutdown."""
    global _pool

    with _pool_lock:
        # closeall() raises PoolError if the pool is already closed.
        if _pool is not None and not _pool.closed:
            _pool.closeall()

        _pool = None


def _safe_rollback(connection):
    """Roll back, tolerating an already-dead connection.

    rollback() raises InterfaceError("connection already closed") when the
    server has gone away, which would otherwise mask the real OperationalError.
    """
    try:
        connection.rollback()
    except psycopg2.Error:
        pass


@contextmanager
def get_cursor(commit: bool = False):
    """Yield a cursor, then ALWAYS return the connection to the pool.

    Commits on clean exit when commit=True, rolls back on any exception, and
    returns the connection in a finally so it can never leak.

    Note: `with connection:` is deliberately NOT used -- in psycopg2 that
    commits unconditionally and does not close/return the connection.
    """
    pool = get_pool()
    connection = pool.getconn()

    try:
        with connection.cursor() as cursor:
            yield cursor

        if commit:
            connection.commit()
        else:
            # End the read transaction so the connection goes back IDLE
            # rather than "idle in transaction".
            _safe_rollback(connection)

    except Exception:
        _safe_rollback(connection)
        raise

    finally:
        pool.putconn(connection)  # replaces close(); never call conn.close()


def create_tables():
    with get_cursor(commit=True) as cursor:
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS trips (
                id SERIAL PRIMARY KEY,
                destination VARCHAR(255) NOT NULL,
                country VARCHAR(255) DEFAULT '',
                days INTEGER NOT NULL,
                travelers INTEGER NOT NULL,
                budget NUMERIC NOT NULL,
                travel_style VARCHAR(100) DEFAULT 'balanced',
                interests TEXT,
                plan JSONB,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
