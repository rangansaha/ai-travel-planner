import type { SavedTrip } from "@/lib/types";

type SavedTripsProps = {
  trips: SavedTrip[];
  isOpen: boolean;
  isLoading: boolean;
  onToggle: () => void;
  onRefresh: () => void;
  onOpen: (trip: SavedTrip) => void;
  onDelete: (tripId: number) => void;
  formatDate: (dateString: string | null) => string;
};

export default function SavedTrips({
  trips,
  isOpen,
  isLoading,
  onToggle,
  onRefresh,
  onOpen,
  onDelete,
  formatDate,
}: SavedTripsProps) {
  return (
    <section className="mb-6 mt-12">

      {/* Button */}

      <button
        type="button"

        onClick={onToggle}

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
            trips.length
          }
        </span>

        <span
          className={`ml-1 text-xs text-slate-500 transition-transform duration-200 ${isOpen
            ? "rotate-180"
            : ""
            }`}
        >
          ▼
        </span>

      </button>

      {/* Dropdown */}

      {isOpen && (
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
                onRefresh
              }

              disabled={
                isLoading
              }

              className="rounded-lg px-3 py-2 text-xs font-medium text-blue-400 transition hover:bg-slate-800 hover:text-blue-300 disabled:opacity-50"
            >
              {isLoading
                ? "Refreshing..."
                : "↻ Refresh"}
            </button>

          </div>

          {/* Loading */}

          {isLoading && (
            <div className="px-5 py-8 text-center text-sm text-slate-500">
              Loading saved trips...
            </div>
          )}

          {/* Empty */}

          {!isLoading &&
            trips.length ===
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

          {!isLoading &&
            trips.length >
            0 && (

              <div className="divide-y divide-slate-800">

                {trips.map(
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
                            onOpen(
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
                            onDelete(
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
  );
}
