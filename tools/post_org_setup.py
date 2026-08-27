#!/usr/bin/env python3
"""Post an org-setup.yaml to the Strollopia server to create/initialize an organization.

Can be run standalone or called from the wizard.

Standalone usage:
    python tools/post_org_setup.py myorg.strollopia.com
    python tools/post_org_setup.py myorg.strollopia.com --output-dir org-data/
"""

import argparse
import getpass
import os
import sys

import yaml

from api_client import admin_login, initialize_org_from_yaml, login, print_api_base_url


def check_org_maps_have_data(yaml_path):
    """Warn about any org_maps entry with no import-schema.yaml/map-data.tsv yet.

    initialize_org_from_yaml will happily create a map with no content --
    the gap only surfaces later, as a confusing failure in the import step.
    Catching it here, before posting, is cheap.
    """
    with open(yaml_path) as f:
        org_creds = yaml.safe_load(f)
    org_maps = org_creds.get('org_maps') or {}
    if not org_maps:
        return
    map_root = os.path.dirname(yaml_path)
    incomplete = []
    for map_name in org_maps:
        map_dir = os.path.join(map_root, map_name)
        schema = os.path.join(map_dir, 'import-schema.yaml')
        data = os.path.join(map_dir, 'map-data.tsv')
        if not (os.path.exists(schema) and os.path.exists(data)):
            incomplete.append(map_name)
    if incomplete:
        print("WARNING: these org_maps entries have no import-schema.yaml/map-data.tsv yet:")
        for name in incomplete:
            print(f"  - {name}")
        print("They'll be created empty on the server with nothing to import.")
        print("Consider removing them from org_maps until their data is ready.\n")


def verify_org_admin_login(yaml_path):
    """Confirm the org admin defined in the YAML can actually log in.

    initialize_org_from_yaml does NOT reset the password of an
    already-existing user -- if this email/org combination was set up
    before (even with an old placeholder password), the account keeps
    its original password even after a successful post. Catching that
    here, right after posting, avoids discovering it much later during
    the data import.
    """
    with open(yaml_path) as f:
        org_creds = yaml.safe_load(f)
    email = org_creds.get('main_admin_email')
    password = org_creds.get('main_admin_password')
    org_domain_name = org_creds.get('org_domain_name')
    if not (email and password and org_domain_name):
        return

    print(f"\nVerifying org admin can log in with the password in {yaml_path} ...")
    try:
        login(email, password, org_domain_name)
        print("  OK: org admin login verified.")
    except RuntimeError:
        print("  WARNING: org admin login FAILED with the password in this YAML.")
        print("  This usually means the account already existed (from an earlier")
        print("  setup attempt) and kept its old password -- initialize_org_from_yaml")
        print("  does not change the password of an existing user.")
        print("  Before importing data, find/reset the account's real working")
        print("  password (e.g. an earlier placeholder value), or reset it through")
        print("  the actual admin backend -- then update this YAML to match, or pass")
        print("  --email/--password overrides to strollopia_import.py.")


def post_org_setup(yaml_path):
    """Prompt for super-admin credentials, log in, and post the YAML file.

    Returns True on success, False on failure.
    """
    print_api_base_url()
    check_org_maps_have_data(yaml_path)

    print("A Django super-admin account is required to create an organization.\n")
    email = input("Super-admin email: ").strip()
    if not email:
        print("No email provided. Aborted.")
        return False
    password = getpass.getpass("Super-admin password: ")
    if not password:
        print("No password provided. Aborted.")
        return False

    print(f"\nLogging in as {email} via admin.strollopia.com ...")
    token = admin_login(email, password)
    if not token:
        return False

    print("Login successful.")
    print(f"Posting {yaml_path} ...")
    success, data = initialize_org_from_yaml(yaml_path, token)
    if success:
        print(f"Organization created: {data}")
        verify_org_admin_login(yaml_path)
    else:
        print(f"Post failed: {data}")
    return success


def main():
    parser = argparse.ArgumentParser(
        description="Post an org-setup.yaml to the Strollopia server."
    )
    parser.add_argument(
        "org_domain_name",
        help="Org domain name (e.g. myorg.strollopia.com)",
    )
    parser.add_argument(
        "--output-dir",
        default="org-data/",
        help="Base directory for org data (default: org-data/)",
    )
    args = parser.parse_args()

    yaml_path = os.path.join(args.output_dir, args.org_domain_name, "org-setup.yaml")
    if not os.path.exists(yaml_path):
        print(f"Error: file not found: {yaml_path}")
        sys.exit(1)

    print(f"\n=== Post Org Setup: {args.org_domain_name} ===\n")
    print(f"YAML file: {yaml_path}\n")

    success = post_org_setup(yaml_path)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
