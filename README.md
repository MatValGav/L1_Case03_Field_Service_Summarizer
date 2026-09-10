# Field Service Report Summarizer

## What the tool does

A desktop tool that transforms raw field service reports into clean,
customer-facing summaries suitable for publication on a client portal. The
reader is the client's facilities contact — not an engineer, not an internal
employee.

The tool reads a JSONL file where each line is one service report, sends each
report to Google Gemini for summarization, and produces a single Markdown file
with all summaries.

Each summary includes:

- The asset serviced and the date of the visit.
- What was found.
- What was done.
- Parts fitted, if any.
- Anything outstanding or recommended.
- Time on site.

### Edge case handling

- **PII redaction:** Personal names, phone numbers, email addresses, home
  addresses, and site access information (key locations, door codes, alarm
  codes) are silently omitted from every summary. No markers are left
  indicating that anything was removed. Redaction is category-based, not
  string-based, so it works against unseen reports.
- **Contradictions:** When fields conflict (e.g. parts listed but resolution
  says none, or timestamps don't match the stated duration), the summary
  includes both values and explicitly flags the inconsistency for
  clarification.
- **Insufficient data:** When a report lacks enough detail for a meaningful
  summary, the tool publishes whatever is available and explicitly states that
  the report is incomplete, recommending follow-up.
- **Prompt injection:** If technician notes contain language that attempts to
  instruct the tool, those instructions are ignored. The summary is generated
  normally from factual content, and the report is flagged for review with the
  submitting engineer.

## Quick start (Windows)

1. Install Python from https://www.python.org/downloads (check "Add to PATH"
   during installation).
2. Get a free API key from https://aistudio.google.com/apikey.
3. Create a `.env` file in the project folder with: `GOOGLE_API_KEY=your-key-here`
4. Double-click `run.bat`.
5. The tool opens — select your JSONL file and click Generate.

`run.bat` handles the virtual environment, dependencies, and API key loading
automatically. Steps 2-3 are only needed the first time.

## Tech stack

- **Python 3** — standard library for everything except the LLM SDK.
- **Tkinter** — GUI framework, ships with Python.
- **Google Gemini** (free tier) — LLM for summarization, via the `google-genai`
  SDK.

## Prerequisites

- Python 3.12 or later.
- A Google Gemini API key (free at https://aistudio.google.com/apikey).

## Setup and installation

1. Clone the repository

2. Create a virtual environment and install dependencies:

   ```
   python -m venv venv
   ```

   Activate the environment:
   - Windows: `venv\Scripts\activate`
   - macOS / Linux: `source venv/bin/activate`

   Then install:

   ```
   pip install -r requirements.txt
   ```

3. Configure the API key. Copy the template and add your key:

   ```
   cp .env.example .env
   ```

   Edit `.env` and replace `your-key-here` with your actual Gemini API key.
   The `.env` file is gitignored and will not be committed.

## How to run

```
python main.py
```

This launches the GUI. The workflow is:

1. **Select file** — click Browse and choose a `.jsonl` file containing the
   service reports.
2. **Generate** — click Generate Summaries. The progress bar advances as each
   report is processed, showing status like "Processing 3/20..." and
   "(waiting for API rate limit)" during the delay between requests.
3. **Review results** — the results list shows each report's ID, asset name,
   and status (OK or Review). Click a row to see the reason for any Review
   flag.
4. **Save** — click Save Markdown to write the output file to disk.

On the Gemini free tier (5 requests per minute), processing 20 reports takes
approximately 4 minutes due to the rate limit delay between requests. A paid
API tier removes this delay.

## Project structure

```
run.bat              One-click launcher (Windows) — sets up venv and runs the tool
main.py              Entry point — launches the GUI
gui.py               Tkinter interface (file picker, progress, results, save)
processor.py         Orchestrates report processing (parse, send, collect)
llm_client.py        Gemini API integration, prompt construction, retry logic
report_parser.py     JSONL reader, field validation, contradiction detection
markdown_writer.py   Assembles the final Markdown output
requirements.txt     Python dependencies (google-genai)
.env.example         API key template
.gitignore           Excludes .env, __pycache__, venv, output files
spec.md              Product specification
plan.md              Architecture and design plan
tasks.md             Ordered implementation tasks
decisions.md         Design decisions and plan deviations
```

## Spec-Driven Development process

This project was built following a Spec-Driven Development process with four
sequential commits:

1. **01-spec** — the product specification was written first, defining what
   the tool does, its inputs and outputs, and every rule it must follow
   (redaction, contradictions, insufficient data, prompt injection).
2. **02-plan** — an architecture plan was derived from the spec, choosing the
   technology stack, defining the module structure, and documenting the
   processing flow and prompt strategy.
3. **03-tasks** — the plan was broken into ordered, individually testable
   implementation tasks.
4. **04-implement** — the tasks were implemented one at a time, each reviewed
   before moving to the next. Deviations discovered during implementation
   (deprecated SDK, retired model, rate limits) were documented in
   `decisions.md` rather than silently changing direction.

The spec and plan were committed before any code was written. This ensures
that design decisions are reviewable, the implementation can be validated
against a stable specification, and deviations are tracked explicitly.
