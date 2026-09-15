# Scoring components — the rejected design, and the evidence that rejects it

Status: **rejected**, under [decisions.md](../decisions.md) "Scoring has no
constructs of its own". This note keeps the design that ruling declines,
together with the measurement behind the ruling, so that the alternative is
not re-derived: where an obvious shape was tried and set aside, the wall says
why. Nothing here is a proposal.

## The design that does not land

A scoring-component subsystem, in two halves.

**Batched components.** A scoring phase names the components that apply; each
takes the hand result and returns a `ScoreDelta` — a structured value of
per-team or per-player contributions; the phase sums the deltas and applies
the sum once, so component order does not matter and every component reads
pre-batch state:

```text
phase scoring {
  let result = HandResult(contract, declarer_side, ...)
  apply_components: [
    ContractTrickScore,
    OvertrickScore,
    UndertrickPenalty,
    SlamBonus
  ]
}
```

**Triggered components.** A component with a `triggered_by:` clause fires on an
event — a move type, a synthesized phase event, or the boundary
`after apply_components` — evaluates a predicate against post-event state, and
contributes a `ScoreDelta`:

```text
scoring_component <name> {
  triggered_by: <event> [where <predicate>]
  ScoreDelta { ... }
}
```

The decompositions it was designed to carry. Bridge: `ContractTrickScore`,
`OvertrickScore`, `UndertrickPenalty`, `SlamBonus`, and the triggered
`GameBonus` / `RubberBonus` on the below-the-line-crosses-100 and
games-won-reaches-2 thresholds. Spades: `NilScoring`, `ContractScoring`
(accumulating bags on overtricks), and the triggered `BagOverflow` on the
bags-cross-10 threshold. Bridge's coupled reset — both sides' below-the-line
totals return to zero when either side wins a game — was to be a multi-write
`ScoreDelta` inside `GameBonus`.

## Why it does not land

**Every game it was designed for landed without it, in plain statements.**
`docs/games/bridge.cardlang`'s scoring phase writes the game bonus as an `if`
on `below_current[dteam] >= 100` in sequence after the contract arithmetic;
the coupled reset is two assignments, one per team; the rubber bonus is a
nested `if` on `games_won`. `docs/games/spades.cardlang` writes the bag
overflow as a `repeat until` over the teams. Cribbage's pegging stream,
Pinochle's meld and Tarot's settlement each reached the kernel as ordinary
control flow plus a game-local Primitive — `docs/kernel-migration.md`'s
Workstream 4 lists all of them as done ahead of the subsystem it was meant to
build. The subsystem's motivating examples are its counter-examples.

**The corpus does not need it.** Measured 2026-09-07 over `docs/games/`
(denominator 32, from parsed ASTs, `PRIMITIVE_IMPLEMENTATIONS` and execution):

| what a game uses to score | games | expressible today |
|---|---:|---|
| accumulate a per-item value over a collection (`sum of … over cards in …`, `+= 1`) | 21 | yes |
| arithmetic on running totals | 16 | yes |
| a fixed constant on a boolean condition | 15 | yes |
| compare a total to a target and branch | 13 | yes |
| recognize combinations over a set of cards | 9 | partly — the subset binder reaches subset sums, pairs, flushes and rank-distinctness; not partition, catalogue-with-multiplicity, or a cross-zone source |
| zero-sum redistribution over players | 7 | simple pots yes; side-pot eligibility no |
| no arithmetic — a flag set by a terminal condition | 5 | yes |
| a value looked up by something other than rank | 3 | as an `if`/`elif` chain |
| strict-max over players of a derived quantity | 1 | as an idiom |

**21 of 32 games score with no Python at all**, using only the general
expression language, `card_points { }` and `winner:`. What each further step
would newly make Python-free: a subset source spanning two zones — cribbage;
partition-argmin — gin; a declared meld catalogue — belote, canasta, pinochle,
skat; composite ordering *and* side-pot eligibility together — the three poker
games; an ordinal-to-value table — five-hundred; tarot's settlement — tarot.
Of the 44 Primitives the corpus declares, 15 are scoring and 29 are legality,
turn order, trick routing, auction ladders or reveal sequencing; the five
mechanic-slot namespaces that also reach Python contain no scoring at all.
`poker.py` — one shared module behind three games' declared Primitives — is the
corpus's only library-shaped Python; every other item in the tail is
one-of-a-kind.

**No language with a corpus has built one.** Read 2026-09-07 from sources:
CARDSTOCK/RECYCLE (117 games) scores with a single grammar production,
`scoring : ('min' | 'max') int`, unchanged since 2016 while its corpus grew
from 9 games; its real scoring surface is an additive attribute-to-value table
declared per game, which is `card_points { }`. Ludii has six end ludemes; GDL
has `goal(R,N)` and `terminal`; RBG has bounded score variables. In all four,
scoring is a variable play adds to plus one instruction on how to rank it, and
the variety lives in the general expression language. What bounded RECYCLE's
grammar was deletion: 31 of the 135 productions it ever defined were removed
and never restored. Dead surface is the measured failure in both healthy
corpora — one RECYCLE construct is used by none of its 265 files in eleven
years, and Ludii's `payoffs` appears in 2 of 2,200 files, both test fixtures.
(The growth-over-time claims in this paragraph are from that research pass and
were not re-derived from the upstream history here; the repository's language,
grammar file and file counts were.)

**Its escape hatch would have been at the wrong granularity.** ZRF has no
arithmetic and cannot score a bridge hand; it offered a whole-game C plug-in
whose outcome channel is three categorical constants, and the hatch bought
nothing. The `primitives { }` block is a typed function declared in the game
file, which is the granularity Forge uses to cover 33,700 cards with no
per-card code.

## What the ruling licenses instead

Recognition over card sets grows on witnesses, as general constructs — the
subset binder is the first; a subset source that spans two zones (cribbage's
hand and starter) is the next, widening the subset form's own source slot and
never the shared `zone_expr`, because the union is a computed collection that
the type system already refuses wherever a zone is demanded. Pricing stays in
`card_points { }` or in the arithmetic beside it. What the language cannot yet
say about a hand stays a declared Primitive: gin's partition minimum, tarot's
settlement, and poker's shared module until composite ordering and a
player-returning selection earn witnesses of their own.
