#!/bin/bash
set -euo pipefail
cd ../strollopia-sites/sites/stryi

# Create the Cloudflare Pages project
npx wrangler pages project create stryi --production-branch main

# Deploy
npx wrangler pages deploy . --project-name stryi --commit-dirty=true
