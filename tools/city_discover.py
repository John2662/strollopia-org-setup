#!/usr/bin/env python3
"""
Capture City — automated city POI discovery for Strollopia.

Discovers businesses, landmarks, public art, and parks for a target city
using Google Places API (primary) and OpenStreetMap Overpass API (supplementary).
Generates per-language TSV data files and import schemas ready for strollopia_import.py.

Usage:
    python tools/city_discover.py "Innsbruck, Austria" --languages de,en --init
    python tools/city_discover.py "Innsbruck, Austria" --no-photos --maps landmarks,parks
"""

import argparse
import csv
import math
import os
import random
import re
import secrets
import string
import sys
import time
import unicodedata

import requests
import yaml

# ── Constants ──────────────────────────────────────────────────────────────────

GOOGLE_PLACES_BASE = "https://maps.googleapis.com/maps/api/place"
GOOGLE_GEOCODE_BASE = "https://maps.googleapis.com/maps/api/geocode/json"
NOMINATIM_BASE = "https://nominatim.openstreetmap.org/search"
OVERPASS_BASE = "https://overpass-api.de/api/interpreter"

DEFAULT_RADIUS_M = 5000
DEDUP_THRESHOLD_M = 30
OVERPASS_TIMEOUT = 30
PHOTO_MAX_WIDTH = 1200

# Google Places day index → strollopia schedule key
GOOGLE_DAY_KEYS = [
    "hours_sun", "hours_mon", "hours_tue", "hours_wed",
    "hours_thu", "hours_fri", "hours_sat",
]

TSV_COLUMNS = [
    "name", "lat", "lng", "category", "subcategory", "description",
    "phone", "website", "address",
    "hours_mon", "hours_tue", "hours_wed", "hours_thu",
    "hours_fri", "hours_sat", "hours_sun",
    "image_file",
]

# ── Presets ────────────────────────────────────────────────────────────────────

PRESETS = {
    "businesses": {
        "dir_name": "business-map",
        "osm_primary": False,
        "google_types": [
            "restaurant", "cafe", "bar", "bakery", "store", "supermarket",
            "clothing_store", "pharmacy", "bank", "hair_care", "gym",
            "lodging", "gas_station",
        ],
        "osm_tags": [
            ("amenity", "restaurant"), ("amenity", "cafe"), ("amenity", "bar"),
            ("amenity", "pharmacy"), ("amenity", "bank"), ("shop", "*"),
        ],
        "type_to_category": {
            "restaurant":     ("Business", "Restaurant"),
            "cafe":           ("Business", "Cafe"),
            "bar":            ("Business", "Bar"),
            "bakery":         ("Business", "Food"),
            "store":          ("Business", "Shops"),
            "supermarket":    ("Business", "Shops"),
            "clothing_store": ("Business", "Shops"),
            "pharmacy":       ("Business", "Health"),
            "bank":           ("Business", "Finance"),
            "hair_care":      ("Business", "Services"),
            "gym":            ("Business", "Health"),
            "lodging":        ("Business", "Accommodation"),
            "gas_station":    ("Business", "Automotive"),
        },
        "default_category": ("Business", "Business"),
    },
    "landmarks": {
        "dir_name": "landmark-map",
        "osm_primary": False,
        "google_types": [
            "museum", "art_gallery", "library", "church", "city_hall",
            "tourist_attraction", "university", "movie_theater",
            "performing_arts_theater",
        ],
        "osm_tags": [
            ("tourism", "museum"), ("tourism", "attraction"), ("tourism", "gallery"),
            ("historic", "*"), ("amenity", "library"), ("amenity", "theatre"),
            ("amenity", "place_of_worship"),
        ],
        "type_to_category": {
            "museum":                  ("Landmark", "Museum"),
            "art_gallery":             ("Landmark", "Gallery"),
            "library":                 ("Landmark", "Library"),
            "church":                  ("Landmark", "Religious"),
            "place_of_worship":        ("Landmark", "Religious"),
            "city_hall":               ("Landmark", "Civic"),
            "tourist_attraction":      ("Landmark", "Historic"),
            "historic":                ("Landmark", "Historic"),
            "university":              ("Landmark", "Education"),
            "movie_theater":           ("Landmark", "Cultural"),
            "performing_arts_theater": ("Landmark", "Cultural"),
            "theatre":                 ("Landmark", "Cultural"),
        },
        "default_category": ("Landmark", "Landmark"),
    },
    "public-art": {
        "dir_name": "public-art-map",
        "osm_primary": True,
        "google_types": ["tourist_attraction"],
        "osm_tags": [
            ("tourism", "artwork"),
        ],
        "type_to_category": {
            "mural":        ("Art", "Mural"),
            "sculpture":    ("Art", "Sculpture"),
            "statue":       ("Art", "Statue"),
            "installation": ("Art", "Installation"),
        },
        "default_category": ("Art", "Public Art"),
    },
    "parks": {
        "dir_name": "park-map",
        "osm_primary": False,
        "google_types": ["park", "campground", "natural_feature"],
        "osm_tags": [
            ("leisure", "park"), ("leisure", "garden"), ("leisure", "nature_reserve"),
            ("natural", "wood"), ("natural", "water"), ("landuse", "recreation_ground"),
        ],
        "type_to_category": {
            "park":             ("Nature", "Park"),
            "garden":           ("Nature", "Garden"),
            "nature_reserve":   ("Nature", "Reserve"),
            "campground":       ("Nature", "Camping"),
            "natural_feature":  ("Nature", "Natural Feature"),
            "wood":             ("Nature", "Natural Feature"),
            "water":            ("Nature", "Natural Feature"),
        },
        "default_category": ("Nature", "Park"),
    },
}


