#!/usr/bin/env python3
"""
qa-metrics: JUnit XML in, QA dashboard and Power BI CSVs out.

    python cli.py --input samples --out out --requirements requirements.txt
"""
from __future__ import annotations

import argparse
from pathlib import Path

from src import metrics
from src.parse_junit import parse_dir
from src.report import write_csvs, write_html


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--input", type=Path, required=True, help="directory of JUnit XML files")
    ap.add_argument("--out", type=Path, default=Path("out"))
    ap.add_argument("--requirements", type=Path,
                    help="text file of requirement ids, one per line, to find gaps")
    ap.add_argument("--fail-under", type=float, default=None,
                    help="exit non-zero if the latest pass rate is below this")
    args = ap.parse_args()

    rows = parse_dir(args.input)
    if not rows:
        print(f"no JUnit XML found in {args.input}")
        return 2

    required = []
    if args.requirements and args.requirements.exists():
        required = [l.strip() for l in args.requirements.read_text().splitlines() if l.strip()]

    runs = metrics.run_summary(rows)
    trace = metrics.traceability(rows, required)
    context = {
        "runs": runs,
        "suites": metrics.suite_summary(rows),
        "flaky": metrics.flaky_tests(rows),
        "fixed": metrics.regressions(rows),
        "failing": metrics.always_failing(rows),
        "slowest": metrics.slowest_tests(rows),
        "traceability": trace,
        "coverage_pct": metrics.coverage_pct(trace),
    }

    write_csvs({"results": rows, "runs": runs, "suites": context["suites"],
                "flaky": context["flaky"], "fixed": context["fixed"],
                "traceability": trace}, args.out / "csv")
    html_path = write_html(context, args.out / "dashboard.html")

    latest = runs[-1]
    print(f"runs parsed      : {len(runs)}")
    print(f"test executions  : {len(rows)}")
    print(f"latest pass rate : {latest['pass_rate_pct']}%  ({latest['failed']} failing)")
    print(f"flaky tests      : {len(context['flaky'])}")
    broke = [r for r in context['fixed'] if r['status_now'] == 'STILL FAILING']
    print(f"regressions      : {len(context['fixed'])} "
          f"({len(broke)} still failing, {len(context['fixed']) - len(broke)} fixed)")
    print(f"req. coverage    : {context['coverage_pct']}%")
    print(f"dashboard        : {html_path}")
    print(f"power bi csvs    : {args.out / 'csv'}")

    if args.fail_under is not None and latest["pass_rate_pct"] < args.fail_under:
        print(f"FAIL: pass rate {latest['pass_rate_pct']}% below threshold {args.fail_under}%")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
