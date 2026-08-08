#!/usr/bin/env bash
# tools/merge-gate.sh — the agent merge gate. Run before ANY agent merge;
# exit 0 is the only permission an agent has to press the button.
#
# docs/harness.md owns every clause's semantics: the merge gate (CI green,
# "Verifying changes" in CLAUDE.md), the Review threads rule (zero
# unresolved), and the Merge Lanes (mechanical lane C or D, computed by
# tools/lane-of.sh over the PR's files — hand-classifying around the tool
# is not a lane verdict). Prints its evidence; fails loudly on anything
# it cannot verify — a gate that cannot fail is not a gate.
#
# Usage: merge-gate.sh <pr-number>
set -euo pipefail

REPO=jbgh2/card-game-dsl
N=${1:?usage: merge-gate.sh <pr-number>}
fail=0

base=$(gh pr view "$N" --repo "$REPO" --json baseRefName --jq .baseRefName)
if [ "$base" = "main" ]; then echo "base: main -- ok"; else echo "base: $base -- FAIL (agent merges target main only)"; fail=1; fi

# Required checks come from branch protection — the platform's own
# registry, never a hand list. A required check must CONCLUDE SUCCESS:
# SKIPPED is how ci.yml treats fork PRs and drafts, so skipped-as-green
# would let a gate PASS having run nothing. Non-required checks (the
# weekly canary) must merely not fail.
required_json=$(gh api "repos/$REPO/branches/main/protection" --jq '[.required_status_checks.contexts[]]')
if [ "$(echo "$required_json" | jq length)" -lt 1 ]; then
  echo "required checks: none readable from branch protection -- FAIL (the gate must be able to fail)"; fail=1
else
  echo "required checks (from branch protection): $(echo "$required_json" | jq -r 'join(", ")')"
fi
checks=$(gh pr view "$N" --repo "$REPO" --json statusCheckRollup --jq '
  .statusCheckRollup
  | if length == 0 then error("no checks reported — the gate must be able to fail") else . end' \
  | jq --argjson req "$required_json" '
  map(
    (if .__typename == "CheckRun"
     then {name, done: (.status == "COMPLETED"), verdict: (.conclusion // "PENDING")}
     else {name: .context, done: true, verdict: .state} end)
    | . + {required: ((.name as $n | $req | index($n)) != null)}
    | . + {ok: (.done and (if .required then .verdict == "SUCCESS"
                           else (.verdict == "SUCCESS" or .verdict == "NEUTRAL" or .verdict == "SKIPPED") end))})')
echo "$checks" | jq -r '.[] | "check: \(.name)\(if .required then " [required]" else "" end) -- \(.verdict) -- \(if .ok then "ok" else "FAIL" end)"'
echo "$checks" | jq -e 'all(.ok)' >/dev/null || fail=1
missing=$(jq -n --argjson req "$required_json" --argjson have "$(echo "$checks" | jq '[.[].name]')" '($req - $have) | length')
if [ "$missing" -ne 0 ]; then echo "gate: $missing required check(s) absent from the rollup -- FAIL"; fail=1; fi

threads=$(gh api graphql -f query="{ repository(owner: \"jbgh2\", name: \"card-game-dsl\") {
    pullRequest(number: $N) { reviewThreads(first: 100) { totalCount nodes { isResolved } } } } }" \
  --jq '.data.repository.pullRequest.reviewThreads
        | if .totalCount > 100 then error("capped: \(.totalCount) threads") else . end
        | [.nodes[] | select(.isResolved | not)] | length')
if [ "$threads" -eq 0 ]; then echo "unresolved threads: 0 -- ok"; else echo "unresolved threads: $threads -- FAIL"; fail=1; fi

# Capture before iterating — a mid-pagination failure must kill the gate,
# not classify the fetched prefix. A renamed file contributes BOTH paths:
# the destination alone would launder a stricter-lane file into a softer
# lane.
files_raw=$(gh api --paginate "repos/$REPO/pulls/$N/files" --jq '.[] | .filename, (.previous_filename // empty)')
files=()
while IFS= read -r f; do [ -n "$f" ] && files+=("$f"); done <<<"$files_raw"
if [ "${#files[@]}" -ge 3000 ]; then echo "files: ${#files[@]} path entries hit the API listing cap -- FAIL (cannot classify a capped diff)"; fail=1; fi
lane_out=$("$(dirname "$0")/lane-of.sh" "${files[@]}")
echo "$lane_out" | sed 's/^/lane-of: /'
mergeable=$(echo "$lane_out" | awk -F': ' '/^agent-mergeable:/ { print $2 }')
[ "$mergeable" = "yes" ] || fail=1

if [ "$fail" -eq 0 ]; then
  echo "merge-gate: PASS — an agent may merge PR #$N"
else
  echo "merge-gate: FAIL — PR #$N is the operator's button"
  exit 1
fi