# ── Slug & Domain Utilities ────────────────────────────────────────────────────

# Characters that NFKD does not decompose to ASCII — map them explicitly.
# Relevant for German (ß), French (œ, æ), Nordic (ø, ð, þ) city names.
_TRANSLITERATE = str.maketrans({
    "ß": "ss", "œ": "oe", "æ": "ae", "ø": "o", "ð": "d", "þ": "th",
    "Æ": "AE", "Ø": "O", "Ð": "D", "Þ": "TH"
})


def slugify(text):
    """Lowercase, strip accents, replace non-alphanumeric runs with hyphens."""
    text = str(text).translate(_TRANSLITERATE)
    text = unicodedata.normalize("NFKD", text)
    text = text.encode("ascii", "ignore").decode("ascii")
    text = text.lower()
    text = re.sub(r"[^a-z0-9]+", "-", text)
    return text.strip("-")


def make_domain(country_code, state, city):
    """Build auto-generated org domain from geocoder components."""
    parts = [country_code.lower(), slugify(state), slugify(city)]
    return "-".join(p for p in parts if p) + ".strollopia.com"


def domain_to_slug(domain):
    """Return directory slug: strip .strollopia.com suffix, else take first component."""
    if domain.endswith(".strollopia.com"):
        return domain[: -len(".strollopia.com")]
    return domain.split(".")[0]


def generate_admin_email(city_name):
    """Generate a per-town admin email: {townname}{4 random digits}@strollopia.com.

    Uses the strollopia.com catch-all. The random digit suffix keeps the
    address from being guessable from the town name alone (e.g. by someone
    at a neighboring town poking at an obvious admin@ address), even though
    the naming pattern itself is public.
    """
    local = slugify(city_name).replace("-", "")
    suffix = "".join(secrets.choice(string.digits) for _ in range(4))
    return f"{local}{suffix}@strollopia.com"


def generate_admin_password(length=16):
    """Generate a random admin password using a cryptographically secure RNG."""
    alphabet = string.ascii_letters + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(length))


# ── Geometry & Deduplication ──────────────────────────────────────────────────

def haversine_m(lat1, lng1, lat2, lng2):
    """Return distance in metres between two lat/lng points."""
    R = 6_371_000
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lng2 - lng1)
    a = (math.sin(dphi / 2) ** 2
         + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2)
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def deduplicate(google_places, osm_places, threshold_m=DEDUP_THRESHOLD_M):
    """Merge Google and OSM place lists, removing near-duplicates.

    When a Google and OSM place are within threshold_m, keep the Google record.
    Also deduplicates within google_places.
    Returns a flat list of place dicts.
    """
    kept = []
    for place in google_places:
        too_close = any(
            haversine_m(place["lat"], place["lng"], k["lat"], k["lng"]) < threshold_m
            for k in kept
        )
        if not too_close:
            kept.append(place)

    osm_google_coords = [(p["lat"], p["lng"]) for p in kept]
    for place in osm_places:
        too_close = any(
            haversine_m(place["lat"], place["lng"], lat, lng) < threshold_m
            for lat, lng in osm_google_coords
        )
        if not too_close:
            kept.append(place)
            osm_google_coords.append((place["lat"], place["lng"]))

    return kept


