"""Integration test: city_discover.py's real output is importable.

Exercises the actual glue between Task 1 (city_discover.py) and Task 2
(per-language schema/data resolution in strollopia_import.py) without
mocking either -- only the network calls (geocoding, Places, OSM) are
mocked, since this test must not require a real API key or network access.
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'tools'))

from unittest.mock import patch
from city_discover import run
from strollopia_import import find_map_dirs, resolve_map_dir_paths


def test_city_discover_output_is_importable(tmp_path):
    geocode_result = {
        "lat": 45.0779, "lng": -64.4934,
        "country_code": "CA", "state": "Nova Scotia", "city": "Kentville",
        "bbox": (45.05, -64.52, 45.10, -64.46),
    }
    fake_place = {
        "name": "Test Cafe", "lat": 45.0779, "lng": -64.4934,
        "category": "Business", "subcategory": "Cafe",
        "description": "<b>Test Cafe</b>", "phone": "", "website": "", "address": "",
        "hours_mon": "closed", "hours_tue": "closed", "hours_wed": "closed",
        "hours_thu": "closed", "hours_fri": "closed", "hours_sat": "closed",
        "hours_sun": "closed", "image_file": "",
        "_source": "google", "_place_id": None, "_photo_reference": None,
    }
    with patch("city_discover.geocode_city", return_value=geocode_result), \
         patch("city_discover.discover_google", return_value=[fake_place]), \
         patch("city_discover.discover_osm", return_value=[]):
        result = run(
            city="Kentville, NS", api_key="fake-key", domain=None,
            languages=["en", "fr"], preset_names=["businesses"],
            init=True, no_photos=True, force=False,
            output_dir=str(tmp_path),
        )

    org_dir = result["org_dir"]
    map_dirs = find_map_dirs(org_dir)
    assert len(map_dirs) == 1
    assert os.path.basename(map_dirs[0]) == "business-map"

    # Both languages produced a schema+data pair strollopia_import can resolve
    paths_en = resolve_map_dir_paths(map_dirs[0], schema_path=os.path.join(map_dirs[0], "import-schema.en.yaml"))
    assert os.path.isfile(paths_en["data"])
    paths_fr = resolve_map_dir_paths(map_dirs[0], schema_path=os.path.join(map_dirs[0], "import-schema.fr.yaml"))
    assert os.path.isfile(paths_fr["data"])
