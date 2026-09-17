# Field Service Report Summarizer

## What the tool does

A desktop tool that transforms raw field service reports into clean,
customer-facing summaries suitable for publication on a client portal. The
reader is the client's facilities contact — not an engineer, not an internal
employee.

The tool reads a JSONL file where each line is one service report, sends each
report to Groq (Llama 3.3 70B) for summarization, and produces a single
Markdown file with all summaries.

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
2. Get a free API key from https://console.groq.com.
3. Create a `.env` file in the project folder with: `GROQ_API_KEY=your-groq-key-here`
4. Double-click `run.bat`.
5. The tool opens — select your JSONL file and click Generate.

`run.bat` handles the virtual environment, dependencies, and API key loading
automatically. Steps 2-3 are only needed the first time.

## Tech stack

- **Python 3** — standard library for everything except the LLM SDK.
- **Tkinter** — GUI framework, ships with Python.
- **Groq** (free tier) — LLM inference for summarization, running Llama 3.3
  70B via the `groq` SDK.

## Prerequisites

- Python 3.12 or later.
- A Groq API key (free at https://console.groq.com).

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

   Edit `.env` and replace `your-groq-key-here` with your actual Groq API key.
   The `.env` file is gitignored and will not be committed.

## How to run

```
python main.py
```

This launches the GUI. The workflow is:

1. **Select file** — click Browse and choose a `.jsonl` file containing the
   service reports.
2. **Generate** — click Generate Summaries. The progress bar advances as each
   report is processed.
3. **Review results** — the results list shows each report's ID, asset name,
   and status (OK or Review). Click a row to see the reason for any Review
   flag.
4. **Save** — click Save Markdown to write the output file to disk.

## Project structure

```
main.py              Entry point — launches the GUI
gui.py               Tkinter interface (file picker, progress, results, save)
processor.py         Orchestrates report processing (parse, send, collect)
llm_client.py        Groq API integration and prompt construction
report_parser.py     JSONL reader, field validation, contradiction detection
markdown_writer.py   Assembles the final Markdown output
run.bat              One-click launcher (Windows) — sets up venv and runs the tool
run_edge_tests.py    Manual edge-case runner
requirements.txt     Python dependencies (groq)
.env.example         API key template
spec.md              Product specification
plan.md              Architecture and design plan
tasks.md             Ordered implementation tasks

data/                JSONL data files (service_reports, test data)
docs/                Documentation and review artifacts (decisions.md, etc.)
output/              Generated summaries (gitignored except .gitkeep)
tests/               Automated test suite (pytest)
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
   (deprecated SDK, retired model, rate limits, provider switch) were
   documented in `docs/decisions.md` rather than silently changing direction.

The spec and plan were committed before any code was written. This ensures
that design decisions are reviewable, the implementation can be validated
against a stable specification, and deviations are tracked explicitly.