def dedup_by_place_id(places):
    """Remove places whose Google place_id was already seen earlier in the list.

    Used to merge multiple presets' results into one map: a single Google
    place can carry several `types` (e.g. a well-known cafe tagged as both
    "cafe" and "tourist_attraction"), so two different presets' Nearby
    Search calls can each return it even though their type lists don't
    literally overlap. First occurrence wins. Places without a place_id
    (OSM-sourced) are never considered duplicates of each other here --
    within-preset haversine dedup already handled those.
    """
    seen_ids = set()
    kept = []
    for place in places:
        pid = place.get("_place_id")
        if pid is not None:
            if pid in seen_ids:
                continue
            seen_ids.add(pid)
        kept.append(place)
    return kept


# ── Hours & Description Formatters ────────────────────────────────────────────

def parse_google_hours(periods):
    """Convert Google opening_hours.periods to strollopia schedule format.

    Returns dict with keys hours_mon..hours_sun.
    Values are "F: HH:MM T: HH:MM" or "closed".
    Google day index: 0=Sun, 1=Mon, ..., 6=Sat.
    """
    result = {k: "closed" for k in GOOGLE_DAY_KEYS}
    for period in periods:
        day = period["open"]["day"]
        open_time = period["open"]["time"]
        open_fmt = f"{open_time[:2]}:{open_time[2:]}"
        if "close" not in period:
            close_fmt = "24:00"
        else:
            close_time = period["close"]["time"]
            close_fmt = f"{close_time[:2]}:{close_time[2:]}"
        result[GOOGLE_DAY_KEYS[day]] = f"F: {open_fmt} T: {close_fmt}"
    return result


def build_description(name, summary, address, phone, website):
    """Build HTML description blurb for a POI."""
    if summary:
        html = f"<b>{name}</b> — {summary}<br><i>{address}</i>"
    else:
        html = f"<b>{name}</b><br><i>{address}</i>"
    if phone:
        html += f"<br>Tel: {phone}"
    if website:
        html += f'<br><a href="{website}">{website}</a>'
    return html


# ── Geocoding ──────────────────────────────────────────────────────────────────

def geocode_city(city, api_key):
    """Return geocode result dict for a city string.

    Uses Google Geocoding API if api_key is set, else Nominatim.
    Result: {lat, lng, country_code, state, city, bbox: (south, west, north, east)}
    Calls sys.exit(1) if no results found.
    """
    if api_key:
        resp = requests.get(GOOGLE_GEOCODE_BASE, params={
            "address": city,
            "key": api_key,
        })
        resp.raise_for_status()
        data = resp.json()
        if data.get("status") != "OK" or not data.get("results"):
            print(f"[geocode] No results for {city!r} (status: {data.get('status')})")
            sys.exit(1)
        result = data["results"][0]
        loc = result["geometry"]["location"]
        vp = result["geometry"]["viewport"]
        country_short = next(
            (c["short_name"] for c in result["address_components"]
             if "country" in c["types"]),
            ""
        )
        components = {
            comp_type: comp["long_name"]
            for comp in result["address_components"]
            for comp_type in comp["types"]
        }
        return {
            "lat": loc["lat"],
            "lng": loc["lng"],
            "country_code": country_short.upper(),
            "state": components.get("administrative_area_level_1", ""),
            "city": components.get("locality", city.split(",")[0].strip()),
            "bbox": (
                vp["southwest"]["lat"], vp["southwest"]["lng"],
                vp["northeast"]["lat"], vp["northeast"]["lng"],
            ),
        }
    else:
        resp = requests.get(NOMINATIM_BASE, params={
            "q": city,
            "format": "json",
            "addressdetails": 1,
            "limit": 1,
        }, headers={"User-Agent": "strollopia-city-discover/1.0"})
        resp.raise_for_status()
        data = resp.json()
        if not data:
            print(f"[geocode] No results for {city!r} via Nominatim")
            sys.exit(1)
        item = data[0]
        addr = item.get("address", {})
        bb = item["boundingbox"]   # [south, north, west, east]
        return {
            "lat": float(item["lat"]),
            "lng": float(item["lon"]),
            "country_code": addr.get("country_code", "").upper(),
            "state": addr.get("state", ""),
            "city": addr.get("city") or addr.get("town") or addr.get("village", ""),
            "bbox": (float(bb[0]), float(bb[2]), float(bb[1]), float(bb[3])),
        }


