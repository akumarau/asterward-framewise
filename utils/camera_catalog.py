"""Dynamic camera catalog backed by the Lensfun camera database."""
from __future__ import annotations

import io
import json
import re
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from xml.etree import ElementTree

import requests


APP_DIR = Path(__file__).resolve().parents[1]
CATALOG_PATH = APP_DIR / "data" / "camera_catalog.json"
CURATED_SPECS_PATH = APP_DIR / "data" / "camera_specs.json"
LENSFUN_ARCHIVE_URL = "https://github.com/lensfun/lensfun/archive/refs/heads/master.zip"
LENSFUN_PROJECT_URL = "https://github.com/lensfun/lensfun"
LENSFUN_LICENSE_URL = "https://creativecommons.org/licenses/by-sa/3.0/"
REQUEST_HEADERS = {"User-Agent": "FrameWise/0.1 (https://github.com/akumarau/Framewise)"}

BRAND_ALIASES = {
    "aee dv": "AEE",
    "asahi optical co.,ltd": "Pentax",
    "canon": "Canon",
    "casio": "Casio",
    "casio computer co.,ltd": "Casio",
    "casio computer co.,ltd.": "Casio",
    "contax": "Contax",
    "dji": "DJI",
    "eastman kodak company": "Kodak",
    "fujifilm": "Fujifilm",
    "gitup": "GitUp",
    "gopro": "GoPro",
    "hasselblad": "Hasselblad",
    "kodak": "Kodak",
    "konica minolta": "Konica Minolta",
    "konica minolta camera, inc.": "Konica Minolta",
    "leica": "Leica",
    "leica camera ag": "Leica",
    "mamiya": "Mamiya",
    "minolta co., ltd.": "Minolta",
    "nikon": "Nikon",
    "nikon corporation": "Nikon",
    "olympus": "Olympus",
    "olympus corporation": "Olympus",
    "olympus imaging corp.": "Olympus",
    "olympus optical co.,ltd": "Olympus",
    "om digital solutions": "OM System",
    "panasonic": "Panasonic",
    "pentax": "Pentax",
    "pentax corporation": "Pentax",
    "phase one": "Phase One",
    "ricoh": "Ricoh",
    "ricoh imaging company, ltd.": "Ricoh",
    "rolleiflex": "Rolleiflex",
    "samsung": "Samsung",
    "samsung techwin": "Samsung",
    "samsung techwin co.": "Samsung",
    "seiko epson corp.": "Epson",
    "sigma": "Sigma",
    "sony": "Sony",
    "yi technology": "YI Technology",
}

EXCLUDED_MAKERS = {
    "apple",
    "generic",
    "honor",
    "huawei",
    "lg mobile",
    "microsoft",
    "nokia",
}


class CameraCatalogError(RuntimeError):
    """Raised when the remote camera catalog cannot be refreshed."""


def _clean_text(value: str) -> str:
    return " ".join(value.split())


def _normalise_brand(maker: str) -> str | None:
    cleaned = _clean_text(maker)
    key = cleaned.casefold()
    if not cleaned or key in EXCLUDED_MAKERS:
        return None
    return BRAND_ALIASES.get(key, cleaned)


def _natural_sort_key(value: str) -> list[str | int]:
    return [int(part) if part.isdigit() else part.casefold() for part in re.split(r"(\d+)", value)]


