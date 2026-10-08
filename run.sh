#!/usr/bin/env bash
# ============================================================================
#  TestPilot - the only script you need.
#
#    ./run.sh              ask what kind of run you want
#    ./run.sh --demo       visible browser, slowed down   (~2.5 min)
#    ./run.sh --fast       hidden browser, full speed     (~15 sec)
#    ./run.sh --story      break it, catch it, fix it     (~1 min)
#    ./run.sh --reset      clear all generated output and start clean
#    ./run.sh 2            just project 2
#    ./run.sh 1 --fast     just project 1, full speed
#    ./run.sh --no-open    do not open the result files at the end
#
#  Press Ctrl-C once at any point to SKIP the current step and move on.
#  Press it twice quickly to quit.
# ============================================================================
set -uo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"

B=$'\033[1m'; G=$'\033[32m'; Y=$'\033[33m'; D=$'\033[2m'; N=$'\033[0m'
banner() { printf '\n%s%s\n  %s\n%s%s\n' "$B" "$(printf '=%.0s' {1..78})" "$1" "$(printf '=%.0s' {1..78})" "$N"; }
step()   { printf '\n%s>> %s%s\n' "$B" "$1" "$N"; }
note()   { printf '   %s\n' "$1"; }
dim()    { printf '   %s%s%s\n' "$D" "$1" "$N"; }
warn()   { printf '   %s%s%s\n' "$Y" "$1" "$N"; }

# ------------------------------------------------- Ctrl-C skips, not quits
SKIPPED=0
on_int() {
  SKIPPED=$((SKIPPED + 1))
  printf '\n   %s-- skipped --%s\n' "$Y" "$N"
  LAST_INT=$(date +%s)
}
trap on_int INT

# ---------------------------------------------------------- arguments
WHICH="all"; MODE=""; OPEN=1
for arg in "$@"; do
  case "$arg" in
    1|2|3)      WHICH="$arg" ;;
    --demo)     MODE="demo" ;;
    --fast)     MODE="fast" ;;
    --story)    MODE="fast"; WHICH="story" ;;
    --reset)    WHICH="reset" ;;
    --no-open)  OPEN=0 ;;
    -h|--help)  sed -n '2,16p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *)          echo "unknown option: $arg"; exit 1 ;;
  esac
done

# ------------------------------------------------------- pick the mode
if [ -z "$MODE" ]; then
  printf '\n%sHow do you want to run this?%s\n\n' "$B" "$N"
  printf '   %s1%s  Demo   - browser visible, slowed to 700ms per action   (~2.5 min)\n' "$B" "$N"
  printf '          Use this when someone is watching.\n\n'
  printf '   %s2%s  Test   - browser hidden, full speed                    (~15 sec)\n' "$B" "$N"
  printf '          Use this to just check everything still passes.\n\n'
  printf '   %s3%s  Story  - break something real, watch the tools catch it,\n' "$B" "$N"
  printf '          then fix it and watch them record the recovery   (~1 min)\n'
  printf '          %sUse this one in an interview.%s\n\n' "$B" "$N"
  printf 'Choice [1/2/3, default 1]: '
  read -r choice
  case "${choice:-1}" in
    2) MODE="fast" ;;
    3) MODE="fast"; WHICH="story" ;;
    *) MODE="demo" ;;
  esac
fi

if [ "$MODE" = "fast" ]; then
  PWFLAGS=""; MODE_LABEL="TEST RUN (hidden browser, full speed)"
else
  PWFLAGS="--headed --slow-mo 700"; MODE_LABEL="DEMO (visible browser, slowed down)"
fi

PY="$(command -v python3)"
BPY="$ROOT/.venv/bin/python3"

# ------------------------------------------------------------- setup
if ! "$BPY" -c "import playwright" >/dev/null 2>&1; then
  banner "SETUP (first run only)"
  note "macOS refuses system-wide pip installs, so this uses a local .venv."
  [ -d "$ROOT/.venv" ] || python3 -m venv .venv
  "$ROOT/.venv/bin/pip" install --quiet --upgrade pip
  "$ROOT/.venv/bin/pip" install --quiet playwright pytest
  "$ROOT/.venv/bin/playwright" install chromium
fi

# Stale .pyc files survive their source being deleted and produce import errors
# pointing at code that no longer exists. Cheap to prevent.
find "$ROOT" -name '__pycache__' -type d -not -path "$ROOT/.venv/*" -exec rm -rf {} + 2>/dev/null

printf '\n%sMode:%s %s\n' "$B" "$N" "$MODE_LABEL"
dim "Ctrl-C once skips the current step and moves on."

# ============================================================ PROJECT 1
project1() {
banner "PROJECT 1 of 3  ---  UI TEST AUTOMATION"
cat <<'TXT'
   WHAT IT IS
     Automated tests that drive a real Chrome browser through a real website
     (saucedemo.com): log in, add a product to the cart, check out.

   WHY IT MATTERS
     A human doing this by hand takes ~15 seconds per run and gets bored.
     This does it on every code change, forever, without skipping a step.

   HOW IT IS BUILT
     pages/   one class per screen. A test never contains a CSS selector.
              When the site changes you edit one file, not twenty tests.
     tests/   16 tests across login, cart and checkout.
TXT
step "Running the tests"
[ -n "$PWFLAGS" ] && { note "A Chrome window is about to open. Do not touch it."; sleep 2; }
cd "$ROOT/1-test-automation"
"$BPY" -m pytest $PWFLAGS -q \
  --junitxml="$ROOT/2-quality-dashboard/sample-runs/build-007.xml" 2>&1 | tail -6
cd "$ROOT"
note ""
note "Each test just gave a verdict. That verdict is now a file:"
dim "  2-quality-dashboard/sample-runs/build-007.xml"
note "That file is the handoff to projects 2 and 3."
}

