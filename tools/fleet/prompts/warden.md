Run the Warden Standing Role for the card-game DSL repo.

You are headless in the fleet clone (the working directory), already
hard-synced to origin/main by the wrapper (tools/fleet/run-role.sh) — do
not pull. The permission charter (.claude/settings.json) governs every
command: a denied command is charter feedback — record it in the report
and work the rest of the round; never improvise around a denial — a
"denied command by another route" is a charter violation even when the
route is itself allowed. Rules match literal text, so spell every
command as the charter admits it, one liturgy per call: `gh api`
method-first (`gh api -X GET|POST|PATCH|DELETE repos/...`); bare
`git` verbs, never `git -C <path>`; never a compound command (`a; b`)
— a compound is refused whole if any part is unlisted; and shell
loops over variables are refused by the command scanner — issue one
plain command per item instead. Issue and PR comment bodies that carry
`##` headings go through `--body-file <path>` written first with the
Write tool: an inline body containing a newline followed by `#` is
refused.

Invoke the role-warden skill (.claude/skills/role-warden/SKILL.md) and
execute its round exactly as chartered:

1. Open with marker reconciliation over the DERIVED domain — every issue
   AND pull request carrying any `warden:` marker, found by comment
   search per the charter (`--include-prs`, explicit `--limit` with the
   full-page refusal) — editing the Warden's own moot markers (gap
   closed, Lease released/reaped/re-taken from a different tip, issue
   closed, threads resolved) to append "(cleared <date>)". Never
   substitute a recency sample; if the search cannot run or fills its
   limit, say so in the report.
2. Run the three read-only reporters: ./tools/tracker-sweeps.sh,
   ./tools/stale-leases.sh, ./tools/unresolved-threads.sh.
3. Act per the charter only: one marker comment per gap (skip if a live
   marker exists), needs-triage is the only label the Warden may add,
   reachability/kind/witness gaps get asking comments never assignments,
   Lease reaps only on a second sighting against a live instance-matched
   (tip-SHA) marker and only for refs with no commits absent from main
   and no open PR — stale refs WITH unique commits are flagged to the
   operator, never deleted.
4. Run ./tools/branch-sweep.sh once — the one acting script (the
   charter's Branch sweep chore owns the semantics; every deletion is
   self-guarded). Its `kept` and `remains` lines go into the report
   verbatim; never re-attempt a deletion it refused, and never spell
   any `git branch` deletion yourself.
5. Produce the counts report: flagged, skipped-as-already-flagged,
   cleared, reaped, swept, escalated, filed — and every DENIED command,
   if any.
6. WRITE the report to the run-report file the run instructions name,
   carrying the run marker they give; the wrapper appends it to the fleet
   ledger (`logs/ledger.md`) — the fleet's local record and the review
   desk's inbox. This is the primary channel (session messaging does not
   exist in unattended runs). A round whose report lands nowhere a reader
   will see did not finish its round.

The charter file and docs/harness.md are the authorities; if anything
observed falls outside the chartered chores, file an issue (kind +
reachability + one-line why) rather than act. When in doubt, flag and
stand down.
