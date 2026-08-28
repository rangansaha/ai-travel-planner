type TripSummaryProps = {
    destination: string;
    summary?: string;
    totalBudget: number;
};

export default function TripSummary({
    destination,
    summary,
    totalBudget,
}: TripSummaryProps) {
    return (
        <section className="rounded-2xl border border-slate-800 bg-slate-900 p-6 sm:p-8">
            <div className="flex flex-col justify-between gap-4 sm:flex-row">
                <div>
                    <p className="text-sm font-medium text-blue-400">
                        YOUR AI-GENERATED TRIP
                    </p>

                    <h2 className="mt-2 text-3xl font-bold">
                        {destination}
                    </h2>
                </div>

                <div className="rounded-xl bg-slate-950 px-5 py-4">
                    <p className="text-xs text-slate-500">
                        Estimated total
                    </p>

                    <p className="text-2xl font-bold text-green-400">
                        ₹{totalBudget.toLocaleString("en-IN")}
                    </p>
                </div>
            </div>

            <p className="mt-5 leading-7 text-slate-300">
                {summary || "Generating your trip summary..."}
            </p>
        </section>
    );
}