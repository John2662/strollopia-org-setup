#!/bin/bash
# Interactive, step-by-step wizard for bringing a new town live on prod.
#
# Prompts for the town's details, then walks through each stage of the
# go-live pipeline one at a time: runs it, shows what happened, explains
# the next step, and waits for Enter before continuing. Cloudflare's
# dashboard-only steps are never executed -- this just prints exactly
# what to click, then waits for you to confirm you've done it.
#
# Run from anywhere; it locates the repo root itself.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$REPO_ROOT"

PYTHON="$REPO_ROOT/.env/bin/python"

if [ ! -x "$PYTHON" ]; then
  echo "FAILED: no venv python at $PYTHON -- run this from a strollopia-org-setup checkout with .env/ set up." >&2
  exit 1
fi

BOLD=$(tput bold 2>/dev/null || true)
RESET=$(tput sgr0 2>/dev/null || true)
GREEN=$(tput setaf 2 2>/dev/null || true)
YELLOW=$(tput setaf 3 2>/dev/null || true)

section() {
  echo
  echo "${BOLD}=== $1 ===${RESET}"
}

pause() {
  # $1 = plain-English description of what's about to run
  echo
  echo "${YELLOW}Next: $1${RESET}"
  read -r -p "Press Enter to continue (Ctrl+C to stop here)... "
  echo
}

fail() {
  echo
  echo "FAILED: $1" >&2
  exit 1
}

section "Town details"
read -r -p "Town name (e.g. Kingston): " TOWN
read -r -p "Province/state (e.g. Nova Scotia): " PROVINCE
read -r -p "Country [Canada]: " COUNTRY
COUNTRY=${COUNTRY:-Canada}
[ -n "$TOWN" ] || fail "town name is required"
[ -n "$PROVINCE" ] || fail "province/state is required"

CITY_QUERY="$TOWN, $PROVINCE, $COUNTRY"
echo
echo "Will geocode: \"$CITY_QUERY\""
read -r -p "Domain override (leave blank to auto-generate the standard slug): " DOMAIN_OVERRIDE

if [ ! -f .secrets.env ]; then
  fail ".secrets.env not found in $REPO_ROOT -- needed for GOOGLE_PLACES_API_KEY"
fi
set -a
source .secrets.env
set +a

export USE_PROD=1
echo
echo "${BOLD}Target: PRODUCTION${RESET} (USE_PROD=1) -- this brings a town live for real."
pause "run discovery for \"$CITY_QUERY\" (Google Places + OSM -- this spends real Google API usage)"

section "Step 0/6: Discover POIs"
DISCOVER_ARGS=(tools/city_discover.py "$CITY_QUERY" --languages en --init)
if [ -n "$DOMAIN_OVERRIDE" ]; then
  DISCOVER_ARGS+=(--domain "$DOMAIN_OVERRIDE")
fi
DISCOVER_OUTPUT=$("$PYTHON" "${DISCOVER_ARGS[@]}" 2>&1 | tee /dev/stderr) \
  || fail "city_discover.py failed -- see output above"

ACTUAL_DOMAIN=$(printf '%s\n' "$DISCOVER_OUTPUT" | grep -m1 '^\[domain\]' | awk '{print $2}')
[ -n "$ACTUAL_DOMAIN" ] || fail "could not read the org domain from city_discover.py's output"
SLUG=${ACTUAL_DOMAIN%.strollopia.com}

echo
echo "What happened: discovery complete."
echo "  Domain: $ACTUAL_DOMAIN"
echo "  Slug:   $SLUG"
echo "  Data:   org-data/$SLUG/"
echo "Check: skim the counts above (any preset at 0 found is worth a second look)."

pause "create the org on prod -- this will prompt YOU for your Django super-admin email and password"

section "Step 1/6: Create the org on prod"
"$PYTHON" tools/post_org_setup.py "$SLUG" \
  || fail "post_org_setup.py failed -- fix the error above, then re-run: $PYTHON tools/post_org_setup.py $SLUG"

echo
echo "What happened: org created."
echo "Check: it should have printed \"Organization created\" and \"OK: org admin login verified\" above."

pause "import the discovered POIs (uses the org-admin credentials already saved in org-setup.secrets.yaml -- no login needed from you)"

section "Step 2/6: Import POIs"
"$PYTHON" tools/strollopia_import.py "org-data/$SLUG/" --all-maps \
  || fail "strollopia_import.py failed -- see output above"

echo
echo "What happened: POIs imported."
echo "Check: the row count posted should match the number discovery reported."

pause "generate deploy.sh -- looks up the map's numeric pk from the live API and writes org-data/$SLUG/deploy.sh"

section "Step 3/6: Generate the deploy script"
"$PYTHON" tools/generate_deploy_script.py "$SLUG" \
  || fail "generate_deploy_script.py failed -- see output above"

echo
echo "What happened: org-data/$SLUG/deploy.sh written."
echo "Check: open it if you want to see exactly what it'll run before the next step."

pause "run deploy.sh -- needs YOUR wrangler/Cloudflare login (it may open a browser OAuth prompt the first time), and will pause partway through asking you to paste in a new KV namespace id"

section "Step 4/6: Deploy the Cloudflare Pages site"
bash "org-data/$SLUG/deploy.sh" \
  || fail "deploy.sh failed -- see output above (the KV JSON->TOML paste-in is the most common snag)"

echo
echo "What happened: template copied into sites/$SLUG/, KV namespace + Pages project created, site deployed."
echo "Check: the last wrangler output line should show a *.pages.dev URL you can open right now."

section "Step 5/6: Attach the custom domain (Cloudflare dashboard -- manual, nothing to run)"
cat <<EOF

Do this yourself in the Cloudflare dashboard:

  1. Workers & Pages -> $SLUG -> Custom domains -> Add a domain -> $ACTUAL_DOMAIN
     (this leaves it in a "pending" state)
  2. strollopia.com zone -> DNS -> Add record
       Type:  CNAME
       Name:  $SLUG
       Target: $SLUG.pages.dev
       Proxy status: Proxied (orange cloud -- grey/DNS-only won't work)
  3. Wait ~1-2 minutes for the certificate to flip from "pending" to "active"

EOF
pause "verify the site is actually live once the certificate is active"

section "Step 6/6: Verify it's live"
"$PYTHON" tools/check_live.py "$ACTUAL_DOMAIN" \
  || fail "check_live.py reported a problem -- see above (often just DNS not fully propagated yet; wait a bit and re-run: $PYTHON tools/check_live.py $ACTUAL_DOMAIN)"

echo
echo "${GREEN}${BOLD}Done. $TOWN is live at https://$ACTUAL_DOMAIN/${RESET}"
