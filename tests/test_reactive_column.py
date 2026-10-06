"""Tests for the reactive_column feature in strollopia_import.py.

Regression coverage for a real bug: build_content_wrapper() hardcoded
reactive=0 for every content field, silently shipping Valley Art Map's
"in person" audio ungated despite real per-POI in_person_radius values
(50m/500m/1000m, tuned per installation) already sitting in map-data.tsv.
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'tools'))

from strollopia_import import (
    resolve_reactive_value, build_content_wrapper, collect_schema_columns,
)


def test_resolve_reactive_value_reads_configured_column():
    row = {"in_person_radius": "500"}
    mapping = {"column": "in_person_file", "reactive_column": "in_person_radius"}
    assert resolve_reactive_value(row, mapping, "a2") == 500


def test_resolve_reactive_value_defaults_to_zero_when_not_configured():
    row = {"in_person_radius": "500"}
    mapping = {"column": "in_person_file"}  # no reactive_column
    assert resolve_reactive_value(row, mapping, "a2") == 0


def test_resolve_reactive_value_defaults_to_zero_for_bare_string_mapping():
    row = {"in_person_radius": "500"}
    assert resolve_reactive_value(row, "in_person_file", "a2") == 0


def test_resolve_reactive_value_defaults_to_zero_when_blank():
    row = {"in_person_radius": ""}
    mapping = {"column": "in_person_file", "reactive_column": "in_person_radius"}
    assert resolve_reactive_value(row, mapping, "a2") == 0


def test_resolve_reactive_value_defaults_to_zero_when_missing_from_row():
    row = {}
    mapping = {"column": "in_person_file", "reactive_column": "in_person_radius"}
    assert resolve_reactive_value(row, mapping, "a2") == 0


def test_resolve_reactive_value_defaults_to_zero_on_invalid_value():
    row = {"in_person_radius": "not-a-number"}
    mapping = {"column": "in_person_file", "reactive_column": "in_person_radius"}
    assert resolve_reactive_value(row, mapping, "a2") == 0


def test_build_content_wrapper_defaults_reactive_to_zero():
    wrapper = build_content_wrapper(
        field_key="a1", media_type_name="audio", media_type_pk=5, value="teaser.mp3",
    )
    assert wrapper["reactive"] == 0


def test_build_content_wrapper_uses_given_reactive():
    wrapper = build_content_wrapper(
        field_key="a2", media_type_name="richtext", media_type_pk=1, value="", reactive=50,
    )
    assert wrapper["reactive"] == 50


def test_collect_schema_columns_includes_reactive_column():
    schema = {
        "content_columns": {
            "a2": {"column": "in_person_file", "reactive_column": "in_person_radius"},
        }
    }
    assert "in_person_radius" in collect_schema_columns(schema)
    assert "in_person_file" in collect_schema_columns(schema)
