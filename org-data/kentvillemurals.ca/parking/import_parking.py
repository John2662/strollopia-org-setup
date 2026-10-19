#!/usr/bin/env python3
"""Import Kentville's downtown parking into the business map.

Reuses the Wolfville importer (org-data/strollwolfville.ca/parking/
import_parking.py) with Kentville's data, subcategories and card text:
36 areas (30 two-hour stretches and lots, 6 free all-day lots) and 6
public washrooms. Names already on the map are skipped, so it is safe to
re-run. Server from USE_LOCAL_HOST / USE_PROD (default dev). From the repo
root:

    python org-data/kentvillemurals.ca/parking/import_parking.py --dry-run
    USE_PROD=1 python org-data/kentvillemurals.ca/parking/import_parking.py --dry-run

Dev still has Kentville under its old name; test there with
`--org kentville.strollopia.com`.
"""
import importlib.util
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ORG_DIR = os.path.dirname(HERE)
WOLFVILLE = os.path.join(ORG_DIR, '..', 'strollwolfville.ca', 'parking', 'import_parking.py')

spec = importlib.util.spec_from_file_location('wolfville_import_parking', WOLFVILLE)
base = importlib.util.module_from_spec(spec)
spec.loader.exec_module(base)

base.GEOJSON = os.path.join(HERE, 'kentville-downtown-parking.geojson')
base.SOURCE = 'Source: Town of Kentville, Downtown Parking Map (2025).'
# subcategory -> (category, colour, pin glyph from the shared library)
base.SUBCATEGORIES = {
    '2 Hour Parking': ('Parking', '#0085ca', 'Car'),
    'All Day Parking': ('Parking', '#9aab1f', 'Car'),
    'Public Washroom': ('Visitor Services', '#555555', 'Toilet'),
}


def card_text(props):
    category, street = props['category'], props['street']
    if category == 'Public Washroom':
        first = f"Public washroom: {props['where']}. Open during business hours only."
    elif props.get('lot'):
        what = 'Free all-day parking' if category == 'All Day Parking' else '2-hour parking'
        place = props['name'].split(' - ', 1)[1]
        first = f'{what}: {place}.'
    else:
        first = f'2-hour parking on {street}.'
    if props.get('note'):
        first += f" {props['note']}"
    return f'<p>{first}</p><p>{base.SOURCE}</p>'


base.card_text = card_text

# --org overrides the org domain from org-setup.yaml (for dev's old name).
_load = base.load_org_credentials
_org = None
if '--org' in sys.argv:
    i = sys.argv.index('--org')
    _org = sys.argv[i + 1]
    del sys.argv[i:i + 2]


def load_org_credentials(*args, **kwargs):
    creds = _load(*args, **kwargs)
    if _org:
        creds['org_domain_name'] = _org
    return creds


base.load_org_credentials = load_org_credentials

if __name__ == '__main__':
    if '--map' not in sys.argv:
        sys.argv += ['--map', 'business-map']
    if '--org-dir' not in sys.argv:
        sys.argv += ['--org-dir', ORG_DIR]
    base.main()
