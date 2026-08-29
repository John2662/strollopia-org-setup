#!/usr/bin/env python3
"""HTTP-level check that a deployed trial site is live and correctly wired.

Run by hand after completing the manual Cloudflare custom-domain/DNS steps
printed by generate_deploy_script.py's print_manual_checklist -- this is
not called automatically by go_live.py.

Usage:
    python tools/check_live.py ca-ns-kentville.strollopia.com
    python tools/check_live.py ca-ns-kentville.strollopia.com --map-id 42
"""
import argparse
import sys

import requests


def check_live(domain, map_id=None, timeout=10):
    """Return True if the trial site is live and looks like our template.

    Prints a diagnosis either way. If map_id is given, also checks that the
    map page responds and references the right embed URL.
    """
    url = f"https://{domain}/"
    try:
        resp = requests.get(url, timeout=timeout)
    except requests.exceptions.RequestException as exc:
        print(f"FAIL: could not reach {url}: {exc}")
        return False

    if resp.status_code != 200:
        print(f"FAIL: {url} returned HTTP {resp.status_code}")
        return False

    if "Open the Map" not in resp.text:
        print(f"FAIL: {url} responded 200 but doesn't look like the strollopia "
              f"template (missing \"Open the Map\" link)")
        return False

    print(f"OK: {url} is live and looks like the strollopia template.")

    if map_id is None:
        return True

    map_url = f"https://{domain}/maps/{map_id}/"
    try:
        map_resp = requests.get(map_url, timeout=timeout)
    except requests.exceptions.RequestException as exc:
        print(f"FAIL: could not reach {map_url}: {exc}")
        return False

    if map_resp.status_code != 200:
        print(f"FAIL: {map_url} returned HTTP {map_resp.status_code}")
        return False

    if f"/embed/maps/{map_id}/" not in map_resp.text:
        print(f"FAIL: {map_url} responded 200 but doesn't reference "
              f"/embed/maps/{map_id}/ -- MAP_ID may be wrong.")
        return False

    print(f"OK: {map_url} is live and correctly wired to map {map_id}.")
    return True


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Check that a deployed trial site is live and correctly wired."
    )
    parser.add_argument("domain", help="e.g. ca-ns-kentville.strollopia.com")
    parser.add_argument("--map-id", type=int, default=None,
                        help="Also check the map page at /maps/<id>/")
    args = parser.parse_args(argv)

    ok = check_live(args.domain, map_id=args.map_id)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
