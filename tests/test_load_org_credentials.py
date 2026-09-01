"""Tests for strollopia_import.load_org_credentials"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'tools'))

import pytest
import yaml
from strollopia_import import load_org_credentials


def test_load_org_credentials_merges_secrets_sidecar(tmp_path):
    # Regression test: load_org_credentials used to yaml.safe_load the
    # org-setup.yaml path directly, never checking for the secrets sidecar
    # that city_discover.py writes main_admin_email/main_admin_password
    # into -- every real import failed with "Missing required key" (or
    # silently used stale/wrong values) until this was fixed.
    yaml_path = tmp_path / "org-setup.yaml"
    yaml_path.write_text(yaml.dump({
        "org_domain_name": "test-town.strollopia.com",
        "main_admin_name": "Admin",
    }))
    (tmp_path / "org-setup.secrets.yaml").write_text(yaml.dump({
        "main_admin_email": "testtown1234@strollopia.com",
        "main_admin_password": "RealPassword123",
    }))

    creds = load_org_credentials(str(yaml_path))

    assert creds["org_domain_name"] == "test-town.strollopia.com"
    assert creds["main_admin_email"] == "testtown1234@strollopia.com"
    assert creds["main_admin_password"] == "RealPassword123"


def test_load_org_credentials_without_secrets_sidecar(tmp_path):
    # Legacy orgs set up before the sidecar existed still carry credentials
    # directly in org-setup.yaml.
    yaml_path = tmp_path / "org-setup.yaml"
    yaml_path.write_text(yaml.dump({
        "org_domain_name": "test-town.strollopia.com",
        "main_admin_email": "legacy@example.com",
        "main_admin_password": "changeme123",
    }))

    creds = load_org_credentials(str(yaml_path))

    assert creds["main_admin_email"] == "legacy@example.com"
    assert creds["main_admin_password"] == "changeme123"


def test_load_org_credentials_overrides_take_precedence(tmp_path):
    yaml_path = tmp_path / "org-setup.yaml"
    yaml_path.write_text(yaml.dump({"org_domain_name": "test-town.strollopia.com"}))
    (tmp_path / "org-setup.secrets.yaml").write_text(yaml.dump({
        "main_admin_email": "fromsidecar@strollopia.com",
        "main_admin_password": "fromsidecar",
    }))

    creds = load_org_credentials(
        str(yaml_path), email_override="override@example.com", password_override="override-pw",
    )

    assert creds["main_admin_email"] == "override@example.com"
    assert creds["main_admin_password"] == "override-pw"


def test_load_org_credentials_raises_when_missing(tmp_path):
    yaml_path = tmp_path / "org-setup.yaml"
    yaml_path.write_text(yaml.dump({"org_domain_name": "test-town.strollopia.com"}))

    with pytest.raises(ValueError):
        load_org_credentials(str(yaml_path))
