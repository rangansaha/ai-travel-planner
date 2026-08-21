import logging
from typing import List

from pydantic import BaseModel, Field

from app.services.ollama_service import OllamaBadOutput, ask_ollama_json
from app.trip import TripRequest


logger = logging.getLogger(__name__)

# Temperature per attempt, so len() is also the attempt count. Attempt 1 is
# greedy for reproducibility; later attempts MUST sample, or they just
# reproduce the output that was rejected. Temperature -- not the seed -- is the
# lever: at temperature 0 llama.cpp decodes greedily and the seed does nothing.
# Each attempt is a full generation (~80s for a 5-day plan), so keep this short.
TEMPERATURES = (0.0, 0.4, 0.8)

MAX_ATTEMPTS = len(TEMPERATURES)


# ============================================================
# PLAN SCHEMA
# ============================================================

# These field names and this nesting ARE the frontend contract: page.tsx reads
# plan.summary, plan.estimated_budget (iterated by key), plan.days[].day,
# plan.days[].morning/afternoon/evening.place/.activity and plan.tips[].
# Do not rename or re-nest without changing the frontend.

class Activity(BaseModel):
    place: str
    activity: str


class DayPlan(BaseModel):
    day: int
    morning: Activity
    afternoon: Activity
    evening: Activity


class EstimatedBudget(BaseModel):
    accommodation: int
    food: int
    transport: int
    activities: int
    miscellaneous: int


class TripPlan(BaseModel):
    summary: str
    estimated_budget: EstimatedBudget
    days: List[DayPlan]
    tips: List[str] = Field(min_length=3)  # emits minItems: 3


class InvalidTripPlan(Exception):
    """Schema-valid JSON that violates the trip's own rules."""


def _build_schema(days: int) -> dict:
    """TripPlan's JSON schema with the day count pinned.

    Ollama's grammar-constrained decoding honours minItems/maxItems, so this
    makes the right number of days structural, not merely requested.
    """
    schema = TripPlan.model_json_schema()

    schema["properties"]["days"]["minItems"] = days
    schema["properties"]["days"]["maxItems"] = days

    return schema


# ============================================================
# PROMPT
# ============================================================

def _build_prompt(trip: TripRequest) -> str:
    interests = ", ".join(trip.interests)

    # No JSON-formatting instructions here on purpose -- the schema passed as
    # `format` constrains the shape. What the schema CANNOT express is the
    # semantics, so the budget and itinerary rules below must stay: without
    # them the model happily returns a schema-valid all-zero budget.
    return f"""You are an AI travel planner.

Create a practical travel itinerary using these details:

Destination: {trip.destination}
Country: {trip.country}
Number of days: {trip.days}
Number of travelers: {trip.travelers}
Total budget: {trip.budget} INR
Travel style: {trip.travel_style}
Interests: {interests}

The destination and country must be treated as one exact location.
Do NOT substitute another place with the same name in another country.

BUDGET RULES:
- All five budget categories must contain realistic integer rupee amounts.
- Do NOT return 0 for a category unless it genuinely costs nothing.
- The sum of all five categories must NOT exceed {trip.budget}.
- Aim for a total of roughly 80-95% of {trip.budget}, never above it.
- The budget must be realistic for {trip.travelers} travelers over {trip.days} days.

ITINERARY RULES:
- Create exactly {trip.days} day entries, numbered 1 to {trip.days}.
- Every day must contain morning, afternoon and evening.
- Use real places that actually exist in {trip.destination}, {trip.country}.
- The "place" field must contain ONLY the place name.
- The "activity" field must describe what the traveler should do there.
- Avoid vague locations such as "explore the city".
- Choose places that match the traveler's interests.

Provide at least 3 practical tips."""


# ============================================================
# BUDGET FITTING
# ============================================================

def _fit_budget(plan: TripPlan, trip: TripRequest) -> None:
    """Scale the breakdown down to fit the budget, keeping its proportions.

    Measured on llama3.2: the model allocates *relatively* well -- the ratios
    between accommodation, food, transport and activities are consistently
    plausible -- but it cannot hold a running total, so whichever category it
    emits last absorbs the whole arithmetic error. Five samples of one 200k
    trip totalled 150k, 180k, 210k, 230k and 240k, with `miscellaneous`
    swinging between 10k and 80k to make up the difference.

    Rejecting the overshoots meant failing a request the model had otherwise
    answered well, and no amount of prompting fixes arithmetic a 3B model
    cannot do. So the split is the model's and the total is arithmetic's.
    """
    budget = plan.estimated_budget
    amounts = budget.model_dump()
    total = sum(amounts.values())

    # Already inside the budget (or all zeros, which _validate rejects next).
    if total <= trip.budget:
        return

    scale = trip.budget / total

    # int() floors, so the scaled total can never exceed the budget. The few
    # rupees of rounding shortfall are invisible against a trip budget.
    for field, amount in amounts.items():
        setattr(budget, field, int(amount * scale))

    fitted = sum(budget.model_dump().values())

    # Every category floored to zero, so the budget cannot be split five ways.
    if fitted <= 0:
        raise InvalidTripPlan(
            f"a budget of {trip.budget:.0f} INR is too small to plan this trip"
        )

    logger.info(
        "Scaled estimated budget %d -> %d to fit the %.0f limit.",
        total,
        fitted,
        trip.budget,
    )


# ============================================================
# VALIDATION
# ============================================================

def _validate(plan: TripPlan, trip: TripRequest) -> None:
    """Checks the schema cannot express.

    format=<schema> guarantees the shape, never the semantics. Runs after
    _fit_budget, so the total is already known to fit.
    """
    if len(plan.days) != trip.days:
        raise InvalidTripPlan(
            f"asked for {trip.days} days, model returned {len(plan.days)}"
        )

    # An all-zero budget is schema-valid but useless, and it makes the
    # frontend's progress bars compute 0/0 -> NaN%.
    if sum(plan.estimated_budget.model_dump().values()) <= 0:
        raise InvalidTripPlan("model returned a zero budget")


# ============================================================
# GENERATE
# ============================================================

def generate_trip_plan(trip: TripRequest) -> dict:
    """Return a validated trip plan as a plain dict.

    The dict shape is both the stored JSONB and the frontend payload, so it
    must stay exactly TripPlan's.
    """
    schema = _build_schema(trip.days)
    prompt = _build_prompt(trip)
    last = None

    for attempt in range(1, MAX_ATTEMPTS + 1):
        temperature = TEMPERATURES[attempt - 1]

        try:
            plan = ask_ollama_json(
                prompt,
                TripPlan,
                schema=schema,
                seed=42 + attempt,
                temperature=temperature,
            )
            _fit_budget(plan, trip)
            _validate(plan, trip)

        except (InvalidTripPlan, OllamaBadOutput) as exc:
            last = exc
            logger.warning(
                "Trip plan attempt %d (temp %.1f) rejected: %s",
                attempt,
                temperature,
                exc,
            )
            continue

        # Day numbering is cosmetic -- normalise rather than fail.
        for index, day in enumerate(plan.days, start=1):
            day.day = index

        return plan.model_dump()

    raise InvalidTripPlan(
        f"the AI could not produce a usable trip plan: {last}"
    )
