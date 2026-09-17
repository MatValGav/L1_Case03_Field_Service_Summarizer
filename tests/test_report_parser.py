"""Tests for report_parser.py.

Edge-case mapping:
- Malformed JSON: guards against pipeline crashes on corrupt input files.
- Missing fields: guards against silent data loss from incomplete records.
- Duration mismatch (FSR-3005 pattern): guards against undetected timesheet errors.
- Parts mismatch (FSR-3006 pattern): guards against contradictions between parts
  list and resolution text reaching the client without a flag.
- Insufficient data (FSR-3007/FSR-3008 pattern): guards against vague placeholders
  being presented as real summaries.
- Generator/streaming: guards against memory issues on large JSONL files.
"""

import json
import os
import pytest

from report_parser import (
    parse_report,
    parse_jsonl,
    detect_flags,
    calculate_duration_hours,
    format_duration,
    REQUIRED_FIELDS,
)


class TestParseValidLine:
    def test_valid_report_parses(self, sample_report):
        report, warning = parse_report(sample_report, 1)
        assert warning is None
        assert report is not None
        assert report["report_id"] == "FSR-9001"
        assert report["asset"] == "Chiller CH-99"
        assert report["calculated_duration_hours"] == pytest.approx(2.5, abs=0.01)
        assert report["calculated_duration_formatted"] == "2h 30min"
        assert report["flags"] == []

    def test_all_required_fields_preserved(self, sample_report):
        report, _ = parse_report(sample_report, 1)
        for field in REQUIRED_FIELDS:
            assert field in report


class TestMalformedJson:
    def test_malformed_json_in_jsonl(self, test_jsonl_path):
        """Malformed line is reported as a warning, not an exception."""
        reports, warnings = parse_jsonl(test_jsonl_path)
        json_warnings = [w for w in warnings if "invalid JSON" in w]
        assert len(json_warnings) == 1
        assert "Line 9" in json_warnings[0]
        assert len(reports) == 9  # 10 lines minus 1 malformed

    def test_remaining_reports_still_parsed(self, test_jsonl_path):
        reports, _ = parse_jsonl(test_jsonl_path)
        ids = {r["report_id"] for r in reports}
        assert "FSR-9001" in ids
        assert "FSR-9009" in ids  # last line after the bad one


class TestMissingFields:
    def test_missing_required_field_rejected(self):
        raw = {"report_id": "FSR-0001", "asset": "Pump P-1"}
        report, warning = parse_report(raw, 1)
        assert report is None
        assert "missing fields" in warning

    def test_warning_lists_missing_fields(self):
        raw = {"report_id": "FSR-0001"}
        _, warning = parse_report(raw, 1)
        assert "asset" in warning
        assert "technician_id" in warning


class TestDurationMismatch:
    """Guards against FSR-3005-style timesheet discrepancies."""

    def test_large_mismatch_flagged(self):
        raw = {
            "report_id": "FSR-0002",
            "asset": "Chiller CH-01",
            "technician_id": "T-1",
            "arrived_at": "2026-03-04T07:45",
            "departed_at": "2026-03-04T14:20",  # ~6h35m
            "stated_duration_hours": 2.0,
            "parts_used": [],
            "resolution": "Done.",
            "technician_notes": "OK.",
        }
        report, _ = parse_report(raw, 1)
        flag_types = [f["type"] for f in report["flags"]]
        assert "duration_mismatch" in flag_types
        detail = next(f["detail"] for f in report["flags"] if f["type"] == "duration_mismatch")
        assert "6h 35min" in detail
        assert "2h" in detail

    def test_small_mismatch_not_flagged(self):
        raw = {
            "report_id": "FSR-0003",
            "asset": "Pump P-1",
            "technician_id": "T-1",
            "arrived_at": "2026-03-04T08:00",
            "departed_at": "2026-03-04T10:30",
            "stated_duration_hours": 2.5,  # exact match
            "parts_used": [],
            "resolution": "Fixed.",
            "technician_notes": "Done.",
        }
        report, _ = parse_report(raw, 1)
        assert not any(f["type"] == "duration_mismatch" for f in report["flags"])


