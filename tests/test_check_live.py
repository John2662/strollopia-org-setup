"""Tests for check_live.py"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'tools'))

from unittest.mock import patch, MagicMock
import requests
from check_live import check_live


def _mock_response(status_code, text):
    resp = MagicMock()
    resp.status_code = status_code
    resp.text = text
    return resp


def test_check_live_succeeds_for_valid_template_site():
    with patch("check_live.requests.get", return_value=_mock_response(200, "...Open the Map...")):
        assert check_live("ca-ns-kentville.strollopia.com") is True


def test_check_live_fails_on_non_200():
    with patch("check_live.requests.get", return_value=_mock_response(404, "not found")):
        assert check_live("ca-ns-kentville.strollopia.com") is False


def test_check_live_fails_when_page_doesnt_look_like_the_template():
    with patch("check_live.requests.get", return_value=_mock_response(200, "<html>parked domain</html>")):
        assert check_live("ca-ns-kentville.strollopia.com") is False


def test_check_live_fails_on_connection_error():
    with patch("check_live.requests.get", side_effect=requests.exceptions.ConnectionError("dns failure")):
        assert check_live("ca-ns-kentville.strollopia.com") is False


def test_check_live_also_checks_map_page_when_map_id_given():
    splash = _mock_response(200, "...Open the Map...")
    map_page = _mock_response(200, "/embed/maps/42/")
    with patch("check_live.requests.get", side_effect=[splash, map_page]) as mock_get:
        assert check_live("ca-ns-kentville.strollopia.com", map_id=42) is True
    urls_requested = [call.args[0] for call in mock_get.call_args_list]
    assert "https://ca-ns-kentville.strollopia.com/" in urls_requested
    assert "https://ca-ns-kentville.strollopia.com/maps/42/" in urls_requested


def test_check_live_fails_when_map_page_missing_embed_reference():
    splash = _mock_response(200, "...Open the Map...")
    map_page = _mock_response(200, "<html>no iframe here</html>")
    with patch("check_live.requests.get", side_effect=[splash, map_page]):
        assert check_live("ca-ns-kentville.strollopia.com", map_id=42) is False
