#!/usr/bin/env python3
"""Fix places imported as "open Sundays only" that are really always open.

Before 2026-10-25, city_discover.parse_google_hours read Google's always-open
period (one period, Sunday 00:00, no close) as Sunday only. This finds places
on an org's public maps whose only opening hours are Sunday 00:00-23:59 and
adds Monday to Saturday 00:00-23:59 (PATCH /api/content/pois/<id>/ with
open_hours for the six missing days; Sunday is kept).

Dry run unless --apply. Logs in with the org admin from the org folder's
org-setup.secrets.yaml. From the repo root:

    USE_PROD=1 python tools/fix_always_open.py org-data/ca-nova-scotia-lunenburg
    USE_PROD=1 python tools/fix_always_open.py org-data/ca-nova-scotia-* --apply
"""
import argparse
import os
import sys

import requests

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from api_client import get_api_base_url, get_org_policy, login, print_api_base_url  # noqa: E402
from strollopia_import import load_org_credentials  # noqa: E402

MISSING_DAYS = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday']


def sunday_only_all_day(poi):
    hours = poi.get('open_hours') or []
    return (len(hours) == 1 and hours[0]['day_of_week'] == 'Sunday'
            and str(hours[0]['open_time']).startswith('00:00')
            and str(hours[0]['close_time']).startswith('23:59'))


def fix_org(org_dir, apply):
    creds = load_org_credentials(os.path.join(org_dir, 'org-setup.yaml'))
    org = creds['org_domain_name']
    base = get_api_base_url()
    found = []
    for m in get_org_policy(org)['public_org_maps']:
        pois = requests.get(f'{base}api/content/maps/{m["map_obj"]}/',
                            params={'org_domain_name': org}, timeout=120).json()['pois']
        found += [p for p in pois if sunday_only_all_day(p)]
    print(f'{org}: {len(found)} places open Sundays only')
    if not apply or not found:
        return len(found), 0
    token = login(creds['main_admin_email'], creds['main_admin_password'], org)
    headers = {'Authorization': f'Token {token}'}
    hours = [{'day_of_week': d, 'open_time': '00:00', 'close_time': '23:59'} for d in MISSING_DAYS]
    fixed = 0
    for p in found:
        payload = {'geometry': {'type': 'Point',
                                'coordinates': [float(p['longitude']), float(p['latitude'])]},
                   'properties': {'open_hours': hours}}
        resp = requests.patch(f'{base}api/content/pois/{p["id"]}/', params={'org_domain_name': org},
                              json=payload, headers=headers, timeout=60)
        if resp.status_code == 200:
            fixed += 1
        else:
            print(f'  FAILED {p["id"]} {p["name"]}: HTTP {resp.status_code} {resp.text[:200]}')
    print(f'  fixed {fixed} of {len(found)}')
    return len(found), fixed


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    parser.add_argument('org_dirs', nargs='+', help='org-data folders')
    parser.add_argument('--apply', action='store_true', help='write the hours')
    args = parser.parse_args(argv)
    print_api_base_url()
    total = done = 0
    for d in args.org_dirs:
        n, f = fix_org(d, args.apply)
        total += n
        done += f
    print(f'Total: {total} places' + (f', fixed {done}' if args.apply else ' (dry run)'))


if __name__ == '__main__':
    main()
