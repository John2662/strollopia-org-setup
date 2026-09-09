#!/bin/bash
set -euo pipefail
cd ../strollopia-sites/sites/ca-nova-scotia-lunenburg

# Create the Cloudflare Pages project
npx wrangler pages project create ca-nova-scotia-lunenburg --production-branch main

# Deploy
npx wrangler pages deploy . --project-name ca-nova-scotia-lunenburg --commit-dirty=true
