from datetime import datetime, timezone


def build_markdown(results):
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    lines = [
        "# Service Report Summaries",
        "",
        f"Generated: {timestamp}",
        "",
    ]

    for r in results:
        lines.append(f"## {r['report_id']} — {r['asset']}")
        lines.append("")

        if r["summary_text"]:
            lines.append(r["summary_text"])
        else:
            lines.append("*Summary could not be generated for this report.*")
        lines.append("")

        if r["status"] == "Review":
            lines.append("> **Requires review:** " + r["status_reason"])
            lines.append("")

        lines.append("---")
        lines.append("")

    return "\n".join(lines)
