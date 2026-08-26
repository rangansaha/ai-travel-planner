"""End-to-end checks against the real model. Opt in with --live.

Everything else in this suite stubs the model out, which is what keeps it fast
and hermetic -- but a stub cannot tell you that llama3.2 still produces a
usable itinerary. These two cases are the ones that actually broke in a
browser, so they are worth the couple of minutes they cost.

Each test is one full generation (~100s measured for a 5-day plan), and
generate_trip_plan may retry up to MAX_ATTEMPTS times, so budget for several
minutes per test in the worst case.
"""

import pytest

from app.services.trip_service import generate_trip_plan


pytestmark = pytest.mark.live


# The plan is the model's, so exact amounts are never assertable. What IS
# assertable is that the plan spends a serious fraction of the budget: the
# failure mode this guards against is the model anchoring on a "normal" trip
# cost and ignoring the budget it was given. Measured 77.5% at 10 lakh and 77%
# on a 5-day Jaipur trip, so 40% is a floor with real headroom, not a
# rubber-stamp.
MIN_BUDGET_USED = 0.40


def _check(plan: dict, trip) -> int:
    """Assert the invariants that must hold for ANY live plan, return the total."""
    assert len(plan["days"]) == trip.days

    # Day numbers are normalised after generation, so they must be exactly 1..n.
    assert [day["day"] for day in plan["days"]] == list(range(1, trip.days + 1))

    assert len(plan["tips"]) >= 3
    assert plan["summary"].strip()

    total = sum(plan["estimated_budget"].values())

    # The two failures that reached the browser: a zero budget, and a total
    # over the limit the user set.
    assert total > 0, "model returned a zero budget"
    assert total <= trip.budget, f"total {total} exceeds the {trip.budget} limit"

    # Every category should carry a real amount; an all-but-one-zero split is
    # schema-valid but useless to a traveller.
    for category, amount in plan["estimated_budget"].items():
        assert amount > 0, f"{category} came back as zero"

    return total


def test_ten_lakh_budget_is_actually_used(make_trip):
    """A 10 lakh budget must produce a 10 lakh trip, not a 2 lakh one.

    _fit_budget only ever scales DOWN, so nothing in the code corrects a model
    that lowballs. If this fails, the prompt has stopped conveying the budget
    and the UI will report a trip costing a fraction of what the user asked to
    spend.
    """
    trip = make_trip(budget=1_000_000.0)

    plan = generate_trip_plan(trip)
    total = _check(plan, trip)

    assert total >= trip.budget * MIN_BUDGET_USED, (
        f"only {total / trip.budget:.0%} of a {trip.budget:.0f} budget was "
        f"allocated; the model is ignoring the budget"
    )


def test_barcelona_two_lakh_still_fits():
    """The original reported failure: Barcelona/Spain, 5 days, 2 people, 200k.

    Raw samples of this exact request totalled 150k-240k against the 200k
    limit, and the overshoots used to surface as "model returned a zero
    budget". _fit_budget scales them to fit instead.
    """
    from app.trip import TripRequest

    trip = TripRequest(
        destination="Barcelona",
        country="Spain",
        days=5,
        travelers=2,
        budget=200_000.0,
        travel_style="balanced",
        interests=["culture", "football"],
    )

    plan = generate_trip_plan(trip)
    _check(plan, trip)
