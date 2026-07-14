"""Camera specification helpers.

The app uses a small curated JSON database plus a manual fallback.
This avoids scraping manufacturer pages and keeps the app reliable.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any


DATA_PATH = Path(__file__).resolve().parents[1] / "data" / "camera_specs.json"


def _normalise(text: str) -> str:
    """Normalise user-entered camera names for forgiving lookup."""
    value = text.lower().replace("α", "alpha")
    value = value.replace("-", " ").replace("_", " ")
    value = re.sub(r"[^a-z0-9]+", " ", value)
    return " ".join(value.split())


def _compact_key(text: str) -> str:
    """Return a punctuation/spacing-insensitive key for model lookup."""
    return re.sub(r"[^a-z0-9]+", "", text.lower().replace("α", "alpha"))

def load_camera_specs(path: Path = DATA_PATH) -> dict[str, dict[str, Any]]:
    return json.loads(path.read_text(encoding="utf-8"))


def find_camera_spec(camera_model: str, specs: dict[str, dict[str, Any]] | None = None) -> dict[str, Any] | None:
    """Return camera spec by canonical name or alias.

    The lookup is intentionally forgiving, so compact names such as
    "Sony A7R6" can match aliases like "Sony A7R VI".
    """
    specs = specs or load_camera_specs()
    query = _normalise(camera_model)
    query_compact = _compact_key(camera_model)

    for key, spec in specs.items():
        names = [key, spec.get("display_name", ""), *spec.get("aliases", [])]
        normalised_names = {_normalise(name) for name in names if name}
        compact_names = {_compact_key(name) for name in names if name}
        if query in normalised_names or query_compact in compact_names:
            return spec

    # Soft contains match, useful for entries like "Sony A7R6 with 24-70".
    for key, spec in specs.items():
        names = [key, spec.get("display_name", ""), *spec.get("aliases", [])]
        if any(_normalise(name) in query for name in names if name):
            return spec
        if any(_compact_key(name) in query_compact for name in names if name):
            return spec

    return None

def resolution_summary(spec: dict[str, Any] | None) -> dict[str, Any]:
    """Return a normalized resolution object for UI display."""
    if spec:
        width, height = spec["max_resolution_px"]
        mp = spec.get("megapixels") or round((width * height) / 1_000_000, 1)
        return {
            "display_name": spec.get("display_name", "Known camera"),
            "width": int(width),
            "height": int(height),
            "megapixels": float(mp),
            "sensor": spec.get("sensor", "Unknown"),
            "source": spec.get("source", "Local curated data"),
            "known": True,
        }

    return {
        "display_name": "Unknown camera",
        "width": None,
        "height": None,
        "megapixels": None,
        "sensor": "Unknown",
        "source": "No detailed camera specification is available",
        "known": False,
    }