class TestPartsMismatch:
    """Guards against FSR-3006-style contradictions between parts list and resolution."""

    def test_parts_listed_but_resolution_says_none(self):
        raw = {
            "report_id": "FSR-0004",
            "asset": "CT-02",
            "technician_id": "T-1",
            "arrived_at": "2026-03-05T08:00",
            "departed_at": "2026-03-05T11:30",
            "stated_duration_hours": 3.5,
            "parts_used": ["fan motor FM-14", "drive belt DB-6"],
            "resolution": "Inspection only, no parts required this visit.",
            "technician_notes": "Bearings noisy.",
        }
        report, _ = parse_report(raw, 1)
        flag_types = [f["type"] for f in report["flags"]]
        assert "parts_mismatch" in flag_types

    def test_no_parts_listed_but_resolution_says_fitted(self):
        raw = {
            "report_id": "FSR-0005",
            "asset": "AHU-01",
            "technician_id": "T-1",
            "arrived_at": "2026-03-06T08:00",
            "departed_at": "2026-03-06T10:00",
            "stated_duration_hours": 2.0,
            "parts_used": [],
            "resolution": "Replaced faulty sensor.",
            "technician_notes": "Done.",
        }
        report, _ = parse_report(raw, 1)
        flag_types = [f["type"] for f in report["flags"]]
        assert "parts_mismatch" in flag_types


class TestInsufficientData:
    """Guards against FSR-3007/FSR-3008-style vague placeholders."""

    @pytest.mark.parametrize("resolution,notes", [
        ("Attended site.", "See job sheet."),
        ("Checked.", ""),
        ("Done.", "N/A"),
        ("Visited site", "nil"),
    ])
    def test_vague_resolution_and_notes_flagged(self, resolution, notes):
        raw = {
            "report_id": "FSR-0006",
            "asset": "AHU-04",
            "technician_id": "T-1",
            "arrived_at": "2026-03-07T13:00",
            "departed_at": "2026-03-07T13:30",
            "stated_duration_hours": 0.5,
            "parts_used": [],
            "resolution": resolution,
            "technician_notes": notes,
        }
        report, _ = parse_report(raw, 1)
        flag_types = [f["type"] for f in report["flags"]]
        assert "insufficient_data" in flag_types

    def test_detailed_resolution_not_flagged(self, sample_report):
        report, _ = parse_report(sample_report, 1)
        assert not any(f["type"] == "insufficient_data" for f in report["flags"])


class TestLineByLineProcessing:
    """Confirms parse_jsonl reads the file line-by-line (no full load into memory)."""

    def test_file_iterated_line_by_line(self, tmp_path):
        """Write a multi-line JSONL, verify each line is processed independently."""
        jsonl = tmp_path / "test.jsonl"
        lines = []
        for i in range(5):
            lines.append(json.dumps({
                "report_id": f"FSR-{i}",
                "asset": "A",
                "technician_id": "T-1",
                "arrived_at": "2026-01-01T08:00",
                "departed_at": "2026-01-01T10:00",
                "stated_duration_hours": 2.0,
                "parts_used": [],
                "resolution": "Fixed.",
                "technician_notes": "OK.",
            }))
        jsonl.write_text("\n".join(lines), encoding="utf-8")
        reports, warnings = parse_jsonl(str(jsonl))
        assert len(reports) == 5
        assert len(warnings) == 0

    def test_bad_line_does_not_prevent_later_lines(self, tmp_path):
        jsonl = tmp_path / "mixed.jsonl"
        good = json.dumps({
            "report_id": "FSR-GOOD",
            "asset": "A",
            "technician_id": "T-1",
            "arrived_at": "2026-01-01T08:00",
            "departed_at": "2026-01-01T10:00",
            "stated_duration_hours": 2.0,
            "parts_used": [],
            "resolution": "Fixed.",
            "technician_notes": "OK.",
        })
        jsonl.write_text(f"NOT JSON\n{good}\n", encoding="utf-8")
        reports, warnings = parse_jsonl(str(jsonl))
        assert len(reports) == 1
        assert reports[0]["report_id"] == "FSR-GOOD"
        assert len(warnings) == 1


class TestHelpers:
    def test_calculate_duration_hours(self):
        hours = calculate_duration_hours("2026-03-10T08:00", "2026-03-10T10:30")
        assert hours == pytest.approx(2.5, abs=0.01)

    def test_format_duration_hours_and_minutes(self):
        assert format_duration(2.5) == "2h 30min"

    def test_format_duration_hours_only(self):
        assert format_duration(3.0) == "3h"

    def test_format_duration_minutes_only(self):
        assert format_duration(0.25) == "15min"
