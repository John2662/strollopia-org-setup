#!/bin/bash
set -euo pipefail
cd ../strollopia-sites

# 1. Copy the template
cp -r _template sites/ca-nova-scotia-grand-pre

# 2. Replace placeholders
find sites/ca-nova-scotia-grand-pre -type f \( -name '*.html' -o -name '*.toml' \) -exec \
  sed -i \
    -e 's/REPLACE_MAP_ID/23/g' \
    -e 's/REPLACE_WITH_SITE_SLUG/ca-nova-scotia-grand-pre/g' \
    -e 's/Your Site Name/Grand Pré/g' \
  {} +
sed -i 's/const MAP_ID      = null;.*/const MAP_ID      = 23;/' sites/ca-nova-scotia-grand-pre/admin.html
mv sites/ca-nova-scotia-grand-pre/maps/REPLACE_MAP_ID sites/ca-nova-scotia-grand-pre/maps/23

# 3. Create the KV namespace, then paste its id into wrangler.toml by hand
#    (wrangler prints the id; there's no scripted way to feed it back into
#    this same run without a second manual step)
npx wrangler kv namespace create "ca-nova-scotia-grand-pre-SPLASH_CONTENT"
echo "Paste the id above into sites/ca-nova-scotia-grand-pre/wrangler.toml's REPLACE_WITH_NEW_KV_NAMESPACE_ID, then press Enter to continue."
read -r

# 4. Create the Cloudflare Pages project
npx wrangler pages project create ca-nova-scotia-grand-pre --production-branch main

# 5. Deploy
cd sites/ca-nova-scotia-grand-pre && npx wrangler pages deploy . --project-name ca-nova-scotia-grand-pre --commit-dirty=true
