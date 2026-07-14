from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import streamlit as st

from utils.camera_specs import camera_match_candidates, resolution_summary
from utils.gear_recommender import build_recommendation, load_subject_rules, normalize_subject_term, parse_lenses
from utils.weather import (
    fetch_weather,
    geocode_location,
    known_location_candidates,
    merge_location_candidates,
    weather_risk_notes,
)


APP_DIR = Path(__file__).resolve().parent
DEFAULT_KIT = json.loads((APP_DIR / "data" / "default_kit.json").read_text(encoding="utf-8"))
AUTO_SUBJECT_OPTION = "Auto-detect from text"
CONFIDENCE_LOW = "low"


def _init_state(subject_rules: dict[str, dict[str, Any]]) -> None:
    if "inputs" not in st.session_state:
        st.session_state.inputs = {
            "camera_model": DEFAULT_KIT["camera"],
            "manual_width": 0,
            "manual_height": 0,
            "location_query": "",
            "subject_text": "",
            "subject_choice": AUTO_SUBJECT_OPTION,
            "indoor_outdoor": "Outdoor",
            "walking_level": "Light",
            "carry_style": "Minimalist",
            "flash_allowed": False,
            "lens_text": "\n".join(DEFAULT_KIT["lenses"]),
        }
    if "workflow_step" not in st.session_state:
        st.session_state.workflow_step = "inputs"
    if "review" not in st.session_state:
        st.session_state.review = {}
    if "camera_accepted" not in st.session_state:
        st.session_state.camera_accepted = False
    if "location_accepted" not in st.session_state:
        st.session_state.location_accepted = False
    if "subject_accepted" not in st.session_state:
        st.session_state.subject_accepted = False
    if "final_ready" not in st.session_state:
        st.session_state.final_ready = False
    if "final_data" not in st.session_state:
        st.session_state.final_data = {}

    if st.session_state.inputs.get("subject_choice") not in [AUTO_SUBJECT_OPTION, *subject_rules.keys()]:
        st.session_state.inputs["subject_choice"] = AUTO_SUBJECT_OPTION


def _analyse_inputs(subject_rules: dict[str, dict[str, Any]]) -> None:
    values = st.session_state.inputs
    camera_candidates = camera_match_candidates(values["camera_model"], limit=5)

    selected_subject = None
    subject_confidence = CONFIDENCE_LOW
    if values["subject_choice"] != AUTO_SUBJECT_OPTION:
        selected_subject = values["subject_choice"]
        subject_confidence = "high"
    else:
        selected_subject = normalize_subject_term(values["subject_text"], rules=subject_rules)
        if selected_subject:
            subject_confidence = "medium"

    geocoded = []
    geocode_error = None
    if values["location_query"].strip():
        try:
            geocoded = geocode_location(values["location_query"])
        except Exception as exc:
            geocoded = []
            geocode_error = str(exc)
    fallback = known_location_candidates(values["location_query"], limit=5) if values["location_query"].strip() else []
    location_candidates = merge_location_candidates(geocoded, fallback, limit=5)

    st.session_state.review = {
        "camera_candidates": camera_candidates,
        "camera_index": 0,
        "camera_confidence": camera_candidates[0]["confidence"] if camera_candidates else CONFIDENCE_LOW,
        "subject": selected_subject,
        "subject_confidence": subject_confidence,
        "location_candidates": location_candidates,
        "location_index": 0,
        "location_confidence": "high" if len(location_candidates) == 1 else ("medium" if location_candidates else CONFIDENCE_LOW),
        "geocode_error": geocode_error,
    }
    st.session_state.camera_accepted = False
    st.session_state.subject_accepted = False
    st.session_state.location_accepted = not values["location_query"].strip()
    st.session_state.final_ready = False
    st.session_state.final_data = {}
    st.session_state.workflow_step = "review"


