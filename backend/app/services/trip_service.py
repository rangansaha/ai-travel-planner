import json

from app.services.ollama_service import ask_ollama
from app.trip import TripRequest


def generate_trip_plan(
    trip: TripRequest
) -> dict:

    interests = ", ".join(
        trip.interests
    )


    prompt = f"""
You are an AI travel planner.

Create a practical travel itinerary using these details:

Destination: {trip.destination}
Country: {trip.country}
Number of days: {trip.days}
Number of travelers: {trip.travelers}
Total budget: ₹{trip.budget}
Travel style: {trip.travel_style}
Interests: {interests}

IMPORTANT:

The destination and country must be treated as one exact location.

Destination:
{trip.destination}

Country:
{trip.country}

Do NOT substitute another place with the same name in another country.

Return ONLY valid JSON.

Use exactly this structure:

{{
    "summary": "short description of the trip",

    "estimated_budget": {{
        "accommodation": 0,
        "food": 0,
        "transport": 0,
        "activities": 0,
        "miscellaneous": 0
    }},

    "days": [
        {{
            "day": 1,

            "morning": {{
                "place": "place name",
                "activity": "what to do"
            }},

            "afternoon": {{
                "place": "place name",
                "activity": "what to do"
            }},

            "evening": {{
                "place": "place name",
                "activity": "what to do"
            }}
        }}
    ],

    "tips": [
        "tip 1",
        "tip 2",
        "tip 3"
    ]
}}

IMPORTANT BUDGET RULES:

- The 0 values above are placeholders only.
- You MUST replace them with realistic estimated amounts.
- Do NOT return 0 unless that category genuinely costs nothing.
- All five budget categories must contain integer amounts.
- The sum of all five categories must be within the total budget of ₹{trip.budget}.
- The estimated budget should be realistic for {trip.travelers} travelers and {trip.days} days.
- Consider the destination, country, travel style, and interests.
- Make the total estimated spending reasonably close to the available budget.
- Never exceed the user's total budget.

IMPORTANT ITINERARY RULES:

- Create exactly {trip.days} day entries.
- Every day MUST contain morning, afternoon, and evening.
- Every morning, afternoon, and evening entry MUST contain a real place.
- Use actual places that exist in {trip.destination}, {trip.country}.
- The "place" field must contain ONLY the place name.
- The "activity" field must describe what the traveler should do there.
- Do NOT invent fictional places.
- Avoid vague locations such as "explore the city".
- Choose places that match the user's interests.
- Keep the itinerary practical and realistic.
- Try to group nearby places together when possible.

IMPORTANT JSON RULES:

- Return ONLY valid JSON.
- Do NOT use markdown.
- Do NOT use code fences.
- Do NOT add explanations before or after the JSON.
- Use double quotes for all JSON keys and string values.
- Do not include trailing commas.

Prices are estimates and may change.
"""


    response = ask_ollama(
        prompt
    )


    try:

        return json.loads(
            response
        )

    except json.JSONDecodeError:

        return {
            "error":
                "The AI returned an invalid JSON response.",

            "raw_response":
                response
        }