#!/usr/bin/env python3
"""Post an org-setup.yaml to the Strollopia server to create/initialize an organization.

Can be run standalone or called from the wizard.

Standalone usage:
    python tools/post_org_setup.py kentville
    python tools/post_org_setup.py kentville --output-dir org-data/

The org_slug is the directory label (e.g. 'kentville'), not the domain name.
The runtime org_domain_name is read from the org-setup.yaml inside that directory.
"""

import argparse
import getpass
import os
import sys

import yaml

from api_client import admin_login, initialize_org_from_config, login, print_api_base_url
from strollopia_import import find_schemas_in_map_dir, find_data_path_for_schema


def secrets_path_for(yaml_path):
    """Return the gitignored secrets sidecar path next to a given org-setup.yaml."""
    return os.path.join(os.path.dirname(yaml_path), "org-setup.secrets.yaml")


def load_org_config(yaml_path):
    """Load org-setup.yaml merged with its secrets sidecar, if one exists.

    main_admin_email/main_admin_password live in the gitignored
    org-setup.secrets.yaml (see city_discover.py) rather than the committed
    org-setup.yaml, so anything that needs those fields must go through
    this rather than loading yaml_path alone. Orgs set up before the
    sidecar existed still carry those fields directly in org-setup.yaml,
    which this also handles fine since the sidecar is optional.
    """
    with open(yaml_path) as f:
        config = yaml.safe_load(f) or {}
    secrets_path = secrets_path_for(yaml_path)
    if os.path.exists(secrets_path):
        with open(secrets_path) as f:
            config.update(yaml.safe_load(f) or {})
    return config


def check_org_maps_have_data(yaml_path):
    """Warn about any org_maps entry with no ready import-schema/map-data yet.

    initialize_org_from_config will happily create a map with no content --
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
        ready = False
        for schema_path in find_schemas_in_map_dir(map_dir):
            try:
                find_data_path_for_schema(map_dir, schema_path)
                ready = True
                break
            except FileNotFoundError:
                continue
        if not ready:
            incomplete.append(map_name)
    if incomplete:
        print("WARNING: these org_maps entries have no ready import-schema/map-data yet:")
        for name in incomplete:
            print(f"  - {name}")
        print("They'll be created empty on the server with nothing to import.")
        print("Consider removing them from org_maps until their data is ready.\n")


def verify_org_admin_login(yaml_path):
    """Confirm the org admin defined in the org config can actually log in.

    initialize_org_from_config does NOT reset the password of an
    already-existing user -- if this email/org combination was set up
    before (even with an old placeholder password), the account keeps
    its original password even after a successful post. Catching that
    here, right after posting, avoids discovering it much later during
    the data import.
    """
    org_creds = load_org_config(yaml_path)
    email = org_creds.get('main_admin_email')
    password = org_creds.get('main_admin_password')
    org_domain_name = org_creds.get('org_domain_name')
    if not (email and password and org_domain_name):
        return

    print(f"\nVerifying org admin can log in with email {email} ...")
    try:
        login(email, password, org_domain_name)
        print("  OK: org admin login verified.")
    except RuntimeError:
        print("  WARNING: org admin login FAILED with this password.")
        print("  This usually means the account already existed (from an earlier")
        print("  setup attempt) and kept its old password -- initialize_org_from_config")
        print("  does not change the password of an existing user.")
        print("  Before importing data, find/reset the account's real working")
        print("  password (e.g. an earlier placeholder value), or reset it through")
        print("  the actual admin backend -- then update the secrets file to match, or")
        print("  pass --email/--password overrides to strollopia_import.py.")


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
    config = load_org_config(yaml_path)
    success, data = initialize_org_from_config(config, os.path.basename(yaml_path), token)
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
        "org_slug",
        help="Directory label for this org (e.g. 'kentville'). The runtime domain is read from org-setup.yaml.",
    )
    parser.add_argument(
        "--output-dir",
        default="org-data/",
        help="Base directory for org data (default: org-data/)",
    )
    args = parser.parse_args()

    yaml_path = os.path.join(args.output_dir, args.org_slug, "org-setup.yaml")
    if not os.path.exists(yaml_path):
        print(f"Error: file not found: {yaml_path}")
        sys.exit(1)

    with open(yaml_path) as f:
        org_domain_name = (yaml.safe_load(f) or {}).get('org_domain_name', args.org_slug)

    print(f"\n=== Post Org Setup: {org_domain_name} (slug: {args.org_slug}) ===\n")
    print(f"YAML file: {yaml_path}\n")

    success = post_org_setup(yaml_path)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
