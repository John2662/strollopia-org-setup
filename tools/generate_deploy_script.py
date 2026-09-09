#!/usr/bin/env python3
"""Generate reviewable shell scripts that deploy a trial site from
strollopia-sites/_template for a newly-provisioned org.

This does not execute anything -- it only writes scripts for a human (or
go_live_wizard.sh) to read and run. Split into two scripts, not one,
because the KV namespace step in between them needs a live decision (parse
the id automatically, or paste it by hand) that can't happen inside a
non-interactively-reviewable shell script -- see go_live_wizard.sh's own
KV step. The Cloudflare custom-domain and DNS steps are deliberately left
out of both scripts entirely (see print_manual_checklist) since they need
dashboard access or an elevated API token this pipeline doesn't have.
"""
import argparse
import os

import yaml

from api_client import get_org_policy
from strollopia_import import get_map_pk_from_policy


BUILD_SCRIPT_TEMPLATE = """#!/bin/bash
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
"""

PUBLISH_SCRIPT_TEMPLATE = """#!/bin/bash
set -euo pipefail
cd {sites_repo}/{site_dir}

# Create the Cloudflare Pages project
npx wrangler pages project create {org_slug} --production-branch main

# Deploy
npx wrangler pages deploy . --project-name {org_slug} --commit-dirty=true
"""


def generate_deploy_scripts(org_slug, display_name, map_id, sites_repo, output_dir=None):
    """Build the build/publish deploy scripts for one org.

    Returns (build_script, publish_script) text. If output_dir is given,
    writes them there as deploy-1-build.sh and deploy-2-publish.sh
    (executable) -- the numbering matches the order they run in and the
    KV namespace step that belongs between them, run separately (by
    go_live_wizard.sh, not by either of these scripts).
    """
    site_dir = os.path.join("sites", org_slug)
    build_script = BUILD_SCRIPT_TEMPLATE.format(
        sites_repo=sites_repo,
        site_dir=site_dir,
        map_id=map_id,
        org_slug=org_slug,
        display_name=display_name,
    )
    publish_script = PUBLISH_SCRIPT_TEMPLATE.format(
        sites_repo=sites_repo,
        site_dir=site_dir,
        org_slug=org_slug,
    )
    if output_dir:
        build_path = os.path.join(output_dir, "deploy-1-build.sh")
        publish_path = os.path.join(output_dir, "deploy-2-publish.sh")
        for path, text in ((build_path, build_script), (publish_path, publish_script)):
            with open(path, "w") as f:
                f.write(text)
            os.chmod(path, 0o755)
    return build_script, publish_script


def print_manual_checklist(org_slug, domain):
    """Print the Cloudflare-dashboard-only steps that can't be scripted.

    Confirmed against real screenshots of the current dashboard (Sep 2026):
    "Set up a custom domain" is one combined flow that proposes and creates
    the CNAME itself -- there is no separate DNS-tab step to do by hand
    anymore (an earlier version of this checklist had one; it's gone).
    """
    print(f"""
Manual steps (Cloudflare dashboard -- need dashboard access or an elevated API token):
  1. Workers & Pages -> {org_slug} -> Custom domains -> "Set up a custom domain"
  2. Enter {domain}, continue to "Configure DNS" -- Cloudflare shows you the
     CNAME record it's about to add (Name: {org_slug}, Target: {org_slug}.pages.dev)
     -- then click "Activate Domain". Nothing to do in a separate DNS tab.
  3. Status shows "Initializing". Cloudflare's own UI warns "up to 48 hours",
     but for a strollopia.com-zone domain it's typically ~1-2 minutes to flip
     to "Active" with SSL enabled. Then run:
       python tools/check_live.py {domain}
""")


def main(argv=None):
    """CLI: resolve an org's map pk from the live API and write the two
    deploy scripts.

    Reads display_name/org_domain_name from the org's own org-setup.yaml
    so the only required argument is the org_slug -- everything else
    (map pk, domain) is looked up, not retyped by hand.
    """
    parser = argparse.ArgumentParser(
        description="Generate reviewable deploy-1-build.sh/deploy-2-publish.sh for an already-imported org.",
    )
    parser.add_argument("org_slug", help="Directory label under org-data/ (e.g. 'ca-nova-scotia-kingston')")
    parser.add_argument("--map-name", default="main-map",
                         help="org_map_name to deploy (default: main-map)")
    parser.add_argument("--sites-repo", default="../strollopia-sites",
                         help="Path to a strollopia-sites checkout (default: ../strollopia-sites)")
    parser.add_argument("--output-dir", default="org-data",
                         help="Base org-data directory (default: org-data)")
    parser.add_argument("--no-checklist", action="store_true",
                         help="Skip printing the manual Cloudflare checklist (for callers, "
                              "like go_live_wizard.sh, that present it themselves as its own step)")
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

    org_output_dir = os.path.join(args.output_dir, args.org_slug)
    generate_deploy_scripts(args.org_slug, display_name, map_id, args.sites_repo, output_dir=org_output_dir)
    print(f"Written {org_output_dir}/deploy-1-build.sh and {org_output_dir}/deploy-2-publish.sh (map pk {map_id})")
    if not args.no_checklist:
        print_manual_checklist(args.org_slug, org_domain_name)
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
