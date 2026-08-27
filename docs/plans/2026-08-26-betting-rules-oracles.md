# Betting-rules oracles for `poker_betting`

Four P1 findings landed in one construct across one review series, every
one of them in the same place: the arithmetic that decides whether a
wager is a raise. This plan closes the class in the library and in the
instruments that failed to see it.

## What the four findings share

The library records `bet_to_match` — where the bet stands — and nothing
that says which of those standings a wager actually reached in full. Every
finding is that missing distinction:

| # | Finding | The missing fact |
| --- | --- | --- |
| 1 | the threshold measured the completion distance, not a full bet | what a full bet is, here |
| 2 | the same yardstick error one grid over | as above |
| 3 | no completion offered above the last full wager | where the last full wager was |
| 4 | a wager that reaches a full wager neither counts nor reopens | as above |

Name the missing fact `level` — the highest wager any seat has made in
full on this street, zero until one does — and the four collapse into one.

### Three positions, not a number line

`level` turns the standing bet into a three-valued position, and every
finding is a transition into or out of the third:

| Position | Test | Reached by |
| --- | --- | --- |
| **Open** | `bet_to_match is 0` | a street opening |
| **Level** | `bet_to_match is level` | a full wager, or an all-in of half a bet or more |
| **Short** | `level < bet_to_match < level + limit` | a bring-in, or an all-in short of a full wager |

The clarifying consequence: **Stud's bring-in and a short all-in occupy the
same position.** One rule governs both, which is why completing a bring-in
and completing over a short shove are the same move, and why a library
that cannot name the position gets both wrong.

## Acceptance criteria

1. **Runs.** All five consumers play: `holdem`, `holdem-heads-up`,
   `kuhn-poker`, `leduc-poker`, `seven-card-stud`.
2. **Regression-clean.** Bare `mypy`; full `pytest`. Goldens move only
   where the rules require and are swept at **full width**
   (`CARDLANG_GOLDEN_SEEDS=full`, CLAUDE.md "Verifying changes") — the
   dial has now hidden a real movement in this construct three times.
3. **Info sets derive.** `level` is public betting information: every
   seat sees the bet level, so it must be observable to all and derived,
   never assumed. The `openspiel_ready` proofs carry it — their
   `facts[...state_vars=N]` census moves, and that movement is the
   evidence the new variable is projected rather than invisible.

**Corpus lockstep.** `level` is library-owned `state`, so no game declares
it. Stud writes `bet_to_match` and `raises` by hand for the bring-in and
must NOT write `level` — a bring-in is a wager short of a full bet, so
zero is already correct. Each game file's betting prose is checked against
the new rule in the same change (operating rule 2).

**Witness.** The position is already corpus-reachable and measured: Stud
seeds 30 and 37 move under the current change, and the bring-in sits in
**Short** at the top of every 3rd street. No fixture needed.

## Reachability and proportionality (Gate 3.5)

**R1 — corpus-reachable, measured.** Not "a designer could write this": the
corpus does it, on named seeds, in a construct five games import. Four
confirmed P1s in one series is the cost of the current instruments; the
suite below is smaller than the review rounds it replaces.

None of the four stop conditions fires: no doctrine edit, no all-R4
scaffolding, no settled decision reverted, and the justification is an
R1 defect rather than a gate.

## Classification (Gate 2)

Corpus library (`.cardlang`) plus tests and goldens. **Not** Merge Lane A —
no grammar or `.lark` surface changes, so no Language Owner counsel. The
change adds a closed-domain mechanism, so the **surface-totality audit
fires** and its Step 1 runs at planning time: the grid exists red before
the implementation.

---

## The Architect's counsel

### Headnote

Four review findings in one construct all came from the same missing fact,
and the tests missed all four for three separate reasons. The fact is the
last wager anyone made in full; adding it closes the code side.

The test side is where the decision is. Two of the three gaps are ordinary
engineering — cross the rule's positions rather than literal numbers, and
play sequences instead of single decisions. The third is not: every
expected value in this suite is read out of a rulebook by hand, and no
test can check a reading. The recommendation is to build the two ordinary
layers, plus a small layer that pins the rulebooks' OWN printed worked
examples, and to NOT build a second implementation of the rule in Python.
A second implementation would catch the kind of error where the rule was
understood and the arithmetic lost it — one of the four — while sharing
the author's reading, which is where the other three came from. It costs a
permanent second copy to catch the minority case.

