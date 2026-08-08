#!/usr/bin/env bash
# tools/unresolved-threads.sh — unresolved review threads across open PRs.
#
# docs/harness.md ("Review threads") owns the rule; the platform enforces
# it at the merge button — this surfaces the forgotten before anyone gets
# there. Read-only; loud on any capped fetch.
set -euo pipefail

gh api graphql --paginate -f query='
  query($endCursor: String) {
    repository(owner: "jbgh2", name: "card-game-dsl") {
      pullRequests(states: OPEN, first: 50, after: $endCursor) {
        pageInfo { hasNextPage endCursor }
        nodes {
          number
          title
          reviewThreads(first: 100) { totalCount nodes { isResolved } }
        }
      }
    }
  }' | jq -s -r '
  [.[].data.repository.pullRequests.nodes[]]
  | (map(select(.reviewThreads.totalCount > 100))
     | if length > 0
       then error("capped: PR(s) \([.[].number]) carry more than 100 threads")
       else empty end),
  (map({number, title,
        unresolved: ([.reviewThreads.nodes[] | select(.isResolved | not)] | length)})
   | map(select(.unresolved > 0))
   | if length == 0
     then "clean: no open PR carries an unresolved thread"
     else .[] | "#\(.number)\tunresolved=\(.unresolved)\t\(.title)" end)'
