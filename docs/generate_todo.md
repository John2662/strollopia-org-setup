# generate_todo.py — go-live checklist

Shows which steps of launching a town are already done and which remain,
by checking real state (prod org, imported data, local site files, live
domain) instead of assuming a fresh town. Safe to re-run at any point.

## Running it

From `strollopia-org-setup`, against prod:

```bash
export USE_PROD=1
python tools/generate_todo.py ca-nova-scotia-annapolis-royal
```

Or from `strollopia-sites`, via the Makefile wrapper (defaults to prod):

```bash
make todo SITE=ca-nova-scotia-annapolis-royal
```

### Alternative: country/province/town instead of the slug

```bash
python tools/generate_todo.py --country CA --province "Nova Scotia" --town "Annapolis Royal"
```

This composes the slug the same way `city_discover.py`'s own `make_domain()`
does (see below) and is equivalent to typing the slug directly for the
common case. **The slug form is the authoritative one** — if a town was
originally discovered with a custom `--domain` override in
`city_discover.py` (for a name that doesn't fit the standard pattern), its
real directory name won't match this composition, and only the slug form
will find it. When in doubt, use the slug.

## Parameters

| Parameter | Required | Notes |
|---|---|---|
| `org_slug` (positional) | One of this or the three below | e.g. `ca-nova-scotia-annapolis-royal` — the directory name under `org-data/` |
| `--country` | With `--province`/`--town` | e.g. `CA` |
| `--province` | With `--country`/`--town` | e.g. `Nova Scotia` |
| `--town` | With `--country`/`--province` | e.g. `Annapolis Royal` |
| `--output-dir` | No (default `org-data`) | Base directory for org data |
| `--sites-repo` | No (default `../strollopia-sites`) | Path to a strollopia-sites checkout, to check whether the site directory exists locally |

## What each step checks

1. **Org posted to prod** — `GET /api/org/org-policy/`. Done if the org exists.
2. **Data imported** — logs in with the credentials from the org's
   `org-setup.secrets.yaml` (no prompt needed) and compares the live POI
   count against the local TSV's row count. Shows `[?]` rather than
   pending/done if the org isn't posted yet, or if login fails (that
   usually means the live password and the secrets file have drifted —
   see the `set_user_password` Django admin gotcha below).
3. **`deploy.sh` generated** — checked by file existence in `org-data/<slug>/`.
4. **`wrangler` deploy run** — checked by whether `sites/<slug>/` exists
   locally in the sites repo. A local-existence heuristic, not a live
   check — the site could exist locally but not be pushed.
5. **Custom domain + DNS attached** — inferred from whether the site
   responds live at its `https://<slug>.strollopia.com/` domain.
6. **Live and correctly wired** — same live check as step 5; if the site
   responds with the template marker, both are considered done.

A quick note on the password-drift gotcha mentioned in step 2: if
`set_user_password` was ever used in Django admin to reset an org admin's
password directly (bypassing `org-setup.secrets.yaml`), the secrets file
and the live password can go out of sync. When that happens, step 2 shows
`[?]` with an "admin login failed" detail rather than guessing — update
the secrets file to match whatever was actually set, or reset the live
password to match the file, and re-run.

## How the town's location actually reaches Google

This tool **never talks to Google** — it only checks state after the
fact. Worth being precise about where the real Google calls happen,
since it's easy to assume `--country`/`--province`/`--town` here feed
into that, and they don't.

The actual geocoding happens in `city_discover.py`, and it's a two-stage
process against two different Google products:

1. **Geocoding API (once per town).** `city_discover.py`'s CLI takes a
   single free-text `city` argument — e.g. `"Annapolis Royal, NS"` — not
   separate country/province/town fields. `geocode_city()` sends that
   exact string as-is to Google's Geocoding API
   (`GET https://maps.googleapis.com/maps/api/geocode/json?address=<city>&key=<api_key>`).
   Google resolves it into a single `lat`/`lng` point, a viewport bounding
   box, and structured `address_components`. `city_discover.py` then
   pulls `country_code`, `state`, and `city` out of **Google's own parsed
   response** — not the raw input string — and uses those to build the
   org domain via `make_domain(country_code, state, city)`. That's the
   exact origin of a slug like `ca-nova-scotia-annapolis-royal`.

2. **Places API (many times per town, after step 1).** Actually
   discovering POIs (`discover_google()`) calls Google Places' Nearby
   Search endpoint using **only** the resolved `lat`/`lng` as a `location`
   center point plus a fixed radius (5km by default) — never a text
   address again. Every business/landmark/park search for that town
   revolves around that one resolved point.

So `generate_todo.py`'s `--country`/`--province`/`--town` are a
convenience for *re-deriving* a slug that should match what Google's
geocoding *already produced* during discovery — they're not a new input
to Google, and there's no guarantee they'll reconstruct the slug exactly
if the original discovery run's geocoding resolved slightly different
component names than what gets typed here. The `org_slug` form sidesteps
that entirely by just naming the real directory.
