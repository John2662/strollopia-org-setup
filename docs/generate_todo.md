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

## Expected output, so you know what you're looking at

The `Step` column is the **exact command to run**, copy-pasteable as-is
(where one exists — steps 3 and 5 are actions, not shell commands). Long
lines wrap, but never mid-word/mid-slug, so a wrapped command is still
safe to copy in full. The `Status` column is one of:

- **`[done]`** — that step is confirmed complete.
- **`[pending]`** — checked, and it's genuinely not done yet.
- **`[?]`** — couldn't determine either way (see the per-step notes below
  for what causes this on each one) — treat this as "needs a manual look,"
  not as pending.

### A town partway through launch (real output, Annapolis Royal)

```
=== Go-live checklist: ca-nova-scotia-annapolis-royal (ca-nova-scotia-annapolis-royal.strollopia.com) ===

cd /home/john/strollopia_git_hub/strollopia-org-setup
source .env/bin/activate
export USE_PROD=1
-- run those three first; every command below targets prod, needs the
   venv active, and assumes that working directory.

┌─────┬────────────────────┬────────────────────────────────────────────────────────────────────────────┬────────────────────────────┐
│ #   │ Status             │ Step                                                                       │ Who                        │
├─────┼────────────────────┼────────────────────────────────────────────────────────────────────────────┼────────────────────────────┤
│ 1   │ [done]             │ python tools/post_org_setup.py ca-nova-scotia-annapolis-royal              │ You (super-admin login)    │
├─────┼────────────────────┼────────────────────────────────────────────────────────────────────────────┼────────────────────────────┤
│ 2   │ [done]             │ python tools/strollopia_import.py org-data/ca-nova-scotia-annapolis-royal/ │ You, or I can run it       │
│     │ 133 POIs live      │ --all-maps                                                                 │ (reads secrets file)       │
│     │ (expected 133)     │ (no --email/--password needed, reads the secrets file automatically)       │                            │
├─────┼────────────────────┼────────────────────────────────────────────────────────────────────────────┼────────────────────────────┤
│ 3   │ [done]             │ Generate deploy.sh once the map pk is known                                │ I can do this              │
├─────┼────────────────────┼────────────────────────────────────────────────────────────────────────────┼────────────────────────────┤
│ 4   │ [done]             │ bash org-data/ca-nova-scotia-annapolis-royal/deploy.sh                     │ You (Cloudflare/wrangler   │
│     │                    │ (watch for the KV JSON→TOML gotcha, see ONBOARDING.md)                     │ login)                     │
├─────┼────────────────────┼────────────────────────────────────────────────────────────────────────────┼────────────────────────────┤
│ 5   │ [pending]          │ Attach custom domain + create DNS CNAME (Cloudflare dashboard)             │ You (Cloudflare dashboard) │
├─────┼────────────────────┼────────────────────────────────────────────────────────────────────────────┼────────────────────────────┤
│ 6   │ [pending]          │ python tools/check_live.py ca-nova-scotia-annapolis-royal.strollopia.com   │ I can do this              │
└─────┴────────────────────┴────────────────────────────────────────────────────────────────────────────┴────────────────────────────┘

How to do step 5 (Cloudflare dashboard):

Manual steps (Cloudflare dashboard -- need dashboard access or an elevated API token):
  1. Attach custom domain: Workers & Pages -> ca-nova-scotia-annapolis-royal -> Custom domains
     -> Add a domain -> ca-nova-scotia-annapolis-royal.strollopia.com
  2. Create DNS record: strollopia.com zone -> DNS -> Add record
       Type: CNAME   Name: ca-nova-scotia-annapolis-royal   Target: ca-nova-scotia-annapolis-royal.pages.dev
       Proxy status: Proxied
  3. Wait ~1-2 minutes for the certificate, then run:
       python tools/check_live.py ca-nova-scotia-annapolis-royal.strollopia.com
```

Whenever step 5 isn't done yet, its exact instructions print right after
the table automatically (reusing `generate_deploy_script.py`'s own
`print_manual_checklist()`, so the two can never drift apart) — once step
5 is confirmed done, this block disappears from the output.

### A fully launched town (real output, New Minas)

