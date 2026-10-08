#!/usr/bin/env python3
"""
Builds one self-contained HTML report for the run that just finished.

Opening raw .py and .md files in a text editor tells a viewer nothing. This
collects what all three projects produced into a single page a person can read
top to bottom and understand without being walked through it.
"""
from __future__ import annotations

import csv
import html
import json
import sys
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).parent
P1_XML = ROOT / "2-quality-dashboard" / "sample-runs" / "build-007.xml"
CSV_DIR = ROOT / "2-quality-dashboard" / "out" / "csv"
DASHBOARD = ROOT / "2-quality-dashboard" / "out" / "dashboard.html"
GEN_DIR = ROOT / "3-ai-test-generator" / "out"


def read_junit(path: Path) -> dict:
    if not path.exists():
        return {}
    root = ET.parse(path).getroot()
    suites = [root] if root.tag == "testsuite" else root.findall("testsuite")
    cases = []
    for suite in suites:
        for case in suite.findall("testcase"):
            failure = case.find("failure") if case.find("failure") is not None else case.find("error")
            cases.append({
                "name": case.get("name", ""),
                "suite": (case.get("classname", "") or "").split(".")[-1],
                "time": float(case.get("time", 0) or 0),
                "ok": failure is None,
                "message": (failure.get("message") if failure is not None else "") or "",
            })
    return {
        "cases": cases,
        "total": len(cases),
        "passed": sum(c["ok"] for c in cases),
        "failed": sum(not c["ok"] for c in cases),
        "duration": round(sum(c["time"] for c in cases), 1),
    }


def read_csv(path: Path) -> list[dict]:
    if not path.exists() or not path.stat().st_size:
        return []
    with path.open() as fh:
        return list(csv.DictReader(fh))


def card(value, label, tone="") -> str:
    return (f'<div class="card {tone}"><div class="k">{html.escape(str(value))}</div>'
            f'<div class="l">{html.escape(label)}</div></div>')


def table(rows: list[dict], columns: list[str] | None = None, empty="nothing to show") -> str:
    if not rows:
        return f'<p class="empty">{html.escape(empty)}</p>'
    columns = columns or list(rows[0])
    head = "".join(f"<th>{html.escape(c.replace('_', ' '))}</th>" for c in columns)
    body = ""
    for row in rows:
        cells = ""
        for c in columns:
            value = str(row.get(c, ""))
            cls = ""
            if value in ("PASS", "green again"):
                cls = "good"
            elif value in ("FAIL", "NOT COVERED", "STILL FAILING"):
                cls = "bad"
            cells += f'<td class="{cls}">{html.escape(value)}</td>'
        body += f"<tr>{cells}</tr>"
    return f"<table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table>"


def trend_svg(runs: list[dict]) -> str:
    if not runs:
        return ""
    values = [float(r["pass_rate_pct"]) for r in runs]
    labels = [r["run_id"] for r in runs]
    width, height, pad = 720, 170, 34
    low = min(80.0, min(values) - 3)
    x = lambda i: pad + (width - 2 * pad) * (0 if len(values) == 1 else i / (len(values) - 1))
    y = lambda v: height - pad - (height - 2 * pad) * ((v - low) / ((100 - low) or 1))
    parts = []
    for gl in (low, (low + 100) / 2, 100.0):
        parts.append(f'<line x1="{pad}" y1="{y(gl):.1f}" x2="{width-pad}" y2="{y(gl):.1f}" '
                     f'stroke="currentColor" stroke-opacity=".13"/>')
        parts.append(f'<text x="2" y="{y(gl)+4:.1f}" font-size="11" fill="currentColor" '
                     f'fill-opacity=".5">{gl:.0f}%</text>')
    points = " ".join(f"{x(i):.1f},{y(v):.1f}" for i, v in enumerate(values))
    parts.append(f'<polyline points="{points}" fill="none" stroke="var(--accent)" '
                 f'stroke-width="2.5" stroke-linejoin="round"/>')
    for i, v in enumerate(values):
        colour = "var(--bad)" if v < 100 else "var(--accent)"
        parts.append(f'<circle cx="{x(i):.1f}" cy="{y(v):.1f}" r="4" fill="{colour}">'
                     f'<title>{html.escape(labels[i])}: {v}%</title></circle>')
    return (f'<svg viewBox="0 0 {width} {height}" preserveAspectRatio="none" role="img" '
            f'aria-label="Pass rate per build">{"".join(parts)}</svg>')


