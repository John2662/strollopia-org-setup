#!/bin/bash
set -euo pipefail
cd ../strollopia-sites

# 1. Copy the template
cp -r _template sites/ca-nova-scotia-baddeck

# 2. Replace placeholders
find sites/ca-nova-scotia-baddeck -type f \( -name '*.html' -o -name '*.toml' \) -exec \
  sed -i \
    -e 's/REPLACE_MAP_ID/29/g' \
    -e 's/REPLACE_WITH_SITE_SLUG/ca-nova-scotia-baddeck/g' \
    -e 's/Your Site Name/Baddeck/g' \
  {} +
sed -i 's/const MAP_ID      = null;.*/const MAP_ID      = 29;/' sites/ca-nova-scotia-baddeck/admin.html
mv sites/ca-nova-scotia-baddeck/maps/REPLACE_MAP_ID sites/ca-nova-scotia-baddeck/maps/29
