"""Tests for api_client.py"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'tools'))

import yaml
from unittest.mock import patch, MagicMock
from api_client import initialize_org_from_config


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
