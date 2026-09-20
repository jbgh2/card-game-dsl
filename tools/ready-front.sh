#!/usr/bin/env bash
# tools/ready-front.sh — the Ready Front sweep.
#
# The third sibling of the two CLAUDE.md tracker sweeps: derived,
# superset-style — an open issue is Ready unless a disqualifier holds.
# docs/harness.md ("The Ready Front") owns the definition; a change to
# what Ready means is a change to that file first (its Merge Lane table,
# "tools/ harness scripts — semantics").
#
# stdout: one takeable row per line — number, reachability, priority tier
#         ("-" where no tier applies), title — in the front's own order.
#         First the ACTIVE rows: each open milestone is an Active Epic
#         (docs/harness.md, "The Ready Front"), and its epic issue is the
#         one row that stands for it — reachability column "M", tier column
#         the milestone's closed/total issues, title the milestone's then the
#         epic's — the nearest due date first, an undated milestone last.
#         Every other issue in an open milestone is held off the front:
#         the epic is taken as a unit, and its children are that unit's
#         parts. Then the Ready rows: tier (P1, P2, none), then
#         reachability, then number. A blocker inherits the tier of every
#         open issue it blocks, transitively, so a tiered issue's
#         unblocking work ranks where the issue does. The tier and the
#         milestones are the direction review's decisions; nothing here
#         reads #143. An open milestone with no epic issue in it aborts:
#         a unit with no row to take it by is a milestone nobody can work.
# stderr: every open issue accounted for, as counted exclusion buckets.
#         The sweep never truncates silently: a capped fetch is a loud
#         failure, never a shorter list, and a failed Lease or label
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
            milestone { number title state dueOn done: issues(states: [CLOSED]) { totalCount } all: issues { totalCount } }
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

result=$(jq -s \
  --argjson leased "$leased_json" \
  --argjson ordering "$ORDERING_ISSUE" '
  def labelnames: [.labels.nodes[].name];
  def kinds: ["bug", "enhancement", "documentation", "tech-debt"];
  # Tier order: P1 before P2 before none. Any other priority: spelling is
  # a label outside the vocabulary and aborts rather than sorting somewhere.
  def own_tier:
    ([labelnames[] | select(startswith("priority:"))]
     | if length > 1 then error("issue #\(.number) carries two priority labels") else .[0] // "" end)
    | if . == "priority:P1" then 1 elif . == "priority:P2" then 2 elif . == "" then 3
      else error("unknown priority label \(.)") end;
  # A blocker inherits the best tier of what it blocks; relaxed to a fixed
  # point, so a chain of blockers carries the tier the whole way down.
  def inherit_tiers:
    . as $rows
    | (map({key: (.number | tostring), value: .tier}) | from_entries) as $init
    | reduce range(0; length) as $_ ($init;
        . as $t
        | reduce ($rows[] | select(.blockers | length > 0)) as $r ($t;
            reduce $r.blockers[] as $b (.;
              (.[$b | tostring] // 3) as $cur
              | ($t[$r.number | tostring] // 3) as $from
              | if $from < $cur then .[$b | tostring] = $from else . end)));
  def in_open_milestone: (.milestone != null) and (.milestone.state == "OPEN");
  # One bucket per issue, first match wins, in docs/harness.md list order.
  # The epic of an open milestone is ACTIVE unless a hand is on it; the
  # rest of the milestone is held, whatever else it carries.
  def bucket:
    .number as $n
    | if $n == $ordering then "ordering issue (not work)"
    elif in_open_milestone and (labelnames | index("epic")) then
      (if .assignees.totalCount > 0 then "claimed (assigned)"
       elif $leased | index($n) then "leased"
       else "ACTIVE" end)
    elif in_open_milestone then "held by an open milestone"
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
    # Every open milestone must be stood for by exactly one epic issue.
    (map(select(in_open_milestone)) | group_by(.milestone.number)
     | map({m: .[0].milestone, epics: [.[] | select(labelnames | index("epic")) | .number]})
     | map(select((.epics | length) != 1))
     | if length > 0
       then error("open milestone(s) without exactly one epic issue: \(map("\(.m.title) (epics: \(.epics))") | join("; "))")
       else empty end),
  (map({number, title, bucket: bucket,
        reach: (([labelnames[] | select(startswith("reachability:"))][0] // "")
                | sub("^reachability:"; "")),
        tier: own_tier,
        milestone: (if in_open_milestone then .milestone else null end),
        progress: (if in_open_milestone then "\(.milestone.done.totalCount)/\(.milestone.all.totalCount)" else "" end),
        blockers: [.blockedBy.nodes[] | select(.state == "OPEN") | .number]})
   | (inherit_tiers) as $tiers
   | map(.tier = $tiers[.number | tostring])
   | {stats: (group_by(.bucket) | map({bucket: .[0].bucket, n: length})),
      active: ([.[] | select(.bucket == "ACTIVE")]
               | sort_by([(.milestone.dueOn // "9999"), .milestone.number])),
      ready: ([.[] | select(.bucket == "READY")]
              | sort_by([.tier, .reach, .number]))})
  ' <<<"$issues_json")

{
  echo "open issues by bucket:"
  jq -r '.stats[] | "  \(.n)\t\(.bucket)"' <<<"$result"
} >&2

jq -r '(.active[] | [.number, "M", .progress, "\(.milestone.title) -- \(.title)"] | @tsv),
       (.ready[] | [.number, .reach, (if .tier == 1 then "P1" elif .tier == 2 then "P2" else "-" end), .title] | @tsv)' <<<"$result"
