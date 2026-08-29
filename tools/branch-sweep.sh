#!/usr/bin/env bash
# tools/branch-sweep.sh — the local branch-hygiene sweep.
#
# role-warden (.claude/skills/role-warden/SKILL.md, "Branch sweep") owns
# the semantics. This is the one Warden script that acts as it reports:
# every deletion is guarded mechanically, so a judgment call adds nothing
# a report line does not. Two proven classes are deleted — ancestor-merged
# branches, where `git branch -d`'s own refusal is the guard (unmerged or
# checked-out refs survive it), and `claude/`-namespace branches whose
# upstream is gone AND whose merge GitHub records as a merged PR (the
# squash case: ancestry never shows a squash merge, so the recorded PR is
# the proof). Everything else — never-pushed work, live upstreams, other
# namespaces' unmerged refs — is out of scope by construction and appears
# as a `remains` line. `git worktree prune` clears admin records of
# already-deleted directories; it never removes a directory. The sweep
# cleans only the checkout it runs in.
#
# Output: TSV — action (deleted/kept/remains/summary), ref, reason.
set -euo pipefail

REPO=jbgh2/card-game-dsl

git fetch --prune --quiet origin

deleted_merged=0
deleted_proven=0
kept=0

# Ancestor-merged refs: git's own -d is the guard.
merged=$(git for-each-ref refs/heads --format='%(refname:short)' --merged=origin/main)
while IFS= read -r b; do
  [ -n "$b" ] || continue
  [ "$b" = main ] && continue
  if out=$(git branch -d "$b" 2>&1); then
    printf 'deleted\t%s\tmerged into origin/main\n' "$b"
    deleted_merged=$((deleted_merged + 1))
  else
    printf 'kept\t%s\t%s\n' "$b" "$(printf '%s' "$out" | head -1)"
    kept=$((kept + 1))
  fi
done <<EOF
$merged
EOF

# claude/ refs whose upstream is gone: the merged-PR record is the proof.
gone=$(git for-each-ref 'refs/heads/claude/*' \
         --format='%(refname:short)	%(upstream:track)' \
       | awk -F'\t' '$2=="[gone]"{print $1}')
while IFS= read -r b; do
  [ -n "$b" ] || continue
  pr=$(gh pr list --repo "$REPO" --head "$b" --state merged \
         --json number --jq '.[0].number // empty')
  if [ -n "$pr" ]; then
    if out=$(git branch -D "$b" 2>&1); then
      printf 'deleted\t%s\tmerged as PR #%s (upstream gone)\n' "$b" "$pr"
      deleted_proven=$((deleted_proven + 1))
    else
      printf 'kept\t%s\t%s\n' "$b" "$(printf '%s' "$out" | head -1)"
      kept=$((kept + 1))
    fi
  else
    printf 'kept\t%s\tupstream gone, no merged PR recorded\n' "$b"
    kept=$((kept + 1))
  fi
done <<EOF
$gone
EOF

git worktree prune

git for-each-ref refs/heads \
  --format='remains	%(refname:short)	%(upstream:short)%(upstream:track)'

printf 'summary\tdeleted=%d (ancestor=%d, pr-proven=%d)\tkept=%d\n' \
  "$((deleted_merged + deleted_proven))" "$deleted_merged" \
  "$deleted_proven" "$kept"
