# One-off: ran directly via `python manage.py shell` on prod (2026-10-06),
# bypassing the REST API login - the stored admin password
# (org-setup.yaml's main_admin_password) was stale, rejected with "Mal
# formed user login request". See tools/fix_valleyartmap_reactive.py for
# the reusable REST-API version of this fix, for orgs where credentials
# are current.
#
# Sets PoiContentWrapper.reactive on Valley Art Map's a2 (in-person audio)
# fields, matched by POI name, to the real per-installation GPS-proximity
# radius - values confirmed against the live legacy site (valleyartmap.ca)
# by the customer before this was run. Kept here as a record of what was
# actually applied to prod, not for reuse (the data is org-specific and
# this has already been run).

from content.models import Poi, PoiContentWrapper

ORG_DOMAIN_NAME = 'valleyartmap.strollopia.com'
FIELD_KEY = 'a2'
APPLY = False  # flip to True after reviewing the dry-run output below

RADIUS_BY_NAME = {
    'Work at the Trestle': 50,
    'Dominion Atlantic Railroad': 500,
    'Acadian Deportation Cross': 1000,
    'Disruptor': 1000,
    'The Joy is Almost Too Much to Bear': 50,
    'Dr. Apple': 1000,
    'Fountain of Grand-Pré': 1000,
    'Statue of Evangeline': 1000,
    'The Tide Flows': 50,
    'Indeterminate Tillage': 1000,
    'That You May Live': 1000,
    'Pasture Gate': 500,
    'Harold Lothrop Borden Monument': 1000,
    'Emergency Exit': 1000,
    'Charles Macdonald Concrete House Museum': 1000,
    'Aylesford in Times Gone By': 1000,
    'Untitled Stone Head': 1000,
}

pois = Poi.objects.filter(owning_map__owning_user__owning_org__org_domain_name=ORG_DOMAIN_NAME)
pois_by_name = {p.name: p for p in pois}

matched = 0
unmatched = []
changed = 0
for name, radius in RADIUS_BY_NAME.items():
    poi = pois_by_name.get(name)
    if poi is None:
        unmatched.append(name)
        continue
    matched += 1
    wrappers = PoiContentWrapper.objects.filter(owning_container__owning_poi=poi, field_key=FIELD_KEY)
    if not wrappers.exists():
        print(f'  no {FIELD_KEY} wrapper for "{name}" - skipping')
        continue
    for wrapper in wrappers:
        print(f'  "{name}": reactive {wrapper.reactive} -> {radius}')
        if APPLY:
            wrapper.reactive = radius
            wrapper.save(update_fields=['reactive'])
            changed += 1

print()
print(f'Matched: {matched}/{len(RADIUS_BY_NAME)}')
if unmatched:
    print(f'Unmatched: {unmatched}')
print(f'Applied: {changed}' if APPLY else 'DRY RUN - set APPLY=True and re-run to commit.')
