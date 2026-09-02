#!/usr/bin/env python3
"""Generate a go-live checklist for one town, showing which steps are
already done and which remain -- so a fresh session doesn't need to be
told the current state by hand.

Checks real state (prod org, imported data, local site files, live
domain) rather than assuming a fresh town; safe to re-run at any point
in the launch process. See docs/generate_todo.md for full usage and how
this fits with city_discover.py's own Google geocoding step (this tool
never talks to Google -- see that doc for why).

Usage:
    python tools/generate_todo.py ca-nova-scotia-annapolis-royal
    python tools/generate_todo.py --country CA --province "Nova Scotia" --town "Annapolis Royal"
"""
import argparse
import csv
import os
import sys

import requests

from api_client import get_api_base_url, get_org_policy, login
from city_discover import make_domain, domain_to_slug
from org_config import load_org_config


def resolve_org_slug(org_slug, country, province, town):
    """Return an org_slug from either the slug itself or country/province/town.

    country/province/town are composed the same way city_discover.py's own
    make_domain() would, for the common case. This does NOT re-derive
    anything from Google -- if the real org was created with a custom
    --domain override in city_discover.py, its directory name won't match
    this composition, and org_slug must be passed directly instead.
    """
    if org_slug:
        return org_slug
    if not (country and province and town):
        raise ValueError(
            "Provide org_slug, or all three of --country/--province/--town."
        )
    return domain_to_slug(make_domain(country, province, town))


def _org_posted(domain):
    try:
        get_org_policy(domain)
        return True
    except Exception:
        return False


def _local_row_count(org_dir):
    tsv_path = os.path.join(org_dir, "main-map", "map-data.en.tsv")
    if not os.path.exists(tsv_path):
        return None
    with open(tsv_path, newline="", encoding="utf-8") as f:
        return sum(1 for _ in csv.DictReader(f, delimiter="\t"))


def _data_imported(org_dir, domain):
    """Return (status, detail) where status is True/False/None (unknown)."""
    yaml_path = os.path.join(org_dir, "org-setup.yaml")
    if not os.path.exists(yaml_path):
        return None, "no org-setup.yaml found locally"
    config = load_org_config(yaml_path)
    email = config.get("main_admin_email")
    password = config.get("main_admin_password")
    if not (email and password):
        return None, "no admin credentials found locally"

    try:
        token = login(email, password, domain)
    except RuntimeError as exc:
        return None, f"admin login failed ({exc}) -- credentials may be out of sync, check manually"

    resp = requests.get(
        f"{get_api_base_url()}api/content/pois/?org_domain_name={domain}",
        headers={"Authorization": f"Token {token}"},
    )
    if resp.status_code != 200:
        return None, f"could not list POIs (HTTP {resp.status_code})"
    live_count = len(resp.json())
    expected = _local_row_count(org_dir)
    if expected is None:
        return live_count > 0, f"{live_count} POIs live"
    if live_count >= expected:
        return True, f"{live_count} POIs live (expected {expected})"
    return False, f"{live_count}/{expected} POIs live -- import incomplete or in progress"


def _site_live(domain):
    try:
        resp = requests.get(f"https://{domain}/", timeout=10)
        return resp.status_code == 200 and "Open the Map" in resp.text
    except requests.exceptions.RequestException:
        return False


def build_checklist(org_slug, output_dir, sites_repo):
    org_dir = os.path.join(output_dir, org_slug)
    domain = f"{org_slug}.strollopia.com"
    site_dir = os.path.join(sites_repo, "sites", org_slug)

    posted = _org_posted(domain)
    if posted:
        imported, imported_detail = _data_imported(org_dir, domain)
    else:
        imported, imported_detail = None, "org not posted yet"
    deploy_script_exists = os.path.exists(os.path.join(org_dir, "deploy.sh"))
    site_dir_exists = os.path.isdir(site_dir)
    site_live = _site_live(domain) if posted else False

    rows = [
        (1, "Post org to prod (post_org_setup.py)", "You (super-admin login)", posted),
        (2, f"Import POI data (strollopia_import.py) -- {imported_detail}",
         "You, or I can run it (reads secrets file)", imported),
        (3, "Generate deploy.sh", "I can do this", deploy_script_exists),
        (4, "Run deploy.sh (wrangler)", "You (Cloudflare/wrangler login)", site_dir_exists),
        (5, "Attach custom domain + DNS CNAME", "You (Cloudflare dashboard)", site_live),
        (6, "Confirm with check_live.py", "I can do this", site_live),
    ]
    return domain, rows


def print_checklist(org_slug, output_dir, sites_repo):
    domain, rows = build_checklist(org_slug, output_dir, sites_repo)
    print(f"\n=== Go-live checklist: {org_slug} ({domain}) ===\n")
    for num, step, who, status in rows:
        mark = "[done]" if status is True else "[?]" if status is None else "[pending]"
        print(f"{num}. {mark:<9} {step}")
        print(f"   {'':<9} Who: {who}")
    print()


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Generate a go-live checklist for one town, showing done vs pending steps."
    )
    parser.add_argument("org_slug", nargs="?", default=None,
                        help="e.g. ca-nova-scotia-annapolis-royal")
    parser.add_argument("--country", default=None, help="e.g. CA (used with --province/--town)")
    parser.add_argument("--province", default=None, help="e.g. 'Nova Scotia'")
    parser.add_argument("--town", default=None, help="e.g. 'Annapolis Royal'")
    parser.add_argument("--output-dir", default="org-data",
                        help="Base output directory (default: org-data)")
    parser.add_argument("--sites-repo", default="../strollopia-sites",
                        help="Path to a strollopia-sites checkout (default: ../strollopia-sites)")
    args = parser.parse_args(argv)

    try:
        org_slug = resolve_org_slug(args.org_slug, args.country, args.province, args.town)
    except ValueError as exc:
        parser.error(str(exc))

    print_checklist(org_slug, args.output_dir, args.sites_repo)
    return 0


if __name__ == "__main__":
    sys.exit(main())
