"""Open-Meteo weather (external API #1, no key).

Geocodes a location, fetches current temperature + condition, and derives
the `temp_band` + `season` the L4 filter uses. Degrades gracefully: if the
network is unavailable, callers can pass `temp_c` directly and we still
band it.
"""

from __future__ import annotations

from datetime import UTC, datetime

import requests
from langsmith import traceable

from ..schema import Season, TempBand

GEOCODE_URL = "https://geocoding-api.open-meteo.com/v1/search"
FORECAST_URL = "https://api.open-meteo.com/v1/forecast"

# WMO weather codes -> coarse condition label
_WMO = {
    0: "clear",
    1: "mostly clear",
    2: "partly cloudy",
    3: "overcast",
    45: "fog",
    48: "fog",
    51: "drizzle",
    53: "drizzle",
    55: "drizzle",
    61: "rain",
    63: "rain",
    65: "heavy rain",
    71: "snow",
    73: "snow",
    75: "heavy snow",
    80: "showers",
    81: "showers",
    82: "heavy showers",
    95: "thunderstorm",
    96: "thunderstorm",
    99: "thunderstorm",
}


def temp_to_band(temp_c: float) -> TempBand:
    if temp_c < 0:
        return "freezing"
    if temp_c < 10:
        return "cold"
    if temp_c < 16:
        return "cool"
    if temp_c < 22:
        return "mild"
    if temp_c < 28:
        return "warm"
    return "hot"


def month_to_season(month: int, southern: bool = False) -> Season:
    north = {
        12: "winter",
        1: "winter",
        2: "winter",
        3: "spring",
        4: "spring",
        5: "spring",
        6: "summer",
        7: "summer",
        8: "summer",
        9: "autumn",
        10: "autumn",
        11: "autumn",
    }
    s = north[month]
    if southern:
        flip = {"winter": "summer", "summer": "winter", "spring": "autumn", "autumn": "spring"}
        s = flip[s]
    return s  # type: ignore[return-value]


@traceable(name="external.open_meteo", run_type="tool")
def get_weather(location: str, timeout: float = 10.0) -> dict:
    """Return {temp_c, condition, temp_band, season} for a location name.

    Raises on network failure — callers that want a fallback should catch
    and supply temp_c manually (see context_assembler)."""
    geo = requests.get(GEOCODE_URL, params={"name": location, "count": "1"}, timeout=timeout).json()
    results = geo.get("results")
    if not results:
        raise ValueError(f"could not geocode location: {location!r}")
    lat, lon = results[0]["latitude"], results[0]["longitude"]

    fc = requests.get(
        FORECAST_URL,
        params={"latitude": lat, "longitude": lon, "current": "temperature_2m,weather_code"},
        timeout=timeout,
    ).json()
    current = fc["current"]
    temp_c = float(current["temperature_2m"])
    condition = _WMO.get(int(current["weather_code"]), "unknown")
    return {
        "temp_c": temp_c,
        "condition": condition,
        "temp_band": temp_to_band(temp_c),
        "season": month_to_season(datetime.now(UTC).month, southern=lat < 0),
    }
