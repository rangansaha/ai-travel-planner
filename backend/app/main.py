from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

import json

from app.trip import TripRequest
from app.services.trip_service import generate_trip_plan
from app.services.weather_service import get_weather
from app.services.ollama_service import ask_ollama
from app.database import create_tables, get_connection


# ============================================================
# APP
# ============================================================

app = FastAPI(
    title="AI Travel Planner API",
    version="0.1.0"
)


# ============================================================
# DATABASE
# ============================================================

create_tables()


# ============================================================
# CORS
# ============================================================

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================
# AI REQUEST
# ============================================================

class AIRequest(BaseModel):
    prompt: str


# ============================================================
# ROOT
# ============================================================

@app.get("/")
def root():
    return {
        "message": "AI Travel Planner API is running!"
    }


# ============================================================
# HEALTH
# ============================================================

@app.get("/health")
def health():
    return {
        "status": "ok"
    }


# ============================================================
# AI TEST
# ============================================================

@app.post("/ai/test")
def test_ai(request: AIRequest):

    answer = ask_ollama(
        request.prompt
    )

    return {
        "answer": answer
    }


# ============================================================
# CREATE TRIP PLAN
# ============================================================

@app.post("/trip/plan")
def create_trip_plan(
    trip: TripRequest
):

    # --------------------------------------------------------
    # Generate AI plan
    # --------------------------------------------------------

    plan = generate_trip_plan(
        trip
    )

    # --------------------------------------------------------
    # If AI failed
    # --------------------------------------------------------

    if "error" in plan:

        return {
            "destination":
                trip.destination,

            "country":
                trip.country,

            "days":
                trip.days,

            "travelers":
                trip.travelers,

            "budget":
                trip.budget,

            "travel_style":
                trip.travel_style,

            "interests":
                trip.interests,

            "plan":
                plan,
        }


    # --------------------------------------------------------
    # Save trip
    # --------------------------------------------------------

    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute(
        """
        INSERT INTO trips
        (
            destination,
            country,
            days,
            travelers,
            budget,
            travel_style,
            interests,
            plan
        )
        VALUES
        (
            %s,
            %s,
            %s,
            %s,
            %s,
            %s,
            %s,
            %s
        )
        RETURNING id
        """,
        (
            trip.destination,
            trip.country,
            trip.days,
            trip.travelers,
            trip.budget,
            trip.travel_style,
            ", ".join(
                trip.interests
            ),
            json.dumps(plan),
        ),
    )

    trip_id = cursor.fetchone()[0]

    connection.commit()

    cursor.close()
    connection.close()


    # --------------------------------------------------------
    # Return trip
    # --------------------------------------------------------

    return {
        "id":
            trip_id,

        "destination":
            trip.destination,

        "country":
            trip.country,

        "days":
            trip.days,

        "travelers":
            trip.travelers,

        "budget":
            trip.budget,

        "travel_style":
            trip.travel_style,

        "interests":
            trip.interests,

        "plan":
            plan,
    }


# ============================================================
# WEATHER
# ============================================================

@app.get("/weather/{destination}")
def weather(
    destination: str,
    country: str = Query(
        default=""
    )
):

    return get_weather(
        destination,
        country
    )


# ============================================================
# SAVED TRIPS
# ============================================================

@app.get("/trips")
def get_trips():

    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute(
        """
        SELECT
            id,
            destination,
            country,
            days,
            travelers,
            budget,
            travel_style,
            interests,
            plan,
            created_at
        FROM trips
        ORDER BY id DESC
        """
    )

    rows = cursor.fetchall()

    cursor.close()
    connection.close()


    trips = []

    for row in rows:

        trips.append(
            {
                "id":
                    row[0],

                "destination":
                    row[1],

                "country":
                    row[2],

                "days":
                    row[3],

                "travelers":
                    row[4],

                "budget":
                    float(row[5]),

                "travel_style":
                    row[6],

                "interests":
                    row[7],

                "plan":
                    row[8],

                "created_at":
                    row[9].isoformat()
                    if row[9]
                    else None,
            }
        )


    return {
        "trips":
            trips
    }

@app.delete("/trips/{trip_id}")
def delete_trip(trip_id: int):

    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute(
        """
        DELETE FROM trips
        WHERE id = %s
        RETURNING id
        """,
        (trip_id,),
    )

    deleted = cursor.fetchone()

    connection.commit()

    cursor.close()
    connection.close()

    if not deleted:
        return {
            "error": "Trip not found"
        }

    return {
        "message": "Trip deleted successfully",
        "id": trip_id,
    }