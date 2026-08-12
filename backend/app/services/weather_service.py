import requests


# ============================================================
# COUNTRY NORMALIZATION
# ============================================================

COUNTRY_ALIASES = {
    "india": "india",
    "in": "india",

    "usa": "united states",
    "us": "united states",
    "u.s.a": "united states",
    "united states": "united states",
    "united states of america": "united states",

    "uk": "united kingdom",
    "u.k": "united kingdom",
    "united kingdom": "united kingdom",
    "great britain": "united kingdom",
    "england": "united kingdom",

    "uae": "united arab emirates",
    "u.a.e": "united arab emirates",
    "united arab emirates": "united arab emirates",

    "south korea": "south korea",
    "republic of korea": "south korea",

    "north korea": "north korea",
    "dprk": "north korea",

    "russia": "russia",
    "russian federation": "russia",

    "czech republic": "czechia",
    "czechia": "czechia",

    "vietnam": "vietnam",
    "viet nam": "vietnam",

    "myanmar": "myanmar",
    "burma": "myanmar",

    "japan": "japan",
    "china": "china",
    "nepal": "nepal",
    "bhutan": "bhutan",
    "bangladesh": "bangladesh",
    "sri lanka": "sri lanka",
    "thailand": "thailand",
    "singapore": "singapore",
    "malaysia": "malaysia",
    "indonesia": "indonesia",
    "australia": "australia",
    "canada": "canada",
    "france": "france",
    "germany": "germany",
    "italy": "italy",
    "spain": "spain",
    "portugal": "portugal",
    "switzerland": "switzerland",
    "netherlands": "netherlands",
    "belgium": "belgium",
    "austria": "austria",
    "greece": "greece",
    "turkey": "turkey",
    "egypt": "egypt",
    "south africa": "south africa",
    "new zealand": "new zealand",
    "brazil": "brazil",
    "argentina": "argentina",
    "mexico": "mexico",
}


COUNTRY_CODES = {
    "india": "in",
    "united states": "us",
    "united kingdom": "gb",
    "united arab emirates": "ae",
    "south korea": "kr",
    "north korea": "kp",
    "czechia": "cz",
    "vietnam": "vn",
    "russia": "ru",
    "china": "cn",
    "japan": "jp",
    "france": "fr",
    "germany": "de",
    "italy": "it",
    "spain": "es",
    "portugal": "pt",
    "switzerland": "ch",
    "canada": "ca",
    "australia": "au",
    "new zealand": "nz",
    "singapore": "sg",
    "malaysia": "my",
    "indonesia": "id",
    "thailand": "th",
    "nepal": "np",
    "bhutan": "bt",
    "bangladesh": "bd",
    "sri lanka": "lk",
}


def normalize_country(
    country: str
) -> str:

    value = (
        country
        .strip()
        .lower()
    )

    return COUNTRY_ALIASES.get(
        value,
        value
    )


# ============================================================
# WEATHER
# ============================================================

def get_weather(
    destination: str,
    country: str = ""
) -> dict:

    destination = (
        destination.strip()
    )

    country = (
        country.strip()
    )


    if not destination:

        return {
            "error":
                "Destination is required."
        }


    if not country:

        return {
            "error":
                "Country is required for accurate weather information."
        }


    normalized_country = (
        normalize_country(country)
    )


    # --------------------------------------------------------
    # GEOCODING
    # --------------------------------------------------------

    geocoding_url = (
        "https://geocoding-api.open-meteo.com/v1/search"
    )

    geocoding_params = {
        "name":
            destination,

        "count":
            100,

        "language":
            "en",

        "format":
            "json",
    }


    try:

        response = requests.get(
            geocoding_url,
            params=geocoding_params,
            timeout=10,
        )

        response.raise_for_status()

        geocoding_data = (
            response.json()
        )

    except requests.RequestException as error:

        return {
            "error":
                f"Weather location search failed: {error}"
        }


    results = (
        geocoding_data.get(
            "results",
            []
        )
    )


    if not results:

        return {
            "error":
                f"Could not find '{destination}' in '{country}'."
        }


    # --------------------------------------------------------
    # FIND COUNTRY MATCH
    # --------------------------------------------------------

    matching_locations = []


    for result in results:

        result_country = (
            result.get(
                "country",
                ""
            )
            .strip()
            .lower()
        )

        result_country_code = (
            result.get(
                "country_code",
                ""
            )
            .strip()
            .lower()
        )


        # Exact country name
        if (
            result_country ==
            normalized_country
        ):

            matching_locations.append(
                result
            )

            continue


        # Country code
        expected_code = (
            COUNTRY_CODES.get(
                normalized_country
            )
        )


        if (
            expected_code
            and
            result_country_code ==
            expected_code
        ):

            matching_locations.append(
                result
            )


    # --------------------------------------------------------
    # DON'T RETURN WRONG COUNTRY
    # --------------------------------------------------------

    if not matching_locations:

        return {
            "error":
                f"Could not find '{destination}' in {country}. "
                "Please check the destination and country."
        }


    # --------------------------------------------------------
    # BEST MATCH
    # --------------------------------------------------------

    location = (
        matching_locations[0]
    )


    latitude = (
        location["latitude"]
    )

    longitude = (
        location["longitude"]
    )

    location_name = (
        location.get(
            "name",
            destination
        )
    )

    actual_country = (
        location.get(
            "country",
            country
        )
    )

    country_code = (
        location.get(
            "country_code",
            ""
        )
    )


    # --------------------------------------------------------
    # FORECAST
    # --------------------------------------------------------

    weather_url = (
        "https://api.open-meteo.com/v1/forecast"
    )

    weather_params = {

        "latitude":
            latitude,

        "longitude":
            longitude,

        "current": (
            "temperature_2m,"
            "relative_humidity_2m,"
            "apparent_temperature,"
            "precipitation,"
            "weather_code,"
            "wind_speed_10m"
        ),

        "daily": (
            "weather_code,"
            "temperature_2m_max,"
            "temperature_2m_min,"
            "precipitation_probability_max,"
            "sunrise,"
            "sunset"
        ),

        "timezone":
            "auto",

        "forecast_days":
            7,
    }


    try:

        weather_response = requests.get(
            weather_url,
            params=weather_params,
            timeout=10,
        )

        weather_response.raise_for_status()

        weather_data = (
            weather_response.json()
        )

    except requests.RequestException as error:

        return {
            "error":
                f"Weather forecast failed: {error}"
        }


    # --------------------------------------------------------
    # RETURN
    # --------------------------------------------------------

    return {

        "location":
            location_name,

        "country":
            actual_country,

        "country_code":
            country_code,

        "latitude":
            latitude,

        "longitude":
            longitude,

        "current":
            weather_data.get(
                "current",
                {}
            ),

        "daily":
            weather_data.get(
                "daily",
                {}
            ),
    }