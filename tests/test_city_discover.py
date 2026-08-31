"""Tests for city_discover.py"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'tools'))

import tempfile
import yaml
from unittest.mock import patch, MagicMock
from city_discover import (
    PRESETS, slugify, make_domain, domain_to_slug,
    parse_google_hours, build_description,
    haversine_m, deduplicate, dedup_by_place_id,
    generate_admin_email, generate_admin_password,
    geocode_city, discover_osm,
    discover_google, enrich_place, download_photo,
    write_tsv, write_schema, write_org_setup,
)


def test_presets_keys():
    assert set(PRESETS.keys()) == {"businesses", "landmarks", "public-art", "parks"}


def test_preset_businesses_has_required_fields():
    p = PRESETS["businesses"]
    assert "dir_name" in p
    assert "google_types" in p
    assert "osm_tags" in p
    assert "type_to_category" in p
    assert p["dir_name"] == "business-map"


def test_preset_public_art_osm_primary():
    assert PRESETS["public-art"]["osm_primary"] is True


def test_all_presets_have_dir_name():
    for name, preset in PRESETS.items():
        assert "dir_name" in preset, f"Preset {name!r} missing dir_name"


def test_slugify_basic():
    assert slugify("Innsbruck") == "innsbruck"


def test_slugify_accents():
    assert slugify("Île-de-France") == "ile-de-france"
    assert slugify("Tirol") == "tirol"
    assert slugify("Nova Scotia") == "nova-scotia"


def test_slugify_special_chars():
    assert slugify("São Paulo") == "sao-paulo"
    assert slugify("Düsseldorf") == "dusseldorf"


def test_slugify_collapses_hyphens():
    assert slugify("foo--bar  baz") == "foo-bar-baz"


def test_make_domain():
    assert make_domain("AT", "Tirol", "Innsbruck") == "at-tirol-innsbruck.strollopia.com"
    assert make_domain("CA", "Nova Scotia", "Kentville") == "ca-nova-scotia-kentville.strollopia.com"
    assert make_domain("US", "Texas", "Austin") == "us-texas-austin.strollopia.com"


def test_make_domain_accents():
    assert make_domain("FR", "Île-de-France", "Paris") == "fr-ile-de-france-paris.strollopia.com"


def test_domain_to_slug_strollopia():
    assert domain_to_slug("at-tirol-innsbruck.strollopia.com") == "at-tirol-innsbruck"
    assert domain_to_slug("kentville.strollopia.com") == "kentville"


def test_domain_to_slug_custom():
    assert domain_to_slug("maps.kentville.ca") == "maps"
    assert domain_to_slug("innsbruck.example.com") == "innsbruck"


def test_slugify_german_sharp_s():
    assert slugify("Straße") == "strasse"
    assert slugify("straße") == "strasse"


def test_slugify_ligatures():
    assert slugify("œuvre") == "oeuvre"
    assert slugify("Ærø") == "aero"


def test_generate_admin_email_format():
    email = generate_admin_email("New Minas")
    local, domain = email.split("@")
    assert domain == "strollopia.com"
    assert local[:-4] == "newminas"
    assert local[-4:].isdigit()


def test_generate_admin_email_strips_spaces_and_accents():
    email = generate_admin_email("São Paulo")
    local = email.split("@")[0]
    assert local[:-4] == "saopaulo"


def test_generate_admin_email_is_randomized():
    emails = {generate_admin_email("Kentville") for _ in range(20)}
    # 4-digit suffix means collisions are possible but vanishingly unlikely
    # across 20 draws - this just confirms it isn't a fixed/deterministic value.
    assert len(emails) > 1


def test_generate_admin_password_length_and_charset():
    import string
    password = generate_admin_password()
    assert len(password) == 16
    assert all(c in string.ascii_letters + string.digits for c in password)


def test_generate_admin_password_is_randomized():
    passwords = {generate_admin_password() for _ in range(10)}
    assert len(passwords) == 10


def test_dedup_by_place_id_removes_duplicate():
    places = [
        {"name": "Old Fort", "_place_id": "ChIJshared"},
        {"name": "Old Fort", "_place_id": "ChIJshared"},
    ]
    result = dedup_by_place_id(places)
    assert len(result) == 1


def test_dedup_by_place_id_keeps_first_occurrence():
    places = [
        {"name": "Landmark version", "_place_id": "ChIJshared", "category": "Landmark"},
        {"name": "Art version", "_place_id": "ChIJshared", "category": "Art"},
    ]
    result = dedup_by_place_id(places)
    assert len(result) == 1
    assert result[0]["category"] == "Landmark"


def test_dedup_by_place_id_keeps_places_without_place_id():
    # OSM-sourced places have no place_id - never treated as duplicates here.
    places = [
        {"name": "OSM Mural A", "_place_id": None},
        {"name": "OSM Mural B", "_place_id": None},
    ]
    result = dedup_by_place_id(places)
    assert len(result) == 2


def test_haversine_same_point():
    assert haversine_m(47.27, 11.40, 47.27, 11.40) == 0.0


def test_haversine_known_distance():
    # Innsbruck Hauptbahnhof to Goldenes Dachl — ~700m
    d = haversine_m(47.2631, 11.4006, 47.2683, 11.3937)
    assert 600 < d < 800


def test_deduplicate_keeps_google_when_overlap():
    google = [{"name": "Café A", "lat": 47.2700, "lng": 11.4000, "_source": "google"}]
    osm    = [{"name": "Cafe A", "lat": 47.2700, "lng": 11.4001, "_source": "osm"}]
    result = deduplicate(google, osm, threshold_m=30)
    assert len(result) == 1
    assert result[0]["_source"] == "google"


def test_deduplicate_keeps_both_when_far_apart():
    google = [{"name": "Café A", "lat": 47.2700, "lng": 11.4000, "_source": "google"}]
    osm    = [{"name": "Park B", "lat": 47.2800, "lng": 11.4100, "_source": "osm"}]
    result = deduplicate(google, osm, threshold_m=30)
    assert len(result) == 2


def test_deduplicate_empty_google_keeps_osm():
    osm = [{"name": "Mural X", "lat": 47.27, "lng": 11.40, "_source": "osm"}]
    result = deduplicate([], osm, threshold_m=30)
    assert len(result) == 1
    assert result[0]["_source"] == "osm"


def test_deduplicate_deduplicates_within_google():
    google = [
        {"name": "Café A", "lat": 47.2700, "lng": 11.4000, "_source": "google"},
        {"name": "Café A copy", "lat": 47.2700, "lng": 11.4001, "_source": "google"},
    ]
    result = deduplicate(google, [], threshold_m=30)
    assert len(result) == 1


def test_parse_google_hours_basic():
    periods = [
        {"open": {"day": 1, "time": "0900"}, "close": {"day": 1, "time": "1700"}},
        {"open": {"day": 2, "time": "0900"}, "close": {"day": 2, "time": "1700"}},
    ]
    result = parse_google_hours(periods)
    assert result["hours_mon"] == "F: 09:00 T: 17:00"
    assert result["hours_tue"] == "F: 09:00 T: 17:00"
    assert result["hours_wed"] == "closed"
    assert result["hours_sun"] == "closed"


def test_parse_google_hours_24h():
    # 24-hour place has open period with no close key
    periods = [{"open": {"day": 0, "time": "0000"}}]
    result = parse_google_hours(periods)
    assert result["hours_sun"] == "F: 00:00 T: 24:00"


def test_parse_google_hours_empty():
    result = parse_google_hours([])
    assert all(v == "closed" for v in result.values())
    assert set(result.keys()) == {
        "hours_mon", "hours_tue", "hours_wed", "hours_thu",
        "hours_fri", "hours_sat", "hours_sun",
    }


def test_build_description_full():
    html = build_description(
        name="Café Central",
        summary="A historic Viennese coffee house.",
        address="Herrengasse 14, 1010 Wien",
        phone="+43 1 533 3763",
        website="https://cafecentral.wien",
    )
    assert "<b>Café Central</b>" in html
    assert "A historic Viennese coffee house." in html
    assert "Herrengasse 14" in html
    assert "+43 1 533 3763" in html
    assert "https://cafecentral.wien" in html


def test_build_description_no_summary():
    html = build_description(
        name="Park Platz",
        summary="",
        address="Hauptstraße 1",
        phone="",
        website="",
    )
    assert "<b>Park Platz</b>" in html
    assert "Hauptstraße 1" in html
    assert " — " not in html


def test_build_description_no_phone_or_website():
    html = build_description(
        name="Test Place",
        summary="A place.",
        address="123 Main St",
        phone="",
        website="",
    )
    assert "Tel:" not in html
    assert "href" not in html


GOOGLE_GEOCODE_RESPONSE = {
    "status": "OK",
    "results": [{
        "geometry": {
            "location": {"lat": 47.2692, "lng": 11.4041},
            "viewport": {
                "southwest": {"lat": 47.24, "lng": 11.36},
                "northeast": {"lat": 47.30, "lng": 11.45},
            },
        },
        "address_components": [
            {"types": ["locality"], "long_name": "Innsbruck"},
            {"types": ["administrative_area_level_1"], "long_name": "Tirol"},
            {"types": ["country"], "long_name": "Austria", "short_name": "AT"},
        ],
    }],
}

NOMINATIM_RESPONSE = [{
    "lat": "47.2692",
    "lon": "11.4041",
    "boundingbox": ["47.24", "47.30", "11.36", "11.45"],
    "address": {
        "city": "Innsbruck",
        "state": "Tirol",
        "country_code": "at",
    },
}]


def test_geocode_city_with_google_key():
    with patch("city_discover.requests.get") as mock_get:
        mock_resp = MagicMock()
        mock_resp.json.return_value = GOOGLE_GEOCODE_RESPONSE
        mock_resp.raise_for_status = MagicMock()
        mock_get.return_value = mock_resp

        result = geocode_city("Innsbruck, Austria", api_key="fake-key")

    assert result["lat"] == 47.2692
    assert result["lng"] == 11.4041
    assert result["country_code"] == "AT"
    assert result["state"] == "Tirol"
    assert result["city"] == "Innsbruck"
    assert result["bbox"] == (47.24, 11.36, 47.30, 11.45)


def test_geocode_city_nominatim_fallback():
    with patch("city_discover.requests.get") as mock_get:
        mock_resp = MagicMock()
        mock_resp.json.return_value = NOMINATIM_RESPONSE
        mock_resp.raise_for_status = MagicMock()
        mock_get.return_value = mock_resp

        result = geocode_city("Innsbruck, Austria", api_key=None)

    assert result["lat"] == 47.2692
    assert result["lng"] == 11.4041
    assert result["country_code"] == "AT"
    assert result["city"] == "Innsbruck"
    assert result["state"] == "Tirol"
    assert result["bbox"] == (47.24, 11.36, 47.30, 11.45)


def test_geocode_city_raises_on_no_results():
    with patch("city_discover.requests.get") as mock_get:
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"status": "ZERO_RESULTS", "results": []}
        mock_resp.raise_for_status = MagicMock()
        mock_get.return_value = mock_resp

        try:
            geocode_city("Nonexistent Place XYZ", api_key="fake-key")
            assert False, "Should have raised"
        except SystemExit:
            pass


OVERPASS_RESPONSE = {
    "elements": [
        {
            "type": "node",
            "id": 111,
            "lat": 47.27,
            "lon": 11.40,
            "tags": {
                "name": "Mural am Domplatz",
                "name:de": "Mural am Domplatz",
                "name:en": "Mural at Cathedral Square",
                "tourism": "artwork",
                "artwork_type": "mural",
            },
        },
        {
            "type": "node",
            "id": 222,
            "lat": 47.28,
            "lon": 11.41,
            "tags": {
                "name": "Bronzestatue",
                "tourism": "artwork",
                "artwork_type": "statue",
            },
        },
        {
            "type": "way",
            "id": 333,
            "tags": {"tourism": "artwork"},
        },
    ]
}


def test_discover_osm_public_art():
    bbox = (47.24, 11.36, 47.30, 11.45)
    with patch("city_discover.requests.post") as mock_post:
        mock_resp = MagicMock()
        mock_resp.json.return_value = OVERPASS_RESPONSE
        mock_resp.raise_for_status = MagicMock()
        mock_post.return_value = mock_resp

        places = discover_osm(PRESETS["public-art"], bbox, language="de")

    assert len(places) == 2  # way skipped
    assert places[0]["name"] == "Mural am Domplatz"
    assert places[0]["category"] == "Art"
    assert places[0]["subcategory"] == "Mural"
    assert places[0]["_source"] == "osm"
    assert places[0]["lat"] == 47.27


def test_discover_osm_uses_language_name():
    bbox = (47.24, 11.36, 47.30, 11.45)
    with patch("city_discover.requests.post") as mock_post:
        mock_resp = MagicMock()
        mock_resp.json.return_value = OVERPASS_RESPONSE
        mock_resp.raise_for_status = MagicMock()
        mock_post.return_value = mock_resp

        places = discover_osm(PRESETS["public-art"], bbox, language="en")

    assert places[0]["name"] == "Mural at Cathedral Square"


def test_discover_osm_timeout_returns_empty():
    bbox = (47.24, 11.36, 47.30, 11.45)
    with patch("city_discover.requests.post") as mock_post:
        import requests as req
        mock_post.side_effect = req.exceptions.Timeout()
        places = discover_osm(PRESETS["public-art"], bbox, language="en")
    assert places == []


NEARBY_RESPONSE_PAGE1 = {
    "status": "OK",
    "results": [
        {
            "name": "Café Katzung",
            "geometry": {"location": {"lat": 47.2701, "lng": 11.4012}},
            "place_id": "ChIJabc123",
            "types": ["cafe", "food"],
            "photos": [{"photo_reference": "PHOTO_REF_1", "height": 800, "width": 1200}],
        },
    ],
}

DETAILS_RESPONSE = {
    "status": "OK",
    "result": {
        "name": "Café Katzung",
        "formatted_address": "Hofgasse 2, 6020 Innsbruck",
        "formatted_phone_number": "+43 512 584040",
        "website": "https://cafe-katzung.at",
        "opening_hours": {
            "periods": [
                {"open": {"day": 1, "time": "0800"}, "close": {"day": 1, "time": "1800"}},
            ]
        },
        "editorial_summary": {"overview": "A cosy coffee house near the Hofburg."},
    },
}


def test_discover_google_returns_places():
    center = {"lat": 47.2692, "lng": 11.4041}
    with patch("city_discover.requests.get") as mock_get:
        mock_resp = MagicMock()
        mock_resp.json.return_value = NEARBY_RESPONSE_PAGE1
        mock_resp.raise_for_status = MagicMock()
        mock_get.return_value = mock_resp

        places = discover_google(PRESETS["businesses"], center, api_key="fake", language="en")

    assert len(places) == 1
    assert places[0]["name"] == "Café Katzung"
    assert places[0]["_source"] == "google"
    assert places[0]["_place_id"] == "ChIJabc123"
    assert places[0]["category"] == "Business"
    assert places[0]["subcategory"] == "Cafe"


def test_discover_google_no_api_key_returns_empty():
    center = {"lat": 47.2692, "lng": 11.4041}
    places = discover_google(PRESETS["businesses"], center, api_key=None, language="en")
    assert places == []


def test_enrich_place_fills_fields():
    place = {
        "name": "Café Katzung", "lat": 47.27, "lng": 11.40,
        "category": "Business", "subcategory": "Cafe",
        "description": "", "phone": "", "website": "", "address": "",
        "hours_mon": "", "hours_tue": "", "hours_wed": "", "hours_thu": "",
        "hours_fri": "", "hours_sat": "", "hours_sun": "",
        "image_file": "", "_source": "google",
        "_place_id": "ChIJabc123", "_photo_reference": "PHOTO_REF_1",
    }
    with patch("city_discover.requests.get") as mock_get:
        mock_resp = MagicMock()
        mock_resp.json.return_value = DETAILS_RESPONSE
        mock_resp.raise_for_status = MagicMock()
        mock_get.return_value = mock_resp

        enriched = enrich_place(place, api_key="fake", language="en")

    assert enriched["address"] == "Hofgasse 2, 6020 Innsbruck"
    assert enriched["phone"] == "+43 512 584040"
    assert enriched["website"] == "https://cafe-katzung.at"
    assert enriched["hours_mon"] == "F: 08:00 T: 18:00"
    assert "<b>Café Katzung</b>" in enriched["description"]
    assert "A cosy coffee house" in enriched["description"]


def test_download_photo_skips_existing(tmp_path):
    dest = tmp_path / "existing.jpg"
    dest.write_bytes(b"fake image data")
    result = download_photo("PHOTO_REF", "fake-key", str(dest))
    assert result is True


def test_download_photo_writes_file(tmp_path):
    dest = tmp_path / "new_photo.jpg"
    with patch("city_discover.requests.get") as mock_get:
        mock_resp = MagicMock()
        mock_resp.content = b"\xff\xd8\xff fake jpeg"
        mock_resp.raise_for_status = MagicMock()
        mock_get.return_value = mock_resp

        result = download_photo("PHOTO_REF", "fake-key", str(dest))

    assert result is True
    assert dest.read_bytes() == b"\xff\xd8\xff fake jpeg"


SAMPLE_PLACES = [
    {
        "name": "Café Katzung",
        "lat": 47.2701, "lng": 11.4012,
        "category": "Business", "subcategory": "Cafe",
        "description": "<b>Café Katzung</b>",
        "phone": "+43 512 584040",
        "website": "https://cafe-katzung.at",
        "address": "Hofgasse 2, 6020 Innsbruck",
        "hours_mon": "F: 08:00 T: 18:00",
        "hours_tue": "F: 08:00 T: 18:00",
        "hours_wed": "F: 08:00 T: 18:00",
        "hours_thu": "F: 08:00 T: 18:00",
        "hours_fri": "F: 08:00 T: 18:00",
        "hours_sat": "F: 09:00 T: 16:00",
        "hours_sun": "closed",
        "image_file": "cafe_katzung.jpg",
        "_source": "google", "_place_id": "abc", "_photo_reference": "X",
    }
]


def test_write_tsv_creates_file():
    with tempfile.TemporaryDirectory() as tmpdir:
        write_tsv(SAMPLE_PLACES, tmpdir, language="de")
        tsv_path = os.path.join(tmpdir, "map-data.de.tsv")
        assert os.path.exists(tsv_path)
        with open(tsv_path) as f:
            lines = f.readlines()
        assert lines[0].strip().split("\t")[0] == "name"
        assert "Café Katzung" in lines[1]
        assert "47.2701" in lines[1]


def test_write_tsv_skips_existing_without_force():
    with tempfile.TemporaryDirectory() as tmpdir:
        tsv_path = os.path.join(tmpdir, "map-data.de.tsv")
        with open(tsv_path, "w") as f:
            f.write("existing content")
        write_tsv(SAMPLE_PLACES, tmpdir, language="de", force=False)
        with open(tsv_path) as f:
            assert f.read() == "existing content"


def test_write_tsv_overwrites_with_force():
    with tempfile.TemporaryDirectory() as tmpdir:
        tsv_path = os.path.join(tmpdir, "map-data.de.tsv")
        with open(tsv_path, "w") as f:
            f.write("existing content")
        write_tsv(SAMPLE_PLACES, tmpdir, language="de", force=True)
        with open(tsv_path) as f:
            content = f.read()
        assert "Café Katzung" in content


def test_write_schema_image_layout():
    with tempfile.TemporaryDirectory() as tmpdir:
        write_schema(tmpdir, language="de", has_photos=True)
        schema_path = os.path.join(tmpdir, "import-schema.de.yaml")
        assert os.path.exists(schema_path)
        with open(schema_path) as f:
            schema = yaml.safe_load(f)
        assert schema["card_layout"] == "image"
        assert schema["options"]["language"] == "de"
        assert schema["poi_fields"]["name"] == "name"
        assert "rt1" in schema["content_columns"]
        assert "i1" in schema["content_columns"]


def test_write_schema_text_layout_when_no_photos():
    with tempfile.TemporaryDirectory() as tmpdir:
        write_schema(tmpdir, language="en", has_photos=False)
        with open(os.path.join(tmpdir, "import-schema.en.yaml")) as f:
            schema = yaml.safe_load(f)
        assert schema["card_layout"] == "text"
        assert "i1" not in schema["content_columns"]


def test_write_org_setup_creates_file():
    with tempfile.TemporaryDirectory() as tmpdir:
        geocode = {"lat": 47.2692, "lng": 11.4041,
                   "country_code": "AT", "state": "Tirol", "city": "Innsbruck"}
        write_org_setup(
            org_dir=tmpdir,
            org_domain="at-tirol-innsbruck.strollopia.com",
            geocode=geocode,
            preset_names=["businesses", "landmarks"],
            languages=["de", "en"],
        )
        yaml_path = os.path.join(tmpdir, "org-setup.yaml")
        assert os.path.exists(yaml_path)
        with open(yaml_path) as f:
            config = yaml.safe_load(f)

        assert config["org_domain_name"] == "at-tirol-innsbruck.strollopia.com"
        assert config["viewer"] == "https://at-tirol-innsbruck.viewer.strollopia.com"
        # Must fit core.models.ORG_KEY_LEN (14) in strollopia-api
        assert len(config["anonymous_settings"]["org_key"]) == 14
        assert config["map_default_lat"] == 47.2692
        assert config["display_name"] == "Innsbruck"
        # All presets' POIs are merged into one map, not one map per preset -
        # see write_org_setup's docstring / city_discover.run.
        assert set(config["org_maps"].keys()) == {"main-map"}
        # Both flags required - the org-policy API's public_org_maps list
        # (what strollopia_import.py resolves map pks from) filters on
        # in_public_viewer_list specifically, not is_public.
        assert config["org_maps"]["main-map"] == {"is_public": True, "in_public_viewer_list": True}
        assert config["ui_support"]["ui_config"]["builder"]["default_target_map"] == "main-map"
        assert config["ui_support"]["ui_config"]["viewer"]["default_map_pks"] == ["main-map"]
        assert "Business" in config["categories"]
        assert "Landmark" in config["categories"]
        assert config["ui_support"]["default_language"] == "de"
        # Excludes the default - see test_write_org_setup_languages_excludes_default
        assert config["ui_support"]["languages"] == ["en"]
        # Admin credentials are NOT in org-setup.yaml - they live in the
        # gitignored secrets sidecar (see test_write_org_setup_writes_secrets_sidecar)
        assert "main_admin_email" not in config
        assert "main_admin_password" not in config


def test_write_org_setup_writes_secrets_sidecar():
    with tempfile.TemporaryDirectory() as tmpdir:
        geocode = {"lat": 45.07, "lng": -64.45,
                   "country_code": "CA", "state": "Nova Scotia", "city": "New Minas"}
        write_org_setup(
            org_dir=tmpdir,
            org_domain="ca-nova-scotia-new-minas.strollopia.com",
            geocode=geocode,
            preset_names=["businesses"],
            languages=["en"],
        )
        secrets_path = os.path.join(tmpdir, "org-setup.secrets.yaml")
        assert os.path.exists(secrets_path)
        with open(secrets_path) as f:
            secrets_config = yaml.safe_load(f)

        email = secrets_config["main_admin_email"]
        assert email.split("@")[1] == "strollopia.com"
        assert email.split("@")[0][:-4] == "newminas"
        assert len(secrets_config["main_admin_password"]) == 16


def test_write_org_setup_languages_excludes_default():
    # The API's UiPage.generate_categories_page does [default_language] +
    # languages - including the default in languages too makes it process
    # twice and hit a duplicate-key error server-side (found by actually
    # posting a single-language org and getting an HTTP 500).
    with tempfile.TemporaryDirectory() as tmpdir:
        geocode = {"lat": 45.07, "lng": -64.45,
                   "country_code": "CA", "state": "Nova Scotia", "city": "New Minas"}
        write_org_setup(
            org_dir=tmpdir,
            org_domain="ca-nova-scotia-new-minas.strollopia.com",
            geocode=geocode,
            preset_names=["businesses"],
            languages=["en"],
        )
        with open(os.path.join(tmpdir, "org-setup.yaml")) as f:
            config = yaml.safe_load(f)
        assert config["ui_support"]["default_language"] == "en"
        assert config["ui_support"]["languages"] == []


def test_write_org_setup_skips_existing_without_force():
    with tempfile.TemporaryDirectory() as tmpdir:
        yaml_path = os.path.join(tmpdir, "org-setup.yaml")
        with open(yaml_path, "w") as f:
            f.write("existing: true\n")
        geocode = {"lat": 47.27, "lng": 11.40,
                   "country_code": "AT", "state": "Tirol", "city": "Innsbruck"}
        write_org_setup(tmpdir, "test.strollopia.com", geocode, ["businesses"], ["en"])
        with open(yaml_path) as f:
            assert "existing: true" in f.read()


def test_write_org_setup_overwrites_with_force():
    with tempfile.TemporaryDirectory() as tmpdir:
        yaml_path = os.path.join(tmpdir, "org-setup.yaml")
        with open(yaml_path, "w") as f:
            f.write("existing: true\n")
        geocode = {"lat": 47.27, "lng": 11.40,
                   "country_code": "AT", "state": "Tirol", "city": "Innsbruck"}
        write_org_setup(tmpdir, "test.strollopia.com", geocode, ["businesses"], ["en"], force=True)
        with open(yaml_path) as f:
            config = yaml.safe_load(f)
        assert "org_domain_name" in config


from unittest.mock import patch, MagicMock
from city_discover import run


def test_run_returns_org_slug_domain_and_display_name(tmp_path):
    geocode_result = {
        "lat": 47.2692, "lng": 11.4041,
        "country_code": "AT", "state": "Tirol", "city": "Innsbruck",
        "bbox": (47.24, 11.36, 47.30, 11.45),
    }
    with patch("city_discover.geocode_city", return_value=geocode_result), \
         patch("city_discover.discover_google", return_value=[]), \
         patch("city_discover.discover_osm", return_value=[]):
        result = run(
            city="Innsbruck, Austria", api_key=None, domain=None,
            languages=["en"], preset_names=["parks"],
            init=True, no_photos=True, force=False,
            output_dir=str(tmp_path),
        )

    assert result["org_slug"] == "at-tirol-innsbruck"
    assert result["domain"] == "at-tirol-innsbruck.strollopia.com"
    assert result["display_name"] == "Innsbruck"
    assert result["org_dir"] == str(tmp_path / "at-tirol-innsbruck")


def _place(name, place_id, category, subcategory):
    return {
        "name": name, "lat": 47.27, "lng": 11.40,
        "category": category, "subcategory": subcategory,
        "description": "", "phone": "", "website": "", "address": "",
        "hours_mon": "", "hours_tue": "", "hours_wed": "", "hours_thu": "",
        "hours_fri": "", "hours_sat": "", "hours_sun": "",
        "image_file": "", "_source": "google",
        "_place_id": place_id, "_photo_reference": None,
    }


def test_run_merges_presets_into_single_main_map(tmp_path):
    geocode_result = {
        "lat": 47.2692, "lng": 11.4041,
        "country_code": "AT", "state": "Tirol", "city": "Innsbruck",
        "bbox": (47.24, 11.36, 47.30, 11.45),
    }

    def fake_discover_google(preset, center, api_key, language="en"):
        if preset["dir_name"] == "business-map":
            return [_place("Cafe Landmark", "ChIJshared", "Business", "Cafe")]
        if preset["dir_name"] == "landmark-map":
            # Same real place, also returned by the landmarks search (a
            # cafe can carry a "tourist_attraction" type in Google's data).
            return [_place("Cafe Landmark", "ChIJshared", "Landmark", "Historic")]
        return []

    with patch("city_discover.geocode_city", return_value=geocode_result), \
         patch("city_discover.discover_google", side_effect=fake_discover_google), \
         patch("city_discover.discover_osm", return_value=[]), \
         patch("city_discover.enrich_place", side_effect=lambda p, api_key, language="en": p):
        run(
            city="Innsbruck, Austria", api_key="fake-key", domain=None,
            languages=["en"], preset_names=["businesses", "landmarks"],
            init=False, no_photos=True, force=False,
            output_dir=str(tmp_path),
        )

    org_dir = tmp_path / "at-tirol-innsbruck"
    assert (org_dir / "main-map").is_dir()
    assert not (org_dir / "business-map").exists()
    assert not (org_dir / "landmark-map").exists()

    with open(org_dir / "main-map" / "map-data.en.tsv") as f:
        rows = f.readlines()
    # header + 1 deduped row (both presets returned the same place_id;
    # businesses ran first, so its category wins)
    assert len(rows) == 2
    assert "Business" in rows[1]
    assert "Cafe" in rows[1]
