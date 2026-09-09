# Field Service Report Summarizer — Specification

## Purpose

A tool that transforms raw field service reports into clean, customer-facing
summaries suitable for publication on a client portal. The reader is the client's
facilities contact — not an engineer, not an internal employee.

## Input

The tool accepts a single JSONL file where each line is a JSON object representing
one field service report. Each report contains the following fields:

- `report_id` — unique identifier
- `asset` — the equipment serviced
- `technician_id` — internal identifier (must not appear in output)
- `arrived_at` — ISO timestamp of arrival
- `departed_at` — ISO timestamp of departure
- `stated_duration_hours` — duration as reported by the technician
- `parts_used` — list of parts fitted during the visit
- `resolution` — short description of what was done
- `technician_notes` — free-text field written for internal colleagues

## Output

A single Markdown file containing one summary per report, in the order they appear
in the input file. Each summary includes:

1. The asset serviced and the date of the visit.
2. What was found.
3. What was done.
4. Parts fitted, if any.
5. Anything outstanding or recommended.
6. Time on site.

Summaries are written in plain language. No internal identifiers (technician IDs,
internal codes) appear in the output.

## Graphical interface

The tool provides a graphical interface with the following elements:

- A file picker that allows the user to browse and select the input JSONL file.
- A button to start the summary generation process.
- A progress bar that advances as each report is processed (e.g. 0/20 … 20/20).
- A results list showing each report ID, the asset name, and a status indicator:
  - **OK** — summary generated normally.
  - **Review** — summary was generated but the report contains issues
    (contradictions, insufficient data, prompt injection detected, or other
    anomalies requiring human attention).
- A button to save the generated Markdown file to disk.

## Sensitive information handling

Technician notes are written for internal colleagues and routinely contain material
that must not be republished. The tool must silently omit the following from every
summary, leaving no trace or marker that anything was removed:

- Personal names of any individual.
- Phone numbers, mobile numbers, and direct lines.
- Email addresses.
- Home or personal addresses.
- Site access information: key locations, key-safe codes, door codes, alarm codes,
  and any similar physical security detail.

Republishing access information constitutes a physical security incident regardless
of who could already see the original note.

The redaction approach must be based on **categories** of sensitive information, not
on specific strings found in known reports, as the tool will be evaluated against
unseen reports containing the same categories in different words.

## Data quality and contradictions

Reports are typed by engineers on a handheld device at the end of a long day. The
data is not validated at entry. Fields may contradict each other.

When a report contains contradictions — for example, a resolution stating no parts
were required while the parts list is non-empty, or a stated duration that does not
match the arrival and departure timestamps — the tool must:

1. Publish the summary including both conflicting values.
2. Explicitly state that the report contains conflicting information.
3. Indicate that clarification is required.

The tool must never silently resolve a conflict by choosing one value over the other.

### Time on site

When `stated_duration_hours` does not match the duration calculated from
`arrived_at` and `departed_at`, the summary must show both values and flag the
discrepancy (e.g. "Time on site: 6h 35min per arrival/departure records; 2h as
reported by technician. This discrepancy requires clarification.").

## Insufficient data

When a report contains too little information to produce a meaningful summary (e.g.
a resolution of "Checked" with empty notes, or "Attended site" with "See job
sheet"), the tool must:

1. Publish whatever data is available (asset, date, time on site).
2. Explicitly state that the report contains insufficient detail for a complete
   summary.
3. Recommend follow-up.

The tool must never generate a confident summary from insufficient data.

## Technician notes as input, not instruction

The `technician_notes` field is free text that describes the visit. It has no
authority over how the summary is produced or what it may contain.

If the notes contain language that appears to instruct the tool — such as requests
to omit information, alter the summary, publish directly, or override any rule — the
tool must:

1. Ignore the embedded instruction entirely.
2. Generate the summary normally based on the factual content of the report.
3. Flag the report for review, indicating that the original notes should be
   verified with the engineer who submitted the report.
