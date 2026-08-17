Run a round of the Dispatcher Standing Role for the card-game DSL repo.

You are headless in the fleet clone (the working directory), already
hard-synced to origin/main by the wrapper (tools/fleet/run-role.sh) — do
not pull. The permission charter (.claude/settings.json) governs every
command: a denied command is charter feedback — record it in the report
and work the rest of the round; never improvise around a denial — a
"denied command by another route" is a charter violation even when the
route is itself allowed. Rules match literal text, so spell every
command as the charter admits it, one liturgy per call: `gh api`
method-first (`gh api -X GET|POST|PATCH|DELETE repos/...`); `git`
verb-first from inside the directory it acts on — `cd` into the
worktree in its own call, then bare `git diff` / `git log`; never
`git -C <path>`; never a compound preflight (`a; b; c`) — a compound
is refused whole if any part is unlisted. Issue and PR bodies go
through `--body-file <path>` written first with the Write tool: an
inline body containing a newline followed by `#` is refused, which
would ban every `##` heading. Rebase is not available to a fleet round
(force-push is denied by design): a Lease branch behind main takes a
merge of `origin/main`, never a rebase. The
operator is not watching: proceed through the whole round without
waiting for input; park anything that needs a human and continue.

GUARD: if .claude/skills/role-dispatcher/SKILL.md does not exist here,
report exactly that and stop; do not improvise a charter.

Then invoke the role-dispatcher skill and execute its round exactly as
chartered:

- Preflight: ./tools/ready-front.sh; free slots = WIP cap 2 minus open
  claude/issue-* PRs and live Leases. A parked Lease with pushed work (a
  linkage comment on the issue says so) is the round's FIRST pick —
  finish parked work before taking new.
- Select from the top of the front (#143 rank, then reachability, then
  age), skipping Merge Lane A work, spend-requiring items, and blocked
  issues; honor #143 clusters as one item (Lease the primary, comment
  the linkage on siblings). Prefer disjoint subsystems across
  simultaneous slots.
- Per item: Lease via the create-only ref API (422 = taken, next) →
  body-sufficiency check (bounce loudly on failure: comment +
  needs-triage + release own ref) → cardlang-planning gates (a Gate 3.5
  stop-shape = park: comment the question, release the Lease, next) →
  implement on the Lease branch in a worktree INSIDE this clone: the
  Lease ref was born on the server after the wrapper's sync, so fetch
  first, then create the local branch from the remote ref —
  `git fetch -q origin && git worktree add -B claude/issue-N
  .claude/worktrees/issue-N origin/claude/issue-N` (`-B` also absorbs a
  leftover local branch from an earlier round; the path is already
  gitignored, and headless file access does not extend outside this
  clone) → push early → run locally what the change can
  affect, evidence that can fail (no piped exit codes): from the
  worktree root use `./tools/verify.sh mypy` and
  `./tools/verify.sh pytest -q -n 8` — verify.sh binds PYTHONPATH to
  the current directory and the engine venv; never invoke bare
  python/pip → surface-totality-audit where its trigger matches →
  cardlang-code-review at the classification's tier →
  PR via cardlang-pr-description (Closes #N; when the item is listed in
  issue #143, the PR body's "For the reviewer" bullets name the trim per
  #143's contract — never edit #143 itself).
- Watch, then answer — linearized for a headless session (a background
  watcher would outlive you): after ALL of the round's PRs are open,
  take them one at a time, and for each FIRST query what already landed
  (`gh pr view <N> --json comments,reviews,statusCheckRollup` — a review
  that arrived while you worked elsewhere is invisible to a watcher
  started now, because pr-watch baselines at startup and reports only
  increases). Handle anything already present, and only then watch in
  the foreground (`./tools/pr-watch.sh <N> both`) for what hasn't.
  Handle each review round per the thread rule (disposition reply +
  resolve; a finding on the fix for a previous finding escalates to the
  operator — say so on the PR and stand down); after any fix push,
  query-then-watch again. The charter's arm-in-background language is
  for interactive sessions; every other step of its round binds here
  unchanged.
- Merge ONLY on ./tools/merge-gate.sh exit 0 (merge commit, delete the
  branch); otherwise post the gate's evidence block as a PR comment and
  leave the PR for the operator.
- Never: Lane A work, editing #143 or doctrine, spending money, working
  blocked issues, merging past the gate.
- Produce the full report: taken, produced (PR numbers), merged (with
  gate evidence), parked (with questions), bounced, skipped (with
  reasons), and every DENIED command — count everything.
- POST the report as a comment on epic #274 — the fleet's public record
  and the review desk's inbox. This is the primary channel (session
  messaging does not exist in unattended runs). A round whose report
  lands nowhere a reader will see did not finish its round.
