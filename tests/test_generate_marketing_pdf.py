"""Tests for generate_marketing_pdf.py"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'tools'))

import csv
import yaml
from generate_marketing_pdf import (
    load_poi_counts, pick_sample_pois, qr_data_uri,
    _summary_only, build_html, generate_marketing_pdf,
)

TSV_COLUMNS = [
    "name", "lat", "lng", "category", "subcategory", "description",
    "phone", "website", "address",
    "hours_mon", "hours_tue", "hours_wed", "hours_thu",
    "hours_fri", "hours_sat", "hours_sun",
    "image_file",
]


def _row(name, category, subcategory, description="", image_file=""):
    return {
        "name": name, "lat": "45.07", "lng": "-64.45",
        "category": category, "subcategory": subcategory,
        "description": description, "phone": "", "website": "", "address": "",
        "hours_mon": "", "hours_tue": "", "hours_wed": "", "hours_thu": "",
        "hours_fri": "", "hours_sat": "", "hours_sun": "",
        "image_file": image_file,
    }


def _write_tsv(path, rows):
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=TSV_COLUMNS, delimiter="\t")
        writer.writeheader()
        writer.writerows(rows)


def _write_tiny_png(path):
    from PIL import Image
    Image.new("RGB", (4, 4), color="red").save(path)


def test_load_poi_counts_sorted_descending(tmp_path):
    tsv_path = tmp_path / "map-data.en.tsv"
    _write_tsv(tsv_path, [
        _row("A", "Business", "Cafe"),
        _row("B", "Business", "Restaurant"),
        _row("C", "Landmark", "Museum"),
    ])
    counts = load_poi_counts(str(tsv_path))
    assert counts == {"Business": 2, "Landmark": 1}


def test_pick_sample_pois_requires_photo_and_description(tmp_path):
    tsv_path = tmp_path / "map-data.en.tsv"
    media_dir = tmp_path / "media"
    media_dir.mkdir()
    _write_tiny_png(media_dir / "has-photo.jpg")

    _write_tsv(tsv_path, [
        _row("No Photo", "Business", "Cafe", description="<b>No Photo</b> — great place", image_file=""),
        _row("No Description", "Business", "Cafe", description="", image_file="has-photo.jpg"),
        _row("Has Both", "Business", "Cafe", description="<b>Has Both</b> — great place", image_file="has-photo.jpg"),
    ])
    picked = pick_sample_pois(str(tsv_path), str(media_dir))
    assert [row["name"] for row in picked] == ["Has Both"]


def test_pick_sample_pois_prefers_category_diversity(tmp_path):
    tsv_path = tmp_path / "map-data.en.tsv"
    media_dir = tmp_path / "media"
    media_dir.mkdir()
    _write_tiny_png(media_dir / "photo.jpg")

    _write_tsv(tsv_path, [
        _row("Cafe 1", "Business", "Cafe", description="<b>Cafe 1</b> — good coffee", image_file="photo.jpg"),
        _row("Cafe 2", "Business", "Cafe", description="<b>Cafe 2</b> — also good", image_file="photo.jpg"),
        _row("Museum", "Landmark", "Museum", description="<b>Museum</b> — local history", image_file="photo.jpg"),
        _row("Park", "Nature", "Park", description="<b>Park</b> — green space", image_file="photo.jpg"),
    ])
    picked = pick_sample_pois(str(tsv_path), str(media_dir), limit=3)
    categories = {row["category"] for row in picked}
    assert len(picked) == 3
    assert categories == {"Business", "Landmark", "Nature"}


def test_pick_sample_pois_returns_fewer_than_limit_if_not_enough(tmp_path):
    tsv_path = tmp_path / "map-data.en.tsv"
    media_dir = tmp_path / "media"
    media_dir.mkdir()
    _write_tiny_png(media_dir / "photo.jpg")

    _write_tsv(tsv_path, [
        _row("Only One", "Business", "Cafe", description="<b>Only One</b> — good coffee", image_file="photo.jpg"),
    ])
    picked = pick_sample_pois(str(tsv_path), str(media_dir), limit=3)
    assert len(picked) == 1


def test_summary_only_extracts_text_after_em_dash():
    description = "<b>Cafe Katzung</b> — A cosy coffee house.<br><i>Hofgasse 2</i><br>Tel: 555-1234"
    assert _summary_only(description) == "A cosy coffee house."


def test_summary_only_returns_empty_when_no_summary():
    description = "<b>Cafe Katzung</b><br><i>Hofgasse 2</i>"
    assert _summary_only(description) == ""


def test_qr_data_uri_format():
    uri = qr_data_uri("https://example.strollopia.com")
    assert uri.startswith("data:image/png;base64,")
    assert len(uri) > 100


def _make_org_dir(tmp_path):
    org_dir = tmp_path / "test-town"
    map_dir = org_dir / "main-map"
    media_dir = map_dir / "media"
    media_dir.mkdir(parents=True)
    _write_tiny_png(media_dir / "photo.jpg")
    _write_tsv(map_dir / "map-data.en.tsv", [
        _row("Test Cafe", "Business", "Cafe", description="<b>Test Cafe</b> — great coffee", image_file="photo.jpg"),
        _row("Test Museum", "Landmark", "Museum", description="<b>Test Museum</b> — local history", image_file="photo.jpg"),
    ])
    with open(org_dir / "org-setup.yaml", "w") as f:
        yaml.dump({
            "org_domain_name": "test-town.strollopia.com",
            "display_name": "Test Town",
            "tag_line": "Explore Test Town",
        }, f)
    with open(org_dir / "org-setup.secrets.yaml", "w") as f:
        yaml.dump({
            "main_admin_email": "testtown1234@strollopia.com",
            "main_admin_password": "RealPassword123",
        }, f)
    return str(org_dir)


def test_build_html_includes_key_content(tmp_path):
    org_dir = _make_org_dir(tmp_path)
    from post_org_setup import load_org_config
    config = load_org_config(os.path.join(org_dir, "org-setup.yaml"))

    html = build_html(org_dir, config)

    assert "Test Town" in html
    assert "https://test-town.strollopia.com" in html
    assert "testtown1234@strollopia.com" in html
    assert "RealPassword123" in html
    assert "Test Cafe" in html
    assert "great coffee" in html


def test_generate_marketing_pdf_writes_valid_pdf(tmp_path):
    org_dir = _make_org_dir(tmp_path)
    output_path = generate_marketing_pdf(org_dir)

    assert os.path.exists(output_path)
    with open(output_path, "rb") as f:
        header = f.read(5)
    assert header == b"%PDF-"
