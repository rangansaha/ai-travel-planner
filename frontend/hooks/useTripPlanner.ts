"use client";

import { useEffect, useState } from "react";

import { api } from "@/lib/api";
import type { PartialTripPlan, SavedTrip, TripPlan, WeatherData } from "@/lib/types";

/* =========================================================
   PARTIAL JSON PARSER (FOR SSE STREAMING)
========================================================= */

function tryParsePartialJson<T>(raw: string): T | null {
  const trimmed = raw.trim();
  if (!trimmed.startsWith("{")) return null;

  try {
    return JSON.parse(trimmed) as T;
  } catch {}

  let inString = false;
  let isEscaped = false;
  const stack: string[] = [];

  for (let i = 0; i < trimmed.length; i++) {
    const char = trimmed[i];
    if (isEscaped) {
      isEscaped = false;
      continue;
    }
    if (char === "\\") {
      isEscaped = true;
      continue;
    }
    if (char === '"') {
      inString = !inString;
      continue;
    }
    if (!inString) {
      if (char === "{" || char === "[") {
        stack.push(char);
      } else if (char === "}") {
        if (stack.length && stack[stack.length - 1] === "{") {
          stack.pop();
        }
      } else if (char === "]") {
        if (stack.length && stack[stack.length - 1] === "[") {
          stack.pop();
        }
      }
    }
  }

  let candidate = trimmed;
  if (inString) {
    candidate += '"';
  }

  candidate = candidate.replace(/,\s*$/, "");
  candidate = candidate.replace(/:\s*$/, ': ""');

  let closing = "";
  for (let i = stack.length - 1; i >= 0; i--) {
    if (stack[i] === "{") closing += "}";
    else if (stack[i] === "[") closing += "]";
  }

  try {
    return JSON.parse(candidate + closing) as T;
  } catch {}

  const cleaned = candidate
    .replace(/,\s*"[^"]*"?\s*$/, "")
    .replace(/:\s*"[^"]*"?\s*$/, ': ""');

  try {
    return JSON.parse(cleaned + closing) as T;
  } catch {}

  return null;
}

/* =========================================================
   useTripPlanner — all state + API logic for the home page.
========================================================= */

