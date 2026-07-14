from __future__ import annotations

import logging

import streamlit as st

from utils.camera_catalog import (
    CameraCatalogError,
    camera_brands,
    camera_details,
    camera_models,
    fetch_camera_catalog,
    load_camera_catalog,
)
from utils.camera_specs import find_camera_spec, resolution_summary
from utils.gear_recommender import build_recommendation, load_subject_rules, parse_lenses
from utils.weather import (
    LocationLookupError,
    LocationResult,
    WeatherLookupError,
    fetch_weather,
    geocode_location,
    weather_risk_notes,
)


LOGGER = logging.getLogger(__name__)
CAMERA_NOT_LISTED = "My camera is not listed"
SELECT_CAMERA_BRAND = "Select a camera brand"
SELECT_CAMERA_MODEL = "Select a camera model"


@st.cache_data(ttl=86_400, show_spinner="Refreshing the camera catalog...")
def load_dynamic_camera_catalog() -> tuple[dict, str | None]:
    try:
        return fetch_camera_catalog(), None
    except CameraCatalogError as exc:
        LOGGER.warning("Using the bundled camera catalog: %s", exc)
        return load_camera_catalog(), str(exc)


def reset_camera_model() -> None:
    st.session_state.camera_model = SELECT_CAMERA_MODEL


def clear_location_search() -> None:
    for key in ("location_results", "location_search_error", "selected_location_index"):
        st.session_state.pop(key, None)


@st.cache_data(ttl=604_800, show_spinner="Searching for matching locations...")
def search_locations(query: str) -> list[LocationResult]:
    return geocode_location(query, count=10)


st.set_page_config(
    page_title="FrameWise",
    page_icon="📷",
    layout="wide",
)

st.title("📷 FrameWise")
st.caption("Your intelligent photography advisor.")

if "access_mode" not in st.session_state:
    st.session_state.access_mode = None

if st.session_state.access_mode is None:
    _, login_column, _ = st.columns([1, 1.4, 1])

    with login_column:
        with st.container(border=True):
            st.subheader("Welcome to FrameWise")
            st.write("Build a practical camera, lens, weather, and technique plan for your next shoot.")
            st.info(
                "FrameWise is currently a public beta. Accounts and saved profiles are not enabled yet, "
                "and the app does not store your personal information."
            )

            if st.button("Open FrameWise", type="primary", width="stretch"):
                st.session_state.access_mode = "guest"
                st.rerun()

            st.caption("No account is required. Your entries remain only in the current app session.")

    st.stop()

with st.sidebar:
    st.subheader("Public beta")
    st.write("Using FrameWise in **guest mode**")
    st.caption("Accounts and saved profiles are planned but not enabled.")
    if st.button("Return to welcome", width="stretch"):
        st.session_state.access_mode = None
        st.rerun()

    st.divider()
    st.header("How it works")

    workflow_steps = [
        ("Choose your camera", "Select the camera brand and model."),
        ("Describe the shoot", "Set the subject, venue, mobility, carry style, and flash rules."),
        ("Confirm the location", "Search for the place and choose the exact address for weather."),
        ("Add your lens inventory", "List compatible lenses you own or plan to use."),
        ("Build the shoot plan", "Review the recommended kit, setup, techniques, and risks."),
    ]
    for step_number, (title, description) in enumerate(workflow_steps, start=1):
        st.markdown(f"**{step_number}. {title}**")
        st.caption(description)

    st.info(
        "FrameWise never assumes that you own a lens. It uses your inventory when provided "
        "and recommends suitable lens classes when it is empty."
    )

subject_rules = load_subject_rules()
catalog, catalog_refresh_error = load_dynamic_camera_catalog()
brands = camera_brands(catalog)

st.subheader("Shoot details")

selected_location = None
col1, col2 = st.columns(2)
with col1:
    camera_brand = st.selectbox(
        "Camera brand",
        [SELECT_CAMERA_BRAND, *brands],
        key="camera_brand",
        on_change=reset_camera_model,
    )
    brand_selected = camera_brand != SELECT_CAMERA_BRAND

    if brand_selected:
        models = camera_models(catalog, camera_brand)
        model_options = [SELECT_CAMERA_MODEL, *models, CAMERA_NOT_LISTED]
    else:
        model_options = [SELECT_CAMERA_MODEL]

    selected_camera_model = st.selectbox(
        "Camera model",
        model_options,
        key="camera_model",
        disabled=not brand_selected,
    )

    if brand_selected and selected_camera_model == CAMERA_NOT_LISTED:
        camera_model = st.text_input(
            "Enter camera model",
            placeholder="e.g. Canon EOS R5 Mark II",
            key=f"manual_camera_model_{camera_brand}",
        )
    elif brand_selected and selected_camera_model != SELECT_CAMERA_MODEL:
        camera_model = selected_camera_model
    else:
        camera_model = ""

    if not brand_selected:
        st.caption("Select a camera brand, then choose its model.")
    elif selected_camera_model == SELECT_CAMERA_MODEL:
        st.caption("Select a camera model to continue.")
    else:
        selected_spec = find_camera_spec(camera_model)
        if selected_spec:
            st.caption(
                f"Known resolution: {selected_spec['max_resolution_px'][0]} × "
                f"{selected_spec['max_resolution_px'][1]} px"
            )
        else:
            st.caption("Detailed resolution is not available for this model.")
    location_query = st.text_input(
        "Location",
        placeholder="e.g. Sydney Opera House, Sydney, Australia",
        key="location_query",
        on_change=clear_location_search,
    )
    if st.button(
        "Find location",
        disabled=not location_query.strip(),
        width="stretch",
    ):
        try:
            st.session_state.location_results = search_locations(location_query.strip())
            st.session_state.location_search_error = None
            st.session_state.selected_location_index = 0
        except LocationLookupError as exc:
            LOGGER.warning("Location search failed: %s", exc)
            st.session_state.location_results = []
            st.session_state.location_search_error = str(exc)

    if st.session_state.get("location_search_error"):
        st.warning(st.session_state.location_search_error)

    location_results = st.session_state.get("location_results", [])
    if location_results:
        selected_location_index = st.selectbox(
            "Choose the exact location",
            range(len(location_results)),
            format_func=lambda index: location_results[index].label,
            key="selected_location_index",
        )
        selected_location = location_results[selected_location_index]
        st.caption(
            f"Selected coordinates: {selected_location.latitude:.5f}, "
            f"{selected_location.longitude:.5f}"
        )
        st.markdown(
            "Location search © [OpenStreetMap contributors]"
            "(https://www.openstreetmap.org/copyright)."
        )
    elif location_query.strip():
        st.caption("Select **Find location**, then confirm the exact match before building the plan.")

    st.markdown(
        f"Camera list: [{catalog['source']['name']}]({catalog['source']['project_url']}) "
        f"({catalog['source']['license']}), refreshed daily."
    )
    st.caption(
        f"{catalog['model_count']:,} models across {catalog['brand_count']} brands. "
        "Use the manual option if a new or specialist camera is missing."
    )
    if catalog_refresh_error:
        st.warning("The live catalog could not be refreshed, so FrameWise is using its bundled fallback.")

