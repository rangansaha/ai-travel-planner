type Budget = {
    accommodation: number;
    food: number;
    transport: number;
    activities: number;
    miscellaneous: number;
};

type BudgetBreakdownProps = {
    budgetData: Budget;
    totalBudget: number;
};

export default function BudgetBreakdown({
    budgetData,
    totalBudget,
}: BudgetBreakdownProps) {
    const totalEstimated = Object.values(budgetData).reduce(
        (total, value) => total + Number(value),
        0
    );

    const percentage = Math.min(
        (totalEstimated / totalBudget) * 100,
        100
    );

    return (
        <section className="mt-6 rounded-2xl border border-slate-800 bg-slate-900 p-6 sm:p-8">
            <h3 className="text-2xl font-bold">💰 Budget breakdown</h3>

            <div className="mt-6 grid gap-4 sm:grid-cols-2 lg:grid-cols-5">
                {Object.entries(budgetData).map(([category, amount]) => (
                    <div
                        key={category}
                        className="rounded-xl bg-slate-950 p-4"
                    >
                        <p className="text-sm capitalize text-slate-500">
                            {category}
                        </p>

                        <p className="mt-2 text-xl font-bold">
                            ₹{Number(amount).toLocaleString("en-IN")}
                        </p>
                    </div>
                ))}
            </div>

            <div className="mt-5 border-t border-slate-800 pt-5">
                <div className="flex items-center justify-between">
                    <span className="font-medium text-slate-400">
                        Your budget
                    </span>

                    <span className="font-bold">
                        ₹{totalBudget.toLocaleString("en-IN")}
                    </span>
                </div>

                <div className="mt-3 h-3 overflow-hidden rounded-full bg-slate-800">
                    <div
                        className="h-full rounded-full bg-blue-500 transition-all"
                        style={{ width: `${percentage}%` }}
                    />
                </div>

                <p className="mt-2 text-sm text-slate-500">
                    Estimated spending: ₹
                    {totalEstimated.toLocaleString("en-IN")}
                </p>
            </div>
        </section>
    );
}