/* =========================================================
   Shared types for the AI Travel Planner frontend.

   Single source of truth — imported by every component and
   hook that touches the API.  Mirrors the backend's Pydantic
   models (app/services/trip_service.py, app/trip.py).
========================================================= */

// ── Trip plan ───────────────────────────────────────────────

export type Activity = {
  place: string;
  activity: string;
};

export type DayPlan = {
  day: number;
  morning: Activity;
  afternoon: Activity;
  evening: Activity;
};

export type Budget = {
  accommodation: number;
  food: number;
  transport: number;
  activities: number;
  miscellaneous: number;
};

export type TripPlan = {
  summary: string;
  estimated_budget: Budget;
  days: DayPlan[];
  tips: string[];
};

// ── Partial Trip Plan (used during SSE streaming) ───────────

export type PartialActivity = {
  place?: string;
  activity?: string;
};

export type PartialDayPlan = {
  day?: number;
  morning?: PartialActivity;
  afternoon?: PartialActivity;
  evening?: PartialActivity;
};

export type PartialBudget = {
  accommodation?: number;
  food?: number;
  transport?: number;
  activities?: number;
  miscellaneous?: number;
};

export type PartialTripPlan = {
  summary?: string;
  estimated_budget?: PartialBudget;
  days?: PartialDayPlan[];
  tips?: string[];
};

// ── Weather ─────────────────────────────────────────────────

export type WeatherData = {
  location: string;
  country: string;
  country_code?: string;

  current: {
    time: string;
    temperature_2m: number;
    relative_humidity_2m: number;
    apparent_temperature: number;
    precipitation: number;
    weather_code: number;
    wind_speed_10m: number;
  };

  daily: {
    time: string[];
    weather_code: number[];
    temperature_2m_max: number[];
    temperature_2m_min: number[];
    precipitation_probability_max: number[];
  };
};

// ── Saved trip (GET /trips response row) ────────────────────

export type SavedTrip = {
  id: number;
  destination: string;
  country?: string;
  days: number;
  travelers: number;
  budget: number;
  travel_style: string;
  interests: string | string[];
  plan: TripPlan | string;
  created_at: string | null;
};
