## Simultaneous moves and atomic effect

Some game steps consist of several moves that observers must see
as a single event, not as a sequence. Hearts' passing phase is
four card transfers happening as one act; a Catan-style trade is
two resource transfers that observers should see as a single
swap. The `simultaneously:` construct expresses this pattern
uniformly for cards and resources.

The construct is purely about atomic effect and block-exit
observation. It introduces no new mutation mode beyond
[mutation semantics](mutation-semantics.md#mutation-semantics)'s batched-write semantics
and no new projection beyond the existing per-observer lattice
under [knowledge, visibility, and the projection model](knowledge-visibility-and-the-projection-model.md#knowledge-visibility-and-the-projection-model);
the privacy of choices made inside the block is handled by the
source zone's projection, not by the block itself.

**Two surface forms, one semantics.** A wrapper block for the
general case and a player-iteration form for the common Hearts
pattern:

```text
// Wrapper form.
simultaneously: {
  <move1>
  <move2>
  ...
}

// Player-iteration form (sugar).
each player simultaneously:
  <body using `player`>
```

The iteration form desugars to a wrapper block whose body is
the per-player body instantiated for each player, all running
as one atomic step. The two forms compile to the same
underlying construct; the iteration form exists because
"all players act simultaneously" is how rulebooks read in the
Hearts case, and the iteration sugar matches that reading.
(Compare Getaway's sequential sibling `each player in turn
starting from dealer.left:`; the language has a parallel pair
of constructs for the two timing modes.)

**The iteration form's body is one chosen transfer.** That is not an
implementation limit dressed up as a rule — it falls out of the pre-block read
semantics below. The form must snapshot *every* player's selection against the
state as it was at block entry, and only then apply them all; that is what makes
the pass atomic, and it is why nobody sees a passed card before choosing their
own. A snapshot is only defined for a chosen transfer out of a zone, so anything
else in that slot — an assignment, a plain (unchosen) transfer, a block — is
rejected. The runtime has always required this; the checker now says so, instead
of letting it through to a crash.

**Read semantics: pre-block state.** Every operation inside the
block reads state as it was at block entry. No operation
observes another's effects, including its own writes. This is
the language's one batched-write context ("Mutation semantics"): reads
see pre-block state, and nothing else in the language reads that way. The order of statements
in the body is irrelevant; swapping lines yields the same
result.

**Write semantics: batched at block-exit.** All effects produced
inside the block are collected and applied as a single mutation
at block-exit. The surrounding phase body remains sequential
per [mutation semantics](mutation-semantics.md#mutation-semantics); the block is one
indivisible step in that sequence. A statement following the
block reads the block's post-state.

**Observation semantics: one batch per block, at block-exit.** At
block-exit, each observer receives the block's moves as one
batch: an ordinary movement event per constituent transfer, each
projected through the observer's existing zone visibilities
(see [knowledge, visibility, and the projection model](knowledge-visibility-and-the-projection-model.md#knowledge-visibility-and-the-projection-model)),
landing together with nothing between them. A transfer both of
whose sides are trivial to an observer carries nothing to it and
emits nothing, as for any movement. The batch runs in seat order,
which is fixed before anyone chooses, so observers cannot infer
any ordering among the moves; no ordering exists to infer.

The block does not introduce a new event category: each event of
the batch is the movement event a lone transfer emits. Under
perfect recall (the default), each observer's candidate set
updates exactly once per block, at block-exit.

That is the effect. The *elicitation* is sequential, because the
OpenSpiel tree carries no simultaneous node: the block asks one
seat at a time in seat order — one chooser call per seat, itself
one decision node per card the call draws — with every selection
taken against the pre-block state and none applied until all are
in. The ordering is not itself observable: a seat's information
state moves at its own picks and at block-exit, never across
another seat's.

**Privacy of in-block choices is handled by source-zone
projections, not by the block.** A `choose` step inside the
block operates on a zone whose projection already determines
what other observers see. In Hearts, the source `hand[player]`
is `Hand<player>` — identity to owner, count_only to others —
so when a player chooses three cards to pass, the choice itself
is a private observation for that player; other observers see
nothing about which cards were chosen until the block-exit
batch reveals (at their projection level) each transfer. No new "commit then reveal" event split is needed;
the existing projection model already covers it.

**Failure semantics: atomic-or-nothing.** If any move inside
the block would error — either because no candidate satisfies a
rule's `demands:` and the rule's `if_impossible:` is `error`, or
because the move violates a zone constraint, or for any other
reason a single move would fail — the block aborts and *none*
of the block's moves apply. This generalizes single-move failure
to the block scope: the block is a single failure unit.

The block does *not* model abandonment ("Alice and Bob negotiate
a trade and Alice walks away"). Abandonment is a legitimate
game outcome, not an error, and belongs to the phase machinery
([typed phase outcomes](typed-phase-outcomes.md#typed-phase-outcomes)), not to the
commit construct. A negotiable trade is a *phase* whose outcome
is either `agreed(...)` (entering a `simultaneously:` block to
commit) or `declined` (no commit, no block). The block is purely
the commit step; the choice of whether to commit is elsewhere.

**Hearts passing.** The passing phase reads as:

```cardlang-fragment passing_phase
phase passing when pass_direction is not hold {
  legal_moves:  [transfer_between_hands]

  each player simultaneously:
    move chosen 3 cards
      from hand[player]
      to   hand[player offset_by pass_direction]
}
```

The four transfers — one per player — are committed as one
atomic step. Each player's choice of which three cards to pass
is private to them (per `Hand<player>`'s projection); each
player learns the three cards they receive (per their own
hand's identity-to-owner projection) at block-exit. No observer
learns which cards passed between any other pair of players
beyond `count_only`, because that's what `Hand<player>` projects
to non-owners.

**Catan-style trade (sketch).** A two-player resource trade
that may or may not be agreed:

```text
phase trade_negotiation → outcome { agreed(Trade) | declined } {
  // ... players negotiate, propose, accept/reject ...
}

trade_negotiation produces:
  agreed(t) {
    simultaneously: {
      move t.alice_gives from hand[alice] to hand[bob]
      move t.bob_gives   from hand[bob]   to hand[alice]
    }
  }
  declined {
    // no transfer; play continues
  }
```

The negotiation lives in a phase with typed outcomes; the
commit lives in the block. Observers of the resource hands see
both transfers in one block-exit batch at their projection level
— for public-count resources, the two counts together; for
private hands, identity to the participants and count_only to
others.

**Coup's challenge and block windows.** Coup tests this boundary with a
real published game. "Any player may challenge" and "the target may
block" sound like simultaneous group decisions, but the step that
carries weight is a *conditional commit* — challenge or not, block or
not — with a branching result (the claim stands or is refuted; the
action is blocked or proceeds). That is a sequenced-response shape,
not the atomic-effect block: serializing responders in seat order is
faithful, because a response reacts to what is already on the table. No
`simultaneously:` block appears in Coup, and none of the
unforced body-grammar extensions below (in-block `if`, nested blocks)
is needed — the forcing function confirmed the split rather than
reopening it. (The encoding sequences real `challenge`/`allow` decisions
clockwise from the claimant — a `repeat until` pointer walk with one
`offer` per responder, first challenge closing the window,
[games/coup.cardlang](../games/coup.cardlang) — and the blocker's claimed
character is folded into the block window's vocabulary, so the bluff is
itself the offered decision.)

**Body grammar.** The body admits:

- **Moves** ([library.md](../library.md), "Move types") and
  **memory operations** ([library.md](../library.md), "Memory
  operations") — the primary contents.
- **`choose` expressions** inside move arguments — player
  decisions feeding move parameters. Standard expression form
  ([decisions.md](../decisions.md), "`choose` as expression").
- **`for each` iteration over fixed collections** — the shape a
  "each player passes one card to each other player" push would
  take inside the block. The iteration must be over a value known
  at block entry (the player set, a fixed list); it cannot
  iterate over a collection whose membership is determined by
  in-block choices, since reads see pre-block state. (Tichu's
  push in fact needs no `simultaneously:` block at all: each
  player's three picks land in a per-player `gift` pile and are
  distributed only after every pick, so plain sequential chosen
  transfers are simultaneous by construction —
  [games/tichu.cardlang](../games/tichu.cardlang).)
- **`transfer` effects** — relocation of cards and resources.

The body does *not* admit:

- **State writes** (`:=`, `+=`) — no game in the corpus has
  needed a state write inside a `simultaneously:` block beyond
  what `transfer` already provides. Permitting them would raise
  semantic questions about whether the write participates in
  the batch and what other body statements observe (the read
  semantics says "pre-block state," but a write would seem to
  imply otherwise). Reserved until a real game forces it.
- **`if` branches** — same shape: branching effects in a batched
  context raise "which branch participates" questions. Hearts'
  passing skips passing entirely when `pass_direction is hold`
  via a phase-level `when:` guard rather than an in-block
  branch. Reserved until forced.
- **`let` bindings** — the body's expressions are short enough
  that in-block intermediate bindings haven't been forced.
- **Nested `simultaneously:` blocks** — composing batched-write
  scopes has unresolved semantics for which writes participate
  in which batch.

The unforced forms are not architectural blockers — adding any
of them later is a small change to the body parser. They're
omitted because the corpus hasn't validated what their semantics
should be, and committing semantics speculatively risks pinning
a wrong choice. Tichu's push and Hearts' pass cover the patterns
the corpus actually uses; the open grammar would be earned by a
game that demonstrably needs it.

**Placement.** A `simultaneously:` block may appear anywhere a
statement can appear in a phase body — as a phase's sole body,
as one statement among many, or inside an iterative construct.
The surrounding phase body remains sequential per
[mutation semantics](mutation-semantics.md#mutation-semantics); the block is one
indivisible step in that sequence.

**OpenSpiel compilation.** The block compiles to a single
information-state transition per observer. Each observer
receives the block's batch at block-exit — one projection-shaped
movement event per transfer, at that observer's visibility level,
exactly the shape of single-move events. Perfect-recall
guarantees and CFR / IS-MCTS applicability are preserved.
