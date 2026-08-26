"""_fit_budget and _validate: the rules the JSON schema cannot express.

llama3.2 allocates a budget in sensible *ratios* but cannot hold a running
total, so whichever category it emits last absorbs the whole arithmetic error.
Five live samples of one 200k trip totalled 150k, 180k, 210k, 230k and 240k.
_fit_budget's job is therefore to keep the model's split and let arithmetic
decide the amounts -- which is why most of the assertions here are about
proportions and exact rupees rather than about "the total looks about right".

Every test builds its own plan and trip, so nothing here depends on order.
"""

import itertools

import pytest

from app.services.trip_service import InvalidTripPlan, _fit_budget, _validate


# The five live samples of the request that exposed the bug (Barcelona, 5 days,
# 2 travellers, 200k INR), keyed by the total the model actually returned. The
# four "real" categories stay plausible across all five while `miscellaneous`
# swings from 10k to 40k absorbing the error -- the totals differ, the trip did
# not.
LIVE_SAMPLES = {
    150_000: (60_000, 45_000, 15_000, 20_000, 10_000),
    180_000: (60_000, 45_000, 15_000, 20_000, 40_000),
    210_000: (60_000, 45_000, 15_000, 20_000, 70_000),
    230_000: (80_000, 60_000, 25_000, 35_000, 30_000),
    240_000: (80_000, 60_000, 25_000, 35_000, 40_000),
}

OVER_BUDGET = (210_000, 230_000, 240_000)

# Breakdowns whose scaled amounts land just short of a whole rupee in several
# categories at once. Rounding to nearest would push the fitted total *above*
# the ceiling; only flooring cannot.
AWKWARD = (
    (3, 3, 3, 3, 13),
    (3, 3, 3, 7, 11),
    (3, 3, 3, 7, 13),
    (11, 13, 7, 3, 3),
    (7, 7, 7, 7, 7),
)

CATEGORIES = (
    "accommodation",
    "food",
    "transport",
    "activities",
    "miscellaneous",
)


def _amounts(plan) -> tuple:
    """The five category amounts, in the frontend's display order."""
    return tuple(getattr(plan.estimated_budget, name) for name in CATEGORIES)


def _shares(amounts) -> tuple:
    """Each category as a fraction of the total -- the part the model owns."""
    total = sum(amounts)

    return tuple(amount / total for amount in amounts)


# ============================================================
# FITTING AN OVER-BUDGET PLAN
# ============================================================

@pytest.mark.parametrize("total", sorted(LIVE_SAMPLES))
def test_no_live_sample_is_ever_left_over_budget(total, make_trip, make_plan):
    """The one invariant every caller downstream leans on, over real data."""
    trip = make_trip(budget=200_000.0)
    plan = make_plan(budget=LIVE_SAMPLES[total])

    _fit_budget(plan, trip)

    assert sum(_amounts(plan)) <= trip.budget


@pytest.mark.parametrize("total", OVER_BUDGET)
def test_an_over_budget_plan_is_scaled_down_rather_than_rejected(
    total, make_trip, make_plan
):
    """Scaled *to* the budget, not merely to something under it.

    Flooring five categories can lose at most one rupee each, so a correctly
    scaled plan lands within five rupees of the ceiling. Anything further below
    it means the plan was shrunk by something other than the budget.
    """
    trip = make_trip(budget=200_000.0)
    plan = make_plan(budget=LIVE_SAMPLES[total])

    _fit_budget(plan, trip)
    fitted = sum(_amounts(plan))

    assert fitted <= trip.budget
    assert trip.budget - fitted < len(CATEGORIES)


def test_the_measured_230k_case_fits_to_199997(make_trip, make_plan):
    """The exact case from the bug report, asserted to the rupee.

    Pinning the amounts rather than a range is what locks int() in: rounding to
    nearest would fit this same plan to exactly 200000, and the frontend's
    progress bar would sit at a suspiciously perfect 100%.
    """
    trip = make_trip(budget=200_000.0)
    plan = make_plan(budget=LIVE_SAMPLES[230_000])

    _fit_budget(plan, trip)

    assert _amounts(plan) == (69_565, 52_173, 21_739, 30_434, 26_086)
    assert sum(_amounts(plan)) == 199_997

    # EstimatedBudget declares five ints and that shape is the stored JSONB.
    # setattr bypasses pydantic validation, so nothing but int() enforces it.
    assert all(isinstance(amount, int) for amount in _amounts(plan))


@pytest.mark.parametrize("breakdown", AWKWARD)
@pytest.mark.parametrize("budget", (7.0, 13.0, 99.0, 1_234.0))
def test_flooring_can_never_push_the_total_over_the_budget(
    budget, breakdown, make_trip, make_plan
):
    """Tiny budgets, where a single rounded-up rupee is a visible overshoot.

    At 200k a rounding rupee hides in the noise; at 7 INR it does not, so these
    are the sizes at which rounding-to-nearest gets caught.
    """
    trip = make_trip(budget=budget)
    plan = make_plan(budget=breakdown)

    _fit_budget(plan, trip)

    assert sum(_amounts(plan)) <= trip.budget


# ============================================================
# PRESERVING THE MODEL'S RATIOS
# ============================================================

def test_the_ratios_between_categories_survive_scaling(make_trip, make_plan):
    """The whole point of scaling instead of rejecting.

    Asserted as pairwise ratios, because a fitted total that threw the model's
    proportions away -- five equal fifths, say -- would satisfy the ceiling
    just as well while describing a completely different trip.
    """
    trip = make_trip(budget=200_000.0)
    original = LIVE_SAMPLES[240_000]
    plan = make_plan(budget=original)

    _fit_budget(plan, trip)
    fitted = _amounts(plan)

    for left, right in itertools.combinations(range(len(CATEGORIES)), 2):
        assert fitted[left] / fitted[right] == pytest.approx(
            original[left] / original[right], rel=1e-3
        )


