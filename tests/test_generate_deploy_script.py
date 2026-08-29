"""Tests for generate_deploy_script.py"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'tools'))

import stat
from generate_deploy_script import generate_deploy_script


def test_generated_script_substitutes_all_tokens():
    script = generate_deploy_script(
        org_slug="ca-ns-kentville", display_name="Kentville",
        map_id=42, sites_repo="/home/john/strollopia_git_hub/strollopia-sites",
    )
    assert "REPLACE_MAP_ID" not in script
    assert "REPLACE_WITH_SITE_SLUG" not in script
    assert "Your Site Name" not in script
    assert "ca-ns-kentville" in script
    assert "Kentville" in script
    assert "42" in script
    assert "/home/john/strollopia_git_hub/strollopia-sites" in script


def test_generated_script_references_correct_site_dir():
    script = generate_deploy_script(
        org_slug="ca-ns-kentville", display_name="Kentville",
        map_id=42, sites_repo="/tmp/sites",
    )
    assert "sites/ca-ns-kentville" in script
    assert "cp -r _template sites/ca-ns-kentville" in script


def test_generated_script_creates_kv_namespace_with_slug_prefix():
    script = generate_deploy_script(
        org_slug="ca-ns-kentville", display_name="Kentville",
        map_id=42, sites_repo="/tmp/sites",
    )
    assert 'ca-ns-kentville-SPLASH_CONTENT' in script


def test_generate_deploy_script_writes_executable_file(tmp_path):
    output_path = tmp_path / "deploy.sh"
    generate_deploy_script(
        org_slug="ca-ns-kentville", display_name="Kentville",
        map_id=42, sites_repo="/tmp/sites", output_path=str(output_path),
    )
    assert output_path.exists()
    mode = output_path.stat().st_mode
    assert mode & stat.S_IXUSR
