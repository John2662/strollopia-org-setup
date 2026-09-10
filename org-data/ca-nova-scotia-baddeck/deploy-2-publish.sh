#!/bin/bash
set -euo pipefail
cd ../strollopia-sites/sites/ca-nova-scotia-baddeck

# Create the Cloudflare Pages project
npx wrangler pages project create ca-nova-scotia-baddeck --production-branch main

# Deploy
npx wrangler pages deploy . --project-name ca-nova-scotia-baddeck --commit-dirty=true
