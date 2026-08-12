"use client";

type WeatherData = {
    location: string;
    country: string;

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

type WeatherCardProps = {
    weather: WeatherData | { weather: WeatherData };
};

function getWeatherDescription(code: number) {
    if (code === 0) return "Clear sky";
    if (code === 1) return "Mainly clear";
    if (code === 2) return "Partly cloudy";
    if (code === 3) return "Overcast";

    if ([45, 48].includes(code)) return "Foggy";
    if ([51, 53, 55].includes(code)) return "Drizzle";
    if ([61, 63, 65].includes(code)) return "Rain";
    if ([71, 73, 75].includes(code)) return "Snow";
    if ([80, 81, 82].includes(code)) return "Rain showers";
    if ([95, 96, 99].includes(code)) return "Thunderstorm";

    return "Mixed weather";
}

function getWeatherIcon(code: number) {
    if (code === 0) return "☀️";
    if ([1, 2].includes(code)) return "🌤️";
    if (code === 3) return "☁️";
    if ([45, 48].includes(code)) return "🌫️";
    if ([51, 53, 55].includes(code)) return "🌦️";
    if ([61, 63, 65, 80, 81, 82].includes(code)) return "🌧️";
    if ([71, 73, 75].includes(code)) return "❄️";
    if ([95, 96, 99].includes(code)) return "⛈️";

    return "🌤️";
}

export default function WeatherCard({ weather }: WeatherCardProps) {
    // Handles both:
    // { location, current, daily }
    // and:
    // { weather: { location, current, daily } }

    const data =
        "weather" in weather
            ? weather.weather
            : weather;

    const current = data.current;
    const daily = data.daily;

    if (!current || !daily) {
        return (
            <section className="mt-6 rounded-2xl border border-red-900 bg-red-950/40 p-6">
                <h3 className="text-xl font-bold text-red-400">
                    Weather data unavailable
                </h3>

                <p className="mt-2 text-slate-300">
                    The weather service returned an unexpected response format.
                </p>
            </section>
        );
    }

    return (
        <section className="mt-6 rounded-2xl border border-slate-800 bg-slate-900 p-6">

            {/* Header */}
            <div className="mb-6">
                <p className="text-sm font-semibold uppercase tracking-wider text-blue-400">
                    Weather
                </p>

                <h3 className="mt-1 text-3xl font-bold">
                    {getWeatherIcon(current.weather_code)} {data.location}
                </h3>

                <p className="mt-1 text-slate-400">
                    {data.country}
                </p>
            </div>

            {/* Current Weather */}
            <div className="grid gap-4 md:grid-cols-4">

                <div className="rounded-xl bg-slate-950 p-4">
                    <p className="text-sm text-slate-400">
                        Current
                    </p>

                    <p className="mt-2 text-3xl font-bold">
                        {current.temperature_2m}°C
                    </p>

                    <p className="mt-1 text-slate-300">
                        {getWeatherIcon(current.weather_code)}{" "}
                        {getWeatherDescription(current.weather_code)}
                    </p>
                </div>

                <div className="rounded-xl bg-slate-950 p-4">
                    <p className="text-sm text-slate-400">
                        Feels like
                    </p>

                    <p className="mt-2 text-2xl font-bold">
                        {current.apparent_temperature}°C
                    </p>
                </div>

                <div className="rounded-xl bg-slate-950 p-4">
                    <p className="text-sm text-slate-400">
                        Humidity
                    </p>

                    <p className="mt-2 text-2xl font-bold">
                        {current.relative_humidity_2m}%
                    </p>
                </div>

                <div className="rounded-xl bg-slate-950 p-4">
                    <p className="text-sm text-slate-400">
                        Rain chance
                    </p>

                    <p className="mt-2 text-2xl font-bold">
                        {daily.precipitation_probability_max[0]}%
                    </p>
                </div>

            </div>

            {/* Extra Current Details */}
            <div className="mt-4 grid gap-4 md:grid-cols-2">

                <div className="rounded-xl bg-slate-950 p-4">
                    <p className="text-sm text-slate-400">
                        Wind speed
                    </p>

                    <p className="mt-2 text-2xl font-bold">
                        {current.wind_speed_10m} km/h
                    </p>
                </div>

                <div className="rounded-xl bg-slate-950 p-4">
                    <p className="text-sm text-slate-400">
                        Precipitation
                    </p>

                    <p className="mt-2 text-2xl font-bold">
                        {current.precipitation} mm
                    </p>
                </div>

            </div>

            {/* 7-Day Forecast */}
            <div className="mt-6">

                <h4 className="mb-4 text-xl font-bold">
                    7-day forecast
                </h4>

                <div className="grid gap-3 sm:grid-cols-2 md:grid-cols-4 lg:grid-cols-7">

                    {daily.time.map((date, index) => (

                        <div
                            key={date}
                            className="rounded-xl bg-slate-950 p-4 text-center"
                        >

                            <p className="text-sm text-slate-400">
                                {new Date(date).toLocaleDateString(
                                    "en-IN",
                                    {
                                        weekday: "short",
                                        day: "numeric",
                                        month: "short",
                                    }
                                )}
                            </p>

                            <p className="my-3 text-3xl">
                                {getWeatherIcon(
                                    daily.weather_code[index]
                                )}
                            </p>

                            <p className="text-sm text-slate-300">
                                {getWeatherDescription(
                                    daily.weather_code[index]
                                )}
                            </p>

                            <p className="mt-3 font-semibold">
                                {Math.round(
                                    daily.temperature_2m_max[index]
                                )}
                                ° /{" "}
                                {Math.round(
                                    daily.temperature_2m_min[index]
                                )}
                                °C
                            </p>

                            <p className="mt-1 text-xs text-blue-400">
                                🌧️{" "}
                                {
                                    daily
                                        .precipitation_probability_max[
                                    index
                                    ]
                                }
                                %
                            </p>

                        </div>

                    ))}

                </div>

            </div>

        </section>
    );
}