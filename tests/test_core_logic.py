import io
import zipfile

from utils.camera_catalog import build_camera_catalog, camera_brands, camera_details, camera_models
from utils.camera_specs import find_camera_spec, resolution_summary
from utils.gear_recommender import build_recommendation, match_lenses_for_subject, parse_lenses
from utils.weather import parse_location_results


def test_camera_alias_lookup():
    spec = find_camera_spec("Sony A1 II")
    assert spec is not None
    summary = resolution_summary(spec)
    assert summary["width"] == 8640
    assert summary["height"] == 5760


def test_unknown_camera_resolution():
    summary = resolution_summary(None)
    assert summary["width"] is None
    assert summary["megapixels"] is None


def test_lens_parsing_and_matching():
    lenses = parse_lenses("24-70mm f/2.8, 70-200mm f/2.8\n200-600mm")
    selected = match_lenses_for_subject(lenses, "Wildlife / Birds")
    assert selected[0] == "200-600mm"


def test_recommendation_does_not_invent_a_lens_inventory():
    recommendation = build_recommendation(
        subject="Wildlife / Birds",
        lenses=[],
        indoor_outdoor="Outdoor",
        walking_level="Light",
        flash_allowed=False,
        carry_style="Minimalist",
    )

    assert recommendation["primary_lenses"] == []
    assert recommendation["optional_lens"] is None
    assert recommendation["recommended_lenses"][0] == "400-600mm lens"


def test_recommendation_adjusts_focal_length_for_crop_sensor():
    recommendation = build_recommendation(
        subject="Street / Travel",
        lenses=[],
        indoor_outdoor="Outdoor",
        walking_level="Light",
        flash_allowed=False,
        carry_style="Minimalist",
        crop_factor=1.5,
    )

    assert recommendation["recommended_lenses"][:2] == [
        "Approx. 16-47mm lens (24-70mm full-frame equivalent)",
        "Approx. 23mm lens (35mm full-frame equivalent)",
    ]


def test_sony_a7r6_lookup():
    spec = find_camera_spec("Sony A7R6")
    assert spec is not None
    summary = resolution_summary(spec)
    assert summary["display_name"] == "Sony Alpha 7R VI"
    assert summary["width"] == 9984
    assert summary["height"] == 6656
    assert summary["megapixels"] == 66.8


def test_sony_a7r_vi_spacing_lookup():
    spec = find_camera_spec("Sony A7 R6")
    assert spec is not None
    assert spec["display_name"] == "Sony Alpha 7R VI"


def test_camera_catalog_normalises_brands_and_excludes_phones():
    database = b"""
    <lensdatabase>
      <camera>
        <maker>Nikon Corporation</maker>
        <model>Nikon Z8</model>
        <mount>Nikon Z</mount>
        <cropfactor>1.0</cropfactor>
      </camera>
      <camera><maker>Nikon</maker><model>Nikon Z 8</model></camera>
      <camera><maker>Apple</maker><model>iPhone 16 Pro</model></camera>
    </lensdatabase>
    """
    archive_buffer = io.BytesIO()
    with zipfile.ZipFile(archive_buffer, "w") as archive:
        archive.writestr("lensfun-master/data/db/test.xml", database)

    curated_specs = {
        "canon eos r5 mark ii": {
            "brand": "Canon",
            "display_name": "Canon EOS R5 Mark II",
        }
    }
    catalog = build_camera_catalog(archive_buffer.getvalue(), curated_specs=curated_specs)

    assert camera_brands(catalog) == ["Canon", "Nikon"]
    assert camera_models(catalog, "Nikon") == ["Nikon Z8"]
    assert camera_details(catalog, "Nikon", "Nikon Z8") == {
        "crop_factor": 1.0,
        "mounts": ["Nikon Z"],
    }
    assert catalog["model_count"] == 2


def test_location_results_keep_full_address_context():
    results = parse_location_results(
        [
            {
                "name": "Sydney Opera House",
                "display_name": (
                    "Sydney Opera House, Bennelong Point, Sydney, "
                    "New South Wales, Australia"
                ),
                "lat": "-33.85678",
                "lon": "151.21530",
                "address": {
                    "state": "New South Wales",
                    "country": "Australia",
                },
            }
        ]
    )

    assert results[0].label.endswith("New South Wales, Australia")
    assert results[0].latitude == -33.85678