def _model_identity(model: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", model.casefold().replace("α", "alpha"))


def _load_curated_specs(path: Path = CURATED_SPECS_PATH) -> dict[str, dict[str, Any]]:
    return json.loads(path.read_text(encoding="utf-8"))


def build_camera_catalog(
    archive_bytes: bytes,
    curated_specs: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Build a normalized brand/model catalog from a Lensfun archive."""
    models_by_brand: dict[str, dict[str, dict[str, Any]]] = {}

    def add_model(
        brand: str,
        model: str,
        *,
        crop_factor: float | None = None,
        mounts: list[str] | None = None,
        prefer: bool = False,
    ) -> None:
        identity = _model_identity(model)
        if not identity:
            return
        brand_models = models_by_brand.setdefault(brand, {})
        current = brand_models.get(identity)
        if current is None:
            current = {
                "model": model,
                "crop_factor": crop_factor,
                "mounts": set(mounts or []),
            }
            brand_models[identity] = current
            return

        if prefer or len(model) < len(current["model"]):
            current["model"] = model
        if current["crop_factor"] is None and crop_factor is not None:
            current["crop_factor"] = crop_factor
        current["mounts"].update(mounts or [])

    try:
        with zipfile.ZipFile(io.BytesIO(archive_bytes)) as archive:
            database_files = [
                name
                for name in archive.namelist()
                if "/data/db/" in name and name.endswith(".xml")
            ]
            if not database_files:
                raise CameraCatalogError("The Lensfun archive did not contain camera database files.")

            for name in database_files:
                root = ElementTree.fromstring(archive.read(name))
                for camera in root.findall(".//camera"):
                    maker = camera.findtext("maker") or ""
                    model = _clean_text(camera.findtext("model") or "")
                    brand = _normalise_brand(maker)
                    if brand and model:
                        crop_factor_text = camera.findtext("cropfactor")
                        try:
                            crop_factor = float(crop_factor_text) if crop_factor_text else None
                        except ValueError:
                            crop_factor = None
                        mounts = [
                            _clean_text(mount.text or "")
                            for mount in camera.findall("mount")
                            if _clean_text(mount.text or "")
                        ]
                        add_model(
                            brand,
                            model,
                            crop_factor=crop_factor,
                            mounts=mounts,
                        )
    except (zipfile.BadZipFile, ElementTree.ParseError) as exc:
        raise CameraCatalogError("The Lensfun camera archive could not be parsed.") from exc

    curated_specs = curated_specs if curated_specs is not None else _load_curated_specs()
    for spec in curated_specs.values():
        brand = _normalise_brand(str(spec.get("brand", "")))
        model = _clean_text(str(spec.get("display_name", "")))
        if brand and model:
            add_model(
                brand,
                model,
                crop_factor=spec.get("crop_factor"),
                mounts=list(spec.get("mounts", [])),
                prefer=True,
            )

    brands = {
        brand: sorted(
            (record["model"] for record in models.values()),
            key=_natural_sort_key,
        )
        for brand, models in sorted(models_by_brand.items(), key=lambda item: item[0].casefold())
    }
    camera_details = {
        brand: {
            record["model"]: {
                "crop_factor": record["crop_factor"],
                "mounts": sorted(record["mounts"]),
            }
            for record in models.values()
            if record["crop_factor"] is not None or record["mounts"]
        }
        for brand, models in models_by_brand.items()
    }
    model_count = sum(len(models) for models in brands.values())
    if not brands:
        raise CameraCatalogError("The generated camera catalog was empty.")

    return {
        "schema_version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": {
            "name": "Lensfun camera database",
            "project_url": LENSFUN_PROJECT_URL,
            "archive_url": LENSFUN_ARCHIVE_URL,
            "license": "CC BY-SA 3.0",
            "license_url": LENSFUN_LICENSE_URL,
            "attribution": "Lensfun contributors",
        },
        "brand_count": len(brands),
        "model_count": model_count,
        "brands": brands,
        "camera_details": camera_details,
    }


def fetch_camera_catalog(timeout: float = 60) -> dict[str, Any]:
    """Download and normalize the latest Lensfun camera database."""
    try:
        response = requests.get(
            LENSFUN_ARCHIVE_URL,
            headers=REQUEST_HEADERS,
            timeout=timeout,
        )
        response.raise_for_status()
    except requests.RequestException as exc:
        raise CameraCatalogError("The latest Lensfun camera catalog could not be downloaded.") from exc

    catalog = build_camera_catalog(response.content)
    if catalog["model_count"] < 100:
        raise CameraCatalogError("The refreshed camera catalog was unexpectedly small.")
    return catalog


def load_camera_catalog(path: Path = CATALOG_PATH) -> dict[str, Any]:
    """Load the bundled fallback camera catalog."""
    try:
        catalog = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise CameraCatalogError("The bundled camera catalog could not be loaded.") from exc

    if not isinstance(catalog.get("brands"), dict):
        raise CameraCatalogError("The bundled camera catalog has an invalid format.")
    return catalog


def save_camera_catalog(catalog: dict[str, Any], path: Path = CATALOG_PATH) -> None:
    """Save a generated catalog atomically."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = path.with_suffix(f"{path.suffix}.tmp")
    temporary_path.write_text(
        json.dumps(catalog, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    temporary_path.replace(path)


def camera_brands(catalog: dict[str, Any]) -> list[str]:
    return list(catalog.get("brands", {}).keys())


def camera_models(catalog: dict[str, Any], brand: str) -> list[str]:
    return list(catalog.get("brands", {}).get(brand, []))


def camera_details(catalog: dict[str, Any], brand: str, model: str) -> dict[str, Any]:
    return dict(catalog.get("camera_details", {}).get(brand, {}).get(model, {}))
