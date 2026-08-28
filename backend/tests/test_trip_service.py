"""Regression net for the trip service's schema, prompt and retry loop.

Nothing here reaches a real model: `ask_ollama_json` is replaced by a scripted
stand-in that records how it was called, so every assertion is about what the
service ASKS FOR and what it does with the answer.

The three things being locked in, all of which were bugs once:
  * the day count is pinned in the schema, not merely requested in the prose;
  * the semantic budget rules stay in the prompt, because a schema-only prompt
    yields a schema-valid all-zero budget;
  * retries escalate the temperature, because at temperature 0 llama.cpp
    decodes greedily and a fresh seed alone reproduces the rejected bytes.
"""

from types import SimpleNamespace

import pytest

from app.services.ollama_service import OllamaBadOutput, OllamaUnavailable
from app.services.trip_service import (
    MAX_ATTEMPTS,
    TEMPERATURES,
    InvalidTripPlan,
    TripPlan,
    _build_prompt,
    _build_schema,
    generate_trip_plan,
)


# A budget whose decimal form ("123456.75") contains no '0' digit, so a test
# can look for the literal "0" of the zero-category rule without matching a
# digit of the budget that appears on the very same rules block.
ZEROLESS_BUDGET = 123_456.75

BUDGET_CATEGORIES = {
    "accommodation",
    "food",
    "transport",
    "activities",
    "miscellaneous",
}


# ============================================================
# STAND-IN
# ============================================================

class FakeModel:
    """Scripted `ask_ollama_json`, one outcome per attempt.

    An outcome is either a TripPlan to return or an exception to raise. The
    script is exhausted deliberately rather than looped: a service that makes
    one attempt too many fails the test with the message below instead of
    quietly consuming another canned success.
    """

    def __init__(self, *outcomes):
        self.outcomes = outcomes
        self.calls = []

    def __call__(
        self,
        prompt,
        schema_model,
        *,
        schema=None,
        num_predict=4096,
        seed=42,
        temperature=0.0,
    ):
        self.calls.append(
            SimpleNamespace(
                prompt=prompt,
                schema_model=schema_model,
                schema=schema,
                seed=seed,
                temperature=temperature,
            )
        )

        if len(self.calls) > len(self.outcomes):
            raise AssertionError(
                f"ask_ollama_json called {len(self.calls)} times, but only "
                f"{len(self.outcomes)} attempts were scripted"
            )

        outcome = self.outcomes[len(self.calls) - 1]

        if isinstance(outcome, Exception):
            raise outcome

        return outcome


@pytest.fixture
def scripted(monkeypatch):
    """Install a FakeModel over the service's ask_ollama_json and return it.

    The service imports the name, so the patch has to land on the service
    module rather than on ollama_service.
    """
    from app.services import trip_service

    def install(*outcomes):
        fake = FakeModel(*outcomes)
        monkeypatch.setattr(trip_service, "ask_ollama_json", fake)

        return fake

    return install


# ============================================================
# SCHEMA
# ============================================================

@pytest.mark.parametrize("days", [1, 3, 5, 12])
def test_build_schema_pins_the_day_count(days):
    """Both bounds, not just one.

    Ollama honours minItems/maxItems in grammar-constrained decoding, so
    setting both is what makes the day count structural rather than a request
    the model is free to ignore. minItems alone still lets it pad, maxItems
    alone still lets it stop short.
    """
    schema = _build_schema(days)

    assert schema["properties"]["days"]["minItems"] == days
    assert schema["properties"]["days"]["maxItems"] == days


def test_build_schema_keeps_the_plan_shape():
    """The pinned schema is what constrains the sampler, so it must still
    describe the whole plan -- a hand-rolled dict would drop the $defs the
    nested day/activity objects are expressed through."""
    schema = _build_schema(5)

    assert set(schema["properties"]) == {
        "summary",
        "estimated_budget",
        "days",
        "tips",
    }
    assert "DayPlan" in schema["$defs"]
    assert "Activity" in schema["$defs"]


def test_build_schema_does_not_mutate_the_model_schema():
    """_build_schema edits the dict in place, so it must own that dict.

    If the base schema were ever cached at module scope, one request's day
    count would pin every later request -- and ask_ollama_json falls back to
    TripPlan.model_json_schema() itself when no schema is passed, so the
    damage would not stay inside this module.
    """
    three = _build_schema(3)
    nine = _build_schema(9)

    assert three is not nine
    assert three["properties"]["days"]["minItems"] == 3
    assert three["properties"]["days"]["maxItems"] == 3

    fresh = TripPlan.model_json_schema()["properties"]["days"]

    assert "minItems" not in fresh
    assert "maxItems" not in fresh