# ============================================================ PROJECT 2
project2() {
banner "PROJECT 2 of 3  ---  QUALITY & METRICS DASHBOARD"
cat <<'TXT'
   WHAT IT IS
     Project 1 only knows about right now. This reads EVERY past run together
     and answers the questions a QA lead asks on Monday morning.

   WHY IT MATTERS
     Test results land as XML files nobody opens. This turns them into a
     pass-rate trend, a flaky-test list, and a list of requirements that have
     no test behind them.

   HOW IT IS BUILT
     Standard library only. Read XML -> flatten to rows -> compute -> render
     an HTML page plus CSVs that Power BI imports directly.
TXT
step "Reading every build"
cd "$ROOT/2-quality-dashboard"
"$PY" cli.py --input sample-runs --out out --requirements requirements.txt | sed 's/^/   /'
step "Pass rate over time"
"$PY" -c "
import csv
rows=list(csv.reader(open('out/csv/runs.csv')))
w=[max(len(r[i]) for r in rows)+2 for i in range(len(rows[0]))]
for r in rows: print('   '+''.join(c.ljust(w[i]) for i,c in enumerate(r)))"
step "Regressions it found (broke at a known build, fixed at a known build)"
"$PY" -c "
import csv,os
f='out/csv/fixed.csv'
rows=list(csv.reader(open(f))) if os.path.getsize(f) else []
if not rows: print('   none')
else:
    w=[max(len(r[i]) for r in rows)+2 for i in range(len(rows[0]))]
    for r in rows: print('   '+''.join(c.ljust(w[i]) for i,c in enumerate(r)))"
step "Requirements with no test behind them"
"$PY" -c "
import csv
rows=[r for r in csv.DictReader(open('out/csv/traceability.csv')) if r['state']=='NOT COVERED']
if not rows: print('   none')
for r in rows: print('   '+r['requirement']+'   NOT COVERED')"
cd "$ROOT"
}

# ============================================================ PROJECT 3
project3() {
banner "PROJECT 3 of 3  ---  AI TEST GENERATOR"
cat <<'TXT'
   WHAT IT IS
     Give it a requirements document. It writes EXECUTABLE tests and runs them.

   WHY IT MATTERS
     An AI that writes test cases as prose is worth nothing - somebody still
     has to turn them into code. This produces real Playwright tests that
     import, run, and pass or fail for a real reason.

   HOW IT IS BUILT
     Generation is constrained: the model picks an action from a fixed
     vocabulary that maps onto project 1's page objects, rather than writing
     free-form Python. Code that does not compile is worse than no test.
     With no API key, keyword rules drive the same vocabulary - so it works
     offline and in CI.
TXT
step "The input: a plain requirements document"
sed -n '3,12p' "$ROOT/3-ai-test-generator/requirements.md" | sed 's/^/   /'
step "Generating tests from it, then running them"
cd "$ROOT/3-ai-test-generator"
if [ -n "$PWFLAGS" ]; then
  "$BPY" cli.py --out out --headed --slow-mo 700
else
  "$BPY" cli.py --out out
fi
step "What it wrote (this is real code, not a description of code)"
sed -n '/^@pytest.mark/,/^$/p' out/test_generated.py | head -14 | sed 's/^/   /'
step "Grouping failures into real problems"
"$PY" cli.py --triage "$ROOT/2-quality-dashboard/sample-runs" --out out | sed 's/^/   /'
cd "$ROOT"
}

if [ "$WHICH" = "reset" ]; then
  banner "RESET"
  rm -rf "$ROOT/2-quality-dashboard/out" "$ROOT/3-ai-test-generator/out" \
         "$ROOT/1-test-automation/screenshots" "$ROOT/report.html"
  find "$ROOT/2-quality-dashboard/sample-runs" -name 'build-0[7-9]*.xml' -delete 2>/dev/null
  find "$ROOT/2-quality-dashboard/sample-runs" -name 'story-*.xml' -delete 2>/dev/null
  find "$ROOT" -name '__pycache__' -type d -not -path "$ROOT/.venv/*" -exec rm -rf {} + 2>/dev/null
  note "Cleared all generated output. The six stored builds are untouched, so"
  note "projects 2 and 3 still have history to read."
  note ""
  note "Run ./run.sh again for a clean demo."
  exit 0
fi

case "$WHICH" in
  1)     project1 ;;
  2)     project2 ;;
  3)     project3 ;;
  story) . "$ROOT/story.sh" ;;
  *)     project1; project2; project3 ;;
esac

# ------------------------------------------------------- show the results
banner "DONE"
if [ "$WHICH" = "all" ] || [ "$WHICH" = "story" ]; then
cat <<'TXT'
   HOW THEY CONNECT

     Project 1  runs the tests     ->  writes build-NNN.xml
     Project 2  reads those files  ->  charts them, finds regressions
     Project 3  writes the tests   ->  and groups the failures

     The link is one file format: JUnit XML. Every test tool emits it, which
     is why projects 2 and 3 work with any test suite, not only this one.
TXT
fi
[ "$SKIPPED" -gt 0 ] && warn "$SKIPPED step(s) were skipped with Ctrl-C."

step "Building the report"
REPORT="$("$PY" "$ROOT/make_report.py" "$MODE_LABEL")"
note "Everything that just happened, on one page:"
dim "  $REPORT"

if [ "$OPEN" -eq 1 ] && command -v open >/dev/null 2>&1; then
  open "$REPORT"
  dim "(./run.sh --no-open skips this)"
fi
