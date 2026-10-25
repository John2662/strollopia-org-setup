#!/bin/bash
set -euo pipefail
cd ../strollopia-sites/sites/ca-nova-scotia-antigonish

# Create the Cloudflare Pages project
npx wrangler pages project create ca-nova-scotia-antigonish --production-branch main

# Deploy
npx wrangler pages deploy . --project-name ca-nova-scotia-antigonish --commit-dirty=true
