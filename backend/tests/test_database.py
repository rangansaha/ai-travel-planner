"""Tests for the connection pool in app/database.py.

The bug these lock in is a per-request connection LEAK: every request used to
open its own connection via `get_connection()` and nothing closed it when the
request failed, so each failure stranded one connection forever. `get_cursor`
now takes a connection from a pool and returns it in a `finally`.

So the assertion that matters is arithmetic, not stylistic: after N blocks --
successful, failed, or concurrent -- the pool must have exactly zero
connections checked out. Every loop below runs more than POOL_MAX iterations,
because psycopg2 raises PoolError the instant maxconn is reached and never
waits, so a leak does not merely look untidy: it kills the process.
"""

import subprocess
import sys
import threading
from pathlib import Path
from uuid import uuid4

import psycopg2
import pytest
from psycopg2 import extensions as pg_ext
from psycopg2 import pool as pg_pool

from app import database
from app.database import get_cursor


# One more than the pool can hold, so any leak is fatal rather than cosmetic:
# with the `finally` removed these loops die on iteration POOL_MAX + 1.
LEAK_CYCLES = database.POOL_MAX + 5

# Comfortably under POOL_MAX, which is what makes concurrency legal at all.
CONCURRENT_BLOCKS = 16

_BACKEND_ROOT = Path(__file__).resolve().parent.parent


# ============================================================
# HELPERS
# ============================================================

class _Boom(Exception):
    """Raised inside a get_cursor block to drive the error path."""


class _FakeConnection:
    """Stand-in for a connection: _safe_rollback only calls rollback()."""

    def __init__(self, error=None):
        self.error = error
        self.rollbacks = 0

    def rollback(self):
        self.rollbacks += 1

        if self.error is not None:
            raise self.error


def _checked_out(pool) -> int:
    """How many connections psycopg2 still believes a caller is holding.

    `_used` is the pool's own key -> connection map of handed-out connections;
    it is the ledger a leak shows up in. `_pool` is the idle free list.
    """
    return len(pool._used)


def _rows(table: str) -> list:
    """Read a scratch table through a fresh block, so only committed data."""
    with get_cursor() as cursor:
        cursor.execute(f"SELECT value FROM {table} ORDER BY value")

        return [row[0] for row in cursor.fetchall()]


# ============================================================
# FIXTURES
# ============================================================

@pytest.fixture
def scratch_table():
    """An empty single-column table, dropped again afterwards.

    Deliberately a real table and not a TEMPORARY one: a temp table lives in
    one session, and the pool hands each block whichever connection happens
    to be free, so a temp table would be invisible to the block that checks it.
    """
    name = f"pytest_scratch_{uuid4().hex}"

    with get_cursor(commit=True) as cursor:
        cursor.execute(f"CREATE TABLE {name} (value TEXT)")

    try:
        yield name

    finally:
        with get_cursor(commit=True) as cursor:
            cursor.execute(f"DROP TABLE IF EXISTS {name}")


@pytest.fixture
def handback_statuses(monkeypatch):
    """Record each connection's transaction status as get_cursor hands it back.

    Measured at hand-back and not after the block because psycopg2's putconn
    rolls back anything it finds mid-transaction, which would tidy away the
    very difference these tests exist to catch.
    """
    pool = database.get_pool()
    statuses = []
    putconn = pool.putconn

    def spy(conn=None, key=None, close=False):
        statuses.append(conn.info.transaction_status)

        return putconn(conn, key, close)

    monkeypatch.setattr(pool, "putconn", spy)

    return statuses


@pytest.fixture
def fake_pool(monkeypatch):
    """Replace ThreadedConnectionPool so pool wiring is testable with no server.

    Yields the list of pools that got built, newest last, so a test can prove
    how many constructions happened rather than only comparing identities.
    """
    built = []

    class FakePool:

        def __init__(self, minconn, maxconn, **config):
            self.minconn = minconn
            self.maxconn = maxconn
            self.config = config
            self.closed = False

            built.append(self)

        def closeall(self):
            # psycopg2 raises instead of closing twice. close_pool's `.closed`
            # guard exists solely because of this, so the fake must copy it.
            if self.closed:
                raise pg_pool.PoolError("connection pool is closed")

            self.closed = True

    monkeypatch.setattr(database.pg_pool, "ThreadedConnectionPool", FakePool)

    return built


