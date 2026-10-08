"""Emit a Power BI-ready CSV set and a self-contained HTML dashboard."""
from __future__ import annotations

import csv
import html
import json
from pathlib import Path


def write_csvs(tables: dict[str, list[dict]], out_dir: Path) -> list[Path]:
    """One flat CSV per table. Power BI imports the folder directly."""
    out_dir.mkdir(parents=True, exist_ok=True)
    written = []
    for name, rows in tables.items():
        path = out_dir / f"{name}.csv"
        if not rows:
            path.write_text("")
            written.append(path)
            continue
        with path.open("w", newline="") as fh:
            writer = csv.DictWriter(fh, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)
        written.append(path)
    return written


def _table(rows: list[dict], empty: str) -> str:
    if not rows:
        return f'<p class="empty">{html.escape(empty)}</p>'
    head = "".join(f"<th>{html.escape(c.replace('_', ' '))}</th>" for c in rows[0])
    body = "".join(
        "<tr>" + "".join(
            f'<td class="{_cls(v)}">{html.escape(str(v))}</td>' for v in r.values()
        ) + "</tr>" for r in rows
    )
    return f"<table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table>"


def _cls(value) -> str:
    text = str(value)
    if text in ("COVERED - PASSING",):
        return "good"
    if text in ("NOT COVERED", "COVERED - FAILING"):
        return "bad"
    return ""


def write_html(context: dict, out_path: Path) -> Path:
    runs = context["runs"]
    trend = [r["pass_rate_pct"] for r in runs]
    labels = [r["run_id"] for r in runs]
    latest = runs[-1] if runs else {"pass_rate_pct": 0, "total": 0, "failed": 0}

    cards = [
        ("Pass rate (latest run)", f'{latest["pass_rate_pct"]}%'),
        ("Tests executed", str(latest["total"])),
        ("Failing now", str(latest["failed"])),
        ("Flaky tests", str(len(context["flaky"]))),
        ("Requirement coverage", f'{context["coverage_pct"]}%'),
    ]
    card_html = "".join(
        f'<div class="card"><div class="k">{html.escape(v)}</div>'
        f'<div class="l">{html.escape(k)}</div></div>' for k, v in cards)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(_TEMPLATE
        .replace("__CARDS__", card_html)
        .replace("__TREND__", json.dumps(trend))
        .replace("__LABELS__", json.dumps(labels))
        .replace("__SUITES__", _table(context["suites"], "no suites"))
        .replace("__FLAKY__", _table(context["flaky"], "No flaky tests detected."))
        .replace("__FIXED__", _table(context["fixed"], "No regressions in this window."))
        .replace("__FAILING__", _table(context["failing"], "Nothing failing consistently."))
        .replace("__SLOW__", _table(context["slowest"], "no timing data"))
        .replace("__TRACE__", _table(context["traceability"], "no requirements"))
    )
    return out_path


_TEMPLATE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>QA Automation Metrics</title>
<style>
:root{--bg:#f7f8fa;--fg:#14161a;--mut:#5b6472;--line:#e1e5ea;--card:#fff;--good:#17703f;--bad:#b4231f;--accent:#1f4fd8}
*{box-sizing:border-box}
body{margin:0;padding:24px 16px;background:var(--bg);color:var(--fg);
 font:15px/1.5 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif}
.wrap{max-width:1120px;margin:0 auto}
h1{font-size:22px;margin:0 0 4px}
.sub{color:var(--mut);margin:0 0 20px;font-size:14px}
h2{font-size:15px;text-transform:uppercase;letter-spacing:.06em;color:var(--mut);
 margin:28px 0 10px;border-bottom:1px solid var(--line);padding-bottom:6px}
.cards{display:grid;gap:12px;grid-template-columns:repeat(auto-fit,minmax(170px,1fr))}
.card{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:14px 16px}
.k{font-size:26px;font-weight:650;letter-spacing:-.02em}
.l{color:var(--mut);font-size:13px;margin-top:2px}
table{width:100%;border-collapse:collapse;background:var(--card);
 border:1px solid var(--line);border-radius:10px;overflow:hidden;font-size:13.5px}
th,td{text-align:left;padding:8px 12px;border-bottom:1px solid var(--line);vertical-align:top}
th{background:#eef1f5;font-weight:600;font-size:12px;text-transform:uppercase;letter-spacing:.04em;color:var(--mut)}
tr:last-child td{border-bottom:none}
td.good{color:var(--good);font-weight:600}
td.bad{color:var(--bad);font-weight:600}
.empty{color:var(--mut);font-style:italic;margin:4px 0 0}
svg{background:var(--card);border:1px solid var(--line);border-radius:10px;width:100%;height:190px}
@media(prefers-color-scheme:dark){:root:not([data-theme=light]){
 --bg:#101216;--fg:#e9ecf1;--mut:#9aa4b2;--line:#262b33;--card:#171a20;--good:#5ed69a;--bad:#ff8077;--accent:#7aa2ff}
 th{background:#1d2129}}
</style></head><body><div class="wrap">
<h1>QA Automation Metrics</h1>
<p class="sub">Generated from JUnit XML produced by the CI test runs. No manual data entry.</p>
<div class="cards">__CARDS__</div>
<h2>Pass rate trend</h2>
<svg id="trend" viewBox="0 0 720 190" preserveAspectRatio="none" role="img"
     aria-label="Pass rate per run"></svg>
<h2>By suite</h2>__SUITES__
<h2>Flaky tests</h2>__FLAKY__
<h2>Regressions (broke at a known build)</h2>__FIXED__
<h2>Failing in every run</h2>__FAILING__
<h2>Slowest tests</h2>__SLOW__
<h2>Requirement traceability</h2>__TRACE__
</div>
<script>
const data=__TREND__,labels=__LABELS__;
const svg=document.getElementById("trend"),W=720,H=190,P=30;
if(data.length){
 const min=Math.min(80,Math.min(...data)-2),max=100;
 const x=i=>P+(W-2*P)*(data.length===1?0.5:i/(data.length-1));
 const y=v=>H-P-(H-2*P)*((v-min)/(max-min||1));
 let g="";
 for(const v of [min,(min+max)/2,max]){
  g+=`<line x1="${P}" y1="${y(v)}" x2="${W-P}" y2="${y(v)}" stroke="currentColor" stroke-opacity=".14"/>`;
  g+=`<text x="4" y="${y(v)+4}" font-size="11" fill="currentColor" fill-opacity=".55">${v.toFixed(0)}%</text>`;
 }
 const pts=data.map((v,i)=>`${x(i)},${y(v)}`).join(" ");
 g+=`<polyline points="${pts}" fill="none" stroke="var(--accent)" stroke-width="2.5"
      stroke-linejoin="round" stroke-linecap="round"/>`;
 data.forEach((v,i)=>{
  g+=`<circle cx="${x(i)}" cy="${y(v)}" r="3.5" fill="var(--accent)"><title>${labels[i]}: ${v}%</title></circle>`;
 });
 svg.innerHTML=g;
}
</script></body></html>
"""
