#!/usr/bin/env bash
# ============================================================================
#  The full simulation: a working suite, a change that breaks it, the tools
#  catching it, and the fix.
#
#  Called by run.sh --story. Not meant to be run on its own.
# ============================================================================
RUNS="$ROOT/2-quality-dashboard/sample-runs"
PAGE="$ROOT/1-test-automation/pages/inventory_page.py"
BACKUP="/tmp/inventory_page.backup.py"

# Whatever happens - a failed test, Ctrl-C, a crash - put the file back.
restore_page() {
  [ -f "$BACKUP" ] && cp "$BACKUP" "$PAGE" && rm -f "$BACKUP"
}
trap restore_page EXIT

run_suite() {   # $1 = build id, $2 = headline, $3 = optional timeout in ms
  step "$2"
  cd "$ROOT/1-test-automation"
  PW_TIMEOUT_MS="${3:-8000}" "$BPY" -m pytest $PWFLAGS -q \
    --junitxml="$RUNS/$1.xml" 2>&1 | tail -6 | sed 's/^/   /'
  cd "$ROOT"
}

banner "FULL SIMULATION  ---  break it, catch it, fix it"
cat <<'TXT'
   THE SCENARIO

     A website ships a redesign. Nobody tells the QA team. The HTML class
     names change, so the automation can no longer find the products on the
     page - and every test that touches the product grid starts failing.

     This is the single most common way a UI test suite breaks in real life.
     Watch what each tool does about it.
TXT

# ---------------------------------------------------------------- 1. green
run_suite "story-01" "STAGE 1 - the suite today. Everything passes."

# ----------------------------------------------------------------- 2. break
step "STAGE 2 - the site ships a redesign"
cp "$PAGE" "$BACKUP"
"$PY" - "$PAGE" <<'PY'
import sys
path = sys.argv[1]
source = open(path).read()
target = '    ITEM = ".inventory_item"'
if target not in source:
    sys.exit("could not find the product selector to break - page object changed shape")
open(path, "w").write(source.replace(target, '    ITEM = ".inventory-card"   # <-- the site renamed this class'))
PY
if [ $? -ne 0 ]; then warn "could not introduce the defect; aborting the story"; exit 1; fi
note "The product tiles are now called .inventory-card instead of .inventory_item."
note "Our page object still looks for the old name. One line changed:"
dim "  pages/inventory_page.py:  ITEM = \".inventory_item\"  ->  \".inventory-card\""

# ------------------------------------------------------------------- 3. red
# 2.5s, not the 30s Playwright defaults to. Nine elements that will never
# appear should be declared missing in seconds.
run_suite "story-02" "STAGE 3 - the very next run, with nobody told anything" 2500
note ""
note "The suite caught it on its own. Screenshots of each failure were saved:"
ls "$ROOT/1-test-automation/screenshots" 2>/dev/null | head -4 | sed 's/^/     /' || note "     (none captured)"

# --------------------------------------------------------- 4. what the tools say
step "STAGE 4 - the dashboard notices"
cd "$ROOT/2-quality-dashboard"
"$PY" cli.py --input sample-runs --out out --requirements requirements.txt | sed 's/^/   /'
"$PY" -c "
import csv
rows=list(csv.reader(open('out/csv/runs.csv')))[-4:]
hdr=list(csv.reader(open('out/csv/runs.csv')))[0]
rows=[hdr]+[r for r in rows if r!=hdr]
w=[max(len(r[i]) for r in rows)+2 for i in range(len(rows[0]))]
print()
for r in rows: print('   '+''.join(c.ljust(w[i]) for i,c in enumerate(r)))"
cd "$ROOT"

step "STAGE 5 - the triage tool says what kind of problem it is"
cd "$ROOT/3-ai-test-generator"
"$PY" cli.py --triage "$RUNS" --out out | sed 's/^/   /'
cd "$ROOT"
note ""
note "Read the category, not just the count. The failures are tagged"
note "Test code (selector) - the automation cannot find an element. The"
note "website is fine; our page object is looking for a name that no longer"
note "exists. That tag is the difference between filing a bug against the"
note "developers and fixing your own test."

# ------------------------------------------------------------------ 5. fix
step "STAGE 6 - a QA engineer fixes it"
restore_page
note "One line, in one file, put back:"
dim "  pages/inventory_page.py:  ITEM = \".inventory_item\""
note ""
note "That is the payoff of the page object pattern. The redesign broke every"
note "test that touches the product grid, across three different test files,"
note "and the fix touched ONE line in ONE file. Without page objects you would"
note "be hunting that selector through every test that uses it."

# ---------------------------------------------------------------- 6. green
run_suite "story-03" "STAGE 7 - green again"

step "STAGE 8 - the dashboard records the whole episode"
cd "$ROOT/2-quality-dashboard"
"$PY" cli.py --input sample-runs --out out --requirements requirements.txt >/dev/null
"$PY" -c "
import csv, os
f='out/csv/fixed.csv'
rows=list(csv.DictReader(open(f))) if os.path.getsize(f) else []
story=[r for r in rows if r['broke_at'].startswith('story')]
print(f\"   {len(story)} test(s) broke at story-02 and were green again at story-03.\")
for r in story[:4]:
    print('     ' + r['test'].split('::')[-1][:64])
if len(story) > 4: print(f'     ... and {len(story)-4} more')"
cd "$ROOT"
note ""
note "Broke at a known build. Fixed at a known build. Recorded without anyone"
note "writing a status update."