What this makes newly required: every future rules question that turns out
to be a misreading ends by adding its worked example, so the one layer
that can catch a misreading grows exactly where we have been wrong.

Info-set verdict: does not move — `level` is public betting information,
derived through the same projection as the other betting variables, and
the readiness proofs carry it.

Precedent standing: established citation. The oracle taxonomy and the
warning that derived oracles inherit the blind spots of what they derive
from are the book's Area 5, not a lead.

Bottom line: build three layers, defer the fourth. The strongest reason
against is real and must be stated in the ledger rather than papered
over — three layers leave the expected column resting on one reading, so
the suite still cannot certify rulebook fidelity, and external review
stays load-bearing for it. The operator decides whether that residual
dependence is acceptable or whether the second implementation is worth
its permanent cost.

### 1. The decision

Not "what suite covers betting". The gaps divide unevenly:

- (a) grids drove literal values instead of the rule's positions, and
- (b) nothing played a sequence

are ordinary test engineering with obvious fixes. The decision at stake is
(c): **can the rulebook's arithmetic become a specified oracle, or must
every expected value stay derived from one reading?**

### 2. The law

- CLAUDE.md, load-bearing: "Execution finds what enumeration cannot" —
  when a choice exists between enforcement machinery and a witness, build
  the witness.
- `decisions.md`, "Closed-domain completeness": the grid IS the coverage
  record; an uncovered cell is a mark naming its reason. "Vacuously
  green" ranks with "accepted-but-ignored".
- **P11** — an oracle is trusted only after it has caught a planted fault,
  and it never calls the code it judges.
- **P10** — an oracle reaches only what its generator reaches.
- **P12** — a specified instance with a known value is the preferred first
  witness.

None of this is re-litigated below.

### 3. Precedent

The sourcebook's Area 5 (compiler testing) is squarely on point.

- **Barr, Harman, McMinn, Shahbaz, Yoo (TSE 2015)** supplies the taxonomy:
  *specified* oracles, *derived* oracles (differential, metamorphic), and
  *implicit* oracles — with the explicit warning that **derived oracles
  inherit the blind spots of what they derive from**. The caveat in the
  brief is not a hedge; it is this finding, and it decides the question.
- **McKeeman (1998)** and **Csmith (Yang et al., PLDI 2011)** establish
  differential testing and its precondition: a genuinely second
  interpretation.
- **YARPGen (Livinskii et al., OOPSLA 2020)**: uniform random generation
  under-reaches, and generators need aimed diversity. Observed here
  directly — uniform playouts reached these positions on 2 seeds of 50.
- **Csmith's triage warning**: a generator without a reduction story
  produces findings nobody can afford to read.
- Repo precedent: `tests/native_oracle.py` is the alternating
  perfect-information differential and does not reach poker; the
  `openspiel_ready` adapter agreement for Kuhn and Leduc IS an external
  differential, but both games have deep stacks and no all-ins, so it is
  **structurally blind to this entire class**. Worth stating plainly: an
  external oracle already exists here and could never have caught any of
  the four.

### 4. The options

**Option A — four layers as sketched** (worked examples, relation grid,
sequence enumerator, independent Python model of rules 3/5/6).

Cost: the model is a second implementation of the rule in a second
language, maintained in lockstep forever — the two-copies-drift failure
`maintaining.md` rule 4 names. Under P11 it must never call the library
and must catch a planted fault before it is trusted, both achievable.
Under Barr et al. its independence is *implementation*-deep only: it
shares the author's reading, so findings 1 and 3 (misreadings) survive it
intact. It would have caught finding 4 (understood rule, lost arithmetic).

**Option B — three layers, sequences enumerated exhaustively.**

Drops the model; keeps a bounded-exhaustive walk of the reachable state
space. Cost: the space is only finite for tiny stacks, and each state
expansion has to run the DSL — the existing offers grid costs about
0.16s per cell, so a low-millions state space is not payable. The
generator's reach would be provable, but the bound would have to be so
small that its reach stops being interesting.

**Option C — three layers, sequences as a TRANSITION grid.** *(recommended)*