# ============================================================
# THE LEAK
# ============================================================

@pytest.mark.db
def test_successful_blocks_return_every_connection():
    pool = database.get_pool()

    for _ in range(LEAK_CYCLES):
        with get_cursor() as cursor:
            cursor.execute("SELECT 1")

            assert cursor.fetchone()[0] == 1

    assert _checked_out(pool) == 0
    assert pool._rused == {}

    # POOL_MIN connections stay warm; the point is they are in the free list
    # and not in some caller's hands.
    assert pool._pool


@pytest.mark.db
def test_failing_blocks_return_every_connection():
    """The path that actually leaked: nothing returned the connection.

    commit=True as well, so this also covers "commit was requested but the
    block blew up first".
    """
    pool = database.get_pool()

    for _ in range(LEAK_CYCLES):
        with pytest.raises(_Boom):
            with get_cursor(commit=True) as cursor:
                cursor.execute("SELECT 1")

                raise _Boom("the caller's code failed mid-block")

    assert _checked_out(pool) == 0
    assert pool._rused == {}


@pytest.mark.db
def test_failing_statements_return_every_connection_and_leave_it_usable():
    """A failure from the server, not from the caller.

    Two separate hazards here: the connection must come back, and it must come
    back rolled back -- a connection returned mid-aborted-transaction poisons
    whichever later request picks it up ("current transaction is aborted").
    """
    pool = database.get_pool()

    for _ in range(LEAK_CYCLES):
        with pytest.raises(psycopg2.Error):
            with get_cursor(commit=True) as cursor:
                cursor.execute("SELECT * FROM a_table_that_does_not_exist")

    assert _checked_out(pool) == 0

    with get_cursor() as cursor:
        cursor.execute("SELECT 1")

        assert cursor.fetchone()[0] == 1


@pytest.mark.db
def test_a_leaked_connection_really_does_exhaust_the_pool(monkeypatch):
    """The canary for the three tests above.

    Those tests assert that nothing leaks; this one proves that assertion has
    teeth by reinstating the pre-fix behaviour -- a get_cursor that never gives
    the connection back -- and showing the pool is dead a few calls later.
    POOL_MAX is dialled down first so this costs 4 connections, not 41.
    """
    monkeypatch.setattr(database, "POOL_MAX", 3)

    pool = database.get_pool()

    # Read the bound off the pool rather than trusting the monkeypatch: if an
    # earlier caller already built the pool, the loop must still be correct.
    monkeypatch.setattr(pool, "putconn", lambda *args, **kwargs: None)

    with pytest.raises(pg_pool.PoolError):
        for _ in range(pool.maxconn + 1):
            with get_cursor() as cursor:
                cursor.execute("SELECT 1")

    assert _checked_out(pool) == pool.maxconn


@pytest.mark.db
def test_concurrent_blocks_all_succeed_and_leak_nothing():
    """POOL_MAX is 40 because anyio runs sync `def` endpoints in a 40-thread
    pool, so 40 requests really can be inside get_cursor at once.
    """
    assert CONCURRENT_BLOCKS < database.POOL_MAX

    pool = database.get_pool()

    barrier = threading.Barrier(CONCURRENT_BLOCKS)
    observed = []
    results = []
    failures = []

    def worker(index):
        try:
            with get_cursor() as cursor:
                # Nobody proceeds until everyone is inside a block, so all the
                # connections are genuinely held at the same instant. Without
                # this the threads could serialise and reuse one connection,
                # and the test would prove nothing about concurrency.
                barrier.wait(timeout=30)

                observed.append(_checked_out(pool))

                cursor.execute("SELECT %s", (index,))
                results.append(cursor.fetchone()[0])

        except BaseException as exc:
            failures.append(exc)

            # Free anyone still waiting instead of making them time out.
            barrier.abort()

    threads = [
        threading.Thread(target=worker, args=(index,))
        for index in range(CONCURRENT_BLOCKS)
    ]

    for thread in threads:
        thread.start()

    for thread in threads:
        thread.join(timeout=60)

    assert [thread for thread in threads if thread.is_alive()] == []
    assert failures == []
    assert sorted(results) == list(range(CONCURRENT_BLOCKS))

    # The first thread to look after the barrier releases sees every block
    # still holding its connection, because a thread only leaves its block
    # after it has looked. Hence max(), not each observation.
    assert max(observed) == CONCURRENT_BLOCKS

    assert _checked_out(pool) == 0


