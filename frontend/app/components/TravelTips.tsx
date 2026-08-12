type TravelTipsProps = {
    tips: string[];
};

export default function TravelTips({
    tips,
}: TravelTipsProps) {
    return (
        <section className="mt-6 rounded-2xl border border-slate-800 bg-slate-900 p-6 sm:p-8">
            <h3 className="text-2xl font-bold">
                💡 Travel tips
            </h3>

            <ul className="mt-5 space-y-3">
                {tips.map((tip, index) => (
                    <li
                        key={index}
                        className="rounded-xl bg-slate-950 p-4 text-slate-300"
                    >
                        {tip}
                    </li>
                ))}
            </ul>
        </section>
    );
}