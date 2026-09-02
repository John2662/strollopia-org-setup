"""Tests for generate_todo.py"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'tools'))

import csv
import yaml
from unittest.mock import patch, MagicMock
from generate_todo import (
    resolve_org_slug, _local_row_count, _org_posted, _site_live,
    _data_imported, build_checklist, _wrap_lines, _render_table,
    print_checklist,
)


def test_resolve_org_slug_from_slug_directly():
    assert resolve_org_slug("ca-nova-scotia-new-minas", None, None, None) == "ca-nova-scotia-new-minas"


def test_resolve_org_slug_from_country_province_town():
    slug = resolve_org_slug(None, "CA", "Nova Scotia", "Annapolis Royal")
    assert slug == "ca-nova-scotia-annapolis-royal"


def test_resolve_org_slug_requires_all_three_geo_fields():
    import pytest
    with pytest.raises(ValueError):
        resolve_org_slug(None, "CA", "Nova Scotia", None)


def test_resolve_org_slug_prefers_explicit_slug_over_geo_fields():
    # If both are given, the explicit slug wins (e.g. a custom --domain
    # override in city_discover.py wouldn't match the geo composition).
    slug = resolve_org_slug("custom-slug", "CA", "Nova Scotia", "Annapolis Royal")
    assert slug == "custom-slug"


def test_local_row_count_reads_tsv(tmp_path):
    map_dir = tmp_path / "main-map"
    map_dir.mkdir()
    with open(map_dir / "map-data.en.tsv", "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["name"], delimiter="\t")
        writer.writeheader()
        writer.writerows([{"name": "A"}, {"name": "B"}, {"name": "C"}])

    assert _local_row_count(str(tmp_path)) == 3


def test_local_row_count_missing_file_returns_none(tmp_path):
    assert _local_row_count(str(tmp_path)) is None


def test_org_posted_true_when_policy_fetch_succeeds():
    with patch("generate_todo.get_org_policy", return_value={}):
        assert _org_posted("test.strollopia.com") is True


def test_org_posted_false_when_policy_fetch_raises():
    with patch("generate_todo.get_org_policy", side_effect=Exception("404")):
        assert _org_posted("test.strollopia.com") is False


def test_site_live_true_on_200_with_template_marker():
    with patch("generate_todo.requests.get") as mock_get:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = "<a>Open the Map</a>"
        mock_get.return_value = mock_resp
        assert _site_live("test.strollopia.com") is True


def test_site_live_false_on_404():
    with patch("generate_todo.requests.get") as mock_get:
        mock_resp = MagicMock()
        mock_resp.status_code = 404
        mock_resp.text = ""
        mock_get.return_value = mock_resp
        assert _site_live("test.strollopia.com") is False


def _write_org_config(org_dir, email="admin@strollopia.com", password="realpass"):
    os.makedirs(org_dir, exist_ok=True)
    with open(os.path.join(org_dir, "org-setup.yaml"), "w") as f:
        yaml.dump({"org_domain_name": "test.strollopia.com"}, f)
    with open(os.path.join(org_dir, "org-setup.secrets.yaml"), "w") as f:
        yaml.dump({"main_admin_email": email, "main_admin_password": password}, f)


def test_data_imported_true_when_live_count_meets_expected(tmp_path):
    org_dir = tmp_path / "test-town"
    _write_org_config(str(org_dir))
    map_dir = org_dir / "main-map"
    map_dir.mkdir()
    with open(map_dir / "map-data.en.tsv", "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["name"], delimiter="\t")
        writer.writeheader()
        writer.writerows([{"name": "A"}, {"name": "B"}])

    with patch("generate_todo.login", return_value="fake-token"), \
         patch("generate_todo.requests.get") as mock_get:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = [{"pk": 1, "name": "A"}, {"pk": 2, "name": "B"}]
        mock_get.return_value = mock_resp

        status, detail = _data_imported(str(org_dir), "test.strollopia.com")

    assert status is True
    assert "2 POIs live" in detail


def test_data_imported_false_when_partial(tmp_path):
    org_dir = tmp_path / "test-town"
    _write_org_config(str(org_dir))
    map_dir = org_dir / "main-map"
    map_dir.mkdir()
    with open(map_dir / "map-data.en.tsv", "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["name"], delimiter="\t")
        writer.writeheader()
        writer.writerows([{"name": "A"}, {"name": "B"}, {"name": "C"}])

    with patch("generate_todo.login", return_value="fake-token"), \
         patch("generate_todo.requests.get") as mock_get:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = [{"pk": 1, "name": "A"}]
        mock_get.return_value = mock_resp

        status, detail = _data_imported(str(org_dir), "test.strollopia.com")

    assert status is False
    assert "1/3" in detail


def test_data_imported_unknown_when_login_fails(tmp_path):
    org_dir = tmp_path / "test-town"
    _write_org_config(str(org_dir))

    with patch("generate_todo.login", side_effect=RuntimeError("bad creds")):
        status, detail = _data_imported(str(org_dir), "test.strollopia.com")

    assert status is None
    assert "admin login failed" in detail


def test_build_checklist_org_not_posted_short_circuits(tmp_path):
    with patch("generate_todo._org_posted", return_value=False), \
         patch("generate_todo._site_live", return_value=False):
        domain, rows = build_checklist("test-town", str(tmp_path), str(tmp_path))

    assert domain == "test-town.strollopia.com"
    posted_row = rows[0]
    assert posted_row[3] is False
    imported_row = rows[1]
    assert imported_row[3] is None
    assert "org not posted yet" in imported_row[4]


def test_wrap_lines_never_breaks_a_slug_mid_hyphen():
    # Regression test: a slug like ca-nova-scotia-annapolis-royal must
    # never split across lines -- these lines are meant to be
    # copy-pasted as real commands, and a hyphen-broken slug pastes as
    # a broken command.
    text = "python tools/post_org_setup.py ca-nova-scotia-annapolis-royal  (USE_PROD=1)"
    lines = _wrap_lines(text, width=40)
    assert not any(line.endswith("-") for line in lines)
    assert "ca-nova-scotia-annapolis-royal" in "".join(lines)


def test_wrap_lines_respects_embedded_newlines_as_hard_breaks():
    lines = _wrap_lines("first line\nsecond line", width=40)
    assert lines == ["first line", "second line"]


def test_render_table_produces_aligned_box_when_content_fits():
    table = _render_table(
        ["#", "Step"], [["1", "short"], ["2", "two words"]],
        widths=[3, 12],
    )
    lines = table.split("\n")
    # Every line should be the same length (straight box edges) when
    # every word fits within its column.
    widths_seen = {len(line) for line in lines}
    assert len(widths_seen) == 1
    assert lines[0].startswith("┌") and lines[0].endswith("┐")
    assert lines[-1].startswith("└") and lines[-1].endswith("┘")


def test_render_table_overflows_rather_than_breaks_an_unbreakable_word():
    # A single word longer than its column can't be wrapped without
    # breaking it -- by design (see _wrap_lines), it's left intact and
    # allowed to overflow that one line's width instead.
    table = _render_table(["#", "Step"], [["1", "unbreakablylongword"]], widths=[3, 5])
    assert "unbreakablylongword" in table


def test_print_checklist_includes_setup_commands(tmp_path, capsys):
    with patch("generate_todo._org_posted", return_value=False), \
         patch("generate_todo._site_live", return_value=False):
        print_checklist("test-town", str(tmp_path), str(tmp_path))

    out = capsys.readouterr().out
    assert "cd " in out
    assert "source .env/bin/activate" in out
    assert "export USE_PROD=1" in out
    # The cd target must be a real, absolute path to this repo, not a
    # placeholder -- it should exist and contain this tool.
    cd_line = next(line for line in out.splitlines() if line.startswith("cd "))
    repo_root = cd_line[len("cd "):]
    assert os.path.isfile(os.path.join(repo_root, "tools", "generate_todo.py"))
