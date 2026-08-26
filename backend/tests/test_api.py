"""HTTP-surface tests for app/main.py.

Both of the app's dependencies are replaced per test -- `generate_trip_plan`
and `get_cursor` -- so nothing in this file needs Postgres or Ollama and
nothing in it is marked `db`.

TestClient is deliberately built WITHOUT `with`. Starlette only runs the
lifespan handler inside the context manager, and this app's lifespan calls
create_tables(); entering it would drag a real database into the very tests
that are meant to prove these routes work without one.
"""

from contextlib import contextmanager
from datetime import datetime
from decimal import Decimal

import psycopg2
import pytest
from fastapi.testclient import TestClient

from app import main
from app.services.ollama_service import (
    OllamaBadOutput,
    OllamaError,
    OllamaTimeout,
    OllamaUnavailable,
)
from app.services.trip_service import InvalidTripPlan


# ============================================================
# CONTRACTS
# ============================================================

# page.tsx reads every one of these off the POST /trip/plan response, and the
# same nine plus created_at off each row of GET /trips. Compared as exact sets
# so a dropped key and a renamed key both fail.

TRIP_KEYS = {
    "id",
    "destination",
    "country",
    "days",
    "travelers",
    "budget",
    "travel_style",
    "interests",
    "plan",
}

SAVED_TRIP_KEYS = TRIP_KEYS | {"created_at"}


# ============================================================
# STAND-INS
# ============================================================

class _StubCursor:
    """The three cursor methods the endpoints use, plus psycopg2's close rule.

    fetchone/fetchall raise InterfaceError once the enclosing `with` block has
    exited, exactly as a real closed psycopg2 cursor does. That is what makes
    the success tests below fail if a fetchone() ever drifts back out of the
    with-block -- the bug the "must stay inside" comment in main.py guards.
    """

    def __init__(self, fetchone=None, fetchall=(), error=None):
        self._fetchone = fetchone
        self._fetchall = list(fetchall)
        self._error = error

        self.closed = False
        self.commit_requested = None
        self.executed = []

    def execute(self, sql, params=None):
        self.executed.append((sql, params))

        if self._error is not None:
            raise self._error

    def fetchone(self):
        self._require_open()

        return self._fetchone

    def fetchall(self):
        self._require_open()

        return self._fetchall

    def _require_open(self):
        if self.closed:
            raise psycopg2.InterfaceError("cursor already closed")


@pytest.fixture
def client():
    # No `with`: see the module docstring.
    return TestClient(main.app)


@pytest.fixture
def stub_db(monkeypatch):
    """Swap app.main.get_cursor for an in-memory stand-in.

    Each test declares only the rows it wants back, or the psycopg2 failure it
    wants raised, and gets the cursor handed back so it can assert on what the
    endpoint actually asked the database to do.
    """
    def install(fetchone=None, fetchall=(), error=None):
        cursor = _StubCursor(fetchone, fetchall, error)

        @contextmanager
        def get_cursor(commit=False):
            cursor.commit_requested = commit

            yield cursor

            cursor.closed = True

        monkeypatch.setattr(main, "get_cursor", get_cursor)

        return cursor

    return install


@pytest.fixture
def forbid_db(monkeypatch):
    """Make any database access from the route under test fail loudly.

    Used by the routes that must work with nothing running, and by the AI
    failure tests -- a plan that could not be generated must never be saved.
    """
    def explode(*args, **kwargs):
        raise AssertionError("this route must not touch the database")

    monkeypatch.setattr(main, "get_cursor", explode)


@pytest.fixture
def stub_ai(monkeypatch):
    """Swap app.main.generate_trip_plan for a fixed result or a failure.

    Returns the call log, so a test can also assert the AI was NOT called.
    """
    def install(plan=None, error=None):
        calls = []

        def generate_trip_plan(trip):
            calls.append(trip)

            if error is not None:
                raise error

            return plan

        monkeypatch.setattr(main, "generate_trip_plan", generate_trip_plan)

        return calls

    return install


# ============================================================
# AI ERROR MAPPING
# ============================================================

# _ai_http_error exists so the UI can say something true about a failure.
# OllamaTimeout, OllamaUnavailable and OllamaBadOutput are all OllamaError
# subclasses, so each of these also pins the isinstance ordering: a broadened
# first branch would swallow the ones below it.

def test_timeout_maps_to_504(client, make_trip, stub_ai, forbid_db):
    stub_ai(error=OllamaTimeout("Ollama did not respond within 300.0s"))

    response = client.post("/trip/plan", json=make_trip().model_dump())

    assert response.status_code == 504
    assert "took too long" in response.json()["detail"]


