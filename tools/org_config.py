"""Shared helper for loading an org's on-disk config merged with its
gitignored secrets sidecar (main_admin_email/main_admin_password).

Lives in its own module because both post_org_setup.py and
strollopia_import.py need it, and post_org_setup.py already imports from
strollopia_import.py (find_schemas_in_map_dir, find_data_path_for_schema)
-- putting this there too would create an import cycle.
"""
import os

import yaml


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
