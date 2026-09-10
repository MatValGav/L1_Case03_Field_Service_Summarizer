# Field Service Report Summarizer — Decisions

Standing decisions for cases the specification leaves open. Applied consistently
across all modules.

---

## Contradicting fields

Publish the summary with both conflicting values and a caveat requesting
clarification. Never withhold a summary entirely.

## Duration mismatch

Show both the calculated time (from timestamps) and the stated time. Flag the
discrepancy explicitly in the summary.

## Insufficient data

Publish whatever is available (asset, date, time) with an explicit notice that
the report is incomplete. Recommend follow-up.

## Prompt injection

Ignore any instructions found in technician_notes. Generate the summary normally
from factual content. Flag the report for review with the engineer who submitted
it.

## Sensitive information

Omit silently with no markers. Redaction is category-based — personal names,
phone numbers, email addresses, home/personal addresses, and site access
information (key locations, key-safe codes, door codes, alarm codes). Redaction
is never based on specific strings from known reports.

---

## Plan deviations

### SDK: google-generativeai → google-genai

The plan specified `google-generativeai` as the Gemini SDK. During Task 1 setup
the package installed with a deprecation notice stating that all support has
ended and no further updates or bug fixes will be released. The officially
supported successor is `google-genai`, which covers the same Gemini free tier
and uses the same `GOOGLE_API_KEY` environment variable. The project was
switched to `google-genai` before any application code was written.

### Model: gemini-2.0-flash → gemini-3.6-flash

During Task 3 testing, the Gemini API returned a 404 stating that
`gemini-2.0-flash` is no longer available and recommending `gemini-3.6-flash`.
The model was updated accordingly. Same free tier, same API surface.

### API rate limit handling

The Gemini free tier enforces 5 requests per minute. Sending 20 reports
back-to-back caused 429 errors from report 6 onward. Two mechanisms were
added:

1. **Fixed delay (primary):** 12-second pause between every API call. At
   5 requests per minute the natural spacing stays within the limit.
2. **Retry with exponential backoff (fallback):** If a 429 still occurs,
   the client parses the suggested retry delay from the error, waits, and
   retries up to 3 times.

The GUI progress bar shows a "(waiting for API rate limit)" message during
the delay so the user knows the tool is working.

**Note:** This delay is specific to the Gemini free tier. In a production
environment with a paid API, the 12-second delay would be removed as paid
tiers allow thousands of requests per minute. The retry logic would remain
as a safety net.
