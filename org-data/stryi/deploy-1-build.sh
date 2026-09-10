#!/bin/bash
set -euo pipefail
cd ../strollopia-sites

# 1. Copy the template
cp -r _template sites/stryi

# 2. Replace placeholders
find sites/stryi -type f \( -name '*.html' -o -name '*.toml' \) -exec \
  sed -i \
    -e 's/REPLACE_MAP_ID/27/g' \
    -e 's/REPLACE_WITH_SITE_SLUG/stryi/g' \
    -e 's/Your Site Name/Stryi/g' \
  {} +
sed -i 's/const MAP_ID      = null;.*/const MAP_ID      = 27;/' sites/stryi/admin.html
mv sites/stryi/maps/REPLACE_MAP_ID sites/stryi/maps/27
