# Design decisions

This document specifies the design's load-bearing decisions in detail.
Open questions — designs that aren't yet committed — live in
[open-questions/](open-questions/).

## Typed phase outcomes

Some phases have more than one legitimate way to end. Pinochle's
`declare_trump` phase resolves either as "trump declared" or as "the
bidder had no marriage and abandoned the contract." Bridge's `bidding`
phase resolves either as a final contract with a declarer or as "all
four players passed without bidding."

A phase declares its outcome type in its signature:

```
phase declare_trump → outcome { trump_declared(Suit) | bid_abandoned }
```

The enclosing structure pattern-matches on the outcome:

```
declare_trump produces:
  trump_declared(t):
    continue to melding
  bid_abandoned:
    score[high_bidder.team] -= current_bid
    skip to next hand
```

This makes failure-by-design a first-class concept without exception
ceremony. Most phases still have a single implicit success outcome;
the typed-outcome syntax appears only when a phase can resolve more
than one way.

Rules signal "satisfied" or "unsatisfiable" without dictating what
happens next. A rule that finds no legal move in its `demands`
reports unsatisfiable; the enclosing phase interprets that signal in
context. The phase decides whether unsatisfiable means error, fallback,
or a typed outcome other than success.

**Mechanics produce typed outcomes the same way.** A mechanic that
resolves to a tagged value uses the same `outcome` parameter the
mechanic accepts as a callback. Pinochle's `Auction` takes
`outcome: (final_bid, last_active_player) → effect`; Skat's
`Reizen` takes `outcome: (winner, value: Integer | all_pass) → effect`;
French Tarot's `TarotBidding` takes
`outcome: (winner, level: BidLevel) | all_pass → effect`; Trick's
`outcome` parameter produces a Player. The enclosing structure
pattern-matches on the produced value the same way it does for
phase outcomes:

```
bidding produces:
  taker_chosen(_, level):
    if level == Petite or level == Garde:
      continue to chien_visible
    else:
      continue to play
  all_pass:
    skip to next hand
```

Mechanics and phases are *not* further unified at the construct
level. The distinction stays:

- A **mechanic** is a named, parameterized, reusable unit, instantiated
  with arguments. It's the right shape when a chunk of logic appears
  in multiple games (Trick, Auction, BettingRound).
- A **phase** is a positional unit in the phase tree, not parameterized
  and not reusable across games. It's the right shape when a chunk
  appears at a specific position with semantics tied to where it sits.

Both can produce typed outcomes; both can be dispatched on. What
the typed-outcome system unifies is the *result discipline* — every
named piece of game logic that resolves to a value uses the same
tagged-value protocol — not the structural distinction between
"reusable abstraction" and "positional step."

## The boolean-as-sub-phase criterion

A boolean state variable that *gates rules* should be a sub-phase
instead. A boolean that's *purely informational* (read by scoring or
similar end-of-phase logic, not by any rule's `applies_when:` or
`demands:`) stays a variable.

Examples:

- `hearts_broken` in Hearts: gates the `NoLeadingHeartsUntilBroken`
  rule. Modeled as a sub-phase transition, not a boolean.
- `spades_broken` in Spades: same shape, same treatment.
- `is_first_trick`: gates rules unique to the first trick. Modeled
  as a sibling sub-phase (`first_trick`) rather than a boolean.
- `bid_abandoned` in Pinochle: a candidate boolean that would gate
  scoring branches. Modeled instead as a typed outcome on the
  `declare_trump` phase (see "Typed phase outcomes" above) — the
  phase resolves either to `trump_declared(Suit)` or `bid_abandoned`,
  and enclosing structure routes on the outcome.
- `dummy_revealed` in Bridge: read by zone-routing helper, no rule
  gates on it. Correctly a boolean.

The criterion: ask whether any rule reads the boolean in its
`applies_when:` clause. If yes, the boolean is hiding a phase
transition; refactor to sub-phases. If no, it's just data.

**Per-player exception.** A boolean indexed by player (e.g.,
`has_played_yet[player]` in Tichu) that gates only a move's own
preconditions is left as state rather than reified as a per-player
sub-phase. Reifying would require parallel sub-phase instances and
per-instance transition triggers — language surface the corpus has
chosen not to add. The boolean form keeps the gating in the move
type's `preconditions:` block, which is co-located with the move
it's about.

## Sub-phase entry and exit

A sub-phase is entered and exited in one of three ways. All three
exist in the corpus; choosing among them is a matter of which one
the rulebook describes.

**Sequencing (default).** The enclosing phase body lists sub-phases
in order; control enters the next sub-phase when the previous one
ends. Used for setup → bidding → play → scoring pipelines.

**Predicate guard.** `phase X when <pred>` makes the sub-phase
active *exactly when* the predicate holds. The phase is entered the
first time the predicate becomes true and exited as soon as it
becomes false. Hearts' `passing` sub-phase uses this for the case
when `pass_direction != none`; Tichu's `wish_active` sub-phase uses
this for the case when a Mahjong wish stands. No explicit
`transition_to:` is needed — the predicate is the entry guard *and*
the exit condition.

