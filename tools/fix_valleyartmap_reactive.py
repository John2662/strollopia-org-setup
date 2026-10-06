#!/usr/bin/env python3
"""One-off: apply Valley Art Map's real per-installation in-person audio
proximity radius to the already-imported live POIs.

These 17 POIs were imported before strollopia_import.py supported
reactive_column (see resolve_reactive_value() / the Valley Art Map schema's
a2.reactive_column), so every "in person" audio field's `reactive` is
currently 0 (always unlocked, no GPS-proximity gate) despite map-data.tsv
already carrying a real, per-installation in_person_radius value (50m/500m/
1000m, tuned per piece). New imports pick this up automatically now; this
script is only for the POIs that predate that fix.

Values were confirmed against the live legacy site (valleyartmap.ca) by the
customer as correct before this was run (2026-10-06).

Usage:
    python tools/fix_valleyartmap_reactive.py                 # dry run
    python tools/fix_valleyartmap_reactive.py --apply          # apply for real

Target environment follows api_client's normal USE_PROD/USE_LOCAL_HOST
convention, e.g.:
    USE_PROD=1 python tools/fix_valleyartmap_reactive.py --apply
"""
import argparse
import csv
import os
import sys

from api_client import (
    get_map_poi_pks,
    get_org_layout_fields,
    login,
    patch_poi_content,
    print_api_base_url,
)
from org_config import load_org_config
from strollopia_import import get_layout_card_info

ORG_DIR = os.path.join(os.path.dirname(__file__), '..', 'org-data', 'valleyartmap.strollopia.com')
MAP_DIR = os.path.join(ORG_DIR, 'art-map')
FIELD_KEY = 'a2'
LAYOUT_NAME = 'layout1'
RADIUS_COLUMN = 'in_person_radius'
LANGUAGE = 'en'


def build_radius_by_name(tsv_path):
    """Return {poi_name: radius_metres} for every row with a valid radius."""
    radius_by_name = {}
    with open(tsv_path, newline='', encoding='utf-8') as f:
        for row in csv.DictReader(f, delimiter='\t'):
            raw = row.get(RADIUS_COLUMN, '').strip()
            if not raw:
                continue
            try:
                radius_by_name[row['name']] = int(float(raw))
            except ValueError:
                continue
    return radius_by_name


def build_content_block(layout_card_pk, media_type_pk, radius):
    """Build the minimal content_block payload to patch just a2's reactive."""
    return [{
        'language': LANGUAGE,
        'layout_card': layout_card_pk,
        'content_array': [{
            'field_key': FIELD_KEY,
            'media_type': media_type_pk,
            'reactive': radius,
        }],
    }]


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--apply', action='store_true',
                        help='Actually PATCH. Without this, only prints the plan.')
    args = parser.parse_args(argv)

    print_api_base_url()

    config = load_org_config(os.path.join(ORG_DIR, 'org-setup.yaml'))
    org_domain_name = config['org_domain_name']

    radius_by_name = build_radius_by_name(os.path.join(MAP_DIR, 'map-data.tsv'))
    print(f'{len(radius_by_name)} installations with a radius in map-data.tsv\n')

    token = login(config['main_admin_email'], config['main_admin_password'], org_domain_name)

    org_layouts = get_org_layout_fields(org_domain_name)
    layout_card_pk, layout_fields = get_layout_card_info(org_layouts, LAYOUT_NAME)
    if layout_card_pk is None or layout_fields is None or FIELD_KEY not in layout_fields:
        print(f'ERROR: could not resolve layout "{LAYOUT_NAME}" field "{FIELD_KEY}" from org layouts.')
        return 1
    _media_type_name, media_type_pk = layout_fields[FIELD_KEY]

    pk_by_name = get_map_poi_pks(token, org_domain_name)

    matched = 0
    unmatched = []
    applied = 0
    failed = []
    for name, radius in radius_by_name.items():
        pk = pk_by_name.get(name)
        if pk is None:
            unmatched.append(name)
            continue
        matched += 1
        content_block = build_content_block(layout_card_pk, media_type_pk, radius)

        if args.apply:
            success, data = patch_poi_content(pk, content_block, token, org_domain_name)
            if success:
                applied += 1
                print(f'  OK   {name!r} (pk={pk}) -> reactive={radius}')
            else:
                failed.append((name, data))
                print(f'  FAIL {name!r} (pk={pk}): {data}')
        else:
            print(f'  WOULD SET {name!r} (pk={pk}) -> reactive={radius}')

    print()
    print(f'Matched: {matched}/{len(radius_by_name)}')
    if unmatched:
        print(f'Unmatched (no live POI with this name): {unmatched}')
    if args.apply:
        print(f'Applied: {applied}, Failed: {len(failed)}')
    else:
        print('Dry run only -- re-run with --apply to commit.')

    return 1 if (unmatched or failed) else 0


if __name__ == '__main__':
    sys.exit(main())
