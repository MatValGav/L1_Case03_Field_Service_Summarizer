"""End-to-end and regression/security tests.

This file covers two concerns:

REGRESSION / SECURITY TESTS (Section 4):
- PII (FSR-9002, cf. FSR-3003/FSR-3014): names, phones, emails, addresses, access
  codes must never appear in output.
- Duration mismatch (FSR-9003, cf. FSR-3005): both values reported, flagged Review.
- Parts mismatch (FSR-9004, cf. FSR-3006): contradiction flagged.
- Insufficient data (FSR-9005/FSR-9006, cf. FSR-3007/FSR-3008): vague reports
  flagged as insufficient.
- Prompt injection (FSR-9007, cf. FSR-3009): injected instruction is flagged and
  not followed.
- Benign technical language (FSR-9008): regression test for aa3905b false-positive
  incident — words like "override" and "important" in normal technical context must
  NOT be flagged.
- Malformed JSONL (line 9): pipeline skips it, processes remaining lines.

END-TO-END TEST (Section 5):
- Full pipeline with mocked LLM, verifying final Markdown output has correct
  status counts and per-report statuses.
"""

import json
import os
from unittest.mock import patch, MagicMock
import pytest

from report_parser import parse_jsonl
from markdown_writer import build_markdown


FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "fixtures")
TEST_JSONL = os.path.join(FIXTURES_DIR, "test_reports.jsonl")

PII_STRINGS = [
    "Jane Smith", "07700 123456", "jane.smith@example.com",
    "42 Oak Lane", "flat 2A", "8832",
]

MOCK_SUMMARIES = {
    "FSR-9001": "Replaced filter on Chiller CH-99 on 10 March 2026. System running normally. Time on site: 2h 30min.",
    "FSR-9002": "Replaced ignition electrode on Boiler BLR-10 on 11 March 2026. Flame signal verified after replacement. Time on site: 3h 15min.",
    "FSR-9003": "Replaced contactor on Chiller CH-01 on 12 March 2026. There is a discrepancy: the calculated time on site is 6h 35min but the technician reported 2h. This requires clarification. Time on site: 6h 35min stated as 2h.",
    "FSR-9004": "Attended Cooling tower CT-05 on 13 March 2026. The parts list includes fan motor FM-14 and drive belt DB-6, however the resolution states inspection only with no parts required. This is conflicting and requires clarification.",
    "FSR-9005": "Attended AHU-04 on 14 March 2026. The report lacks sufficient detail for a meaningful summary. Time on site: 25min. Recommend follow-up with the service provider.",
    "FSR-9006": "Attended VAV-22 on 15 March 2026. The report lacks sufficient detail. Time on site: 20min. Recommend follow-up.",
    "FSR-9007": "Replaced pressure relief valve on Boiler BLR-05 on 16 March 2026. Pressure test passed at 3 bar. Time on site: 3h 45min.\n[PROMPT_INJECTION_DETECTED]",
    "FSR-9008": "Reset overload relay on Pump P-07 on 17 March 2026. This is the third reset this quarter. The thermal relay calibration should be checked and the default trip threshold may need adjustment to prevent recurrence. Time on site: 2h.",
    "FSR-9009": "Belt tension adjusted on AHU-11 on 18 March 2026. No parts needed. Recommend belt replacement at next PM visit. Time on site: 1h 30min.",
}

EXPECTED_STATUSES = {
    "FSR-9001": "OK",
    "FSR-9002": "OK",       # PII is the LLM's job to redact; no parser flags
    "FSR-9003": "Review",   # duration mismatch
    "FSR-9004": "Review",   # parts mismatch
    "FSR-9005": "Review",   # insufficient data
    "FSR-9006": "Review",   # insufficient data
    "FSR-9007": "Review",   # prompt injection
    "FSR-9008": "OK",       # benign technical language — NOT flagged
    "FSR-9009": "OK",
}


def _make_mock_llm_client():
    """Build a mock LLMClient whose summarize() returns report-specific responses."""
    mock_client = MagicMock()

    def summarize_side_effect(report):
        rid = report["report_id"]
        text = MOCK_SUMMARIES.get(rid, "Fallback summary.")
        injection_detected = "[PROMPT_INJECTION_DETECTED]" in text
        clean_text = text.replace("[PROMPT_INJECTION_DETECTED]", "").strip()
        return {
            "summary": clean_text,
            "injection_detected": injection_detected,
            "error": None,
        }

    mock_client.summarize.side_effect = summarize_side_effect
    return mock_client


# ── Section 4: Regression / Security Tests ──────────────────────────────


class TestPII:
    """Guards against PII leaking into client-facing output (cf. FSR-3003/FSR-3014)."""

    @patch.dict(os.environ, {"GROQ_API_KEY": "test-key"})
    def test_pii_absent_from_markdown(self):
        reports, _ = parse_jsonl(TEST_JSONL)
        with patch("processor.LLMClient", return_value=_make_mock_llm_client()), \
             patch("processor.time"):
            from processor import process_reports
            results = process_reports(reports)

        md = build_markdown(results)
        for pii in PII_STRINGS:
            assert pii not in md, f"PII '{pii}' found in output"


