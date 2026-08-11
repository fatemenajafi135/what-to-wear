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


def _geocode_once(name: str, timeout: float) -> tuple[float, float] | None:
    geo = requests.get(GEOCODE_URL, params={"name": name, "count": "1"}, timeout=timeout).json()
    results = geo.get("results")
    if not results:
        return None
    return results[0]["latitude"], results[0]["longitude"]


def _geocode(location: str, timeout: float) -> tuple[float, float]:
    """Geocodes `location` as given first, then — on a miss — retries against progressively
    coarser comma-separated segments, dropping the left-most (most specific) one each time.

    issue #68: `location` isn't always a bare city. A picked calendar event's location is
    Google's own raw free text (`adapters/google_calendar.py`), and a conversational mention can
    carry a venue name along with the city even after the extraction prompt is told to prefer
    the city (prompts/conversational_turn_system.md) — e.g. "Wedding hall, MQVP+X67, Tbilisi,
    Georgia" fails whole, but "Tbilisi, Georgia" (dropping the venue name and the plus code)
    succeeds. Dropping from the left rather than guessing which single segment is "the city"
    means this needs no knowledge of what a segment contains.

    A location with no commas (already just a city) makes exactly one request, same as before
    this fallback existed."""
    segments = [s.strip() for s in location.split(",") if s.strip()]
    candidates = [", ".join(segments[i:]) for i in range(len(segments))] if segments else [location]
    for candidate in candidates:
        coords = _geocode_once(candidate, timeout)
        if coords is not None:
            return coords
    raise ValueError(f"could not geocode location: {location!r}")


@traceable(name="external.open_meteo", run_type="tool")
def get_weather(location: str, timeout: float = 10.0) -> dict:
    """Return {temp_c, condition, temp_band, season} for a location name.

    Raises on network failure — callers that want a fallback should catch
    and supply temp_c manually (see context_assembler)."""
    lat, lon = _geocode(location, timeout)

    forecast_params: dict[str, str | float] = {
        "latitude": lat,
        "longitude": lon,
        "current": "temperature_2m,weather_code",
    }
    fc = requests.get(FORECAST_URL, params=forecast_params, timeout=timeout).json()
    current = fc["current"]
    temp_c = float(current["temperature_2m"])
    condition = _WMO.get(int(current["weather_code"]), "unknown")
    return {
        "temp_c": temp_c,
        "condition": condition,
        "temp_band": temp_to_band(temp_c),
        "season": month_to_season(datetime.now(UTC).month, southern=lat < 0),
    }
