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


def _token_score(query: str, candidate: str) -> int:
    query_tokens = {token for token in query.split() if len(token) > 1}
    candidate_tokens = {token for token in candidate.split() if len(token) > 1}
    if not query_tokens or not candidate_tokens:
        return 0
    overlap = len(query_tokens & candidate_tokens)
    if not overlap:
        return 0
    coverage = overlap / max(1, len(query_tokens))
    return int(40 + (coverage * 30))


def load_camera_specs(path: Path = DATA_PATH) -> dict[str, dict[str, Any]]:
    return json.loads(path.read_text(encoding="utf-8"))


def camera_match_candidates(
    camera_model: str,
    specs: dict[str, dict[str, Any]] | None = None,
    limit: int = 5,
) -> list[dict[str, Any]]:
    """Return ranked camera candidates for forgiving user input."""
    specs = specs or load_camera_specs()
    query = _normalise(camera_model)
    query_compact = _compact_key(camera_model)
    if not query:
        return []

    candidates: list[dict[str, Any]] = []
    for key, spec in specs.items():
        names = [key, spec.get("display_name", ""), *spec.get("aliases", [])]
        best_score = 0
        best_basis = "weak token overlap"

        for name in names:
            if not name:
                continue
            normalised_name = _normalise(name)
            compact_name = _compact_key(name)
            score = 0
            basis = "weak token overlap"

            if query == normalised_name or query_compact == compact_name:
                score = 100
                basis = "exact alias match"
            elif query and query in normalised_name:
                score = 85
                basis = "partial alias match"
            elif normalised_name and normalised_name in query:
                score = 80
                basis = "camera alias found inside input"
            elif query_compact and query_compact in compact_name:
                score = 75
                basis = "compact partial alias match"
            elif compact_name and compact_name in query_compact:
                score = 70
                basis = "compact alias found inside input"
            else:
                score = _token_score(query, normalised_name)
                if score:
                    basis = "token overlap match"

            if score > best_score:
                best_score = score
                best_basis = basis

        if best_score > 0:
            confidence = "low"
            if best_score >= 95:
                confidence = "high"
            elif best_score >= 70:
                confidence = "medium"

            candidates.append(
                {
                    "canonical_key": key,
                    "display_name": spec.get("display_name", key),
                    "score": best_score,
                    "confidence": confidence,
                    "match_basis": best_basis,
                    "spec": spec,
                }
            )

    candidates.sort(key=lambda item: item["score"], reverse=True)
    return candidates[:limit]


def find_camera_spec(camera_model: str, specs: dict[str, dict[str, Any]] | None = None) -> dict[str, Any] | None:
    """Return camera spec by canonical name or alias.

    The lookup is intentionally forgiving, so compact names such as
    "Sony A7R6" can match aliases like "Sony A7R VI".
    """
    candidates = camera_match_candidates(camera_model, specs=specs, limit=1)
    if not candidates:
        return None
    return candidates[0]["spec"]

def resolution_summary(spec: dict[str, Any] | None, manual_width: int | None = None, manual_height: int | None = None) -> dict[str, Any]:
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

    if manual_width and manual_height:
        return {
            "display_name": "Manual camera entry",
            "width": int(manual_width),
            "height": int(manual_height),
            "megapixels": round((manual_width * manual_height) / 1_000_000, 1),
            "sensor": "Unknown",
            "source": "Manual user input",
            "known": False,
        }

    return {
        "display_name": "Unknown camera",
        "width": None,
        "height": None,
        "megapixels": None,
        "sensor": "Unknown",
        "source": "No camera match and no manual resolution supplied",
        "known": False,
    }
