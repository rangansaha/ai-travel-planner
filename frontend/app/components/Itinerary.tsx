import type { Activity, DayPlan, PartialActivity, PartialDayPlan } from "@/lib/types";

type ItineraryProps = {
    days?: (DayPlan | PartialDayPlan)[];
};

type ActivityCardProps = {
    activity?: Activity | PartialActivity;
    label: string;
    icon: string;
};

function ActivityCard({
    activity,
    label,
    icon,
}: ActivityCardProps) {
    const place = activity?.place || "Planning place...";
    const description = activity?.activity || "Drafting activity...";

    return (
        <div>
            <p className="mb-3 text-sm font-semibold text-blue-400">
                {icon} {label}
            </p>

            <h5 className="text-xl font-bold text-white">
                📍 {place}
            </h5>

            <p className="mt-2 leading-6 text-slate-300">
                {description}
            </p>

            {activity?.place && (
                <a
                    href={`https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(
                        activity.place
                    )}`}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="mt-4 inline-block rounded-lg border border-slate-700 px-4 py-2 text-sm font-semibold text-blue-400 transition hover:bg-slate-800"
                >
                    🗺️ View on Map
                </a>
            )}
        </div>
    );
}

export default function Itinerary({
    days,
}: ItineraryProps) {
    return (
        <section className="mt-8">

            <h3 className="mb-6 text-3xl font-bold">
                🗓️ Your itinerary
            </h3>

            <div className="space-y-6">
                {(days || []).map((day, idx) => (
                    <article
                        key={day.day || idx + 1}
                        className="overflow-hidden rounded-2xl border border-slate-800 bg-slate-900"
                    >

                        {/* Day Header */}
                        <div className="border-b border-slate-800 bg-slate-950 px-6 py-6">
                            <h4 className="text-2xl font-bold">
                                Day {day.day || idx + 1}
                            </h4>
                        </div>

                        {/* Activities */}
                        <div className="grid gap-8 p-6 md:grid-cols-3">

                            <ActivityCard
                                activity={day.morning}
                                label="MORNING"
                                icon="🌅"
                            />

                            <ActivityCard
                                activity={day.afternoon}
                                label="AFTERNOON"
                                icon="☀️"
                            />

                            <ActivityCard
                                activity={day.evening}
                                label="EVENING"
                                icon="🌆"
                            />

                        </div>
                    </article>
                ))}

            </div>
        </section>
    );
}