# Camera Gear Scout

A lightweight Streamlit app that helps photographers choose a small, practical kit for a shoot.

The app asks for:

1. **Camera model** — used to show maximum still-image resolution.
2. **Location** — geocoded to GPS coordinates and used to fetch weather.
3. **Subject** — used to recommend lenses, composition ideas, and techniques.
4. **Available lenses** — optional inventory so the advice is based on what the photographer actually owns.

## Why this app exists

Photographers often carry too much gear. This app turns a broad gear checklist into a practical shoot plan: two primary lenses, one optional lens, useful accessories, camera setup, weather risks, and technique notes.

## Features

- Camera specs lookup from `data/camera_specs.json`
- Manual resolution fallback for unknown cameras
- Location search using Open-Meteo Geocoding API
- Forecast and current weather using Open-Meteo Forecast API
- Subject-based recommendations from `data/subject_rules.json`
- Editable default kit in `data/default_kit.json`
- No paid API key required for the starter version

## Repository structure

```text
camera-gear-scout-app/
├── app.py
├── requirements.txt
├── README.md
├── .gitignore
├── data/
│   ├── camera_specs.json
│   ├── default_kit.json
│   └── subject_rules.json
├── utils/
│   ├── __init__.py
│   ├── camera_specs.py
│   ├── gear_recommender.py
│   └── weather.py
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

Current starter camera entries include Sony Alpha 1 II, Sony Alpha 1, Sony Alpha 7R V, Sony Alpha 7R VI, Canon EOS R5 Mark II, Nikon Z8, and Fujifilm X-T5. The lookup accepts common compact aliases such as `Sony A7R6`, `A7R VI`, `Sony A1II`, and `Canon R5II`.


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

## Push to GitHub

Create an empty GitHub repository, then run:

```bash
git init
git add .
git commit -m "Initial Camera Gear Scout app"
git branch -M main
git remote add origin https://github.com/YOUR-USERNAME/YOUR-REPO.git
git push -u origin main
```

Or, with GitHub CLI:

```bash
gh repo create YOUR-REPO --public --source=. --remote=origin --push
```

## Deployment options

Good starter options:

- Streamlit Community Cloud
- Render
- Hugging Face Spaces
- Docker on any cloud VM

## Important notes

- The camera database is a starter dataset, not a complete camera-specs database.
- Avoid scraping manufacturer or retailer pages unless you have permission and stable terms.
- For production, add a proper camera-specs admin screen or a reviewed CSV/JSON import workflow.
- Weather is forecast-based and should be checked again close to the shoot.
