"""Open-Meteo geocoding and weather helpers."""
from __future__ import annotations

import json
import requests
from dataclasses import dataclass
from pathlib import Path
from typing import Any


GEOCODING_URL = "https://geocoding-api.open-meteo.com/v1/search"
FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
KNOWN_LOCATIONS_PATH = Path(__file__).resolve().parents[1] / "data" / "known_locations.json"
COORDINATE_PRECISION = 5


@dataclass
class LocationResult:
    name: str
    country: str
    admin1: str | None
    latitude: float
    longitude: float
    timezone: str | None

    @property
    def label(self) -> str:
        parts = [self.name, self.admin1, self.country]
        return ", ".join([p for p in parts if p])


def _normalise_location_text(text: str) -> str:
    return " ".join("".join(ch if ch.isalnum() else " " for ch in text.lower()).split())


def load_known_locations(path: Path = KNOWN_LOCATIONS_PATH) -> list[dict[str, Any]]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []


def known_location_candidates(query: str, path: Path = KNOWN_LOCATIONS_PATH, limit: int = 5) -> list[LocationResult]:
    """Return fallback location candidates from local known landmarks."""
    normalised_query = _normalise_location_text(query)
    if not normalised_query:
        return []

    scored: list[tuple[int, LocationResult]] = []
    for item in load_known_locations(path):
        aliases = item.get("aliases", [])
        names = [item.get("name", ""), item.get("admin1", ""), item.get("country", ""), *aliases]
        normalised_names = [_normalise_location_text(name) for name in names if name]

        score = 0
        if any(normalised_query == name for name in normalised_names):
            score = 100
        elif any(normalised_query in name for name in normalised_names):
            score = 80
        elif any(name and name in normalised_query for name in normalised_names):
            score = 70

        if score > 0:
            try:
                location = LocationResult(
                    name=item.get("name", "Unknown"),
                    country=item.get("country", ""),
                    admin1=item.get("admin1"),
                    latitude=float(item["latitude"]),
                    longitude=float(item["longitude"]),
                    timezone=item.get("timezone"),
                )
            except (KeyError, TypeError, ValueError):
                continue
            scored.append((score, location))

    scored.sort(key=lambda row: row[0], reverse=True)
    return [location for _, location in scored[:limit]]


def merge_location_candidates(
    geocoded: list[LocationResult],
    fallback: list[LocationResult],
    limit: int = 5,
) -> list[LocationResult]:
    """Merge geocoded and fallback locations while removing duplicates."""
    merged: list[LocationResult] = []
    seen: set[tuple[int, int]] = set()
    for item in [*geocoded, *fallback]:
        key = (round(item.latitude, COORDINATE_PRECISION), round(item.longitude, COORDINATE_PRECISION))
        if key in seen:
            continue
        seen.add(key)
        merged.append(item)
        if len(merged) >= limit:
            break
    return merged


def geocode_location(query: str, count: int = 5) -> list[LocationResult]:
    """Return up to `count` matching locations for a text query."""
    if not query.strip():
        return []
    params = {"name": query, "count": count, "language": "en", "format": "json"}
    response = requests.get(GEOCODING_URL, params=params, timeout=15)
    response.raise_for_status()
    payload = response.json()
    results = payload.get("results", []) or []
    return [
        LocationResult(
            name=item.get("name", "Unknown"),
            country=item.get("country", ""),
            admin1=item.get("admin1"),
            latitude=float(item["latitude"]),
            longitude=float(item["longitude"]),
            timezone=item.get("timezone"),
        )
        for item in results
        if "latitude" in item and "longitude" in item
    ]


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
    response = requests.get(FORECAST_URL, params=params, timeout=15)
    response.raise_for_status()
    return response.json()


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