The rule is a state machine over the three positions. Cross
**positions x action kinds** and assert the landing position plus the
bookkeeping, each cell a two- or three-action script through the real
library. Small, total over the domain that matters, and it is exactly
what finding 4 is: a missing transition out of **Short**. Add a cheap
randomized sequence fuzz carrying only *structural* invariants — chips
conserved, `bet_to_match` monotone within a street, `level <=
bet_to_match`, termination, `raises <= raise_cap` — which can afford to
be random precisely because its oracle is implicit rather than an
expected column.

### 5. What becomes illegal after

- `bet_to_match` may no longer be read as "the level a raise measures
  from". That is `level`; `bet_to_match` becomes "where the bet stands"
  and nothing more. Both `bet` and `raise` compute their target from
  `level`.
- A consumer game may not write `level` — it is library-owned `state`.
  Stud's hand-written bring-in bookkeeping stays legal precisely because a
  bring-in leaves `level` at zero.
- No test may assert a betting expectation from a literal standing bet
  without saying which position that literal occupies. The relation grid's
  axis derivation makes the position the axis, so a literal alone stops
  being expressible.

### 6. Counsel

**Strongest case for Option C.** It puts the instrument where the defects
are. All four findings are position-transitions, and a transition grid
over three positions is small enough to be total and cheap enough to run
every commit. It also fixes the deeper fault in the existing grids, which
is not that they were too small but that their axes were the wrong KIND —
literal values cannot be crossed against a rule stated in relations, and
no amount of adding values fixes that.

**Strongest case against.** Option C does not close gap (c), and should
not be described as if it does. Three of the four layers still read their
expected values out of Robert's Rules by hand; a misreading survives all
of them, and the two findings that were misreadings would survive again.
The suite will therefore reduce, not remove, the dependence on external
review. Anyone reading a green run as "the betting rules are correct" will
be wrong in exactly the way this construct has already been wrong twice.
That belongs in the ledger in those words.

**What the Architect would do.** Option C, with layer 1 built FIRST and
treated as the layer that grows. The rulebooks' printed worked examples
are *specified* oracles in Barr et al.'s sense — the same standing as a
solved game's known value under P12, and the only thing in this design
that can catch a misreading. There are few of them today, which is an
argument for accreting them, not for skipping them: adopt the rule that
every rules finding closes by adding its worked example, and the one
layer that covers gap (c) grows precisely where the project keeps being
wrong.

Defer Option A's model until the transition grid has run and been shown
insufficient. If it is ever built, the honest place is not this library
but OpenSpiel's `universal_poker` (ACPC), which is a genuine second
implementation by other authors — the only version of layer 4 that would
actually break the shared-reading problem. That is a larger piece of work
and should be its own issue, gated on a witness.

---

## Task list

Each step names the artifact that proves it. Steps 1-3 are authored RED
before step 4 exists (audit Step 1, run at planning time).

| # | Step | Proving artifact |
| --- | --- | --- |
| 1 | Worked examples from the rulebooks, quoted verbatim beside each case | `tests/test_poker_betting_rulebook.py` — each case red against today's library where the rules disagree with it |
| 2 | Relation grid: position x owing x acted x purse x cap x field, position DERIVED not literal | `tests/test_poker_betting_offers.py` — axes re-derived; the `Short`-above-`level` cells red |
| 3 | Transition grid: position x action kind, landing position + `raises` + `acted` clear | `tests/test_poker_betting_transitions.py` — the complete-out-of-`Short` cells red (finding 4) |
| 4 | Add `level` to library state; target `level + limit`; guard arm `bet_to_match > level`; counts iff `now >= level + limit` or `moved + moved >= limit` | steps 1-3 green |
| 5 | Structural-invariant fuzz over randomized sequences | `tests/test_poker_betting_invariants.py`, validated by a planted fault (P11) |
| 6 | Full-width golden sweep; regenerate what the rules move | `CARDLANG_GOLDEN_SEEDS=full`; per-seed diff reported, byte-identical elsewhere |
| 7 | Completeness ledger in each grid's docstring, stating what a green does NOT prove | the ledgers, carrying the gap-(c) sentence in the words above |

**Deferred, with its record:** the independent-model differential (Option
A layer 4), and its honest form as an OpenSpiel `universal_poker`
differential. Needs a tracker issue before any cell cites it.
