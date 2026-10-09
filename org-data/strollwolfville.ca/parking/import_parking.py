#!/usr/bin/env python3
"""Import Wolfville's downtown parking into an org map.

Reads wolfville-downtown-parking.geojson (made by extract_parking.py and
name_areas.py) and, on the server picked by USE_LOCAL_HOST / USE_PROD
(default: dev):

1. adds any missing subcategories: 1 Hr / 3 Hr / All Day / Accessible
   Parking and Loading Zone under "Parking", Bus Stop under a new
   "Transit" category, each with the colour from the source map;
2. creates the 32 parking areas (POST /api/geo/map-area/), each with a
   linked POI in its subcategory and a text card (create_poi);
3. creates the 34 points (accessible spaces, loading zones, bus stops)
   as ordinary POIs with the same card.

Anything already on the map with the same name is skipped, so it is safe
to re-run. Run from the repo root:

    python org-data/strollwolfville.ca/parking/import_parking.py --dry-run
    python org-data/strollwolfville.ca/parking/import_parking.py
    USE_PROD=1 python org-data/strollwolfville.ca/parking/import_parking.py

To test on another org (credentials from that org's folder):

    python org-data/strollwolfville.ca/parking/import_parking.py \
        --org-dir org-data/climate-stories.strollopia.com --map climate-map

Needs the API's create_poi object form (strollopia-api 51746e50,
2026-10-09).
"""

import argparse
import getpass
import json
import os
import sys

import requests

HERE = os.path.dirname(os.path.abspath(__file__))
ORG_DIR = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ORG_DIR, '..', '..', 'tools'))

from api_client import (  # noqa: E402
    get_api_base_url, get_map_pois, get_org_layout_fields, get_org_policy,
    login, post_poi, print_api_base_url,
)
from strollopia_import import (  # noqa: E402
    build_content_wrapper, get_layout_card_info, get_map_pk_from_policy,
    load_org_credentials,
)

GEOJSON = os.path.join(HERE, 'wolfville-downtown-parking.geojson')
SOURCE = 'Source: Town of Wolfville, Map 23A Downtown Parking (2024-07-26).'

# subcategory name -> (category name, colour). Area colours match the
# source map's legend; point colours match its icons.
SUBCATEGORIES = {
    '1 Hr Parking': ('Parking', '#a4a233'),
    '3 Hr Parking': ('Parking', '#33a8a5'),
    'All Day Parking': ('Parking', '#ea3e82'),
    'Accessible Parking': ('Parking', '#0070ff'),
    'Loading Zone': ('Parking', '#1d75bc'),
    'Bus Stop': ('Transit', '#333333'),
}

POINT_TEXT = {
    'Accessible Parking': 'Accessible parking space near {street}.',
    'Loading Zone': 'Loading zone near {street}.',
    'Bus Stop': 'Bus stop on or near {street}.',
}


def card_text(props):
    category, street = props['category'], props['street']
    if props['kind'] == 'area':
        first = f'{category} near {street}.'
    else:
        first = POINT_TEXT[category].format(street=street)
    return f'<p>{first}</p><p>{SOURCE}</p>'


class Api:
    def __init__(self, token, org_domain_name, dry_run):
        self.base = get_api_base_url()
        self.org = org_domain_name
        self.dry_run = dry_run
        self.headers = {'Authorization': f'Token {token}'}

    def url(self, path):
        return f'{self.base}{path}?org_domain_name={self.org}'

    def get(self, path):
        resp = requests.get(self.url(path), headers=self.headers)
        resp.raise_for_status()
        data = resp.json()
        return data.get('results', data) if isinstance(data, dict) else data

    def post(self, path, payload):
        resp = requests.post(self.url(path), json=payload, headers=self.headers)
        if resp.status_code != 201:
            raise RuntimeError(f'POST {path} {payload.get("name")!r}: '
                               f'HTTP {resp.status_code}: {resp.text[:500]}')
        return resp.json()


