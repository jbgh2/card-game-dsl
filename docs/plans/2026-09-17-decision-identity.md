# Telling a seat what it is asked — issue #713

**Date:** 2026-09-17. **Lane:** B (`cardlang/runtime/**`, `cardlang/openspiel/**`).
**Counsel:** Hoyle and Foster, sitting 2026-09-16/17; Headnotes and the joint
bottom line below. **Operator ruling:** the payload's grain, section 4.

## The decision, as narrowed

A Seat Policy is handed its Seat View and the legal action ids and nothing
else, so it cannot tell a lead from a pass. The fact it lacks is not new
knowledge: the game declares it as a phase and as the sentence that asks.

The choice is **where "what this seat is asked" enters the engine's knowledge
model** — as a fourth knowledge source read off control-flow state, or as an
observation the kernel delivers to the decider through the channel the log
already is. Both seats counsel the second.

## What lands

One choke point every decision routes through emits, to the deciding seat,
before any Chooser is consulted:

```
("asked", <phase>, <construct>, <count>, <destination label or None>)
```

`SeatView`, `derive`, `render_information_state`, `Chooser` and the
`SeatPolicy` protocol are unchanged: the fact rides `obs_log`. One helper in
`infostate.py` is the single derivation every consumer reads.

## Why the log and not the world

The adapter's world at a decision node has already unwound past the phase
frames. Measured on this tree, Hearts at seed 7, seat 0's first decision:

| route | state variables in the view | log length |
|---|---|---|
| `replay.run` (pyspiel) | `cumulative_score` | 4 |
| `LiveLine.ask` (`cardlang play`) | `cumulative_score`, `pass_direction` | 4 |

The log agrees across both routes; the state does not. Issue #612 measures the
same thing across a manifest: the log agrees at 64 of 64 decision nodes, the
phase-local state at 0 of 64. A design reading the phase off the running world
is #612 reified; one riding the log is sound on both routes today.

## The operator's ruling — the payload's grain

**Phase, construct, count and the destination zone label.**

The construct's warrant (Hoyle, 2026-09-16, over all corpus games): the phase
identifies every card decision in 26 of 34 games and fails in 8, where two
card decisions of different kinds share one phase.

The destination label's warrant (measured 2026-09-17, this tree): of those 8,
`(phase, construct)` separates 7. Canasta is the residual — `stage_card`,
`add_to_meld` and `discard` are all `move chosen one card from hand[actor]
where <pred> to <dest>`, sharing phase, construct and source zone, and
differing only in destination. French Tarot's two are two halves of one
discard decision, not two kinds. The shape Canasta shows is the generic
melding shape, so the field is bought once here rather than paid for in a
second full-width regeneration later.

## The accepted coverage domain

Derived by a framing check over the whole `cardlang/` package, in a context
holding no plan (the registry-module manifest is issue #108, so the input is
the package by superset). The axes below are what survived the diff against
the author's provisional list; the starred ones the author did not have.

1. **Decision site** — `delegation.DECISION_POINTS`, reconciled against an AST
   scrape. Crossed with: routes through the choke point, emits `asked`.
2. **Round form** — `mechanics.build_form`'s exhaustive match. The round site
   fans out per form. `ROUTED_FORMS` matches by Python class name string, so
   the fan-out carries a rename hazard.
3. **Payload field shape** — `observe.PAYLOAD_SHAPES`, each shape crossed with
   its admitted alternatives and the nearest values a site could hand over
   instead.
4. **Destination-zone knowability, per site** (*) — derived, not uniform:

   | site | destination known |
   |---|---|
   | `execute._select_from`, `_select_filtered`, `_select_joint` | before the pick |
   | `mechanics.run_decision_round` / `TrickForm` | before the pick |
   | `mechanics` / `ClimbForm` | before, except a `pass` choice moves nothing |
   | `execute._pass_selection` | only after every seat has chosen |
   | `execute._offer`, `evaluate._choose`, `AuctionForm` | none |

   So the field admits None, and the sites that cannot know emit None rather
   than a plausible wrong answer.
5. **Consumers of an event kind** (*) — `observe.payload_refusal` (refuses
   loudly), `play.events.event_line`, `infostate.render_information_state`
   (`repr`, no reading), `partition.PAYLOAD_PROBES` / `SYNTHETIC_PAYLOAD`,
   the metamorphic pairing's rename map.
6. **Cross-registry reconciliation** (*) — two sources over one domain with
   nothing crossing them:
   - `EVENT_PAYLOADS` and `EVENT_LINES`. `play/events.py` states "a line for
     every kind `observe.EVENT_PAYLOADS` declares" in prose, and no code
     checks it: a declared-but-unlined kind passes `payload_refusal` and then
     raises `KeyError` where a seat reads its log. This change makes the claim
     a check.
   - `DECISION_POINTS` and `encoding._decides_a_content_item`. Two
     enumerations of the decision-site universe, keyed by call site and by AST
     node type, each reconciled against the tree and neither against the
     other.
7. **Emission per site** (*) — no table governs which sites emit an aggregate
   `chose` or `announce` today, and three (`_select_from`, `_select_filtered`,
   `_select_joint`) emit neither. The choke point makes `asked` uniform across
   all of them, which is the property a per-site hand placement cannot state.

## What this change does not close

- **A claim is not a bid.** Cheat's number is the count a player claims and
  may be lying about. Telling it from a bid needs a declared meaning for a
  number decision, which the language lacks — issue #703's class, not this
  one. The issue's own "what it returns" over-claims here; both seats ruled it
  independently.
