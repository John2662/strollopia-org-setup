#!/bin/bash
set -euo pipefail
cd ../strollopia-sites

# 1. Copy the template
cp -r _template sites/ca-nova-scotia-belnan

# 2. Replace placeholders
find sites/ca-nova-scotia-belnan -type f \( -name '*.html' -o -name '*.toml' \) -exec \
  sed -i \
    -e 's/REPLACE_MAP_ID/25/g' \
    -e 's/REPLACE_WITH_SITE_SLUG/ca-nova-scotia-belnan/g' \
    -e 's/Your Site Name/Belnan/g' \
  {} +
sed -i 's/const MAP_ID      = null;.*/const MAP_ID      = 25;/' sites/ca-nova-scotia-belnan/admin.html
mv sites/ca-nova-scotia-belnan/maps/REPLACE_MAP_ID sites/ca-nova-scotia-belnan/maps/25
