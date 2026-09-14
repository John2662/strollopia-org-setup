"""Tests for generate_marketing_pdf.py"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'tools'))

import csv
import re
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


def test_build_html_includes_features_page(tmp_path):
    '''
    "Why Strollopia?" is a static, org-agnostic features page (no per-org
    data involved) - a lightweight content-presence check is enough here,
    not a check of every bullet's exact wording.
    '''
    org_dir = _make_org_dir(tmp_path)
    from post_org_setup import load_org_config
    config = load_org_config(os.path.join(org_dir, "org-setup.yaml"))

    html = build_html(org_dir, config)

    assert "Why Strollopia?" in html
    # One full-width "Host it your way" lead card (class="feature feature-wide")
    # plus 8 regular half-width cards. re.findall on a word-boundary-safe
    # pattern rather than a plain substring count, since 'class="feature"'
    # doesn't match 'class="feature feature-wide"'.
    assert len(re.findall(r'class="feature(?: feature-wide)?"', html)) == 9
    # CSS also mentions "feature-wide" (the .feature.feature-wide selector),
    # so count only the actual div's class attribute, not the whole document.
    assert html.count('class="feature feature-wide"') == 1
    assert "Business owners manage their own listing" in html
    # The wide card must be the first one, not just present somewhere -
    # that's the whole point of the "move to top" request.
    assert html.index('class="feature feature-wide"') < html.index('class="feature">')


def test_build_html_renders_to_three_pages(tmp_path):
    '''
    Regression test for a real layout bug (2026-09-13): adding the
    analytics-callout screenshot pushed the Getting Started page's
    content into an awkward, mostly-blank third page. Uses weasyprint's
    own render() (no new PDF-reading dependency needed) to count actual
    rendered pages, not just count of page-break divs in the HTML - a
    literal div count wouldn't have caught that bug, since it was
    content overflowing past a page boundary weasyprint decided on, not
    a mismatch in the number of explicit page-break elements.
    '''
    from weasyprint import HTML
    org_dir = _make_org_dir(tmp_path)
    from post_org_setup import load_org_config
    config = load_org_config(os.path.join(org_dir, "org-setup.yaml"))

    html = build_html(org_dir, config)
    document = HTML(string=html, base_url=org_dir).render()

    assert len(document.pages) == 3


def test_build_html_qr_encodes_tracked_path_but_shows_clean_url(tmp_path, monkeypatch):
    '''
    The QR code itself points at /qr-map/ (a strollopia-sites _redirects
    rule, 302 to the site root) so Cloudflare Pages' own per-path
    analytics can report QR-driven scans separately - but the printed,
    human-readable URL text stays the clean root address, since nobody
    should have to type "/qr-map/" by hand.
    '''
    org_dir = _make_org_dir(tmp_path)
    from post_org_setup import load_org_config
    config = load_org_config(os.path.join(org_dir, "org-setup.yaml"))

    import generate_marketing_pdf as gmp
    captured = {}
    original_qr_data_uri = gmp.qr_data_uri

    def spy(url):
        captured["url"] = url
        return original_qr_data_uri(url)

    monkeypatch.setattr(gmp, "qr_data_uri", spy)
    html = gmp.build_html(org_dir, config)

    assert captured["url"] == "https://test-town.strollopia.com/qr-map/"
    url_div = re.search(r'<div class="url">([^<]+)</div>', html)
    assert url_div and url_div.group(1) == "https://test-town.strollopia.com"


def test_build_html_analytics_callout_renders_text_only_without_screenshot(tmp_path, monkeypatch):
    '''
    GA_SCREENSHOT_PATH is a single shared asset (not per-org, since no
    town has its own real GA data - it's opt-in and none has set it up
    yet; the asset itself is a mocked-up illustration, not a real
    dashboard). The callout must still render sensibly when that file
    doesn't exist - pointed at a definitely-missing path here rather
    than relying on the real asset's absence, since a real (mocked)
    screenshot was added 2026-09-14 and this test shouldn't depend on
    whether that file happens to exist on disk.
    '''
    org_dir = _make_org_dir(tmp_path)
    from post_org_setup import load_org_config
    config = load_org_config(os.path.join(org_dir, "org-setup.yaml"))

    import generate_marketing_pdf as gmp
    monkeypatch.setattr(gmp, "GA_SCREENSHOT_PATH", str(tmp_path / "does-not-exist.png"))

    html = gmp.build_html(org_dir, config)

    assert "Want to see who's visiting?" in html
    assert "Organization settings" in html
    # Scoped to the callout div specifically, not the whole page - the QR
    # code elsewhere on the page is legitimately a data:image URI too.
    callout = re.search(r'<div class="analytics-callout">(.*?)</div>', html, re.DOTALL)
    assert callout and "<img" not in callout.group(1)


def test_build_html_analytics_callout_includes_screenshot_when_present(tmp_path, monkeypatch):
    org_dir = _make_org_dir(tmp_path)
    from post_org_setup import load_org_config
    config = load_org_config(os.path.join(org_dir, "org-setup.yaml"))

    fake_screenshot = tmp_path / "fake-ga-screenshot.png"
    _write_tiny_png(fake_screenshot)

    import generate_marketing_pdf as gmp
    monkeypatch.setattr(gmp, "GA_SCREENSHOT_PATH", str(fake_screenshot))

    html = gmp.build_html(org_dir, config)

    assert '<img src="data:image/png;base64,' in html
    assert 'alt="Example Google Analytics dashboard"' in html


def test_generate_marketing_pdf_embeds_photos_not_blank_boxes(tmp_path, monkeypatch):
    '''
    Regression test for a real bug (2026-09-13, found by actually reading
    the generated PDF, not by code inspection): build_html()'s <img src>
    was built from media_dir, a path that already had org_dir baked in
    (needed separately so pick_sample_pois' has_photo() check can open
    the file from the CWD) - weasyprint's HTML(base_url=org_dir) then
    doubled org_dir when resolving that relative src, so every photo
    silently failed to load. write_pdf() doesn't raise on a missing
    image, it just renders a blank box, which is why this went unnoticed
    (a 9-test suite, all passing, existed alongside the live bug).

    This only reproduces with a *relative* org_dir (exactly what main()
    passes: os.path.join(output_dir, org_slug)) - an absolute tmp_path
    used directly as org_dir doesn't trigger it, since Python's own
    os.path.join short-circuits differently than weasyprint's URL-join
    resolution does for two paths that both look absolute. Hence
    monkeypatch.chdir() + a relative org_dir here, and a real end-to-end
    PDF byte check rather than inspecting the HTML string, since the bug
    only manifests in weasyprint's own resolution step.
    '''
    monkeypatch.chdir(tmp_path)
    org_dir_abs = _make_org_dir(tmp_path)
    org_dir_rel = os.path.relpath(org_dir_abs, tmp_path)

    output_path = generate_marketing_pdf(org_dir_rel)

    with open(output_path, "rb") as f:
        pdf_bytes = f.read()
    # A real embedded JPEG carries its SOI marker into the PDF's object
    # stream - a blank/missing-image box does not.
    assert b"\xff\xd8\xff" in pdf_bytes, "no JPEG image data found embedded in the PDF"


def test_generate_marketing_pdf_writes_valid_pdf(tmp_path):
    org_dir = _make_org_dir(tmp_path)
    output_path = generate_marketing_pdf(org_dir)

    assert os.path.exists(output_path)
    with open(output_path, "rb") as f:
        header = f.read(5)
    assert header == b"%PDF-"
