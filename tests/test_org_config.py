"""Tests for org_config.py"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'tools'))

import yaml
from org_config import load_org_config, secrets_path_for


def test_load_org_config_merges_secrets_sidecar(tmp_path):
    yaml_path = tmp_path / "org-setup.yaml"
    yaml_path.write_text(yaml.dump({
        "org_domain_name": "test.strollopia.com",
        "main_admin_name": "Admin",
    }))
    (tmp_path / "org-setup.secrets.yaml").write_text(yaml.dump({
        "main_admin_email": "newminas1234@strollopia.com",
        "main_admin_password": "RealPassword123",
    }))

    config = load_org_config(str(yaml_path))

    assert config["org_domain_name"] == "test.strollopia.com"
    assert config["main_admin_email"] == "newminas1234@strollopia.com"
    assert config["main_admin_password"] == "RealPassword123"


def test_load_org_config_without_secrets_sidecar(tmp_path):
    # Orgs set up before the sidecar existed still carry credentials
    # directly in org-setup.yaml - must keep working with no sidecar present.
    yaml_path = tmp_path / "org-setup.yaml"
    yaml_path.write_text(yaml.dump({
        "org_domain_name": "test.strollopia.com",
        "main_admin_email": "legacy@example.com",
        "main_admin_password": "changeme123",
    }))

    config = load_org_config(str(yaml_path))

    assert config["main_admin_email"] == "legacy@example.com"
    assert config["main_admin_password"] == "changeme123"


def test_secrets_path_for():
    path = secrets_path_for("org-data/newminas/org-setup.yaml")
    assert path == "org-data/newminas/org-setup.secrets.yaml"
