"""Shared fixtures, plus the two gates that keep the default suite hermetic.

Almost every test here runs with no services at all -- the database and the
model are replaced by stand-ins -- so a bare `pytest` is fast and passes on a
machine with nothing running. The few tests that genuinely need real
infrastructure are marked: `db` is skipped when PostgreSQL is unreachable,
`live` unless --live is passed.
"""

from types import SimpleNamespace

import psycopg2
import pytest

from app.services.trip_service import (
    Activity,
    DayPlan,
    EstimatedBudget,
    TripPlan,
)
from app.trip import TripRequest


# ============================================================
# GATES
# ============================================================

def pytest_addoption(parser):
    parser.addoption(
        "--live",
        action="store_true",
        default=False,
        help="also run the tests that call the real Ollama model (slow).",
    )


def _postgres_reachable() -> bool:
    # Imported here, not at module scope, so collection still works if the
    # database module itself is broken.
    from app.database import DB_CONFIG

    try:
        psycopg2.connect(connect_timeout=3, **DB_CONFIG).close()
    except psycopg2.Error:
        return False

    return True


def pytest_collection_modifyitems(config, items):
    live = config.getoption("--live")

    # None until something actually asks, then remembered: probing once per
    # test would mean one TCP connect per db test just to decide to skip it.
    postgres = None

    for item in items:
        if "live" in item.keywords and not live:
            item.add_marker(
                pytest.mark.skip(reason="needs a live model; pass --live")
            )

        if "db" in item.keywords:
            if postgres is None:
                postgres = _postgres_reachable()

            if not postgres:
                item.add_marker(
                    pytest.mark.skip(reason="no reachable PostgreSQL")
                )


# ============================================================
# ISOLATION
# ============================================================

@pytest.fixture(autouse=True)
def _reset_singletons():
    """Undo module-level caching between tests.

    `database._pool` and `ollama_service._client` are process-wide globals
    built on first use. Without this, whichever test touches one first hands
    it to every test that follows -- which is exactly how a stubbed client
    leaks into a test that meant to reach the real model.
    """
    yield

    from app import database
    from app.services import ollama_service

    # The pool owns real sockets, so close it properly.
    if database._pool is not None:
        database.close_pool()

    # The client may be a stand-in with no close(), and a real one is cheap
    # to rebuild, so close if possible and always drop the reference.
    if ollama_service._client is not None:
        closer = getattr(ollama_service._client, "close", None)

        if callable(closer):
            closer()

        ollama_service._client = None


# ============================================================
# FACTORIES
# ============================================================

@pytest.fixture
def make_trip():
    """Build a TripRequest, overriding only what the test cares about.

    The default is the request that first exposed the budget bug: Barcelona,
    5 days, 2 travellers, 200k INR.
    """
    def build(**overrides):
        fields = {
            "destination": "Barcelona",
            "country": "Spain",
            "days": 5,
            "travelers": 2,
            "budget": 200_000.0,
            "travel_style": "balanced",
            "interests": ["culture", "football"],
        }
        fields.update(overrides)

        return TripRequest(**fields)

    return build


@pytest.fixture
def make_plan():
    """Build a TripPlan with the day count and budget split the test wants."""
    def build(
        days: int = 5,
        budget=(40_000, 60_000, 20_000, 30_000, 30_000),
        tips=None,
    ):
        accommodation, food, transport, activities, miscellaneous = budget

        return TripPlan(
            summary=f"A {days} day trip.",
            estimated_budget=EstimatedBudget(
                accommodation=accommodation,
                food=food,
                transport=transport,
                activities=activities,
                miscellaneous=miscellaneous,
            ),
            days=[
                DayPlan(
                    day=index,
                    morning=Activity(place=f"Place {index}A", activity="Visit"),
                    afternoon=Activity(place=f"Place {index}B", activity="Visit"),
                    evening=Activity(place=f"Place {index}C", activity="Visit"),
                )
                for index in range(1, days + 1)
            ],
            tips=tips if tips is not None else ["Tip one", "Tip two", "Tip three"],
        )

    return build


@pytest.fixture
def make_chat_response():
    """Stand in for ollama's ChatResponse.

    The service only ever reads `.message.content` and `.done_reason`, so
    attribute access is the whole contract.
    """
    def build(content, done_reason="stop"):
        return SimpleNamespace(
            message=SimpleNamespace(content=content),
            done_reason=done_reason,
        )

    return build
