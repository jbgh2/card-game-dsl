# Grammar pass, Step 1: the grammar is minimal and complete (#835)

Epic #818, the second unit. The brief is `docs/design-notes/grammar-pass-2026-10-07.md`,
section 5, row 1, read against the operator's rulings of 2026-09-07 and 2026-10-10.

## Acceptance criteria

1. Runs: every corpus game checks and plays; Hearts' one `transfer` line reads `move`.
2. Regression-clean: bare `mypy`, the full suite, the rigs; Hearts' per-seed goldens
   byte-identical at full width; no IR golden moves (the verb is sugar over one node).
3. Info sets derive: no decision site or projection changes; the per-observer streams
   are untouched.

Corpus lockstep: `docs/games/hearts.cardlang` (one line) and its twin if it names the
verb (it does not). Witness: the corpus itself — no file writes `burn`, `muck` or
`transfer`; Hearts is the one writer of `transfer`.

## Classification

Grammar surface (a terminal narrows: Merge Lane A); tests/goldens (the retired-surface
pin, the dead-surface pin); tooling (`tools/dead_surface.py` classifies its rows);
docs (decisions.md "Surface totality", library.md, model.md, the glossary entry for
Transfer, the direction-review skill's dead-surface check). No parse builder, AST,
resolve, typecheck, IR or runtime arm changes: the verb is a token value the engine
never branches on.

## The ruling this unit executes

The language is **minimal but complete**: it avoids synonyms, and it carries no
logical inconsistency — no register with a missing sibling. Applied to the
dead-surface report's rows on main (579d8ba9):

| row | class | fate |
|---|---|---|
| `burn`, `muck`, `transfer` (TRANSFER_VERB alternatives) | synonym of `move` | cut |
| `sq_all`; `agg_subset_sum`, `agg_subset_order`; `q_all_suit`, `q_all_rank`, `q_any_domain`, `q_count_domain`; `divided_by_rounded_down`; `sel_random`; `rule_remove`, `rule_override` and the keywords `suits`, `ranks`, `down`, `random`, `override` | register member with a live sibling | kept, under the sunset |
| `vis_clause` / `visibility` | refused placeholder with a pinned message | Step 2 (the message moves with the post-parse layer) |
| `card_values`, `always` | reject arm with a pinned message | Step 2 |

The sunset: a register member still written by no corpus file ten corpus games after
the direction review first lists it is retired by that review, and the family's
symmetry re-read with it. Ten is the brief's own tell ("a keyword still has one user
after ten more games"); the operator may set another number.

## Reachability

R4: no corpus game writes a cut verb, and a designer who does meets a syntax error
naming the tokens expected. The guarantee protected is the Destination's ("a new game
adds no grammar"): surface with no writer is where the next accepted-but-ignored
sentence lands.

## The totality edge (audit step 1, run here)

- The retired-surface pin (`tests/test_orphaned_surface_retired.py`) gains one sentence
  per cut verb, authored red: each is refused at parse. One terminal carries all three,
  so one refusal mechanism covers the three cells; the ledger says so.
- The dead-surface report classifies every dead row by derivation — **reject** (only a
  `_reject` twin uses the keyword), **placeholder** (a rejection fixture is its only
  consumer), **register** (a live alternative of the same rule), **dead** (none) — and
  `tests/test_dead_surface_report.py` pins the dead class empty on the real tree, with a
  planted orphan proving the pin can fail. No hand list: the classes are read from the
  compiled grammar and the consumer tiers.
- Misuse probes: `burn 1 card from deck to muck`, `muck one card from hand[0] to muck`,
  `transfer chosen 3 cards from hand[p] to hand[q]` — each a located syntax error.

## Hoyle's counsel

### Headnote

The grammar loses three spellings and gains nothing. `burn`, `muck` and `transfer` are
synonyms of `move`: the parser hands the engine the same node whichever word a designer
writes, and no file but Hearts writes any of them, once. The recommended sentence is
Hearts' own line rewritten, `move chosen 3 cards from hand[player] to hand[player
offset_by pass_direction]`; the losing rival is the sentence we have, `transfer chosen 3
cards ...`, kept only by habit. The
library form is the recommended sentence itself: no definition is needed because nothing
enters, so the proof is one line and the Merge Lane is A only because a terminal
narrows. One game moves in lockstep; no settled commitment is cut against — the
2026-09-07 register-symmetry ruling is honoured, not reversed: the fourteen register
members the brief would also cut stay, with a sunset of ten corpus games the direction
review applies. Information sets do not move. The cost: the dead-surface report keeps
listing the register rows, now with their class and reason beside them, and a designer
who writes `burn` meets a syntax error rather than "write `move`" until Step 2's
diagnostic layer lands. What the operator decides: the sunset's number — ten is the
brief's tell, not a measurement.

### 1. The sentences

Hearts, as it stands and as it will read:

```
transfer chosen 3 cards from hand[player] to hand[player offset_by pass_direction]
move chosen 3 cards from hand[player] to hand[player offset_by pass_direction]
```

Alternatives weighed: keep `transfer` as the resource verb only (`transfer 5 chips`) —
rejected, since resource transfers are deferred surface and the item noun already says
`chips`; keep `burn`/`muck` with an implied destination — rejected, the grammar
requires a destination on every form and the implied one was prose that never parsed.
No adjacency hazard: a verb is the statement's first token, and `TRANSFER_VERB` keeps
its whole-word anchoring.

### 2. Precedent

decisions.md "The operation vocabulary" (one primitive, verbs that "differ only in
defaults, not in kind" — and they do not differ at all); "Surface totality" (every
accepted composition has an accounted outcome); the glossary's Transfer entry (the
engine word is Transfer, the surface verb `move`); the 2026-09-07 ruling on register
symmetry and the operator's 2026-10-10 restatement, minimal and complete.

### 3. Corpus impact

One game, one line (Hearts). The witness is the corpus's silence: thirty-four files,
three verbs, one writer.

### 4. The totality edge

Nothing newly accepted. Newly refused: the three sentences above, pinned. The register
rows stay accepted and implemented, each with an executing test today.

### 5. The info-set bound

No observation changes: the Transfer node, its projection and its per-observer event
are the same object under every verb.

### 6. Counsel

For: a synonym is the purest dead surface — same node, same event, a second word to
learn. Against: `burn` reads better than `move ... to burn` at a poker table, and the
diagnostic for a designer who writes it is a bare syntax error until Step 2. Hoyle would
cut the three now, keep the registers whole under the sunset, and let Step 2 give the
retired words their "write `move`" message.

## Task list

1. Red first: the three retired sentences; the dead-surface classes and the empty-dead
   pin with its planted orphan.
2. `TRANSFER_VERB` loses the three words; Hearts rewrites; the parser comment that
   lists the verbs follows.
3. `tools/dead_surface.py` classifies; the report renders the class and reason.
4. Docs: decisions.md "Surface totality" states the rule and the sunset; "The operation
   vocabulary", library.md, model.md and the Transfer entry list three verbs; the
   direction-review skill's check 6 applies the sunset.
5. Gate: bare `mypy`; `pytest -q -n 8`; the rigs; Hearts' goldens at full width;
   `tools/lane-of.sh`; the PR with this counsel, Headnote first.
