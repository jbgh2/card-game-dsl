# The completeness ledger: churn and context poisoning

Exploratory. Not settled spec. Convened on issue #389 with the standing
doctrine set aside. The tracker home for the ledger ruling is **issue #392**.

## The Headnote

The specs are not the problem. Over one shared window the documents that
describe the language are rewritten *less* than the code they describe, and
the churn sits almost entirely in the process rulebook, which describes no
code and so cannot be fixed by any consistency mechanism.

The ledger's problem is narrower than "prose drifts", and it has two faces.
The `covered:` and `sampled:` rows restate what the tests below them already
run, so they change on roughly half the commits that touch their module, and
every change is a diff line a reviewer must adjudicate — the reviewer is
right every time, which is why the finding cannot be argued down and why one
module drew seven of them across four rounds. That is the churn face. The
poisoning face is worse and quieter: `covered:` asserts that something is
tested, which licenses the next reader not to test it. A stale one leaves a
gap open and says it is closed. Measured against `main`, two such rows were
found by agents who were not looking for them, in one afternoon.

The decision is to delete both rows rather than generate them. Deleting is
not merely cheaper: a generated row would be accurate but would keep the
slot, and the slot is what invites the prose. Six agents implementing the
same issue under the two formats bear this out — the four rows that remain
carried every caution the six rows did, and the arm without `covered:`
wrote 9 lines of restatement per module against 63.

What this is NOT bought on: there is no evidence the change improves the
judgment content of a ledger. Both formats produced the same cautions. The
case is surface area — fewer claims, and specifically fewer of the kind that
license inaction — not better ledgers. That is a reasonable bet, not a
measured reduction in defects, and it should be argued as a bet.

## 1. The decision

Delete `covered:` and `sampled:`. Rename `residual:` to `does not prove:` and
route everything that is not an instrument limit to one of five other
destinations.

Taken on the operator's rationale: **less prose is less room for the
problem.** Section 4 tests that rationale rather than assuming it.

## 2. Churn — measured

All rows share one window: every commit since 2026-07-20 (572 commits).
Rewrite ratio is lines deleted per line added — how much existing text is
rewritten rather than appended.

| region | rewrite |
|---|---|
| research + design-notes + open-questions | 0.15 |
| corpus (`docs/games/`) | 0.23 |
| settled specs (decisions, model, principles, library, glossary) | **0.30** |
| CLAUDE.md | 0.32 |
| `cardlang/` — the baseline | **0.47** |
| `tests/` | 0.58 |
| **process/meta** (harness, maintaining, building, implementation, roadmap, kernel-migration) | **1.59** |

Every documentation category that describes the language is more stable than
the engine. An unpartitioned figure for `docs/` is 0.68 and is an artifact of
mixing these categories — dominated by the corpus, which `maintaining.md`
rule 2 *requires* to change in lockstep.

**Ledger churn specifically:** 87 modules carry one; 76 of 87 were rewritten
after creation; ledger prose changed on 49% of the 757 follow-up commits.

## 3. Poisoning — the sharper frame

Rank prose not by how likely it is to be wrong but by **what being wrong
licenses you not to do.** An issue gets tested, because implementing it means
checking its claims. A docstring gets believed, because reading it is not
checking it.

| claim shape | licenses | failure mode |
|---|---|---|
| `covered:` "this is tested" | not writing a test | gap stays open, silently |
| "guarded at X" / "checked upstream" | not adding a guard | no guard, plus a comment saying there is one |
| "cannot happen / guaranteed by" | not handling a case | unhandled case |
| `residual:` "this is NOT tested" | going to look | benign — self-correcting |

This inverts the naive reading. `covered:` is not merely wasteful; it is the
dangerous row. `residual:` is close to harmless — its worst case is wasted
effort.

**The surface is far wider than ledgers.** Prose in `cardlang/` and `tests/`
asserting something is already handled elsewhere: 313 shadow-guard comments
naming an owner, 112 swept/class-closed, 107 guaranteed/cannot-happen, 97
checked-upstream, 15 already-checked — 644 in all. The largest category is
one CLAUDE.md *mandates*. Nothing verifies that a named Owner Guard still
exists or still covers the case its shadow claims.

**And 92% of docstring lines here are claim-bearing, not descriptive.** A
"no narrative comments" rule — the standard cure for AI comment rot — would
touch about 7% of this surface. This repo does not have a narration problem;
it has an assertion problem. (The matcher is permissive, so 7% is a lower
bound on descriptive; the direction is robust.)