```
=== Go-live checklist: ca-nova-scotia-new-minas (ca-nova-scotia-new-minas.strollopia.com) ===

cd /home/john/strollopia_git_hub/strollopia-org-setup
source .env/bin/activate
export USE_PROD=1
-- run those three first; every command below targets prod, needs the
   venv active, and assumes that working directory.

┌─────┬────────────────────┬────────────────────────────────────────────────────────────────────────────┬────────────────────────────┐
│ #   │ Status             │ Step                                                                       │ Who                        │
├─────┼────────────────────┼────────────────────────────────────────────────────────────────────────────┼────────────────────────────┤
│ 1   │ [done]             │ python tools/post_org_setup.py ca-nova-scotia-new-minas                    │ You (super-admin login)    │
├─────┼────────────────────┼────────────────────────────────────────────────────────────────────────────┼────────────────────────────┤
│ 2   │ [done]             │ python tools/strollopia_import.py org-data/ca-nova-scotia-new-minas/       │ You, or I can run it       │
│     │ 248 POIs live      │ --all-maps                                                                 │ (reads secrets file)       │
│     │ (expected 248)     │ (no --email/--password needed, reads the secrets file automatically)       │                            │
├─────┼────────────────────┼────────────────────────────────────────────────────────────────────────────┼────────────────────────────┤
│ 3   │ [done]             │ Generate deploy.sh once the map pk is known                                │ I can do this              │
├─────┼────────────────────┼────────────────────────────────────────────────────────────────────────────┼────────────────────────────┤
│ 4   │ [done]             │ bash org-data/ca-nova-scotia-new-minas/deploy.sh                           │ You (Cloudflare/wrangler   │
│     │                    │ (watch for the KV JSON→TOML gotcha, see ONBOARDING.md)                     │ login)                     │
├─────┼────────────────────┼────────────────────────────────────────────────────────────────────────────┼────────────────────────────┤
│ 5   │ [done]             │ Attach custom domain + create DNS CNAME (Cloudflare dashboard)             │ You (Cloudflare dashboard) │
├─────┼────────────────────┼────────────────────────────────────────────────────────────────────────────┼────────────────────────────┤
│ 6   │ [done]             │ python tools/check_live.py ca-nova-scotia-new-minas.strollopia.com         │ I can do this              │
└─────┴────────────────────┴────────────────────────────────────────────────────────────────────────────┴────────────────────────────┘
```

### Step-by-step: what each mark actually means

**1. Post org to prod**
- `[done]` — the org exists on prod (`get-org-policy` succeeded).
- `[pending]` — it doesn't. Only state this step can be in; no `[?]`.

**2. Import POI data** — the most detailed step; the message after `--`
tells you exactly what was checked:
| Message | Mark | Meaning |
|---|---|---|
| `org not posted yet` | `[?]` | Step 1 isn't done — nothing to check |
| `no org-setup.yaml found locally` | `[?]` | Missing local file, not an import-progress question |
| `no admin credentials found locally` | `[?]` | No `org-setup.secrets.yaml` next to it |
| `admin login failed (...)` | `[?]` | **The password-drift gotcha above** — live password and the secrets file disagree |
| `could not list POIs (HTTP nnn)` | `[?]` | API call itself failed — check the API is reachable |
| `N POIs live (expected M)`, N ≥ M | `[done]` | Every local row has a live counterpart |
| `N/M POIs live -- import incomplete or in progress` | `[pending]` | Fewer live than expected — either still running, or some rows were skipped (see the `skip_existing` name-only-matching limitation documented in `strollopia_import.py` if the count won't budge on a re-run) |
| `N POIs live` (no `expected M`) | `[done]`/`[pending]` | No local TSV found to compare against — this is just "is anything live at all" |

**3. Generate deploy.sh**
- `[done]` — `org-data/<slug>/deploy.sh` exists on disk.
- `[pending]` — it doesn't yet.

**4. Run deploy.sh (wrangler)**
- `[done]` — `sites/<slug>/` exists locally in the sites repo. This is a
  **heuristic**, not a live check: the directory can exist without ever
  having been pushed. If step 4 says done but step 5/6 say pending, that's
  the likely explanation — the deploy ran locally but wasn't pushed, or
  pushed to the wrong project name.

**5. Attach custom domain + DNS CNAME** and **6. Confirm with
check_live.py**
- Both come from the same single check: does `https://<slug>.strollopia.com/`
  respond 200 with the template's "Open the Map" marker? If yes, both are
  `[done]`; if the request fails or the marker's missing, both are
  `[pending]`. There's no way to tell these two apart from the outside —
  a `[pending]` here could mean the domain isn't attached yet, DNS hasn't
  propagated, or the deploy itself was bad.

### A note on `USE_PROD`

`make todo SITE=<slug>` sets `USE_PROD=1` **only for that one command** —
it's an inline prefix (`USE_PROD=1 python tools/generate_todo.py ...`),
not an export. It won't show up in `echo $USE_PROD` in your shell
afterward, and it doesn't need to — the checklist still genuinely checked
prod. Running the script directly instead of through `make todo`, you do
need `export USE_PROD=1` yourself first (see "Running it" above), or it
defaults to checking dev.

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