def test_build_schema_keeps_the_tips_minimum():
    """TripPlan declares tips with Field(min_length=3), which pydantic emits as
    minItems: 3. That bound has to reach the sampler, or the frontend's tips
    list renders with whatever the model felt like providing."""
    schema = _build_schema(5)

    assert schema["properties"]["tips"]["minItems"] == 3


# ============================================================
# PROMPT
# ============================================================

def test_prompt_states_the_budget_ceiling(make_trip):
    """The schema can type the budget integers but cannot bound their sum, so
    the ceiling has to be stated in prose or nothing enforces it up front."""
    trip = make_trip(budget=ZEROLESS_BUDGET)
    prompt = _build_prompt(trip)
    ceiling = str(trip.budget)

    assert ceiling in prompt

    limits = [
        line for line in prompt.splitlines() if "exceed" in line.lower()
    ]

    assert limits, "the prompt no longer states an upper bound on the budget"
    assert any(ceiling in line for line in limits)


def test_prompt_forbids_a_zero_category(make_trip):
    """With the schema alone the model returns a schema-valid all-zero budget,
    which passes shape validation and then divides by zero in the frontend's
    progress bars. This one sentence is what stops it."""
    trip = make_trip(budget=ZEROLESS_BUDGET)
    prompt = _build_prompt(trip)

    # ZEROLESS_BUDGET has no '0' digit, so a line that talks about the budget
    # categories AND contains a literal '0' can only be the zero rule.
    rules = [
        line
        for line in prompt.splitlines()
        if "0" in line and "categor" in line.lower()
    ]

    assert len(rules) == 1, f"expected exactly one zero rule, found {rules}"
    assert "not" in rules[0].lower(), f"{rules[0]!r} no longer forbids zero"


def test_prompt_names_the_trip_details(make_trip):
    """A prompt that drops any of these plans a different trip than the one
    requested -- and the destination/country pair especially, since half the
    world's city names are reused in another country."""
    trip = make_trip(
        destination="Reykjavik",
        country="Iceland",
        days=4,
        travelers=3,
        interests=["volcanoes", "hot springs"],
    )
    prompt = _build_prompt(trip)

    assert trip.destination in prompt
    assert trip.country in prompt

    for interest in trip.interests:
        assert interest in prompt

    # Checked against the lines that name the quantity, so that a stray digit
    # elsewhere in the prompt cannot satisfy the assertion.
    assert any(
        str(trip.days) in line
        for line in prompt.splitlines()
        if "days" in line.lower()
    )
    assert any(
        str(trip.travelers) in line
        for line in prompt.splitlines()
        if "traveler" in line.lower()
    )


# ============================================================
# GENERATE -- WHAT IS ASKED
# ============================================================

def test_generate_passes_the_pinned_schema_and_prompt(make_trip, make_plan, scripted):
    """The pinning only matters if it actually travels to the model: passing
    TripPlan without the schema override silently unpins the day count."""
    trip = make_trip(days=4)
    fake = scripted(make_plan(days=4))

    generate_trip_plan(trip)

    call = fake.calls[0]

    assert call.schema_model is TripPlan
    assert call.schema == _build_schema(trip.days)
    assert call.prompt == _build_prompt(trip)


def test_retries_escalate_temperature(make_trip, make_plan, scripted):
    """The subtle one, and the reason TEMPERATURES exists at all.

    At temperature 0 llama.cpp decodes greedily and ignores the seed entirely,
    so a retry that varies only the seed re-generates the byte-identical plan
    that was just rejected -- three attempts, one outcome. Attempt 1 stays
    greedy so a good request is reproducible; every later attempt must sample.
    """
    trip = make_trip(days=5)
    fake = scripted(
        OllamaBadOutput("truncated"),
        InvalidTripPlan("rejected"),
        make_plan(days=5),
    )

    generate_trip_plan(trip)

    assert [call.temperature for call in fake.calls] == list(TEMPERATURES)
    assert fake.calls[0].temperature == 0.0
    assert all(call.temperature > 0 for call in fake.calls[1:])

    # The seed varies too, but only as a secondary lever -- it does nothing
    # until the temperature is above zero.
    assert len({call.seed for call in fake.calls}) == MAX_ATTEMPTS

    # The loop indexes TEMPERATURES by attempt number, so a MAX_ATTEMPTS that
    # outgrew the tuple would be an IndexError on the final attempt.
    assert MAX_ATTEMPTS == len(TEMPERATURES)


# ============================================================
# GENERATE -- RETRY POLICY
# ============================================================

