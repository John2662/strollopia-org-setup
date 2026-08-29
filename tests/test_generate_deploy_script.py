"""Tests for generate_deploy_script.py"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'tools'))

import shutil
import stat
import subprocess
from generate_deploy_script import generate_deploy_script


def test_generated_script_substitutes_config_values():
    script = generate_deploy_script(
        org_slug="ca-ns-kentville", display_name="Kentville",
        map_id=42, sites_repo="/home/john/strollopia_git_hub/strollopia-sites",
    )
    assert "ca-ns-kentville" in script
    assert "Kentville" in script
    assert "42" in script
    assert "/home/john/strollopia_git_hub/strollopia-sites" in script


def test_generated_script_sed_search_patterns_keep_literal_tokens():
    """Regression test for a bug where extra .replace() calls rewrote the
    LEFT-hand (search-pattern) side of the sed commands too, turning
    `s/REPLACE_MAP_ID/42/g` into the no-op `s/42/42/g`. The literal tokens
    REPLACE_MAP_ID, REPLACE_WITH_SITE_SLUG, and "Your Site Name" must
    survive verbatim as sed search patterns (and as the `mv` source path),
    since they're what sed matches against in the freshly-copied _template
    files when the generated script is actually run later.
    """
    script = generate_deploy_script(
        org_slug="ca-ns-kentville", display_name="Kentville",
        map_id=42, sites_repo="/tmp/sites",
    )
    assert "s/REPLACE_MAP_ID/42/g" in script
    assert "s/REPLACE_WITH_SITE_SLUG/ca-ns-kentville/g" in script
    assert "s/Your Site Name/Kentville/g" in script
    assert "mv sites/ca-ns-kentville/maps/REPLACE_MAP_ID sites/ca-ns-kentville/maps/42" in script


def test_generated_script_actually_substitutes_fixture_template(tmp_path):
    """End-to-end regression test: build a minimal fixture that mirrors
    strollopia-sites/_template's placeholder tokens, generate the deploy
    script pointed at a fake sites_repo, then replicate the script's
    copy/sed/mv steps against the fixture and confirm the tokens are
    correctly substituted and the map directory is correctly renamed.
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

    script = generate_deploy_script(
        org_slug="ca-ns-kentville", display_name="Kentville",
        map_id=42, sites_repo=str(sites_repo),
    )
    script_path = tmp_path / "deploy.sh"
    script_path.write_text(script)
    script_path.chmod(0o755)

    result = subprocess.run(
        ["bash", str(script_path)],
        input="fake-kv-namespace-id\n",
        cwd=str(sites_repo),
        capture_output=True,
        text=True,
    )
    # The script will fail once it reaches `npx wrangler ...` (not installed
    # / no network in this sandbox) -- that's fine, we only care that the
    # copy+sed+mv steps (which run first) succeeded before that point.
    site_dir = sites_repo / "sites" / "ca-ns-kentville"
    assert site_dir.exists(), (
        f"template was not copied; script stderr:\n{result.stderr}"
    )

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
