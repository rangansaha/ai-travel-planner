import logging
from typing import List

from pydantic import BaseModel, Field

from app.services.ollama_service import OllamaBadOutput, ask_ollama_json
from app.trip import TripRequest


logger = logging.getLogger(__name__)

MAX_ATTEMPTS = 2

# The model cannot reliably add five numbers, so it lands near whatever ceiling
# it is given. Asking it to aim under the budget (see the prompt) keeps most
# answers inside it; this tolerance decides what to do with the rest. A small
# overshoot is real information -- the trip costs a bit more than budgeted --
# and the frontend clamps its progress bar at 100%, so rejecting it would turn
# a displayable answer into a total failure. Beyond this, the model has simply
# ignored the constraint.
BUDGET_TOLERANCE = 1.10


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
# VALIDATION
# ============================================================

def _validate(plan: TripPlan, trip: TripRequest) -> None:
    """Checks the schema cannot express.

    format=<schema> guarantees the shape, never the semantics.
    """
    if len(plan.days) != trip.days:
        raise InvalidTripPlan(
            f"asked for {trip.days} days, model returned {len(plan.days)}"
        )

    total = sum(plan.estimated_budget.model_dump().values())

    # An all-zero budget is schema-valid but useless, and it makes the
    # frontend's progress bars compute 0/0 -> NaN%.
    if total <= 0:
        raise InvalidTripPlan("model returned a zero budget")

    if total > trip.budget * BUDGET_TOLERANCE:
        raise InvalidTripPlan(
            f"budget {total} exceeds the limit of {trip.budget}"
        )

    if total > trip.budget:
        logger.info(
            "Plan is %.0f over the %s budget; within tolerance, keeping it.",
            total - trip.budget,
            trip.budget,
        )


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
        try:
            # A fresh seed per attempt: retrying a rejected plan is pointless if
            # the sampler is deterministic, which at temperature 0 it is.
            plan = ask_ollama_json(
                prompt,
                TripPlan,
                schema=schema,
                seed=42 + attempt,
            )
            _validate(plan, trip)

        except (InvalidTripPlan, OllamaBadOutput) as exc:
            last = exc
            logger.warning("Trip plan attempt %d rejected: %s", attempt, exc)
            continue

        # Day numbering is cosmetic -- normalise rather than fail.
        for index, day in enumerate(plan.days, start=1):
            day.day = index

        return plan.model_dump()

    raise InvalidTripPlan(
        f"the AI could not produce a usable trip plan: {last}"
    )