def ensure_subcategories(api):
    """Return {subcategory name: pk}, creating what's missing."""
    categories = {c['name']: c for c in api.get('api/org/categories/')}
    pks = {}
    for sub_name, (cat_name, color) in SUBCATEGORIES.items():
        cat = categories.get(cat_name)
        if cat is None:
            print(f'  + category {cat_name}')
            cat = {'id': None, 'name': cat_name, 'sub_categories': []}
            if not api.dry_run:
                cat = api.post('api/org/categories/', {'name': cat_name})
                cat['sub_categories'] = []
            categories[cat_name] = cat
        existing = {s['name']: s['id'] for s in cat.get('sub_categories', [])}
        if sub_name in existing:
            pks[sub_name] = existing[sub_name]
            continue
        print(f'  + subcategory {cat_name} / {sub_name} {color}')
        if api.dry_run:
            pks[sub_name] = None
            continue
        sub = api.post('api/org/subcategories/', {
            'owning_category': cat['id'], 'name': sub_name, 'color': color,
        })
        cat['sub_categories'].append(sub)
        pks[sub_name] = sub['id']
    return pks


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    parser.add_argument('--org-dir', default=ORG_DIR,
                        help='org-data folder of the target org (default: strollwolfville.ca)')
    parser.add_argument('--map', default='downtown', help='org_map_name (default: downtown)')
    parser.add_argument('--card', default='text', help='layout card name (default: text)')
    parser.add_argument('--language', default='en')
    parser.add_argument('--dry-run', action='store_true',
                        help='show what would be created, change nothing')
    parser.add_argument('--email')
    parser.add_argument('--password')
    parser.add_argument('--ask-password', action='store_true',
                        help="prompt for the org admin's password (not echoed)")
    args = parser.parse_args(argv)

    print_api_base_url()
    if args.ask_password:
        args.password = getpass.getpass('Org admin password: ')
    creds = load_org_credentials(os.path.join(args.org_dir, 'org-setup.yaml'),
                                 args.email, args.password)
    org = creds['org_domain_name']
    token = login(creds['main_admin_email'], creds['main_admin_password'], org)
    api = Api(token, org, args.dry_run)

    map_pk = get_map_pk_from_policy(get_org_policy(org), args.map)
    if map_pk is None:
        sys.exit(f'No public org map named {args.map!r} for {org}.')
    card_pk, card_fields = get_layout_card_info(get_org_layout_fields(org), args.card)
    if card_pk is None:
        sys.exit(f'No layout card named {args.card!r} for {org}.')
    text_keys = [k for k, (media, _) in card_fields.items() if media == 'richtext']
    if not text_keys:
        sys.exit(f'Card {args.card!r} has no richtext field.')
    text_key = text_keys[0]
    print(f'Org {org}, map {args.map} (pk {map_pk}), card {args.card} '
          f'(pk {card_pk}, text field {text_key})')

    print('Subcategories:')
    subcats = ensure_subcategories(api)

    existing_areas = {a['name'] for a in api.get('api/geo/map-area/')
                      if a['owning_map'] == map_pk}
    existing_pois = {p['properties']['name'] for p in get_map_pois(token, org)
                     if p['properties'].get('owning_map', map_pk) == map_pk}

    features = json.load(open(GEOJSON))['features']
    created = skipped = 0
    for f in features:
        props = f['properties']
        name = props['name']
        if name in existing_areas or name in existing_pois:
            skipped += 1
            continue
        text = card_text(props)
        if props['kind'] == 'area':
            print(f'  area  {name}')
            payload = {
                'owning_map': map_pk,
                'name': name,
                'description': f'{props["category"]} near {props["street"]}. {SOURCE}',
                'color': props['color'],
                'lat_lng_array': f['geometry']['coordinates'][0],
                'create_poi': {
                    'sub_categories': [subcats[props['category']]],
                    'layout_card_pk': card_pk,
                    'language': args.language,
                    'fields': {text_key: text},
                },
            }
            if not args.dry_run:
                api.post('api/geo/map-area/', payload)
        else:
            print(f'  point {name}')
            media_pk = card_fields[text_key][1]
            poi = {
                'type': 'Feature',
                'geometry': f['geometry'],
                'properties': {
                    'owning_map': map_pk,
                    'map_content': False,
                    'name': name,
                    'allowed_viewers': [],
                    'allowed_editors': [],
                    'allowed_admins': [],
                    'sub_categories': [subcats[props['category']]],
                    'content_block': [{
                        'language': args.language,
                        'layout_card': card_pk,
                        'user_layout_card': None,
                        'social_media_blurb': '',
                        'content_array': [
                            build_content_wrapper(text_key, 'richtext', media_pk, text)
                        ],
                    }],
                },
            }
            if not args.dry_run:
                ok, data = post_poi(poi, token, org)
                if not ok:
                    raise RuntimeError(f'POI {name!r}: {data}')
        created += 1

    verb = 'Would create' if args.dry_run else 'Created'
    print(f'{verb} {created}, skipped {skipped} already on the map.')


if __name__ == '__main__':
    main()