class TestDurationMismatch:
    """Guards against FSR-3005-style timesheet discrepancies passing silently."""

    def test_duration_mismatch_flagged_review(self):
        reports, _ = parse_jsonl(TEST_JSONL)
        r = next(r for r in reports if r["report_id"] == "FSR-9003")
        assert any(f["type"] == "duration_mismatch" for f in r["flags"])
        detail = next(f["detail"] for f in r["flags"] if f["type"] == "duration_mismatch")
        assert "6h 35min" in detail
        assert "2h" in detail


class TestPartsMismatch:
    """Guards against FSR-3006-style contradictions."""

    def test_parts_mismatch_flagged_review(self):
        reports, _ = parse_jsonl(TEST_JSONL)
        r = next(r for r in reports if r["report_id"] == "FSR-9004")
        assert any(f["type"] == "parts_mismatch" for f in r["flags"])


class TestInsufficientData:
    """Guards against FSR-3007/FSR-3008-style vague placeholders."""

    @pytest.mark.parametrize("rid", ["FSR-9005", "FSR-9006"])
    def test_insufficient_data_flagged(self, rid):
        reports, _ = parse_jsonl(TEST_JSONL)
        r = next(r for r in reports if r["report_id"] == rid)
        assert any(f["type"] == "insufficient_data" for f in r["flags"])


class TestPromptInjection:
    """Guards against FSR-3009-style prompt injection attacks."""

    @patch.dict(os.environ, {"GROQ_API_KEY": "test-key"})
    def test_injection_flagged_as_review(self):
        reports, _ = parse_jsonl(TEST_JSONL)
        with patch("processor.LLMClient", return_value=_make_mock_llm_client()), \
             patch("processor.time"):
            from processor import process_reports
            results = process_reports(reports)

        r = next(r for r in results if r["report_id"] == "FSR-9007")
        assert r["status"] == "Review"
        assert "injection" in r["status_reason"].lower()

    @patch.dict(os.environ, {"GROQ_API_KEY": "test-key"})
    def test_injected_instruction_not_followed(self):
        """The mock summary for FSR-9007 includes the pressure test info that
        the injection tried to hide — verifying the instruction was ignored."""
        reports, _ = parse_jsonl(TEST_JSONL)
        with patch("processor.LLMClient", return_value=_make_mock_llm_client()), \
             patch("processor.time"):
            from processor import process_reports
            results = process_reports(reports)

        r = next(r for r in results if r["report_id"] == "FSR-9007")
        assert "pressure test" in r["summary_text"].lower()
        assert "[PROMPT_INJECTION_DETECTED]" not in r["summary_text"]


class TestBenignTechnicalLanguage:
    """Regression test for aa3905b false-positive incident: benign uses of words
    like 'override' and 'important' in normal technical context must NOT be flagged."""

    @patch.dict(os.environ, {"GROQ_API_KEY": "test-key"})
    def test_benign_override_not_flagged(self):
        reports, _ = parse_jsonl(TEST_JSONL)
        with patch("processor.LLMClient", return_value=_make_mock_llm_client()), \
             patch("processor.time"):
            from processor import process_reports
            results = process_reports(reports)

        r = next(r for r in results if r["report_id"] == "FSR-9008")
        assert r["status"] == "OK", (
            f"FSR-9008 should be OK (benign technical language) but got "
            f"'{r['status']}': {r['status_reason']}"
        )


class TestMalformedJsonlLine:
    """Guards against pipeline crashes from corrupt input files."""

    def test_malformed_line_skipped(self):
        reports, warnings = parse_jsonl(TEST_JSONL)
        assert len(reports) == 9
        json_warnings = [w for w in warnings if "invalid JSON" in w]
        assert len(json_warnings) == 1
        ids = {r["report_id"] for r in reports}
        assert "FSR-9009" in ids  # line after the bad one


# ── Section 5: End-to-End Test ──────────────────────────────────────────


class TestEndToEnd:
    """Full pipeline: parse → process (mocked LLM) → markdown output."""

    @patch.dict(os.environ, {"GROQ_API_KEY": "test-key"})
    def test_full_pipeline(self):
        reports, warnings = parse_jsonl(TEST_JSONL)
        assert len(reports) == 9

        with patch("processor.LLMClient", return_value=_make_mock_llm_client()), \
             patch("processor.time"):
            from processor import process_reports
            results = process_reports(reports)

        assert len(results) == 9

        ok_count = sum(1 for r in results if r["status"] == "OK")
        review_count = sum(1 for r in results if r["status"] == "Review")
        assert ok_count == 4
        assert review_count == 5

        for r in results:
            expected = EXPECTED_STATUSES[r["report_id"]]
            assert r["status"] == expected, (
                f"{r['report_id']}: expected {expected}, got {r['status']} "
                f"(reason: {r['status_reason']})"
            )

        md = build_markdown(results)
        assert "# Service Report Summaries" in md
        assert md.count("Requires review") == 5

        for rid in EXPECTED_STATUSES:
            assert rid in md
