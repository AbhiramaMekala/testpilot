"""Turn a directory of JUnit XML files into flat, analysable rows."""
from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from dataclasses import asdict, dataclass
from pathlib import Path

REQ_RE = re.compile(r"(REQ-\d+)")
SUITE_RE = re.compile(r"(smoke|sanity|integration|regression)", re.I)


@dataclass
class TestResult:
    run_id: str
    suite: str
    classname: str
    name: str
    status: str          # passed | failed | error | skipped
    duration_s: float
    requirement: str
    message: str


def _status(case: ET.Element) -> tuple[str, str]:
    for tag, status in (("failure", "failed"), ("error", "error"), ("skipped", "skipped")):
        node = case.find(tag)
        if node is not None:
            msg = (node.get("message") or node.text or "").strip().splitlines()
            return status, (msg[0][:200] if msg else "")
    return "passed", ""


def _suite_of(case: ET.Element, fallback: str) -> str:
    """Prefer the explicit pytest marker property; fall back to the module
    name, since `tests.test_integration` carries the same information."""
    for prop in case.iterfind("./properties/property"):
        if prop.get("name", "").lower() in ("suite", "marker", "markers"):
            value = prop.get("value", "")
            match = SUITE_RE.search(value)
            if match:
                return match.group(1).lower()
    haystack = f"{case.get('classname','')} {case.get('name','')} {fallback}"
    match = SUITE_RE.search(haystack)
    return match.group(1).lower() if match else "other"


def _requirement(case: ET.Element) -> str:
    """Requirement id from a pytest property, else from the test's own text."""
    for prop in case.iterfind("./properties/property"):
        if prop.get("name", "").lower() in ("requirement", "req", "requirements"):
            return prop.get("value", "")
    match = REQ_RE.search(f"{case.get('name','')} {case.get('classname','')}")
    return match.group(1) if match else ""


def parse_file(path: Path) -> list[TestResult]:
    root = ET.parse(path).getroot()
    suites = [root] if root.tag == "testsuite" else root.findall("testsuite")
    rows: list[TestResult] = []
    for suite in suites:
        suite_name = suite.get("name", "")
        for case in suite.findall("testcase"):
            status, message = _status(case)
            rows.append(TestResult(
                run_id=path.stem,
                suite=_suite_of(case, suite_name),
                classname=case.get("classname", ""),
                name=case.get("name", ""),
                status=status,
                duration_s=round(float(case.get("time", 0) or 0), 4),
                requirement=_requirement(case),
                message=message,
            ))
    return rows


def parse_dir(directory: Path) -> list[dict]:
    rows: list[TestResult] = []
    for path in sorted(directory.glob("*.xml")):
        rows.extend(parse_file(path))
    return [asdict(r) for r in rows]
