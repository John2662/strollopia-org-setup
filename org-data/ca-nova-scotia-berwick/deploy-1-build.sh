#!/bin/bash
set -euo pipefail
cd ../strollopia-sites

# 1. Copy the template
cp -r _template sites/ca-nova-scotia-berwick

# 2. Replace placeholders
find sites/ca-nova-scotia-berwick -type f \( -name '*.html' -o -name '*.toml' \) -exec \
  sed -i \
    -e 's/REPLACE_MAP_ID/28/g' \
    -e 's/REPLACE_WITH_SITE_SLUG/ca-nova-scotia-berwick/g' \
    -e 's/Your Site Name/Berwick/g' \
  {} +
sed -i 's/const MAP_ID      = null;.*/const MAP_ID      = 28;/' sites/ca-nova-scotia-berwick/admin.html
mv sites/ca-nova-scotia-berwick/maps/REPLACE_MAP_ID sites/ca-nova-scotia-berwick/maps/28