def test_unavailable_maps_to_503_and_names_ollama(
    client,
    make_trip,
    stub_ai,
    forbid_db,
):
    stub_ai(error=OllamaUnavailable("Could not reach Ollama at http://x:11434"))

    response = client.post("/trip/plan", json=make_trip().model_dump())

    # Naming Ollama is the point: it tells the user what to go and start.
    assert response.status_code == 503
    assert "Ollama" in response.json()["detail"]


def test_invalid_trip_plan_reason_reaches_the_browser_verbatim(
    client,
    make_trip,
    stub_ai,
    forbid_db,
):
    reason = "a budget of 500 INR is too small to plan this trip"
    stub_ai(error=InvalidTripPlan(reason))

    response = client.post("/trip/plan", json=make_trip().model_dump())

    # str(exc) is passed through untouched -- the whole reason InvalidTripPlan
    # carries a written-out message instead of a code.
    assert response.status_code == 502
    assert response.json()["detail"] == reason


def test_bad_output_message_reaches_the_browser_verbatim(
    client,
    make_trip,
    stub_ai,
    forbid_db,
):
    reason = "Ollama returned a malformed trip plan."
    stub_ai(error=OllamaBadOutput(reason))

    response = client.post("/trip/plan", json=make_trip().model_dump())

    assert response.status_code == 502
    assert response.json()["detail"] == reason


def test_unclassified_ollama_error_maps_to_502_not_500(
    client,
    make_trip,
    stub_ai,
    forbid_db,
):
    stub_ai(error=OllamaError('Ollama returned 404: model "nope" not found'))

    response = client.post("/trip/plan", json=make_trip().model_dump())

    # An upstream failure we cannot classify is still upstream's fault, so it
    # must be a 502 with a safe message -- never an unhandled 500.
    assert response.status_code == 502
    assert response.json()["detail"] == "The AI service failed. Please try again."


def test_database_failure_while_saving_maps_to_503(
    client,
    make_trip,
    make_plan,
    stub_ai,
    stub_db,
):
    calls = stub_ai(plan=make_plan().model_dump())

    # Raised from execute(), not from the pool, so the failure happens inside
    # the with-block where the endpoint's except clause still has to catch it.
    stub_db(error=psycopg2.OperationalError("server closed the connection"))

    response = client.post("/trip/plan", json=make_trip().model_dump())

    assert response.status_code == 503
    assert len(calls) == 1  # got past the AI; it was the save that failed


# ============================================================
# CREATE TRIP PLAN
# ============================================================

def test_create_trip_plan_returns_the_nine_contract_keys(
    client,
    make_trip,
    make_plan,
    stub_ai,
    stub_db,
):
    plan = make_plan().model_dump()
    stub_ai(plan=plan)
    cursor = stub_db(fetchone=(7,))

    trip = make_trip()
    response = client.post("/trip/plan", json=trip.model_dump())
    body = response.json()

    assert response.status_code == 200
    assert set(body) == TRIP_KEYS

    assert body["id"] == 7
    assert body["destination"] == trip.destination
    assert body["country"] == trip.country
    assert body["days"] == trip.days
    assert body["travelers"] == trip.travelers
    assert body["budget"] == trip.budget
    assert body["travel_style"] == trip.travel_style
    assert body["interests"] == trip.interests  # a list out, even though the
    assert body["plan"] == plan                 # column stores it joined

    # An INSERT that is never committed is an INSERT that never happened.
    assert cursor.commit_requested is True


def test_a_large_budget_is_accepted(
    client,
    make_trip,
    make_plan,
    stub_ai,
    stub_db,
):
    stub_ai(plan=make_plan().model_dump())
    stub_db(fetchone=(11,))

    response = client.post(
        "/trip/plan",
        json=make_trip(budget=1_000_000).model_dump(),
    )

    # budget has a lower bound only. A real 10-lakh trip must not 422.
    assert response.status_code == 200
    assert response.json()["budget"] == 1_000_000.0


# ============================================================
# SAVED TRIPS
# ============================================================

def _saved_row(plan, created_at=datetime(2026, 8, 27, 9, 30, 15)):
    """One row in the column order GET /trips selects.

    budget is a Decimal because that is what psycopg2 returns for NUMERIC, and
    interests is a joined string because that is what the TEXT column holds.

    The Decimal is deliberately scale-free. FastAPI's encoder turns
    Decimal("200000.00") into 200000.0 by itself, which would hide a missing
    float() -- but it renders Decimal("200000") as the integer 200000, so only
    this value proves the endpoint's own conversion is still there.
    """
    return (
        7,
        "Barcelona",
        "Spain",
        5,
        2,
        Decimal("200000"),
        "balanced",
        "culture, football",
        plan,
        created_at,
    )