@pytest.mark.db
def test_a_read_block_hands_back_an_idle_connection(handback_statuses):
    """commit=False must still end the transaction.

    Rolling back on the clean read path is what stops the connection going
    home "idle in transaction", where it would hold its snapshot and pin the
    xmin horizon for as long as it sat in the pool.
    """
    with get_cursor() as cursor:
        cursor.execute("SELECT 1")
        cursor.fetchone()

    assert handback_statuses == [pg_ext.TRANSACTION_STATUS_IDLE]


@pytest.mark.db
def test_a_failed_block_hands_back_an_idle_connection(handback_statuses):
    """Returning the connection is only half the fix -- it has to be clean.

    A failed statement leaves the connection INERROR, and a connection put
    back in that state fails every later request that borrows it with
    "current transaction is aborted". get_cursor rolls back before the
    handback rather than leaving it to whoever picks the connection up next.
    """
    with pytest.raises(psycopg2.Error):
        with get_cursor(commit=True) as cursor:
            cursor.execute("SELECT * FROM a_table_that_does_not_exist")

    assert handback_statuses == [pg_ext.TRANSACTION_STATUS_IDLE]


# ============================================================
# COMMIT SEMANTICS
# ============================================================

@pytest.mark.db
def test_commit_true_persists(scratch_table):
    with get_cursor(commit=True) as cursor:
        cursor.execute(f"INSERT INTO {scratch_table} (value) VALUES ('kept')")

    assert _rows(scratch_table) == ["kept"]


@pytest.mark.db
def test_commit_false_does_not_persist(scratch_table):
    """The default. Read paths must not be able to write by accident.

    `with connection:` would break exactly this -- in psycopg2 it commits
    unconditionally on clean exit -- which is why get_cursor does not use it.
    """
    with get_cursor() as cursor:
        cursor.execute(f"INSERT INTO {scratch_table} (value) VALUES ('dropped')")

    assert _rows(scratch_table) == []


@pytest.mark.db
def test_an_exception_rolls_back_the_whole_block(scratch_table):
    """commit=True, one row already written, then the block fails.

    A partial write must not survive: the request that asked for the commit
    never finished.
    """
    with pytest.raises(_Boom):
        with get_cursor(commit=True) as cursor:
            cursor.execute(f"INSERT INTO {scratch_table} (value) VALUES ('first')")
            cursor.execute(f"INSERT INTO {scratch_table} (value) VALUES ('second')")

            raise _Boom("failed after writing")

    assert _rows(scratch_table) == []


@pytest.mark.db
def test_the_block_exception_reaches_the_caller_unchanged():
    """get_cursor must not swallow or rewrap: main.py dispatches on the type
    of what comes out to pick between 404, 502 and 503.
    """
    boom = _Boom("this exact object")

    with pytest.raises(_Boom) as caught:
        with get_cursor() as cursor:
            cursor.execute("SELECT 1")

            raise boom

    assert caught.value is boom


# ============================================================
# POOL LIFECYCLE
# ============================================================

def test_importing_the_module_opens_no_pool():
    """Nothing may connect at import time.

    ThreadedConnectionPool opens POOL_MIN connections in its constructor, so a
    pool built at import means a down database stops the app from booting --
    the exact failure that used to break `import app.main`. Checked in a
    subprocess because app.database is already imported here, and by every
    other test file, so an in-process assertion would only report what some
    earlier test happened to leave behind.
    """
    probe = subprocess.run(
        [sys.executable, "-c", "import app.database as d; print(d._pool is None)"],
        cwd=_BACKEND_ROOT,
        capture_output=True,
        text=True,
        timeout=120,
    )

    assert probe.returncode == 0, probe.stderr
    assert probe.stdout.strip() == "True"


