#!/bin/bash
set -euo pipefail
cd ../strollopia-sites/sites/ca-nova-scotia-berwick

# Create the Cloudflare Pages project
npx wrangler pages project create ca-nova-scotia-berwick --production-branch main

# Deploy
npx wrangler pages deploy . --project-name ca-nova-scotia-berwick --commit-dirty=true