# ── OSM Overpass Discovery ─────────────────────────────────────────────────────

def _build_overpass_query(preset, bbox):
    """Build Overpass QL query for a preset and bounding box."""
    south, west, north, east = bbox
    bbox_str = f"{south},{west},{north},{east}"
    parts = []
    for key, value in preset["osm_tags"]:
        if value == "*":
            parts.append(f'node["{key}"]({bbox_str});')
            parts.append(f'way["{key}"]({bbox_str});')
        else:
            parts.append(f'node["{key}"="{value}"]({bbox_str});')
            parts.append(f'way["{key}"="{value}"]({bbox_str});')
    union = "\n  ".join(parts)
    return f"[out:json][timeout:{OVERPASS_TIMEOUT}];\n(\n  {union}\n);\nout body;\n>;\nout skel qt;"


def discover_osm(preset, bbox, language="en"):
    """Query OSM Overpass for places matching a preset's tags.

    Returns list of normalized place dicts. Skips way/relation elements
    (no direct lat/lon). Falls back to empty list on timeout.
    """
    query = _build_overpass_query(preset, bbox)
    try:
        resp = requests.post(OVERPASS_BASE, data={"data": query},
                             timeout=OVERPASS_TIMEOUT + 5)
        resp.raise_for_status()
        elements = resp.json().get("elements", [])
    except requests.exceptions.Timeout:
        print("  Warning: OSM Overpass timed out — skipping OSM source for this preset")
        return []
    except requests.exceptions.HTTPError as exc:
        print(f"  Warning: OSM Overpass HTTP error ({exc}) — skipping OSM source for this preset")
        return []

    type_map = preset["type_to_category"]
    default_cat = preset["default_category"]
    places = []

    for el in elements:
        if el["type"] != "node":
            continue
        tags = el.get("tags", {})
        name = tags.get(f"name:{language}") or tags.get("name", "")
        if not name:
            continue

        artwork_type = tags.get("artwork_type", "")
        category, subcategory = type_map.get(artwork_type, default_cat)

        places.append({
            "name": name,
            "lat": el["lat"],
            "lng": el["lon"],
            "category": category,
            "subcategory": subcategory,
            "description": "",
            "phone": "",
            "website": "",
            "address": "",
            "hours_mon": "", "hours_tue": "", "hours_wed": "", "hours_thu": "",
            "hours_fri": "", "hours_sat": "", "hours_sun": "",
            "image_file": "",
            "_source": "osm",
            "_place_id": None,
            "_photo_reference": None,
        })

    return places


# ── Google Places Discovery & Enrichment ──────────────────────────────────────

def _google_get(url, params, retries=3):
    """GET with exponential backoff on 429."""
    delay = 1
    resp = None
    for attempt in range(retries):
        resp = requests.get(url, params=params)
        if resp.status_code == 429:
            time.sleep(delay)
            delay *= 2
            continue
        resp.raise_for_status()
        return resp
    if resp is not None:
        resp.raise_for_status()
        return resp
    raise requests.exceptions.ConnectionError(f"_google_get called with retries=0")


def discover_google(preset, center, api_key, language="en"):
    """Query Google Places Nearby Search for a preset.

    Returns list of normalized place dicts (no enrichment yet).
    Returns empty list if api_key is None.
    """
    if not api_key:
        return []

    type_map = preset["type_to_category"]
    default_cat = preset["default_category"]
    places = []
    seen_ids = set()

    for place_type in preset["google_types"]:
        params = {
            "location": f"{center['lat']},{center['lng']}",
            "radius": DEFAULT_RADIUS_M,
            "type": place_type,
            "language": language,
            "key": api_key,
        }
        try:
            while True:
                resp = _google_get(f"{GOOGLE_PLACES_BASE}/nearbysearch/json", params)
                data = resp.json()
                for item in data.get("results", []):
                    pid = item.get("place_id")
                    if not pid:
                        continue
                    if pid in seen_ids:
                        continue
                    seen_ids.add(pid)
                    loc = item["geometry"]["location"]
                    # Prefer category from the item's own types list
                    category, subcategory = default_cat
                    for t in item.get("types", []):
                        if t in type_map:
                            category, subcategory = type_map[t]
                            break
                    photo_ref = None
                    if item.get("photos"):
                        photo_ref = item["photos"][0]["photo_reference"]
                    places.append({
                        "name": item["name"],
                        "lat": loc["lat"],
                        "lng": loc["lng"],
                        "category": category,
                        "subcategory": subcategory,
                        "description": "",
                        "phone": "",
                        "website": "",
                        "address": "",
                        "hours_mon": "", "hours_tue": "", "hours_wed": "", "hours_thu": "",
                        "hours_fri": "", "hours_sat": "", "hours_sun": "",
                        "image_file": "",
                        "_source": "google",
                        "_place_id": pid,
                        "_photo_reference": photo_ref,
                    })
                next_token = data.get("next_page_token")
                if not next_token:
                    break
                time.sleep(2)
                params = {"pagetoken": next_token, "key": api_key}
        except Exception as exc:
            print(f"  Warning: Google Places search failed for type {place_type!r}: {exc}")

    return places