def main() -> int:
    mode = sys.argv[1] if len(sys.argv) > 1 else "run"
    now = datetime.now().strftime("%d %B %Y, %H:%M")

    p1 = read_junit(P1_XML)
    runs = read_csv(CSV_DIR / "runs.csv")
    regressions = read_csv(CSV_DIR / "fixed.csv")
    flaky = read_csv(CSV_DIR / "flaky.csv")
    trace = read_csv(CSV_DIR / "traceability.csv")
    uncovered = [r for r in trace if r.get("state") == "NOT COVERED"]
    gen_cases = read_csv(GEN_DIR / "test_cases.csv")
    gen_run = read_junit(GEN_DIR / "junit.xml")
    triage = (GEN_DIR / "triage_report.md").read_text() if (GEN_DIR / "triage_report.md").exists() else ""
    gen_code = (GEN_DIR / "test_generated.py").read_text() if (GEN_DIR / "test_generated.py").exists() else ""

    # the first generated test, shown as proof the output is real code
    snippet = ""
    if "@pytest.mark" in gen_code:
        block = gen_code[gen_code.index("@pytest.mark"):]
        snippet = "\n".join(block.splitlines()[:11])

    triage_lines = [l for l in triage.splitlines() if l.startswith("- [")]

    sections = []

    # ---- project 1
    sections.append(f'''
<section>
  <h2><span class="num">1</span> UI Test Automation <span class="sub">— ran the tests</span></h2>
  <p class="what">Drove a real Chrome browser through <a href="https://www.saucedemo.com">saucedemo.com</a>:
     logged in, added products to the cart, checked out. One class per screen, so a test never
     contains a CSS selector.</p>
  <div class="cards">
    {card(p1.get("total", "–"), "tests run")}
    {card(p1.get("passed", "–"), "passed", "good")}
    {card(p1.get("failed", "–"), "failed", "bad" if p1.get("failed") else "")}
    {card(f'{p1.get("duration", 0)}s', "duration")}
  </div>
  {table([{"test": c["name"], "suite": c["suite"], "result": "PASS" if c["ok"] else "FAIL",
           "seconds": f'{c["time"]:.2f}', "message": c["message"][:90]}
          for c in p1.get("cases", [])],
         ["test", "suite", "result", "seconds", "message"],
         "project 1 was skipped on this run")}
</section>''')

    # ---- project 2
    sections.append(f'''
<section>
  <h2><span class="num">2</span> Quality &amp; Metrics Dashboard <span class="sub">— read the results</span></h2>
  <p class="what">Project 1 only knows about right now. This reads every past build together:
     the pass-rate trend, which tests are unreliable, and which requirements have no test behind them.</p>
  <div class="cards">
    {card(len(runs), "builds analysed")}
    {card(f'{runs[-1]["pass_rate_pct"]}%' if runs else "–", "latest pass rate")}
    {card(len(flaky), "flaky tests", "bad" if flaky else "good")}
    {card(len(regressions), "regressions")}
    {card(len(uncovered), "requirements with no test", "bad" if uncovered else "good")}
  </div>
  <h3>Pass rate per build</h3>
  {trend_svg(runs)}
  <h3>Regressions — broke at a known build, fixed at a known build</h3>
  {table(regressions, ["test", "broke_at", "failing_runs", "status_now", "green_since"],
         "no regressions in this window")}
  <h3>Requirements with no test behind them</h3>
  {table([{"requirement": r["requirement"], "state": r["state"]} for r in uncovered],
         ["requirement", "state"], "every requirement has a test")}
  <p class="more">Full interactive dashboard: <a href="{DASHBOARD.as_uri()}">dashboard.html</a></p>
</section>''')

    # ---- project 3
    triage_html = "".join(f"<li>{html.escape(l[2:])}</li>" for l in triage_lines) or "<li>no failures</li>"
    generated_this_run = bool(gen_cases)
    if not generated_this_run:
        sections.append(f'''
<section>
  <h2><span class="num">3</span> AI Test Generator <span class="sub">— wrote the tests</span></h2>
  <p class="what">The generator did not run in this mode, so there is nothing new to show for it.
     Its triage half did run, on every stored build — that is the table below.
     Run <code>./run.sh 3</code> to see the generation half on its own.</p>
  <h3>Failure triage — how many real problems?</h3>
  <ul class="triage">{triage_html}</ul>
</section>''')
        page = TEMPLATE.replace("__WHEN__", html.escape(now)) \
                       .replace("__MODE__", html.escape(mode)) \
                       .replace("__BODY__", "".join(sections))
        out = ROOT / "report.html"
        out.write_text(page)
        print(out)
        return 0
    sections.append(f'''
<section>
  <h2><span class="num">3</span> AI Test Generator <span class="sub">— wrote the tests</span></h2>
  <p class="what">Read a plain requirements document and produced <strong>executable</strong> Playwright
     tests, then ran them. Generation is constrained to a fixed vocabulary of page-object actions,
     so the output always imports and always runs — code that does not compile is worse than no test.</p>
  <div class="cards">
    {card(len(gen_cases), "requirements mapped")}
    {card(gen_run.get("total", "–"), "tests generated")}
    {card(gen_run.get("passed", "–"), "passed when run", "good")}
    {card(gen_run.get("failed", "–"), "failed", "bad" if gen_run.get("failed") else "")}
  </div>
  <h3>Requirement → test</h3>
  {table(gen_cases, ["requirement", "action", "source", "description"], "nothing generated")}
  <h3>What it actually wrote</h3>
  <pre><code>{html.escape(snippet) or "no code generated"}</code></pre>
  <h3>Failure triage — how many real problems?</h3>
  <ul class="triage">{triage_html}</ul>
</section>''')

    page = TEMPLATE.replace("__WHEN__", html.escape(now)) \
                   .replace("__MODE__", html.escape(mode)) \
                   .replace("__BODY__", "".join(sections))
    out = ROOT / "report.html"
    out.write_text(page)
    print(out)
    return 0


