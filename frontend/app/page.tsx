"use client";

import { useTripPlanner } from "@/hooks/useTripPlanner";

import TripForm from "./components/TripForm";
import TripSummary from "./components/TripSummary";
import BudgetBreakdown from "./components/BudgetBreakdown";
import Itinerary from "./components/Itinerary";
import TravelTips from "./components/TravelTips";
import WeatherCard from "./components/WeatherCard";
import SavedTrips from "./components/SavedTrips";

/* =========================================================
   HOME
========================================================= */

export default function Home() {
  const trip = useTripPlanner();

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
          destination={trip.destination}
          country={trip.country}
          days={trip.days}
          travelers={trip.travelers}
          budget={trip.budget}
          travelStyle={trip.travelStyle}
          interests={trip.interests}

          setDestination={
            trip.setDestination
          }

          setCountry={
            trip.setCountry
          }

          setDays={trip.setDays}

          setTravelers={
            trip.setTravelers
          }

          setBudget={trip.setBudget}

          setTravelStyle={
            trip.setTravelStyle
          }

          setInterests={
            trip.setInterests
          }

          loading={trip.loading}

          onGenerate={
            trip.generatePlan
          }
        />

        {/* =================================================
            ERROR
        ================================================= */}

        {trip.error && (
          <div className="mx-auto mt-5 max-w-3xl rounded-xl border border-red-900 bg-red-950/40 p-4 text-sm text-red-300">
            {trip.error}
          </div>
        )}

        {/* =================================================
            STREAMING STATUS BANNER
        ================================================= */}

        {trip.isStreaming && (
          <div className="mx-auto mt-6 flex max-w-3xl items-center justify-center gap-3 rounded-xl border border-blue-800/60 bg-blue-950/40 p-4 text-sm text-blue-300 shadow-lg shadow-blue-500/10">
            <span className="relative flex h-3 w-3">
              <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-blue-400 opacity-75" />
              <span className="relative inline-flex h-3 w-3 rounded-full bg-blue-500" />
            </span>
            <span className="font-medium">
              {trip.streamingPhase || "Generating your travel plan in real time..."}
            </span>
          </div>
        )}

        {/* =================================================
            RESULTS
        ================================================= */}

        {trip.plan && (
          <section className="mt-12">

            {/* Summary */}

            <TripSummary
              destination={
                trip.destination
              }

              summary={
                trip.plan.summary
              }

              totalBudget={
                trip.totalBudget
              }
            />

            {/* Budget */}

            <BudgetBreakdown
              budgetData={
                trip.plan.estimated_budget
              }

              totalBudget={
                trip.budget
              }
            />

            {/* Weather */}

            {trip.weather && (
              <WeatherCard
                weather={
                  trip.weather
                }
              />
            )}

            {/* Itinerary */}

            <Itinerary
              days={trip.plan.days}
            />

            {/* Travel Tips */}

            <TravelTips
              tips={trip.plan.tips}
            />

            {/* Reset */}

            <button
              onClick={
                trip.resetTrip
              }

              className="mt-8 w-full rounded-xl border border-slate-700 px-6 py-3 font-semibold transition hover:bg-slate-900"
            >
              Plan another trip
            </button>

          </section>
        )}

        {/* =================================================
            SAVED TRIPS
        ================================================= */}

        <SavedTrips
          trips={trip.savedTrips}
          isOpen={trip.savedTripsOpen}
          isLoading={trip.loadingSavedTrips}

          onToggle={() =>
            trip.setSavedTripsOpen(
              (previous) =>
                !previous
            )
          }

          onRefresh={
            trip.loadSavedTrips
          }

          onOpen={
            trip.openSavedTrip
          }

          onDelete={
            trip.deleteSavedTrip
          }

          formatDate={
            trip.formatDate
          }
        />

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