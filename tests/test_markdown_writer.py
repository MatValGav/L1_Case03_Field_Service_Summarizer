"""Tests for markdown_writer.py.

Edge-case mapping:
- Status badge rendering: guards against incorrect visual indicators reaching
  the client portal.
- Output stability: snapshot tests guard against accidental formatting regressions.
"""

from unittest.mock import patch
from datetime import datetime, timezone
from markdown_writer import build_markdown


FIXED_TIME = datetime(2026, 3, 20, 12, 0, 0, tzinfo=timezone.utc)


def _patch_time(fn):
    """Decorator to freeze the timestamp in build_markdown."""
    def wrapper(*args, **kwargs):
        with patch("markdown_writer.datetime") as mock_dt:
            mock_dt.now.return_value = FIXED_TIME
            mock_dt.side_effect = lambda *a, **k: datetime(*a, **k)
            return fn(*args, **kwargs)
    return wrapper


class TestStatusBadge:
    def test_ok_status_no_review_block(self):
        results = [{
            "report_id": "FSR-1000",
            "asset": "Pump P-1",
            "summary_text": "All good.",
            "status": "OK",
            "status_reason": "",
        }]
        md = build_markdown(results)
        assert "Requires review" not in md
        assert "All good." in md

    def test_review_status_has_review_block(self):
        results = [{
            "report_id": "FSR-1001",
            "asset": "AHU-01",
            "summary_text": "Issues found.",
            "status": "Review",
            "status_reason": "Duration mismatch detected.",
        }]
        md = build_markdown(results)
        assert "> **Requires review:**" in md
        assert "Duration mismatch detected." in md

    def test_no_summary_shows_fallback(self):
        results = [{
            "report_id": "FSR-1002",
            "asset": "BLR-01",
            "summary_text": None,
            "status": "Review",
            "status_reason": "API error.",
        }]
        md = build_markdown(results)
        assert "Summary could not be generated" in md


class TestOutputStability:
    @_patch_time
    def test_single_ok_report_snapshot(self):
        results = [{
            "report_id": "FSR-5000",
            "asset": "Chiller CH-01",
            "summary_text": "Replaced filter. System running.",
            "status": "OK",
            "status_reason": "",
        }]
        md = build_markdown(results)
        expected = (
            "# Service Report Summaries\n"
            "\n"
            "Generated: 2026-03-20 12:00 UTC\n"
            "\n"
            "## FSR-5000 — Chiller CH-01\n"
            "\n"
            "Replaced filter. System running.\n"
            "\n"
            "---\n"
        )
        assert md == expected

    @_patch_time
    def test_review_report_snapshot(self):
        results = [{
            "report_id": "FSR-5001",
            "asset": "AHU-03",
            "summary_text": "Conflicting data found.",
            "status": "Review",
            "status_reason": "Parts mismatch.",
        }]
        md = build_markdown(results)
        assert '> **Requires review:** Parts mismatch.\n' in md
        assert md.index("Conflicting data found.") < md.index("Requires review")
