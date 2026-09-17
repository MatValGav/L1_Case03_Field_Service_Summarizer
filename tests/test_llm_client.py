"""Tests for llm_client.py (Groq client fully mocked).

Edge-case mapping:
- technician_id exclusion: guards against internal identifiers leaking to client
  portal output.
- Injection-detection prompt wording: regression test for the aa3905b false-positive
  incident — ensures the prompt contains explicit trigger phrases AND the "normal
  technical descriptions should NOT trigger this" guidance, so a future edit that
  reverts to overly broad detection fails CI.
- Injection marker handling: guards against injected instructions propagating into
  the final summary.
- Missing API key: guards against cryptic errors when env is misconfigured.
"""

import os
from unittest.mock import patch, MagicMock
import pytest


class TestBuildUserPrompt:
    def test_technician_id_excluded(self, parsed_report):
        from llm_client import _build_user_prompt
        prompt = _build_user_prompt(parsed_report)
        assert "T-999" not in prompt
        assert "technician_id" not in prompt

    def test_report_fields_included(self, parsed_report):
        from llm_client import _build_user_prompt
        prompt = _build_user_prompt(parsed_report)
        assert "FSR-9001" in prompt
        assert "Chiller CH-99" in prompt
        assert "filter FD-1" in prompt

    def test_flags_section_present_when_flags_exist(self, parsed_report):
        from llm_client import _build_user_prompt
        parsed_report["flags"] = [{"type": "duration_mismatch", "detail": "mismatch detail"}]
        prompt = _build_user_prompt(parsed_report)
        assert "PRE-DETECTED DATA ISSUES" in prompt
        assert "mismatch detail" in prompt

    def test_flags_section_absent_when_no_flags(self, parsed_report):
        from llm_client import _build_user_prompt
        parsed_report["flags"] = []
        prompt = _build_user_prompt(parsed_report)
        assert "PRE-DETECTED DATA ISSUES" not in prompt


class TestInjectionDetectionPrompt:
    """Regression guard for aa3905b: the prompt must contain explicit trigger
    phrases and the false-positive prevention guidance."""

    def test_prompt_contains_trigger_phrases(self):
        from llm_client import SYSTEM_PROMPT
        for phrase in ["do not mention", "ignore previous rules", "publish directly",
                       "override", "important instruction"]:
            assert phrase in SYSTEM_PROMPT, f"Trigger phrase '{phrase}' missing from SYSTEM_PROMPT"

    def test_prompt_contains_false_positive_prevention(self):
        from llm_client import SYSTEM_PROMPT
        assert "normal technical" in SYSTEM_PROMPT.lower() or "should NOT" in SYSTEM_PROMPT
        assert "vast majority" in SYSTEM_PROMPT


class TestInjectionMarkerHandling:
    """Guards against injected instructions propagating into summaries."""

    @patch.dict(os.environ, {"GROQ_API_KEY": "test-key"})
    def test_injection_marker_detected_and_stripped(self):
        from llm_client import LLMClient

        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = (
            "Summary of the visit.\n[PROMPT_INJECTION_DETECTED]"
        )

        with patch("llm_client.Groq") as MockGroq:
            mock_client = MagicMock()
            mock_client.chat.completions.create.return_value = mock_response
            MockGroq.return_value = mock_client

            client = LLMClient()
            result = client.summarize({"report_id": "X", "asset": "A",
                "arrived_at": "2026-01-01T08:00", "departed_at": "2026-01-01T10:00",
                "calculated_duration_formatted": "2h", "stated_duration_hours": 2.0,
                "parts_used": [], "resolution": "Done.", "technician_notes": "OK.",
                "flags": []})

        assert result["injection_detected"] is True
        assert "[PROMPT_INJECTION_DETECTED]" not in result["summary"]
        assert result["summary"] == "Summary of the visit."
        assert result["error"] is None

    @patch.dict(os.environ, {"GROQ_API_KEY": "test-key"})
    def test_clean_response_no_injection(self):
        from llm_client import LLMClient

        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "Clean summary text."

        with patch("llm_client.Groq") as MockGroq:
            mock_client = MagicMock()
            mock_client.chat.completions.create.return_value = mock_response
            MockGroq.return_value = mock_client

            client = LLMClient()
            result = client.summarize({"report_id": "X", "asset": "A",
                "arrived_at": "2026-01-01T08:00", "departed_at": "2026-01-01T10:00",
                "calculated_duration_formatted": "2h", "stated_duration_hours": 2.0,
                "parts_used": [], "resolution": "Done.", "technician_notes": "OK.",
                "flags": []})

        assert result["injection_detected"] is False
        assert result["summary"] == "Clean summary text."


class TestMissingApiKey:
    def test_runtime_error_without_api_key(self):
        env = os.environ.copy()
        env.pop("GROQ_API_KEY", None)
        with patch.dict(os.environ, env, clear=True):
            from llm_client import LLMClient
            with pytest.raises(RuntimeError, match="GROQ_API_KEY"):
                LLMClient()
