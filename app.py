from __future__ import annotations

import json
from pathlib import Path

import streamlit as st

from utils.camera_specs import find_camera_spec, resolution_summary
from utils.gear_recommender import build_recommendation, load_subject_rules, parse_lenses
from utils.weather import fetch_weather, geocode_location, weather_risk_notes


APP_DIR = Path(__file__).resolve().parent
DEFAULT_KIT = json.loads((APP_DIR / "data" / "default_kit.json").read_text(encoding="utf-8"))


st.set_page_config(
    page_title="Camera Gear Scout",
    page_icon="📷",
    layout="wide",
)

st.title("📷 Camera Gear Scout")
st.caption("Plan a smaller, smarter photo kit based on camera resolution, location weather, and subject.")

with st.sidebar:
    st.header("How it works")
    st.write(
        "1. Enter a camera model or manual resolution.\\n"
        "2. Enter a location so the app can geocode it and check weather.\\n"
        "3. Choose the subject to get lens, composition, and technique guidance."
    )
    st.info("This is a rule-based starter app. Expand the JSON files as your camera and lens database grows.")

subject_rules = load_subject_rules()

with st.form("planning_form"):
    st.subheader("Shoot details")

    col1, col2 = st.columns(2)
    with col1:
        camera_model = st.text_input(
            "Camera model",
            value=DEFAULT_KIT["camera"],
            placeholder="e.g. Sony Alpha 1 II, Canon EOS R5 Mark II, Nikon Z8",
        )
        manual_width = st.number_input("Manual max image width px, if unknown", min_value=0, value=0, step=1)
        manual_height = st.number_input("Manual max image height px, if unknown", min_value=0, value=0, step=1)
        location_query = st.text_input("Location", placeholder="e.g. Sydney Opera House, NSW")

    with col2:
        subject = st.selectbox("Main subject", list(subject_rules.keys()))
        indoor_outdoor = st.selectbox("Venue type", ["Outdoor", "Indoor", "Mixed"])
        walking_level = st.selectbox("Walking distance / mobility", ["Light", "Moderate", "Heavy"])
        carry_style = st.selectbox("Carry style", ["Minimalist", "Balanced", "Maximum quality"])
        flash_allowed = st.checkbox("Flash allowed", value=False)

    st.markdown("#### Available lenses")
    lens_text = st.text_area(
        "Paste available lenses, one per line or comma-separated",
        value="\\n".join(DEFAULT_KIT["lenses"]),
        height=160,
    )

    submitted = st.form_submit_button("Build shoot plan")

if submitted:
    lenses = parse_lenses(lens_text)

    spec = find_camera_spec(camera_model)
    resolution = resolution_summary(
        spec,
        manual_width=manual_width if manual_width > 0 else None,
        manual_height=manual_height if manual_height > 0 else None,
    )

    weather = None
    selected_location = None
    location_results = []

    if location_query.strip():
        try:
            location_results = geocode_location(location_query)
            if location_results:
                selected_location = location_results[0]
                weather = fetch_weather(selected_location.latitude, selected_location.longitude)
            else:
                st.warning("No location match found. Try a more specific place name.")
        except Exception as exc:
            st.warning(f"Could not fetch location/weather data: {exc}")

    recommendation = build_recommendation(
        subject=subject,
        lenses=lenses,
        indoor_outdoor=indoor_outdoor,
        walking_level=walking_level,
        flash_allowed=flash_allowed,
        carry_style=carry_style,
    )

    st.divider()
    st.header("1. Quick verdict")

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

    st.header("2. Recommended kit table")

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

    st.header("3. What to leave behind")
    selected_items = set(recommendation["primary_lenses"])
    if recommendation["optional_lens"]:
        selected_items.add(recommendation["optional_lens"])
    leave_lenses = [lens for lens in lenses if lens not in selected_items]
    if leave_lenses:
        st.write("Leave these lenses behind unless the brief changes:")
        st.write(", ".join(leave_lenses))
    else:
        st.write("No extra lenses listed.")

    if walking_level == "Heavy":
        st.write("Avoid heavy tripod setups unless the shot depends on long exposure, macro precision, or night work.")

    st.header("4. Camera setup")
    col_a, col_b, col_c = st.columns(3)
    col_a.metric("Camera", resolution["display_name"])
    col_b.metric("Resolution", f"{resolution['width']} × {resolution['height']}" if resolution["width"] else "Unknown")
    col_c.metric("Megapixels", f"{resolution['megapixels']} MP" if resolution["megapixels"] else "Unknown")

    if subject in {"Wildlife / Birds", "Sports / Action", "Events / Stage"}:
        st.write("Suggested setup: continuous AF, subject detection where available, burst mode, Auto ISO, and a shutter-speed floor suitable for movement.")
    elif subject in {"Landscape", "Architecture / Interiors", "Astrophotography", "Macro / Details", "Product / Food"}:
        st.write("Suggested setup: RAW capture, histogram review, careful focus check, and tripod/controlled support where the result benefits.")
    else:
        st.write("Suggested setup: RAW capture, Eye AF where relevant, Auto ISO with a sensible minimum shutter speed, and exposure compensation ready.")

    st.subheader("Composition")
    for item in recommendation["composition"]:
        st.write(f"- {item}")

    st.subheader("Techniques")
    for item in recommendation["techniques"]:
        st.write(f"- {item}")

    st.header("5. Risk notes")

    if selected_location:
        st.write(
            f"Weather location: **{selected_location.label}** "
            f"({selected_location.latitude:.5f}, {selected_location.longitude:.5f})"
        )
        current = (weather or {}).get("current", {})
        if current:
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Temperature", f"{current.get('temperature_2m', '—')} °C")
            c2.metric("Cloud cover", f"{current.get('cloud_cover', '—')} %")
            c3.metric("Wind", f"{current.get('wind_speed_10m', '—')} km/h")
            c4.metric("Rain", f"{current.get('rain', current.get('precipitation', '—'))} mm")
    else:
        st.write("No weather location selected.")

    for note in weather_risk_notes(weather):
        st.write(f"- {note}")

    st.header("6. Optional upgrade, rental, or accessory")
    if subject == "Wildlife / Birds" and not any("600" in lens for lens in lenses):
        st.write("Possible gap: long wildlife reach. Consider renting a 400-600mm class lens before buying.")
    elif subject == "Astrophotography" and not any(("14" in lens or "12-24" in lens or "12 to 24" in lens) for lens in lenses):
        st.write("Possible gap: fast ultra-wide lens for landscape astro. Rent before buying.")
    elif subject == "Macro / Details" and not any("macro" in lens.lower() for lens in lenses):
        st.write("Possible gap: true macro lens. A close-up filter or extension tube is a cheaper experiment.")
    else:
        st.write("No obvious gear gap from the entered kit. Spend effort on timing, access, light, and technique first.")

else:
    st.write("Fill the form and select **Build shoot plan**.")
