#!/bin/bash
set -euo pipefail
cd ../strollopia-sites

# 1. Copy the template
cp -r _template sites/ca-nova-scotia-kingston

# 2. Replace placeholders
find sites/ca-nova-scotia-kingston -type f \( -name '*.html' -o -name '*.toml' \) -exec \
  sed -i \
    -e 's/REPLACE_MAP_ID/22/g' \
    -e 's/REPLACE_WITH_SITE_SLUG/ca-nova-scotia-kingston/g' \
    -e 's/Your Site Name/Kingston/g' \
  {} +
sed -i 's/const MAP_ID      = null;.*/const MAP_ID      = 22;/' sites/ca-nova-scotia-kingston/admin.html
mv sites/ca-nova-scotia-kingston/maps/REPLACE_MAP_ID sites/ca-nova-scotia-kingston/maps/22

# 3. Create the KV namespace, then paste its id into wrangler.toml by hand
#    (wrangler prints the id; there's no scripted way to feed it back into
#    this same run without a second manual step)
npx wrangler kv namespace create "ca-nova-scotia-kingston-SPLASH_CONTENT"
echo "Paste the id above into sites/ca-nova-scotia-kingston/wrangler.toml's REPLACE_WITH_NEW_KV_NAMESPACE_ID, then press Enter to continue."
read -r

# 4. Create the Cloudflare Pages project
npx wrangler pages project create ca-nova-scotia-kingston --production-branch main

# 5. Deploy
cd sites/ca-nova-scotia-kingston && npx wrangler pages deploy . --project-name ca-nova-scotia-kingston --commit-dirty=true
