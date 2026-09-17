"""Run the summarizer pipeline against test_edge_cases.jsonl and print results."""
import sys
import time
from report_parser import parse_jsonl
from llm_client import LLMClient

REQUEST_DELAY = 2

def main():
    filepath = "test_edge_cases.jsonl"
    reports, warnings = parse_jsonl(filepath)

    for w in warnings:
        print(f"[PARSE WARNING] {w}")

    if not reports:
        print("No reports parsed.")
        return

    client = LLMClient()

    for i, report in enumerate(reports):
        if i > 0:
            time.sleep(REQUEST_DELAY)

        print("=" * 80)
        print(f"REPORT: {report['report_id']} | Asset: {report['asset']}")
        print(f"Flags: {report['flags']}")
        print("-" * 80)

        llm_result = client.summarize(report)

        if llm_result["error"]:
            print(f"[ERROR] {llm_result['error']}")
        else:
            print(f"INJECTION DETECTED: {llm_result['injection_detected']}")
            print()
            print(llm_result["summary"])

        # Determine status
        reasons = []
        for flag in report["flags"]:
            reasons.append(flag["detail"])
        if llm_result["injection_detected"]:
            reasons.append("Possible prompt injection detected")
        status = "Review" if reasons else "OK"
        print()
        print(f"STATUS: {status}")
        if reasons:
            print(f"REASONS: {' | '.join(reasons)}")
        print()

if __name__ == "__main__":
    main()
