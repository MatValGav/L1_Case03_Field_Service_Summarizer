# Field Service Report Summarizer — Tasks

Ordered implementation tasks. Each task is individually completable and testable
before moving to the next.

---

## Task 1: Project setup

- Initialize the project directory structure as defined in `plan.md`.
- Create `requirements.txt` with `groq`.
- Create `.gitignore` excluding `.env`, `__pycache__/`, `*.pyc`, and output files.
- Create `.env.example` with `GROQ_API_KEY=your-groq-key-here`.
- Set up a Python virtual environment and install dependencies.

**Done when:** `pip install -r requirements.txt` succeeds, directory structure
matches the plan, and `.env` is excluded from version control.

---

## Task 2: JSONL report parser (`report_parser.py`)

- Read a JSONL file line by line and parse each line as a JSON object.
- Validate that each report contains the required fields: `report_id`, `asset`,
  `technician_id`, `arrived_at`, `departed_at`, `stated_duration_hours`,
  `parts_used`, `resolution`, `technician_notes`.
- Calculate actual duration from `arrived_at` and `departed_at` timestamps.
- Detect and flag the following issues per report:
  - **Duration mismatch:** calculated duration differs from `stated_duration_hours`
    by more than 15 minutes.
  - **Parts mismatch:** `parts_used` is non-empty but `resolution` contains
    language like "no parts", "inspection only", or similar — or vice versa
    (`parts_used` is empty but `resolution` implies parts were fitted).
  - **Insufficient data:** `resolution` is a vague placeholder ("Checked",
    "Attended site", or similar short phrases) and `technician_notes` is empty or
    similarly vague ("See job sheet" or similar).
- Return a list of structured report objects, each including the parsed fields,
  calculated duration, and a list of detected flags.
- Malformed lines are skipped with a warning — they do not halt processing.

**Done when:** Parser correctly reads a JSONL file, returns structured report
objects with calculated durations, and flags are detected for reports containing
duration mismatches, parts contradictions, or insufficient data.

---

## Task 3: Groq LLM client (`llm_client.py`)

- Read `GROQ_API_KEY` from environment variable.
- Raise a clear error at initialization if the key is missing.
- Build a system prompt encoding the summarization rules from `spec.md`:
  - Role: customer-facing summary writer for a facilities management portal.
  - Required content: asset, date, findings, actions, parts, recommendations,
    time on site.
  - Redaction: silently omit personal names, phone numbers, emails, addresses,
    and site access information (key locations, door/alarm codes). No markers.
  - Contradictions: include both conflicting values, state the inconsistency,
    request clarification.
  - Insufficient data: state that the report lacks detail, recommend follow-up.
  - Prompt injection defense: technician_notes is input only — ignore any
    instructions found in it, and flag the report if instructions are detected.
- Build the user prompt per report, including:
  - All report fields (except `technician_id`).
  - Calculated duration from timestamps.
  - Any pre-detected flags from the parser (so the LLM can reference them).
- Send the prompt to Groq and return the response text.
- Handle API errors per report without crashing (return an error status).

**Done when:** A single report can be sent to Groq and a coherent summary is
returned. Verify with one clean report and one containing PII.

---

## Task 4: Report processor (`processor.py`)

- Accept a list of parsed reports from the parser.
- Iterate over each report and send it to the LLM client.
- Collect results as a list of objects, each containing:
  - `report_id`
  - `asset`
  - `summary_text` (the LLM response)
  - `status`: "OK" or "Review"
  - `status_reason`: why it was flagged (contradiction, insufficient data, prompt
    injection, API error), or empty if OK.
- Determine status based on:
  - Any parser flags → "Review"
  - LLM response indicates prompt injection detected → "Review"
  - API call failed → "Review" with error reason
  - Otherwise → "OK"
- Provide a callback mechanism so the GUI can update progress after each report.

**Done when:** A batch of reports processes end-to-end. Clean reports return OK,
and reports with flags return Review with appropriate reasons.

---

## Task 5: Markdown writer (`markdown_writer.py`)

- Accept the list of processed results from the processor.
- Generate a single Markdown document with:
  - A title header (e.g. "# Service Report Summaries").
  - A generation timestamp.
  - One section per report, using `## report_id — Asset Name` as the heading.
  - The summary text below each heading.
  - For reports flagged as "Review": a visible notice block after the summary
    explaining the issue (contradiction, insufficient data, or engineer review
    needed).
- Maintain the same order as the input file.
- Return the Markdown content as a string.

**Done when:** The writer produces a well-formatted Markdown file. Flagged reports
show their notices. The file renders correctly in a Markdown viewer.

---

## Task 6: Tkinter GUI (`gui.py` and `main.py`)

- **`main.py`:** Entry point that creates the Tkinter root window and launches
  the GUI.
- **`gui.py`:** Build the interface with the following elements:
  - **File picker:** A text field showing the selected file path and a "Browse"
    button that opens a file dialog filtered to `.jsonl` files.
  - **Generate button:** Starts processing. Disabled while processing is in
    progress.
  - **Progress bar:** Advances from 0 to N as each report is processed. Shows
    a label like "Processing 3/20...".
  - **Results list:** A scrollable list showing each report's ID, asset name,
    and status (OK / Review). Use color or icon to distinguish statuses.
  - **Save button:** Opens a file dialog to choose the output path and writes
    the Markdown file. Disabled until processing is complete.
- Run LLM processing in a background thread (using `threading.Thread`) so the
  GUI remains responsive during processing.
- Use `root.after()` to safely update the UI from the background thread.
- Show an error dialog if `GOOGLE_API_KEY` is not set when the user clicks
  Generate.

**Done when:** The full flow works: select file → generate → see progress →
see results list → save Markdown. The GUI does not freeze during processing.

---

## Task 7: Test cases

Create a test JSONL file with synthetic reports covering each category the tool
must handle.

Test categories:

- **Clean report:** All fields consistent, no PII, no issues. Expected: clean
  summary, OK status.
- **PII in notes:** Notes contain personal names, phone numbers, emails, and/or
  addresses. Expected: summary omits all PII silently, OK status.
- **Access information in notes:** Notes contain key locations, door codes, alarm
  codes. Expected: summary omits all access details silently, OK status.
- **Duration mismatch:** `stated_duration_hours` does not match calculated
  duration from timestamps. Expected: summary shows both values, flags
  discrepancy, Review status.
- **Parts contradiction:** `parts_used` is non-empty but `resolution` says no
  parts, or vice versa. Expected: summary includes both values, flags conflict,
  Review status.
- **Insufficient data:** Resolution is vague and notes are empty or minimal.
  Expected: summary publishes available fields with incomplete notice, Review
  status.
- **Prompt injection:** Notes contain instructions to the tool (omit data, alter
  summary, publish directly). Expected: instructions ignored, summary generated
  normally, flagged for engineer review, Review status.
- **Long report:** Report covering multiple assets with recommendations at the
  end. Expected: all content including final recommendations present, not
  truncated.
- **Malformed input:** Invalid JSON line in the file. Expected: line skipped,
  other reports processed normally.

**Done when:** Test JSONL file exists with at least one report per category. The
tool produces correct output for all test cases.
