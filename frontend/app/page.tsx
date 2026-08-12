"use client";

import { useEffect, useState } from "react";

import TripForm from "./components/TripForm";
import TripSummary from "./components/TripSummary";
import BudgetBreakdown from "./components/BudgetBreakdown";
import Itinerary from "./components/Itinerary";
import TravelTips from "./components/TravelTips";
import WeatherCard from "./components/WeatherCard";

/* =========================================================
   TYPES
========================================================= */

type DayPlan = {
  day: number;
  morning: any;
  afternoon: any;
  evening: any;
};

type Budget = {
  accommodation: number;
  food: number;
  transport: number;
  activities: number;
  miscellaneous: number;
};

type TripPlan = {
  summary: string;
  estimated_budget: Budget;
  days: DayPlan[];
  tips: string[];
};

type WeatherData = {
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

type SavedTrip = {
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

/* =========================================================
   HOME
========================================================= */

export default function Home() {
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

  const [plan, setPlan] = useState<TripPlan | null>(null);
  const [weather, setWeather] = useState<WeatherData | null>(null);

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  /* =======================================================
     SAVED TRIPS
  ======================================================= */

  const [savedTrips, setSavedTrips] = useState<SavedTrip[]>([]);
  const [savedTripsOpen, setSavedTripsOpen] = useState(false);
  const [loadingSavedTrips, setLoadingSavedTrips] = useState(false);

  /* =========================================================
     LOAD SAVED TRIPS
  ========================================================= */

  async function loadSavedTrips() {
    setLoadingSavedTrips(true);

    try {
      const response = await fetch(
        "http://127.0.0.1:8000/trips"
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
        `http://127.0.0.1:8000/weather/${encodeURIComponent(
          destinationName.trim()
        )}` +
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
     GENERATE TRIP
  ========================================================= */

  async function generatePlan() {
    setLoading(true);
    setError("");
    setPlan(null);
    setWeather(null);

    try {
      const response = await fetch(
        "http://127.0.0.1:8000/trip/plan",
        {
          method: "POST",

          headers: {
            "Content-Type":
              "application/json",
          },

          body: JSON.stringify({
            destination,
            country,
            days,
            travelers,
            budget,
            travel_style: travelStyle,

            interests: interests
              .split(",")
              .map(
                (item) => item.trim()
              )
              .filter(Boolean),
          }),
        }
      );

      if (!response.ok) {
        throw new Error(
          "Failed to generate trip plan"
        );
      }

      const data =
        await response.json();

      if (data.plan?.error) {
        throw new Error(
          data.plan.error
        );
      }

      setPlan(data.plan);

      /* Get weather */

      const weatherData =
        await fetchWeather(
          destination,
          country
        );

      setWeather(weatherData);

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
        `http://127.0.0.1:8000/trips/${tripId}`,
        {
          method: "DELETE",
        }
      );

      if (!response.ok) {
        throw new Error(
          "Failed to delete trip"
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
      plan.estimated_budget
    ).reduce(
      (
        total,
        value
      ) =>
        total +
        Number(value),
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
     UI
  ========================================================= */

  return (
    <main className="min-h-screen bg-slate-950 text-white">

      {/* =================================================
          HERO
      ================================================= */}

      <section className="border-b border-slate-800">

        <div className="mx-auto max-w-6xl px-6 py-16 text-center">

          <p className="mb-3 text-sm font-semibold uppercase tracking-[0.25em] text-blue-400">
            AI Travel Planner
          </p>

          <h1 className="text-4xl font-bold tracking-tight sm:text-6xl">
            Plan your perfect trip
          </h1>

          <p className="mx-auto mt-5 max-w-2xl text-lg text-slate-400">
            Tell us where you want to go,
            how much you want to spend,
            and what you love.
          </p>

        </div>

      </section>

      {/* =================================================
          MAIN CONTENT
      ================================================= */}

      <div className="mx-auto max-w-6xl px-6 py-10">

        {/* =================================================
            TRIP FORM
        ================================================= */}

        <TripForm
          destination={destination}
          country={country}
          days={days}
          travelers={travelers}
          budget={budget}
          travelStyle={travelStyle}
          interests={interests}

          setDestination={
            setDestination
          }

          setCountry={
            setCountry
          }

          setDays={setDays}

          setTravelers={
            setTravelers
          }

          setBudget={setBudget}

          setTravelStyle={
            setTravelStyle
          }

          setInterests={
            setInterests
          }

          loading={loading}

          onGenerate={
            generatePlan
          }
        />

        {/* =================================================
            ERROR
        ================================================= */}

        {error && (
          <div className="mx-auto mt-5 max-w-3xl rounded-xl border border-red-900 bg-red-950/40 p-4 text-sm text-red-300">
            {error}
          </div>
        )}

        {/* =================================================
            RESULTS
        ================================================= */}

        {plan && (
          <section className="mt-12">

            {/* Summary */}

            <TripSummary
              destination={
                destination
              }

              summary={
                plan.summary
              }

              totalBudget={
                totalBudget
              }
            />

            {/* Budget */}

            <BudgetBreakdown
              budgetData={
                plan.estimated_budget
              }

              totalBudget={
                budget
              }
            />

            {/* Weather */}

            {weather && (
              <WeatherCard
                weather={
                  weather
                }
              />
            )}

            {/* Itinerary */}

            <Itinerary
              days={plan.days}
            />

            {/* Travel Tips */}

            <TravelTips
              tips={plan.tips}
            />

            {/* Reset */}

            <button
              onClick={
                resetTrip
              }

              className="mt-8 w-full rounded-xl border border-slate-700 px-6 py-3 font-semibold transition hover:bg-slate-900"
            >
              Plan another trip
            </button>

          </section>
        )}

        {/* =================================================
            SAVED TRIPS
            SMALL BOTTOM DROPDOWN
        ================================================= */}

        <section className="mb-6 mt-12">

          {/* Button */}

          <button
            type="button"

            onClick={() =>
              setSavedTripsOpen(
                (previous) =>
                  !previous
              )
            }

            className="mx-auto flex items-center gap-3 rounded-xl border border-slate-800 bg-slate-900/60 px-5 py-3 text-sm font-semibold text-slate-300 transition hover:border-slate-700 hover:bg-slate-900"
          >

            <span>
              🧳
            </span>

            <span>
              Saved Trips
            </span>

            <span className="rounded-full bg-slate-800 px-2 py-0.5 text-xs text-slate-400">
              {
                savedTrips.length
              }
            </span>

            <span
              className={`ml-1 text-xs text-slate-500 transition-transform duration-200 ${savedTripsOpen
                ? "rotate-180"
                : ""
                }`}
            >
              ▼
            </span>

          </button>

          {/* Dropdown */}

          {savedTripsOpen && (
            <div className="mx-auto mt-3 max-w-3xl overflow-hidden rounded-xl border border-slate-800 bg-slate-900/80 shadow-2xl">

              {/* Header */}

              <div className="flex items-center justify-between border-b border-slate-800 px-4 py-3">

                <div>

                  <p className="text-sm font-semibold text-slate-300">
                    Saved Trips
                  </p>

                  <p className="text-xs text-slate-600">
                    Your previous travel plans
                  </p>

                </div>

                <button
                  type="button"

                  onClick={
                    loadSavedTrips
                  }

                  disabled={
                    loadingSavedTrips
                  }

                  className="rounded-lg px-3 py-2 text-xs font-medium text-blue-400 transition hover:bg-slate-800 hover:text-blue-300 disabled:opacity-50"
                >
                  {loadingSavedTrips
                    ? "Refreshing..."
                    : "↻ Refresh"}
                </button>

              </div>

              {/* Loading */}

              {loadingSavedTrips && (
                <div className="px-5 py-8 text-center text-sm text-slate-500">
                  Loading saved trips...
                </div>
              )}

              {/* Empty */}

              {!loadingSavedTrips &&
                savedTrips.length ===
                0 && (

                  <div className="px-5 py-8 text-center">

                    <div className="mb-2 text-2xl">
                      ✈️
                    </div>

                    <p className="text-sm text-slate-400">
                      No saved trips yet.
                    </p>

                    <p className="mt-1 text-xs text-slate-600">
                      Generate a trip and
                      it will appear here.
                    </p>

                  </div>
                )}

              {/* Trip List */}

              {!loadingSavedTrips &&
                savedTrips.length >
                0 && (

                  <div className="divide-y divide-slate-800">

                    {savedTrips.map(
                      (trip) => (

                        <div
                          key={
                            trip.id
                          }

                          className="flex items-center justify-between gap-4 px-4 py-4 transition hover:bg-slate-950/70"
                        >

                          {/* Trip Information */}

                          <div className="min-w-0 flex-1">

                            <div className="flex flex-wrap items-center gap-2">

                              <h3 className="truncate text-sm font-semibold text-white">

                                {
                                  trip.destination
                                }

                                {trip.country && (
                                  <span className="font-normal text-slate-500">
                                    ,{" "}
                                    {
                                      trip.country
                                    }
                                  </span>
                                )}

                              </h3>

                              <span className="rounded-full bg-emerald-950/50 px-2 py-0.5 text-xs font-medium text-emerald-400">
                                ₹
                                {Number(
                                  trip.budget
                                ).toLocaleString(
                                  "en-IN"
                                )}
                              </span>

                            </div>

                            <p className="mt-1 text-xs text-slate-500">

                              {trip.days}{" "}
                              {trip.days ===
                                1
                                ? "day"
                                : "days"}

                              {" • "}

                              {
                                trip.travelers
                              }{" "}
                              {trip.travelers ===
                                1
                                ? "traveler"
                                : "travelers"}

                              {" • "}

                              <span className="capitalize">
                                {
                                  trip.travel_style
                                }
                              </span>

                            </p>

                            <p className="mt-1 text-[11px] text-slate-600">
                              Saved{" "}
                              {
                                formatDate(
                                  trip.created_at
                                )
                              }
                            </p>

                          </div>

                          {/* Actions */}

                          <div className="flex shrink-0 items-center gap-2">

                            {/* View */}

                            <button
                              type="button"

                              onClick={() =>
                                openSavedTrip(
                                  trip
                                )
                              }

                              className="rounded-lg bg-blue-600 px-3 py-2 text-xs font-semibold text-white transition hover:bg-blue-500"
                            >
                              View →
                            </button>

                            {/* Delete */}

                            <button
                              type="button"

                              onClick={() =>
                                deleteSavedTrip(
                                  trip.id
                                )
                              }

                              title="Delete saved trip"

                              className="rounded-lg border border-red-900/60 px-3 py-2 text-sm text-red-400 transition hover:border-red-700 hover:bg-red-950/50 hover:text-red-300"
                            >
                              🗑️
                            </button>

                          </div>

                        </div>

                      )
                    )}

                  </div>
                )}

            </div>
          )}

        </section>

      </div>

      {/* =================================================
          FOOTER
      ================================================= */}

      <footer className="mt-16 border-t border-slate-800">

        <div className="mx-auto max-w-6xl px-6 py-10">

          <div className="flex flex-col items-center justify-between gap-6 sm:flex-row">

            {/* Brand */}

            <div className="text-center sm:text-left">

              <p className="text-lg font-semibold text-white">
                AI Travel Planner
              </p>

              <p className="mt-1 text-sm text-slate-500">
                Created by Rangan Saha
              </p>

            </div>

            {/* Social Links */}

            <div className="flex items-center gap-3">

              {/* LinkedIn */}

              <a
                href="https://www.linkedin.com/in/rangan-saha/"
                target="_blank"
                rel="noopener noreferrer"
                aria-label="LinkedIn"

                className="flex h-10 w-10 items-center justify-center rounded-lg border border-slate-700 bg-slate-900 text-slate-400 transition-all hover:-translate-y-1 hover:border-blue-500 hover:bg-blue-500/10 hover:text-blue-400"
              >

                <svg
                  className="h-5 w-5"
                  viewBox="0 0 24 24"
                  fill="currentColor"
                >

                  <path d="M20.45 20.45h-3.56v-5.57c0-1.33-.03-3.04-1.85-3.04-1.85 0-2.13 1.45-2.13 2.94v5.67H9.35V9h3.41v1.56h.05c.47-.9 1.63-1.85 3.35-1.85 3.59 0 4.25 2.36 4.25 5.44v6.3zM5.34 7.43a2.06 2.06 0 1 1 0-4.12 2.06 2.06 0 0 1 0 4.12zM3.56 9h3.56v11.45H3.56V9z" />

                </svg>

              </a>

              {/* GitHub */}

              <a
                href="https://github.com/rangansaha"
                target="_blank"
                rel="noopener noreferrer"
                aria-label="GitHub"

                className="flex h-10 w-10 items-center justify-center rounded-lg border border-slate-700 bg-slate-900 text-slate-400 transition-all hover:-translate-y-1 hover:border-white hover:bg-white/10 hover:text-white"
              >

                <svg
                  className="h-5 w-5"
                  viewBox="0 0 24 24"
                  fill="currentColor"
                >

                  <path d="M12 .5a12 12 0 0 0-3.79 23.39c.6.11.82-.26.82-.58v-2.03c-3.34.73-4.04-1.61-4.04-1.61-.55-1.39-1.34-1.76-1.34-1.76-1.09-.75.08-.74.08-.74 1.2.08 1.83 1.23 1.83 1.23 1.07 1.83 2.81 1.3 3.5.99.11-.77.42-1.3.76-1.6-2.67-.3-5.47-1.34-5.47-5.93 0-1.31.47-2.38 1.23-3.22-.12-.3-.53-1.52.12-3.18 0 0 1-.32 3.3 1.23a11.4 11.4 0 0 1 6-.01c2.3-1.55 3.3-1.23 3.3-1.23.65 1.66.24 2.88.12 3.18.77.84 1.23 1.91 1.23 3.22 0 4.6-2.8 5.62-5.48 5.92.43.37.81 1.1.81 2.22v3.29c0 .32.22.69.83.57A12 12 0 0 0 12 .5z" />

                </svg>

              </a>

              {/* Instagram */}

              <a
                href="https://www.instagram.com/rangan_saha_?igsh=MXB3amJhcHp5dmt3Zw=="
                target="_blank"
                rel="noopener noreferrer"
                aria-label="Instagram"

                className="flex h-10 w-10 items-center justify-center rounded-lg border border-slate-700 bg-slate-900 text-slate-400 transition-all hover:-translate-y-1 hover:border-pink-500 hover:bg-pink-500/10 hover:text-pink-400"
              >

                <svg
                  className="h-5 w-5"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2"
                >

                  <rect
                    x="3"
                    y="3"
                    width="18"
                    height="18"
                    rx="5"
                  />

                  <circle
                    cx="12"
                    cy="12"
                    r="4"
                  />

                  <circle
                    cx="17.5"
                    cy="6.5"
                    r="1"
                    fill="currentColor"
                    stroke="none"
                  />

                </svg>

              </a>

              {/* Facebook */}

              <a
                href="https://www.facebook.com/rangan.saha.100"
                target="_blank"
                rel="noopener noreferrer"
                aria-label="Facebook"

                className="flex h-10 w-10 items-center justify-center rounded-lg border border-slate-700 bg-slate-900 text-slate-400 transition-all hover:-translate-y-1 hover:border-blue-500 hover:bg-blue-500/10 hover:text-blue-400"
              >

                <svg
                  className="h-5 w-5"
                  viewBox="0 0 24 24"
                  fill="currentColor"
                >

                  <path d="M13.5 21v-8h2.7l.4-3h-3.1V8.08c0-.87.24-1.46 1.5-1.46h1.7V3.94c-.3-.04-1.32-.14-2.5-.14-2.47 0-4.16 1.51-4.16 4.29V10H7.25v3h2.79v8h3.46z" />

                </svg>

              </a>

            </div>

          </div>

          {/* Bottom line */}

          <div className="mt-8 border-t border-slate-800 pt-6 text-center">

            <p className="text-xs text-slate-600">
              © 2026 AI Travel Planner. All rights reserved.
            </p>

          </div>

        </div>

      </footer>

    </main>
  );
}