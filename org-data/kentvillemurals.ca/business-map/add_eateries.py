#!/usr/bin/env python3
"""Add the eateries listed on kentville.ca/eat but missing from the business map.

S & J's Diner and Tim Hortons (2026-10-20), with the address, phone and hours
from their kentville.ca listing pages and the pin position from the Town's
own /eat/map. Text card only (no photo yet). Names already on the map are
skipped, so it is safe to re-run. From the repo root:

    USE_PROD=1 python org-data/kentvillemurals.ca/business-map/add_eateries.py --dry-run
    USE_PROD=1 python org-data/kentvillemurals.ca/business-map/add_eateries.py
"""
import argparse
import getpass
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ORG_DIR = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ORG_DIR, '..', '..', 'tools'))

from api_client import (  # noqa: E402
    get_map_pois, get_org_layout_fields, get_org_policy, login, post_poi,
    print_api_base_url,
)
from strollopia_import import (  # noqa: E402
    build_content_wrapper, get_layout_card_info, get_map_pk_from_policy,
    load_org_credentials,
)

EATERIES_SUBCATEGORY_ID = 394  # Business > Eateries on kentvillemurals.ca
EATERIES = [
    {
        'name': "S & J's Diner",
        'lng': -64.495207, 'lat': 45.084104,
        'text': ("<b>S &amp; J's Diner</b> — A local diner for breakfast and lunch: "
                 "sandwiches, wraps and diner favourites. Dine in or take out.<br>"
                 "<i>📍 264 Cornwallis St</i> &nbsp;|&nbsp; 📞 902-678-4050"
                 " &nbsp;|&nbsp; 🕖 Daily 7 am to 8 pm"),
    },
    {
        'name': 'Tim Hortons',
        'lng': -64.496755, 'lat': 45.078664,
        'text': ("<b>Tim Hortons</b> — Coffee, baked goods and light lunches. "
                 "Drive-thru and take-out.<br>"
                 "<i>📍 70 Aberdeen St</i> &nbsp;|&nbsp; 📞 902-678-7394"
                 " &nbsp;|&nbsp; 🕕 Daily 6 am to 9 pm"),
    },
]


def main():
    parser = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    parser.add_argument('--map', default='business-map')
    parser.add_argument('--card', default='text')
    parser.add_argument('--dry-run', action='store_true')
    parser.add_argument('--ask-password', action='store_true')
    args = parser.parse_args()

    print_api_base_url()
    password = getpass.getpass('Org admin password: ') if args.ask_password else None
    creds = load_org_credentials(os.path.join(ORG_DIR, 'org-setup.yaml'), None, password)
    org = creds['org_domain_name']
    token = login(creds['main_admin_email'], creds['main_admin_password'], org)

    map_pk = get_map_pk_from_policy(get_org_policy(org), args.map)
    card_pk, card_fields = get_layout_card_info(get_org_layout_fields(org), args.card)
    if map_pk is None or card_pk is None:
        sys.exit(f'map {args.map!r} -> {map_pk}, card {args.card!r} -> {card_pk}')
    text_key = next(k for k, (media, _) in card_fields.items() if media == 'richtext')
    media_pk = card_fields[text_key][1]

    # The live POI list has names only (no map or categories): skip by name
    # across the org; the Eateries subcategory id is from the public map 31.
    names = {p['properties']['name'] for p in get_map_pois(token, org)}
    subcat = EATERIES_SUBCATEGORY_ID
    print(f'Org {org}, map {args.map} (pk {map_pk}), card {args.card} (pk {card_pk}), '
          f'Eateries = {subcat}')

    for e in EATERIES:
        if e['name'] in names:
            print(f'  skip {e["name"]} (already on the map)')
            continue
        print(f'  {"would add" if args.dry_run else "add"} {e["name"]}')
        if args.dry_run:
            continue
        poi = {
            'type': 'Feature',
            'geometry': {'type': 'Point', 'coordinates': [e['lng'], e['lat']]},
            'properties': {
                'owning_map': map_pk, 'map_content': False, 'name': e['name'],
                'allowed_viewers': [], 'allowed_editors': [], 'allowed_admins': [],
                'sub_categories': [subcat],
                'content_block': [{
                    'language': 'en', 'layout_card': card_pk, 'user_layout_card': None,
                    'social_media_blurb': '',
                    'content_array': [
                        build_content_wrapper(text_key, 'richtext', media_pk, e['text'])],
                }],
            },
        }
        ok, data = post_poi(poi, token, org)
        if not ok:
            raise RuntimeError(f'{e["name"]}: {data}')


if __name__ == '__main__':
    main()
