#!/usr/bin/env python3
"""Generate a reviewable shell script that deploys a trial site from
strollopia-sites/_template for a newly-provisioned org.

This does not execute anything -- it only writes a script for a human to
read and run. The Cloudflare custom-domain and DNS steps are deliberately
left out of the script (see print_manual_checklist) since they need
dashboard access or an elevated API token this pipeline doesn't have.
"""
import os


DEPLOY_SCRIPT_TEMPLATE = """#!/bin/bash
set -euo pipefail
cd {sites_repo}

# 1. Copy the template
cp -r _template {site_dir}

# 2. Replace placeholders
find {site_dir} -type f \\( -name '*.html' -o -name '*.toml' \\) -exec \\
  sed -i \\
    -e 's/REPLACE_MAP_ID/{map_id}/g' \\
    -e 's/REPLACE_WITH_SITE_SLUG/{org_slug}/g' \\
    -e 's/Your Site Name/{display_name}/g' \\
  {{}} +
sed -i 's/const MAP_ID      = null;.*/const MAP_ID      = {map_id};/' {site_dir}/admin.html
mv {site_dir}/maps/REPLACE_MAP_ID {site_dir}/maps/{map_id}

# 3. Create the KV namespace, then paste its id into wrangler.toml by hand
#    (wrangler prints the id; there's no scripted way to feed it back into
#    this same run without a second manual step)
npx wrangler kv namespace create "{kv_title}"
echo "Paste the id above into {site_dir}/wrangler.toml's REPLACE_WITH_NEW_KV_NAMESPACE_ID, then press Enter to continue."
read -r

# 4. Create the Cloudflare Pages project
npx wrangler pages project create {org_slug} --production-branch main

# 5. Deploy
cd {site_dir} && npx wrangler pages deploy . --project-name {org_slug} --commit-dirty=true
"""


def generate_deploy_script(org_slug, display_name, map_id, sites_repo, output_path=None):
    """Build the deploy script for one org. Returns the script text.

    Writes it to output_path (executable) if given.
    """
    site_dir = os.path.join("sites", org_slug)
    kv_title = f"{org_slug}-SPLASH_CONTENT"
    script = DEPLOY_SCRIPT_TEMPLATE.format(
        sites_repo=sites_repo,
        site_dir=site_dir,
        map_id=map_id,
        org_slug=org_slug,
        display_name=display_name,
        kv_title=kv_title,
    )
    if output_path:
        with open(output_path, "w") as f:
            f.write(script)
        os.chmod(output_path, 0o755)
    return script


def print_manual_checklist(org_slug, domain):
    """Print the Cloudflare-dashboard-only steps that can't be scripted."""
    print(f"""
Manual steps (Cloudflare dashboard -- need dashboard access or an elevated API token):
  1. Attach custom domain: Workers & Pages -> {org_slug} -> Custom domains
     -> Add a domain -> {domain}
  2. Create DNS record: strollopia.com zone -> DNS -> Add record
       Type: CNAME   Name: {org_slug}   Target: {org_slug}.pages.dev
       Proxy status: Proxied
  3. Wait ~1-2 minutes for the certificate, then run:
       python tools/check_live.py {domain}
""")