- **The hidden-read predicate class.** The swap proof replays one recorded
  history in both worlds and drops pairs where a recorded action becomes
  illegal, so a divergence inside the replayed prefix is invisible to it; one
  first appearing at the pause is caught. The reddening witness is epic #312's
  chartered work. This change builds none and claims none.
- **The gate wall.** A phase gate reading hidden zone contents now states its
  value to the decider. Walling it needs a visibility-aware reading of
  expressions, whose domain is every expression arm — issue #281's engine and
  its audit, not a narrow shadow of it here.

## The plan — each step names the artifact that proves it

| # | Step | Proving artifact |
|---|---|---|
| 1 | The grid, authored red before implementation | `tests/test_asked_event.py`, cells `xfail(strict, raises=)` |
| 2 | `EVENT_PAYLOADS` gains `asked`; `PAYLOAD_SHAPES` gains its field shapes | the grid's shape cells; `test_observation_payloads.py`'s member/refusal reconciliation reddens until each shape has both |
| 3 | The choke point; every decision site routes through it | the `DECISION_POINTS` scrape, re-pointed; a pin that `ctx.chooser(` has one caller |
| 4 | `DECISION_POINTS` gains a construct column, fanned out per round form | the scrape, crossed with `build_form`'s match |
| 5 | Destination label per site, None where unknowable | the per-site knowability cells of the grid |
| 6 | `EVENT_LINES` gains its row, and the prose claim becomes a check | a reconciliation test over the two registries' key sets |
| 7 | `partition.PAYLOAD_PROBES` / `SYNTHETIC_PAYLOAD` gain the shapes | the soundness matrix, which refuses an undeclared shape |
| 8 | `infostate.current_ask` — the one derivation | a scrape pin that no other module reads `asked` off a log |
| 9 | `ranked.py` ranks a lead; the empty-pile draw arm retires | `tests/test_ranked_opponent.py`; the re-measured lead figure |
| 10 | Misuse probes | rejection tests, each loud in its layer's channel |
| 11 | Goldens regenerate at their own width | `CARDLANG_GOLDEN_SEEDS=full` |
| 12 | `decisions.md` bullet, glossary entry | `tests/test_doc_references.py`, `tests/test_glossary.py` |

## Counsel

### Hoyle — Headnote

A seat is never told what it is being asked, so the shipped opponent draws its
leads and passes at random and answers Cheat's "how many?" as a bid. Nothing
new needs saying in a game file: the sentence that asks already says what the
decision is, and the corpus proves it — in every phase where two card
decisions look alike to the seat, the sentences differ in what they move or
where. The rival, naming decisions by hand, loses: it collides with a word the
language already uses, and no game needs it. Not Merge Lane A; the grammar
does not widen. Zero game files move.

The phase is the right word for a person's header but the wrong answer to
"which decision": it separates every card decision in 26 of 34 games and fails
in 8, because designers phase their games at different grains. The precise
fact is the asking sentence's shape — construct and zones, never its line
number.

No rulebook game has a stage of play secret from a player, and the corpus
follows the rulebook idiom: all 23 phase gates read public facts, and the 15
of 326 control predicates that read hidden cards all read the deciding seat's
own and show the result before the next seat decides. So walling the phase
gate to public facts refuses no game.

### Foster — Headnote

The question is not which of three plumbing seams carries the phase; it is
where "what this seat is asked" enters what the engine knows: as a new kind of
public fact read off the running phase, or as something the engine tells the
seat at the moment of asking, through the channel it already uses to tell a
seat what it chose.

Recommended: tell the decider. One choke point that every decision passes
through emits "asked: this phase, this kind of decision, this many picks" to
the deciding seat before any chooser is consulted; the view, the policy
interface and the chooser signature do not change. Rejected: handing the fact
to the policy beside the view — cheapest, invisible to every proof, and absent
from the exported game, so the learned opponents could never see what the
rule-based ones do — and treating the phase as public state read off the
running world, because the adapter reads a world already unwound, so that
design gives the wrong answer on the very route the payoff is measured
against.

Newly required, for whoever writes a decision site: route it through the one
choke point and name its construct, or the table check refuses it. Newly
impossible, for every consumer: reading "what am I asked" off the log anywhere
but the one helper. Info sets: derived via the kernel's own observation to the
decider — no new knowledge source, no debt recorded here.

### The joint bottom line

Written by Foster as the seat sitting last.

No new surface: no grammar moves, zero game files change, and explicit
decision naming in a game file is refused on record. The seat is told what it
is asked through an observation the kernel delivers to the deciding seat at
each decision, from one choke point, before any chooser is consulted. The
payload carries the phase, the designer's own word, and the construct, the
kernel's word for the kind of sentence asking, never a source position: a name
pairs under the layout-neutral transforms, a line number does not. Not blocked
by #612 — this rides the channel that bug measured sound. Not blocked by #281,
provided the ledger names the prefix blindness and cites it rather than
claiming a proof. Land on main, operator merge, with the ranked opponent's
lead arm as the executed consumer.

**Strongest against, from either counsel.** The string moves for every game to
state a fact already implied by it — partition-neutral churn on today's
corpus, paid in every golden regenerating, longer strings on the hottest
derivation, and every recorded prompt or policy keyed on the string changing
shape. And a phase gate reading a hidden zone would now state its value to the
decider outright, where today it leaks only through the legal actions.

**Left to the operator, stated and not resolved.** The gate wall: Hoyle lands
it in the same change, Foster lands none. The scoping dissolves half the
divergence — on the gate alone the wall shadows nothing, and "public" is the
right criterion because a gate has no actor. What remains is ownership: the
wall needs the visibility-aware expression reading that is #281's own engine.
Accepting it rules a hidden gate a defect; declining it rules it a reveal to
the decider. Either way this lands.
