import time
from llm_client import LLMClient

REQUEST_DELAY = 2


def process_reports(reports, progress_callback=None):
    client = LLMClient()
    results = []
    total = len(reports)

    for i, report in enumerate(reports):
        if i > 0:
            time.sleep(REQUEST_DELAY)

        result = _process_single(client, report)
        results.append(result)
        if progress_callback:
            progress_callback(i + 1, total)

    return results


def _process_single(client, report):
    report_id = report["report_id"]
    asset = report["asset"]
    flags = report["flags"]

    llm_result = client.summarize(report)

    if llm_result["error"]:
        return {
            "report_id": report_id,
            "asset": asset,
            "summary_text": None,
            "status": "Review",
            "status_reason": f"API error: {llm_result['error']}",
        }

    reasons = []

    for flag in flags:
        reasons.append(flag["detail"])

    if llm_result["injection_detected"]:
        reasons.append(
            "Possible prompt injection detected in technician notes. "
            "Verify the original report with the submitting engineer."
        )

    status = "Review" if reasons else "OK"

    return {
        "report_id": report_id,
        "asset": asset,
        "summary_text": llm_result["summary"],
        "status": status,
        "status_reason": " | ".join(reasons) if reasons else "",
    }
