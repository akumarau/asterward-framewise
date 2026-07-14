from utils.camera_specs import find_camera_spec, resolution_summary
from utils.gear_recommender import match_lenses_for_subject, parse_lenses


def test_camera_alias_lookup():
    spec = find_camera_spec("Sony A1 II")
    assert spec is not None
    summary = resolution_summary(spec)
    assert summary["width"] == 8640
    assert summary["height"] == 5760


def test_manual_resolution_fallback():
    summary = resolution_summary(None, manual_width=6000, manual_height=4000)
    assert summary["megapixels"] == 24.0


def test_lens_parsing_and_matching():
    lenses = parse_lenses("24-70mm f/2.8, 70-200mm f/2.8\n200-600mm")
    selected = match_lenses_for_subject(lenses, "Wildlife / Birds")
    assert selected[0] == "200-600mm"


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
