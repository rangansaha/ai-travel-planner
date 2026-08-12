"use client";

type TripFormProps = {
    destination: string;
    country: string;
    days: number;
    travelers: number;
    budget: number;
    travelStyle: string;
    interests: string;

    setDestination: (value: string) => void;
    setCountry: (value: string) => void;
    setDays: (value: number) => void;
    setTravelers: (value: number) => void;
    setBudget: (value: number) => void;
    setTravelStyle: (value: string) => void;
    setInterests: (value: string) => void;

    loading: boolean;
    onGenerate: () => void;
};

export default function TripForm({
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

    loading,
    onGenerate,
}: TripFormProps) {
    const budgetPercentage = Math.min(
        100,
        Math.max(0, ((budget - 1000) / (200000 - 1000)) * 100)
    );

    return (
        <section className="mx-auto max-w-5xl overflow-hidden rounded-2xl border border-slate-800 bg-slate-900/80 shadow-2xl shadow-black/20">

            {/* =========================
          HEADER
      ========================== */}
            <div className="border-b border-slate-800 px-8 py-7">
                <div className="flex items-center gap-4">
                    <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-blue-500/10 text-2xl">
                        ✈️
                    </div>

                    <div>
                        <h2 className="text-2xl font-bold text-white">
                            Create your trip
                        </h2>

                        <p className="mt-1 text-sm text-slate-400">
                            Tell us a few details and let AI build your itinerary.
                        </p>
                    </div>
                </div>
            </div>

            {/* =========================
          FORM
      ========================== */}
            <div className="space-y-7 px-8 py-8">

                {/* DESTINATION */}
                <div>
                    <label className="mb-2 block text-sm font-semibold text-slate-200">
                        📍 Where do you want to go?
                    </label>

                    <input
                        type="text"
                        value={destination}
                        onChange={(e) => setDestination(e.target.value)}
                        placeholder="e.g. Goa, Manali, Paris, Tokyo"
                        className="w-full rounded-xl border border-slate-700 bg-slate-950 px-4 py-4 text-white placeholder:text-slate-600 outline-none transition focus:border-blue-500 focus:ring-2 focus:ring-blue-500/20"
                    />

                    <p className="mt-2 text-xs text-slate-500">
                        🌎 National and international destinations are supported.
                    </p>
                </div>

                {/* COUNTRY */}
                <div>
                    <label className="mb-2 block text-sm font-semibold text-slate-200">
                        🌍 Country
                    </label>

                    <input
                        type="text"
                        value={country}
                        onChange={(e) => setCountry(e.target.value)}
                        placeholder="e.g. India, France, Japan, Italy"
                        className="w-full rounded-xl border border-slate-700 bg-slate-950 px-4 py-4 text-white placeholder:text-slate-600 outline-none transition focus:border-blue-500 focus:ring-2 focus:ring-blue-500/20"
                    />

                    <p className="mt-2 text-xs text-slate-500">
                        Enter the country to make the weather location exact.
                    </p>
                </div>

                {/* DAYS + TRAVELERS */}
                <div className="grid grid-cols-1 gap-6 md:grid-cols-2">

                    {/* DAYS */}
                    <div>
                        <label className="mb-2 block text-sm font-semibold text-slate-200">
                            📅 Number of days
                        </label>

                        <div className="relative">
                            <input
                                type="number"
                                min={1}
                                max={30}
                                value={days}
                                onChange={(e) =>
                                    setDays(
                                        Math.min(
                                            30,
                                            Math.max(1, Number(e.target.value) || 1)
                                        )
                                    )
                                }
                                className="w-full rounded-xl border border-slate-700 bg-slate-950 px-4 py-4 pr-20 text-white outline-none transition focus:border-blue-500 focus:ring-2 focus:ring-blue-500/20"
                            />

                            <span className="pointer-events-none absolute right-4 top-1/2 -translate-y-1/2 text-sm text-slate-500">
                                days
                            </span>
                        </div>
                    </div>

                    {/* TRAVELERS */}
                    <div>
                        <label className="mb-2 block text-sm font-semibold text-slate-200">
                            👥 Number of travelers
                        </label>

                        <div className="relative">
                            <input
                                type="number"
                                min={1}
                                max={50}
                                value={travelers}
                                onChange={(e) =>
                                    setTravelers(
                                        Math.min(
                                            50,
                                            Math.max(1, Number(e.target.value) || 1)
                                        )
                                    )
                                }
                                className="w-full rounded-xl border border-slate-700 bg-slate-950 px-4 py-4 pr-24 text-white outline-none transition focus:border-blue-500 focus:ring-2 focus:ring-blue-500/20"
                            />

                            <span className="pointer-events-none absolute right-4 top-1/2 -translate-y-1/2 text-sm text-slate-500">
                                people
                            </span>
                        </div>
                    </div>
                </div>

                {/* =========================
            BUDGET
        ========================== */}
                <div>
                    <div className="mb-3 flex items-center justify-between">
                        <label className="text-sm font-semibold text-slate-200">
                            💰 Total budget
                        </label>

                        <span className="text-lg font-bold text-blue-400">
                            ₹{budget.toLocaleString("en-IN")}
                        </span>
                    </div>

                    <input
                        type="number"
                        min={1000}
                        max={200000}
                        step={500}
                        value={budget}
                        onChange={(e) =>
                            setBudget(
                                Math.min(
                                    200000,
                                    Math.max(1000, Number(e.target.value) || 1000)
                                )
                            )
                        }
                        className="w-full rounded-xl border border-slate-700 bg-slate-950 px-4 py-4 text-white outline-none transition focus:border-blue-500 focus:ring-2 focus:ring-blue-500/20"
                    />

                    {/* BUDGET SLIDER */}
                    <div className="mt-5">
                        <input
                            type="range"
                            min={1000}
                            max={200000}
                            step={500}
                            value={budget}
                            onChange={(e) => setBudget(Number(e.target.value))}
                            className="h-2 w-full cursor-pointer appearance-none rounded-lg bg-slate-700 accent-blue-500"
                        />

                        <div className="mt-2 flex justify-between text-xs text-slate-500">
                            <span>₹1,000</span>
                            <span>₹2,00,000</span>
                        </div>
                    </div>

                    {/* BUDGET INDICATOR */}
                    <div className="mt-4 h-1.5 overflow-hidden rounded-full bg-slate-800">
                        <div
                            className="h-full rounded-full bg-blue-500 transition-all duration-300"
                            style={{
                                width: `${budgetPercentage}%`,
                            }}
                        />
                    </div>
                </div>

                {/* =========================
            TRAVEL STYLE
        ========================== */}
                <div>
                    <label className="mb-3 block text-sm font-semibold text-slate-200">
                        🧳 Travel style
                    </label>

                    <div className="grid grid-cols-1 gap-4 md:grid-cols-3">

                        {/* BUDGET */}
                        <button
                            type="button"
                            onClick={() => setTravelStyle("budget")}
                            className={`rounded-xl border p-5 text-left transition ${travelStyle === "budget"
                                    ? "border-blue-500 bg-blue-500/10 ring-2 ring-blue-500/20"
                                    : "border-slate-700 bg-slate-950 hover:border-slate-600"
                                }`}
                        >
                            <div className="mb-3 text-2xl">🎒</div>

                            <h3 className="font-bold text-white">
                                Budget
                            </h3>

                            <p className="mt-1 text-sm text-slate-500">
                                Save money and explore more.
                            </p>
                        </button>

                        {/* BALANCED */}
                        <button
                            type="button"
                            onClick={() => setTravelStyle("balanced")}
                            className={`rounded-xl border p-5 text-left transition ${travelStyle === "balanced"
                                    ? "border-blue-500 bg-blue-500/10 ring-2 ring-blue-500/20"
                                    : "border-slate-700 bg-slate-950 hover:border-slate-600"
                                }`}
                        >
                            <div className="mb-3 text-2xl">⚖️</div>

                            <h3 className="font-bold text-white">
                                Balanced
                            </h3>

                            <p className="mt-1 text-sm text-slate-500">
                                Comfort without overspending.
                            </p>
                        </button>

                        {/* LUXURY */}
                        <button
                            type="button"
                            onClick={() => setTravelStyle("luxury")}
                            className={`rounded-xl border p-5 text-left transition ${travelStyle === "luxury"
                                    ? "border-blue-500 bg-blue-500/10 ring-2 ring-blue-500/20"
                                    : "border-slate-700 bg-slate-950 hover:border-slate-600"
                                }`}
                        >
                            <div className="mb-3 text-2xl">✨</div>

                            <h3 className="font-bold text-white">
                                Luxury
                            </h3>

                            <p className="mt-1 text-sm text-slate-500">
                                Premium stays and experiences.
                            </p>
                        </button>
                    </div>
                </div>

                {/* =========================
            INTERESTS
        ========================== */}
                <div>
                    <label className="mb-2 block text-sm font-semibold text-slate-200">
                        ❤️ What are you interested in?
                    </label>

                    <input
                        type="text"
                        value={interests}
                        onChange={(e) => setInterests(e.target.value)}
                        placeholder="e.g. beaches, food, photography, nightlife"
                        className="w-full rounded-xl border border-slate-700 bg-slate-950 px-4 py-4 text-white placeholder:text-slate-600 outline-none transition focus:border-blue-500 focus:ring-2 focus:ring-blue-500/20"
                    />

                    <p className="mt-2 text-xs text-slate-500">
                        Separate interests with commas.
                    </p>
                </div>

                {/* =========================
            GENERATE BUTTON
        ========================== */}
                <div className="pt-2">
                    <button
                        type="button"
                        onClick={onGenerate}
                        disabled={
                            loading ||
                            !destination.trim() ||
                            !country?.trim()
                        }
                        className="w-full rounded-xl bg-gradient-to-r from-blue-500 to-indigo-600 px-6 py-4 text-base font-bold text-white shadow-lg shadow-blue-500/20 transition hover:from-blue-400 hover:to-indigo-500 disabled:cursor-not-allowed disabled:opacity-50"
                    >
                        {loading ? (
                            <span className="flex items-center justify-center gap-3">
                                <span className="h-5 w-5 animate-spin rounded-full border-2 border-white/30 border-t-white" />
                                Creating your trip...
                            </span>
                        ) : (
                            "✨ Generate Trip Plan"
                        )}
                    </button>
                </div>

            </div>
        </section>
    );
}