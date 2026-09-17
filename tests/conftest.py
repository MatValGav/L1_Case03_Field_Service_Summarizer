"""Shared fixtures for the Field Service Report Summarizer test suite."""

import sys
import os
import json
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "fixtures")


def _load_fixture(name):
    path = os.path.join(FIXTURES_DIR, name)
    reports = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                reports.append(json.loads(line))
    return reports


@pytest.fixture
def sample_report():
    """A clean, valid report with no flags."""
    return {
        "report_id": "FSR-9001",
        "asset": "Chiller CH-99",
        "technician_id": "T-999",
        "arrived_at": "2026-03-10T08:00",
        "departed_at": "2026-03-10T10:30",
        "stated_duration_hours": 2.5,
        "parts_used": ["filter FD-1"],
        "resolution": "Replaced filter, system running normally.",
        "technician_notes": "Unit back in service.",
    }


@pytest.fixture
def parsed_report(sample_report):
    """A parsed report dict (as returned by parse_report)."""
    from report_parser import parse_report
    report, warning = parse_report(sample_report, 1)
    assert warning is None
    return report


@pytest.fixture
def test_jsonl_path():
    return os.path.join(FIXTURES_DIR, "test_reports.jsonl")
