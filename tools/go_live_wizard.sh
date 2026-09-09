#!/bin/bash
# Interactive, step-by-step wizard for bringing a new town live on prod.
#
# Prompts for the town's details, then walks through each stage of the
# go-live pipeline one at a time: runs it, shows what happened, explains
# the next step, and waits for Enter before continuing. Cloudflare's
# dashboard-only step is never executed -- this just prints exactly what
# to click, tries to open the login page for you, and gates on you
# actually confirming it's done before moving on.
#
# Run from anywhere; it locates the repo root itself.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$REPO_ROOT"

PYTHON="$REPO_ROOT/.env/bin/python"

# Names used to prefix every file path this script prints, so it's always
# clear which of the two sibling repos a path belongs to -- the build/
# publish scripts cd into strollopia-sites partway through, so
# "sites/<slug>/" on its own is ambiguous about which checkout it's
# relative to.
ORG_SETUP_REPO="$(basename "$REPO_ROOT")"
SITES_REPO_PATH="$(cd "$REPO_ROOT/../strollopia-sites" 2>/dev/null && pwd || true)"
SITES_REPO="$(basename "${SITES_REPO_PATH:-strollopia-sites}")"

if [ ! -x "$PYTHON" ]; then
  echo "FAILED: no venv python at $PYTHON -- run this from a $ORG_SETUP_REPO checkout with .env/ set up." >&2
  exit 1
fi

BOLD=$(tput bold 2>/dev/null || true)
RESET=$(tput sgr0 2>/dev/null || true)
GREEN=$(tput setaf 2 2>/dev/null || true)
RED=$(tput setaf 1 2>/dev/null || true)
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
  fail ".secrets.env not found in $ORG_SETUP_REPO -- needed for GOOGLE_PLACES_API_KEY"
fi
set -a
source .secrets.env
set +a

export USE_PROD=1
echo
echo "${BOLD}Target: PRODUCTION${RESET} (USE_PROD=1) -- this brings a town live for real."
pause "run discovery for \"$CITY_QUERY\" (Google Places + OSM -- this spends real Google API usage)"

section "Step 1/8: Discover POIs"
DISCOVER_ARGS=(tools/city_discover.py "$CITY_QUERY" --languages en --init)
if [ -n "$DOMAIN_OVERRIDE" ]; then
  DISCOVER_ARGS+=(--domain "$DOMAIN_OVERRIDE")
fi
DISCOVER_OUTPUT=$("$PYTHON" "${DISCOVER_ARGS[@]}" 2>&1 | tee /dev/stderr) \
  || fail "city_discover.py failed -- see output above"

ACTUAL_DOMAIN=$(printf '%s\n' "$DISCOVER_OUTPUT" | grep -m1 '^\[domain\]' | awk '{print $2}')
[ -n "$ACTUAL_DOMAIN" ] || fail "could not read the org domain from city_discover.py's output"
SLUG=${ACTUAL_DOMAIN%.strollopia.com}
SITE_DIR="$SITES_REPO_PATH/sites/$SLUG"
WRANGLER_TOML="$SITE_DIR/wrangler.toml"

echo
echo "What happened: discovery complete."
echo "  Domain: $ACTUAL_DOMAIN"
echo "  Slug:   $SLUG"
echo "  Data:   $ORG_SETUP_REPO/org-data/$SLUG/"
echo "Check: skim the counts above (any preset at 0 found is worth a second look)."

pause "create the org on prod -- this will prompt YOU for your Django super-admin email and password"

section "Step 2/8: Create the org on prod"
"$PYTHON" tools/post_org_setup.py "$SLUG" \
  || fail "post_org_setup.py failed -- fix the error above, then re-run: $PYTHON tools/post_org_setup.py $SLUG"

echo
echo "What happened: org created."
echo "Check: it should have printed \"Organization created\" and \"OK: org admin login verified\" above."

pause "import the discovered POIs (uses the org-admin credentials already saved in $ORG_SETUP_REPO/org-data/$SLUG/org-setup.secrets.yaml -- no login needed from you)"

section "Step 3/8: Import POIs"
"$PYTHON" tools/strollopia_import.py "org-data/$SLUG/" --all-maps \
  || fail "strollopia_import.py failed -- see output above"

echo
echo "What happened: POIs imported."
echo "Check: the row count posted should match the number discovery reported."

pause "generate and run the build script -- looks up the map's numeric pk from the live API, writes $ORG_SETUP_REPO/org-data/$SLUG/deploy-1-build.sh and deploy-2-publish.sh, then runs the build one (copies the template and substitutes placeholders -- no Cloudflare calls, nothing interactive)"

section "Step 4/8: Build the site from the template"
"$PYTHON" tools/generate_deploy_script.py "$SLUG" --no-checklist \
  || fail "generate_deploy_script.py failed -- see output above"
bash "org-data/$SLUG/deploy-1-build.sh" \
  || fail "deploy-1-build.sh failed -- see output above"

echo
echo "What happened: $SITES_REPO/sites/$SLUG/ was created from the template with the map id, slug, and display name substituted in."
echo "Check: open $SITES_REPO/sites/$SLUG/index.html if you want to confirm before continuing."

pause "create the Cloudflare KV namespace -- needs YOUR wrangler/Cloudflare login (may open a browser OAuth prompt the first time)"

