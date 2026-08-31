#!/usr/bin/env python3
"""Go-live pipeline: city name -> provisioned org+data -> generated deploy script.

Chains city_discover.py (Google Places + OSM discovery), post_org_setup.py
(org creation), and strollopia_import.py (POI import) together, then hands
off to generate_deploy_script.py for the strollopia-sites/Cloudflare side.
Each stage is also independently runnable with its own tool, the same way
it's always been done -- this script only sequences them and stops on the
first failure.

Usage:
    python tools/go_live.py "Kentville, NS" --sites-repo ../strollopia-sites
    python tools/go_live.py "Kentville, NS" --dry-run
"""
import argparse
import os
import sys

import city_discover
import strollopia_import
from post_org_setup import post_org_setup
from api_client import get_org_policy
from strollopia_import import get_map_pk_from_policy
from generate_deploy_script import generate_deploy_script, print_manual_checklist


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Discover a city's POIs, provision the org, and generate "
                    "the deploy script for a strollopia.com trial site."
    )
    parser.add_argument("city", help='City name passed to geocoder (e.g. "Kentville, NS")')
    parser.add_argument("--api-key", default=os.environ.get("GOOGLE_PLACES_API_KEY"),
                        help="Google Places API key (or set GOOGLE_PLACES_API_KEY env var)")
    parser.add_argument("--domain", default=None,
                        help="Explicit org domain. If omitted, auto-generated from geocoder result.")
    parser.add_argument("--languages", default="en",
                        help="Comma-separated language codes (default: en)")
    parser.add_argument("--maps", default="businesses,landmarks,public-art,parks",
                        help="Comma-separated presets to run (default: all four)")
    parser.add_argument("--source", choices=["google", "template"], default="google",
                        help="POI data source. 'template' (org-supplied CSV) is not yet implemented.")
    parser.add_argument("--path", choices=["map", "pwa"], default="map",
                        help="Deploy target. 'pwa' is not yet implemented.")
    parser.add_argument("--sites-repo", default=None,
                        help="Path to a strollopia-sites checkout (required for --path map)")
    parser.add_argument("--output-dir", default="org-data",
                        help="Base output directory (default: org-data)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Run import in dry-run mode; stop before deploy-script generation")
    parser.add_argument("--force", action="store_true",
                        help="Overwrite existing discovery output files")
    args = parser.parse_args(argv)

    if args.source == "template":
        print("--source template is not yet implemented.")
        print("Build org-setup.yaml, map-data.tsv, and import-schema.yaml by hand")
        print("(see README.md), then run post_org_setup.py / strollopia_import.py")
        print("directly against that directory.")
        return 1

    languages = [lang.strip() for lang in args.languages.split(",") if lang.strip()]
    preset_names = [name.strip() for name in args.maps.split(",") if name.strip()]

    print("=== Stage 1: Discovery ===")
    result = city_discover.run(
        city=args.city, api_key=args.api_key, domain=args.domain,
        languages=languages, preset_names=preset_names,
        init=True, no_photos=False, force=args.force, output_dir=args.output_dir,
    )
    org_slug = result["org_slug"]
    domain = result["domain"]
    display_name = result["display_name"]
    yaml_path = os.path.join(args.output_dir, org_slug, "org-setup.yaml")

    print(f"\nmain_admin_email is blank in {yaml_path} -- fill it in before continuing.")
    input("Press Enter once org-setup.yaml is ready to post (Ctrl+C to stop here): ")

    print("\n=== Stage 2: Org creation ===")
    if not post_org_setup(yaml_path):
        print("\nOrg creation failed -- fix the error above, then re-run:")
        print(f"  python tools/post_org_setup.py {org_slug}")
        return 1

    print("\n=== Stage 3: Data import ===")
    import_argv = [os.path.join(args.output_dir, org_slug), "--all-maps"]
    if args.dry_run:
        import_argv.append("--dry-run")
    import_result = strollopia_import.main(import_argv)
    if import_result != 0:
        print("\nImport failed -- fix the error above, then re-run:")
        print(f"  python tools/strollopia_import.py {os.path.join(args.output_dir, org_slug)} --all-maps")
        return 1

    if args.dry_run:
        print("\n--dry-run: stopping before deploy-script generation.")
        return 0

    if args.path == "pwa":
        print(f"\n--path pwa is not yet implemented.")
        print(f"Org and data are provisioned under '{org_slug}'. Finish onboarding")
        print("manually via strollopia_pwa's own setup for the PWA deploy path.")
        return 0

    print("\n=== Stage 4: Deploy script generation ===")
    if not args.sites_repo:
        print("--sites-repo is required for --path map (path to a strollopia-sites checkout).")
        return 1

    org_policy = get_org_policy(domain)
    # All presets discover into one combined "main-map" (see
    # city_discover.write_org_setup) regardless of which presets were run.
    primary_map_dir = "main-map"
    map_id = get_map_pk_from_policy(org_policy, primary_map_dir)
    if map_id is None:
        print(f"Could not find map pk for '{primary_map_dir}' in org policy -- "
              f"check the org was created correctly.")
        return 1

    script_path = os.path.join(args.output_dir, org_slug, "deploy.sh")
    generate_deploy_script(
        org_slug=org_slug, display_name=display_name, map_id=map_id,
        sites_repo=args.sites_repo, output_path=script_path,
    )
    print(f"Deploy script written to: {script_path}")
    print("Review it, then run it to deploy the trial site.")
    print_manual_checklist(org_slug, domain)

    return 0


if __name__ == "__main__":
    sys.exit(main())