def enrich_place(place, api_key, language="en"):
    """Fetch Place Details and fill address, phone, website, hours, description.

    Returns updated place dict (modifies in place and returns it).
    """
    if not api_key or not place.get("_place_id"):
        return place

    params = {
        "place_id": place["_place_id"],
        "fields": "name,formatted_address,formatted_phone_number,website,opening_hours,editorial_summary",
        "language": language,
        "key": api_key,
    }
    try:
        resp = _google_get(f"{GOOGLE_PLACES_BASE}/details/json", params)
        detail = resp.json().get("result", {})

        place["address"] = detail.get("formatted_address", "")
        place["phone"] = detail.get("formatted_phone_number", "")
        place["website"] = detail.get("website", "")
        summary = detail.get("editorial_summary", {}).get("overview", "")

        hours_data = detail.get("opening_hours", {}).get("periods", [])
        if hours_data:
            parsed = parse_google_hours(hours_data)
            place.update(parsed)

        place["description"] = build_description(
            name=place["name"],
            summary=summary,
            address=place["address"],
            phone=place["phone"],
            website=place["website"],
        )
    except Exception:
        return place

    return place


def download_photo(photo_reference, api_key, dest_path):
    """Download a Google Places photo to dest_path.

    Skips if dest_path already exists. Deletes partial file on error.
    Returns True on success or skip, False on failure.
    """
    if os.path.exists(dest_path):
        return True
    params = {
        "photoreference": photo_reference,
        "maxwidth": PHOTO_MAX_WIDTH,
        "key": api_key,
    }
    try:
        resp = _google_get(f"{GOOGLE_PLACES_BASE}/photo", params)
        with open(dest_path, "wb") as f:
            f.write(resp.content)
        return True
    except Exception as exc:
        if os.path.exists(dest_path):
            os.remove(dest_path)
        print(f"  Warning: photo download failed for {os.path.basename(dest_path)}: {exc}")
        return False


# ── File Writers ──────────────────────────────────────────────────────────────

def write_tsv(places, map_dir, language, force=False):
    """Write places to map-data.<lang>.tsv in map_dir.

    Skips if file exists and force is False.
    """
    tsv_path = os.path.join(map_dir, f"map-data.{language}.tsv")
    if os.path.exists(tsv_path) and not force:
        print(f"  Skipping (exists): {tsv_path}")
        return
    with open(tsv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=TSV_COLUMNS, delimiter="\t",
                                extrasaction="ignore")
        writer.writeheader()
        writer.writerows(places)
    print(f"  Written: {tsv_path} ({len(places)} rows)")


def write_schema(map_dir, language, has_photos, force=False):
    """Write import-schema.<lang>.yaml in map_dir.

    Skips if file exists and force is False.
    card_layout is 'image' when has_photos is True, else 'text'.
    """
    schema_path = os.path.join(map_dir, f"import-schema.{language}.yaml")
    if os.path.exists(schema_path) and not force:
        print(f"  Skipping (exists): {schema_path}")
        return

    content_columns = {
        "rt1": {"column": "description"},
    }
    if has_photos:
        content_columns["i1"] = {"column": "image_file"}

    schema = {
        "card_layout": "image" if has_photos else "text",
        "poi_fields": {"name": "name", "lat": "lat", "lng": "lng"},
        "categories": {"category": "category", "subcategory": "subcategory"},
        "schedule": {
            "monday": "hours_mon",
            "tuesday": "hours_tue",
            "wednesday": "hours_wed",
            "thursday": "hours_thu",
            "friday": "hours_fri",
            "saturday": "hours_sat",
            "sunday": "hours_sun",
        },
        "content_columns": content_columns,
        "options": {
            "skip_existing": True,
            "sleep_between_rows": 1,
            "language": language,
        },
    }
    with open(schema_path, "w", encoding="utf-8") as f:
        f.write("---\n")
        yaml.dump(schema, f, default_flow_style=False, sort_keys=False, allow_unicode=True)
    print(f"  Written: {schema_path}")


