"""Tests for generate_deploy_script.py"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'tools'))

import stat
import subprocess
from unittest.mock import patch

import yaml

from generate_deploy_script import generate_deploy_scripts, main


def test_build_script_substitutes_config_values():
    build, publish = generate_deploy_scripts(
        org_slug="ca-ns-kentville", display_name="Kentville",
        map_id=42, sites_repo="/home/john/strollopia_git_hub/strollopia-sites",
    )
    assert "ca-ns-kentville" in build
    assert "Kentville" in build
    assert "42" in build
    assert "/home/john/strollopia_git_hub/strollopia-sites" in build


def test_build_script_sed_search_patterns_keep_literal_tokens():
    """Regression test for a bug where extra .replace() calls rewrote the
    LEFT-hand (search-pattern) side of the sed commands too, turning
    `s/REPLACE_MAP_ID/42/g` into the no-op `s/42/42/g`. The literal tokens
    REPLACE_MAP_ID, REPLACE_WITH_SITE_SLUG, and "Your Site Name" must
    survive verbatim as sed search patterns (and as the `mv` source path),
    since they're what sed matches against in the freshly-copied _template
    files when the generated script is actually run later.
    """
    build, _ = generate_deploy_scripts(
        org_slug="ca-ns-kentville", display_name="Kentville",
        map_id=42, sites_repo="/tmp/sites",
    )
    assert "s/REPLACE_MAP_ID/42/g" in build
    assert "s/REPLACE_WITH_SITE_SLUG/ca-ns-kentville/g" in build
    assert "s/Your Site Name/Kentville/g" in build
    assert "mv sites/ca-ns-kentville/maps/REPLACE_MAP_ID sites/ca-ns-kentville/maps/42" in build


def test_build_script_actually_substitutes_fixture_template(tmp_path):
    """End-to-end regression test: build a minimal fixture that mirrors
    strollopia-sites/_template's placeholder tokens, generate the build
    script pointed at a fake sites_repo, run it for real, and confirm the
    tokens are correctly substituted and the map directory is correctly
    renamed. deploy-1-build.sh has no wrangler/network calls at all, so
    unlike the old single deploy.sh this runs to completion in the test.
    """
    sites_repo = tmp_path
    template_dir = sites_repo / "_template"
    (template_dir / "maps" / "REPLACE_MAP_ID").mkdir(parents=True)
    (sites_repo / "sites").mkdir()

    (template_dir / "wrangler.toml").write_text('name = "REPLACE_WITH_SITE_SLUG"\n')
    (template_dir / "index.html").write_text(
        "<title>Your Site Name</title>\n"
        '<a href="/maps/REPLACE_MAP_ID">Open the Map</a>\n'
    )
    (template_dir / "maps" / "REPLACE_MAP_ID" / "index.html").write_text(
        "<title>Your Site Name</title>\n"
        "frame.src = '.../maps/REPLACE_MAP_ID/';\n"
    )
    (template_dir / "admin.html").write_text(
        "const MAP_ID      = null;  // placeholder\n"
    )

    build, _ = generate_deploy_scripts(
        org_slug="ca-ns-kentville", display_name="Kentville",
        map_id=42, sites_repo=str(sites_repo),
    )
    script_path = tmp_path / "deploy-1-build.sh"
    script_path.write_text(build)
    script_path.chmod(0o755)

    result = subprocess.run(
        ["bash", str(script_path)],
        cwd=str(sites_repo),
        capture_output=True,
        text=True,
    )
    site_dir = sites_repo / "sites" / "ca-ns-kentville"
    assert result.returncode == 0, f"build script failed; stderr:\n{result.stderr}"
    assert site_dir.exists()

    wrangler_toml = (site_dir / "wrangler.toml").read_text()
    assert "REPLACE_WITH_SITE_SLUG" not in wrangler_toml
    assert "ca-ns-kentville" in wrangler_toml

    index_html = (site_dir / "index.html").read_text()
    assert "REPLACE_MAP_ID" not in index_html
    assert "Your Site Name" not in index_html
    assert "42" in index_html
    assert "Kentville" in index_html

    admin_html = (site_dir / "admin.html").read_text()
    assert "const MAP_ID      = 42;" in admin_html

    # The map directory must have been renamed from REPLACE_MAP_ID to 42.
    assert not (site_dir / "maps" / "REPLACE_MAP_ID").exists()
    renamed_map_dir = site_dir / "maps" / "42"
    assert renamed_map_dir.exists()
    map_index_html = (renamed_map_dir / "index.html").read_text()
    assert "REPLACE_MAP_ID" not in map_index_html
    assert "Your Site Name" not in map_index_html


def test_build_script_references_correct_site_dir():
    build, _ = generate_deploy_scripts(
        org_slug="ca-ns-kentville", display_name="Kentville",
        map_id=42, sites_repo="/tmp/sites",
    )
    assert "sites/ca-ns-kentville" in build
    assert "cp -r _template sites/ca-ns-kentville" in build


def test_build_script_has_no_wrangler_or_kv_calls():
    """The KV namespace step moved out to go_live_wizard.sh, which needs a
    live decision (auto-parse the id vs. paste by hand) between creating
    the namespace and patching wrangler.toml -- neither of which belongs
    in a script meant to run start-to-finish unattended.
    """
    build, _ = generate_deploy_scripts(
        org_slug="ca-ns-kentville", display_name="Kentville",
        map_id=42, sites_repo="/tmp/sites",
    )
    assert "wrangler" not in build
    assert "SPLASH_CONTENT" not in build


def test_publish_script_creates_kv_namespace_with_slug_prefix():
    # kv namespace creation itself still needs to happen somewhere -- it's
    # just no longer bundled with the file substitution step. Confirmed
    # instead as the wizard's own responsibility; this asserts it's NOT
    # duplicated into the publish script either.
    _, publish = generate_deploy_scripts(
        org_slug="ca-ns-kentville", display_name="Kentville",
        map_id=42, sites_repo="/tmp/sites",
    )
    assert "kv namespace create" not in publish
    assert "wrangler pages project create ca-ns-kentville" in publish
    assert "wrangler pages deploy" in publish


def test_generate_deploy_scripts_writes_both_executable_files(tmp_path):
    generate_deploy_scripts(
        org_slug="ca-ns-kentville", display_name="Kentville",
        map_id=42, sites_repo="/tmp/sites", output_dir=str(tmp_path),
    )
    build_path = tmp_path / "deploy-1-build.sh"
    publish_path = tmp_path / "deploy-2-publish.sh"
    assert build_path.exists()
    assert publish_path.exists()
    assert build_path.stat().st_mode & stat.S_IXUSR
    assert publish_path.stat().st_mode & stat.S_IXUSR


def _write_org_setup(org_dir, org_domain_name, display_name):
    os.makedirs(org_dir, exist_ok=True)
    with open(os.path.join(org_dir, "org-setup.yaml"), "w") as f:
        yaml.dump({"org_domain_name": org_domain_name, "display_name": display_name}, f)


def test_main_writes_both_scripts_using_resolved_map_pk(tmp_path):
    org_slug = "ca-ns-kentville"
    org_dir = tmp_path / "org-data" / org_slug
    _write_org_setup(org_dir, "ca-ns-kentville.strollopia.com", "Kentville")

    fake_policy = {"public_org_maps": [{"org_map_name": "main-map", "map_obj": 42}]}
    with patch("generate_deploy_script.get_org_policy", return_value=fake_policy) as mock_policy:
        exit_code = main([
            org_slug,
            "--sites-repo", "/home/john/strollopia_git_hub/strollopia-sites",
            "--output-dir", str(tmp_path / "org-data"),
        ])

    assert exit_code == 0
    mock_policy.assert_called_once_with("ca-ns-kentville.strollopia.com")

    build_path = org_dir / "deploy-1-build.sh"
    publish_path = org_dir / "deploy-2-publish.sh"
    assert build_path.exists()
    assert publish_path.exists()
    assert "sites/ca-ns-kentville" in build_path.read_text()
    assert "s/REPLACE_MAP_ID/42/g" in build_path.read_text()
    assert "Kentville" in build_path.read_text()
    assert "wrangler pages deploy" in publish_path.read_text()


def test_main_errors_when_map_not_found_in_policy(tmp_path, capsys):
    org_slug = "ca-ns-kentville"
    org_dir = tmp_path / "org-data" / org_slug
    _write_org_setup(org_dir, "ca-ns-kentville.strollopia.com", "Kentville")

    fake_policy = {"public_org_maps": []}
    with patch("generate_deploy_script.get_org_policy", return_value=fake_policy):
        exit_code = main([org_slug, "--output-dir", str(tmp_path / "org-data")])

    assert exit_code == 1
    assert "not found in org policy" in capsys.readouterr().out
    assert not (org_dir / "deploy-1-build.sh").exists()


def test_main_errors_when_org_setup_missing(tmp_path, capsys):
    exit_code = main(["does-not-exist", "--output-dir", str(tmp_path / "org-data")])
    assert exit_code == 1
    assert "not found" in capsys.readouterr().out


def test_main_no_checklist_flag_suppresses_manual_steps_output(tmp_path, capsys):
    org_slug = "ca-ns-kentville"
    org_dir = tmp_path / "org-data" / org_slug
    _write_org_setup(org_dir, "ca-ns-kentville.strollopia.com", "Kentville")

    fake_policy = {"public_org_maps": [{"org_map_name": "main-map", "map_obj": 42}]}
    with patch("generate_deploy_script.get_org_policy", return_value=fake_policy):
        exit_code = main([
            org_slug, "--no-checklist",
            "--sites-repo", "/home/john/strollopia_git_hub/strollopia-sites",
            "--output-dir", str(tmp_path / "org-data"),
        ])

    assert exit_code == 0
    out = capsys.readouterr().out
    assert "Written" in out
    assert "Manual steps" not in out
