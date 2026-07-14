# FrameWise

**Your intelligent photography advisor.**

A lightweight Streamlit app that helps photographers choose a small, practical kit for a shoot.

> [!NOTE]
> FrameWise is an early public beta. It currently runs without user accounts,
> saved profiles, or persistent shoot plans. Information entered in the UI is
> retained only for the active Streamlit session.

The app asks for:

1. **Camera brand and model** — used for system-aware and crop-factor-aware guidance.
2. **Location** — explicitly selected from matching places before weather is fetched.
3. **Subject** — used to recommend lenses, composition ideas, and techniques.
4. **Available lenses** — optional inventory so the advice is based on what the photographer actually owns.

## Why this app exists

Photographers often carry too much gear. This app turns a broad gear checklist into a practical shoot plan: two primary lenses, one optional lens, useful accessories, camera setup, weather risks, and technique notes.

## Features

- Brand-first camera selection from the Lensfun camera database
- Daily camera-catalog refresh with a bundled offline fallback
- Curated camera specs lookup from `data/camera_specs.json`
- Landmark and address search using OpenStreetMap Nominatim
- Explicit location confirmation before Open-Meteo weather lookup
- Forecast and current weather using Open-Meteo Forecast API
- Subject-based recommendations from `data/subject_rules.json`
- User-entered, camera-system-specific lens inventory
- Crop-factor-aware lens-class recommendations when no inventory is entered
- No paid API key required for the starter version

## Repository structure

```text
Framewise/
├── app.py
├── requirements.txt
├── README.md
├── .gitignore
├── data/
│   ├── camera_specs.json
│   ├── camera_catalog.json
│   ├── CAMERA_CATALOG_LICENSE.md
│   └── subject_rules.json
├── utils/
│   ├── __init__.py
│   ├── camera_specs.py
│   ├── camera_catalog.py
│   ├── gear_recommender.py
│   └── weather.py
├── scripts/
│   └── sync_camera_catalog.py
└── tests/
    └── test_core_logic.py
```

## Run locally

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

On Windows PowerShell:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
streamlit run app.py
```

## Add your own cameras

The brand/model selector refreshes once per day from the
[Lensfun camera database](https://github.com/lensfun/lensfun). If that request
fails, FrameWise uses the bundled `data/camera_catalog.json` snapshot.

Refresh the bundled snapshot manually with:

```powershell
python scripts\sync_camera_catalog.py
```

Lensfun-derived catalog data is licensed under CC BY-SA 3.0. See
`data/CAMERA_CATALOG_LICENSE.md` for attribution and modification details.

Detailed resolution data remains locally curated. Current starter entries include Sony Alpha 1 II, Sony Alpha 1, Sony Alpha 7R V, Sony Alpha 7R VI, Canon EOS R5 Mark II, Nikon Z8, and Fujifilm X-T5. The lookup accepts common compact aliases such as `Sony A7R6`, `A7R VI`, `Sony A1II`, and `Canon R5II`.


Edit `data/camera_specs.json`.

Each camera entry should look like this:

```json
{
  "sony alpha 1 mark ii": {
    "display_name": "Sony Alpha 1 II / Alpha 1 Mark II",
    "aliases": ["sony a1 ii", "sony alpha 1 ii", "sony ilce-1m2"],
    "megapixels": 50.1,
    "max_resolution_px": [8640, 5760],
    "sensor": "35mm full-frame stacked CMOS",
    "source": "Sony official specs"
  }
}
```

## Add your own subject rules

Edit `data/subject_rules.json`.

The recommendation system is intentionally simple and transparent. Add new subject types, focal ranges, lens keywords, composition notes, and technique notes.

## Privacy and external services

- FrameWise does not persist user-entered information in the current beta.
- Camera catalog updates are downloaded from the Lensfun GitHub repository.
- Location searches are sent to OpenStreetMap Nominatim only when the user
  selects **Find location**.
- Selected coordinates are sent to Open-Meteo to retrieve weather information.
- The public Nominatim service is intended for moderate use. For a higher-traffic
  deployment, configure `FRAMEWISE_GEOCODING_URL` to use an appropriate hosted
  geocoding provider.

## Deploy with Streamlit Community Cloud

1. Sign in to [Streamlit Community Cloud](https://share.streamlit.io/).
2. Create an app from this repository.
3. Select the `main` branch and `app.py` entry point.
4. Deploy. The current beta does not require application secrets.

## Important notes

- The camera database is a starter dataset, not a complete camera-specs database.
- Avoid scraping manufacturer or retailer pages unless you have permission and stable terms.
- For production, add a proper camera-specs admin screen or a reviewed CSV/JSON import workflow.
- Weather is forecast-based and should be checked again close to the shoot.
- Authentication and saved user profiles remain planned work.

## Licensing

FrameWise application code is available under the MIT License. The generated
camera catalog is derived from Lensfun and distributed separately under
CC BY-SA 3.0; see `data/CAMERA_CATALOG_LICENSE.md`.
