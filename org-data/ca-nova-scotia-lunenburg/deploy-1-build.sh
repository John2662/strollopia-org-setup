#!/bin/bash
set -euo pipefail
cd ../strollopia-sites

# 1. Copy the template
cp -r _template sites/ca-nova-scotia-lunenburg

# 2. Replace placeholders
find sites/ca-nova-scotia-lunenburg -type f \( -name '*.html' -o -name '*.toml' \) -exec \
  sed -i \
    -e 's/REPLACE_MAP_ID/24/g' \
    -e 's/REPLACE_WITH_SITE_SLUG/ca-nova-scotia-lunenburg/g' \
    -e 's/Your Site Name/Lunenburg/g' \
  {} +
sed -i 's/const MAP_ID      = null;.*/const MAP_ID      = 24;/' sites/ca-nova-scotia-lunenburg/admin.html
mv sites/ca-nova-scotia-lunenburg/maps/REPLACE_MAP_ID sites/ca-nova-scotia-lunenburg/maps/24
