# Launching kentvillemurals.ca and climate-stories.ca on Production

Both orgs have complete, ready-to-import data already sitting in this repo.
Verified against prod's public API on 2026-08-29: **neither org currently
exists on prod** (`public_org_maps` comes back empty for both), so both need
the full backend post + import, not just a fix-up.

| Org | Maps | Rows | Media files |
|---|---|---|---|
| `kentville.strollopia.com` | `mural-map`, `business-map` | 26, 167 | 26, 165 |
| `climate-stories.strollopia.com` | `climate-map` | 27 | 13 |

This is two independent tracks per org — backend data, then frontend site —
using the tools already built this session (`prod-org-setup.md` for the
backend; `strollopia-sites/_template`'s wrapper-page pattern for the
frontend, applied by hand since these sites already exist and only need
their map wired up, not a fresh `_template` copy).

## Part A — Backend (repeat for each org)

Follow `prod-org-setup.md` in full for each org, with these specifics:

1. **Replace the placeholder password first.** Both `org-setup.yaml` files
   currently have `main_admin_password: changeme123` — generate a real
   password and update the file before posting (a stale placeholder in a
   file that gets committed to git is not itself a security problem since
   nothing depends on it being secret until it's live, but don't post it to
   prod as-is).
   ```bash
   python tools/org_yaml_wizard.py --edit org-data/kentville.strollopia.com/org-setup.yaml
   python tools/org_yaml_wizard.py --edit org-data/climate-stories.strollopia.com/org-setup.yaml
   ```
2. **Post to prod** (prompts for your super-admin credentials, not the org's):
   ```bash
   export USE_PROD=1
   python tools/post_org_setup.py kentville.strollopia.com
   python tools/post_org_setup.py climate-stories.strollopia.com
   ```
   Read the post-creation login check output carefully — per
   `prod-org-setup.md`'s documented gotcha, if either `main_admin_email` was
   ever used before under that exact org domain, the account keeps its old
   password even though posting reports success.
3. **Import the data:**
   ```bash
   python tools/strollopia_import.py org-data/kentville.strollopia.com/ --all-maps
   python tools/strollopia_import.py org-data/climate-stories.strollopia.com/ --all-maps
   ```
   Run `--dry-run` first if you want to see the payloads without posting.
4. **Get the real map pks** — needed for Part B. After import, this
   returns them directly:
   ```bash
   curl -s "https://prod.strollopia.com/api/org/org-policy/?org_domain_name=kentville.strollopia.com" | python3 -m json.tool
   curl -s "https://prod.strollopia.com/api/org/org-policy/?org_domain_name=climate-stories.strollopia.com" | python3 -m json.tool
   ```
   Look at `public_org_maps` for each `org_map_name` → `map_obj` (the pk).

## Part B — Frontend (repeat for each site, in `strollopia-sites`)

Both `sites/kentvillemurals-ca/` and `sites/climate-stories-ca/` already
exist as deployed Cloudflare Pages projects (both have Makefile deploy
targets) — this is *not* a fresh `_template` onboarding. What's missing in
both, identically:
- No `maps/<id>/` wrapper page exists yet.
- `index.html` still links to the old legacy map site in 3 places
  (`https://maps.kentvillemurals.ca` / `https://maps.climate-stories.ca`).
- `admin.html`'s `MAP_ID` is still `null`.

For **kentvillemurals-ca**, use the `mural-map` pk (the site's own branding
is murals-specific; `business-map` exists but isn't wired to this site —
treat that as a separate, later decision, not part of this launch).

For **climate-stories-ca**, use the `climate-map` pk (its only map).

Steps, per site:

1. **Create the wrapper page** from the template, substituting the real pk
   and site name:
   ```bash
   cp -r _template/maps/REPLACE_MAP_ID sites/kentvillemurals-ca/maps/<MURAL_MAP_PK>
   sed -i "s/REPLACE_MAP_ID/<MURAL_MAP_PK>/g; s/Your Site Name/Kentville Murals/g" \
     sites/kentvillemurals-ca/maps/<MURAL_MAP_PK>/index.html
   ```
   (repeat for climate-stories-ca with its own pk and "Climate Stories")

2. **Fix the three legacy links** in `index.html` — replace
   `https://maps.kentvillemurals.ca` (or `https://maps.climate-stories.ca`)
   with `/maps/<pk>` in all three occurrences (lines 21, 28, 58 as of this
   writing).

3. **Wire up `admin.html`:**
   ```bash
   sed -i "s/const MAP_ID      = null;.*/const MAP_ID      = <pk>;/" sites/kentvillemurals-ca/admin.html
   sed -i "s/const MAP_ID      = null;.*/const MAP_ID      = <pk>;/" sites/climate-stories-ca/admin.html
   ```

4. **Deploy:**
   ```bash
   make deploy-kentvillemurals-ca
   make deploy-climate-stories-ca
   ```

5. **Verify live:** open `https://kentvillemurals.ca` (or whatever the
   live custom domain is — check the Cloudflare Pages project's Custom
   Domains tab if unsure) and confirm "Open the Map" now loads the new
   embed, not the old legacy site.

## Order of operations

Part A must fully complete (map pks known) before Part B starts, but the
two orgs are otherwise fully independent — do kentvillemurals end-to-end,
then climate-stories, or interleave, whichever is easier to track.
