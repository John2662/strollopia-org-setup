"""Tests for org_slug/org_domain_name decoupling in org_yaml_wizard.py"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'tools'))

from org_yaml_wizard import (
    _draft_path, _save_draft, _load_draft, _delete_draft, write_org_setup,
)


def test_draft_path_uses_slug_not_domain(tmp_path):
    path = _draft_path(str(tmp_path), "kentville")
    assert path == os.path.join(str(tmp_path), "kentville", ".org-setup-draft.yaml")


def test_save_and_load_draft_roundtrip(tmp_path):
    _save_draft({"org_domain_name": "kentville.strollopia.com", "_wizard_step": 3},
                str(tmp_path), "kentville")
    config, step = _load_draft(str(tmp_path), "kentville")
    assert config["org_domain_name"] == "kentville.strollopia.com"
    assert step == 3


def test_delete_draft(tmp_path):
    _save_draft({"_wizard_step": 1}, str(tmp_path), "kentville")
    _delete_draft(str(tmp_path), "kentville")
    config, step = _load_draft(str(tmp_path), "kentville")
    assert config is None


def test_write_org_setup_uses_slug_for_directory(tmp_path):
    config = {
        "org_domain_name": "at-tirol-innsbruck.strollopia.com",
        "_org_slug": "at-tirol-innsbruck",
        "org_maps": {"main-map": {"is_public": True}},
    }
    path = write_org_setup(config, str(tmp_path))
    assert path == str(tmp_path / "at-tirol-innsbruck" / "org-setup.yaml")
    assert os.path.isdir(tmp_path / "at-tirol-innsbruck" / "main-map" / "media")


def test_write_org_setup_falls_back_to_domain_first_label(tmp_path):
    # No explicit _org_slug (e.g. a YAML written before this change) — falls
    # back to the domain's first label, same as before this task.
    config = {"org_domain_name": "kentville.strollopia.com", "org_maps": {}}
    path = write_org_setup(config, str(tmp_path))
    assert path == str(tmp_path / "kentville" / "org-setup.yaml")


def test_write_org_setup_strips_internal_slug_key(tmp_path):
    config = {
        "org_domain_name": "kentville.strollopia.com",
        "_org_slug": "kentville",
        "org_maps": {},
    }
    path = write_org_setup(config, str(tmp_path))
    with open(path) as f:
        content = f.read()
    assert "_org_slug" not in content
