# Go-Live Pipeline — Design Spec

## Purpose

Today, turning a town into a live Strollopia trial site is a manual, multi-hour
process spread across two repos and a Cloudflare dashboard, even though most of
the hard parts already exist as working tools. The goal of this project is a
single orchestrated pipeline that takes "a town" (or an org-supplied POI list)
to "a live trial site on a `*.strollopia.com` subdomain, verified working,"
so we can sell a few dozen towns manually before investing in a marketing site
and campaign.

This is **sub-project B** of the larger go-live vision (see prior discussion).
Sub-project A (Google-tools business discovery) and most of sub-project C
(domain transition) already exist; this spec covers wiring them together and
building the deploy-and-verify leg that doesn't exist yet.

## Scope

**In scope:**
- Reconciling `city_discover.py` (currently stranded in an abandoned local
  clone, `strollopia-clean`) into `strollopia-org-setup`, the repo that's
  actually used for real customer onboarding.
- A new orchestrator, `tools/go_live.py`, sequencing discovery → org creation
  → data import → deploy-script generation → live-check.
- Deploy-script generation for the **simple map path** only (Cloudflare Pages
  + the `strollopia-sites` `_template`), per Approach B: automate the data
  layer fully, generate (don't execute) the Cloudflare/site commands for
  human review and execution.
- An HTTP-level live-check confirming the deployed trial site responds and
  the map embed loads.
- Two forward-looking seams, stubbed but not implemented:
  - `--path {map,pwa}` — deploy target. Only `map` is implemented; `pwa`
    stops cleanly after data provisioning with a clear "finish manually via
    strollopia_pwa" message.
  - `--source {google,template}` — POI data source. Only `google` (via
    `city_discover.py`) is implemented; `template` stops cleanly, pointing at
    a not-yet-built Excel/CSV template path.
- Threading `city_discover.py`'s existing `--languages` flag through
  `go_live.py` unchanged (it's already multi-language capable — one TSV +
  schema pair per language) so multi-language POI data isn't blocked later
  by this plan's own CLI surface.

**Out of scope (explicitly deferred):**
- Localizing the trial site itself (`_template`'s `index.html`/`admin.html`
  copy) and the deploy-script/live-check messaging — stays English-only for
  this phase. The API's map data model and the PWA already handle
  multi-language content; when the simple-map template needs this, look at
  reusing whichever mechanism they use for language-scoped content/strings
  rather than inventing a third approach.
- PWA deploy automation (Vercel + data_logger/strollopia_pwa setup).
- The org-supplied Excel/CSV template itself — including the eventual
  requirement that its columns be derived from a chosen `LayoutCard`'s
  `layout_field` (mirroring how `import-schema.yaml`'s `content_columns`
  already maps arbitrary column names to field keys). Noted as a design
  constraint for whoever builds it later; not designed here.
- Cloudflare API automation for custom-domain attachment and DNS record
  creation — these remain manual dashboard steps (DNS specifically needs a
  `zone:write`-scoped API token we don't currently hold).
- Sub-project C's "generic multi-org admin at `map-admin.strollopia.com`"
  idea — org_domain_name transition itself is already built and tested; the
  admin portal is a future idea, not designed here. Note for whoever designs
  it: `strollopia-native`'s `screens/OrgPickerScreen.js` already implements
  the multi-org login/selection workflow (email+password resolving to a list
  of orgs, user picks one) against the API, which already handles this on
  the backend — that flow should be reused rather than rebuilt.

## Repo Reconciliation

`strollopia-clean` and `strollopia-org-setup` are two local clones of the
same GitHub repo (`John2662/strollopia-org-setup`) that diverged after a
shared commit (`68de7f9`) on 2026-06-03. `strollopia-clean` was never pushed;
it's where `city_discover.py` was built (through 2026-06-21) before being
abandoned. `strollopia-org-setup` kept receiving real production commits
through 2026-08-27+ (wolfville/valleyartmap/kentville onboarding, safety
fixes).

Diffing both against the shared ancestor:

| File | Disposition |
|---|---|
| `tools/city_discover.py`, `tests/test_city_discover.py`, `CLAUDE.md` | New files, no conflict. Copy over as-is. |
| `tools/strollopia_import.py` | Clean added per-language schema discovery (`import-schema.<lang>.yaml` glob instead of one hardcoded `import-schema.yaml`). No overlap with org-setup's independent changes to this file. Port as-is. **Required** — `city_discover.py` writes exactly this per-language schema shape, so without this port its output isn't importable. |
| `tools/org_yaml_wizard.py`, `tools/post_org_setup.py` | Real conflict. Clean reworked these around a stable `org_slug` (directory label) decoupled from `org_domain_name` (the runtime domain), so an org can move to a new domain without renaming its directory or losing git history — directly useful for sub-project C's domain transitions. Org-setup's `main` independently added a whole **Step 9: Theme** (for the PWA path) plus a `_deep_merge` config helper, touching the same `run_wizard` function. Resolution: **do not git-merge**. Re-apply the slug/domain-decoupling intent by hand on top of current `main` (post-Theme-step), preserving Step 9 and `_deep_merge` untouched. |

After reconciliation, `strollopia-clean` is retired (archived, not deleted,
in case anything was missed).

## Architecture

`tools/go_live.py` is a thin sequencer, not a replacement for any existing
tool. Each stage below is already independently runnable today (or becomes so
after reconciliation) — `go_live.py` calls them in order and stops on the
first failure, surfacing whatever that stage already prints. This preserves
the existing workflow of running a stage by hand (`--dry-run`, `--validate-only`)
when something needs a human look, which the current tools and
`prod-org-setup.md` already lean on heavily.

```
go_live.py "Kentville, NS" --source google --path map
  │
  ├─ 1. city_discover.py           → org-setup.yaml + map-data.tsv +
  │                                    import-schema.<lang>.yaml per preset
  │                                    (--source template: stop here, not built)
  │
  ├─ 2. post_org_setup.py          → org + maps created on target server
  │
  ├─ 3. strollopia_import.py       → POIs imported (--all-maps)
  │                                    (--path pwa: stop here, not built)
  │
  ├─ 4. generate_deploy_script.py  → writes a ready-to-run shell script:
  │        (NEW)                      cp _template, token substitution,
  │                                    wrangler kv namespace create,
  │                                    wrangler pages project create,
  │                                    Makefile target, wrangler pages deploy.
  │                                    Prints the two remaining manual
  │                                    Cloudflare-dashboard steps (custom
  │                                    domain attach + DNS CNAME) as an
  │                                    explicit checklist — not executed.
  │
  └─ 5. check_live.py (NEW)        → run by hand after the human completes
                                       the dashboard steps and runs the
                                       generated script; HTTP-checks the
                                       trial URL and confirms the map embed
                                       loads.
```

Stage 4's output is a script, not an action — this is the Approach B
boundary. Nothing after data import touches Cloudflare or DNS without a
human running a generated, reviewable command.

## Data Flow

The contract between stages 1 and 3 is unchanged from today:
`org-setup.yaml` + `<map>/map-data.tsv` + `<map>/import-schema.<lang>.yaml`,
laid out under `org-data/<org_slug>/` exactly as `strollopia_import.py`
already expects. `city_discover.py` already produces this; a future
`--source template` producer would need to produce the identical shape,
which is why no changes are needed downstream of stage 1 to support it later.

## Error Handling

`go_live.py` adds no new error-handling logic of its own beyond sequencing —
each stage keeps its own (e.g. `post_org_setup.py`'s stale-password and
empty-map warnings, `strollopia_import.py`'s validation). A failure at any
stage halts the pipeline before the next one runs; partial progress (e.g. org
created but import failed) is safe to resume by re-running from the failed
stage directly with the existing tools, the same way it's done manually today.

## Testing

- Unit tests for the two ported/reworked pieces: per-language schema
  discovery in `strollopia_import.py`, and the reapplied slug/domain
  decoupling in `org_yaml_wizard.py`/`post_org_setup.py`.
- `go_live.py` itself is tested by composition: a `--dry-run` flag threads
  through to `strollopia_import.py`'s existing dry-run support and stops
  before stage 4, so the full discovery→org→import path can be smoke-tested
  against dev without touching Cloudflare or prod.
- `generate_deploy_script.py` is tested by asserting on its generated
  script's content (token substitution correctness) rather than by actually
  running wrangler commands in tests.

## Open Items Deliberately Left Unresolved

- Exact CLI shape of `generate_deploy_script.py`'s output (a `.sh` file vs.
  stdout) — an implementation-time call.
- Whether `check_live.py` reuses the puppeteer-based harness from prior
  verification work or is a plain HTTP check — plain HTTP is likely
  sufficient for this use case (confirming deploy succeeded, not full
  cross-browser rendering) and is the default assumption; revisit if it
  proves insufficient.
