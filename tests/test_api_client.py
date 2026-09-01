"""Tests for api_client.py"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'tools'))

import yaml
from unittest.mock import patch, MagicMock
from api_client import initialize_org_from_config, get_map_pois


def test_initialize_org_from_config_posts_dumped_yaml():
    config = {
        "org_domain_name": "test.strollopia.com",
        "main_admin_email": "newminas1234@strollopia.com",
        "main_admin_password": "RealPassword123",
    }
    with patch("api_client.requests.post") as mock_post:
        mock_resp = MagicMock()
        mock_resp.status_code = 201
        mock_resp.json.return_value = {"org_domain_name": "test.strollopia.com"}
        mock_post.return_value = mock_resp

        success, data = initialize_org_from_config(config, "org-setup.yaml", token="fake-token")

    assert success is True
    assert data == {"org_domain_name": "test.strollopia.com"}

    _, kwargs = mock_post.call_args
    assert kwargs["headers"] == {"Authorization": "Token fake-token"}
    filename, file_bytes, content_type = kwargs["files"]["file"]
    assert filename == "org-setup.yaml"
    assert content_type == "text/yaml"
    posted_config = yaml.safe_load(file_bytes)
    assert posted_config == config


def test_initialize_org_from_config_returns_false_on_failure():
    config = {"org_domain_name": "test.strollopia.com"}
    with patch("api_client.requests.post") as mock_post:
        mock_resp = MagicMock()
        mock_resp.status_code = 400
        mock_resp.json.return_value = {"main_admin_email": ["This field is required."]}
        mock_post.return_value = mock_resp

        success, data = initialize_org_from_config(config, "org-setup.yaml", token="fake-token")

    assert success is False
    assert "400" in data


def test_get_map_pois_uses_live_list_endpoint_not_map_json():
    # Regression test: get_map_pois used to read /api/content/maps/<pk>/'s
    # map_json.pois, a pre-rendered snapshot that doesn't reflect recently
    # created POIs -- confirmed by actually importing (it returned 0 POIs
    # right after 223 had just been created), which made skip_existing
    # think nothing existed yet and silently re-created ~240 duplicates on
    # a second import run. /api/content/pois/ is live and doesn't have
    # this problem.
    with patch("api_client.requests.get") as mock_get:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = [
            {"pk": 1, "name": "Tim Hortons"},
            {"pk": 2, "name": "Irving Oil"},
        ]
        mock_get.return_value = mock_resp

        pois = get_map_pois("fake-token", "test.strollopia.com")

    args, kwargs = mock_get.call_args
    assert "api/content/pois/" in args[0]
    assert "api/content/maps/" not in args[0]
    assert [p["properties"]["name"] for p in pois] == ["Tim Hortons", "Irving Oil"]


def test_get_map_pois_returns_empty_on_failure():
    with patch("api_client.requests.get") as mock_get:
        mock_resp = MagicMock()
        mock_resp.status_code = 500
        mock_get.return_value = mock_resp

        pois = get_map_pois("fake-token", "test.strollopia.com")

    assert pois == []