# ── org-setup.yaml Writer ─────────────────────────────────────────────────────

def _collect_categories(preset_names):
    """Aggregate category/subcategory pairs from all run presets."""
    categories = {}
    for name in preset_names:
        preset = PRESETS[name]
        for cat, subcat in list(preset["type_to_category"].values()) + [preset["default_category"]]:
            categories.setdefault(cat, [])
            if subcat not in categories[cat]:
                categories[cat].append(subcat)
    return categories


def write_org_setup(org_dir, org_domain, geocode, preset_names, languages, force=False):
    """Write org-setup.yaml with city-app defaults.

    Skips if file exists and force is False.
    """
    yaml_path = os.path.join(org_dir, "org-setup.yaml")
    if os.path.exists(yaml_path) and not force:
        print(f"  Skipping (exists): {yaml_path}")
        return

    city_name = geocode["city"]
    # All presets' POIs are written into one combined map (see run()) so the
    # existing category-filter UI in the embed widget can do the "which
    # type of point" job in one embedded map, instead of splitting business/
    # landmark/art/nature into 4 maps the site can only ever show one of at
    # a time.
    org_maps = {
        # is_public alone isn't enough - the org-policy API's
        # public_org_maps list (what strollopia_import.py resolves map
        # pks from) filters on in_public_viewer_list specifically
        # (see org/views.py). Found by actually importing into a real
        # org: the map existed but was invisible to the import tool.
        "main-map": {"is_public": True, "in_public_viewer_list": True},
    }
    default_map = "main-map"
    default_lang = languages[0] if languages else "en"
    # Must fit core.models.ORG_KEY_LEN (14) in strollopia-api - a longer
    # value throws an unhandled "value too long for type character
    # varying(14)" DataError server-side (found by actually posting an org).
    org_key = "".join(random.choices(string.ascii_letters + string.digits, k=14))

    config = {
        "org_domain_name": org_domain,
        "viewer": f"https://{domain_to_slug(org_domain)}.viewer.strollopia.com",
        "display_name": city_name,
        "tag_line": f"Explore {city_name}",
        "main_admin_name": "Admin",
        "allows_anonymous": True,
        "anonymous_settings": {"period": 3600, "max_anon": 10, "org_key": org_key},
        "map_default_lat": geocode["lat"],
        "map_default_lng": geocode["lng"],
        "restrict_public_map": False,
        "categories": _collect_categories(preset_names),
        "mediatypes": ["richtext", "image"],
        "layouts": {
            "text": ["rt1:richtext"],
            "image": ["rt1:richtext", "i1:image"],
        },
        "org_maps": org_maps,
        "ui_support": {
            "datalogger": "DL",
            "default_language": default_lang,
            # Additional languages beyond the default only - the API's
            # UiPage.generate_categories_page does [default_language] +
            # languages, so including the default here too processes it
            # twice and hits a duplicate-key error server-side.
            "languages": [lang for lang in languages if lang != default_lang],
            "ui_config": {
                "identity": {"app_name": city_name},
                "features": {
                    "enabled_modes": ["home", "viewer"],
                    "start_mode": "home",
                    "allow_anonymous_builder": False,
                    "allow_anonymous_map_creation": False,
                },
                "builder": {
                    "default_target_map": default_map,
                    "show_appender": False,
                    "show_map_designer": False,
                    "show_route_builder": False,
                },
                "viewer": {
                    "default_map_pks": [default_map],
                    "show_routes_link": False,
                },
                "form": {
                    "layout_card": "image",
                    "language": default_lang,
                    "field_key_array": [{"richtext": "rt1"}, {"image": "i1"}],
                },
                "routes": {"speed_presets": [], "point_types": [], "allow_osm_import": False},
                "links": {
                    "terms_url": "", "survey_url": "", "brochure_url": "",
                    "support_url": "", "splash_background_image": "",
                },
                "api": {"upload_max_filesize_mb": 10, "upload_max_dimension_px": 1920},
            },
        },
    }

    # main_admin_email/main_admin_password go in a separate, gitignored
    # sidecar rather than org-setup.yaml itself, so the real admin
    # credentials never end up committed to git (org-setup.yaml is
    # committed; org-setup.secrets.yaml is not -- see .gitignore).
    admin_email = generate_admin_email(city_name)
    admin_password = generate_admin_password()
    secrets_config = {
        "main_admin_email": admin_email,
        "main_admin_password": admin_password,
    }
    secrets_yaml_path = os.path.join(org_dir, "org-setup.secrets.yaml")

    os.makedirs(org_dir, exist_ok=True)
    with open(yaml_path, "w", encoding="utf-8") as f:
        f.write("---\n")
        yaml.dump(config, f, default_flow_style=False, sort_keys=False, allow_unicode=True)
    with open(secrets_yaml_path, "w", encoding="utf-8") as f:
        f.write("---\n")
        yaml.dump(secrets_config, f, default_flow_style=False, sort_keys=False, allow_unicode=True)

    print(f"  Written: {yaml_path}")
    print(f"  Written: {secrets_yaml_path} (gitignored -- real admin email/password)")


