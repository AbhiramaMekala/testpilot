"""Metrics a QA lead actually asks for: pass rate, flaky tests, slow tests,
and which requirements have no test behind them."""
from __future__ import annotations

from collections import defaultdict
from statistics import median

FAIL_STATES = {"failed", "error"}


def _key(row: dict) -> str:
    return f"{row['classname']}::{row['name']}"


def run_summary(rows: list[dict]) -> list[dict]:
    by_run: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        by_run[row["run_id"]].append(row)
    out = []
    for run_id, group in sorted(by_run.items()):
        total = len(group)
        failed = sum(r["status"] in FAIL_STATES for r in group)
        skipped = sum(r["status"] == "skipped" for r in group)
        executed = total - skipped
        out.append({
            "run_id": run_id,
            "total": total,
            "passed": total - failed - skipped,
            "failed": failed,
            "skipped": skipped,
            "pass_rate_pct": round(100 * (executed - failed) / executed, 2) if executed else 0.0,
            "duration_s": round(sum(r["duration_s"] for r in group), 3),
        })
    return out


def suite_summary(rows: list[dict]) -> list[dict]:
    by_suite: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        by_suite[row["suite"]].append(row)
    out = []
    for suite, group in sorted(by_suite.items()):
        failed = sum(r["status"] in FAIL_STATES for r in group)
        out.append({
            "suite": suite,
            "executions": len(group),
            "failures": failed,
            "pass_rate_pct": round(100 * (len(group) - failed) / len(group), 2),
            "median_duration_s": round(median(r["duration_s"] for r in group), 4),
        })
    return out


def _history(rows: list[dict]) -> dict[str, list[dict]]:
    history: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        history[_key(row)].append(row)
    for runs in history.values():
        runs.sort(key=lambda r: r["run_id"])
    return history


def flaky_tests(rows: list[dict], min_runs: int = 3) -> list[dict]:
    """A test that alternates between pass and fail with nothing else changing
    is flaky, and costs more trust than the bug it was meant to catch.

    A test that failed in every early run and has passed ever since is NOT
    flaky - it is a defect that got fixed. Counting those as flaky is the
    usual way this metric becomes noise nobody reads, so they are excluded.
    """
    out = []
    for key, runs in _history(rows).items():
        if len(runs) < min_runs:
            continue
        statuses = [r["status"] for r in runs]
        if not ("passed" in statuses and set(statuses) & FAIL_STATES):
            continue
        failed = [s in FAIL_STATES for s in statuses]
        transitions = sum(a != b for a, b in zip(failed, failed[1:]))
        if _contiguous(failed):
            # Every failure sits in one unbroken block. Something broke at a
            # known build and was fixed at a known build - that is a regression
            # with a start and an end, not a test that cannot make up its mind.
            # Calling it flaky is how this metric fills with noise and stops
            # being read.
            continue
        failures = sum(failed)
        out.append({
            "test": key,
            "suite": runs[0]["suite"],
            "runs": len(runs),
            "failures": failures,
            "flake_rate_pct": round(100 * failures / len(runs), 2),
            "transitions": transitions,
            "last_message": next((r["message"] for r in reversed(runs) if r["message"]), ""),
        })
    return sorted(out, key=lambda r: -r["flake_rate_pct"])


def _contiguous(failed: list[bool]) -> bool:
    """True when every failure sits in one unbroken run of builds."""
    if not any(failed):
        return True
    first, last = failed.index(True), len(failed) - 1 - failed[::-1].index(True)
    return all(failed[first:last + 1])


def regressions(rows: list[dict], min_runs: int = 3) -> list[dict]:
    """A test that was green, went red for a stretch, and is green again.

    Reported separately from flakiness because the response is different: a
    regression has a build that broke it and a build that fixed it, so there is
    a diff to look at. A flaky test has neither.
    """
    out = []
    for key, runs in _history(rows).items():
        if len(runs) < min_runs:
            continue
        failed = [r["status"] in FAIL_STATES for r in runs]
        if not any(failed) or not _contiguous(failed):
            continue
        first = failed.index(True)
        last = len(failed) - 1 - failed[::-1].index(True)
        out.append({
            "test": key,
            "suite": runs[0]["suite"],
            "broke_at": runs[first]["run_id"],
            "failing_runs": sum(failed),
            "status_now": "green again" if not failed[-1] else "STILL FAILING",
            "green_since": runs[last + 1]["run_id"] if not failed[-1] else "",
        })
    return sorted(out, key=lambda r: r["test"])


def recently_fixed(rows: list[dict], min_runs: int = 3) -> list[dict]:
    """Kept as an alias of regressions() that are now green."""
    return [r for r in regressions(rows, min_runs) if r["status_now"] == "green again"]


def always_failing(rows: list[dict]) -> list[dict]:
    history = _history(rows)
    return sorted(
        ({"test": k, "suite": v[0]["suite"], "runs": len(v), "last_message": v[-1]["message"]}
         for k, v in history.items()
         if v and all(r["status"] in FAIL_STATES for r in v)),
        key=lambda r: r["test"])


def slowest_tests(rows: list[dict], top: int = 10) -> list[dict]:
    history: dict[str, list[float]] = defaultdict(list)
    for row in rows:
        history[_key(row)].append(row["duration_s"])
    ranked = sorted(((k, median(v)) for k, v in history.items()), key=lambda x: -x[1])
    return [{"test": k, "median_duration_s": round(v, 4)} for k, v in ranked[:top]]


def traceability(rows: list[dict], requirements: list[str]) -> list[dict]:
    """Requirement -> tests covering it, and whether it is currently green.
    An uncovered requirement is a gap; a covered-but-red one is a defect."""
    covered: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        if row["requirement"]:
            covered[row["requirement"]].append(row)
    out = []
    for req in sorted(set(requirements) | set(covered)):
        runs = covered.get(req, [])
        tests = sorted({_key(r) for r in runs})
        latest = {}
        for r in runs:
            latest[_key(r)] = r["status"]
        if not tests:
            state = "NOT COVERED"
        elif any(s in FAIL_STATES for s in latest.values()):
            state = "COVERED - FAILING"
        else:
            state = "COVERED - PASSING"
        out.append({
            "requirement": req,
            "tests_covering": len(tests),
            "state": state,
            "tests": "; ".join(t.split("::")[-1] for t in tests),
        })
    return out


def coverage_pct(trace: list[dict]) -> float:
    if not trace:
        return 0.0
    covered = sum(1 for t in trace if t["state"] != "NOT COVERED")
    return round(100 * covered / len(trace), 2)