export function useTripPlanner() {
  /* =======================================================
     FORM STATE
  ======================================================= */

  const [destination, setDestination] = useState("");
  const [country, setCountry] = useState("");
  const [days, setDays] = useState(3);
  const [travelers, setTravelers] = useState(2);
  const [budget, setBudget] = useState(15000);
  const [travelStyle, setTravelStyle] = useState("balanced");
  const [interests, setInterests] = useState("");

  /* =======================================================
     RESULT STATE
  ======================================================= */

  const [plan, setPlan] = useState<TripPlan | PartialTripPlan | null>(null);
  const [weather, setWeather] = useState<WeatherData | null>(null);

  const [loading, setLoading] = useState(false);
  const [isStreaming, setIsStreaming] = useState(false);
  const [streamingPhase, setStreamingPhase] = useState("");
  const [error, setError] = useState("");

  /* =======================================================
     SAVED TRIPS
  ======================================================= */

  const [savedTrips, setSavedTrips] = useState<SavedTrip[]>([]);
  const [savedTripsOpen, setSavedTripsOpen] = useState(false);
  const [loadingSavedTrips, setLoadingSavedTrips] = useState(false);

  /* =========================================================
     READ AN ERROR MESSAGE OUT OF A FAILED RESPONSE
  ========================================================= */

  async function extractErrorMessage(
    response: Response,
    fallback: string
  ): Promise<string> {
    let body: Record<string, unknown> | null = null;

    try {
      body = await response.json();
    } catch {
      return fallback;
    }

    /* FastAPI HTTPException: { detail: "..." } */

    if (typeof body?.detail === "string") {
      return body.detail;
    }

    /* FastAPI 422 validation: { detail: [{ loc, msg, type }] } */

    if (Array.isArray(body?.detail)) {
      const messages = (body.detail as Array<{ msg?: string }>)
        .map(
          (item) =>
            typeof item?.msg === "string"
              ? item.msg
              : null
        )
        .filter(Boolean);

      if (messages.length) {
        return messages.join(", ");
      }
    }

    /* Legacy HTTP-200 error shapes, harmless to keep */

    const planObj = (body as Record<string, Record<string, unknown>>)?.plan;
    if (typeof planObj?.error === "string") {
      return planObj.error;
    }

    if (typeof body?.error === "string") {
      return body.error as string;
    }

    return fallback;
  }

  /* =========================================================
     LOAD SAVED TRIPS
  ========================================================= */

  async function loadSavedTrips() {
    setLoadingSavedTrips(true);

    try {
      const response = await fetch(
        api("/trips")
      );

      if (!response.ok) {
        throw new Error("Failed to load saved trips");
      }

      const data = await response.json();

      setSavedTrips(
        Array.isArray(data.trips)
          ? data.trips
          : []
      );
    } catch (err) {
      console.error(
        "Failed to load saved trips:",
        err
      );
    } finally {
      setLoadingSavedTrips(false);
    }
  }

  /* =========================================================
     LOAD SAVED TRIPS WHEN PAGE OPENS
  ========================================================= */

  useEffect(() => {
    loadSavedTrips();
  }, []);

  /* =========================================================
     DATE FORMAT
  ========================================================= */

  function formatDate(
    dateString: string | null
  ) {
    if (!dateString) {
      return "Unknown date";
    }

    const date = new Date(dateString);

    if (Number.isNaN(date.getTime())) {
      return "Unknown date";
    }

    return date.toLocaleDateString(
      "en-IN",
      {
        day: "numeric",
        month: "short",
        year: "numeric",
      }
    );
  }

  /* =========================================================
     WEATHER
  ========================================================= */

  async function fetchWeather(
    destinationName: string,
    countryName: string
  ) {
    try {
      const params = new URLSearchParams();

      if (countryName.trim()) {
        params.set(
          "country",
          countryName.trim()
        );
      }

      const query = params.toString();

      const url =
        api(`/weather/${encodeURIComponent(
          destinationName.trim()
        )}`) +
        (query ? `?${query}` : "");

      const response = await fetch(url);

      if (!response.ok) {
        return null;
      }

      const data = await response.json();

      if (data.error) {
        return null;
      }

      return (
        data.weather ?? data
      ) as WeatherData;
    } catch (err) {
      console.error(
        "Weather error:",
        err
      );

      return null;
    }
  }

  /* =========================================================
     GENERATE TRIP (STREAMING SSE WITH FALLBACK)
  ========================================================= */

  async function generatePlan() {
    setLoading(true);
    setIsStreaming(true);
    setStreamingPhase("Connecting to AI...");
    setError("");
    setPlan(null);
    setWeather(null);

    // Concurrently fetch weather so it's ready when generation finishes
    fetchWeather(destination, country).then((weatherData) => {
      if (weatherData) {
        setWeather(weatherData);
      }
    });

    try {
      const payload = {
        destination,
        country,
        days,
        travelers,
        budget,
        travel_style: travelStyle,
        interests: interests
          .split(",")
          .map((item) => item.trim())
          .filter(Boolean),
      };

      const response = await fetch(
        api("/trip/plan/stream"),
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify(payload),
        }
      );

      if (!response.ok) {
        throw new Error(
          await extractErrorMessage(
            response,
            "Failed to generate trip plan"
          )
        );
      }

      if (!response.body) {
        throw new Error("Streaming response unavailable.");
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";
      let accumulatedTokens = "";
      let completedPlan: TripPlan | null = null;

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        buffer = lines.pop() ?? "";

        let currentEvent = "message";

        for (const line of lines) {
          const trimmed = line.trim();
          if (!trimmed) continue;

          if (trimmed.startsWith("event:")) {
            currentEvent = trimmed.slice(6).trim();
            continue;
          }

          if (trimmed.startsWith("data:")) {
            const dataStr = trimmed.slice(5).trim();
            try {
              const data = JSON.parse(dataStr);

              if (currentEvent === "token") {
                accumulatedTokens += data.token || "";
                const partial = tryParsePartialJson<PartialTripPlan>(accumulatedTokens);
                if (partial) {
                  if (partial.days && partial.days.length > 0) {
                    setStreamingPhase(`Crafting Day ${partial.days.length} itinerary...`);
                  } else if (partial.estimated_budget) {
                    setStreamingPhase("Structuring budget breakdown...");
                  } else if (partial.summary) {
                    setStreamingPhase("Drafting trip summary...");
                  }
                  setPlan(partial as TripPlan);
                }
              } else if (currentEvent === "done") {
                if (data.plan) {
                  completedPlan = data.plan;
                  setPlan(data.plan);
                  setStreamingPhase("Itinerary complete!");
                }
              } else if (currentEvent === "error") {
                throw new Error(data.detail || "The AI service failed. Please try again.");
              }
            } catch (err) {
              if (currentEvent === "error") throw err;
            }
            currentEvent = "message";
          }
        }
      }

      if (completedPlan) {
        setPlan(completedPlan);
      }

      /* Refresh saved trips */
      await loadSavedTrips();

    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Something went wrong while generating your trip."
      );
    } finally {
      setLoading(false);
      setIsStreaming(false);
      setStreamingPhase("");
    }
  }

  /* =========================================================
     OPEN SAVED TRIP
  ========================================================= */

  async function openSavedTrip(
    trip: SavedTrip
  ) {
    setError("");

    try {
      let savedPlan: TripPlan;

      if (
        typeof trip.plan ===
        "string"
      ) {
        savedPlan =
          JSON.parse(trip.plan);
      } else {
        savedPlan = trip.plan;
      }

      if (
        !savedPlan ||
        !savedPlan.summary
      ) {
        throw new Error(
          "Saved trip data is invalid."
        );
      }

      /* Restore form */

      setDestination(
        trip.destination
      );

      setCountry(
        trip.country ?? ""
      );

      setDays(trip.days);
      setTravelers(trip.travelers);
      setBudget(Number(trip.budget));

      setTravelStyle(
        trip.travel_style
      );

      /* Restore interests */

      if (
        Array.isArray(
          trip.interests
        )
      ) {
        setInterests(
          trip.interests.join(", ")
        );
      } else {
        setInterests(
          trip.interests ?? ""
        );
      }

      /* Restore plan */

      setPlan(savedPlan);

      /* Get weather */

      setWeather(null);

      const weatherData =
        await fetchWeather(
          trip.destination,
          trip.country ?? ""
        );

      setWeather(weatherData);

      /* Close saved trips dropdown */

      setSavedTripsOpen(false);

      /* Scroll to top */

      setTimeout(() => {
        window.scrollTo({
          top: 0,
          behavior: "smooth",
        });
      }, 100);

    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Unable to open saved trip."
      );
    }
  }

  /* =========================================================
     DELETE SAVED TRIP
  ========================================================= */

  async function deleteSavedTrip(
    tripId: number
  ) {
    const confirmed =
      window.confirm(
        "Are you sure you want to delete this saved trip?"
      );

    if (!confirmed) {
      return;
    }

    try {
      const response = await fetch(
        api(`/trips/${tripId}`),
        {
          method: "DELETE",
        }
      );

      if (!response.ok) {
        throw new Error(
          await extractErrorMessage(
            response,
            "Failed to delete trip"
          )
        );
      }

      /* Remove immediately from UI */

      setSavedTrips(
        (previous) =>
          previous.filter(
            (trip) =>
              trip.id !== tripId
          )
      );

    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Unable to delete saved trip."
      );
    }
  }

  /* =========================================================
     TOTAL BUDGET
  ========================================================= */

  const totalBudget = plan
    ? Object.values(
      plan.estimated_budget ?? {}
    ).reduce(
      (
        total,
        value
      ) =>
        total +
        (Number(value) || 0),
      0
    )
    : 0;

  /* =========================================================
     RESET TRIP
  ========================================================= */

  function resetTrip() {
    setPlan(null);
    setWeather(null);
    setError("");

    setDestination("");
    setCountry("");

    window.scrollTo({
      top: 0,
      behavior: "smooth",
    });
  }

  /* =========================================================
     RETURN
  ========================================================= */

  return {
    // Form state
    destination,
    country,
    days,
    travelers,
    budget,
    travelStyle,
    interests,

    setDestination,
    setCountry,
    setDays,
    setTravelers,
    setBudget,
    setTravelStyle,
    setInterests,

    // Results
    plan,
    weather,
    loading,
    isStreaming,
    streamingPhase,
    error,
    totalBudget,

    // Saved trips
    savedTrips,
    savedTripsOpen,
    loadingSavedTrips,
    setSavedTripsOpen,

    // Actions
    generatePlan,
    loadSavedTrips,
    openSavedTrip,
    deleteSavedTrip,
    resetTrip,
    formatDate,
  };
}
