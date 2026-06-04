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

from api_client import admin_login, initialize_org_from_yaml, print_api_base_url


def post_org_setup(yaml_path):
    """Prompt for super-admin credentials, log in, and post the YAML file.

    Returns True on success, False on failure.
    """
    print_api_base_url()

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
