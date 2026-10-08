#!/usr/bin/env python3
"""
Requirements document -> executable tests -> run them -> triage what failed.

    python3 cli.py                      # generate and run
    python3 cli.py --no-run             # generate only
    python3 cli.py --triage <junit-dir> # group failures into real problems
"""
from __future__ import annotations

import argparse
import csv
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT))

from src import llm, triage                       # noqa: E402
from src.generator import CONFTEST, generate, to_module   # noqa: E402


def cmd_generate(args) -> int:
    document = args.spec.read_text()
    cases, mode, notes = generate(document)
    if not cases:
        for note in notes:
            print(f"  {note}")
        return 2

    args.out.mkdir(parents=True, exist_ok=True)
    module = args.out / "test_generated.py"
    module.write_text(to_module(cases))
    (args.out / "conftest.py").write_text(CONFTEST)

    with (args.out / "test_cases.csv").open("w", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(["requirement", "action", "source", "description"])
        for case in cases:
            writer.writerow([case.requirement, case.action, case.source, case.text])

    print(f"  source          : {mode}" + (f"  ({llm.available()})" if llm.available() else ""))
    print(f"  requirements    : {len(cases)} mapped to an executable test")
    for case in cases:
        print(f"    {case.requirement:<16} -> {case.action}")
    for note in notes:
        print(f"  note            : {note}")
    print(f"  written         : {module}")

    if args.no_run:
        return 0

    print("\n  running the generated tests against https://www.saucedemo.com ...\n")
    junit = args.out / "junit.xml"
    command = [sys.executable, "-m", "pytest", str(module), "-q",
               "-p", "no:cacheprovider", f"--junitxml={junit}"]
    if args.headed:
        command.append("--headed")
    if args.slow_mo:
        command += ["--slow-mo", str(args.slow_mo)]
    result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True)
    for line in result.stdout.strip().splitlines()[-12:]:
        print(f"    {line}")
    print(f"\n  results written : {junit}")
    return 0


def cmd_triage(args) -> int:
    failures = triage.collect_failures(args.triage)
    clusters = triage.cluster(failures)
    summary, source = triage.summarise(clusters)
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "triage_report.md").write_text(
        f"# Failure triage\n\n{len(failures)} failures -> "
        f"**{len(clusters)} distinct problem(s)**\n\n{summary}\n")
    print(f"  failures        : {len(failures)}")
    print(f"  real problems   : {len(clusters)}")
    for cluster in clusters:
        print(f"    [{cluster['category']:<22}] x{cluster['occurrences']:<3} "
              f"{cluster['signature'][:66]}")
    print(f"  written         : {args.out / 'triage_report.md'}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--spec", type=Path, default=ROOT / "requirements.md")
    ap.add_argument("--out", type=Path, default=ROOT / "out")
    ap.add_argument("--no-run", action="store_true")
    ap.add_argument("--headed", action="store_true", help="show the browser")
    ap.add_argument("--slow-mo", type=int, default=0, metavar="MS")
    ap.add_argument("--triage", type=Path, help="directory of JUnit XML to triage")
    args = ap.parse_args()
    return cmd_triage(args) if args.triage else cmd_generate(args)


if __name__ == "__main__":
    raise SystemExit(main())