TEMPLATE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>TestPilot — Run Report</title>
<style>
:root{--bg:#f6f7f9;--fg:#15181d;--mut:#5c6673;--line:#e2e6eb;--card:#fff;
 --good:#146b3c;--bad:#b02520;--accent:#2250d8;--code:#f1f3f6}
*{box-sizing:border-box}
body{margin:0;padding:28px 18px 60px;background:var(--bg);color:var(--fg);
 font:15.5px/1.6 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif}
.wrap{max-width:980px;margin:0 auto}
header{margin-bottom:28px}
h1{font-size:25px;margin:0 0 4px;letter-spacing:-.02em}
.meta{color:var(--mut);font-size:14px}
section{background:var(--card);border:1px solid var(--line);border-radius:12px;
 padding:20px 22px;margin:18px 0}
h2{font-size:19px;margin:0 0 6px;letter-spacing:-.01em;display:flex;align-items:center;gap:10px}
h2 .num{display:inline-flex;align-items:center;justify-content:center;width:27px;height:27px;
 border-radius:50%;background:var(--accent);color:#fff;font-size:14px;flex:none}
h2 .sub{color:var(--mut);font-weight:400;font-size:15px}
h3{font-size:13px;text-transform:uppercase;letter-spacing:.07em;color:var(--mut);
 margin:22px 0 8px}
.what{color:var(--mut);margin:0 0 16px;max-width:76ch}
.cards{display:grid;gap:10px;grid-template-columns:repeat(auto-fit,minmax(135px,1fr));margin-bottom:4px}
.card{border:1px solid var(--line);border-radius:9px;padding:11px 13px;background:var(--bg)}
.card .k{font-size:24px;font-weight:650;letter-spacing:-.02em}
.card .l{color:var(--mut);font-size:12.5px;margin-top:1px}
.card.good .k{color:var(--good)} .card.bad .k{color:var(--bad)}
table{width:100%;border-collapse:collapse;font-size:13.5px;border:1px solid var(--line);
 border-radius:9px;overflow:hidden}
th,td{text-align:left;padding:7px 11px;border-bottom:1px solid var(--line);vertical-align:top}
th{background:var(--bg);font-size:11.5px;text-transform:uppercase;letter-spacing:.05em;color:var(--mut)}
tr:last-child td{border-bottom:none}
td.good{color:var(--good);font-weight:600} td.bad{color:var(--bad);font-weight:600}
.empty{color:var(--mut);font-style:italic}
pre{background:var(--code);border:1px solid var(--line);border-radius:9px;padding:13px 15px;
 overflow-x:auto;font-size:13px;line-height:1.5;margin:0}
code{font-family:ui-monospace,SFMono-Regular,Menlo,monospace}
svg{width:100%;height:170px;background:var(--bg);border:1px solid var(--line);border-radius:9px}
ul.triage{margin:0;padding-left:20px} ul.triage li{margin:5px 0}
.more{font-size:14px;color:var(--mut);margin:16px 0 0}
a{color:var(--accent)}
footer{color:var(--mut);font-size:14px;margin-top:26px;padding:0 4px}
@media(prefers-color-scheme:dark){:root:not([data-theme=light]){
 --bg:#0f1115;--fg:#e8ebf0;--mut:#98a2b0;--line:#252a33;--card:#161a20;--code:#12151a;
 --good:#5bd392;--bad:#ff8a80;--accent:#7ba1ff}}
</style></head><body><div class="wrap">
<header>
  <h1>TestPilot — Run Report</h1>
  <div class="meta">__WHEN__ &nbsp;·&nbsp; mode: __MODE__</div>
</header>
__BODY__
<footer>
  <strong>How they connect:</strong> project 1 writes a JUnit XML results file;
  projects 2 and 3 read it. JUnit XML is the format every test tool emits, which is
  why projects 2 and 3 work with any test suite, not only this one.
</footer>
</div></body></html>
"""

if __name__ == "__main__":
    raise SystemExit(main())