def _selected_camera_spec() -> dict[str, Any] | None:
    review = st.session_state.review
    candidates = review.get("camera_candidates", [])
    idx = review.get("camera_index", 0)
    if not candidates:
        return None
    return candidates[idx]["spec"]


def _selected_location():
    review = st.session_state.review
    candidates = review.get("location_candidates", [])
    idx = review.get("location_index", 0)
    if not candidates:
        return None
    return candidates[idx]


def _render_final_plan() -> None:
    values = st.session_state.inputs
    review = st.session_state.review
    selected_spec = _selected_camera_spec()
    selected_location = _selected_location()
    lenses = parse_lenses(values["lens_text"])

    resolution = resolution_summary(
        selected_spec,
        manual_width=values["manual_width"] if values["manual_width"] > 0 else None,
        manual_height=values["manual_height"] if values["manual_height"] > 0 else None,
    )

    weather = None
    if selected_location:
        try:
            weather = fetch_weather(selected_location.latitude, selected_location.longitude)
        except Exception as exc:
            st.warning(f"Could not fetch weather data: {exc}")

    recommendation = build_recommendation(
        subject=review["subject"],
        lenses=lenses,
        indoor_outdoor=values["indoor_outdoor"],
        walking_level=values["walking_level"],
        flash_allowed=values["flash_allowed"],
        carry_style=values["carry_style"],
    )

    st.divider()
    st.header("Final shoot plan")

    if recommendation["primary_lenses"]:
        primary_label = " + ".join(recommendation["primary_lenses"])
        verdict = f"Carry **{primary_label}**"
        if recommendation["optional_lens"]:
            verdict += f"; add **{recommendation['optional_lens']}** only if needed."
        else:
            verdict += "."
    else:
        verdict = "No lens inventory entered. Use the recommended focal ranges below."

    st.success(verdict)

    st.subheader("Detected inputs accepted")
    st.write(f"- Camera: **{resolution['display_name']}**")
    st.write(f"- Subject: **{review['subject']}**")
    if selected_location:
        st.write(f"- Location: **{selected_location.label}**")
    else:
        st.write("- Location: **No weather location selected**")

    st.subheader("Recommended kit table")
    kit_rows = []
    for idx, lens in enumerate(recommendation["primary_lenses"], start=1):
        kit_rows.append(
            {
                "Role": f"Primary lens {idx}",
                "Item": lens,
                "Why": recommendation["lens_reason"],
            }
        )
    if recommendation["optional_lens"]:
        kit_rows.append(
            {
                "Role": "Optional lens",
                "Item": recommendation["optional_lens"],
                "Why": "Pack only if the subject variety, distance, or lighting justifies a third lens.",
            }
        )
    for item in recommendation["accessories"]:
        kit_rows.append({"Role": "Accessory", "Item": item, "Why": "Risk or workflow support."})
    st.dataframe(kit_rows, use_container_width=True, hide_index=True)

    st.subheader("What to leave behind")
    selected_items = set(recommendation["primary_lenses"])
    if recommendation["optional_lens"]:
        selected_items.add(recommendation["optional_lens"])
    leave_lenses = [lens for lens in lenses if lens not in selected_items]
    if leave_lenses:
        st.write(", ".join(leave_lenses))
    else:
        st.write("No extra lenses listed.")

    st.subheader("Camera setup")
    col_a, col_b, col_c = st.columns(3)
    col_a.metric("Camera", resolution["display_name"])
    col_b.metric("Resolution", f"{resolution['width']} × {resolution['height']}" if resolution["width"] else "Unknown")
    col_c.metric("Megapixels", f"{resolution['megapixels']} MP" if resolution["megapixels"] else "Unknown")

    st.subheader("Composition")
    for item in recommendation["composition"]:
        st.write(f"- {item}")
    st.subheader("Techniques")
    for item in recommendation["techniques"]:
        st.write(f"- {item}")

    st.subheader("Risk notes")
    for note in weather_risk_notes(weather):
        st.write(f"- {note}")


