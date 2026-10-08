"""Group a wall of CI failures into a short list of distinct defects."""
from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from collections import defaultdict
from pathlib import Path

from . import llm

# Strip the parts of a message that differ run to run, so the same underlying
# fault collapses to one signature instead of fifty.
NOISE = [
    # A trailing parenthetical is the test's own note about the case, not part
    # of the fault. Leaving it in splits one defect across every parametrised
    # case that hit it.
    (re.compile(r"\s+\((?![\'\"])[^()]*\s[^()]*\)\s*$"), ""),
    (re.compile(r"0x[0-9a-fA-F]+"), "<addr>"),
    (re.compile(r"(/[\w.\-]+)+"), "<path>"),
    (re.compile(r"\[[^\]]*\]"), "[<param>]"),
    # Channel identifiers: STATUS 1 and STATUS 2 failing the same way is one
    # problem, not two.
    (re.compile(r"\b(pump|tank|grade)\s*\d+\b", re.I), r"\1 <n>"),
    (re.compile(r"\b([A-Z]{3,12})\s+\d+\b"), r"\1 <n>"),
    (re.compile(r"\d+\.\d+"), "<num>"),
    (re.compile(r"\b\d{2,}\b"), "<num>"),
]

CAUSES = [
    # Checked before the generic timeout rule: "waiting for locator" and
    # "matched nothing" mean the automation looked for something that is not
    # there. That is almost always a selector the site has moved on from, and
    # calling it a product defect sends a QA engineer to argue with the wrong
    # team.
    (re.compile(r"waiting for locator|locator\.|strict mode violation|"
                r"matched \S*nothing|product grid never appeared|selector", re.I),
     "Test code (selector)", "The automation could not find an element. Check the "
     "selector in the page object before assuming the application is broken - a "
     "site redesign breaks tests without breaking the product."),
    (re.compile(r"timed out|timeout|readline|no response", re.I),
     "Environment or timing", "Device did not answer in time. Check the transport "
     "and the timeout before assuming the firmware is wrong."),
    (re.compile(r"connection|refused|reset|broken pipe|socket", re.I),
     "Infrastructure", "Transport dropped. Usually the harness or the test bench, "
     "not the device under test."),
    (re.compile(r"assert|!=|expected|mismatch", re.I),
     "Product defect", "Device returned a value that contradicts the spec. "
     "Most likely a genuine bug - raise a defect."),
    (re.compile(r"ERR |protocolerror", re.I),
     "Protocol or state", "Device rejected a command. Check whether the test "
     "left the pump in the wrong state."),
    (re.compile(r"fixture|import|modulenotfound|collection", re.I),
     "Test code", "The harness failed, not the product. Fix the test first."),
]

SYSTEM = ("You are a QA engineer triaging automated test failures for an "
          "embedded fuel-dispenser controller. Be concise and concrete. "
          "Never claim certainty about a root cause you cannot see.")


def signature(message: str) -> str:
    text = message.strip().splitlines()[0] if message.strip() else "(no message)"
    for pattern, replacement in NOISE:
        text = pattern.sub(replacement, text)
    return text[:160]


def classify(message: str) -> tuple[str, str]:
    for pattern, label, advice in CAUSES:
        if pattern.search(message):
            return label, advice
    return "Unclassified", "No matching heuristic. Read the full log."


def collect_failures(junit_dir: Path) -> list[dict]:
    failures = []
    for path in sorted(junit_dir.glob("*.xml")):
        root = ET.parse(path).getroot()
        suites = [root] if root.tag == "testsuite" else root.findall("testsuite")
        for suite in suites:
            for case in suite.findall("testcase"):
                for tag in ("failure", "error"):
                    node = case.find(tag)
                    if node is None:
                        continue
                    message = (node.get("message") or node.text or "").strip()
                    failures.append({
                        "run": path.stem,
                        "test": f"{case.get('classname','')}::{case.get('name','')}",
                        "message": message,
                    })
    return failures


def cluster(failures: list[dict]) -> list[dict]:
    groups: dict[str, list[dict]] = defaultdict(list)
    for failure in failures:
        groups[signature(failure["message"])].append(failure)
    clusters = []
    for sig, members in groups.items():
        category, advice = classify(members[0]["message"])
        clusters.append({
            "signature": sig,
            "category": category,
            "first_action": advice,
            "occurrences": len(members),
            "tests_affected": sorted({m["test"] for m in members}),
            "runs_affected": sorted({m["run"] for m in members}),
            "example": members[0]["message"][:300],
        })
    return sorted(clusters, key=lambda c: -c["occurrences"])


def summarise(clusters: list[dict]) -> tuple[str, str]:
    """One paragraph a human can paste into a defect record. Falls back to a
    rendered template when no model is reachable."""
    if llm.available():
        listing = "\n\n".join(
            f"[{c['category']}] x{c['occurrences']} - {c['signature']}\n"
            f"tests: {', '.join(c['tests_affected'][:4])}" for c in clusters[:8])
        try:
            return llm.complete(
                "Summarise these clustered test failures for a defect record. "
                "State what is broken, how many distinct problems there are, "
                "and what to investigate first.\n\n" + listing,
                system=SYSTEM, max_tokens=600).strip(), "llm"
        except llm.ModelUnavailable:
            pass
    if not clusters:
        return "No failures in the supplied runs.", "template"
    lines = [f"{len(clusters)} distinct failure signature(s) across "
             f"{sum(c['occurrences'] for c in clusters)} failures."]
    for cluster_ in clusters[:5]:
        lines.append(
            f"- [{cluster_['category']}] {cluster_['signature']} "
            f"(x{cluster_['occurrences']}, {len(cluster_['tests_affected'])} test(s)). "
            f"{cluster_['first_action']}")
    return "\n".join(lines), "template"
