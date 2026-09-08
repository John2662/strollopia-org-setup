Here's the full sequence, in order. Everything with a $ prompt is a real command to run from your terminal.

  Tier 1 — get the org live and importable (needed either way)

  cd /home/john/strollopia_git_hub/strollopia-org-setup
  set -a && source .secrets.env && set +a
  export USE_PROD=1

  https://ca-nova-scotia-kingston.viewer.strollopia.com

  Optional sanity check anytime after step 1, to see what's left in the pipeline:

  cd /home/john/strollopia_git_hub/strollopia-sites
  make todo SITE=ca-nova-scotia-kingston

  Tier 2 — the branded Cloudflare Pages site (only if you have time for the polish)

  cd /home/john/strollopia_git_hub/strollopia-sites

  # Step 3: copy the template
  cp -r _template sites/ca-nova-scotia-kingston

  # Step 4: find the map's numeric pk (needed for REPLACE_MAP_ID)
  curl -s "https://prod.strollopia.com/api/org/org-policy/?org_domain_name=ca-nova-scotia-kingston.strollopia.com" \
    | python3 -c "import json,sys; print(json.load(sys.stdin)['public_org_maps'])"

  Then by hand (not scriptable — see _template/ONBOARDING.md for the full token list):
  - Replace REPLACE_MAP_ID and Your Site Name throughout sites/ca-nova-scotia-kingston/
  - Replace REPLACE_WITH_SITE_SLUG in wrangler.toml with ca-nova-scotia-kingston-ca

  # Step 5: create the KV namespace
  npx wrangler kv namespace create "ca-nova-scotia-kingston-SPLASH_CONTENT"

  Take the id from that JSON output and hand-edit it into wrangler.toml as:
  [[kv_namespaces]]
  binding = "SPLASH_CONTENT"
  id = "<the id from above>"

  # Step 6: create the Pages project
  npx wrangler pages project create ca-nova-scotia-kingston-ca --production-branch main

  # Step 7: deploy
  make deploy SITE=ca-nova-scotia-kingston-ca

  Step 8 — custom domain (Cloudflare dashboard, not bash): Workers & Pages → the project → Custom domains → add ca-nova-scotia-kingston.strollopia.com → then DNS tab
  → add a proxied CNAME record pointed at ca-nova-scotia-kingston-ca.pages.dev. Certificate takes ~1-2 min to go active.

  Given your 9-hour window, I'd stop after Tier 1 for today's call and only do Tier 2 if the meeting goes well and you want a real domain to hand them afterward.


This is the result of the command 
cd /home/john/strollopia_git_hub/strollopia-sites
make todo SITE=ca-nova-scotia-kingston


┌─────┬────────────────────┬────────────────────────────────────────────────────────────────────────────┬────────────────────────────┐
│ #   │ Status             │ Step                                                                       │ Who                        │
├─────┼────────────────────┼────────────────────────────────────────────────────────────────────────────┼────────────────────────────┤
│ 1   │ [pending]          │ python tools/post_org_setup.py ca-nova-scotia-kingston                     │ You (super-admin login)    │
├─────┼────────────────────┼────────────────────────────────────────────────────────────────────────────┼────────────────────────────┤
│ 2   │ [?]                │ python tools/strollopia_import.py org-data/ca-nova-scotia-kingston/        │ You, or I can run it       │
│     │ org not posted yet │ --all-maps                                                                 │ (reads secrets file)       │
│     │                    │ (no --email/--password needed, reads the secrets file automatically)       │                            │
├─────┼────────────────────┼────────────────────────────────────────────────────────────────────────────┼────────────────────────────┤
│ 3   │ [pending]          │ Generate deploy.sh once the map pk is known                                │ I can do this              │
├─────┼────────────────────┼────────────────────────────────────────────────────────────────────────────┼────────────────────────────┤
│ 4   │ [pending]          │ bash org-data/ca-nova-scotia-kingston/deploy.sh                            │ You (Cloudflare/wrangler   │
│     │                    │ (watch for the KV JSON→TOML gotcha, see ONBOARDING.md)                     │ login)                     │
├─────┼────────────────────┼────────────────────────────────────────────────────────────────────────────┼────────────────────────────┤
│ 5   │ [pending]          │ Attach custom domain + create DNS CNAME (Cloudflare dashboard)             │ You (Cloudflare dashboard) │
├─────┼────────────────────┼────────────────────────────────────────────────────────────────────────────┼────────────────────────────┤
│ 6   │ [pending]          │ python tools/check_live.py ca-nova-scotia-kingston.strollopia.com          │ I can do this              │
└─────┴────────────────────┴────────────────────────────────────────────────────────────────────────────┴────────────────────────────┘


This is the intertwining  of the two:

how do the two descriptions intertwine?

● Good catch — the todo tool is right and my Tier 2 was more manual than necessary. Here's how they map:

  My steps: Tier 1 step 1 (post_org_setup.py)
  Their make todo #: #1
  Reconciliation: Identical.
  ────────────────────────────────────────
  My steps: Tier 1 step 2 (strollopia_import.py --all-maps)
  Their make todo #: #2
  Reconciliation: Identical — and their "Who" column confirms what I said: I can run this one, no login needed from you.
  ────────────────────────────────────────
  My steps: Viewer URL shortcut (...viewer.strollopia.com)
  Their make todo #: (not listed)
  Reconciliation: This isn't part of their generated checklist at all — it's an independent shortcut that becomes usable right after step #2, orthogonal to the
  branded-site pipeline below. Good for today's call, doesn't replace anything downstream.
  ────────────────────────────────────────
  My steps: My Tier 2 steps 3–7 (copy _template by hand, replace placeholders, create KV, create Pages project, make deploy)
  Their make todo #: #3 + #4
  Reconciliation: This is where I overcomplicated it. There's a tool I should have used instead of walking you through it manually: tools/generate_deploy_script.py
  generates a single deploy.sh that does all of that (copy, token substitution, KV+Pages+deploy), tailored to the org once the map pk is known. I can generate that
  script — no credentials needed for generating it. You then run bash org-data/ca-nova-scotia-kingston/deploy.sh yourself, since it needs your wrangler/Cloudflare
  login.
  ────────────────────────────────────────
  My steps: My step 8 (custom domain + DNS CNAME)
  Their make todo #: #5
  Reconciliation: Identical — genuinely manual, Cloudflare dashboard only.
  ────────────────────────────────────────
  My steps: (I didn't mention this)
  Their make todo #: #6 (check_live.py)
  Reconciliation: A verification step I should have included — a plain HTTP check that the deployed site is live and correctly wired. No auth needed, so I can run
  this
  one for you too, once DNS is active.

  So the corrected division of labor: you run #1 (super-admin login) and #4/#5 (wrangler + Cloudflare dashboard). I can run #2 (import), #3 (generate the deploy
  script), and #6 (final live check) whenever you're ready for each.

  Want me to generate deploy.sh now (step #3), or wait until after you've run step #1?