def run(city, api_key, domain, languages, preset_names, init, no_photos, force, output_dir):
    """Orchestrate the full discovery pipeline for a city."""
    # 1. Geocode
    print(f"[geocode] {city}")
    geocode = geocode_city(city, api_key)
    print(f"[geocode] → {geocode['lat']:.4f}, {geocode['lng']:.4f} "
          f"({geocode['city']}, {geocode['state']}, {geocode['country_code']})")

    # 2. Resolve domain and org directory (Approach A: slug ≠ domain)
    if not domain:
        domain = make_domain(geocode["country_code"], geocode["state"], geocode["city"])
    print(f"[domain]  {domain}  (Ctrl+C and use --domain to override)\n")

    org_slug = domain_to_slug(domain)
    org_dir = os.path.join(output_dir, org_slug)
    os.makedirs(org_dir, exist_ok=True)

    center = {"lat": geocode["lat"], "lng": geocode["lng"]}
    bbox = geocode["bbox"]

    # All presets discover into one combined map -- see write_org_setup for
    # why (the embed widget can only ever show one Map at a time, but
    # already has a full category filter for showing several types of
    # point within that one map).
    map_dir = os.path.join(org_dir, "main-map")
    media_dir = os.path.join(map_dir, "media")
    os.makedirs(media_dir, exist_ok=True)

    all_places = []
    summary_rows = []

    for preset_name in preset_names:
        preset = PRESETS[preset_name]

        # 3. Discover places
        if preset["osm_primary"] or not api_key:
            print(f"[{preset['dir_name']}] Discovering via OSM...")
            osm_places = discover_osm(preset, bbox, language=languages[0])
            google_places = []
        else:
            print(f"[{preset['dir_name']}] Discovering via Google Places...")
            google_places = discover_google(preset, center, api_key, language=languages[0])
            print(f"[{preset['dir_name']}] Google: {len(google_places)} found")
            print(f"[{preset['dir_name']}] Supplementing with OSM...")
            osm_places = discover_osm(preset, bbox, language=languages[0])

        places = deduplicate(google_places, osm_places)
        print(f"[{preset['dir_name']}] {len(places)} unique places after dedup\n")
        if not places:
            print(f"[{preset['dir_name']}] Warning: zero places found\n")

        summary_rows.append((preset["dir_name"], len(places)))
        all_places.extend(places)

    # 4. Cross-preset dedup: a place can carry several Google `types`, so
    # two different presets' searches can each return it even without
    # identical type lists (see dedup_by_place_id). First preset wins.
    combined_count = len(all_places)
    all_places = dedup_by_place_id(all_places)
    cross_dupes = combined_count - len(all_places)
    if cross_dupes:
        print(f"[main-map] Removed {cross_dupes} cross-preset duplicate(s)\n")

    # 5. Enrich and write per language, into the one combined map
    for language in languages:
        print(f"[main-map/{language}] Enriching {len(all_places)} places...")
        enriched = []
        for i, place in enumerate(all_places, 1):
            p = dict(place)
            p = enrich_place(p, api_key, language)
            # Set image_file from slugified name
            if p.get("_photo_reference") and not no_photos:
                filename = slugify(p["name"]) + ".jpg"
                p["image_file"] = filename
            enriched.append(p)
            if i % 10 == 0 or i == len(all_places):
                print(f"\r[main-map/{language}] {i}/{len(all_places)}", end="", flush=True)
        print()

        # 6. Download photos (once, for first language only)
        has_photos = False
        if not no_photos and api_key and language == languages[0]:
            print("[main-map] Downloading photos...")
            for p in enriched:
                if p.get("_photo_reference") and p.get("image_file"):
                    dest = os.path.join(media_dir, p["image_file"])
                    if download_photo(p["_photo_reference"], api_key, dest):
                        has_photos = True
        elif not no_photos and language == languages[0]:
            # No API key — check if any media already exists
            has_photos = bool(os.listdir(media_dir))
        else:
            has_photos = bool(os.listdir(media_dir))

        # 7. Write TSV and schema
        print(f"[main-map/{language}] Writing files...")
        write_tsv(enriched, map_dir, language, force=force)
        write_schema(map_dir, language, has_photos=has_photos and not no_photos, force=force)

    print()

    # 8. Optionally write org-setup.yaml
    if init:
        print("[org-setup] Writing org-setup.yaml...")
        write_org_setup(org_dir, domain, geocode, preset_names, languages, force=force)

    # 9. Print summary
    print(f"\n✓ Discovery complete: {domain}")
    for preset_dir, count in summary_rows:
        print(f"  {preset_dir:<20} {count:>4} found")
    if cross_dupes:
        print(f"  {'(cross-preset dupes)':<20} {-cross_dupes:>4} removed")
    print(f"  {'main-map (combined)':<20} {len(all_places):>4} POIs  ({', '.join(languages)})")

    print(f"\nNext steps:")
    print(f"  python tools/post_org_setup.py {org_slug}")
    print(f"  python tools/strollopia_import.py {os.path.join(output_dir, org_slug)}/ --all-maps")

    return {
        "org_slug": org_slug,
        "org_dir": org_dir,
        "domain": domain,
        "display_name": geocode["city"],
    }