**Event-triggered sibling transition.** `transition_to: Y when <event>`
inside sibling X switches control to sibling Y when the event fires.
The `<event>` is the same reference form triggered scoring components
use — a move-type event with an optional `where <predicate>` (see
"Triggered scoring components"); there are no ad-hoc event names.
Hearts breaks hearts with `transition_to: hearts_broken when
play_to_trick where action.card.suit == hearts`; Spades breaks spades with
`transition_to: spades_broken when play_to_trick where action.card.suit ==
spades` (the move under inspection is bound as `action` — see "Rule demand
forms"). The transition is one-shot — once Y is entered, X is not
re-entered.

There is no separate construct for "this sub-phase ends and control
returns to the enclosing parent's loop." The predicate-guard form
covers it: when the predicate becomes false, the sub-phase exits,
and control resumes in whatever parent body invoked it. Reaching
for `transition_to: parent` is a sign that what's really needed is a
predicate guard.

## Sub-phase rule and legal-move deltas

A sub-phase inherits its parent's `active_rules` and `legal_moves`. To
modify the inherited sets, the sub-phase uses three operators inside
the slot:

```
phase parent { active_rules: [A, B, C] }

phase child_extend   { active_rules: [+ D] }            // adds D       → A, B, C, D
phase child_remove   { active_rules: [- B] }            // removes B    → A, C
phase child_override { active_rules: [override A2] }    // replaces A   → A2, B, C
```

`override X` matches by name: the parent rule with the same identifier
as `X` is replaced by `X`. If no parent rule matches the override
target, it's a compile error — there's nothing to override.

The same operators apply identically to `legal_moves`:

```
phase parent { legal_moves: [play_to_trick] }
phase child  { legal_moves: [+ declare_marriage] }
```

A slot may mix operators and plain entries — a sub-phase that lists
a bare rule is shadowing inheritance with its own complete set:

```
phase parent { active_rules: [A, B, C] }
phase child  { active_rules: [X, Y] }                   // X, Y only — parent set discarded
```

**Corpus usage.** Every existing use is `+ X`. Hearts, Spades, and
Schnapsen add follow-restriction rules; Pinochle and Spades add
first-trick constraints; Tichu adds the Mahjong-wish rule; Schnapsen
and Tichu add legal moves (close_talon, exchange_trump_jack,
call_tichu, call_grand_tichu) during their respective windows. `- X`
and `override X` are reserved for cases where the rulebook itself
describes a rule being struck out or replaced. The rulebook-natural
reading of every game in the current corpus uses `+ X` even when the
mechanical effect could be expressed as a removal — including
Schnapsen's close-the-talon transition, which was specifically
investigated for `- X` and read as `+ X` on the strict-play
sub-phase.

The criterion for which operator to use: write the slot the way the
game's rulebook introduces the change. Rulebooks describe what
*kicks in*, not what *goes away*; the syntax follows.

## Rule demand forms

A rule's `demands:` clause takes one of two forms, distinguished by
what it constrains:

- **A candidate-card set** — an expression returning the cards a legal
  move may use, filtering a zone. `MustFollowSuit`'s `demands:
  hand.cards_of_suit(state.led_suit)` and Hearts' `demands:
  hand.where(c => c.suit != hearts)` are this form. The legal move set
  is the intersection of every active rule's candidate set.

- **A predicate on the move** — `demands: actions where <predicate>`,
  constraining the shape of the move itself rather than which cards it
  draws from a zone. Hearts' `PassExactlyThreeCards` is `demands: actions
  where action.card_count == 3`; Stud's `BringInMandatory` is `demands:
  actions where action.amount == bring_in_amount`. Cribbage's two-card
  discard and Tichu's one-card-per-opponent push are the same form.

The two are not interchangeable: the first names *which cards*, the
second *how the move is shaped*. A move is legal when it satisfies
every active rule's demand, of either form.

**The move under inspection is bound as `action`.** A predicate over a
player's move — `demands: actions where …` here, and the `when <move-type>
where …` triggers of sub-phase transitions (see "Sub-phase entry and exit")
and triggered scoring components — binds that move as `action`, and its
fields expose the move's data: `action.card` (the card played),
`action.cards`, `action.card_count`, `action.actor`, `action.amount`. The
subject is always reached through `action`; there are no bare field names,
and it is never spelled `move` — `move` is the zone-movement verb (see "The
operation vocabulary"). `action` is the same player-move object the `offer
action` syntax names. (The *concept* is still a move type; `action` is an
instance of one, as taken.)

## Trick mechanic parameters vs rules

Some phase-level configuration is *not* a rule even though it looks
like one. The Trick mechanic accepts `outcome:`, `routing:`,
`early_termination:`, and `chooser_for:` as parameters. These
modify *what happens after a play* (who's the winner, where the
cards go, when the trick ends early, who picks); rules modify
*which plays are legal*.

The categories don't unify:

- **Rules** are filters on the candidate-move set. They're attached
  to phases via `active_rules:` and consulted before each move.
- **Trick parameters** (`outcome:`, `routing:`, early_termination`)
  are arguments to the mechanic. They run once per trick (or per
  play) and produce the trick's effect.
- **Choice helpers** (`chooser_for:`, `play_source_for:`) are
  per-game functions consulted by the mechanic when it solicits a
  move.

Getaway's first-trick-to-waste behaviour is the canonical mistake:
when written as a rule (`rule FirstTrickAlwaysGoesToWaste`) it has
nothing to constrain — its mechanical effect is a routing override
on the Trick instantiation. The correct form is to pass the routing
function directly:

```
phase first_trick {
  active_rules: [MustLeadAceOfSpadesOnFirstPlay]
  instantiate Trick (
    ...
    routing = all cards from trick_pile to waste
  )
}
```

Tichu's Dragon-routing similarly lives in the `TichuTrickRouting`
function, not in a rule. Hearts' `TrumpedHighestOfLedSuit` is an
`outcome:` function, not a rule. The clean test: if the
configuration's effect is "filter legal moves before play," it's a
rule; if its effect is "shape the trick's resolution after play,"
it's a mechanic parameter.

**Per-game predicates for contextual interpretations.** Some games
need to interpret card properties contextually rather than from the
card's intrinsic fields. Skat's jacks are trumps regardless of
printed suit; in Doppelkopf, both queens and jacks would be trumps.
The pattern: a per-game `same_suit_class(c1, c2)` predicate that
the standard `MustFollowSuit` rule consults instead of comparing
`c1.suit == c2.suit` directly. Most games keep the default
(printed-suit equality); games with contextual suits override.
Same shape as the `chooser_for` and `play_source_for` helpers — a
per-game function in the game file, not a new language construct.

## State scoping (lexical)

A variable is scoped to the phase that lexically encloses its
declaration. The variable's lifetime *is* the duration of one
instance of that phase: it is initialized to its declared default
when the phase is entered, and ceases to exist when the phase exits.
Re-entering the phase produces a fresh instance.

This is the conventional rule essentially every modern programming
language uses for block-scoped local variables. No `per_hand` /
`per_rubber` annotation. No `scoped_to:` keyword. The block that
contains the declaration *is* the scope. Refactoring a phase carries
its state with it.

**Reads from enclosing scopes are free.** A scoring component running
inside `hand_sequence` can read `games_won` declared in `rubber`
because `rubber` lexically encloses `hand_sequence`. This is ordinary
nested-scope visibility.

**Writes follow the same rule.** A phase may write to a variable
declared in its enclosing scope (Bridge's `scoring` writes
`games_won += 1` and `below_line_current_game := 0`, both of which
live in `rubber`). A phase may *not* write to a variable declared in
a sibling or descendant scope, because that variable's owning phase
may not be active. This is statically checkable.

**Example: Bridge state declarations.**

```
game Bridge {
  // No game-level state in Bridge.

  phase rubber repeats until any partnership.games_won >= 2 {
    state {
      games_won[partnership]              : Integer = 0
      above_line[partnership]             : Integer = 0
      below_line_current_game[partnership]: Integer = 0
    }

    phase hand_sequence {
      state {
        contract       : Contract? = none
        declarer       : Player?   = none
        dummy          : Player?   = none
        tricks_taken[partnership] : Integer = 0
        dummy_revealed : Boolean   = false
      }
      // ... phases inside hand_sequence ...
    }
  }
}
```

