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
import textwrap

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

    # Each row: (num, step text -- the exact command where one exists,
    # who, status, dynamic detail shown under the status mark)
    rows = [
        (1, f"python tools/post_org_setup.py {org_slug}  (USE_PROD=1)",
         "You (super-admin login)", posted, None),
        (2, f"python tools/strollopia_import.py {org_dir}/ --all-maps\n"
            f"(no --email/--password needed, reads the secrets file automatically)",
         "You, or I can run it (reads secrets file)", imported, imported_detail),
        (3, "Generate deploy.sh once the map pk is known",
         "I can do this", deploy_script_exists, None),
        (4, f"bash {org_dir}/deploy.sh\n(watch for the KV JSON→TOML gotcha, see ONBOARDING.md)",
         "You (Cloudflare/wrangler login)", site_dir_exists, None),
        (5, "Attach custom domain + create DNS CNAME (Cloudflare dashboard)",
         "You (Cloudflare dashboard)", site_live, None),
        (6, f"python tools/check_live.py {domain}",
         "I can do this", site_live, None),
    ]
    return domain, rows


def _wrap_lines(text, width):
    """Wrap text to width, respecting existing newlines as hard breaks.

    break_on_hyphens=False so slugs like ca-nova-scotia-annapolis-royal
    never split mid-word -- these lines are meant to be copy-pasted as
    real commands, and a hyphen-broken slug pastes as a broken command.
    """
    lines = []
    for para in text.split("\n"):
        wrapped = textwrap.wrap(
            para, width=width, break_on_hyphens=False, break_long_words=False,
        ) or [""]
        lines.extend(wrapped)
    return lines


def _render_table(headers, rows, widths):
    """Render a Unicode box-drawing table. rows: list of list-of-cell-strings
    (already the right length); cells may contain embedded newlines."""
    def border(left, mid, right, fill="─"):
        return left + mid.join(fill * (w + 2) for w in widths) + right

    def render_row(cells):
        wrapped_cells = [_wrap_lines(str(c), w) for c, w in zip(cells, widths)]
        height = max(len(wc) for wc in wrapped_cells)
        lines = []
        for i in range(height):
            parts = []
            for wc, w in zip(wrapped_cells, widths):
                text = wc[i] if i < len(wc) else ""
                parts.append(f" {text:<{w}} ")
            lines.append("│" + "│".join(parts) + "│")
        return "\n".join(lines)

    out = [border("┌", "┬", "┐")]
    out.append(render_row(headers))
    out.append(border("├", "┼", "┤"))
    for row in rows:
        out.append(render_row(row))
        out.append(border("├", "┼", "┤"))
    out[-1] = border("└", "┴", "┘")
    return "\n".join(out)


def print_checklist(org_slug, output_dir, sites_repo):
    domain, rows = build_checklist(org_slug, output_dir, sites_repo)
    print(f"\n=== Go-live checklist: {org_slug} ({domain}) ===\n")

    table_rows = []
    for num, step, who, status, detail in rows:
        mark = "[done]" if status is True else "[?]" if status is None else "[pending]"
        status_cell = mark if detail is None else f"{mark}\n{detail}"
        table_rows.append([str(num), status_cell, step, who])

    print(_render_table(["#", "Status", "Step", "Who"], table_rows, widths=[3, 18, 74, 26]))
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
