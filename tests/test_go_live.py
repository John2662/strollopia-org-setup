"""Tests for go_live.py's orchestration and stub behavior."""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'tools'))

from unittest.mock import patch
from go_live import main


def test_source_template_stub_stops_before_discovery():
    with patch("go_live.city_discover.run") as mock_run:
        result = main(["Kentville, NS", "--source", "template"])
    assert result == 1
    mock_run.assert_not_called()


def test_path_pwa_stops_after_import_before_deploy_script(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    with patch("go_live.city_discover.run") as mock_discover, \
         patch("go_live.post_org_setup", return_value=True) as mock_post, \
         patch("go_live.strollopia_import.main", return_value=0) as mock_import, \
         patch("go_live.generate_deploy_script") as mock_deploy, \
         patch("builtins.input", return_value=""):
        mock_discover.return_value = {
            "org_slug": "ca-ns-kentville", "org_dir": str(tmp_path / "ca-ns-kentville"),
            "domain": "ca-ns-kentville.strollopia.com", "display_name": "Kentville",
        }
        result = main(["Kentville, NS", "--path", "pwa"])

    assert result == 0
    mock_post.assert_called_once()
    mock_import.assert_called_once()
    mock_deploy.assert_not_called()


def test_dry_run_stops_before_deploy_script(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    with patch("go_live.city_discover.run") as mock_discover, \
         patch("go_live.post_org_setup", return_value=True), \
         patch("go_live.strollopia_import.main", return_value=0) as mock_import, \
         patch("go_live.generate_deploy_script") as mock_deploy, \
         patch("builtins.input", return_value=""):
        mock_discover.return_value = {
            "org_slug": "ca-ns-kentville", "org_dir": str(tmp_path / "ca-ns-kentville"),
            "domain": "ca-ns-kentville.strollopia.com", "display_name": "Kentville",
        }
        result = main(["Kentville, NS", "--dry-run", "--sites-repo", "/tmp/sites"])

    assert result == 0
    assert "--dry-run" in mock_import.call_args[0][0]
    mock_deploy.assert_not_called()


def test_org_creation_failure_stops_the_pipeline(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    with patch("go_live.city_discover.run") as mock_discover, \
         patch("go_live.post_org_setup", return_value=False), \
         patch("go_live.strollopia_import.main") as mock_import, \
         patch("builtins.input", return_value=""):
        mock_discover.return_value = {
            "org_slug": "ca-ns-kentville", "org_dir": str(tmp_path / "ca-ns-kentville"),
            "domain": "ca-ns-kentville.strollopia.com", "display_name": "Kentville",
        }
        result = main(["Kentville, NS"])

    assert result == 1
    mock_import.assert_not_called()


def test_import_failure_stops_before_deploy_script(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    with patch("go_live.city_discover.run") as mock_discover, \
         patch("go_live.post_org_setup", return_value=True), \
         patch("go_live.strollopia_import.main", return_value=1), \
         patch("go_live.generate_deploy_script") as mock_deploy, \
         patch("builtins.input", return_value=""):
        mock_discover.return_value = {
            "org_slug": "ca-ns-kentville", "org_dir": str(tmp_path / "ca-ns-kentville"),
            "domain": "ca-ns-kentville.strollopia.com", "display_name": "Kentville",
        }
        result = main(["Kentville, NS", "--sites-repo", "/tmp/sites"])

    assert result == 1
    mock_deploy.assert_not_called()
