# Deck-builders as the on-ramp to card effects

*Exploratory design analysis — a proposal about sequencing, not settled
spec. Companion to `generalization-path.md` axis 4 (effect composition, the
CCG horizon). The governing constraint, set explicitly: the effect design
must leave Innovation and bounded Magic: the Gathering **not-impossible** —
the on-ramp may not pour concrete the ceiling would need removed.*

## The reframe

[roadmap.md](../roadmap.md), "Out of scope", defers deck-builders
alongside CCGs. The deferral is really
about one thing, and it is narrower than the grouping suggests. Everything
else in a deck-builder already exists: deck, hand, discard, market row, and
trash are ordinary zones; the cycle-discard-into-deck loop is zone movement
plus `shuffle`; deck-order hiddenness falls out of the existing model with
no new projection — the owner observed every card entering the discard
(identity), the shuffle is a chance node, so the information set correctly
holds the multiset but not the order. Opponents' deck compositions are
derivable from public gains and trashes, making deck-tracking a
perfect-recall skill an artificial seat gets for free (see
`llm-player-seats.md`, the recall-confound caveat).

What deck-builders genuinely force is **effect scripts attached to cards**:
rules that live on a card type and execute when it is played, rather than
rules inlined in phases and moves. That is the mild end of axis 4 — and the
distance between it and MtG is structural, not just quantitative. A
Dominion-class game has a closed card pool fixed at setup, each effect a
bounded imperative script over existing kernel verbs (draw, discard, gain,
trash, adjust counters), no stack, no open-ended targeting. That is exactly
the "extensions compute; only the kernel acts" seam, and the
Turing-completeness construction needs machinery this class deliberately
lacks.

## The ladder

1. **Star Realms / Ascension** — arithmetic effects and count-based
   synergies ("if you played another card of this faction..."). Effect
   scripts at their simplest: straight-line verb sequences plus
   conditionals over public counts.
2. **Dominion (base)** — the two mechanisms that matter: **reactions**
   (Moat — a decision window inserted into another player's turn) and
   **Throne Room** (apply an effect to another card's effect — the first
   genuine higher-order composition).
3. **Dominion (expansions)** — duration cards are **deferred triggers**:
   an effect registered now, firing at a later event. This is the second
   witness for the deferred/conditional-reveal capability C5
   (`../research/topology-and-query-requirements.md`; Fury of Dracula is
   the first), so the corpus-first three-witness discipline starts to bear
   on C5 through this genre.
4. **Aeon's End** — the sleeper: the deck is never shuffled, so chosen
   discard order becomes deterministic future draws. Zone ordering as
   load-bearing strategic state, with zero randomness — a sharp test of
   the ordered-zone model rather than of effects.
5. **Clank! / Dune: Imperium** — deck-building fused with a board (dungeon
   graph; worker placement), joining this genre to the topology axis.
6. **Innovation** — approaching the horizon: dogma's demand/share
   mechanics execute one card's effect *by multiple players*, conditioned
   on derived icon counts (splay), with effect density closer to a CCG.

## The ceiling constraint: not-impossible for Innovation and bounded MtG

The on-ramp is only worth building if the top of the ladder stays
reachable. `generalization-path.md` axis 4 already fixes the outer bound:
unrestricted MtG is Turing-complete and out; **deck-scoped, bounded-length
MtG compiles**. For that to remain true, the effect-script design must
respect five forward-compatibility requirements from day one — none of
which Dominion itself strictly needs in full generality, all of which cost
little if chosen early and a rewrite if not:

1. **Effects are values.** An effect is a first-class datum attached to a
   card type, not syntax inlined at a use site — otherwise Throne Room
   (apply another card's effect) and MtG's effect-granting ("gains haste")
   are unreachable. This is adjacent to, but distinct from, axis 3's
   rules-as-selectable-values.
2. **An open event-trigger registry.** Durations subscribe an effect to a
   future event; MtG's triggered abilities are the general form ("whenever
   X happens, do Y"). The registry must be a language concept even if the
   first release only exposes on-play and duration triggers.
3. **Interrupt windows.** Moat's reaction is the minimal case of a
   decision window inside another player's action; instants and
   counterspells are the general case. The kernel's decision model must
   admit out-of-turn choosers.
4. **Bounds by declaration, not by prohibition.** Totality and sub-Turing
   guarantees are preserved the same way class-7 queries handle NP-hard
   searches: effect iteration and composition depth are admitted against
   declared bounds (deck size, a declared trigger-chain limit), statically
   checked, rejected with a clear message when unbounded. Composition is
   never banned outright — that is what keeps bounded MtG in reach.
5. **Effects act only through kernel verbs.** Every effect's mutations and
   reveals route through the same closed verb set, so observation events —
   and therefore derived information sets — fire uniformly no matter how
   exotic the effect. An effect that bypasses the kernel is the
   `instantiate` escape hatch reborn; the deletion of that hatch is the
   precedent this requirement rests on.

A sixth, softer note for Innovation specifically: dogma needs an effect's
*executor* to vary (each player with fewer icons obeys the demand), i.e.
the actor of a script is a parameter, not a lexical constant. Cheap if the
script model takes an actor argument from the start.

## What this note does not settle

The effect-script surface itself (syntax, verb inventory, how a script
declares its bounds); whether reactions are a kernel change or a phase
pattern; how the market row's variable setup interacts with surface
totality (ten kingdom piles from a large card set = a per-setup closed
pool — likely the same declared-data mechanism as Scrabble's lexicon); and
where on the ladder the first implemented witness should sit — though
Star Realms or base Dominion is the obvious candidate, for the same
corpus-first reason Hearts came before Bridge.
