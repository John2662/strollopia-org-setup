"""Tests for the pure logic in fix_valleyartmap_reactive.py (no network)."""
import csv
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'tools'))

from fix_valleyartmap_reactive import build_radius_by_name, build_content_block


def _write_tsv(path, rows):
    fieldnames = ["name", "in_person_radius"]
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, delimiter="\t")
        writer.writeheader()
        writer.writerows(rows)


def test_build_radius_by_name_reads_valid_rows(tmp_path):
    tsv_path = tmp_path / "map-data.tsv"
    _write_tsv(tsv_path, [
        {"name": "Work at the Trestle", "in_person_radius": "50"},
        {"name": "Dominion Atlantic Railroad", "in_person_radius": "500"},
    ])
    assert build_radius_by_name(str(tsv_path)) == {
        "Work at the Trestle": 50,
        "Dominion Atlantic Railroad": 500,
    }


def test_build_radius_by_name_skips_blank_and_invalid(tmp_path):
    tsv_path = tmp_path / "map-data.tsv"
    _write_tsv(tsv_path, [
        {"name": "No Radius", "in_person_radius": ""},
        {"name": "Bad Radius", "in_person_radius": "not-a-number"},
        {"name": "Good Radius", "in_person_radius": "1000"},
    ])
    assert build_radius_by_name(str(tsv_path)) == {"Good Radius": 1000}


def test_build_content_block_shape():
    block = build_content_block(layout_card_pk=7, media_type_pk=3, radius=500)
    assert block == [{
        "language": "en",
        "layout_card": 7,
        "content_array": [{
            "field_key": "a2",
            "media_type": 3,
            "reactive": 500,
        }],
    }]
