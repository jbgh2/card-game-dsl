# Terminal play: a designer takes a seat against a chosen opponent

Operator go: Ben, 2026-09-06. Three rulings bind this plan and are not
reopened by any stage below.

1. **`play` means a person takes a seat**, against an opponent they choose.
   Today's uniform-random self-play keeps its behaviour under the name
   **`demo`**.
2. **One Seat Policy interface carries three tiers.** The first shipped
   opponent is rule-based — fast, competent enough to tell a designer whether
   their game works. The same interface then carries a trained MCCFR policy
   and an LLM seat *without being reopened*.
3. **The design gets a home inside the gates**: a design note for the
   mechanism, entries in `docs/decisions.md` for the settled rulings.
   `experiments/game-to-artifact-plan.md` keeps the artifact and lab
   material.

Epic [#613](https://github.com/jbgh2/card-game-dsl/issues/613); stages below
map to #620, #614, #615, #616, #617 and #553. The Architect's early counsel is on
the epic and its findings are folded into the obligations here; each
implementing change attaches its own counsel, produced fresh.

The design source is `experiments/game-to-artifact-plan.md`, P0 and "The
generic terminal view". It is experiment-grade and outside both CI gates, so
it is a source, never a citation: what binds moves into the design note and
`decisions.md` at Stage 2. Two of its passages are stale against the tree and
are corrected in the same pass — the claim that the command line stops at
static checking, and its `Pause` (renamed `DecisionNode` by #212).

## Acceptance criteria

1. **Runs** — `uv run cardlang play <file>` from a fresh checkout reaches an
   interactive hand *with pyspiel absent*; the core install stays lark-only. A
   designer plays a hand of a corpus game against a policy that is not a
   uniform draw.
2. **Regression-clean** — bare `mypy`; CI's three checks; byte-identical
   `information_state` output across the Stage 0 extraction, swept at the
   goldens' **full width** (`CARDLANG_GOLDEN_SEEDS=full`), not the sampling
   dial's; no other golden moves.
3. **Info sets derive** — nothing hidden moves and no observation is added.
   The frame is a second rendering of the derivation the OpenSpiel string
   already renders, through the same projections and the same observation
   log. The load-bearing pin is the per-visible-fact soundness matrix run
   against the frame renderer, both directions per fact.

**Corpus lockstep: no game file changes.** No stage touches `docs/games/**`,
so operating rule 2 imposes nothing here. Any stage that finds itself editing
a game file has misdiagnosed a harness problem as a game problem (CLAUDE.md,
"The game does not bend to the harness").

**Witnesses.** Stage 2's witness is the flag PR #608 opens — the frame has a
consumer before the session exists, which is what makes it separable rather
than invented. Stage 5's witness is Tichu, the one corpus game a uniform draw
cannot play through (measured 2026-09-03 on `origin/main`, recorded on #553).

## Gate record (cardlang-planning)

**Gate 1 — owners.**

- *Settled*: `decisions.md` has no section owning the command line, a
  rendering, or a seat policy. The nearest owner is decisions.md,
  "Knowledge, visibility, and the projection model", and its "OpenSpiel
  compilation" subsection; the new entries sit with it. decisions.md, "Closed-domain completeness", governs the vacuity finding below.
- *Named*: the glossary blocks two spellings. `Seat` is a player position, so
  the policy interface cannot take that name; `Playout Policy` is
  definitionally a `Chooser` over `Candidate`s, so it cannot name a policy
  that answers at a Decision Node. `action` is reserved and its
  OpenSpiel-action-id sense is marked Interop-only. Three terms are minted:
  **Seat View**, **Seat Policy** (the sibling entry to Playout Policy, the
  two cross-referencing so the level difference is the distinguishing
  clause), **Opponent Spec**.
- *Open*: open-questions/structural-infoset-proofs.md owns the proof
  machinery Stage 2 reuses, and its documented generator gaps transfer to
  anything built on it.
- *Sketched*: design-notes/llm-player-seats.md — a seat is a chooser and
  one derived interface serves solver, LLM and human alike.
- *Surface*: **no Merge Lane A change.** No stage touches the grammar; the
  `presentation` block stays deferred, so no Hoyle counsel is owed.
- *Engine-structural*: Architect counsel taken at planning time, on #613.

**Gate 2 — classification.** CLI surface and its command registry (#614,
#616); a new rendering layer with two closed-domain dispatches, zone
projections and the observation-event vocabulary (#615); a new registry
(#617); a policy registry changing level, plus a raw-access exemption row
(#553); documentation (all stages). **Every stage is audit-triggering.**

**Gate 3.5 — reachability and proportionality.** Every stage is R2: a
designer meets it on the first game they write. The effort is proportionate
to an operator mandate on the tool's primary loop. One cell is not R2 and is
recorded rather than built — see Stage 4.

**Gate 4 — the grids.** Each stage runs the audit's Step 1 before its own
implementation, and this plan fixes only the *derivation source* of each axis
so that no stage invents its domain:

| Stage | Axis | Derived from |
|---|---|---|
| #614 | commands | `COMMANDS` (`cardlang/cli.py`) |
| #614, #616 | flags per command | the argparse parser, as the surface grid already reads it |
| #615 | zone projections | `ZONE_PROJECTIONS` (`cardlang/stdlib/zones.py`) |
| #615 | observation events | the closed observation-event vocabulary |
| #615 | state value shapes | `infostate._render`'s declared shapes |
| #617 | opponent kinds | the Opponent Spec registry itself |
| #553 | Candidate kinds | `CANDIDATE_RANKERS` |

**Gate 5** — every step below names the artifact that proves it.

**A note on this file's own citations.** Section citations here name their file
WITHOUT backticks. That is deliberate and temporary: `test_doc_references.py`
reads a citation only when nothing sits between the filename and the
connective, so the repo's ordinary backticked style silently exempts one
(issue #619, with #569 the same class in its wrapped form). Restore the house
style once that lands; until then, backticks here would un-check these
pointers.

## The stages

### Stage 0 — #620, extract the derivation (behaviour-neutral)

**This is the stage that needs the operator's word before it starts** (see
"What the operator must decide"). One derivation, two renderings: a Seat View
bundle that `information_state` renders as the OpenSpiel string and the frame
renders as text. The renderer's parameter becomes the bundle, so "the raw
world never reaches the renderer" is a type rather than a claim a reviewer
checks.

- *Proves it*: byte-identical `information_state` on a full-width golden
  sweep, and no other golden moving. The change carries no new behaviour, so
  a moved byte is the whole failure surface.
- *Consumers to keep whole*: `openspiel/game.py::information_state_string`,
  `cli.py`, and `tests/openspiel_ready/partition.py::_default_info`.

**The bundle has three consumers, not two.** The OpenSpiel string and the frame
RENDER it; every Seat Policy also READS it, because a policy handed the raw
decision node could condition on a hand its seat cannot see (Stage 4). That
makes this stage the epic's linchpin rather than a tidiness pass, and it sets
the bundle's sufficiency bar: it carries what a competent policy needs — the
deciding seat's own cards, the declared ranking, the trump — or Stage 5 cannot
be written against it.

### Stage 1 — #614, `play` becomes `demo`

Independent of every other stage and takeable now. Lands after PR #608, which
holds the same three files.

- *Proves it*: the command axis re-derives from `COMMANDS`, so the surface
  grid follows the rename by construction. Misuse probe: the retired spelling
  is refused loudly and names the new one, rather than falling through to the
  implicit `check` path that reads a bare first argument as a file.
- *Prose sweep*: `README.md`, `docs/authoring.md`, the module docstring, and
  `experiments/game-to-artifact-plan.md`'s command table. Editing them runs
  the prose-scraper set and `test_doc_snippets`.

### Stage 2 — #615, the Seat View and the plain renderer

Ships behind the flag PR #608 opens, before any session exists.

- *Proves it, load-bearing*: `partition.check_visible_facts(rs, log, observer,
  info_fn=<frame renderer>)`. The matrix runs one perturbation per fact
  enumerated from the declarations and asserts both directions per fact —
  content shows through `identity`, and does not show through `count_only` or
  `trivial`. Its `ZONE_PROBES` table already refuses an unprobed projection.
- *Red-first obligation*: the adoption is not believed until a planted
  over-hiding renderer — one that drops a zone the seat is entitled to see —
  has been shown to redden the matrix.
- *Proves it, secondary*: two worlds indistinguishable to a seat render
  identical frames, on the existing partition machinery. Kept because it is
  cheap and covers the leak direction; **not** load-bearing, because a
  renderer that displayed nothing at all would pass it, and because the open
  question's generator gaps transfer to it verbatim.
- *Also in this stage*: the event formatter, exhaustive against the closed
  observation-event vocabulary with the static pin and runtime refusal that
  pattern carries; the pause metadata (phase name, hand number) the frame
  header needs, which `DecisionNode` does not carry today.
- *Docs land here*: `docs/design-notes/terminal-play.md`, the `decisions.md`
  entries, and the three glossary terms with their per-term files and index
  rows.

### Stage 3 — #616, the session

**The Seat Policy TYPE lands here, not in Stage 4.** The human is one
implementation of it, so the session cannot be written without it; only the
Opponent Spec grammar and its registry wait. A session that filled seats with a
hard-coded uniform draw would invent a second seat-filling shape and Stage 4
would rewrite it — which is how the two diverge.

**The honest intermediate state, stated so nobody reads Stage 3 as the end.**
Between this stage and Stage 5 the only registered policy is `random`. `play` is
therefore not yet complete against ruling 1 — a designer takes a seat, but the
opponent they can choose is one. That is incremental delivery, not a
contradiction: the epic's acceptance criterion is a hand played against a policy
that is NOT a uniform draw, and only Stage 5 satisfies it. The command says so
at the table rather than implying a choice it cannot offer.

- *Proves it*: `uv run cardlang play <corpus game>` reaches an interactive
  hand with pyspiel absent. Grid over the flag surface and the session's key
  vocabulary; misuse probes for a seat the game does not seat, a pick outside
  the menu, and a resume against a different game file.
- *Measure before building*: the legal-set-size histogram over the corpus,
  read before any paginated menu exists. Climbing games can offer legal sets
  a numbered menu cannot carry, and the mitigation is sized from the measured
  maxima rather than guessed (the plan's risk 10).
- *Free from the replay core*: undo is history truncation.
- *NOT free, and the probe above depends on it*: a saved session is a seed and
  a list of integers, which carry no trace of the game they were played in.
  Resumed against a different file whose early action ids happen to be legal,
  `replay.run` — which takes the path separately — replays them without
  complaint, so the misuse probe cannot tell that case from a valid resume.
  The session file carries a stable game identity, validated before replay.
  See "One identity rule, two artifacts" below.

### Stage 4 — #617, the Seat Policy interface and the Opponent Spec registry

A second seam above `Chooser`, with `ReplayChooser` as the adapter that already
exists and already owns the multi-pick decomposition. `Chooser` is not lifted:
the interpreter needs candidate values, and the action space is a compile-time
artifact it does not own.

**The policy's input is the Seat View, never the raw node.** A `DecisionNode`
carries the live world and EVERY seat's observation log, so a policy typed on it
could condition its choice on a hand the deciding seat cannot see — its strategy
would not be constant within an information set, and the shared interface would
guarantee nothing. That is the same defect #281 records at the rules level, and
it is the same argument that keeps the world away from the renderer: leak-freeness
is a type, not a discipline. So a Seat Policy is
`(Seat View, legal action ids) -> action id`, and converting the node is the
session adapter's job.

One declared exception: a perfect-information reference opponent is a legitimate
measuring instrument (PIMC benchmarks against one). It is a separately typed
thing that says so in its name, never the default interface widened to admit it.

- *Proves it*: the grid derives from the registry itself; per-seat assignment
  crosses seat validity. Misuse probe: an unknown kind is a loud error
  listing the registry, never a fallback to `random`.
- *Recorded, not built*: the stale-generated-file refusal (a brain whose
  embedded source hash does not match the game it is loaded against) has no
  witness until generated files exist. It is a marked cell naming its reason
  with a tracker issue, not a guard against nothing.
- *Named debt, not solved here*: `replay.run` re-simulates the whole history
  at every decision. Invisible at human speed; it is the throughput problem
  tracked as #139 and #158, and the design note says so rather than leaving a
  reader to discover it in an arena.

### Stage 5 — #553, the rule-based Seat Policy

The policy graduates from `tests/` and changes level in the same work: a
`Chooser` over Candidate values becomes a Seat Policy over a Decision Node.
Doing it in two steps would ship a policy no other tier can join.

- *Proves it*: Tichu plays through to a terminal position — the measured
  witness that a uniform draw cannot reach.
- *Placement*: an `_EXEMPT_RAW_ACCESS` row stating the rationale, not a
  directory chosen to sit outside the scrape's glob. The wall's domain is the
  coupling between a game file's declared names and Python that spells them;
  this policy iterates the zone-type map and filters by `ZONE_PROJECTIONS`,
  so every name it touches comes from the kernel's closed registry and no
  game author can rename any of them — the same rationale the existing
  engine-core exemptions carry.
- *Correction in the same change*: the policy's own docstring asserts it
  reads name-keyed state, which is what sent it to `tests/`. The claim is
  imprecise and currently load-bearing for a placement decision.

## One identity rule, two artifacts

Two files in this epic get replayed against a game they claim to belong to and
carry no proof of it: the saved session (Stage 3) and the generated opponent
file (Stage 4). Both fail the same way — silently, against a game whose early
action ids happen to line up — and both are refusals rather than fallbacks. They
take one rule and one implementation: a stable game identity written at save
time and validated before use, refusing loudly on mismatch. Specifying it twice
is how the two drift apart.

## What the operator must decide

Stage 0 refactors the artifact that carries the project's central evidence.
`information_state` is consumed by the adapter, by the command line, and by
the proof harness's own default; the goldens pinning it are the evidence that
information sets derive correctly. The question is whether the extraction
lands as **its own behaviour-neutral change, before either renderer is
written** — which is what makes the byte-identity claim checkable in
isolation — or inside Stage 2, where a moved byte would arrive mixed with new
behaviour.

The alternative to extracting at all is two independent derivations of a
seat's knowledge, kept equal by review. That is the shape the counsel
recommends against, and it is the operator's to overrule.