section "Step 5/8: Create the KV namespace"
KV_TITLE="${SLUG}-SPLASH_CONTENT"
echo "Creating KV namespace \"$KV_TITLE\"..."
KV_OUTPUT=$(npx wrangler kv namespace create "$KV_TITLE" 2>&1 | tee /dev/stderr) \
  || fail "wrangler kv namespace create failed -- see output above"

KV_ID=$(printf '%s\n' "$KV_OUTPUT" | grep -o '"id"[[:space:]]*:[[:space:]]*"[^"]*"' | head -1 \
  | sed -E 's/^"id"[[:space:]]*:[[:space:]]*"([^"]*)"$/\1/')

echo
if [ -z "$KV_ID" ]; then
  echo "${YELLOW}Could not automatically parse the namespace id from wrangler's output above.${RESET}"
  echo "Paste it into $SITES_REPO/sites/$SLUG/wrangler.toml's REPLACE_WITH_NEW_KV_NAMESPACE_ID by hand:"
  echo
  echo '  [[kv_namespaces]]'
  echo '  binding = "SPLASH_CONTENT"'
  echo '  id = "<paste here>"'
  echo
  read -r -p "Press Enter once wrangler.toml is updated... "
else
  echo "Step 5/8: Paste the kv_namespace id ($KV_ID) into $SITES_REPO/sites/$SLUG/wrangler.toml?"
  read -r -p "Would you like me to do this now? (Y/N): " KV_CONFIRM
  case "$KV_CONFIRM" in
    [Yy]*)
      sed -i "s/REPLACE_WITH_NEW_KV_NAMESPACE_ID/$KV_ID/" "$WRANGLER_TOML" \
        && echo "${GREEN}Patched $SITES_REPO/sites/$SLUG/wrangler.toml with id $KV_ID.${RESET}" \
        || fail "sed failed to patch $WRANGLER_TOML"
      ;;
    *)
      echo "OK -- paste \"$KV_ID\" into $SITES_REPO/sites/$SLUG/wrangler.toml's REPLACE_WITH_NEW_KV_NAMESPACE_ID by hand."
      read -r -p "Press Enter once it's updated... "
      ;;
  esac
fi

if grep -q "REPLACE_WITH_NEW_KV_NAMESPACE_ID" "$WRANGLER_TOML" 2>/dev/null; then
  fail "$WRANGLER_TOML still contains REPLACE_WITH_NEW_KV_NAMESPACE_ID -- fix it by hand, then re-run from here"
fi

echo "Check: $WRANGLER_TOML should now have a real hex id, no REPLACE_WITH_NEW_KV_NAMESPACE_ID left."

pause "create the Cloudflare Pages project and deploy -- needs YOUR wrangler/Cloudflare login"

section "Step 6/8: Create the Pages project and deploy"
bash "org-data/$SLUG/deploy-2-publish.sh" \
  || fail "deploy-2-publish.sh failed -- see output above"

echo
echo "What happened: Pages project created and site deployed."
echo "Check: the last wrangler output line should show a *.pages.dev URL you can open right now."

section "Step 7/8: Attach the custom domain (Cloudflare dashboard)"
CF_LOGIN_URL="https://dash.cloudflare.com/login"
cat <<EOF

Do this yourself in the Cloudflare dashboard:

  1. Workers & Pages -> $SLUG -> Custom domains -> "Set up a custom domain"
  2. Enter $ACTUAL_DOMAIN, continue to "Configure DNS" -- Cloudflare shows
     you the CNAME record it's about to add (Name: $SLUG, Target:
     $SLUG.pages.dev) -- then click "Activate Domain". Nothing to do in a
     separate DNS tab; this one flow handles both.
  3. Status shows "Initializing". Cloudflare's own UI warns "up to 48
     hours", but for a strollopia.com-zone domain it's typically ~1-2
     minutes to flip to "Active" with SSL enabled.

Dashboard login: $CF_LOGIN_URL
EOF
( xdg-open "$CF_LOGIN_URL" >/dev/null 2>&1 & ) || true

while true; do
  read -r -p "Did you complete the Cloudflare custom domain + DNS steps above? (Y/N): " CF_DONE
  case "$CF_DONE" in
    [Yy]*) break ;;
    [Nn]*)
      echo
      echo "${YELLOW}If you continue without finishing this:${RESET}"
      echo "  - Step 8's check_live.py will report $ACTUAL_DOMAIN as unreachable"
      echo "    (DNS won't resolve and/or the certificate won't be issued yet)."
      echo "  - Anyone visiting $ACTUAL_DOMAIN right now gets a connection error,"
      echo "    not a broken-looking site -- the domain simply isn't attached yet."
      echo "  - The site IS already live at the *.pages.dev URL from step 6 in the meantime."
      read -r -p "Go back and finish the Cloudflare steps, or continue anyway and check now? [wait/continue]: " CHOICE
      case "$CHOICE" in
        [Cc]*) break ;;
        *) echo "OK -- take your time, I'll ask again when you're ready." ;;
      esac
      ;;
    *) echo "Please answer Y or N." ;;
  esac
done

section "Step 8/8: Verify it's live"
"$PYTHON" tools/check_live.py "$ACTUAL_DOMAIN" \
  || fail "check_live.py reported a problem -- see above (often just DNS not fully propagated yet; wait a bit and re-run: $PYTHON tools/check_live.py $ACTUAL_DOMAIN)"

echo
echo "${GREEN}${BOLD}Done. $TOWN is live at https://$ACTUAL_DOMAIN/${RESET}"