def test_get_pool_builds_one_pool_and_remembers_it(fake_pool):
    """Lazy is not enough -- it must also be built exactly once.

    A get_pool that rebuilt per call would open POOL_MIN connections per
    request and be a slower leak than the one this module fixed.
    """
    first = database.get_pool()
    second = database.get_pool()

    assert first is second
    assert database._pool is first
    assert len(fake_pool) == 1


def test_get_pool_uses_the_configured_bounds(fake_pool):
    pool = database.get_pool()

    assert pool.minconn == database.POOL_MIN
    assert pool.maxconn == database.POOL_MAX
    assert pool.config == database.DB_CONFIG

    # Fewer than anyio's 40 worker threads means a burst of concurrent sync
    # requests gets PoolError rather than waiting for a free connection.
    assert database.POOL_MAX >= 40


def test_close_pool_is_idempotent(fake_pool):
    """Called from lifespan shutdown, which can run more than once per process
    (TestClient, reload, a second lifespan). The second call must be quiet.
    """
    pool = database.get_pool()

    database.close_pool()
    database.close_pool()

    assert pool.closed
    assert database._pool is None


def test_close_pool_needs_no_pool_to_exist():
    """Shutdown after a boot that never touched the database.

    The first call normalises whatever this process inherited; the second is
    the assertion -- closing nothing must not raise.
    """
    database.close_pool()
    database.close_pool()

    assert database._pool is None


def test_close_pool_tolerates_a_pool_someone_else_closed(fake_pool):
    """closeall() raises PoolError when the pool is already closed, so
    close_pool guards on `.closed` instead of calling it blind.
    """
    pool = database.get_pool()
    pool.closeall()

    database.close_pool()

    assert database._pool is None


@pytest.mark.db
def test_get_pool_rebuilds_after_close_pool():
    """Shutdown must not leave the process permanently unable to reach the
    database; close_pool drops the reference rather than parking a closed pool.
    """
    first = database.get_pool()
    database.close_pool()

    second = database.get_pool()

    assert second is not first
    assert not second.closed

    with get_cursor() as cursor:
        cursor.execute("SELECT 1")

        assert cursor.fetchone()[0] == 1


# ============================================================
# THE DELETED API
# ============================================================

def test_get_connection_no_longer_exists():
    """Deleted on purpose, and it must stay deleted.

    `get_connection()` handed out a raw connection and trusted every caller to
    close it on every path, including the error paths. That is the API the leak
    came out of; re-adding it would reintroduce it.
    """
    assert not hasattr(database, "get_connection")


# ============================================================
# _safe_rollback
# ============================================================

def test_safe_rollback_rolls_back():
    connection = _FakeConnection()

    database._safe_rollback(connection)

    assert connection.rollbacks == 1


def test_safe_rollback_tolerates_an_already_closed_connection():
    """When the server has gone away, rollback() raises InterfaceError.

    Letting that out of the except branch would replace the OperationalError
    the caller needs to see with a confusing "connection already closed".
    """
    connection = _FakeConnection(
        psycopg2.InterfaceError("connection already closed")
    )

    database._safe_rollback(connection)

    assert connection.rollbacks == 1


def test_safe_rollback_does_not_hide_non_database_errors():
    """`except psycopg2.Error` is narrow on purpose -- a bare `except
    Exception` here would bury real bugs in the rollback path.
    """
    connection = _FakeConnection(RuntimeError("not a database problem"))

    with pytest.raises(RuntimeError):
        database._safe_rollback(connection)


@pytest.mark.db
def test_safe_rollback_tolerates_a_real_dead_connection():
    """The InterfaceError above is not hypothetical: a real psycopg2
    connection raises it, and this proves the fake is telling the truth.
    """
    connection = psycopg2.connect(**database.DB_CONFIG)
    connection.close()

    with pytest.raises(psycopg2.InterfaceError):
        connection.rollback()

    database._safe_rollback(connection)
