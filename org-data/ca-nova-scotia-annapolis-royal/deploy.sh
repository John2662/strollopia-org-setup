#!/bin/bash
set -euo pipefail
cd /home/john/strollopia_git_hub/strollopia-sites

# 1. Copy the template
cp -r _template sites/ca-nova-scotia-annapolis-royal

# 2. Replace placeholders
find sites/ca-nova-scotia-annapolis-royal -type f \( -name '*.html' -o -name '*.toml' \) -exec \
  sed -i \
    -e 's/REPLACE_MAP_ID/21/g' \
    -e 's/REPLACE_WITH_SITE_SLUG/ca-nova-scotia-annapolis-royal/g' \
    -e 's/Your Site Name/Annapolis Royal/g' \
  {} +
sed -i 's/const MAP_ID      = null;.*/const MAP_ID      = 21;/' sites/ca-nova-scotia-annapolis-royal/admin.html
mv sites/ca-nova-scotia-annapolis-royal/maps/REPLACE_MAP_ID sites/ca-nova-scotia-annapolis-royal/maps/21

# 3. Create the KV namespace, then paste its id into wrangler.toml by hand
#    (wrangler prints the id; there's no scripted way to feed it back into
#    this same run without a second manual step)
npx wrangler kv namespace create "ca-nova-scotia-annapolis-royal-SPLASH_CONTENT"
echo "Paste the id above into sites/ca-nova-scotia-annapolis-royal/wrangler.toml's REPLACE_WITH_NEW_KV_NAMESPACE_ID, then press Enter to continue."
read -r

# 4. Create the Cloudflare Pages project
npx wrangler pages project create ca-nova-scotia-annapolis-royal --production-branch main

# 5. Deploy
cd sites/ca-nova-scotia-annapolis-royal && npx wrangler pages deploy . --project-name ca-nova-scotia-annapolis-royal --commit-dirty=true