**Variables that need cross-phase visibility live in the smallest
enclosing scope that covers all their uses.** If a variable is read
by both `bidding` and `play`, it lives in their parent `hand_sequence`,
not in either. This is also how a result threads from one sub-phase to
a sibling: the trick `leader` that Hearts' `first_trick` hands to
`play` is a `Player` in their enclosing `hand_sequence` state —
`first_trick` seeds it (the two-of-clubs holder) and updates it to the
trick winner, and `play` continues from it. A mechanic's result is read
as bare `outcome` immediately after the mechanic runs (`leader :=
outcome`); there is no construct for referencing a prior phase's
outcome across the phase boundary — the shared enclosing variable is
the channel.

**Mechanic-internal state lives inside the mechanic.** Auction's
`passed[player]`, Trick's per-trick state, BettingRound's
`bet_to_match` all live inside their mechanics. Mechanic instances
are short-lived; their state vanishes with the instance.

**Rules consulted from within a mechanic see the mechanic's state.**
Lexical scoping puts the active mechanic instance's `state { }`
declarations into the scope chain at consultation time. A rule
attached to a phase that has instantiated a mechanic reads
`state.foo` and sees whatever `foo` is in scope — game state,
hand state, phase state, *or* mechanic-internal state — without any
explicit export step. This is the same scoping rule that applies
to imperative code in the phase body. Examples in the corpus:

- Hearts' `MustFollowSuit` reads `state.led_suit`, which lives
  inside the Trick mechanic.
- Pinochle's `BidExceedsCurrent` reads `state.current_bid`, which
  lives inside the Auction mechanic.
- Stud's BettingRound legality rules read `state.bet_to_match`
  and `state.raises_so_far`, which live inside BettingRound.

Rules are reusable across games; what binds them to a particular
mechanic's state is the call site (where the mechanic is
instantiated and the rule is attached as an `active_rules` entry).
Refactoring a mechanic's state shape is a potentially breaking
change for any rule that reads it — same as refactoring any other
in-scope variable. There's no separate "exposed subset" mechanism;
visibility is just lexical scoping.

**Tooling-generated state inventory.** Lexical scoping disperses
declarations across the phase tree. The "what state exists in this
game" view that helps when reading the file is a render of the
program — the doc-rendering pass or language-server walks the phase
tree and emits a per-phase state catalogue. State summary is
documentation, not declaration.

**OpenSpiel compilation.** Each phase frame carries its own state in
the State object, with lifetime tied to phase entry/exit. Standard
activation-record semantics.

## Loop termination semantics

A `repeats until <pred>` clause on a phase (or `repeat until <pred>`
on a phase-body block) is **continuously evaluated**: the loop
terminates as soon as the predicate becomes true, including
mid-iteration. When the loop terminates mid-iteration, every nested
phase, mechanic instance, and inner loop that was active is
abandoned in turn.

This matches standard activation-record semantics — when an outer
scope exits, every inner scope exits with it — and means most games
get mid-phase termination for free. Cribbage is the canonical case:
`phase hand_sequence repeats until any score >= 121` catches a
peg-out during pegging or during the show without any additional
machinery, because the predicate is re-checked the moment `score`
changes. The mechanic instances active when the predicate flips
(PeggingRound, the show batches) are abandoned.

Games where the termination predicate can change only at iteration
boundaries (Hearts: scoring is end-of-hand only) get the same
semantics; the continuous-evaluation rule degenerates to
"checked at iteration boundary" because that's the only time the
predicate could flip.

