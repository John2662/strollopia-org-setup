"""Tests for strollopia_import.py's error reporting: suggest_fix() and
write_import_error_report(). These exist so a batch import's failures are
recorded persistently (not just scrolled past in console log output) and
come with an actionable suggestion where one is known - see run_import's
own per-row exception handling, which already continues past a failed row
rather than aborting the batch; these two functions are what makes those
failures reviewable afterward.
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'tools'))

from strollopia_import import suggest_fix, write_import_error_report


def test_suggest_fix_matches_content_type_error():
    error = "Unsupported content type for upload: application/octet-stream (/some/path/.jpg)"
    suggestion = suggest_fix(error)
    assert suggestion is not None
    assert "slugify" in suggestion
    assert "--force" in suggestion


def test_suggest_fix_matches_missing_image_error():
    error = 'Image file not found: /some/path/media/missing.jpg'
    suggestion = suggest_fix(error)
    assert suggestion is not None
    assert "media/" in suggestion


def test_suggest_fix_returns_none_for_unknown_error():
    assert suggest_fix("Some totally unrelated server error (HTTP 500)") is None


def test_write_import_error_report_returns_none_for_no_errors():
    assert write_import_error_report("/tmp/wherever", []) is None


def test_write_import_error_report_writes_file_with_suggestion(tmp_path):
    errors = [
        (5, "Кафе Львів", "Unsupported content type for upload: application/octet-stream (/x/.jpg)"),
        (12, "Some Place", "HTTP 500: {'detail': 'server error'}"),
    ]
    report_path = write_import_error_report(str(tmp_path), errors)

    assert report_path == os.path.join(str(tmp_path), "import-errors.txt")
    assert os.path.exists(report_path)

    content = open(report_path, encoding="utf-8").read()
    assert "2 row(s) failed" in content
    assert 'Row 5: "Кафе Львів"' in content
    assert "Suggested fix:" in content  # for the known content-type error
    assert 'Row 12: "Some Place"' in content
    # No suggestion available for the unknown HTTP 500 case - the report
    # should still list the row and error, just without a "Suggested fix"
    # line duplicated from the other row's.
    lines = content.splitlines()
    row12_idx = next(i for i, line in enumerate(lines) if 'Row 12' in line)
    row12_block = lines[row12_idx:row12_idx + 3]
    assert not any("Suggested fix" in line for line in row12_block)
