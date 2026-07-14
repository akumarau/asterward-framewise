"""Subject-based lens and technique recommendations."""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any


RULES_PATH = Path(__file__).resolve().parents[1] / "data" / "subject_rules.json"


def load_subject_rules(path: Path = RULES_PATH) -> dict[str, dict[str, Any]]:
    return json.loads(path.read_text(encoding="utf-8"))


def parse_lenses(raw_lenses: str) -> list[str]:
    """Parse newline or comma separated lens inventory."""
    if not raw_lenses:
        return []
    chunks = re.split(r"[,\n]+", raw_lenses)
    return [chunk.strip() for chunk in chunks if chunk.strip()]


def _contains_keyword(lens: str, keyword: str) -> bool:
    return keyword.lower() in lens.lower()


def _format_recommended_lens(focal_range: str, crop_factor: float | None) -> str:
    normalized = focal_range.strip()
    lower = normalized.casefold()
    if lower == "teleconverter":
        return "Compatible teleconverter for additional reach"
    if lower == "telescope":
        return "Telescope and tracking-mount setup"

    match = re.fullmatch(r"(\d+)(?:-(\d+))?mm(?:\s+(.*))?", normalized, flags=re.IGNORECASE)
    if not match:
        return normalized

    low = int(match.group(1))
    high = int(match.group(2)) if match.group(2) else None
    descriptor = (match.group(3) or "").strip()
    descriptor_label = f" {descriptor}" if descriptor else ""

    if crop_factor and abs(crop_factor - 1.0) > 0.05:
        actual_low = round(low / crop_factor)
        actual_high = round(high / crop_factor) if high else None
        actual_range = f"{actual_low}-{actual_high}mm" if actual_high else f"{actual_low}mm"
        return (
            f"Approx. {actual_range}{descriptor_label} lens "
            f"({normalized} full-frame equivalent)"
        )

    return f"{normalized} lens"


def recommended_lens_classes(
    subject: str,
    crop_factor: float | None = None,
    rules: dict[str, dict[str, Any]] | None = None,
) -> list[str]:
    rules = rules or load_subject_rules()
    preferred_ranges = rules.get(subject, {}).get("preferred_focal_ranges", [])
    return [_format_recommended_lens(focal_range, crop_factor) for focal_range in preferred_ranges]


def match_lenses_for_subject(lenses: list[str], subject: str, rules: dict[str, dict[str, Any]] | None = None) -> list[str]:
    """Choose up to two primary lenses and one optional lens based on user inventory."""
    rules = rules or load_subject_rules()
    rule = rules.get(subject, {})
    keywords = rule.get("lens_keywords", [])
    matches: list[str] = []

    for keyword in keywords:
        for lens in lenses:
            if lens not in matches and _contains_keyword(lens, keyword):
                matches.append(lens)

    # Return 2 primary + 1 optional max.
    if matches:
        return matches[:3]

    # Fallback: choose first few lenses but explain that matching was weak in the UI.
    return lenses[:3]


def accessory_advice(subject: str, indoor_outdoor: str, flash_allowed: bool, walking_level: str) -> list[str]:
    advice: list[str] = ["Extra batteries and memory cards"]
    s = subject.lower()

    if any(word in s for word in ["landscape", "architecture", "astro", "macro", "product"]):
        advice.append("Tripod if the location allows it and walking distance is manageable")

    if any(word in s for word in ["portrait", "event", "product", "food", "macro"]) and flash_allowed:
        advice.append("Flash or small light modifier")
    elif any(word in s for word in ["event", "portrait"]) and not flash_allowed:
        advice.append("Fast lens and higher ISO plan because flash is not allowed")

    if "astro" in s:
        advice.extend(["Red headlamp", "Intervalometer", "Dew control if humidity is high"])

    if indoor_outdoor in {"Outdoor", "Mixed"}:
        advice.append("CPL/ND filters only if landscapes, water, glass, or long exposures are expected")
        advice.append("Weather cover or dry bag if rain is possible")

    if walking_level == "Heavy":
        advice.append("Keep to the 2-lens kit unless the subject clearly needs the optional lens")

    return advice


def build_recommendation(
    subject: str,
    lenses: list[str],
    indoor_outdoor: str,
    walking_level: str,
    flash_allowed: bool,
    carry_style: str,
    crop_factor: float | None = None,
) -> dict[str, Any]:
    rules = load_subject_rules()
    rule = rules.get(subject, {})
    selected = match_lenses_for_subject(lenses, subject, rules)
    primary = selected[:2]
    optional = selected[2:3]

    return {
        "subject": subject,
        "primary_lenses": primary,
        "optional_lens": optional[0] if optional else None,
        "lens_reason": rule.get("default_lens_advice", "Use lenses that match subject distance, light, and movement."),
        "preferred_focal_ranges": rule.get("preferred_focal_ranges", []),
        "recommended_lenses": recommended_lens_classes(subject, crop_factor, rules),
        "composition": rule.get("composition", []),
        "techniques": rule.get("techniques", []),
        "accessories": accessory_advice(subject, indoor_outdoor, flash_allowed, walking_level),
        "carry_style": carry_style,
    }
