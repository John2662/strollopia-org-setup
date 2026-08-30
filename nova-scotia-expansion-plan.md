# Nova Scotia Expansion — Candidate Towns and Go-Live Plan

Existing footprint is entirely Annapolis Valley (Kings County): Kentville,
Wolfville, plus the regional `valleyartmap`. The natural next step is towns
already adjacent to that footprint — easiest sales pitch ("your neighbours
are already on this"), easiest to visit in person, and the discovery
pipeline (`tools/go_live.py`) needs no changes to use.

## Candidate list, phased

**Phase 1 — immediate neighbours (Kings County)**
- **New Minas** — adjacent to Kentville, larger retail/commercial strip.
  Good `businesses` preset fit.
- **Berwick** — small walkable downtown, same county.

**Phase 2 — wider Annapolis Valley**
- **Windsor** — Hants County, "gateway to the valley," historic downtown.
- **Middleton** — Annapolis County, already brands itself "Heart of the
  Valley."
- **Bridgetown** — Annapolis County.
- **Annapolis Royal** — highly tourist-oriented, historic. Strong fit for
  `landmarks`/`public-art` presets specifically, not just `businesses`.

**Phase 3 — South Shore (tests whether the model travels beyond the Valley)**
- **Lunenburg** — UNESCO World Heritage site, dense tourism.
- **Mahone Bay** — known for shops/galleries.
- **Chester**
- **Digby** — fishing/tourism town.

**Phase 4 — larger regional hubs (bigger prize, more data volume/effort)**
- **Truro** — central NS hub.
- **Bridgewater** — South Shore commercial hub.
- **Yarmouth**
- **Antigonish** — university town.

**Note:** `org-data/pictou.orangetag.ca/` already exists in this repo, but
it's an unrelated project — a "Pictou Curbside Audit" tool for a different
organization (PCSSA) with its own contact, not a prior lead for this
tourism-map product. Pictou the town is a genuine, untouched candidate;
`city_discover.py`'s own slug convention (`ca-nova-scotia-pictou`) wouldn't
collide with this existing directory anyway.

Recommendation: run Phase 1 first (2 towns) as a small proof pass on the
whole pipeline end-to-end before committing to the rest — cheap to course-
correct on preset choice, card design, or outreach messaging with just two
towns in flight.

## Per-town go-live procedure

Prerequisite: a `GOOGLE_PLACES_API_KEY` (set as an env var, or pass
`--api-key`). Without one, `city_discover.py` falls back to OSM-only data —
usable, but Google Places gives materially better business coverage
(hours, phone, photos) for a first-impression trial site.

For each town:

```bash
python tools/go_live.py "New Minas, NS" --sites-repo ../strollopia-sites
```

This runs discovery → org creation → import → deploy-script generation in
one command (see `CLAUDE.md` for the full stage breakdown). Concretely:

1. **Discovery** writes `org-data/<slug>/` with one `map-data.<lang>.tsv` +
   `import-schema.<lang>.yaml` pair per preset (default: all four —
   businesses, landmarks, public-art, parks). If a preset comes back noisy
   or irrelevant for a given town (e.g. `parks` for a town with none), it's
   safe to delete that map's directory before continuing — `strollopia_
   import.py --all-maps` only picks up what's actually there.
2. The tool pauses for you to fill in `main_admin_email` in the generated
   `org-setup.yaml` before continuing.
3. **Org creation + import** run for real against whichever server
   `USE_PROD`/`USE_LOCAL_HOST` point at (default dev) — prompts for your
   super-admin credentials.
4. **Deploy script generation** writes `org-data/<slug>/deploy.sh` and
   prints the two Cloudflare-dashboard steps that can't be scripted
   (custom domain attach + DNS CNAME) — same as documented in
   `strollopia-sites/_template/ONBOARDING.md` §7.
5. Run the generated script, complete the two manual dashboard steps, then
   verify:
   ```bash
   python tools/check_live.py <slug>.strollopia.com --map-id <pk>
   ```
6. **Outreach** — the live trial link goes to the town (chamber of
   commerce / municipal contact / a specific downtown business association
   contact if you have one). This step is manual and deliberately not
   automated; see the go-live pipeline design spec's Stage 3 note.

## Card design note

`go_live.py` currently generates its own simple text/image layout per org
(via `city_discover.py`'s built-in layout generation) rather than cloning a
card from the default-org catalog (`basic`, `valleyartmap_legacy`,
`kentvillemurals_legacy`) — that "clone from catalog" step is still the
un-automated part of Stage 3 from the go-live pipeline design spec. For a
first trial this default layout is perfectly serviceable; if a town
converts and wants a more distinctive look, use the new drag-and-drop
Design tab (Layout Card Builder → Design) to build one and swap it in for
that org — no HTML required.

## Tracking

`nova-scotia-expansion-tracking.csv` (repo root) has one row per town above,
pre-populated with `phase`, the `slug`/`domain` `city_discover.py` will
generate for it, and empty columns to fill in as each town moves through
the pipeline: `discovery_date`, `posted_live_date`, `outreach_contact`,
`outreach_date`, `response` (free text, but consider a small fixed
vocabulary like `not_started`/`contacted`/`interested`/`declined`/
`converted` if this gets read by tooling later), and `notes`. Plain CSV
deliberately, so it stays lightweight for the "few dozen manual sells"
phase while being a one-line `csv.DictReader` away from a real tracking
tool if volume ever justifies building one.
