import json
import logging
import os
from contextlib import asynccontextmanager

import psycopg2
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.database import close_pool, create_tables, get_cursor
from app.services.ollama_service import (
    OllamaBadOutput,
    OllamaError,
    OllamaTimeout,
    OllamaUnavailable,
    ask_ollama,
    close_client,
)
from app.services.trip_service import (
    InvalidTripPlan,
    generate_trip_plan,
    stream_trip_plan,
)
from app.services.weather_service import get_weather
from app.trip import TripRequest


load_dotenv()

logger = logging.getLogger(__name__)


# ============================================================
# CONFIG
# ============================================================

_cors_raw = os.getenv(
    "CORS_ORIGINS",
    "http://localhost:3000,http://127.0.0.1:3000",
)
CORS_ORIGINS = [origin.strip() for origin in _cors_raw.split(",") if origin.strip()]


# ============================================================
# LIFESPAN
# ============================================================

@asynccontextmanager
async def lifespan(app: FastAPI):

    # Best-effort schema creation. A database that is down must not stop the
    # app from booting -- /health and the AI routes do not need it.
    try:
        create_tables()
    except psycopg2.Error as exc:
        logger.warning(
            "Database unavailable at startup (%s); continuing without it.",
            exc,
        )

    yield

    close_pool()
    close_client()


# ============================================================
# APP
# ============================================================

app = FastAPI(
    title="AI Travel Planner API",
    version="0.1.0",
    lifespan=lifespan
)


# ============================================================
# CORS
# ============================================================

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
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
# ERROR MAPPING
# ============================================================

def _ai_http_error(exc: Exception) -> HTTPException:

    if isinstance(exc, OllamaTimeout):
        return HTTPException(
            504,
            "The AI took too long to respond. Please try again."
        )

    if isinstance(exc, OllamaUnavailable):
        return HTTPException(
            503,
            "The AI service is unavailable. Is Ollama running?"
        )

    if isinstance(exc, (InvalidTripPlan, OllamaBadOutput)):
        return HTTPException(502, str(exc))

    return HTTPException(
        502,
        "The AI service failed. Please try again."
    )


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

    try:
        answer = ask_ollama(
            request.prompt
        )

    except OllamaError as exc:
        raise _ai_http_error(exc) from exc

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

    try:
        plan = generate_trip_plan(
            trip
        )

    except (OllamaError, InvalidTripPlan) as exc:
        raise _ai_http_error(exc) from exc


    # --------------------------------------------------------
    # Save trip
    # --------------------------------------------------------

    try:
        with get_cursor(commit=True) as cursor:

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

            # Must stay inside the with-block: the cursor closes on exit.
            trip_id = cursor.fetchone()[0]

    except psycopg2.Error as exc:
        logger.exception("Failed to save trip")

        raise HTTPException(
            503,
            "Could not save your trip. The database is unavailable."
        ) from exc


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
# STREAM TRIP PLAN (SSE)
# ============================================================

@app.post("/trip/plan/stream")
def stream_create_trip_plan(
    trip: TripRequest
):
    def event_generator():
        try:
            for event_type, payload in stream_trip_plan(trip):
                if event_type == "token":
                    data = json.dumps({"token": payload})
                    yield f"event: token\ndata: {data}\n\n"

                elif event_type == "done":
                    plan = payload
                    trip_id = None

                    try:
                        with get_cursor(commit=True) as cursor:
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
                                    ", ".join(trip.interests),
                                    json.dumps(plan),
                                ),
                            )
                            trip_id = cursor.fetchone()[0]

                    except psycopg2.Error as exc:
                        logger.warning("Failed to save streamed trip to database: %s", exc)

                    response_data = {
                        "id": trip_id,
                        "destination": trip.destination,
                        "country": trip.country,
                        "days": trip.days,
                        "travelers": trip.travelers,
                        "budget": trip.budget,
                        "travel_style": trip.travel_style,
                        "interests": trip.interests,
                        "plan": plan,
                    }
                    yield f"event: done\ndata: {json.dumps(response_data)}\n\n"

        except (OllamaError, InvalidTripPlan) as exc:
            http_err = _ai_http_error(exc)
            err_data = json.dumps({
                "detail": http_err.detail,
                "status_code": http_err.status_code,
            })
            yield f"event: error\ndata: {err_data}\n\n"

        except Exception as exc:
            logger.exception("Unexpected error in trip plan stream")
            err_data = json.dumps({
                "detail": "The AI service failed. Please try again.",
                "status_code": 502,
            })
            yield f"event: error\ndata: {err_data}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


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

    try:
        with get_cursor() as cursor:

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

    except psycopg2.Error as exc:
        logger.exception("Failed to load trips")

        raise HTTPException(
            503,
            "Could not load saved trips. The database is unavailable."
        ) from exc


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


# ============================================================
# DELETE TRIP
# ============================================================

@app.delete("/trips/{trip_id}")
def delete_trip(trip_id: int):

    try:
        with get_cursor(commit=True) as cursor:

            cursor.execute(
                """
                DELETE FROM trips
                WHERE id = %s
                RETURNING id
                """,
                (trip_id,),
            )

            deleted = cursor.fetchone()

    except psycopg2.Error as exc:
        logger.exception("Failed to delete trip")

        raise HTTPException(
            503,
            "Could not delete the trip. The database is unavailable."
        ) from exc

    if not deleted:
        raise HTTPException(404, "Trip not found")

    return {
        "message": "Trip deleted successfully",
        "id": trip_id,
    }