@pytest.mark.parametrize("total", OVER_BUDGET)
def test_each_category_keeps_its_share_of_the_total(total, make_trip, make_plan):
    """Same guarantee stated per category, which is how the UI reads it."""
    trip = make_trip(budget=200_000.0)
    original = LIVE_SAMPLES[total]
    plan = make_plan(budget=original)

    _fit_budget(plan, trip)

    assert _shares(_amounts(plan)) == pytest.approx(_shares(original), rel=1e-3)


# ============================================================
# PLANS THAT MUST NOT BE TOUCHED
# ============================================================

@pytest.mark.parametrize("total", (150_000, 180_000))
def test_an_under_budget_plan_is_left_exactly_untouched(
    total, make_trip, make_plan
):
    """No silent inflation to fill the budget.

    A 150k plan for a 200k trip is the model saying the trip costs 150k, not an
    invitation to spend the rest: scaling up would invent costs the itinerary
    never justified. Jaipur legitimately sits at 77% of its budget.
    """
    trip = make_trip(budget=200_000.0)
    original = LIVE_SAMPLES[total]
    plan = make_plan(budget=original)

    _fit_budget(plan, trip)

    assert _amounts(plan) == original


def test_a_plan_that_exactly_equals_the_budget_is_untouched(
    make_trip, make_plan
):
    """The <= boundary: equal to the budget is inside it, not over it."""
    trip = make_trip(budget=200_000.0)
    original = (70_000, 55_000, 20_000, 30_000, 25_000)
    plan = make_plan(budget=original)

    assert sum(original) == trip.budget

    _fit_budget(plan, trip)

    assert _amounts(plan) == original


def test_an_all_zero_budget_is_left_for_validate_to_reject(
    make_trip, make_plan
):
    """Zeros must take the early return, not the scaling path.

    A total of 0 is under any budget, so _fit_budget returns before dividing by
    it -- scaling an all-zero breakdown would be a ZeroDivisionError, and a 500
    instead of the retry _validate triggers.
    """
    trip = make_trip(budget=200_000.0)
    plan = make_plan(budget=(0, 0, 0, 0, 0))

    _fit_budget(plan, trip)

    assert _amounts(plan) == (0, 0, 0, 0, 0)

    with pytest.raises(InvalidTripPlan):
        _validate(plan, trip)


# ============================================================
# BUDGETS TOO SMALL TO SPLIT
# ============================================================

def test_a_budget_too_small_to_split_five_ways_is_rejected(
    make_trip, make_plan
):
    """Every category floors to zero, so there is no plan left to return.

    Two rupees is absurd on purpose: the guard is only reachable once the
    largest category itself floors away, which for this split needs a budget
    under three.
    """
    trip = make_trip(budget=2.0)
    plan = make_plan(budget=(40_000, 60_000, 20_000, 30_000, 30_000))

    with pytest.raises(InvalidTripPlan, match=r"2 INR is too small"):
        _fit_budget(plan, trip)


def test_a_single_surviving_rupee_is_not_rejected(make_trip, make_plan):
    """The guard is on the fitted *total*, not on any category hitting zero.

    Categories may legitimately floor to zero -- the prompt allows a genuine 0
    -- so rejecting on "any category is zero" would throw away good plans. One
    rupee left in one category still passes _validate.
    """
    trip = make_trip(budget=3.0)
    plan = make_plan(budget=(40_000, 60_000, 20_000, 30_000, 30_000))

    _fit_budget(plan, trip)

    assert sum(_amounts(plan)) == 1
    assert _validate(plan, trip) is None


# ============================================================
# THE MUTATION CONTRACT
# ============================================================

def test_fit_budget_returns_none_and_mutates_in_place(make_trip, make_plan):
    """Callers re-read plan.estimated_budget; they never rebind a return value.

    generate_trip_plan calls _fit_budget for its side effect and then dumps the
    same plan object, so returning a fitted copy instead of mutating would drop
    the fit silently rather than fail.
    """
    trip = make_trip(budget=200_000.0)
    plan = make_plan(budget=LIVE_SAMPLES[240_000])
    budget_before = plan.estimated_budget

    assert _fit_budget(plan, trip) is None

    assert plan.estimated_budget is budget_before
    assert _amounts(plan) != LIVE_SAMPLES[240_000]


# ============================================================
# VALIDATION
# ============================================================

def test_validate_accepts_a_correct_plan(make_trip, make_plan):
    trip = make_trip(days=5, budget=200_000.0)
    plan = make_plan(days=5, budget=LIVE_SAMPLES[150_000])

    assert _validate(plan, trip) is None


def test_validate_rejects_a_zero_budget(make_trip, make_plan):
    """A real user-facing failure, and schema-valid: five zeros are five ints.

    The frontend divides each category by the total for its progress bars, so
    an all-zero budget renders NaN% rather than looking obviously broken.
    """
    trip = make_trip(budget=200_000.0)
    plan = make_plan(budget=(0, 0, 0, 0, 0))

    with pytest.raises(InvalidTripPlan, match=r"model returned a zero budget"):
        _validate(plan, trip)


@pytest.mark.parametrize("returned", (4, 6))
def test_validate_rejects_a_day_count_mismatch(returned, make_trip, make_plan):
    """Too many days is as wrong as too few, and the message must say both
    numbers -- it is the only record of what the model did, since the rejected
    plan itself is dropped and the retry overwrites the log line."""
    trip = make_trip(days=5)
    plan = make_plan(days=returned)

    with pytest.raises(
        InvalidTripPlan, match=rf"asked for 5 days.*returned {returned}"
    ):
        _validate(plan, trip)
