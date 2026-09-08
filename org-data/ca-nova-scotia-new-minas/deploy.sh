#!/bin/bash
set -euo pipefail
cd /home/john/strollopia_git_hub/strollopia-sites

# 1. Copy the template
cp -r _template sites/ca-nova-scotia-new-minas

# 2. Replace placeholders
find sites/ca-nova-scotia-new-minas -type f \( -name '*.html' -o -name '*.toml' \) -exec \
  sed -i \
    -e 's/REPLACE_MAP_ID/16/g' \
    -e 's/REPLACE_WITH_SITE_SLUG/ca-nova-scotia-new-minas/g' \
    -e 's/Your Site Name/New Minas/g' \
  {} +
sed -i 's/const MAP_ID      = null;.*/const MAP_ID      = 16;/' sites/ca-nova-scotia-new-minas/admin.html
mv sites/ca-nova-scotia-new-minas/maps/REPLACE_MAP_ID sites/ca-nova-scotia-new-minas/maps/16

# 3. Create the KV namespace, then paste its id into wrangler.toml by hand
#    (wrangler prints the id; there's no scripted way to feed it back into
#    this same run without a second manual step)
npx wrangler kv namespace create "ca-nova-scotia-new-minas-SPLASH_CONTENT"
echo "Paste the id above into sites/ca-nova-scotia-new-minas/wrangler.toml's REPLACE_WITH_NEW_KV_NAMESPACE_ID, then press Enter to continue."
read -r

# 4. Create the Cloudflare Pages project
npx wrangler pages project create ca-nova-scotia-new-minas --production-branch main

# 5. Deploy
cd sites/ca-nova-scotia-new-minas && npx wrangler pages deploy . --project-name ca-nova-scotia-new-minas --commit-dirty=true
