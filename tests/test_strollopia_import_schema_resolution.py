"""Tests for per-language schema/data resolution in strollopia_import.py"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'tools'))

import pytest
from strollopia_import import (
    find_schemas_in_map_dir, find_data_path_for_schema, resolve_map_dir_paths,
    find_map_dirs,
)


def _write(path, content="x"):
    with open(path, "w") as f:
        f.write(content)


def test_find_schemas_legacy_only(tmp_path):
    _write(tmp_path / "import-schema.yaml")
    assert find_schemas_in_map_dir(str(tmp_path)) == [str(tmp_path / "import-schema.yaml")]


def test_find_schemas_language_specific_sorted(tmp_path):
    _write(tmp_path / "import-schema.en.yaml")
    _write(tmp_path / "import-schema.de.yaml")
    result = find_schemas_in_map_dir(str(tmp_path))
    assert result == [str(tmp_path / "import-schema.de.yaml"), str(tmp_path / "import-schema.en.yaml")]


def test_find_schemas_prefers_language_specific_over_legacy(tmp_path):
    _write(tmp_path / "import-schema.yaml")
    _write(tmp_path / "import-schema.en.yaml")
    result = find_schemas_in_map_dir(str(tmp_path))
    assert result == [str(tmp_path / "import-schema.en.yaml")]


def test_find_schemas_none_found(tmp_path):
    assert find_schemas_in_map_dir(str(tmp_path)) == []


def test_find_data_path_legacy(tmp_path):
    schema = tmp_path / "import-schema.yaml"
    _write(schema)
    _write(tmp_path / "map-data.tsv")
    data_path, delimiter = find_data_path_for_schema(str(tmp_path), str(schema))
    assert data_path == str(tmp_path / "map-data.tsv")
    assert delimiter == "\t"


def test_find_data_path_language_specific(tmp_path):
    schema = tmp_path / "import-schema.de.yaml"
    _write(schema)
    _write(tmp_path / "map-data.de.tsv")
    _write(tmp_path / "map-data.tsv")  # decoy legacy file, must not be picked
    data_path, delimiter = find_data_path_for_schema(str(tmp_path), str(schema))
    assert data_path == str(tmp_path / "map-data.de.tsv")


def test_find_data_path_csv_fallback(tmp_path):
    schema = tmp_path / "import-schema.fr.yaml"
    _write(schema)
    _write(tmp_path / "map-data.fr.csv")
    data_path, delimiter = find_data_path_for_schema(str(tmp_path), str(schema))
    assert data_path == str(tmp_path / "map-data.fr.csv")
    assert delimiter == ","


def test_find_data_path_missing_raises(tmp_path):
    schema = tmp_path / "import-schema.de.yaml"
    _write(schema)
    with pytest.raises(FileNotFoundError):
        find_data_path_for_schema(str(tmp_path), str(schema))


def test_resolve_map_dir_paths_multi_language(tmp_path):
    org_dir = tmp_path / "myorg"
    map_dir = org_dir / "main-map"
    map_dir.mkdir(parents=True)
    _write(org_dir / "org-setup.yaml")
    _write(map_dir / "import-schema.de.yaml")
    _write(map_dir / "map-data.de.tsv")
    _write(map_dir / "import-schema.en.yaml")
    _write(map_dir / "map-data.en.tsv")

    # No override: resolves to the first language-specific schema (sorted)
    paths = resolve_map_dir_paths(str(map_dir))
    assert paths["schema"] == str(map_dir / "import-schema.de.yaml")
    assert paths["data"] == str(map_dir / "map-data.de.tsv")

    # Explicit override: pairs with the matching language's data file
    paths_en = resolve_map_dir_paths(str(map_dir), schema_path=str(map_dir / "import-schema.en.yaml"))
    assert paths_en["schema"] == str(map_dir / "import-schema.en.yaml")
    assert paths_en["data"] == str(map_dir / "map-data.en.tsv")


def test_find_map_dirs_recognizes_language_specific_schemas(tmp_path):
    org_dir = tmp_path / "myorg"
    map_dir = org_dir / "business-map"
    map_dir.mkdir(parents=True)
    _write(map_dir / "import-schema.en.yaml")
    other_dir = org_dir / "not-a-map"
    other_dir.mkdir()
    assert find_map_dirs(str(org_dir)) == [str(map_dir)]
