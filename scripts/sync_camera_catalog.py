"""Refresh the bundled FrameWise camera catalog."""
from __future__ import annotations

import sys
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPOSITORY_ROOT))

from utils.camera_catalog import fetch_camera_catalog, save_camera_catalog


def main() -> None:
    catalog = fetch_camera_catalog()
    save_camera_catalog(catalog)
    print(
        f"Saved {catalog['model_count']} camera models "
        f"across {catalog['brand_count']} brands."
    )


if __name__ == "__main__":
    main()