@pytest.mark.parametrize(
    "first_attempt",
    [
        # Both InvalidTripPlan paths come from the real _validate rather than a
        # hand-raised exception, so the test also proves they are reachable.
        pytest.param(lambda make_plan: make_plan(days=4), id="wrong-day-count"),
        pytest.param(
            lambda make_plan: make_plan(budget=(0, 0, 0, 0, 0)),
            id="zero-budget",
        ),
        pytest.param(
            lambda make_plan: OllamaBadOutput("Ollama returned a malformed trip plan."),
            id="bad-output",
        ),
    ],
)
def test_a_plan_accepted_later_is_returned(
    first_attempt, make_trip, make_plan, scripted
):
    """One bad generation is not fatal -- the request only fails if every
    attempt fails."""
    trip = make_trip(days=5)
    fake = scripted(first_attempt(make_plan), make_plan(days=5))

    plan = generate_trip_plan(trip)

    assert len(fake.calls) == 2
    assert len(plan["days"]) == 5
    assert sum(plan["estimated_budget"].values()) > 0


def test_gives_up_after_exactly_max_attempts(make_trip, make_plan, scripted):
    """Each attempt is a full generation -- ~80s for a 5-day plan -- so the
    loop is bounded and the bound is the length of TEMPERATURES."""
    trip = make_trip(days=5)
    fake = scripted(
        *[OllamaBadOutput(f"attempt {n} truncated") for n in range(1, MAX_ATTEMPTS + 1)]
    )

    with pytest.raises(InvalidTripPlan):
        generate_trip_plan(trip)

    assert len(fake.calls) == MAX_ATTEMPTS


def test_a_non_retryable_ollama_failure_is_not_retried(make_trip, scripted):
    """Only bad CONTENT earns a retry. A dead server or a blown read timeout
    will still be dead on attempt 2, so widening the except clause would spend
    three generation timeouts to report the same thing."""
    trip = make_trip()
    fake = scripted(OllamaUnavailable("Could not reach Ollama"))

    with pytest.raises(OllamaUnavailable):
        generate_trip_plan(trip)

    assert len(fake.calls) == 1


def test_final_failure_reports_the_last_reason(make_trip, make_plan, scripted):
    """The reason surfaced has to be the last one, not the first.

    The last attempt is the one that ran at the highest temperature, so its
    rejection is the one that describes what the model could not manage; the
    first attempt's failure is often just the greedy sample being truncated.
    """
    trip = make_trip(days=5)
    scripted(
        OllamaBadOutput("first attempt was truncated"),
        OllamaBadOutput("second attempt was malformed"),
        make_plan(budget=(0, 0, 0, 0, 0)),  # _validate: "zero budget"
    )

    with pytest.raises(InvalidTripPlan) as failure:
        generate_trip_plan(trip)

    message = str(failure.value)

    assert "zero budget" in message
    assert "first attempt was truncated" not in message


# ============================================================
# GENERATE -- WHAT COMES BACK
# ============================================================

def test_day_numbering_is_normalised(make_trip, make_plan, scripted):
    """llama3.2 hands back plausible days under implausible numbers (3, 7, 9
    for a 3-day trip). The count is already correct, so renumbering is honest
    and rejecting the plan would waste a good generation."""
    trip = make_trip(days=3)
    plan = make_plan(days=3)

    for day, number in zip(plan.days, (3, 7, 9)):
        day.day = number

    scripted(plan)

    result = generate_trip_plan(trip)

    assert [day["day"] for day in result["days"]] == [1, 2, 3]

    # Renumbered in place: the itinerary keeps the model's ordering.
    assert [day["morning"]["place"] for day in result["days"]] == [
        "Place 1A",
        "Place 2A",
        "Place 3A",
    ]


def test_returns_a_plain_dict_in_the_frontend_shape(make_trip, make_plan, scripted):
    """This dict is both the JSONB stored in trips.plan and the API payload the
    frontend destructures, so its keys are a contract in two directions. A
    TripPlan (or a shallow dict(plan) holding nested models) is not JSON
    serialisable and breaks both.
    """
    trip = make_trip(days=2)
    scripted(make_plan(days=2))

    result = generate_trip_plan(trip)

    assert type(result) is dict
    assert set(result) == {"summary", "estimated_budget", "days", "tips"}

    assert type(result["estimated_budget"]) is dict
    assert set(result["estimated_budget"]) == BUDGET_CATEGORIES

    assert type(result["days"][0]) is dict
    assert set(result["days"][0]) == {"day", "morning", "afternoon", "evening"}
    assert set(result["days"][0]["morning"]) == {"place", "activity"}

    assert isinstance(result["tips"], list)
    assert all(isinstance(tip, str) for tip in result["tips"])
