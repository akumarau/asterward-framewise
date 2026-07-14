"""Open-Meteo geocoding and weather helpers."""
from __future__ import annotations

import os
import threading
import time
from dataclasses import dataclass
from typing import Any

import requests


GEOCODING_URL = os.getenv(
    "FRAMEWISE_GEOCODING_URL",
    "https://nominatim.openstreetmap.org/search",
)
FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
GEOCODING_HEADERS = {
    "User-Agent": os.getenv(
        "FRAMEWISE_GEOCODING_USER_AGENT",
        "FrameWise/0.1 (https://github.com/akumarau/Framewise)",
    ),
    "Referer": "https://github.com/akumarau/Framewise",
}
_GEOCODING_LOCK = threading.Lock()
_LAST_GEOCODING_REQUEST = 0.0


class LocationLookupError(RuntimeError):
    """Raised when a location search cannot be completed."""


class WeatherLookupError(RuntimeError):
    """Raised when weather data cannot be fetched."""


@dataclass
class LocationResult:
    name: str
    country: str
    admin1: str | None
    latitude: float
    longitude: float
    timezone: str | None
    display_name: str | None = None

    @property
    def label(self) -> str:
        if self.display_name:
            return self.display_name
        parts = [self.name, self.admin1, self.country]
        return ", ".join([p for p in parts if p])


def parse_location_results(payload: list[dict[str, Any]]) -> list[LocationResult]:
    """Convert Nominatim search results into FrameWise locations."""
    return [
        LocationResult(
            name=item.get("name") or item.get("display_name", "Unknown").split(",")[0],
            country=item.get("address", {}).get("country", ""),
            admin1=(
                item.get("address", {}).get("state")
                or item.get("address", {}).get("region")
                or item.get("address", {}).get("county")
            ),
            latitude=float(item["lat"]),
            longitude=float(item["lon"]),
            timezone=None,
            display_name=item.get("display_name"),
        )
        for item in payload
        if "lat" in item and "lon" in item
    ]


def geocode_location(query: str, count: int = 10) -> list[LocationResult]:
    """Return explicit landmark/address matches for a text query."""
    global _LAST_GEOCODING_REQUEST

    query = query.strip()
    if not query:
        return []

    params = {
        "q": query,
        "limit": min(max(count, 1), 40),
        "format": "jsonv2",
        "addressdetails": 1,
        "accept-language": "en",
    }

    try:
        with _GEOCODING_LOCK:
            elapsed = time.monotonic() - _LAST_GEOCODING_REQUEST
            if elapsed < 1:
                time.sleep(1 - elapsed)
            response = requests.get(
                GEOCODING_URL,
                params=params,
                headers=GEOCODING_HEADERS,
                timeout=15,
            )
            _LAST_GEOCODING_REQUEST = time.monotonic()
        response.raise_for_status()
        payload = response.json()
    except (requests.RequestException, ValueError) as exc:
        raise LocationLookupError("The location search service is currently unavailable.") from exc

    if not isinstance(payload, list):
        raise LocationLookupError("The location search service returned an unexpected response.")
    try:
        return parse_location_results(payload)
    except (TypeError, ValueError) as exc:
        raise LocationLookupError("The location search service returned invalid coordinates.") from exc


def fetch_weather(latitude: float, longitude: float, forecast_days: int = 3) -> dict[str, Any]:
    """Fetch current and short-range forecast information."""
    params = {
        "latitude": latitude,
        "longitude": longitude,
        "timezone": "auto",
        "forecast_days": forecast_days,
        "current": ",".join([
            "temperature_2m",
            "relative_humidity_2m",
            "precipitation",
            "rain",
            "weather_code",
            "cloud_cover",
            "wind_speed_10m",
        ]),
        "hourly": ",".join([
            "temperature_2m",
            "precipitation_probability",
            "precipitation",
            "cloud_cover",
            "wind_speed_10m",
            "visibility",
        ]),
        "daily": ",".join([
            "sunrise",
            "sunset",
            "precipitation_probability_max",
            "wind_speed_10m_max",
        ]),
    }
    try:
        response = requests.get(FORECAST_URL, params=params, timeout=15)
        response.raise_for_status()
        return response.json()
    except (requests.RequestException, ValueError) as exc:
        raise WeatherLookupError("Weather data is currently unavailable for this location.") from exc


def weather_risk_notes(weather: dict[str, Any] | None) -> list[str]:
    """Generate practical photo risks from a weather payload."""
    if not weather:
        return ["Weather unavailable: check local forecast before leaving."]

    current = weather.get("current", {}) or {}
    notes: list[str] = []
    cloud = current.get("cloud_cover")
    rain = current.get("rain") or current.get("precipitation")
    wind = current.get("wind_speed_10m")
    humidity = current.get("relative_humidity_2m")

    if rain and float(rain) > 0:
        notes.append("Rain is showing now: pack weather protection, lens cloths, and avoid exposed lens changes.")
    if cloud is not None and float(cloud) > 80:
        notes.append("Heavy cloud cover: expect flat light; use colour contrast, reflections, or longer exposures.")
    elif cloud is not None and float(cloud) < 20:
        notes.append("Clear sky: strong midday contrast is likely; prioritise golden hour, shade, or backlight.")
    if wind is not None and float(wind) >= 25:
        notes.append("Wind is elevated: secure tripod, raise shutter speed, and avoid fragile macro setups.")
    if humidity is not None and float(humidity) >= 85:
        notes.append("High humidity: carry cloths and consider dew control for night or long tripod work.")

    return notes or ["No major weather risk flagged from the current forecast."]