st.set_page_config(
    page_title="Camera Gear Scout",
    page_icon="📷",
    layout="wide",
)

st.title("📷 Camera Gear Scout")
st.caption("Plan a smaller, smarter photo kit using guided matching and confirmation before generating recommendations.")

with st.sidebar:
    st.header("Flow")
    st.write("1) Enter inputs. 2) Review detected matches. 3) Accept or edit. 4) Build final plan.")

subject_rules = load_subject_rules()
_init_state(subject_rules)
subject_options = [AUTO_SUBJECT_OPTION, *subject_rules.keys()]
inputs = st.session_state.inputs

st.header("Step 1: Enter shoot details")
with st.form("inputs_form"):
    col1, col2 = st.columns(2)
    with col1:
        camera_model = st.text_input(
            "Camera model (generic terms supported)",
            value=inputs["camera_model"],
            placeholder="e.g. sony a7r, canon r5, nikon z",
        )
        manual_width = st.number_input(
            "Manual max image width px (fallback)",
            min_value=0,
            value=inputs["manual_width"],
            step=1,
        )
        manual_height = st.number_input(
            "Manual max image height px (fallback)",
            min_value=0,
            value=inputs["manual_height"],
            step=1,
        )
        location_query = st.text_input(
            "Location (generic terms supported)",
            value=inputs["location_query"],
            placeholder="e.g. three sisters, sydney, opera house",
        )
    with col2:
        subject_text = st.text_input(
            "Subject keywords (optional)",
            value=inputs["subject_text"],
            placeholder="e.g. birds, city, portraits",
        )
        subject_choice = st.selectbox(
            "Subject override",
            subject_options,
            index=subject_options.index(inputs["subject_choice"]),
        )
        indoor_outdoor = st.selectbox(
            "Venue type",
            ["Outdoor", "Indoor", "Mixed"],
            index=["Outdoor", "Indoor", "Mixed"].index(inputs["indoor_outdoor"]),
        )
        walking_level = st.selectbox(
            "Walking distance / mobility",
            ["Light", "Moderate", "Heavy"],
            index=["Light", "Moderate", "Heavy"].index(inputs["walking_level"]),
        )
        carry_style = st.selectbox(
            "Carry style",
            ["Minimalist", "Balanced", "Maximum quality"],
            index=["Minimalist", "Balanced", "Maximum quality"].index(inputs["carry_style"]),
        )
        flash_allowed = st.checkbox(
            "Flash allowed",
            value=inputs["flash_allowed"],
        )

    lens_text = st.text_area(
        "Available lenses (one per line or comma-separated)",
        value=inputs["lens_text"],
        height=150,
    )
    analyse = st.form_submit_button("Analyze matches")

if analyse:
    st.session_state.inputs = {
        "camera_model": camera_model,
        "manual_width": int(manual_width),
        "manual_height": int(manual_height),
        "location_query": location_query,
        "subject_text": subject_text,
        "subject_choice": subject_choice,
        "indoor_outdoor": indoor_outdoor,
        "walking_level": walking_level,
        "carry_style": carry_style,
        "flash_allowed": flash_allowed,
        "lens_text": lens_text,
    }
    _analyse_inputs(subject_rules)