with col2:
    subject = st.selectbox("Main subject", list(subject_rules.keys()))
    indoor_outdoor = st.selectbox("Venue type", ["Outdoor", "Indoor", "Mixed"])
    walking_level = st.selectbox("Walking distance / mobility", ["Light", "Moderate", "Heavy"])
    carry_style = st.selectbox("Carry style", ["Minimalist", "Balanced", "Maximum quality"])
    flash_allowed = st.checkbox("Flash allowed", value=False)

st.markdown("#### Lens inventory")
lens_text = st.text_area(
    "Enter lenses you own or plan to use, one per line or comma-separated",
    value="",
    height=160,
    placeholder="e.g. 24-70mm f/2.8\n70-200mm f/2.8",
    key=f"lens_inventory_{camera_brand}",
    disabled=not brand_selected,
)
if brand_selected:
    st.caption(
        f"Selected camera system: {camera_brand}. "
        "Adapted and third-party lenses are supported."
    )
else:
    st.caption("Select a camera system before adding lenses.")

submitted = st.button("Build shoot plan", type="primary")

if submitted:
    if not brand_selected or not camera_model.strip():
        st.error("Select a camera brand and model before building the shoot plan.")
        st.stop()

    lenses = parse_lenses(lens_text)

    spec = find_camera_spec(camera_model)
    selected_camera_details = camera_details(catalog, camera_brand, camera_model)
    resolution = resolution_summary(spec)

    weather = None

    if location_query.strip():
        if selected_location is None:
            st.error("Find and choose the exact location before building the shoot plan.")
            st.stop()
        try:
            weather = fetch_weather(selected_location.latitude, selected_location.longitude)
        except WeatherLookupError as exc:
            st.warning(str(exc))

    recommendation = build_recommendation(
        subject=subject,
        lenses=lenses,
        indoor_outdoor=indoor_outdoor,
        walking_level=walking_level,
        flash_allowed=flash_allowed,
        carry_style=carry_style,
        crop_factor=selected_camera_details.get("crop_factor"),
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
        recommended_primary = recommendation["recommended_lenses"][:2]
        recommended_optional = recommendation["recommended_lenses"][2:3]
        primary_label = " + ".join(recommended_primary)
        verdict = f"Recommended starting kit: **{primary_label}**"
        if recommended_optional:
            verdict += f"; consider **{recommended_optional[0]}** only if needed."
        else:
            verdict += "."

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
    if not recommendation["primary_lenses"]:
        for idx, lens in enumerate(recommendation["recommended_lenses"][:2], start=1):
            kit_rows.append(
                {
                    "Role": f"Recommended lens {idx}",
                    "Item": lens,
                    "Why": recommendation["lens_reason"],
                }
            )
        for lens in recommendation["recommended_lenses"][2:3]:
            kit_rows.append(
                {
                    "Role": "Optional lens",
                    "Item": lens,
                    "Why": "Add only if the subject variety, distance, or lighting justifies another lens.",
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
    elif not lenses:
        st.write("No owned lenses were entered. Use the recommendations above as a rental, purchase, or packing guide.")
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
    if not lenses:
        st.write("Rent or borrow the recommended lens class before buying, especially for specialist subjects.")
    elif subject == "Wildlife / Birds" and not any("600" in lens for lens in lenses):
        st.write("Possible gap: long wildlife reach. Consider renting a 400-600mm class lens before buying.")
    elif subject == "Astrophotography" and not any(("14" in lens or "12-24" in lens or "12 to 24" in lens) for lens in lenses):
        st.write("Possible gap: fast ultra-wide lens for landscape astro. Rent before buying.")
    elif subject == "Macro / Details" and not any("macro" in lens.lower() for lens in lenses):
        st.write("Possible gap: true macro lens. A close-up filter or extension tube is a cheaper experiment.")
    else:
        st.write("No obvious gear gap from the entered kit. Spend effort on timing, access, light, and technique first.")

else:
    st.write("Fill the form and select **Build shoot plan**.")