def main():
    parser = argparse.ArgumentParser(
        description="Discover POI data for a city and generate Strollopia import files.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python tools/city_discover.py "Innsbruck, Austria" --languages de,en --init
  python tools/city_discover.py "Innsbruck, Austria" --maps businesses,landmarks --no-photos
  python tools/city_discover.py "Innsbruck, Austria" --domain innsbruck.example.com --init
""",
    )
    parser.add_argument("city", help='City name passed to geocoder (e.g. "Innsbruck, Austria")')
    parser.add_argument("--api-key", default=os.environ.get("GOOGLE_PLACES_API_KEY"),
                        help="Google Places API key (or set GOOGLE_PLACES_API_KEY env var)")
    parser.add_argument("--domain", default=None,
                        help="Explicit org domain. If omitted, auto-generated from geocoder result.")
    parser.add_argument("--languages", default="en",
                        help="Comma-separated language codes (default: en)")
    parser.add_argument("--maps", default="businesses,landmarks,public-art,parks",
                        help="Comma-separated presets to run (default: all four)")
    parser.add_argument("--init", action="store_true",
                        help="Also generate org-setup.yaml with city defaults")
    parser.add_argument("--no-photos", action="store_true",
                        help="Skip photo downloads")
    parser.add_argument("--force", action="store_true",
                        help="Overwrite existing TSV, schema, and org-setup files")
    parser.add_argument("--output-dir", default="org-data",
                        help="Base output directory (default: org-data)")
    args = parser.parse_args()

    languages = [lang.strip() for lang in args.languages.split(",") if lang.strip()]
    preset_names = [p.strip() for p in args.maps.split(",") if p.strip()]

    if not languages:
        parser.error("--languages must include at least one language code")
    if not preset_names:
        parser.error("--maps must include at least one preset name")
    for name in preset_names:
        if name not in PRESETS:
            parser.error(f"Unknown preset: {name!r}. Choose from: {', '.join(PRESETS)}")

    if not args.api_key:
        print("Warning: No Google Places API key — running in OSM-only mode.")
        print("  Set GOOGLE_PLACES_API_KEY or pass --api-key to enable Google Places.\n")

    run(args.city, args.api_key, args.domain, languages, preset_names,
        args.init, args.no_photos, args.force, args.output_dir)


if __name__ == "__main__":
    main()