**The scale of the false fraction is unmeasured, and that is itself the
finding.** Two attempts to count stale referents both over-reported — one
counted a Python builtin, a DSL type name and an env var as unresolved.
Separating "stale" from "correctly names a non-Python thing" is the whole
difficulty, and it is what `tests/test_ledger_referents.py` (PR #394) spends
1,272 lines on. The way to size it is to **sample**: draw ~30 stratified
across the five shapes, establish what fraction are genuine inaction licenses
and what fraction are false *by execution*, and treat the confirmed-false
ones as the defects they are.

## 4. Does "less prose, less room" hold?

Tested with six agents implementing issue #113 — three under each format,
identical prompts but for the doctrine block, isolated worktrees, nobody told
it was an experiment. Metrics fixed in writing beforehand.

Ledger lines each agent **authored**:

| arm | mirror (`covered`/`sampled`) | judgment | frame | total |
|---|---|---|---|---|
| A — six rows | **63.3** (49-77) | 69.7 | 46.3 | 179 |
| B — four rows | **8.7** (7-10) | 52.0 | 68.3 | 129 |

**Supports the rationale.** The reduction lands exactly on the dangerous
rows: mirror prose falls ~86%, ranges non-overlapping. Total ledger size
falls 28%. Frame rows *rise*, because boundary statements moved into
`domain:` stated positively instead of sitting in `residual:` as though
something were missing. Fewer claims, and the ones deleted are the
inaction-licensing kind.

**Does not support a stronger claim.** Both arms wrote the instrument-limit
cautions — arm A put them in `sampled:`/`residual:` ("the audited-top set is
a COUNT per module, not an enumeration"; "that argument is not pinned here";
"Record: OWED"). The format changed where the caution goes, not whether it is
written. And whether the format reduces *unbacked* claims was never measured;
all three arms self-corrected claims mid-run via the existing framing check,
which may be doing that work in both arms regardless of format.

**Why delete rather than generate.** A generated `covered:` would be accurate
and could not poison, which on paper dominates deletion. Three things decide
against it: the generator is machinery that must itself be maintained and can
go quietly wrong (one agent hit exactly this — a guard-derived axis *loses* a
cell instead of reddening when a source is dropped, and had to state the
domain a second time by hand); the slot survives generation, and the slot is
what invites hand-written prose back; and the experiment shows ledgers are
good without it. Deletion has no moving parts.

## 5. The taxonomy

Classifying all 88 residual rows by what the reader must *do*. Three of the
six kinds are not residuals at all — they are other things mis-filed into a
catch-all slot, which is what a catch-all noun does.

| # | kind | belongs | still a row? |
|---|---|---|---|
| 1 | **Deferred work** | tracker: `issue #N` + one line | no |
| 2 | **Uncovered cell** | `skip`/`xfail` in the grid, with reason | no |
| 3 | **Domain boundary** — nothing missing | `domain:`, stated positively | no |
| 4 | **Designed constraint** — never to be fixed | the spec, or a comment at the construct | no |
| 5 | **Instrument limit** — what a green does *not* prove | `does not prove:` | **yes, the only one** |
| 6 | **Empty** | nothing | no |

The resulting format:

```text
property:        <the guarantee, one line>
domain:          <what is quantified over, and what is deliberately
                  outside it — the boundary stated positively>
registry:        <where each axis is derived in code>
does not prove:  <what a green here does NOT establish, and why>
```

The slot name does the sorting. A row called `does not prove:` cannot hold
deferred work or a domain boundary; mis-filing stops at the point of writing
rather than at review.

## 6. The change list

**Format definition** — two files, must move together:
- `docs/decisions.md` "Closed-domain completeness": the template block, and
  the "gate is symmetric" paragraph, which names two rows that no longer exist.
- `.claude/skills/surface-totality-audit/SKILL.md` Step 3: the same two edits.
- Both additionally gain the six-kind routing table.

**Downstream references that go stale:** `CLAUDE.md` (the completeness-ledger
mandate; "residual" in the closed-domain paragraph), roadmap.md, "Where the
work is tracked" (the issue-citing rule and the not-work carve-out),
`.github/pull_request_template.md` (Artifacts), and four skills — `cardlang-planning`, `cardlang-pr-description`,
`cardlang-code-review`, `cardlang-direction-review`.

**The 87 modules:** delete `covered:`/`sampled:`, route each `residual:` item
to one of six destinations, rename the remainder. The routing is judgment, not
mechanism — this wants staging, not one PR.

**PR #394** should be kept and *widened*, not closed. Its doctrine paragraphs
about `covered:` are stillborn under this ruling, but its referent-resolution
scrape generalizes to any safety claim naming a symbol — which is a problem an
order of magnitude larger than the ledger.

## 7. What is explicitly not claimed

- That this reduces defects. Surface area is the argument; M4 was never
  measured, and that was the pre-registered condition for closing #392 as
  "format is not the cause". It remains open.
- That ledgers get better. Both formats produced the same cautions.
- That the 644 safety claims elsewhere are mostly false. Nobody knows; the
  sample in section 3 is how to find out.
