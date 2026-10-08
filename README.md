# TestPilot

**Break it on purpose, so it doesn't break on a customer.**

[![tests](https://github.com/AbhiramaMekala/testpilot/actions/workflows/tests.yml/badge.svg)](https://github.com/AbhiramaMekala/testpilot/actions/workflows/tests.yml)

A quality engineering toolkit in three parts: it runs browser tests, measures
what those runs tell you over time, and writes new tests from a requirements
document. Each part feeds the next.

```bash
./run.sh
```

First run installs Playwright into a local `.venv`. Nothing is installed
system-wide. Then it asks what kind of run you want:

| | Mode | What it does | Time |
|---|---|---|---|
| **1** | Demo | Browser visible, slowed to 700ms per action | ~2.5 min |
| **2** | Test | Browser hidden, full speed | ~15 sec |
| **3** | **Story** | **Breaks something real, catches it, fixes it** | ~90 sec |

Press **Ctrl-C once** at any point to skip the current step and move on.
At the end it builds `report.html` — everything that happened, on one page —
and opens it.

```bash
./run.sh --story     # the simulation, no prompt
./run.sh --fast      # just check everything passes
./run.sh 2           # one project on its own
./run.sh --reset     # clear all generated output
./run.sh --help
```

---

## The three projects

| | Project | What it does |
|---|---|---|
| **1** | `1-test-automation` | **Runs** the tests — drives a real browser through [saucedemo.com](https://www.saucedemo.com): login, cart, checkout. 16 tests. |
| **2** | `2-quality-dashboard` | **Reads** the results — pass-rate trend, flaky tests, regressions, requirements with no test. Standard library only. |
| **3** | `3-ai-test-generator` | **Writes** the tests — turns a requirements document into executable tests, runs them, and groups failures into real problems. |

**How they connect:** project 1 writes a JUnit XML results file; projects 2 and 3
read it. JUnit XML is the format every test tool emits, so projects 2 and 3 work
with any test suite, not only this one.

---

## 1 — UI Test Automation

Page Object Model: one class per screen in `pages/`, so a test never contains a
CSS selector. When the site changes you edit one file, not twenty tests. Each
test gets a fresh browser context — no cookies or cart carried over, which is
the main cause of flaky UI suites.

Two timeout budgets, because they are two different waits. Finding an element on
a loaded page gets 8 seconds, so a genuine failure fails fast. Fetching a page
over the internet gets 20, because that depends on someone else's server.
Playwright's 30-second default for both means nine failures cost four minutes of
waiting for things that were never going to appear.

## 2 — Quality & Metrics Dashboard

Reads every past build together and reports the pass-rate trend, the slowest
tests, requirements with no test behind them, and — separately — **flaky** versus
**broken**.

That distinction is the point. Failures in one unbroken block mean something
broke at a known build and was fixed at a known build, so there is a diff to look
at. Failures scattered across non-adjacent builds with no diff to blame are
genuinely flaky. The response to each is different, so counting them together is
how this metric turns into noise nobody reads.

Writes an HTML dashboard plus CSVs that Power BI imports directly.

## 3 — AI Test Generator

Give it a requirements document; it produces **executable** Playwright tests and
runs them.

Generation is constrained: the model picks an action from a fixed vocabulary that
maps onto project 1's page objects, rather than writing free-form Python. Code
that does not compile is worse than no test. With no API key, keyword rules drive
the same vocabulary, so it works offline and in CI — every record carries whether
a rule or the model produced it.

It also triages failures: strips the parts of each message that change run to
run, groups by what is left, and classifies the cause.

---

## The story mode

Worth running before anything else. A website ships a redesign, nobody tells the
QA team, the HTML class names change — the most common way a UI suite breaks in
real life.

1. The suite runs green.
2. One line changes: `ITEM = ".inventory_item"` → `".inventory-card"`.
3. The next run goes red on its own, with screenshots.
4. The dashboard shows the drop.
5. The triage tool tags it **`Test code (selector)`** — *not* a product defect.
   The website is fine; the automation is looking for a name that no longer
   exists. That tag is the difference between filing a bug against the developers
   and fixing your own test.
6. One line, one file, put back.
7. Green again.
8. The dashboard records it: broke at a known build, fixed at a known build.

The redesign broke every test touching the product grid, across three test files.
The fix touched one line in one file. That is the argument for the Page Object
Model, demonstrated rather than claimed.

The file is restored on exit no matter what — test failure, crash, or Ctrl-C.

---

## Bugs these found while being built

**Tests that assumed the network was instant.** The suite read each page
immediately after clicking. Against a local server that always worked; against
the real site it read pages before they had loaded and six of eleven tests
failed. Fixed with explicit waits on the element each test needs — not `sleep()`.

**Shared state that looked like flakiness.** A cart leaking between browser
sessions made tests pass alone and fail in a suite.

**A regression test that could not detect its own bug.** The rounding test used a
value where both rounding modes agree, so it passed either way — coverage that
tested nothing. Caught by re-introducing the bug and watching the test stay
green.

**A failure message that said `assert 0 > 0`.** Now it says which selector
matched nothing and what to check first. A failure should explain itself without
anyone opening the code.

---

## Requirements

Python 3.9+. Everything else is installed by `./run.sh` into a local `.venv`.
Projects 2 and 3 need no installation at all — standard library only.
