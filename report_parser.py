import json
import re
from datetime import datetime, timezone


REQUIRED_FIELDS = [
    "report_id",
    "asset",
    "technician_id",
    "arrived_at",
    "departed_at",
    "stated_duration_hours",
    "parts_used",
    "resolution",
    "technician_notes",
]

DURATION_TOLERANCE_MINUTES = 15

NO_PARTS_PATTERNS = re.compile(
    r"\b(no parts|no replacement|inspection only|no components|parts not required)\b",
    re.IGNORECASE,
)

PARTS_FITTED_PATTERNS = re.compile(
    r"\b(replaced|installed|fitted|swapped)\b",
    re.IGNORECASE,
)

VAGUE_RESOLUTION_PATTERNS = re.compile(
    r"^(checked|attended site|see job sheet|site visit|visited site|completed|done)\.?$",
    re.IGNORECASE,
)

VAGUE_NOTES_PATTERNS = re.compile(
    r"^(see job sheet|n/?a|none|nil|-|as above|see above)?\.?$",
    re.IGNORECASE,
)

INSUFFICIENT_DATA_WORD_THRESHOLD = 3


def parse_timestamp(value):
    return datetime.fromisoformat(value).astimezone(timezone.utc)


def calculate_duration_hours(arrived_at, departed_at):
    arrived = parse_timestamp(arrived_at)
    departed = parse_timestamp(departed_at)
    delta = departed - arrived
    return delta.total_seconds() / 3600


def format_duration(hours):
    total_minutes = round(hours * 60)
    h, m = divmod(total_minutes, 60)
    if h and m:
        return f"{h}h {m}min"
    if h:
        return f"{h}h"
    return f"{m}min"


def _is_insufficient_data_by_length(resolution_text, notes_text):
    """Word-count based secondary detection for insufficient data.

    Returns True if both resolution and notes are suspiciously brief,
    regardless of the specific words used. This catches vague reports
    that regex patterns might miss.

    A report is considered insufficient if:
    - Resolution has ≤5 words AND
    - Notes have ≤5 words (including empty)
    """
    resolution_words = len(resolution_text.split())
    notes_words = len(notes_text.split())
    return resolution_words <= INSUFFICIENT_DATA_WORD_THRESHOLD and notes_words <= INSUFFICIENT_DATA_WORD_THRESHOLD


def detect_flags(report, calculated_duration_hours):
    flags = []

    stated = report.get("stated_duration_hours")
    if stated is not None and calculated_duration_hours is not None:
        diff_minutes = abs(calculated_duration_hours - stated) * 60
        if diff_minutes > DURATION_TOLERANCE_MINUTES:
            flags.append({
                "type": "duration_mismatch",
                "detail": (
                    f"Calculated duration is {format_duration(calculated_duration_hours)} "
                    f"but technician reported {format_duration(stated)}."
                ),
            })

    parts_used = report.get("parts_used", [])
    resolution = report.get("resolution", "")
    has_parts = isinstance(parts_used, list) and len(parts_used) > 0
    resolution_says_no_parts = bool(NO_PARTS_PATTERNS.search(resolution))
    resolution_says_parts_fitted = bool(PARTS_FITTED_PATTERNS.search(resolution))

    if has_parts and resolution_says_no_parts:
        flags.append({
            "type": "parts_mismatch",
            "detail": (
                "Parts list is non-empty but resolution states no parts were required."
            ),
        })
    elif not has_parts and resolution_says_parts_fitted:
        flags.append({
            "type": "parts_mismatch",
            "detail": (
                "Resolution implies parts were fitted but parts list is empty."
            ),
        })

    resolution_text = resolution.strip()
    notes_text = report.get("technician_notes", "").strip()
    regex_match = VAGUE_RESOLUTION_PATTERNS.match(resolution_text) and VAGUE_NOTES_PATTERNS.match(notes_text)
    length_match = _is_insufficient_data_by_length(resolution_text, notes_text)
    if regex_match or length_match:
        flags.append({
            "type": "insufficient_data",
            "detail": "Resolution is a vague placeholder and technician notes are empty or minimal.",
        })

    return flags


def parse_report(raw, line_number):
    missing = [f for f in REQUIRED_FIELDS if f not in raw]
    if missing:
        return None, f"Line {line_number}: missing fields: {', '.join(missing)}"

    calculated_duration_hours = None
    try:
        calculated_duration_hours = calculate_duration_hours(
            raw["arrived_at"], raw["departed_at"]
        )
    except (ValueError, TypeError) as e:
        calculated_duration_hours = None

    flags = detect_flags(raw, calculated_duration_hours)

    return {
        "report_id": raw["report_id"],
        "asset": raw["asset"],
        "technician_id": raw["technician_id"],
        "arrived_at": raw["arrived_at"],
        "departed_at": raw["departed_at"],
        "stated_duration_hours": raw["stated_duration_hours"],
        "parts_used": raw["parts_used"],
        "resolution": raw["resolution"],
        "technician_notes": raw["technician_notes"],
        "calculated_duration_hours": calculated_duration_hours,
        "calculated_duration_formatted": (
            format_duration(calculated_duration_hours)
            if calculated_duration_hours is not None
            else None
        ),
        "flags": flags,
    }, None


def parse_jsonl(filepath):
    reports = []
    warnings = []

    with open(filepath, "r", encoding="utf-8") as f:
        for line_number, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                raw = json.loads(line)
            except json.JSONDecodeError as e:
                warnings.append(f"Line {line_number}: invalid JSON — {e}")
                continue

            report, warning = parse_report(raw, line_number)
            if warning:
                warnings.append(warning)
                continue
            reports.append(report)

    return reports, warnings
