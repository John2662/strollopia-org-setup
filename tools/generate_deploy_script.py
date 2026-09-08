#!/usr/bin/env python3
"""Generate a reviewable shell script that deploys a trial site from
strollopia-sites/_template for a newly-provisioned org.

This does not execute anything -- it only writes a script for a human to
read and run. The Cloudflare custom-domain and DNS steps are deliberately
left out of the script (see print_manual_checklist) since they need
dashboard access or an elevated API token this pipeline doesn't have.
"""
import argparse
import os

import yaml

from api_client import get_org_policy
from strollopia_import import get_map_pk_from_policy


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


def main(argv=None):
    """CLI: resolve an org's map pk from the live API and write deploy.sh.

    Reads display_name/org_domain_name from the org's own org-setup.yaml
    so the only required argument is the org_slug -- everything else
    (map pk, domain) is looked up, not retyped by hand.
    """
    parser = argparse.ArgumentParser(
        description="Generate a reviewable deploy.sh for an already-imported org.",
    )
    parser.add_argument("org_slug", help="Directory label under org-data/ (e.g. 'ca-nova-scotia-kingston')")
    parser.add_argument("--map-name", default="main-map",
                         help="org_map_name to deploy (default: main-map)")
    parser.add_argument("--sites-repo", default="../strollopia-sites",
                         help="Path to a strollopia-sites checkout (default: ../strollopia-sites)")
    parser.add_argument("--output-dir", default="org-data",
                         help="Base org-data directory (default: org-data)")
    args = parser.parse_args(argv)

    yaml_path = os.path.join(args.output_dir, args.org_slug, "org-setup.yaml")
    if not os.path.exists(yaml_path):
        print(f"Error: file not found: {yaml_path}")
        return 1
    with open(yaml_path) as f:
        config = yaml.safe_load(f) or {}
    org_domain_name = config.get("org_domain_name")
    if not org_domain_name:
        print(f"Error: {yaml_path} has no org_domain_name")
        return 1
    display_name = config.get("display_name", args.org_slug)

    policy = get_org_policy(org_domain_name)
    map_id = get_map_pk_from_policy(policy, args.map_name)
    if map_id is None:
        print(f"Error: map {args.map_name!r} not found in org policy for {org_domain_name}.")
        print("Is it public/in_public_viewer_list, and has the import run yet?")
        return 1

    output_path = os.path.join(args.output_dir, args.org_slug, "deploy.sh")
    generate_deploy_script(args.org_slug, display_name, map_id, args.sites_repo, output_path=output_path)
    print(f"Written {output_path} (map pk {map_id})")
    print_manual_checklist(args.org_slug, org_domain_name)
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
