#!/usr/bin/env bash
# tools/ready-front.sh — the Ready Front sweep.
#
# The third sibling of the two CLAUDE.md tracker sweeps: derived,
# superset-style — an open issue is Ready unless a disqualifier holds.
# docs/harness.md ("The Ready Front") owns the definition; a change to
# what Ready means is a change to that file first (its Merge Lane table,
# "tools/ harness scripts — semantics").
#
# stdout: one Ready issue per line — number, reachability, #143 rank
#         ("-" where the ordering issue does not reference it), title.
# stderr: every open issue accounted for, as counted exclusion buckets.
#         The sweep never truncates silently: a capped fetch is a loud
#         failure, never a shorter list, and a failed Lease or rank
#         lookup aborts rather than degrading.
#
# Read-only. Needs gh (authenticated) and jq.
set -euo pipefail

OWNER=jbgh2
NAME=card-game-dsl
ORDERING_ISSUE=143   # a living document, not work; its body owns its contract

issues_json=$(gh api graphql --paginate \
  -F owner="$OWNER" -F name="$NAME" -f query='
    query($owner: String!, $name: String!, $endCursor: String) {
      repository(owner: $owner, name: $name) {
        issues(states: OPEN, first: 100, after: $endCursor) {
          pageInfo { hasNextPage endCursor }
          nodes {
            number
            title
            labels(first: 50) { totalCount nodes { name } }
            blockedBy(first: 50) { totalCount nodes { number state } }
            assignees(first: 10) { totalCount }
          }
        }
      }
    }')

# A Lease is exactly refs/heads/claude/issue-<N> (docs/harness.md, "Leases");
# the prefix query over-fetches, pages are aggregated before the exact-match
# filter narrows — the no-truncation property covers Leases too.
leased_json=$(gh api --paginate "repos/$OWNER/$NAME/git/matching-refs/heads/claude/issue-" \
  | jq -s 'add // []
           | [.[].ref | select(test("^refs/heads/claude/issue-[0-9]+$"))
              | sub("^refs/heads/claude/issue-"; "") | tonumber]')

# First-appearance rank of every #N the ordering issue's body references.
# Advisory annotation only — ordering authority stays with #143 itself.
ranks_json=$(gh issue view "$ORDERING_ISSUE" --repo "$OWNER/$NAME" --json body -q .body \
  | { grep -oE '#[0-9]+' || true; } | tr -d '#' | awk '!seen[$0]++' \
  | jq -Rn '[inputs] | to_entries | map({key: .value, value: (.key + 1)}) | from_entries')

result=$(jq -s \
  --argjson leased "$leased_json" \
  --argjson ranks "$ranks_json" \
  --argjson ordering "$ORDERING_ISSUE" '
  def labelnames: [.labels.nodes[].name];
  def kinds: ["bug", "enhancement", "documentation", "tech-debt"];
  # One bucket per issue, first match wins, in docs/harness.md list order.
  def bucket:
    .number as $n
    | if $n == $ordering then "ordering issue (not work)"
    elif labelnames | index("epic") then "epic (container)"
    elif (labelnames | index("needs-triage"))
         or (((labelnames - (labelnames - kinds)) | length) == 0)
      then "unclassified (no kind, or needs-triage)"
    elif ([labelnames[] | select(startswith("reachability:"))] | length) == 0
      then "unordered (no reachability label)"
    elif ([labelnames[] | select(startswith("blocked:"))] | length) > 0
      then "witness-gated (blocked: label)"
    elif ([.blockedBy.nodes[] | select(.state == "OPEN")] | length) > 0
      then "blocked (open dependency)"
    elif .assignees.totalCount > 0 then "claimed (assigned)"
    elif $leased | index($n) then "leased"
    else "READY" end;
  [.[].data.repository.issues.nodes[]]
  | (map(select(.labels.totalCount > 50 or .blockedBy.totalCount > 50))
     | if length > 0
       then error("capped fetch on issue(s) \([.[].number]) — a connection passed first: 50; raise it")
       else empty end),
  (map({number, title, bucket: bucket,
        reach: (([labelnames[] | select(startswith("reachability:"))][0] // "")
                | sub("^reachability:"; "")),
        rank: ($ranks[.number | tostring] // null)})
   | {stats: (group_by(.bucket) | map({bucket: .[0].bucket, n: length})),
      ready: ([.[] | select(.bucket == "READY")]
              | sort_by([(.rank // 999999), .reach, .number]))})
  ' <<<"$issues_json")

{
  echo "open issues by bucket:"
  jq -r '.stats[] | "  \(.n)\t\(.bucket)"' <<<"$result"
} >&2

jq -r '.ready[] | [.number, .reach, (.rank // "-"), .title] | @tsv' <<<"$result"
