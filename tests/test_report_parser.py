#!/usr/bin/env python3
"""
Unit tests for report_parser.py against real PGAWR report files.
Tests parsing quality, edge cases, and content extraction.
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from backend.core.report_parser import parse_html_report

REPORTS_DIR = Path(__file__).resolve().parent.parent.parent / "reports"
REPORT1 = REPORTS_DIR / "PGAWR_13558_13559_172.24.202.145_EXTENDED.html"
REPORT2 = REPORTS_DIR / "PGAWR_13560_13561_172.24.202.145_EXTENDED.html"

results = []


def record(test: str, passed: bool, detail: str = ""):
    results.append({"test": test, "passed": passed, "detail": detail})
    status = "PASS" if passed else "FAIL"
    print(f"  [{status}] {test}" + (f" -- {detail[:150]}" if detail else ""))


def test_report1():
    print("\n=== Report 1: PGAWR_13558_13559 ===")
    html = REPORT1.read_text(encoding="utf-8", errors="replace")
    record("Report1 file loaded", len(html) > 1000, f"size={len(html)} chars")

    parsed = parse_html_report(html, REPORT1.name)
    record("parse_html_report returns non-empty", len(parsed) > 100, f"parsed_len={len(parsed)}")

    record("Contains report filename", REPORT1.name in parsed, "")
    record("Contains DB Name (paaspg)", "paaspg" in parsed, "")
    record("Contains DB Host (172.24.202.145)", "172.24.202.145" in parsed, "")
    record("Contains Postgres version (15.15)", "15.15" in parsed, "")
    record("Contains snapshot IDs (13558)", "13558" in parsed, "")
    record("Contains snapshot IDs (13559)", "13559" in parsed, "")
    record("Contains 'System Information' or table headers",
           "System" in parsed or "Server Info" in parsed or "CPU" in parsed, "")
    record("Contains table-like content (pipe-delimited)",
           "| " in parsed and " |" in parsed, "Has markdown table rows")

    # Check sections
    for keyword in ["Top SQLs", "DB Statistics", "Vacuum", "Session", "IO"]:
        found = keyword.lower() in parsed.lower()
        record(f"Contains section: {keyword}", found, "")

    record("Parsed output size reasonable (>500 chars)", len(parsed) > 500,
           f"len={len(parsed)}")
    record("No 'Could not extract' fallback message",
           "Could not extract" not in parsed, "")

    return parsed


def test_report2():
    print("\n=== Report 2: PGAWR_13560_13561 ===")
    html = REPORT2.read_text(encoding="utf-8", errors="replace")
    record("Report2 file loaded", len(html) > 1000, f"size={len(html)} chars")

    parsed = parse_html_report(html, REPORT2.name)
    record("parse_html_report returns non-empty", len(parsed) > 100, f"parsed_len={len(parsed)}")

    record("Contains snapshot IDs (13560)", "13560" in parsed, "")
    record("Contains snapshot IDs (13561)", "13561" in parsed, "")
    record("Contains report start time (15:30)", "15:30" in parsed, "")

    return parsed


def test_edge_cases():
    print("\n=== Edge Cases ===")

    # Empty HTML
    try:
        result = parse_html_report("", "empty.html")
        record("Empty HTML: no exception", True, f"result_len={len(result)}")
        record("Empty HTML: contains fallback or filename", 
               "empty.html" in result or "Could not extract" in result, result[:100])
    except Exception as e:
        record("Empty HTML: exception raised", False, str(e))

    # Malformed HTML
    try:
        result = parse_html_report("<html><body><table><tr><td>broken", "broken.html")
        record("Malformed HTML: no exception", True, f"result_len={len(result)}")
    except Exception as e:
        record("Malformed HTML: exception raised", False, str(e))

    # Just text, no tables
    try:
        result = parse_html_report("<html><body><p>Just a paragraph</p></body></html>", "plain.html")
        record("Plain HTML (no tables): no exception", True, f"result_len={len(result)}")
    except Exception as e:
        record("Plain HTML: exception raised", False, str(e))

    # Nested tables
    try:
        nested = "<html><body><table><tr><th>A</th></tr><tr><td><table><tr><td>inner</td></tr></table></td></tr></table></body></html>"
        result = parse_html_report(nested, "nested.html")
        record("Nested tables: no exception", True, f"result_len={len(result)}")
    except Exception as e:
        record("Nested tables: exception raised", False, str(e))

    # Very large content
    try:
        large = "<html><body>" + "<table><tr><th>H</th></tr>" + "<tr><td>X</td></tr>" * 10000 + "</table></body></html>"
        result = parse_html_report(large, "large.html")
        record("Large HTML (10k rows): no exception", True, f"result_len={len(result)}")
        record("Large HTML: truncation applied (<=50 rows in output)",
               result.count("| X |") <= 50, f"row_count={result.count('| X |')}")
    except Exception as e:
        record("Large HTML: exception raised", False, str(e))


def test_comparison_detection():
    """Test ChatSession's _detect_report_groups with both reports."""
    print("\n=== Report Comparison Detection ===")
    try:
        from backend.core.chat_session import ChatSession
        session = ChatSession()
        
        html1 = REPORT1.read_text(encoding="utf-8", errors="replace")
        parsed1 = parse_html_report(html1, REPORT1.name)
        session.add_report(REPORT1.name, parsed1)
        
        html2 = REPORT2.read_text(encoding="utf-8", errors="replace")
        parsed2 = parse_html_report(html2, REPORT2.name)
        session.add_report(REPORT2.name, parsed2)

        record("Two reports added to session", len(session.reports) == 2,
               f"count={len(session.reports)}")

        groups = session._detect_report_groups()
        record("Report group detection finds groups", len(groups) > 0,
               f"groups={groups}")
        
        # Check that both reports are in the same group
        if groups:
            first_group = list(groups.values())[0]
            record("Both reports in same group",
                   REPORT1.name in first_group and REPORT2.name in first_group,
                   f"group={first_group}")
        
        # Build system prompt and check comparison instructions
        prompt = session.build_system_prompt()
        record("System prompt includes comparison instructions",
               "Report Comparison" in prompt or "comparison" in prompt.lower(),
               f"prompt_len={len(prompt)}")
        
    except Exception as e:
        record("Comparison detection", False, str(e))


def main():
    print("=" * 60)
    print("Report Parser Unit Tests")
    print("=" * 60)

    parsed1 = test_report1()
    parsed2 = test_report2()
    test_edge_cases()
    test_comparison_detection()

    total = len(results)
    passed = sum(1 for r in results if r["passed"])
    failed = sum(1 for r in results if not r["passed"])
    print("\n" + "=" * 60)
    print(f"TOTAL: {total} | PASSED: {passed} | FAILED: {failed}")
    print("=" * 60)

    out_path = REPORTS_DIR / "parser_test_results.json"
    with open(out_path, "w") as f:
        json.dump({"total": total, "passed": passed, "failed": failed, "results": results}, f, indent=2)
    print(f"\nJSON results written to {out_path}")

    # Also write parsed samples for review
    sample_path = REPORTS_DIR / "parsed_report_sample.txt"
    with open(sample_path, "w", encoding="utf-8") as f:
        if parsed1:
            f.write("=== REPORT 1 PARSED OUTPUT (first 3000 chars) ===\n\n")
            f.write(parsed1[:3000])
            f.write("\n\n")
        if parsed2:
            f.write("=== REPORT 2 PARSED OUTPUT (first 3000 chars) ===\n\n")
            f.write(parsed2[:3000])
    print(f"Parsed samples written to {sample_path}")


if __name__ == "__main__":
    main()
