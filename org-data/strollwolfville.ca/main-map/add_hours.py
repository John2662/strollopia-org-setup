#!/usr/bin/env python3
"""Add opening hours to strollwolfville.ca's live map from this folder's discovery data.

map-data.en.tsv here is a Google Places / OSM discovery set that was never
imported (see the 2026-10-06 marketing-PDF commit), but it has opening hours
for many places that are on the live "downtown" map, which has none. This
copies them across:

- a place matches when its name appears once in the TSV and once on the map
  (case and spacing ignored) and the two pins are within MAX_METRES;
- places that already have hours are left alone;
- each match gets PATCH /api/content/pois/<id>/ with only open_hours.

Dry run by default (no login needed). From the repo root:

    USE_PROD=1 python org-data/strollwolfville.ca/main-map/add_hours.py
    USE_PROD=1 python org-data/strollwolfville.ca/main-map/add_hours.py --apply

--apply asks for the org admin's password (not echoed).
"""
import argparse
import collections
import getpass
import math
import os
import sys

import requests
import yaml

HERE = os.path.dirname(os.path.abspath(__file__))
ORG_DIR = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ORG_DIR, '..', '..', 'tools'))

from api_client import get_api_base_url, get_org_policy, login, print_api_base_url  # noqa: E402
from strollopia_import import load_data, parse_open_hours  # noqa: E402

MAP_NAME = 'downtown'
MAX_METRES = 150


def norm(name):
    return ' '.join((name or '').lower().split())


DAYS = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']


def hours_for(row, schema):
    """The row's hours; Sunday 00:00-23:59 alone means always open.

    The discovery data was written before city_discover.parse_google_hours
    understood Google's always-open period (2026-10-25), so it says Sunday.
    """
    hours = parse_open_hours(row, schema)
    if hours and len(hours) == 1 and hours[0] == {
            'day_of_week': 'Sunday', 'open_time': '00:00', 'close_time': '23:59'}:
        return [{'day_of_week': d, 'open_time': '00:00', 'close_time': '23:59'} for d in DAYS]
    return hours


def metres(lat1, lng1, lat2, lng2):
    dy = (lat2 - lat1) * 111320
    dx = (lng2 - lng1) * 111320 * math.cos(math.radians(lat1))
    return math.hypot(dx, dy)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    parser.add_argument('--apply', action='store_true', help='write the hours (asks for the password)')
    args = parser.parse_args(argv)

    print_api_base_url()
    org_cfg = yaml.safe_load(open(os.path.join(ORG_DIR, 'org-setup.yaml')))
    org = org_cfg['org_domain_name']
    schema = yaml.safe_load(open(os.path.join(HERE, 'import-schema.en.yaml')))
    _, rows = load_data(os.path.join(HERE, 'map-data.en.tsv'))

    maps = [m for m in get_org_policy(org)['public_org_maps'] if m['org_map_name'] == MAP_NAME]
    if not maps:
        sys.exit(f'No public map named {MAP_NAME!r} for {org}.')
    map_pk = maps[0]['map_obj']
    base = get_api_base_url()
    pois = requests.get(f'{base}api/content/maps/{map_pk}/',
                        params={'org_domain_name': org}, timeout=120).json()['pois']

    tsv_count = collections.Counter(norm(r['name']) for r in rows)
    map_by_name = collections.defaultdict(list)
    for p in pois:
        map_by_name[norm(p['name'])].append(p)

    matches, skipped = [], collections.Counter()
    for row in rows:
        hours = hours_for(row, schema)
        if not hours:
            continue
        key = norm(row['name'])
        found = map_by_name.get(key, [])
        if not found:
            skipped['not on the map'] += 1
            continue
        if tsv_count[key] > 1 or len(found) > 1:
            skipped['name not unique'] += 1
            print(f'  skip {row["name"]!r}: name appears more than once')
            continue
        poi = found[0]
        if poi.get('open_hours'):
            skipped['already has hours'] += 1
            continue
        d = metres(float(row['lat']), float(row['lng']),
                   float(poi['latitude']), float(poi['longitude']))
        if d > MAX_METRES:
            skipped['pins too far apart'] += 1
            print(f'  skip {row["name"]!r}: pins {d:.0f} m apart')
            continue
        matches.append((poi, hours, d))

    for poi, hours, d in matches:
        days = ', '.join(f'{h["day_of_week"][:3]} {h["open_time"]}-{h["close_time"]}' for h in hours)
        print(f'  {poi["id"]:>5} {poi["name"]} ({d:.0f} m): {days}')
    print(f'{len(matches)} places to update; skipped: {dict(skipped)}')

    if not args.apply:
        print('Dry run: nothing written. Re-run with --apply.')
        return
    token = login(org_cfg['main_admin_email'], getpass.getpass('Org admin password: '), org)
    headers = {'Authorization': f'Token {token}'}
    done = 0
    for poi, hours, _ in matches:
        payload = {'geometry': {'type': 'Point',
                                'coordinates': [float(poi['longitude']), float(poi['latitude'])]},
                   'properties': {'open_hours': hours}}
        resp = requests.patch(f'{base}api/content/pois/{poi["id"]}/', params={'org_domain_name': org},
                              json=payload, headers=headers, timeout=60)
        if resp.status_code != 200:
            print(f'  FAILED {poi["id"]} {poi["name"]}: HTTP {resp.status_code} {resp.text[:200]}')
            continue
        done += 1
    print(f'Updated {done} of {len(matches)}.')


if __name__ == '__main__':
    main()