A separate `early_termination:` parameter does appear on the Trick
mechanic — that's for *trick-level* termination on game-state-free
conditions (Getaway's first-trick-to-waste). It is not for
game-ending; game-ending is the `repeats until` clause's job.

## Mutation semantics

**Sequential mutation within a phase body.** `:=` (assign) and `+=` /
`-=` (accumulate) statements execute in order. A statement sees the
writes of all earlier statements in the same body. A rule's
`applies_when:` and `demands:` are evaluated against the current
state at the moment the rule is consulted — meaning the rule sees the
writes of every preceding statement in the enclosing phase, plus
mutations triggered by intervening moves. No transactional isolation,
no copy-on-write, no implicit ordering tricks.

**Batched mutation for scoring components.** The one site where
mutation is *not* purely sequential is `apply_components:`. Each
component produces a `ScoreDelta` against the *pre-batch* state. The
deltas are summed, and the sum is applied once. This means:

- The order of components in the `apply_components:` list does not
  affect the result. (Component A and component B both reading
  `is_vulnerable(p)` see the same value, because neither has applied
  yet.)
- Threshold checks that should fire *after* the batch (Bridge's
  GameBonus reading `below_line_current_game >= 100`) are expressed
  as triggered components with `triggered_by: after apply_components`
  (see "Triggered scoring components" below). They see post-batch
  state.

This is the only batched-write site in the language. It has
fundamentally different read semantics from in-phase imperative
writes and is worth documenting as a distinct mutation mode.

A phase may contain *multiple* `apply_components:` batches in
sequence. Each batch is internally unordered (deltas summed against
pre-batch state, applied at once), but later batches see the
accumulated effect of earlier batches and any intervening imperative
statements. Cribbage's show uses this — non-dealer hand, dealer
hand, and crib are three sequential batches, with the
hand_sequence's `score >= 121` termination check observed between
each. Batching encodes "these scores are independent of each
other"; sequencing encodes "these scores depend on what came
before, potentially including game termination."

**Event-driven sub-phase transitions are not a third mutation mode.**
Hearts' `transition_to: hearts_broken when play_to_trick where
action.card.suit == hearts` is *phase entry/exit* triggered by the
move-emitted event.
The implied state change (the `NoLeadingHeartsUntilBroken` rule
becomes inactive) happens because the active rule set changes when
the phase changes, not because a `hearts_broken` boolean was written.

**Bulk write syntax.** Setup phases regularly do `tricks_won := 0 for
each team and player`. Generalized form: `var := initial for each
index`. The single-cell write `score := 0` and the indexed form
`score[t] := 0 for each team t` desugar to the same loop.

**Coupled resets and modulus accumulation are explicit.** Bridge's
"below-line resets for both sides when either side wins a game" is
written as a multi-write `ScoreDelta` inside the GameBonus triggered
component (see "Triggered scoring components" below). Spades'
bags-modulus reset is the same shape inside BagOverflow. There's no
language-level "coupled variables" or "wrapping accumulator"
construct; an explicit multi-write delta reads correctly.

**Phase-outcome destructuring** (Bridge's `bidding produces:
contract_made(c, d): contract := c; declarer := d; ...`) is just
ordinary sequential assignment — the destructuring binds locals; the
assignments are imperative writes following the same rules.

## Typed object model

The language has a typed object model with stdlib types built in,
user-defined types declared per-game, and convenience sugar that
rewrites to underlying forms.

**Stdlib types (built into the language):**

- `Card` — `{ suit, rank, attributes, optional facing }`. Suit and
  rank are declared at the game level (`cards { suits: { ... } }`,
  see "Deck declaration" below). Attributes are a per-game extension
  point. Facing is an optional built-in dimension that composes with
  zone visibility (see "Knowledge, visibility, and the projection
  model" below). Suit and rank are deck-defined *values*, not language
  keywords — a rank is any name or number, checked against the deck's
  `Rank` enum, so the grammar reserves no rank letters. A card is
  written either as `<rank> of <suit>` (`2 of clubs`, `Q of spades`)
  or, for a named card, as the bare constant the deck declares
  (`Dragon`, `Duke`), which resolves like a `Suit` value. The two axes
  are flexible: a suitless game degenerates one of them — Coup carries
  the character as the `rank` under a singleton dummy suit `court`, and
  makes no suit comparison.
- `Resource<Type>` — fungible quantity of the named type. Declared
  by the game's `resources { }` block.
- `Suit`, `Rank` — enumerable value types defined by the game's
  `cards` header.
- `Player` — bare identity; relational queries delegate to Seating.
- `Partnership` (alias: `Team`) — declared in the game header;
  indexable as a key into per-partnership state.
- `Seating` — derived from `players` + `partnerships`; exposes
  `partner_of(p)`, `left_of(p)`, `right_of(p)`, `LHO_of(p)`,
  `RHO_of(p)`, `opposite_of(p)`. Surface syntax `declarer.partner`
  is sugar for `seating.partner_of(declarer)`.
- `Zone<Contents>` — a container parameterized by what it holds.
  Carries a per-observer visibility declaration (see "Knowledge,
  visibility, and the projection model"), ownership, and structural
  type (set, ordered, stack).
- `ZoneContents` — the query API on zones and intermediate
  collections. Common operations: `where`, `count`, `non_empty`,
  `empty`. Card-specific: `cards_of_suit`, `highest_of_suit`,
  `has_card_of_suit`, `highest_by`, `contains_card_of_suit`.
  Resource-specific: `amount_of(type)`, `total_amount`,
  `types_present`.
- Phase outcomes — tagged-union values; pattern-matched, not
  dot-accessed.

**User-definable types.** Games declare struct-like types that the
language treats as first-class values:

```
type Contract = {
  level         : Integer in 1..7
  suit          : Suit | NT
  doubled_state : Doubled | Redoubled | Undoubled
}

type HandResult = {
  contract        : Contract
  declarer_side   : Partnership
  defender_side   : Partnership
  tricks_actual   : Integer
  tricks_required : Integer
}
derived {
  made = tricks_actual >= tricks_required
}
```

Derived fields are computable functions of declared fields. They're
accessed identically to declared fields (`result.made`) but are
stored nowhere; the compiler inlines them.

User-defined types may be parameterized with the same angle-bracket
convention as stdlib generics. They are the language's extension
point: games introduce concepts (Contract, HandResult, Meld, Pot) by
declaring them. The DSL doesn't ship a vocabulary covering every
possible game.

**Deck declaration.** The `cards { }` block declares which cards
exist in the deck. The canonical form is a per-suit map: each suit
names its own rank sequence. A list of suits as a key is shorthand
for "these suits share this rank list."

```
cards: {
  suits: {
    [S, H, D, C]: [2, 3, 4, 5, 6, 7, 8, 9, 10, J, Q, K, A]
  }
}
```

Tarot decks need this generality — the trump suit has a different
rank set from the standard suits:

```
cards: {
  suits: {
    [S, H, D, C]: [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, J, Cavalier, Q, K]
    atouts:      [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21]
  }
  specials: [Excuse]
}
```

**Stdlib decks.** Common deck compositions are stdlib constants —
see [library.md](library.md) "Stdlib decks". A game with a standard
deck writes one line:

```
cards: standard52
```

Games that extend a stdlib deck compose with `+`:

```
cards: standard52 + { specials: [Mahjong, Dog, Phoenix, Dragon] }
```

The composition adds the right-side clauses to the stdlib base. Used
by Tichu, which is standard52 plus four named singletons. (Tichu's
specials being non-(suit, rank) cards is a separate question from
how the deck composes; see
[open-questions/special-cards-declaration.md](open-questions/special-cards-declaration.md).)

**Per-card attributes.** Games can declare additional
Boolean/enum/integer attributes attached to every card in their
`cards { ... }` block:

```
cards: {
  suits: { [S, H, D, C]: [2..10, J, Q, K, A] }
  attributes: {
    tapped         : Boolean              = false
    counters       : Map<Name, Integer>   = {}
    summoning_sick : Boolean              = true
  }
}
```

Attributes are accessed via dot notation (`card.tapped`,
`card.counters`) and sugared over the underlying attributes map.
The mechanism is in place for CCGs and oriented-card games
(face-up/down piles, tapping, status effects) but no game in the
current corpus uses card attributes.

**Convenience sugar (rewrites that compile away):**

- `player.hand` → `hand[player]`
- `player.partner` → `seating.partner_of(player)`
- `player.team` → `team_of(player)`
- `team.score` → `score[team]`
- `partnership.games_won` → `games_won[partnership]`
- `state.foo` → `foo` (just a disambiguating prefix)
- `card.tapped` → `card.attributes[tapped]`

Sugar is documented; the underlying form is what the compiler
manipulates.

**Stylistic discipline.** The bracket form is the canonical
access syntax; the dot form is sugar for the simple-receiver
case. The corpus uses brackets whenever the index is a computed
expression (`hand[player]`, `captured[team_of(outcome)]`,
`hand[player offset_by pass_direction]`) and dots when the
receiver is a simple identifier (`p.hand`, `outcome.hand`,
`team.score`). Whether the dot form should admit complex
receivers, and whether the bracket form should be elevated to
*the* canonical form rather than a sibling, is an open
question (see
[open-questions/zone-access-syntax.md](open-questions/zone-access-syntax.md)).

## Resource amount syntax

A resource quantity in a `transfer` is written `<count> <type>` — the
count (an integer expression, or `all`) followed by the resource type
name:

```
transfer 1 coin       from treasury to coins[player]
transfer 7 coins      from coins[actor] to treasury
transfer amount coins from coins[target] to coins[actor]
transfer all coins    from coins[p] to treasury
```

Stud (`transfer 5 chips`, `transfer ante_amount chips`) and Coup
(`transfer 2 coins`, `transfer min(2, …) coins`) — the two
resource-using games in the corpus — both read this way, and both move
a single resource type per transfer. The `<count> <type>` form is the
canonical surface for that case.

For a transfer that moves *several* resource types at once, the
generalization is a map literal `{ type: count, … }`:

```
transfer { wood: 2, brick: 1 } from bank to hand[player]
```

No corpus game moves multiple types in one transfer yet, but the map
form is the multi-entry generalization of the single-type form (which
is the one-entry case, written without braces) and is reserved for it.
The rejected alternative `type × count` overloads multiplication and
reads worse beside ordinary arithmetic in amount expressions.

## Resource transfer failure

A `transfer` whose source lacks the requested amount is a hard error:
the move is illegal. The language provides no partial-fulfillment
primitive. A game that wants partial behaviour writes it explicitly,
with `min` or a conditional amount:

```
// Coup steal — take 2, or 1 if that's all the target has:
let amount = min(2, coins[target].amount_of(coin))
transfer amount coins from coins[target] to coins[actor]
```

```
// Stud all-in call — match the bet, or commit the whole stack:
let amount = min(bet_to_match - bet_by[actor], stack[actor].count)
transfer amount chips from stack[actor] to pots[0].contents
```

The two resource-using games converge on the same shape: compute the
deliverable amount at the game level, then transfer exactly that. The
complementary case — a payment that must *not* underflow (Coup's Coup
fee of 7, its Assassinate fee of 3) — is handled upstream by an
affordability rule that gates the action's legality, so the fee
transfer is always satisfiable when it runs. Neither case needs a
primitive; the explicit form reads correctly and keeps the failure
policy visible in the game file.

## The operation vocabulary

Games relocate cards and resources, reveal and hide them, shuffle and
rotate. These operations are a small, closed vocabulary in three families,
not an open-ended set of verbs. The surface reads like a rulebook, but each
verb lowers to one of a few semantic primitives — the same
small-core/rich-library split that makes `Trick` a library item rather than
syntax ([principles.md](principles.md)).

**Movement** — relocating items between two places. One primitive underlies
every movement verb: `deal`, `transfer`, `move`, `burn`, `muck`, and `draw`
are sugar that differ only in defaults (which zone, which visibility), not in
kind. A movement carries a selection (`all`, a count, or a `chosen`/`random`
amount), an item noun (cards, or a resource such as coins), a source place, a
destination (a single zone or `to each` recipient), and an optional
visibility override. The same construct is both a statement and a value — a
`Trick`'s `routing` argument is a movement. Because the amount is an
expression and the item names the unit, a resource transfer and a variable
amount are the *same* construct as a card deal; there is no separate
resource-movement syntax.

**Epistemic** — changing knowledge or order without relocating anything:
`reveal`, `peek`, `hide`, `announce`, `expose_top`, `forget`, `shuffle`. A
closed family; each is a prose statement (`shuffle deck`, `reveal proof to
all`) normalized to one IR node and resolved against a signature table
([library.md](library.md) "Operations"). Their effect is defined in the
projection vocabulary of "Knowledge, visibility, and the projection model"
below.

**State-cycle** — advancing a state variable through a list of values, e.g.
`rotate pass_direction through [left, right, across, none]`. Orthogonal to
the other two (it touches no zone): a single small construct.

**Surface: actions are prose, queries are calls.** Every operation above is a
prose statement — the built-in vocabulary reads as rulebook commands, one
surface for "what the game does." Call syntax (`player_holding(2 of clubs)`,
`cards_of_suit(s)`) is reserved for value-returning functions and named
user-defined operations, which appear in expression position. The dividing
line is *do* versus *answer*: an operation acts (a statement with effects), a
function answers (a value in an expression). The families above are a
*semantic* classification — each lowers to a small set of IR nodes — and are
independent of this surface choice; the bounded cost of the prose surface is
one production per operation, added as the corpus needs it.

A new rulebook verb is presumed an instance of an existing family — movement
sugar or an epistemic op — until a game proves it is genuinely none of them.
Adding a fourth family is a deliberate act, not the default response to a new
word.

## Knowledge, visibility, and the projection model

Knowledge over zone contents is the primitive concept for everything
the language models about information asymmetry. Cards and resources
both live in zones; visibility is a per-observer projection
assignment rather than a binary hidden/public flag.

### Knowledge as candidate sets

Every observer (player) has, at every moment, a **knowledge state**
about each zone they can observe. The knowledge state is a
**candidate set over possible zone contents**: which configurations
of the zone are consistent with what the observer has seen.

Two extremes:

- **Full knowledge**: the candidate set is a singleton — exactly one
  possible configuration.
- **No knowledge**: the candidate set spans every configuration the
  zone could possibly be in given the observer's prior information.

Most real states sit in between. Perfect recall means candidate sets
only narrow over time.

### Projections: what visibility controls

Visibility declares **which projection of the zone's contents the
observer's knowledge state is informed by**. A projection is a
function from "full zone contents" to "some derived value."
Observers see (and remember) values of the projection; their
candidate set is consistent with those observed values.

Six projections, ordered by informativeness:

| Projection | What it reveals | What an observer with this projection knows |
|---|---|---|
| `identity` | the full multiset of object/resource identities | exact contents, fully resolved |
| `identity_set` | the *set* (not multiset) of identities present | which objects/types are present, ignoring duplicates |
| `count_by_type` | a map from type → count | how many of each type, no individuation |
| `count_only` | one integer: total count | how many things, nothing else |
| `existence_only` | one bit: empty or not | whether the zone has anything |
| `trivial` | nothing | no information at all |

These form a lattice ordered by informativeness:

```
identity ⊐ identity_set ⊐ count_by_type ⊐ count_only ⊐ existence_only ⊐ trivial
```

Each step down "forgets" some structure of the full contents.

**Identity for resources** means "this zone holds N units of wood
and M units of brick" — for a fungible Resource, the identity-level
view is the count-by-type level. There is no per-unit identity
below that, because units have no individuated identity.

**Identity for cards** means the full multiset of cards, by suit and
rank — the per-card identification card games are built around.

The lattice is uniform: `identity` is the most informative
projection the contents support, whatever that means for the
contents' type.

### Per-observer visibility on zones

A zone's visibility declaration assigns each observer a projection:

```
zone_name : Zone<ContentType> {
  composition : <projection> to <observer-set>, <projection> to <observer-set>, ...
}
```

Three common shapes:

```
public_zone   : Zone<Card>     { composition: identity to all }
private_hand  : Zone<Card>     { composition: identity to owner, count_only to others }
hidden_deck   : Zone<Card>     { composition: count_only to all }
catan_hand    : Zone<Resource> { composition: count_by_type to owner, count_only to others }
```

Library types in [library.md](library.md) wrap common combinations
under named aliases.

### Per-observer visibility on moves

Moves can override the zone's default projection for specific
observers. When a move's effect on knowledge differs from what the
zone declaration alone would imply, the move carries a `visibility:`
clause:

```
transfer 1 random Resource from hand[victim] to hand[thief],
  visibility: {
    thief  : identity,
    victim : identity,
    others : count_only
  }
```

Without the override, observers see the move through their existing
zone projections. With it, the move emits per-observer events at the
declared projection level. Zone declaration is the default; the move
clause is the override.

### Observation events

A move from zone A to zone B transfers some sub-content. Observers
see the move through each side's projection:

- The **source projection** updates: A's contents shrink. Observers
  learn what left if their projection of A reveals it.
- The **destination projection** updates: B's contents grow.
  Observers learn what arrived if their projection of B reveals it.
- **Identity continuity** between source and destination is observed
  only if both projections support identity.

If A is `identity`-visible and B is `identity`-visible to observer
P, P sees the full move (specific object X went from A to B). If A
is `count_by_type` and B is `count_by_type`, P sees "one wood left
A, one wood arrived at B." If A is `identity` but B is
`count_only`, P observes a structurally weaker fact at the
destination — "a piece arrived" without learning its type.

### Formal distinctions

From the dynamic epistemic logic and partial-observation game theory
literatures:

- **De re vs de dicto knowledge.** *De re* is positional/identity
  knowledge ("I know *this specific card* is the Ace of Spades").
  *De dicto* is existential ("I know there is an Ace of Spades
  somewhere in this zone"). For cards, the `identity` projection
  gives de re; lower projections give progressively weaker de dicto
  knowledge. For resources, de re knowledge doesn't exist — there
  are no individual identities for resource units to have. The
  strongest knowledge available for resources is `identity` =
  `count_by_type` (knowing the type breakdown), which is itself a
  de dicto claim. A shuffle of a resource zone is a no-op
  semantically.

- **Perfect recall vs imperfect recall.** Perfect recall means
  "players never forget information revealed to them, nor the order
  in which it was revealed" (Kuhn 1953). Perfect recall is the
  precondition for CFR's regret bounds and for the equivalence of
  mixed and behavioral strategies. Perfect recall is the default;
  imperfect recall is opt-in via the explicit `forget` operation.
  Under perfect recall, candidate sets only narrow over time.

- **Public vs private vs semi-private events.** A public event is
  one where all observers get the same `identity`-level projection;
  a private event is one where only a subset gets `identity` and
  others get `trivial`; a semi-private event is one where
  non-participants get a non-trivial weaker projection (typically
  `count_only` or `existence_only`), observing that something
  happened without learning what. These distinctions map directly
  onto projection assignment per observer.

### Stdlib memory-affecting operations

| Operation | What it does | Effect on projections |
|---|---|---|
| `peek(target, observer)` | observer privately gains identity knowledge of the target | projection for observer becomes `identity`; emits private observation; other observers' projections unchanged |
| `reveal(target, observers = all)` | target is shown to observers (default: everyone) | projection for each named observer becomes `identity`; when `observers = all`, knowledge becomes common knowledge |
| `hide(target, hidden_from = all_except_owner)` | target's future projection is downgraded for the listed observers | downgrades to the zone's default-hidden projection; prior identity knowledge is preserved under perfect recall — observers remember what they saw |
| `shuffle(zone)` | the zone is shuffled (cards only; no-op on pure-resource zones) | preserves `count_by_type` and below; destroys any positional or per-card identity knowledge of zone contents |
| `announce(fact, observers = all)` | a propositional fact is communicated | observers' candidate sets updated by intersecting with `fact`; no physical zone change |
| `expose_top(zone)` | the top card flips face-up | shorthand for `reveal(zone.top, all)` |
| `deal(from, to, visibility)` | items move with per-recipient visibility | sequence of moves with per-recipient projection; emits implicit `count_only` semi-private observation to non-recipients (they see something moved) |
| `transfer(amount, from, to, visibility?)` | resource units move | analogous to `deal` for fungible quantities; per-observer projections per visibility clause or zone defaults |
| `muck(target)` | item leaves play to a trivial-projection zone | future zone projection is `trivial` for all observers; prior identity knowledge persists in observer histories (perfect recall) |
| `forget(observer, target)` | observer loses identity knowledge of the target | observer's projection of the target widens to the unseen universe; **breaks perfect recall** |

### `forget` is the escape hatch

`forget` is the only operation that breaks perfect recall. CFR's
regret bounds, the Kuhn-theorem equivalence of mixed and behavioral
strategies, and standard IS-MCTS guarantees no longer apply once a
game uses `forget`. The compiler emits a warning when `forget` is
used. Designers can express memory loss when a game demands it
(Cabo, Coup challenge resolutions, memory variants), but they're
informed of what they're giving up.

### OpenSpiel compilation

Provided no `forget` is used, the resulting game is perfect-recall
and CFR / IS-MCTS apply with standard regret bounds. Observation
events compile to per-player projection emissions; OpenSpiel's
information-state tensors flow through unchanged, generalized to
projection-shaped events.

## Scoring composition

Scoring composes from named components. The scoring phase of a game
declares which components apply:

```
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

Each component takes the hand result and returns a `ScoreDelta` — a
structured value carrying per-partnership (or per-player)
contributions. The scoring phase sums the deltas across all
components and applies the result atomically.

This composes by summation: the order of components in the list
does not affect the result (per "Mutation semantics" above, batched
mutation). Each component reads pre-batch state; all components
contribute to a single applied write.

**Structured-score shapes are per-game, not generalized.** Bridge's
`ScoreDelta { above_line, below_line }` has two channels per
partnership because the game-win threshold cares specifically about
below-the-line accumulation. Stud has a different shape: a list of
pots with per-pot eligibility, length data-dependent on all-in
history. The four games whose score is a single integer per player
— Cribbage, Skat, Oh Hell, Pinochle (final team score) — don't have
a "structure" at all; the structure lives in the *computation*
(Skat's `base × multiplier`, Cribbage's pegging stream + show), not
the *output*.

Bridge's channels and Stud's pots-with-eligibility don't share a
structural form. The minimal generalization that fits both ("list
of scoring channels with per-channel eligibility") would constrain
the corpus to express simpler games through a heavier abstraction,
and the third structured-score game (Skat) declined to produce a
third shape — it kept a scalar score. The honest read: structured
score is a per-game declaration, not a language-level concept. Each
game's `ScoreDelta` carries whatever fields the game's scoring
mechanics need (one integer, two channels, a list of pots, etc.);
no shared `ScoreStructure` type.

**Per-card point values are inline expressions or per-game
helpers.** Hearts scores `if card.suit == hearts then 1 elif
card == queen_of_spades then 13 else 0` inline; Pinochle scores
`if card.rank in [A, 10, K] then 10 else 0` inline; Tichu mixes
specials and ranks. A declarative rank-keyed `counters: { ... }`
block on the card definition was considered but only cleanly
handles the Pinochle shape — Hearts' suit-plus-special-card and
Tichu's special-card-plus-rank scoring both need richer
expressions. Inline conditionals scale to all three. Lift to a
per-game helper function when a table is large enough to repay
the indirection (the cribbage show-scoring components are an
example).

## Triggered scoring components

Some scoring fires in response to a specific event rather than as
part of an `apply_components:` batch. Bridge's GameBonus fires when
a partnership's below-the-line score crosses 100; RubberBonus fires
when `games_won` reaches 2; Spades' bag-overflow fires when
`bags >= 10`; Cribbage's pegging events (fifteens, pairs, runs,
thirty-one, last-card) fire on each play during pegging. These
share one shape, distinct from the batched per-hand composition:
fire on an event, evaluate a predicate, contribute a `ScoreDelta`.

A scoring component declares the trigger with a `triggered_by:`
clause analogous to a rule's `applies_when:`:

```
scoring_component <name> {
  triggered_by: <event> [where <predicate>]
  ScoreDelta { ... }
}
```

The event is either:

- A **move-type name** (`play_card`, `cut_starter`, `submit_bid`).
  The component fires when that move type is executed; the
  predicate is evaluated against post-move state and the move's
  carried data.
- A **synthesized phase event** (`end_of_round`,
  `transition_to: <target>` reached). These are emitted by mechanics
  or sub-phase transitions and named at their emission site.
- The synthetic boundary `after apply_components`. The component
  fires immediately after the enclosing scoring batch settles and
  reads post-batch state. This is how Bridge's GameBonus, RubberBonus,
  and Spades' bag overflow fire: a `ScoreDelta` accumulated by the
  batch may push a counter past a threshold, and the triggered
  bonus reacts to the resulting state.

The `where` clause is a boolean predicate on game state at the
moment the event fires. Common idioms:

- Threshold crossing: `below_line_current_game[winner] crosses 100`.
  Reads as "the value just changed *to* something ≥ 100 from
  something < 100." A value already above the threshold doesn't
  re-fire on every event; the predicate is true only on the
  transition.
- State equality: `running_total == 31 after the play`.
- Derived properties: `play_pile.suffix_same_rank_count >= 2`.

Triggered components are independent of `apply_components:`. They
are declared in the same `scoring_component` namespace and use the
same `ScoreDelta` machinery. A game's scoring is the union of its
batched components and its triggered components; both contribute
to the same accumulated score.

When a triggered component would cause a game-ending threshold
(Cribbage's 121, or any termination predicate), the `repeats until`
clause on the enclosing loop fires immediately upon the
triggered-component delta being applied. See "Loop termination
semantics" above.

**Corpus usage.** The corpus presently has nine triggered
components across three games — Bridge (GameBonus, RubberBonus),
Spades (BagOverflow), Cribbage (HisHeels, PeggingFifteen,
PeggingThirtyOne, PeggingPair, PeggingRun, PeggingLastCard). All
fit the shape above.

## `choose` as expression

`choose` is a primitive that elicits a player decision. It is used
in two forms in the corpus:

```
// Statement form (Pinochle Auction, declare_trump):
offer action to active_player:
  submit_bid:
    choose Integer with bid > current_bid ...
    current_bid := bid
```

```
// Expression form (Tichu Dragon routing):
all cards from trick_pile to captured[team of (winner chooses one opponent)]
```

The statement form is a binding: `choose <Type> with <constraint>`
names the chosen value and introduces it into the surrounding
scope. The expression form `<actor> chooses <description>` returns
the chosen value as an inline subexpression.

Both forms emit a public observation event of the choice. The
chooser is the named `actor` (explicit in the expression form;
implicit from the enclosing `offer action to` in the statement
form). The candidate set is determined by the type or description.

`choose` may appear inside routing functions, outcome functions,
phase bodies, mechanic bodies — anywhere an expression of the
chosen type is expected. There is no separate "choice-embedded
routing" mechanism; routing functions are ordinary expressions and
ordinary expressions may include `choose`.

## Bidding patterns

The corpus has three structurally distinct bidding patterns; bid
*value* and bid *meaning* are per-game concerns interpreted by each
game's scoring code rather than shared via a mechanic parameter.

| Game | Bidding shape | Bid value means |
| --- | --- | --- |
| Pinochle | ascending `Auction` mechanic (opening_bid 50, increment 10) | per-team total-points target (≥ bid succeeds) |
| Spades | inline per-player, no constraint between bids | per-team threshold tricks (≥ bid succeeds) |
| Oh Hell | inline per-player, dealer-hook constraint | per-player exact-tricks target (= bid succeeds) |
| Bridge | structured contract bidding (level + suit + doubling) | structured Contract value, not an Integer |

The four games don't share a common bid type or interpretation.
Bridge's contract is a structured value rather than an integer;
Oh Hell's bid is per-player; Spades and Pinochle differ on
threshold vs total-points. A `bid_meaning:` parameter on Auction
would only cover Pinochle's case, since Spades/Oh Hell/Bridge don't
use the Auction mechanic.

Bid interpretation is therefore a per-game scoring concern. Each
game's `scoring_component`s declare what counts as making the bid:

```
// Spades (ContractScoring):
if result.tricks_won[t] >= non_nil_bid:           // threshold
  delta_score[t] += 10 * non_nil_bid
```

```
// Oh Hell (TricksAndExactBonus):
if result.tricks_won[p] == result.bid[p]:         // exact
  delta[p] += 10
```

```
// Pinochle (inline):
if bidder_team_total >= current_bid:              // total-points threshold
  score[bidder_team] += bidder_team_total
```

The shared *bidding mechanic* possibilities — Auction for ascending
bidding, an inline per-player pattern — are extracted only when
multiple games clearly share them. Auction is the only such
extracted-and-reused mechanic so far (Pinochle uses it; Bridge will
have its own `BridgeAuction` for doubling and structured contracts).
Spades and Oh Hell both use inline per-player bidding; a
`PerPlayerBidding` mechanic could be extracted, deferred until a
third per-player-bid game (Wizard, Boerenbridge variant, 7-Truf)
arrives to confirm the shape.

## Delegated play

A move is normally chosen by the player it's attributed to: the
active player picks from their own hand, submits a bid on their own
behalf. Some games separate these — a move comes from one player's
zone, attribution stays with that player, but the *choice* is made
by a different player.

The canonical case is Bridge's dummy. Once revealed, dummy's cards
play from `dummy_hand[dummy]` (the move belongs to dummy, the
information-state attributes the play to dummy), but declarer is
the one who picks which card. Defenders play their own cards
normally.

The language handles this with per-game helper functions, not new
zone-level or move-level constructs:

```
play_source_for(actor) =                // which zone the move comes from
  if actor == declarer.partner and dummy_revealed:
    dummy_hand[actor]
  else:
    private_hand[actor]

chooser_for(actor) =                    // who decides what move it is
  if actor == declarer.partner and dummy_revealed:
    declarer
  else:
    actor
```

The Trick mechanic accepts an optional `chooser_for:` parameter
that defaults to the identity function (actor chooses for
themselves). Bridge passes its game-defined helper. Other games
omit the parameter. Any other choice-prompting mechanic that
exposes a similar parameter follows the same convention.

A game with delegated play also typically wants a parallel
`play_source_for` helper to route the actor's move-source zone
through the conditional. Both helpers live as ordinary per-game
functions in the game file.

The default — actor is chooser, hand is source — is implicit.
Games without delegated play declare neither helper and the
defaults apply.

**Why per-game helpers, not a zone-level construct.** A
`choices_made_by:` declaration on the zone type was considered.
The case against: delegated play is a niche pattern (Bridge dummy
and its near-variants — Honeymoon Bridge, Solo Whist with a
dummy). Lifting it to the zone type would add language surface
that every reader has to understand for a feature most games
never use. Per-game helpers stay local to the game that needs
them and integrate with the existing convention for routing
helpers (Bridge already had `play_source_for` before this
resolution; `chooser_for` is the symmetric counterpart).

Apparent second data points like Sheepshead's partner-by-card and
Doppelkopf's Re/Kontra announcements turn out *not* to be
actor-vs-chooser cases on close reading — they are
hidden-information / team-formation patterns where each player
still chooses their own moves. The Bridge family is the only
known case of true delegated play in the standard-deck corpus.

## Simultaneous moves and atomic effect

Some game steps consist of several moves that observers must see
as a single event, not as a sequence. Hearts' passing phase is
four card transfers happening as one act; a Catan-style trade is
two resource transfers that observers should see as a single
swap. The `simultaneously:` construct expresses this pattern
uniformly for cards and resources.

The construct is purely about atomic effect and coalesced
observation. It introduces no new mutation mode beyond
[mutation semantics](#mutation-semantics)'s batched-write semantics
and no new projection beyond the existing per-observer lattice
under [knowledge, visibility, and the projection model](#knowledge-visibility-and-the-projection-model);
the privacy of choices made inside the block is handled by the
source zone's projection, not by the block itself.

**Two surface forms, one semantics.** A wrapper block for the
general case and a player-iteration form for the common Hearts
pattern:

```
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

**Read semantics: pre-block state.** Every operation inside the
block reads state as it was at block entry. No operation
observes another's effects, including its own writes. This is
the same model as `apply_components:` in
[mutation semantics](#mutation-semantics) — a batched-write
context whose reads see pre-batch state. The order of statements
in the body is irrelevant; swapping lines yields the same
result.

**Write semantics: batched at block-exit.** All effects produced
inside the block are collected and applied as a single mutation
at block-exit. The surrounding phase body remains sequential
per [mutation semantics](#mutation-semantics); the block is one
indivisible step in that sequence. A statement following the
block reads the block's post-state.

**Observation semantics: one coalesced event per observer.** At
block-exit, the block emits exactly one observation event per
observer, recording the *set* of moves that occurred — each
projected through the observer's existing zone visibilities
(see [knowledge, visibility, and the projection model](#knowledge-visibility-and-the-projection-model)).
Observers cannot infer any ordering among the moves; no ordering
exists to infer.

The block does not introduce a new event category. It composes
the existing per-zone projections into a single coalesced event
per observer. Under perfect recall (the default), each observer's
candidate set updates exactly once per block, at block-exit.

**Privacy of in-block choices is handled by source-zone
projections, not by the block.** A `choose` step inside the
block operates on a zone whose projection already determines
what other observers see. In Hearts, the source `hand[player]`
is `Hand<player>` — identity to owner, count_only to others —
so when a player chooses three cards to pass, the choice itself
is a private observation for that player; other observers see
nothing about which cards were chosen until the coalesced
block-exit event reveals (at their projection level) the net
transfer. No new "commit then reveal" event split is needed;
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
([typed phase outcomes](#typed-phase-outcomes)), not to the
commit construct. A negotiable trade is a *phase* whose outcome
is either `agreed(...)` (entering a `simultaneously:` block to
commit) or `declined` (no commit, no block). The block is purely
the commit step; the choice of whether to commit is elsewhere.

**Hearts passing.** The passing phase reads as:

```
phase passing when pass_direction != none {
  active_rules: [PassExactlyThreeCards]
  legal_moves:  [transfer_between_hands]

  each player simultaneously:
    transfer chosen 3 cards
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
beyond `count_only`, because that's what `Hand<Owner>` projects
to non-owners.

**Catan-style trade (sketch).** A two-player resource trade
that may or may not be agreed:

```
phase trade_negotiation → outcome { agreed(Trade) | declined } {
  // ... players negotiate, propose, accept/reject ...
}

trade_negotiation produces:
  agreed(t):
    simultaneously: {
      transfer t.alice_gives from hand[alice] to hand[bob]
      transfer t.bob_gives   from hand[bob]   to hand[alice]
    }
  declined:
    // no transfer; play continues
```

The negotiation lives in a phase with typed outcomes; the
commit lives in the block. Observers of the resource hands see
one coalesced event at the block's projection level — for
public-count resources, both transfers as one swap; for private
hands, identity to the participants and count_only to others.

**Coup's challenge and block windows.** Coup tests this boundary with a
real published game. "Any player may challenge" and "the target may
block" sound like simultaneous group decisions, but the step that
carries weight is a *conditional commit* — challenge or not, block or
not — with a branching result (the claim stands or is refuted; the
action is blocked or proceeds). That is the phase/typed-outcome shape,
not the atomic-effect block. Coup models each window as a mechanic
resolving to a typed outcome (`claim_stands | claim_refuted`,
`blocked | not_blocked`), dispatched with `produces:`, with the
optional decision offered as `challenge`/`pass` (or `block`/`pass`)
moves. No `simultaneously:` block appears in Coup, and none of the
unforced body-grammar extensions below (in-block `if`, nested blocks)
is needed — the forcing function confirmed the split rather than
reopening it.

**Body grammar.** The body admits:

- **Moves** ([library.md](library.md), "Move types") and
  **memory operations** ([library.md](library.md), "Memory
  operations") — the primary contents.
- **`choose` expressions** inside move arguments — player
  decisions feeding move parameters. Standard expression form
  ([decisions.md](decisions.md), "`choose` as expression").
- **`for each` iteration over fixed collections** — used by
  Tichu's pushing phase to express "each player passes one card
  to each other player." The iteration must be over a value known
  at block entry (the player set, a fixed list); it cannot
  iterate over a collection whose membership is determined by
  in-block choices, since reads see pre-block state.
- **`transfer` effects** — card and resource movement.

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
  passing skips passing entirely when `pass_direction == none`
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
[mutation semantics](#mutation-semantics); the block is one
indivisible step in that sequence.

**OpenSpiel compilation.** The block compiles to a single
information-state transition per observer. Each observer
receives one projection-shaped event recording the net effect
of the block's moves at that observer's visibility level —
exactly the same shape as single-move events, just with multiple
moves coalesced. Perfect-recall guarantees and CFR / IS-MCTS
applicability are preserved.
