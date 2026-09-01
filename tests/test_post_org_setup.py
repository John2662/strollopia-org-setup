"""Tests for post_org_setup.py"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'tools'))

import yaml
from post_org_setup import check_org_maps_have_data


def _write_org_setup(org_dir, org_maps):
    os.makedirs(org_dir, exist_ok=True)
    yaml_path = os.path.join(org_dir, "org-setup.yaml")
    with open(yaml_path, "w") as f:
        yaml.dump({"org_domain_name": "test.strollopia.com", "org_maps": org_maps}, f)
    return yaml_path


def test_check_org_maps_have_data_passes_for_legacy_schema(tmp_path, capsys):
    yaml_path = _write_org_setup(tmp_path, {"main-map": {"is_public": True}})
    map_dir = tmp_path / "main-map"
    map_dir.mkdir()
    (map_dir / "import-schema.yaml").write_text("x")
    (map_dir / "map-data.tsv").write_text("x")

    check_org_maps_have_data(str(yaml_path))

    assert "WARNING" not in capsys.readouterr().out


def test_check_org_maps_have_data_passes_for_language_specific_schema(tmp_path, capsys):
    # This is the case that broke before this task: a city_discover.py
    # output with only import-schema.en.yaml + map-data.en.tsv, no bare
    # import-schema.yaml, used to be incorrectly flagged as incomplete.
    yaml_path = _write_org_setup(tmp_path, {"business-map": {"is_public": True}})
    map_dir = tmp_path / "business-map"
    map_dir.mkdir()
    (map_dir / "import-schema.en.yaml").write_text("x")
    (map_dir / "map-data.en.tsv").write_text("x")

    check_org_maps_have_data(str(yaml_path))

    assert "WARNING" not in capsys.readouterr().out


def test_check_org_maps_have_data_warns_when_schema_has_no_data(tmp_path, capsys):
    yaml_path = _write_org_setup(tmp_path, {"empty-map": {"is_public": True}})
    map_dir = tmp_path / "empty-map"
    map_dir.mkdir()
    (map_dir / "import-schema.en.yaml").write_text("x")
    # no map-data.en.tsv

    check_org_maps_have_data(str(yaml_path))

    assert "empty-map" in capsys.readouterr().out


def test_check_org_maps_have_data_warns_when_map_dir_missing(tmp_path, capsys):
    yaml_path = _write_org_setup(tmp_path, {"missing-map": {"is_public": True}})

    check_org_maps_have_data(str(yaml_path))

    assert "missing-map" in capsys.readouterr().out