if st.session_state.workflow_step == "review":
    review = st.session_state.review
    st.divider()
    st.header("Step 2: Review detected matches")

    st.subheader("Detected camera")
    camera_candidates = review.get("camera_candidates", [])
    if camera_candidates:
        camera_labels = [
            f"{item['display_name']} ({item['confidence']} confidence, {item['match_basis']})"
            for item in camera_candidates
        ]
        review["camera_index"] = st.selectbox(
            "Choose camera option",
            options=list(range(len(camera_candidates))),
            index=min(review.get("camera_index", 0), len(camera_candidates) - 1),
            format_func=lambda idx: camera_labels[idx],
        )
        if camera_candidates[review["camera_index"]]["confidence"] == CONFIDENCE_LOW:
            st.warning("Low-confidence camera match. Please choose another option or edit camera input.")
        c1, c2, c3 = st.columns(3)
        if c1.button("Accept match", key="accept_camera"):
            st.session_state.camera_accepted = True
        if c2.button("Choose another option", key="change_camera"):
            st.session_state.camera_accepted = False
            if len(camera_candidates) > 1:
                review["camera_index"] = (review["camera_index"] + 1) % len(camera_candidates)
        if c3.button("Edit input", key="edit_camera"):
            st.session_state.workflow_step = "inputs"
    else:
        st.warning("No camera candidate detected.")
        if st.session_state.inputs["manual_width"] > 0 and st.session_state.inputs["manual_height"] > 0:
            st.info("Manual resolution fallback is available.")
            c1, c2 = st.columns(2)
            if c1.button("Accept manual fallback", key="accept_manual_camera"):
                st.session_state.camera_accepted = True
            if c2.button("Edit input", key="edit_manual_camera"):
                st.session_state.workflow_step = "inputs"
        else:
            st.info("Add manual width and height or edit camera input.")

    st.subheader("Detected subject")
    if review.get("subject"):
        st.write(
            f"Detected subject: **{review['subject']}** "
            f"(confidence: **{review.get('subject_confidence', CONFIDENCE_LOW)}**)"
        )
        s1, s2, s3 = st.columns(3)
        if s1.button("Accept subject", key="accept_subject"):
            st.session_state.subject_accepted = True
        if s2.button("Choose another option", key="change_subject"):
            st.session_state.subject_accepted = False
            st.session_state.workflow_step = "inputs"
        if s3.button("Edit input", key="edit_subject"):
            st.session_state.workflow_step = "inputs"
    else:
        st.warning("No subject match detected. Add subject keywords or use Subject override.")

    st.subheader("Detected location")
    location_candidates = review.get("location_candidates", [])
    if st.session_state.inputs["location_query"].strip():
        if review.get("geocode_error"):
            st.info(f"Live geocoding was unavailable: {review['geocode_error']}. Showing fallback/local matches when possible.")
        if location_candidates:
            location_labels = [f"{item.label} ({item.latitude:.5f}, {item.longitude:.5f})" for item in location_candidates]
            review["location_index"] = st.selectbox(
                "Choose location option",
                options=list(range(len(location_candidates))),
                index=min(review.get("location_index", 0), len(location_candidates) - 1),
                format_func=lambda idx: location_labels[idx],
            )
            if len(location_candidates) > 1:
                st.info("Multiple location matches found. Confirm one before continuing.")
            l1, l2, l3 = st.columns(3)
            if l1.button("Accept location", key="accept_location"):
                st.session_state.location_accepted = True
            if l2.button("Choose another option", key="change_location"):
                st.session_state.location_accepted = False
                if len(location_candidates) > 1:
                    review["location_index"] = (review["location_index"] + 1) % len(location_candidates)
            if l3.button("Edit input", key="edit_location"):
                st.session_state.workflow_step = "inputs"
        else:
            st.warning("No location match found from geocoding or local fallback.")
            l1, l2 = st.columns(2)
            if l1.button("Continue without weather", key="skip_location"):
                st.session_state.location_accepted = True
            if l2.button("Edit input", key="edit_location_missing"):
                st.session_state.workflow_step = "inputs"
    else:
        st.write("No location provided. Weather will be skipped.")

    all_inputs_confirmed = (
        st.session_state.camera_accepted
        and st.session_state.subject_accepted
        and st.session_state.location_accepted
    )

    if all_inputs_confirmed:
        st.success("All required inputs are accepted.")
        if st.button("Build final shoot plan", key="build_final"):
            st.session_state.final_ready = True
    else:
        st.warning("Please accept camera, subject, and location decisions (or skip location) before finalizing.")

if st.session_state.final_ready:
    _render_final_plan()
