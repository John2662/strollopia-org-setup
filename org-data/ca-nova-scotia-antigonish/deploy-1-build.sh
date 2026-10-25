#!/bin/bash
set -euo pipefail
cd ../strollopia-sites

# 1. Copy the template
cp -r _template sites/ca-nova-scotia-antigonish

# 2. Replace placeholders
find sites/ca-nova-scotia-antigonish -type f \( -name '*.html' -o -name '*.toml' \) -exec \
  sed -i \
    -e 's/REPLACE_MAP_ID/37/g' \
    -e 's/REPLACE_WITH_SITE_SLUG/ca-nova-scotia-antigonish/g' \
    -e 's/Your Site Name/Antigonish/g' \
  {} +
sed -i 's/const MAP_ID      = null;.*/const MAP_ID      = 37;/' sites/ca-nova-scotia-antigonish/admin.html
mv sites/ca-nova-scotia-antigonish/maps/REPLACE_MAP_ID sites/ca-nova-scotia-antigonish/maps/37