def test_get_trips_returns_the_ten_contract_keys(
    client,
    make_plan,
    stub_db,
):
    plan = make_plan().model_dump()
    stub_db(fetchall=[_saved_row(plan)])

    response = client.get("/trips")
    body = response.json()

    assert response.status_code == 200
    assert len(body["trips"]) == 1

    row = body["trips"][0]

    assert set(row) == SAVED_TRIP_KEYS

    assert row["id"] == 7
    assert row["destination"] == "Barcelona"
    assert row["country"] == "Spain"
    assert row["days"] == 5
    assert row["travelers"] == 2
    assert row["travel_style"] == "balanced"
    assert row["interests"] == "culture, football"
    assert row["plan"] == plan
    assert row["created_at"] == "2026-08-27T09:30:15"

    # The frontend does arithmetic on budget, so it must arrive as a number.
    assert isinstance(row["budget"], float)
    assert row["budget"] == 200_000.0


def test_get_trips_tolerates_a_null_created_at(client, make_plan, stub_db):
    stub_db(fetchall=[_saved_row(make_plan().model_dump(), created_at=None)])

    response = client.get("/trips")

    # A row inserted before the column had a default has created_at NULL;
    # calling .isoformat() on it unguarded would 500 the whole list.
    assert response.status_code == 200
    assert response.json()["trips"][0]["created_at"] is None


def test_get_trips_returns_an_empty_list_when_there_are_no_rows(
    client,
    stub_db,
):
    stub_db(fetchall=[])

    response = client.get("/trips")

    # The frontend maps over trips, so "none saved" is 200 + [], not a 404.
    assert response.status_code == 200
    assert response.json() == {"trips": []}


def test_get_trips_maps_a_database_failure_to_503(client, stub_db):
    stub_db(error=psycopg2.OperationalError("could not connect to server"))

    response = client.get("/trips")

    assert response.status_code == 503
    assert "database" in response.json()["detail"].lower()


# ============================================================
# DELETE TRIP
# ============================================================

def test_delete_missing_trip_returns_404(client, stub_db):
    stub_db(fetchone=None)  # RETURNING id gave nothing back

    response = client.delete("/trips/999")

    # It used to return 200 and claim success for a row it never deleted, so
    # the UI removed a card that was still in the database.
    assert response.status_code == 404
    assert response.json()["detail"] == "Trip not found"


def test_delete_existing_trip_returns_the_id(client, stub_db):
    cursor = stub_db(fetchone=(7,))

    response = client.delete("/trips/7")
    body = response.json()

    assert response.status_code == 200
    assert body["id"] == 7
    assert cursor.commit_requested is True


def test_delete_maps_a_database_failure_to_503(client, stub_db):
    stub_db(error=psycopg2.OperationalError("could not connect to server"))

    response = client.delete("/trips/7")

    assert response.status_code == 503


# ============================================================
# VALIDATION
# ============================================================

@pytest.mark.parametrize(
    "overrides, dropped",
    [
        pytest.param({"budget": 0}, (), id="zero-budget"),
        pytest.param({"days": 0}, (), id="zero-days"),
        pytest.param({"travelers": 0}, (), id="zero-travelers"),
        pytest.param({"destination": ""}, (), id="blank-destination"),
        pytest.param({}, ("destination",), id="missing-destination"),
    ],
)
def test_validation_error_puts_detail_in_a_list(
    client,
    make_trip,
    stub_ai,
    forbid_db,
    overrides,
    dropped,
):
    calls = stub_ai(plan={})

    # Built from a valid payload so only the named field is at fault.
    payload = make_trip().model_dump()
    payload.update(overrides)

    for field in dropped:
        payload.pop(field)

    response = client.post("/trip/plan", json=payload)
    detail = response.json()["detail"]

    assert response.status_code == 422

    # extractErrorMessage() in page.tsx branches on detail being a list rather
    # than a string; every other error on this surface returns a string.
    assert isinstance(detail, list)
    assert detail

    # Rejection happens before generation -- a bad field must not cost 80s.
    assert calls == []


# ============================================================
# ROUTES THAT NEED NOTHING RUNNING
# ============================================================

def test_health_needs_no_database(client, forbid_db):
    response = client.get("/health")

    # /health is what tells an operator the app booted while Postgres was
    # down, so it must not itself depend on Postgres.
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_root_needs_no_database(client, forbid_db):
    response = client.get("/")

    assert response.status_code == 200
    assert response.json()["message"]
