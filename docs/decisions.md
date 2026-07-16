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
  trump_declared(t) { continue to melding }
  bid_abandoned {
    score[high_bidder.team] -= current_bid
    skip to next hand
  }
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

**Rounds and mechanics produce typed outcomes the same way.** A `round`
that resolves to a tagged value names an `outcome` callback over its bid
history: Bridge's auction produces
`contract_finalized(declarer, level, strain, doubling) | all_pass`,
Pinochle's produces `bid_won(declarer, bid)`, Tarot's
`taken(taker, level) | thrown_in`; the trick `round`'s `outcome` function
produces a Player. (An auction with nothing to tag — Skat's Reizen, a
betting round — omits the callback and threads phase state instead.) The
enclosing structure pattern-matches on the produced value the same way it
does for phase outcomes:

```
bidding produces:
  taker_chosen(_, level) {
    if level is Petite or level is Garde { continue to chien_visible }
    else { continue to play }
  }
  all_pass { skip to next hand }
```

A round's result is also available as the bare `outcome` pronoun
in the enclosing body, immediately after the `round`: Hearts
follows its trick `round` with `leader := outcome`, reading the trick's selected
player. This is the same value a `produces:` block would match; the bare
`outcome` is the shorthand for a single-payload result that needs no tag.

Mechanics and phases are *not* further unified at the construct
level. The distinction stays:

- A **mechanic** is a named, parameterized, reusable unit — the shape for
  a chunk of logic that appears in multiple games. The corpus currently
  has none: the trick, the auction, a betting round, and the climbing
  trick are configurations of the kernel `round` construct, and every
  formerly-Python hand engine is DSL over it. The category remains for
  future in-DSL definitions promoted corpus-first (an ascending `auction`,
  a `betting` round, real response windows).
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

- `hearts_broken` in Hearts: gates the `NoLeadingSuitUntilBroken(hearts)`
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
when `pass_direction is not hold`; Tichu's `wish_active` sub-phase uses
this for the case when a Mahjong wish stands. No explicit
`transition_to:` is needed — the predicate is the entry guard *and*
the exit condition.

**Event-triggered sibling transition.** `transition_to: Y when <event>`
inside sibling X switches control to sibling Y when the event fires.
The `<event>` is the same reference form triggered scoring components
use — a move-type event with an optional `where <predicate>` (see
"Triggered scoring components"); there are no ad-hoc event names.
Hearts breaks hearts with `transition_to: hearts_broken when
play_to_trick where action.card.suit is hearts`; Spades breaks spades with
`transition_to: spades_broken when play_to_trick where action.card.suit is
spades` (the move under inspection is bound as `action` — see "Rule demand
forms"). The transition is one-shot — once Y is entered, X is not
re-entered. It is scoped to the enclosing phase instance: when a
`repeat until` loop begins a new iteration and re-enters the phase, the
transition resets (Hearts re-breaks hearts each hand), per the
activation-record semantics in "Loop lifecycle".

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

**Corpus usage.** Every existing use is `+ X`. Hearts and Spades add
follow-restriction rules; Pinochle and Spades add
first-trick constraints; Tichu adds the Mahjong-wish rule; Tichu adds
legal moves (call_tichu, call_grand_tichu) during its window. `- X`
and `override X` are reserved for cases where the rulebook itself
describes a rule being struck out or replaced. The rulebook-natural
reading of every game in the current corpus uses `+ X` even when the
mechanical effect could be expressed as a removal.

The criterion for which operator to use: write the slot the way the
game's rulebook introduces the change. Rulebooks describe what
*kicks in*, not what *goes away*; the syntax follows.

## Rule demand forms

A rule's `demands:` clause takes one of two forms, distinguished by
what it constrains:

- **A candidate-card set** — an expression returning the cards a legal
  move may use, filtering a zone. `MustFollowSuit`'s `demands:
  cards in hand where card.suit is state.led_suit` and Hearts' `demands:
  cards in hand where card.suit is not hearts` are this form. The legal move set
  is the intersection of every active rule's candidate set. Because that
  intersection can empty — a void player cannot follow suit — a card-set
  `demands` **must** declare an `if_impossible:` fallback: `hand` to play any
  card, or `error(...)` to reject the move. There is no silent default (see "No
  implicit actions"); a card-set rule without `if_impossible` is rejected at
  resolve time.

- **A predicate on the move** — `demands: actions where <predicate>`,
  constraining the shape of the move itself rather than which cards it
  draws from a zone. Hearts' `PassExactlyThreeCards` is `demands: actions
  where action.card_count is 3`; Stud's `BringInMandatory` is `demands:
  actions where action.amount is bring_in_amount`. Cribbage's two-card
  discard and Tichu's one-card-per-opponent push are the same form.

The two are not interchangeable: the first names *which cards*, the
second *how the move is shaped*. A move is legal when it satisfies
every active rule's demand, of either form.

> **Enforcement status.** Card-set demands are enforced where the trick form
> computes card legality (`rules.legal_cards`, the trick round's decision
> site). The `actions where` form, and rules constraining move types other
> than `play_to_trick`, are resolved, type-checked, and emitted to IR but
> **not yet enforced at runtime** — rule application today runs at the trick
> form's card-decision site only. Hearts' `PassExactlyThreeCards` documents
> the game's law while the pass movement's `chosen 3` enforces the count.
> Widening rule application beyond trick play is an open question
> ([open-questions/rule-scope-beyond-trick-play.md](open-questions/rule-scope-beyond-trick-play.md)).

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

## Rule exemption (`exempts:`)

A rule may declare `exempts: <card-set expr>` alongside (or instead of)
`demands:`. When the rule's `applies_when` holds, the cards it selects sit
**outside the demand cascade entirely**: no other rule's `demands` can narrow
them away, they never count toward satisfying an obligation, and — when the
rule `constrains` a move — they are legal candidates offered **after every
other legal card**, in hand order, regardless of where they sit in the hand.

This is a distinct axis from `demands:`, not a special case of it. A card-set
`demands` can only *narrow* the running candidate set (`rules.legal_cards`'s
per-rule intersection); it has no way to *reorder* a card to the end of the
result regardless of hand position. French Tarot's Excuse needs exactly that:
it is never subject to follow-suit/trump/over-trump, never able to satisfy
one, and must be offered last — reproducing the reference implementation's
`base + excuse` candidate order, which the RNG stream depends on (a
determinized replay must draw the same candidate at the same list index).
Folding this into `demands:` (e.g. a "the demands union" trick, or
re-ordering the whole cascade's output) cannot express "exempt AND always
last" without special-casing the exempt cards somewhere — which is exactly
what a dedicated clause makes explicit instead of implicit.

Semantics (`cardlang/runtime/rules.py::legal_cards`): a pre-pass collects the
exempt set from every rule that `constrains` the move type in question and
whose `applies_when` holds; `working` is the hand minus that set; the demand
cascade runs over `working` exactly as before (unchanged code path); the
result is `working`'s narrowed survivors, in hand order, followed by the hand's
exempt cards, in hand order. A rule with no `exempts:` clause contributes
nothing to the exempt set, so a game that never uses this clause sees a
byte-for-byte identical result to before the axis existed (verified: every
pre-existing game's golden IR and characterization tests are untouched by its
introduction). `applies_when` gates exemption exactly as it gates a demand —
French Tarot's `ExcuseIsExempt` only exempts the Excuse once a suit has been
led (`state.led_suit is not none`), so the leader (who faces no obligations at
all) still sees their whole hand in its ordinary, unreordered position.

## Round configuration vs rules

Some phase-level configuration is *not* a rule even though it looks like one. A
trick `round` carries an `outcome` function and optional `trump` / `early`
clauses, and the surrounding body does the routing. These shape *what happens
after a play* (who is selected, when the pass ends early, where the cards go);
rules shape *which plays are legal*.

The categories don't unify:

- **Rules** are filters on the candidate-move set. They attach to phases via
  `active_rules:` and are consulted before each move.
- **Round configuration** (`outcome`, `early`, `trump`) and the post-round body
  routing run once per trick (or per play) and produce the trick's effect.

Getaway's first-trick-to-waste behaviour is the canonical mistake: written as a
rule (`rule FirstTrickAlwaysGoesToWaste`) it has nothing to constrain — its
effect is *where the cards go*, an ordinary body movement after the round:

```
phase first_trick {
  active_rules: [MustLeadAceOfSpadesOnFirstPlay]
  round play_to_trick from leader over all players source hand into trick_pile
        outcome highest_of_led_suit
  move all cards from trick_pile to waste
}
```

Hearts' `highest_of_led_suit` is the round's `outcome` function, not a rule. The
clean test: if the configuration's effect is "filter legal moves before play,"
it is a rule; if its effect is "shape the trick's resolution after play," it is
round configuration or body routing.

**Routing has two surface forms, both ordinary body statements.** When the
routing is a single unconditional movement, it is one statement after the round
(Hearts; Getaway's first trick: `move all cards from trick_pile to waste`). When
it branches — Getaway routes the pile to the trick winner on a tochoo (pickup)
but to the waste otherwise — it is an `if` over the round's terminal state:

```
phase play {
  round play_to_trick from leader over players where not eliminated[player]
        source hand into trick_pile outcome highest_of_led_suit early on_play_of_tochoo
  if state.trick_terminated_early { move all cards from trick_pile to hand[outcome] }
  else { move all cards from trick_pile to waste }
}
```

The body reads the round's `outcome` (the selected player) and its terminal
`state` (e.g. `state.trick_terminated_early`): a finished round's state stays
readable as `state.x` until the next round runs. Routing is just body
statements — there is no separate routing construct.

**Per-game predicates for contextual interpretations.** Some games
need to interpret card properties contextually rather than from the
card's intrinsic fields. Skat's jacks are trumps regardless of
printed suit; in Doppelkopf, both queens and jacks would be trumps.
The pattern: a per-game `same_suit_class(c1, c2)` predicate that
the standard `MustFollowSuit` rule consults instead of comparing
`c1.suit is c2.suit` directly. Most games keep the default
(printed-suit equality); games with contextual suits override.
Same shape as a `round`'s `outcome` or `early` function — a per-game or
stdlib function referenced by name, not a new language construct.

## The auction form of `round`

A trick is one pass over the participants; an auction is a *continuous ring* —
the turn order cycles repeatedly until the bidding closes. Both are the same
kernel `round`, configured along different axes ("Interactive decisions: a kernel
and an in-DSL standard library"). The continuous ring, its accumulator, and its
termination are axes **on the `round`**, not a `repeat until` loop wrapped around
a single-pass round: the loop, the turn-cycling, and the close condition live in
the kernel so the per-game file supplies only *values* (the move vocabulary, the
termination predicate, the outcome). Even Skat's Reizen call-and-response is a
*configuration* of this form — role-guarded moves over a two-participant ring
(the call-and-response bullet below) — not bespoke loop code in the game's
body.

The surface:

```
round offering [<move_type>, …] from <seat> over <ring>
      [order <ring | priority>] until <predicate> [outcome <fn>]
```

- **Move vocabulary (`offering`).** Each turn presents the acting player **one
  flat candidate list** of the legal concrete moves — every parameterized
  `move_type` expanded over its value-domain and guard-filtered, plus the nullary
  moves, in the order the vocabulary lists them (`offering [...]`) — resolved by a
  **single** decision (one chooser draw). This is not stylistic: the target
  runtime (OpenSpiel) mandates one
  finite, enumerable action set per decision node, so a turn is one node over a
  flat set, never an outer move-type choice followed by an inner parameter choice.
  Bridge's `submit_bid(strain : Suit?)` expands to one bid per strain whose
  cheapest beating level is still legal; `pass`/`double`/`redouble` are nullary.
  The declared domain set each parameter draws from, the cross-product rule
  for a multi-parameter move type, and the plain `offer` statement's
  identical enumeration are "Declared parameter domains," below.
- **The ring (`over`) is explicit; there is no silent skip.** A participant
  offered a turn always has at least one legal move — the finite-action invariant
  of a decision node. The game states *who is still in the ring* through the
  participants clause (`over <players> [where <predicate>]`, the same participants
  axis the trick uses — Getaway's `over players where not eliminated[player]`) and
  *when the bidding closes* through `until`. A player who has dropped out (passed
  for good, folded) is excluded by the participants predicate, and "all but one has
  passed" is a termination predicate — neither is an engine default. So a
  participant with no legal move is a **malformed game** (a missing always-legal
  move, or a participants filter that should have dropped the player), reported as
  an error, not a silently-skipped turn. Bridge keeps every seat in the ring with
  an always-legal `pass`. The participants predicate is **re-evaluated each turn**
  — the participant-filter axis: a ring that *shrinks* as players drop out
  (Pinochle's passed bidders and the standing high bidder, Stud's folders) drops a
  player the moment the predicate stops holding for it, so it is never offered
  another turn and consumes no draw. A static ring (Bridge's `all players`) is the
  invariant case. The trick form evaluates its ring once per pass, which — a trick
  being a single pass per participant — is observationally identical; this is one
  participants axis, with the continuous auction ring the case where per-turn
  re-evaluation is visible.
- **Order (`order`).** How the ring is traversed — a value on the closed order
  axis (turn-from-a-seat / priority / simultaneous). `order ring` (the default)
  is the continuous ring: the pointer advances each turn, so after a player acts
  the next *seat* is offered, wrapping. `order priority` re-scans the seat order
  from the leader every turn and offers the first still-pending participant: after
  an aggression re-opens earlier seats, action returns to the *earliest* owing
  seat, not the next one round the ring. Bridge/Pinochle/Tarot auctions are
  `ring`; Stud's betting is `priority` (a checked player responds to a later raise
  before seats that have not yet acted), and Coup's *interactive* response
  windows — the scope upgrade beyond its migrated rng gates
  ([kernel-migration.md](kernel-migration.md), Workstream 5) — would be too.
- **Call-and-response is a configuration, not an order value.** Skat's Reizen —
  a speaker naming successive ladder values against a responder who holds or
  passes, twice in sequence with the survivor advancing — runs on the plain
  ring: `round offering [bid, yes, pass] from <speaker> over players where
  player is <speaker> or player is <responder> until <someone passed, or the
  ladder is exhausted>`, with `bid` guarded to the speaker and `yes` to the
  responder. The seemingly new requirements each map to an existing axis:
  role-dependent vocabularies are move guards (the speaker's candidates filter
  to `[bid, pass]`, the responder's to `[yes, pass]`); conditional
  participation is the `until` predicate, checked before each draw (a pass —
  or the exhausted bid ladder, the reference's zero-draw auto-pass — ends the
  contest before the responder is offered a turn); the speaks-before-his-seat
  reorder is `from <speaker>` (the ring starts at the speaker regardless of
  seating); and the two sequential contests are two `round` statements
  threading the survivor through phase state. The order axis stays two values
  (`ring`, `priority`).
- **Accumulator.** The decision-relevant running state (Bridge's standing level,
  strain, doubling, high bidder, pass count) is ordinary **phase state**, read and
  written by the move-type effects and read by the termination predicate. No
  separate accumulator construct.
- **Termination (`until`).** A predicate over that state, checked each time around
  the ring (Bridge: three passes after a bid, four with no bid).
- **Outcome (optional).** A named function over the threaded **bid history** plus
  the terminal state — the same status as a trick's `outcome` callback (a
  runtime-primitive, no decisions of its own) — that produces the phase's typed
  variant. Bridge's `bridge_auction_outcome` finds the declarer (the first player
  of the high side to have named the final strain) and produces
  `contract_finalized(declarer, level, strain, doubling) | all_pass`. The `outcome`
  clause is **omitted** when the ring produces no variant: a betting round mutates
  shared chip/fold state directly through its move effects, so when the ring closes
  it simply returns and the surrounding body deals the next street or settles — no
  typed outcome, no `produces:` arm.

An auction's only decision points are these per-turn candidate draws; the outcome
callback consumes no randomness. So two auctions that present the same per-turn
candidate lists (same length and order) play identically under a random playout —
the property that lets a hand-written engine be re-expressed in this form without
changing behaviour.

## Declared parameter domains

A `move_type` may take any number of parameters (Go Fish's `ask(target :
Player, rank : Rank)`), each drawn from a declared, enumerable value-domain.
The parameters enumerate in **declaration order** (leftmost outermost) into a
**guard-filtered cross-product**: one candidate per combination of the
parameters' domain values that survives the move's guard, whether the move
type carries one parameter or several. This cross-product — not any single
parameter's domain in isolation — is what the OpenSpiel adapter treats as the
move's action space: a fixed set built from the declared domains, independent
of any one game state, with the guard evaluated per state as a **mask** over
that fixed set, never a set that grows or shrinks.

The enumerable *move-parameter* domains are a **closed set** — `Suit`, `Suit?`,
`Rank`, `Player`, `Card` — enforced at resolve time (see "Surface totality"):
any other parameter type is rejected with a message, and so is a
bounded-`Integer` parameter (not yet a *parameter* domain — the signed,
small-integer `play_card(delta : Integer)` case;
[open-questions/move-parameter-domains.md](open-questions/move-parameter-domains.md)).
A bounded-`Integer` **`choose`** domain, by contrast, *is* settled — see "The
integer `choose` domain," below.

- **`Suit` / `Suit?`.** A fixed value table: the four suits, plus `none` for
  the nullable form (Bridge's `submit_bid(strain : Suit?)`).
- **`Rank` / `Player`.** Fixed-from-type domains: `Rank` enumerates the
  game's declared `ranking:`, `Player` enumerates the seats — both closed,
  finite sets the runtime already knows independent of any one decision, so
  each enumerates the same way whether its parameter stands alone or is
  crossed with another in the same move type.
- **`Card`** — the corpus's first **state-dependent** parameter domain
  (Schnapsen's `play_card(c : Card)`, the lead-any-card arm of the leader's
  mixed vocabulary). `Card` enumerates the **acting player's live hand, in
  hand order**, then guard-filters like any other parameterized move. Hand
  order is load-bearing: card plays are offered in hand order everywhere
  else in the runtime (the trick form, filtered movements), so a deck-order
  enumeration filtered to the hand would put the same decision under a
  different chooser-draw contract. `Card` may appear only as a move's
  **sole** parameter: a second Card-parameterized move in one vocabulary, a
  Card parameter combined with another parameter, and a Card parameter in a
  game with no `hand[player]` zone are each rejected with a message.

**Enumeration surfaces.** A plain `offer` statement enumerates a
parameterized move type the same way the auction `round offering` vocabulary
does ("The auction form of `round`," above): every combination of its
declared domain(s), guard-filtered, folded into **one flat candidate list**
resolved by a single decision — one chooser draw, one public announce —
never an outer move-type choice followed by an inner parameter choice. Go
Fish's `ask(target : Player, rank : Rank)` is offered this way via a plain
`offer`: the declared domain is the full 4 × 13 seat-by-rank cross-product,
and the guards ("not yourself", "a rank you currently hold") mask it down,
per state, to whichever pairs are actually legal for whoever is on turn
([games/go-fish.md](games/go-fish.md)).

**OpenSpiel encoding.** `Suit`, `Suit?`, `Rank`, and `Player` parameters each
mint one vocabulary action id per cross-product combination, fixed for the
game regardless of how many combinations are ever legal in any one state.
`Card` is the exception: a Card-parameterized move contributes **no
vocabulary action ids**. A card play already has an id — the card block's —
so the adapter folds a `(play_card, c)` candidate into `card_to_action(c)`,
and a card's action id is identical whether it is the leader's `play_card` or
the follower's plain movement pick; `num_distinct_actions` does not grow with
the parameter. (Minting per-card vocabulary ids instead would give one card
play two representations.) This is also why at most one Card-parameterized
move may appear per vocabulary: the card id alone must name the move.

**The integer `choose` domain.** `choose integer in <lo> .. <hi>` is the
numeric decision form (a bid — Spades' `0 .. 13`, Oh Hell's `0 .. hand_size`).
Its domain is a bounded integer interval, and it satisfies the same
closed-contract-plus-mask rule as the fixed domains above: the OpenSpiel action
space reserves a fixed block of ids `0 .. ceiling` up front, and the live
`lo .. hi` range masks it per state (the runtime already offers exactly
`range(lo, hi + 1)`). The **ceiling is a declared, checked static bound**, never
inferred from the deck or a runtime value:

- When `hi` is itself a static integer literal (Spades' `13`), that literal is
  the ceiling — no extra syntax.
- When `hi` is a runtime expression (Oh Hell's per-hand `hand_size`), the author
  declares the ceiling with an **`up to N`** clause
  (`choose integer in 0 .. hand_size up to 10`), `N` a bare integer literal.

`up to` is *only* for a runtime `hi`. On a literal `hi` it is rejected at
resolve — the literal is already the exact ceiling, so an `up to` there is
either contradictory (a ceiling below the literal makes the runtime range guard
fail for every playout) or redundant (a ceiling above it reserves action ids
legal in no state). A `choose` whose ceiling cannot be determined statically (a
non-literal `hi` with no `up to`) is likewise a resolve-time error — surface
totality, never a silent default (`up to N` takes a bare non-negative integer
literal, so the ceiling is always well-formed). A **literal lower bound above
the ceiling** — an inverted literal range (`5 .. 3`) or a literal `lo` past an
`up to` ceiling (`11 .. n up to 10`) — is rejected the same way: the smallest
value the `choose` could offer already exceeds every id the block reserves, so
no value can ever be chosen; a runtime `lo` is not statically decidable and is
left to the runtime guard. At runtime the *range* is guarded
where `hi` is evaluated (`lo >= 0` and `hi <= ceiling`): a live range that
escaped its declared domain would offer a legal value with no action id, and a
value-only check would pass whenever the chooser happened to draw inside the
reserved block. The OpenSpiel integer block is sized to the game's **largest**
declared ceiling (one shared block; a game has at most one `choose` per decision
point today), so `num_distinct_actions` reflects the declared bounds — not a
fixed deck-sized constant. The still-open sibling is the bounded-`Integer`
*parameter* domain (signed `delta`), which fits neither this `0 .. ceiling` id
scheme nor any corpus game yet
([open-questions/move-parameter-domains.md](open-questions/move-parameter-domains.md)).

## The climbing form of `round`

Combination-climbing games (Big Two, Tichu) run on a third
configuration of the kernel `round`. A climbing trick plays like a trick, but each
play is a *combination* (a computed set of cards), not a single card:

```
round climb <move_type> from <leader> over <participants>
      source <zone> into <zone>
      combinations <lead_query> follows <follows_query>
      until <predicate>
```

The leader leads a combination from the `combinations` lead query; each
participant in turn beats the standing play with a higher combination of the same
size (from the `follows` query) or passes — a pass does **not** drop a player. The
trick ends when action returns to the last player who played (everyone else passed
one full lap), when `until` holds (a player has shed out — Big Two; a game whose
tricks always play out writes `until false` and ends the hand in the surrounding
`repeat until` — Tichu), or the instant the lead itself is a trick-ending play:
the engine may mark a play `ends_trick` (Tichu's Dog), and the form then closes
the trick with **zero follower draws**. The last player to play is
the `outcome`; the surrounding body routes the pile and the next lead, exactly as
for a trick. Like the trick form, the climbing form exposes its terminal state to
the body (`mech_state` → `last_round_state`, read as `state.x`):
`state.lead_ended_trick`, and `state.shed_first` / `state.shed_second` — the
first two players who played their last cards this trick, in play order, from
which a finishing-order game (Tichu: double victory, first-out routing, call
payouts) folds its global out-order without any extra chooser draw.

Two decisions distinguish it from the trick and auction forms:

- **The combination engine is a named query, not a DSL value.** A combination play
  moves a *specific computed card-set* — the cards of the chosen combination — and
  the movement vocabulary moves cards *by count* (`all` / `one` / `N cards`), never
  a named set. So a combination play cannot be a DSL `move_type` effect the way a
  bet is, and there is no DSL-visible `Combination` value. Instead the engine is two
  **game-local stdlib queries** named on the round — `combinations` (lead options)
  and `follows` (legal follows) — and the climb form performs the card movement itself.
  The engines stay per-game because the combination rules differ materially (Big
  Two: suit tie-breaks on every play, flushes and quads, cross-type beating within
  the five-card group; Tichu: rank-only keys, bombs, the four special cards); they
  merge only at a third instance (Pinochle melds would be a further one), per the
  promote-at-the-third rule. The construct depends only on the queries' interface: a
  list of plays, each exposing its cards as `.cards`.

- **The winner is the loop's last player, not an outcome function.** Unlike the
  trick form, which selects the winner from the played cards, the climbing winner is
  whoever played the standing combination when everyone else passed — returned
  directly. There is no `outcome` callback.

As with the auction form, the round's only decision points are the per-turn
candidate draws (the lead query, then `[follows…, pass]`); the scoring and routing
in the surrounding body consume no randomness — where a game's *rules* are random
(Tichu's Dragon trick going to a random opponent, its random-rate call gates at
the migrated scope), that randomness is a game-local stdlib primitive drawing on
the shared `rng`, not a chooser decision. So a climbing hand re-expressed on
this form reproduces a hand-written engine's behaviour byte-for-byte when it
presents the same per-turn candidate lists — the property both migrations
([games/big-two.cardlang](games/big-two.cardlang),
[games/tichu.cardlang](games/tichu.cardlang)) are verified against
([kernel-migration.md](kernel-migration.md), Workstream 3).

For the OpenSpiel action space, a climb play's id comes from the engine's play
universe — enumerated and golden-pinned when it is small (Big Two: 19,898), or
**computed by an arithmetic codec** (pure card-set ↔ index functions over a
fixed per-kind block layout) when enumeration is infeasible (Tichu:
211,204,694 — straights under free suit assignment dominate). Either way the id
is a stable function of the card-set, which is what determinized replay needs;
the codec route is the designed answer for any future engine whose combination
space explodes ([kernel-migration.md](kernel-migration.md), Workstream 3).

## No implicit actions

Every decision point has at least one legal move, and the engine neither invents
one nor silently skips the decision. Where a player would have nothing legal to
do, that is a **malformed game** — reported as an error, not absorbed. This keeps
the action space honest (the OpenSpiel finite-enumerable invariant) and makes a
missing rule, an unguarded choice, or a too-wide participant set *loud* instead of
hidden. The fix is always something the game states explicitly; the reusable forms
live in the standard library so a game opts into a behaviour by name:

- **An `offer` (or any ring of decisions) with no legal move** → add an
  always-legal move to the vocabulary (an unguarded `pass`/`decline`), or guard the
  decision (`if <able> { offer … }`). For a ring that shrinks as players drop out,
  narrow the participants clause (`over <players> where <still-in>`) so a player
  with nothing to do is never offered a turn.
- **A rule that can filter every candidate** → declare its `if_impossible`:
  `error(...)` to reject the move, or an explicit fallback card-set. A trick play
  with no legal card (a rule emptied the set with no fallback, or the hand is
  exhausted) is an error, not an implicit pass.
- **A `choose` over an empty domain** (e.g. an inverted range) → an error; a choice
  must offer at least one candidate.
- **The acting player is never defaulted.** A choice or chosen movement made with
  no acting player is an error ("who is choosing?"), not a silent attribution to
  player 0 — wrap it in a per-player context (`for each player p`, the simultaneous
  pass) so the chooser knows who decides.

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

  phase rubber repeat until any partnership.games_won >= 2 {
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

**Round-internal state lives inside the round.** The trick `round`'s
per-trick state (`led_suit`, the played cards) and the climb's
(`lead_ended_trick`, the shed order) live inside the construct's own frame,
readable as `state.x` during the round and, for the just-finished round, in
the surrounding body. (Schnapsen's talon-closing snapshot, once a Python
mechanic's local, is ordinary phase state now that its hand runs on the
kernel — closes and marriages are public declarations at the table, so
`closed_by` and the closer-snapshot counters are public state per "Hidden
information lives only in zones; state is public"; Coup's window results are
public phase-state Booleans the same way.) A round's frame is short-lived;
its state vanishes when the next round runs. (An auction's pass state or a
betting round's `bet_to_match` is *not*
round-internal — those forms of `round` thread their accumulator through
ordinary **phase state**, declared in the phase's `state { }`.)

**A round PUBLISHES a closed, typed set of fields, and `state.` names only
those.** A form's frame is also its working memory — the trick form drives its
turn order off a ring cursor and a materialized order list — and the two are not
the same thing. The published fields are declared once, with their types
(`cardlang/stdlib/round_state.py`): the trick form publishes `led_suit : Suit?`
and `trick_terminated_early : Boolean`; the climb form publishes
`lead_ended_trick : Boolean`, `shed_first : Player?` and `shed_second : Player?`;
the auction and betting forms publish **nothing** (their accumulator is ordinary
phase state, above — and that empty row is load-bearing, not an omission: it is
what makes "the auction form has no `state.`" a checkable fact). Naming anything
else — a misspelling, or one of the form's internals — is a compile error that
lists what *is* published. The wall is what keeps a form's working memory out of
the language: without it, a round's private ring cursor is nameable, type-checks,
runs, and silently changes the game. The declared types carry the same weight — an
untyped `state.x` is contagiously `Any`, and every comparison wall is dark behind
it.

**Rules consulted from within a round see the round's state.**
Lexical scoping puts the active round's state frame
into the scope chain at consultation time. A rule
attached to a phase whose round is running reads
`state.foo` and sees whatever `foo` is in scope — game state,
hand state, phase state, *or* round-internal state — without any
explicit export step. This is the same scoping rule that applies
to imperative code in the phase body. Examples in the corpus:

- Hearts' `MustFollowSuit` reads `state.led_suit`, which lives
  inside the trick `round`.

(The auction and betting forms of `round` express their legality differently —
not as `active_rules:` reading round state, but as the move types' own `when:`
guards over phase state: Pinochle's ascending bid guards `submit_bid` on the
standing bid; Stud's `check`/`bet`/`call`/`raise`/`fold` guard on `bet_to_match`,
`bet_by`, and `raises`.)

Rules are reusable across games; what binds them to a particular
round's state is the call site (the phase where the round runs and
the rule is attached as an `active_rules` entry).
Refactoring a form's state shape is a potentially breaking
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

**`let` bindings scope forward and carry their type.** A `let` binds
its name for the rest of the statement tuple it appears in — the same
sequential fold at all three layers: the resolver scopes the name, the
checker types it, the runtime binds the value. The binder's static type
is its initializer's inferred type in the environment at that point, so
every wall answers the same for the bound name as for the inline
expression (`let z = hearts` followed by `z is 3` is rejected exactly
as `hearts is 3` is). In a phase body the fold runs across the items:
a preceding `let` scopes over later statements and nested phases (their
`when`/`repeat until` qualifiers included) — what the driver evaluates
mid-body with the threaded context. It does NOT scope over the phase's
own `before_each`/`after_each` hooks or its state-block defaults, which
run at entry, before any body `let` has executed — reading a body `let`
from either is an unresolved name, not a runtime surprise. (An
ENCLOSING body's `let` is visible to both — the nested phase receives
the threaded context.) A transition predicate is stricter still: it may
read no `let` at all, enclosing or not. It is fired by whichever round
matches its event, and rounds both before and after any given `let` can
be in scope, so no lexical position makes a binding reliably live at
evaluation time — configuration reads state and the action, not body
bindings.

The indexed form `let base[p] = E` is a per-player map: the key binder
types as `Player` inside `E` only, and `base` as a collection of `E`'s
type, keyed by `Player`. Keyed collections — indexed lets and indexed
state variables — carry their key domain, and subscript reads and
indexed writes are checked against it (`n[hearts]` on a player-keyed
store is a compile error). A zone VALUE is likewise distinguished from
a computed card collection: a query result or list literal types
`Collection<Card>` too, but only a zone (or a binder holding one) may
stand in a movement endpoint or an epistemic target — narrowing a
movement is the `where` filter's job, not a laundered query's. An initializer the checker deliberately
leaves loose (`outcome`, an unregistered `action` field) carries that
looseness forward — ordinary gradual typing, with the runtime's typed
errors behind it. A `let` is a bound value, not a variable: it is not
assignable (see "Mutation semantics").

## Loop termination semantics

A `repeat until <pred>` clause on a phase (or `repeat until <pred>`
on a phase-body block) is **continuously evaluated**: the loop
terminates as soon as the predicate becomes true, including
mid-iteration. When the loop terminates mid-iteration, every nested
phase, mechanic instance, and inner loop that was active is
abandoned in turn.

This matches standard activation-record semantics — when an outer
scope exits, every inner scope exits with it — and means most games
get mid-phase termination for free. Cribbage is the canonical case: a
peg-out can occur mid-hand, during pegging or during the show, and the
game stops the instant either score reaches 121 — expressed by an
`if game_over() { skip to next hand }` guard at each scoring point,
which unwinds the active pegging loop and show statements to the
enclosing `phase hand_sequence repeat until (any player where score[player]
>= 121)`, whose predicate then ends the game at the hand boundary.

Games where the termination predicate can change only at iteration
boundaries (Hearts: scoring is end-of-hand only) get the same
semantics; the continuous-evaluation rule degenerates to
"checked at iteration boundary" because that's the only time the
predicate could flip.

A `round`'s optional `early` predicate does provide *trick-level*
termination on game-state-free conditions (Getaway's tochoo ends the
trick the moment a void player plays off-suit). It is not for
game-ending; game-ending is the `repeat until` clause's job.

## Game length as a declared contract

Every game declares `max_length: <n>` — a positive integer bound on
decision/loop iterations. It replaces what used to be two disconnected
magic constants (a hardcoded 10,000-iteration runtime safety cap and the
OpenSpiel adapter's invented `max_game_length=40000`) with one number the
game's author reasons about and the checker enforces.

The same declared value is enforced three ways, against two different
units, because no single check covers every non-termination shape:

- **The decision counter** — the one the corpus's declared values are
  actually sized against (250-seed measured random-playout lengths).
  Every chooser pick, of any kind, increments a single per-game counter
  (`RuntimeState.decisions_made`, wrapped around the chooser once in
  `play_game`); exceeding `max_length` raises a `RuntimeError` naming the
  count reached and the declared bound. This is the only one of the three
  that a structurally-terminating loop making unboundedly many decisions
  per iteration cannot evade — a loop that completes in very few
  iterations, each making many picks, would sail past either loop guard
  below while still making far more decisions than the game's declared
  bound.
- **The runtime's two loop guards.** Both loop forms — the phase-level
  `repeat until` (`docs/model.md`) and the statement-level `repeat
  until` — separately count their own *iterations* and raise the same
  kind of `RuntimeError` once that count exceeds `max_length`. Counting
  iterations (typically hands, not individual actions) against the same
  number the decision counter uses makes these two guards deliberately
  far more generous than their own natural unit — they exist to catch the
  shape the decision counter cannot: a loop whose body makes few or zero
  decisions per iteration (e.g. `repeat until false {}`), which would
  otherwise spin forever without ever tripping the decision counter at
  all.
- **The OpenSpiel adapter's `max_game_length`.** `cardlang/openspiel/game.py`
  reads the declared value directly, rather than inventing a blanket
  number generous enough for the corpus's longest game (which used to
  make every other game's reported bound meaningless). Because the
  decision counter enforces the same bound on the same unit
  `max_game_length` is denominated in (decisions, i.e. actions), a
  registered game's real trajectory length cannot silently exceed what it
  advertises to OpenSpiel.

`max_length` is required, not defaulted: the resolver rejects a game with
no declaration, or with a non-positive one, as a diagnostic error before
anything runs. A silently-generous default would defeat the point — the
whole reason for this declaration is to make "how long can this game
legitimately run?" a question its author answers on purpose, not an
interpreter implementation detail. (The stress-test corpus's Palace/
Shithead — a real game whose random playouts legitimately run thousands
of turns — crashed on 10-15% of random seeds against the old blanket
10,000 cap, with nothing pointing the author at the actual cause; a
per-game declared bound converts that into a diagnostic the author can
act on.)

Corpus values are sized from measured random-playout lengths (250 seeds
per game), not guessed: a per-game number generous enough that ordinary
random play — including the long tail of multi-hand, score-race, and
elimination games — never approaches it, while still being far tighter
than one blanket constant sized for the corpus's longest game.

Static bounds derived from a game's own structure (e.g. card-conservation
arguments for trick-taking games) could tighten this further, checked
against the declared value; that is future work, not required by this
declaration.

## Loop lifecycle: `before_each` and `after_each`

A `repeat until` phase runs per-iteration setup and teardown through two
optional hooks, siblings of its `state` block and distinct from its
sub-phases:

- **`before_each { … }`** runs at the start of every iteration (after the
  termination predicate is checked, before the body sub-phases). It is where a
  hand is prepared — gather, shuffle, deal.
- **`after_each { … }`** runs at the end of every iteration that started,
  *including one the termination predicate abandons mid-body*. This is the
  guarantee a trailing sub-phase cannot give: under continuous evaluation
  ("Loop termination semantics" above) a loop can exit mid-iteration, and a
  "last sub-phase = cleanup" would be skipped — whereas `after_each` always
  runs (the test-framework `afterEach` semantic). Oh Hell, French Tarot, and
  Skat use `after_each` for end-of-hand teardown.

The loop's `state { }` initializes once and **persists** across iterations;
the hooks run **each** iteration. That separates per-game state from
per-iteration work. Phase-specific setup stays inside the phase as its first
statements (Hearts' `first_trick` sets its own leader); the hooks are only for
the per-iteration boundary. Finer per-phase hooks (`before <phase>`) are
deliberately *not* provided until a game requires them.

Hearts uses `before_each` to gather the previous hand's cards, shuffle, and
deal:

```
before_each {
  move all cards to deck
  shuffle deck
  deal 13 cards from deck to each hand
  rotate pass_direction through [left, right, across, hold]
}
```

`move all cards to deck` is a destination-only **gather** movement (no `from`):
it collects every card from all other zones into the named zone. A `Deck`-typed
zone is initialized at game start holding the deck's cards, so the first
`before_each` gather is a no-op and the deal is well-defined.

## Mutation semantics

**Only a declared state variable can be written.** `x := …`, `x += …`, and `rotate x
through […]` all write persistent state, and persistent state is the only thing they
can write. A write target is an ordinary name, resolved exactly like a name in any
other position — so "what may I write to?" is not a separate rule with its own
vocabulary, it is the ordinary answer to "what is this name?", filtered to one
kind. A binder (a `let`, a loop or query binder, a `move_type` or `procedure`
parameter), a zone, a deck value and a pronoun are all *values*, not variables:
readable, passable, not writable. A name that resolves to none of them is unresolved,
which makes the ordinary typo — `totaly_score := 1` — a compile error like any other
misspelling, rather than a runtime one.

That uniformity is the point, and it is worth saying why. A **read** resolves lexical
binders *before* state variables. If a write target were not resolved the same way,
a binder shadowing a state variable would make one name mean two things — a read of
`x` finding the binder while `x := 1` wrote the state variable, with nothing to
notice. Resolving the target makes that shape *impossible* rather than merely
detected: the target resolves to the binder, and a binder is not writable. (This is
one seam of a larger question about what a bare name may denote —
[open-questions/name-namespaces.md](open-questions/name-namespaces.md).)

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
statements. Batching encodes "these scores are independent of each
other"; sequencing encodes "these scores depend on what came
before, potentially including game termination."

**Event-driven sub-phase transitions are not a third mutation mode.**
Hearts' `transition_to: hearts_broken when play_to_trick where
action.card.suit is hearts` is *phase entry/exit* triggered by the
move-emitted event.
The implied state change (the `NoLeadingSuitUntilBroken(hearts)` rule
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
  `RHO_of(p)`, `opposite_of(p)`. Relational queries are function
  calls (and the `offset_by` operator), never dot chains — see the
  access discipline below.
- `Zone<Contents>` — a container parameterized by what it holds.
  Carries a per-observer visibility declaration (see "Knowledge,
  visibility, and the projection model"), ownership, and structural
  type (set, ordered, stack).
- Zone contents are read through the English query surface (see "The
  expression register"): `cards in … where`, `number of cards in …`,
  `any/all card(s) in … where`, `sum of … over cards in …`,
  `highest/lowest … over cards in … or <default>`, and the emptiness
  checks `is empty` / `is not empty`. Resource queries are unbuilt
  ([roadmap.md](roadmap.md)).
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

**Optional types and the `none` literal.** A type written `T?` is optional: it
holds a `T` or the absence value `none`. `none` is the language's single
absence literal, used by every optional (`leader : Player? = none`, `contract :
Contract? = none`, `state.led_suit is none`) — it is not a member of any enum.
Where a game needs a value that reads like "nothing happens" but is a real
domain choice — Hearts' no-pass hand — it gets its *own* enum value
(`Direction = {left, right, across, hold}`), never `none`. This keeps `none`
unambiguously "no value": a `Player` that is `none` is unset, not the string
`"none"`.

`true` and `false` are the two boolean literals, the values a `Boolean` field
takes (`eliminated[player] : Boolean = false`, `eliminated[p] := true`). Like
`none`, they are language literals rather than enum members, so a game never
declares them.

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

- `state.foo` → `foo` (just a disambiguating prefix)
- `card.tapped` → `card.attributes[tapped]`

Sugar is documented; the underlying form is what the compiler
manipulates.

**Access discipline.** The bracket form is the only indexed
access: `hand[player]`, `captured[team_of(outcome)]`,
`hand[player offset_by pass_direction]`, `score[team]`. The dot
form is **object-member access and nothing else** — fields of a
`Card` (`card.suit`, `card.rank`, attribute sugar), fields of a
`Move` (`action.card`), and declared or derived fields of
user-defined structs (`result.made`). A dot whose receiver is a
player, team, integer, or boolean is a static error pointing at
the bracket form — including receivers rooted at loop, quantifier,
player-query, and comprehension binders, which the checker types
by their roles (a `for each player p` / `any player p` binder is a
`Player`, a `for each team t` binder a `Team`, a comprehension
binder its source's element type). The one receiver the checker
still cannot type is a lambda parameter (a lambda's element type
belongs to its receiver, which the checker does not model); there
the runtime fails loud rather than guessing. Relational
chains stay out of subject position: the corpus derives them with
`offset_by`, functions, and player-indexed public state. The
predicted forcing case — Doppelkopf's Fox/Charlie scoring, which
the rulebook phrases as "the partner of the ♦A's player, relative
to the trick winner's side" — flattened to equalities over
player-indexed public state
([games/doppelkopf.cardlang](games/doppelkopf.cardlang)) rather
than needing `dealer.left.partner.hand`-style chains, so no
complex-receiver dot form exists. Koenigrufen's runtime-chosen
called king is the named reopener if a future game's relational
subject resists this flattening.

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
small-core/rich-library split that makes the trick a `round` configuration
rather than syntax ([principles.md](principles.md)).

**Movement** — relocating items between two places. One primitive underlies
every movement verb: `deal`, `transfer`, `move`, `burn`, `muck`, and `draw`
are sugar that differ only in defaults, not in kind. A movement carries a
selection (`all`, a count, or a `chosen`/`random` amount), an item noun, a
source place, and a destination (a single zone or `to each` recipient). The
item noun is `cards`/`card` today; the noun stays open in the grammar so a
resource transfer (coins, chips) can one day be the *same* construct as a
card deal rather than separate syntax — but resource movements and the
grammar's per-movement `visibility =` override are deferred surface, rejected
by the checker ([roadmap.md](roadmap.md)) rather than left for the runtime to
silently ignore.

A `to each` deal distributes the stated amount to every recipient. When the
amount is `all` and the deck does not divide evenly, `as-equally-as-possible`
deals it round-robin so the remainder is spread across the first recipients —
Getaway deals the whole deck across 3–8 hands this way (`deal all cards from
deck as-equally-as-possible to each hand`).

The checker enforces the production's valid combinations ("Surface totality"
below): `as-equally-as-possible` requires an `all` deal `to each` with no
selection mode (it distributes the whole source — or the whole `where` pool —
round-robin); `deal all … to each` *without* it is rejected as a trap (the
first recipient would drain the source); a gather (`move all cards to
<zone>`, no `from`) collects everything into a single zone — counted,
selected, or `to each` gathers are rejected; and the `in <zone>` form is
deferred ([roadmap.md](roadmap.md)).

**Movement `where` filter.** The `from` form of a movement (any destination
shape) takes an optional `where <lambda>` clause, narrowing the *source pool*
to the cards matching the predicate — in source order — before the selection
draws from it: `move chosen 6 cards from hand[p] where is_pref_discard(card)
to discard[p]`. The four selection modes read the narrowed pool exactly as
they would read the whole source: `chosen`/`random` draw `count` from the pool
via the chooser/RNG; the default (dealt) form takes the pool's first `count` —
first *match* in source order, not top-of-source, since non-matching cards
were already skipped; `all` takes every matching card and leaves the rest
untouched in the source. Requesting more than the pool holds fails loudly,
identically to the unfiltered form. The destination forms compose: a filtered
`to each` deal narrows each recipient's pool in turn, and a filtered
`as-equally-as-possible` deal distributes the whole matching pool round-robin,
leaving non-matching cards in the source. An unfiltered movement is
unaffected — the filter is a genuinely separate code path
(`execute.py::_select_filtered`), not a generalization of the unfiltered one,
so no existing game's card-selection behaviour changed when this clause was
added.

French Tarot's chien discard is the corpus's first use: the taker's kept
chien cards must exclude every bout while preferring plain non-King cards
when six exist (`cards in hand where is_pref_discard(card)`, falling back to
`cards in hand where not is_bout(card)` when fewer than six such cards remain) — a
per-card predicate over which cards a decision may even draw from, distinct
from the *count* a plain `chosen N cards` movement already expressed.

**Epistemic** — changing knowledge or order without relocating anything:
`reveal`, `peek`, `hide`, `announce`, `expose_top`, `forget`, `shuffle`. A
closed family; each is a prose statement (`shuffle deck`, `reveal proof to
all`) normalized to one IR node and resolved against a signature table
([library.md](library.md) "Operations"). Their effect is defined in the
projection vocabulary of "Knowledge, visibility, and the projection model"
below.

**State-cycle** — advancing a state variable through a list of values, e.g.
`rotate pass_direction through [left, right, across, hold]`. Orthogonal to
the other two (it touches no zone): a single small construct.

**Surface: actions are prose, queries are calls.** Every operation above is a
prose statement — the built-in vocabulary reads as rulebook commands, one
surface for "what the game does." Call syntax (`player_holding(2 of clubs)`,
`rank_value(card)`) is reserved for value-returning functions and named
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

## The expression register

The expression layer speaks the same English register as the statement layer:
queries and predicates are rulebook sentences, and their binders are
implicit. There is no method register (`zone.method(…)`) and no lambda
syntax; a query names its domain noun and binds the corresponding pronoun per
candidate — `player` in the player queries, `card` in the card queries,
`team`/`suit`/`rank` in the quantifiers. One spelling per concept governs
every form here ([principles.md](principles.md)).

**The word/symbol line.** Words spell logic, equality, membership, and
quantification: `is`, `is not`, `in`, `not`, `and`, `or`, `any`, `all`,
`number of … where`. Symbols spell arithmetic, ordering, and state change:
`+` `-` `*`, `<` `<=` `>` `>=`, `:=` `+=` `-=`. This is one sentence a
designer can internalize — and it is Python's line, so the surface stays
familiar. English forms for assignment were considered and rejected: the
symbols carry no confusion cost, there is no compact English word for `>=`,
and the per-line verbosity cost would be the largest in the language. `is`,
`not`, and `number` are reserved words — no state variable, zone, function,
or binder may take one of these names.

**Equality is `is` / `is not`** — plain equality, with no identity/equality
split to trip over. `a is not b` is a single operator, never `a is (not b)`.
The right-hand keywords `none` and `empty` are a closed set dispatching to
the absence and emptiness checks (`led_suit is none`, `hand[p] is not
empty`); every other operand is ordinary equality. `==`/`!=` are not part of
the language; the checker rejects them with the replacement spelling.

**Card queries** mirror the player queries ("Player-collection queries"
below), binding `card` per candidate over a named zone:

- `cards in <zone> where <pred>` — the matching cards;
- `number of cards in <zone> [where <pred>]` — how many match (bare: the
  zone's size);
- `any card in <zone> where <pred>` / `all cards in <zone> where <pred>`.

**Aggregations** name their operation and bind `card` implicitly:

- `sum of <expr> over cards in <zone> [where <pred>]`;
- `highest <expr> over cards in <zone> [where <pred>] or <default>` and
  `lowest …` — the empty-set default is mandatory (the `or` clause), so an
  emptied zone yields the declared value instead of a crash; the default
  sits below `or`-precedence (parenthesize a compound default).

**Quantifiers bind their role noun implicitly**: `any player where <pred>`,
`all players where <pred>`, and the `team`/`suit`/`rank` forms (`any suit
where …` ranges over the deck's suits; `any rank where …` over the declared
`ranking:`, else the deck's ranks). The iteration-role set is closed
(player/team/suit/rank); card quantification is the card-query form above.
`for each <role> <binder>:` keeps its explicit binder — it is a statement
loop, not a predicate, and its binder is genuinely chosen (`for each player
p:`).

**Membership is `in`**: `Q of spades in captured[p]` (zone membership),
`card.suit in [hearts, spades]` (a `[…]` list literal, never empty). The
grammar owns `in`'s three uses — range (`choose integer in 0 .. 13`), query
source (`cards in hand`), and membership — explicitly.

**Rank and suit values.** Suits and name-form ranks are bare enum values
(`card.suit is hearts`, `card.rank is K`, `card.rank is Duke`); the rank
namespace comes from the deck, not `ranking:` (Coup and Tarot declare no
ranking). Numeric ranks spell as validated strings (`card.rank is "10"`) —
a bare `10` is an Integer literal — and the checker rejects every
silently-false comparison shape: Rank vs Integer, a name-form rank written
as a string, a string outside the deck's rank set, and cross-enum
comparisons.

**Movement and reveal filters** are ordinary predicates with `card` bound
per candidate (`move chosen 6 cards from hand[p] where is_pref_discard(card)
to …`), the same `where` the card queries use.

**`repeat until` is the one iteration lexeme**, as a statement and as the
phase qualifier (`phase hand_sequence repeat until …`) — one lexeme is worth
more than the third-person `s`.

The rulings here were produced by the corpus-wide register analysis in
[design-notes/lexical-cleanup.md](design-notes/lexical-cleanup.md), which
records the rejected alternatives (explicit binders, the `count`/`max`/`min`
comprehension spellings, noun sugar for counting) and the evidence.

## Named functions

A game factors an expression it would otherwise repeat with a **named function** —
a parameterized expression callable wherever an expression appears:

```
function <name>(<param> : <type>, …) = <expr>
```

declared at the top level alongside the `move_type`s. A call `<name>(<arg>, …)`
evaluates the body with the parameters bound to the arguments. Seven-Card Stud's
betting ring uses three: `can_act(p)` (not folded, still holds chips), `owes(p)`
(still owes the standing bet), and `pending(p) = can_act(p) and (not acted[p] or
owes(p))` (the ring/termination predicate). The `over` filter and the `until`
terminator both name `pending(player)`, so they cannot drift out of step — a
correctness property, not only brevity.

The body is **hermetic**: it reads only its parameters and game/phase state (read
at call time), never the caller's local binders or call-site `actor` / `action` /
`outcome`. A function that needs a player takes it as a parameter. It is
**non-recursive** — the call graph must be acyclic. Both are enforced at compile
time, with the ordinary checks: a call to an unknown function, a wrong argument
count or type, a body name that is neither a parameter nor a binding the body
itself introduces (`number of players where …`), and a call cycle are each a loud
error. The body's type is inferred — a function whose body is a `Player` used
where a `Boolean` is expected is caught at the call site — and a function may call
another (`pending` calls `can_act` and `owes`).

This is a deliberate, authorized general construct: factoring predicates is a need
the corpus has as games grow more advanced, not a Stud-only convenience. It
resolves the *named-predicate* half of
[open-questions/round-config-factoring.md](open-questions/round-config-factoring.md);
the *street-loop* half (folding a repeated parameterized `round` block into one
loop) remains open.

## Named procedures

A game factors a *statement sequence* it would otherwise repeat with a **named
procedure** — the statement layer's sibling of the named function above:

```
procedure <name>(<param> : <type>, …) { <statement>* }
```

declared at the top level, and invoked as a statement: `run <name>(<arg>, …)`.
A keyword leads the invocation, because the statement layer has no
expression-statement form and that absence is worth keeping — statement-hood
stays visible.

Reuse is a **splice**: the expander replaces each `run` with the procedure's body
and consumes the procedure, so no `run` and no `procedure` survives the front end.
This is what makes the construct safe against the invariant that governs everything
here — *the observation events a procedure contributes, and therefore the
information sets derived from them, are exactly what the written text emits*,
because a procedure does not exist at the layer where observations are emitted. It
is the opposite of the retired `instantiate` escape hatch, which injected Python
the kernel could not see; a procedure injects only DSL the kernel already
interprets. Coup is the forcing case: three blocks pasted 29 times, most of a
521-line file, now written once.

A `run f(a, b)` becomes one block:

```
block {
  let @f.p = a            // each argument evaluated ONCE, in the caller's context
  let @f.q = b
  <the body, reading @f.p and @f.q>
}
```

The block is a real construct in the tree, not an `if true { … }` standing in for
one, and the difference is not cosmetic: an `if` tells every downstream pass that
the body *may be skipped*. The deck-capacity gate believed it — it carries the worst
case across a conditional — so a procedure that refilled the deck failed to reset the
gate's running total, and the very same program was accepted written inline and
rejected written as a `run`. That is precisely the property a procedure exists to
guarantee, so the tree has to say what is true. (The statement layer has no block
form and needs none: nothing but expansion creates one.)

Two properties, and each is load-bearing rather than cosmetic:

**Arguments are evaluated once, by value, before the body runs.** A by-name splice
— copying the argument *expression* to every place the body reads its parameter —
is silently wrong in three ways, and all three are reachable. `run
bump(choose integer in 0 .. 1)` is ONE decision in the written text; by name it
becomes one decision *per read*, polled independently, so two reads can get two
different answers and credit two different players. A parameter read zero times
drops the argument, and its decision, entirely. And an argument naming state the
body then assigns denotes a different value on its second read than its first. The
first of those changes the game's *decision count* relative to what the designer
wrote, which is exactly the thing the OpenSpiel target cannot tolerate. Binding
each argument up front makes a call read the way it looks.

**The body's bindings scope to the body.** That is what the block is for. State
assignments and card movements persist, of course — a procedure acts on the game.
Only its `let`s are local, which is the whole difference between a procedure and a
paste: without it, a body that binds `target` would silently capture a caller's own
`target`, read *after* the `run` site.

Together these mean the caller cannot corrupt the body and the body cannot corrupt
the caller, *by construction* — so there is no capture wall to remember, and none
to get wrong. One wall does remain, because expansion cannot fix it: a body binder
sharing a **parameter's name** is ambiguous at classification time (both are local
binders), so substitution cannot tell them apart. That is rejected.

Expansion runs **after typecheck**, not beside rule-template instantiation in
resolve. That is forced by the parameter types: they can only bite while the `run`
site still exists to check its arguments against, and expanding earlier would leave
them parsed and ignored — the accepted-but-ignored class.

The body is **hermetic**, in the same sense a function body is: it reads only its
parameters, the binders it introduces, and game/phase state — never the caller's
locals, and never the call-site pronouns `actor` / `action` / `outcome`, so its
meaning cannot depend on where it is run from. A procedure that needs the actor
takes it as a parameter, and because arguments are evaluated in the caller's
context, `run lose_influence(actor)` passes the *move's* actor even into a body
that rebinds the acting player. Coup depends on that at four sites.

Parameter domains are a closed set — `Player`, `Rank`, `Rank?` — and any other
domain is rejected. A procedure may not run another procedure, hold a `round`
(which binds its own `outcome`), or contain non-local control flow (`produce`,
`continue to`, `skip to next hand`), and one that is never run is an error, since
its body would be spliced nowhere and checked by nothing. Every one of those is a
loud wall with a recorded deferral ([roadmap.md](roadmap.md)); none is silently
accepted.

## Knowledge, visibility, and the projection model

Knowledge over zone contents is the primitive concept for everything
the language models about information asymmetry. Cards and resources
both live in zones; visibility is a per-observer projection
assignment rather than a binary hidden/public flag.

### Hidden information lives only in zones; state is public

The projection vocabulary below applies to **zones and nothing else**.
Every `state` variable — game-, phase-, and loop-level, scalar or
player-indexed — is public to every observer, always. There is no
observer-dependent scalar state and no way to declare any.

This is a deliberate boundary, not a missing feature. It is what makes
information sets derivable: an observer's knowledge is exactly (their
zone projections) + (the public state and public move history), so the
information-state encoding never has to ask *which* variables an
observer may read. It also gives claim-versus-content games their
natural encoding for free — a public assertion (a claimed rank, a named
bid meaning, a running count) is a state variable *because* it is
public, while the concealed truth it may misrepresent sits in a
face-down zone whose projection hides it.

The corollary is a modeling rule: **anything an observer must not know
is contents, not state.** A hidden scalar (a secret counter, a sealed
simultaneous bid) is encoded as tokens or cards in a zone whose
projection conceals them — `count_only` if the *amount* is the secret's
public residue, `trivial` if even that leaks. If a future game's rules
genuinely require a hidden scalar that resists token encoding, that is
a challenge to this decision and goes through
[open-questions/knowledge-events.md](open-questions/knowledge-events.md)'s
adjacent territory rather than around it.

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

### Higher-order knowledge is out of scope

The knowledge model is first-order: an observer's candidate set ranges
over zone contents (what *is* the case), with the de re / de dicto
refinement above. It does **not** model higher-order knowledge — "P knows
that Q knows X" — because no card game's *rules* read it. A survey of the
usual suspects confirms this. Hanabi's rules constrain hints to truthful,
complete facts about tile colours and values and never reference what a
player knows about another's knowledge; its famous higher-order reasoning
(finesses, conventions) is optional play layered on top, explicitly
outside the rules. Sheepshead's called partner is genuine *first-order*
private information — the partner's identity is known only to the partner
— with no rule reading knowledge-of-knowledge. The pattern generalizes:
rulebooks route every legality, resolution, and scoring condition through
observable card facts (and at most one layer of hidden state) precisely so
a referee can adjudicate them. Higher-order reasoning is real in optimal
*play* — Hanabi conventions, bluff modelling in Coup and bridge — but it
lives in strategy, not in the rules the DSL describes, and the candidate
sets the language already tracks are exactly what CFR / IS-MCTS consume.
Modelling belief-about-belief would add machinery no in-scope game
exercises. If a game ever surfaces a rule that reads second-order
knowledge, this is the decision to revisit.

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

Ahead of a true compilation pass, a **runtime adapter** already validates that
the IR/runtime *can* drive OpenSpiel: Hearts is registered as a `pyspiel.Game`
and passes OpenSpiel's own consistency tester with leak-free, perfect-recall
information states. It works by re-simulation — the OpenSpiel state is
`(seed, action history)`, and every query replays the game through the runtime's
`chooser` seam, which suspends at the next decision via a `ChooserAbort`
protocol. This makes the state trivially cloneable (the property OpenSpiel
exercises most) and confirms the finite-action-space anchor end to end. The
adapter is per-game and proof-scoped; the general, all-corpus path remains the
eventual compilation pass (see [roadmap.md](roadmap.md)).

Info-set derivation is uniform across the corpus: every game's decisions run
on kernel sites that emit observation events, no Python mechanic exists (the
`instantiate` construct is deleted), and the readiness proofs cover
every corpus game ([kernel-migration.md](kernel-migration.md)). The remaining
honesty line is scope, not derivation: no rules-level randomness remains —
every monolith-era rng gate (Coup's windows, claims, and targets; Tichu's
call windows and Dragon routing) is a real announced decision in the
observation stream. What stays reduced is named per game in its file
(Tichu's Mahjong wish and bomb variants, and the like), as scope, not as
hidden randomness.

## Game result: `winner:` and `loser:`

A game declares its terminal result with exactly one top-level clause,
evaluated against the final state when the phase tree finishes:

```
winner: lowest cumulative_score      // Hearts — rank a score variable
loser:  the player where hand[player] is not empty   // Getaway — select directly
```

The two forms reflect two shapes of game. A *scored* game accumulates a
numeric variable and the result is whoever ranks first by it, so
`winner: <lowest|highest> <score-var>` names the rank direction and the
variable. An *elimination* game has no score: players drop out until one
remains, and that survivor is named directly, so `loser: <selection>`
takes a player-valued expression (typically the singular player-selection
`the player where <pred>`) evaluated at game end.

`loser:` reads zone state (`hand[player]` non-empty), not phase-scoped
variables, so it resolves at the top level after the elimination phase
has exited. The runtime returns the selected player as the result; a
`winner:` game additionally carries its final scores, a `loser:` game
does not (it has none).

A game declares one or the other, never both. `winner:` is not sugar for
`loser:` of the complement: an elimination game may end with several
non-losers whom the rules never rank, so there is no single winner to
name.

## Player-collection queries

Three expression forms query the player ring by a predicate:

```
players where <pred>              // the set of matching players
the player where <pred>           // the unique matching player (errors if not exactly one)
number of players where <pred>    // how many match
```

The predicate is evaluated once per player with `player` bound to the
candidate, so it reads like the per-player indexing used everywhere else:
`players where not eliminated[player]`, `the player where hand[player] is
not empty`, `number of players where hand[player] is not empty`. The
binder is the fixed name `player` (the canonical seating role), not a
user-chosen variable — these are filters over a single known ring, not
general comprehensions, so there is nothing to name.

Like the quantifiers (`any player where …`) and aggregations (`sum of … over
… as …`) forms, a player query sits at the top of the expression grammar:
its `where <pred>` body extends as far right as possible, giving one
canonical parse. To compare a count, parenthesize it: `(number of players
where not eliminated[player]) > 1`.

`the player where <pred>` is the singular selection a `loser:` clause
uses; it is an error at runtime for the predicate to match zero or
several players, since it names exactly one.

`is not empty` is the negation of `is empty` (a zone predicate), paired
for elimination games that select the player who *still* holds cards.

## Scoring composition

> **Status: designed, not yet built.** No game runs this subsystem — the runtime
> has no `apply_components:` construct, and `ScoreDelta`/`triggered_by:` are not
> implemented. It is the intended shape for composed scoring; the corpus scores
> through game-local statements and stdlib primitives today (Bridge and Spades
> inline; Pinochle's `pinochle_meld_value`, Tarot's `tarot_per_opp`, Cribbage's
> pegging/show primitives). The components named here and in the sibling sections
> are the proposed decomposition, promoted corpus-first when the subsystem lands.

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
helpers.** Hearts scores `if card.suit is hearts then 1 elif
card is Q of spades then 13 else 0` inline; Pinochle scores
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

> Part of the `scoring_component` subsystem — designed, not yet built (see
> "Scoring composition" above).

Some scoring fires in response to a specific event rather than as
part of an `apply_components:` batch. Bridge's GameBonus fires when
a partnership's below-the-line score crosses 100; RubberBonus fires
when `games_won` reaches 2; Spades' bag-overflow fires when
`bags >= 10`. These
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
- State equality: `running_total is 31 after the play`.
- Derived properties: `play_pile.suffix_same_rank_count >= 2`.

Triggered components are independent of `apply_components:`. They
are declared in the same `scoring_component` namespace and use the
same `ScoreDelta` machinery. A game's scoring is the union of its
batched components and its triggered components; both contribute
to the same accumulated score.

When a triggered component would cause a game-ending threshold
(Cribbage's 121, or any termination predicate), the `repeat until`
clause on the enclosing loop fires immediately upon the
triggered-component delta being applied. See "Loop termination
semantics" above.

**Corpus usage.** The corpus presently has three triggered
components across two games — Bridge (GameBonus, RubberBonus) and
Spades (BagOverflow). All fit the shape above.

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
if result.tricks_won[p] is result.bid[p]:         // exact
  delta[p] += 10
```

```
// Pinochle (inline):
if bidder_team_total >= current_bid:              // total-points threshold
  score[bidder_team] += bidder_team_total
```

The shared *bidding mechanic* possibilities — an ascending-bid `auction`
definition, an inline per-player pattern — are extracted only when
multiple games clearly share them. Bridge's auction (doubling, redoubling, and
the structured contract outcome) runs on the auction form of the kernel `round`
(see "The auction form of `round`" above), game-local until the shared `auction`
definition is promoted corpus-first.
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
  if actor is declarer.partner and dummy_revealed:
    dummy_hand[actor]
  else:
    private_hand[actor]

chooser_for(actor) =                    // who decides what move it is
  if actor is declarer.partner and dummy_revealed:
    declarer
  else:
    actor
```

The intended mechanism: a choice-prompting kernel construct (`round` /
`offer`) consults an optional `chooser_for` helper that defaults to the
identity function (actor chooses for themselves), and Bridge supplies its
game-defined helper. This is a planned kernel hook — not yet wired, since no
formalized game models delegated play today (`round` currently always lets the
actor choose). It is recorded here as the design, not a built capability.

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

**The iteration form's body is one chosen movement.** That is not an
implementation limit dressed up as a rule — it falls out of the pre-block read
semantics below. The form must snapshot *every* player's selection against the
state as it was at block entry, and only then apply them all; that is what makes
the pass atomic, and it is why nobody sees a passed card before choosing their
own. A snapshot is only defined for a chosen movement out of a zone, so anything
else in that slot — an assignment, a plain (unchosen) movement, a block — is
rejected. The runtime has always required this; the checker now says so, instead
of letting it through to a crash.

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
phase passing when pass_direction is not hold {
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
  agreed(t) {
    simultaneously: {
      transfer t.alice_gives from hand[alice] to hand[bob]
      transfer t.bob_gives   from hand[bob]   to hand[alice]
    }
  }
  declined {
    // no transfer; play continues
  }
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
action is blocked or proceeds). That is a sequenced-response shape,
not the atomic-effect block: serializing responders in priority order is
faithful, because a response reacts to what is already on the table. No
`simultaneously:` block appears in Coup, and none of the
unforced body-grammar extensions below (in-block `if`, nested blocks)
is needed — the forcing function confirmed the split rather than
reopening it. (The encoding sequences real `challenge`/`allow` decisions
clockwise from the claimant — a `repeat until` pointer walk with one
`offer` per responder, first challenge closing the window,
[games/coup.cardlang](games/coup.cardlang) — and the blocker's claimed
character is folded into the block window's vocabulary, so the bluff is
itself the offered decision.)

**Body grammar.** The body admits:

- **Moves** ([library.md](library.md), "Move types") and
  **memory operations** ([library.md](library.md), "Memory
  operations") — the primary contents.
- **`choose` expressions** inside move arguments — player
  decisions feeding move parameters. Standard expression form
  ([decisions.md](decisions.md), "`choose` as expression").
- **`for each` iteration over fixed collections** — the shape a
  "each player passes one card to each other player" push would
  take inside the block. The iteration must be over a value known
  at block entry (the player set, a fixed list); it cannot
  iterate over a collection whose membership is determined by
  in-block choices, since reads see pre-block state. (Tichu's
  push in fact needs no `simultaneously:` block at all: each
  player's three picks land in a per-player `gift` pile and are
  distributed only after every pick, so plain sequential chosen
  movements are simultaneous by construction —
  [games/tichu.cardlang](games/tichu.cardlang).)
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
[mutation semantics](#mutation-semantics); the block is one
indivisible step in that sequence.

**OpenSpiel compilation.** The block compiles to a single
information-state transition per observer. Each observer
receives one projection-shaped event recording the net effect
of the block's moves at that observer's visibility level —
exactly the same shape as single-move events, just with multiple
moves coalesced. Perfect-recall guarantees and CFR / IS-MCTS
applicability are preserved.

## Off-the-clock windows

Some rules offer a move "at any time" rather than on a turn: Tichu's
tichu call (any time before the caller's first play), Doppelkopf's
Re/Kontra and level announcements (any time during the play, gated by
the announcer's own hand size). The language expresses these as a
**quiescence-lap poll** — an idiom over the existing kernel, not a
construct:

```
if <public window gate> {
  quiet := 0
  round offering [<window moves>, decline] from <player about to act>
        over all players until quiet >= <player count>
}
```

placed before each decision the enclosing phase offers. Every window
move's effect resets the `quiet` counter; the decline increments it; a
full silent lap closes the poll. An announcement re-opens the lap, so
chains of reactions (Re → no 90 → Kontra) resolve at a single poll
point in any order the players choose.

Three properties make the serialization faithful and leak-free:

- **The gate reads public state only** (hand counts through their
  `count_only` projections, announcement flags), so observers can
  compute exactly when polls are skipped — a closed window emits
  nothing and reveals nothing.
- **Private eligibility lives in the move guards.** A player whose
  guards all fail is offered only the decline and submits the same
  public decline event a player declining by choice submits, so
  ineligibility is indistinguishable from silence — the projection of
  "hasn't announced yet" that real play gives.
- **A participant's own thresholds change only when the participant
  acts** (hand sizes decrement on the owner's plays), so polling before
  each decision offers every window move at exactly the hand sizes the
  paper rules allow; no legal timing is lost to the serialization.

The poll's decisions are ordinary `offer`-shaped kernel decisions
emitting ordinary public announce events — no new observation kind, no
change to how information states derive.

Rejected alternatives: a dedicated `may submit X` phase verb (deferred
per corpus-first promotion — Tichu and Doppelkopf are two witnesses,
and constructs are earned at the third instance, e.g. Belote's
mid-trick declarations); an `optional: true` move-type property
(optionality belongs to the offer site, not the move); a state write
outside the move framework (removes the decision from the observation
stream, breaking derived information sets).

Witnesses: Doppelkopf's announcement ladder at full fidelity
([games/doppelkopf.cardlang](games/doppelkopf.cardlang)); Tichu's call
windows (the WS5 upgrade,
[kernel-migration.md](kernel-migration.md)).

## Interactive decisions: a kernel and an in-DSL standard library

The structure of a game (zones, phases, dealing), trick-taking, and scoring are
directly expressible. The part that resists expression is **interactive decision
logic** — heterogeneous action choice, auctions, betting, challenge/block
windows, combination climbing. These are factored into one semantic primitive
and a small surface, with the richer vocabulary built *in the language* rather
than baked into the engine.

**One primitive: the decision node.** A participant chooses one action from a set
that is *finitely enumerable from current state*, over a move-type vocabulary
fixed at game-definition time; the action has an effect and may yield a typed
outcome. Plus chance nodes for shuffles/deals. Everything below lowers to this.

**Two surface constructs.**

- `offer` — a single decision: an acting player chooses one of a set of
  `move_type`s (each a guard plus an effect), and the chosen move's effect runs
  with `actor` bound to that player.
- `round` — a sequence of decisions over participants, varying only along a
  *closed* set of axes: participants (actor / others / ring / list), order
  (turn-from a seat / priority / simultaneous), an accumulator threaded across
  steps, a termination predicate, and a typed outcome. Auctions, betting,
  climbing, response windows, and the trick are all `round` configurations.

**Richer vocabulary is a standard library written in the DSL, not engine
presets.** `challenge`, `block`, `auction`, `climb`, and `trick` are *definitions*
composed from `offer`/`round` and the effect verbs — readable in the game's own
terms rather than hidden behind keywords. The governing rule: **a definition adds
words, not semantics.** It may name and compose over the fixed kernel (a typed
function: parameters in, typed outcome out, a body that lowers to decision/chance
nodes); it may not introduce new control primitives, reflection, or runtime
rule-mutation. This is the line between a game that *defines* "challenge" (Coup)
and one that mutates its own rules at runtime (Mao), the latter being out of
scope (below).

**Discipline.** Variation lives in *values* along the closed axes (a new bid
step, a different threshold) — never in new constructs. A new *axis* is a major
change requiring sign-off. A definition is promoted from game-local to the shared
DSL standard library only once roughly three corpus games exhibit the same shape
(corpus-first; abstract at the third instance, not the first).

**Anchored to a finite action space.** The "finitely enumerable from current
state, fixed vocabulary" requirement is inherited from the target runtime
(OpenSpiel mandates a finite, enumerable action space), not chosen for
convenience. It is the load-bearing invariant of the whole approach, and it puts
games needing a *runtime-extensible* action vocabulary or mutable rules (Mao,
Nomic, CCG card-text) out of scope by construction rather than by preference.

The full design — the kernel/standard-library split, the closed axes, the
promotion rule, and the worked Coup example — is in
[../superpowers/specs/2026-06-06-interaction-decision-sublanguage-design.md](../superpowers/specs/2026-06-06-interaction-decision-sublanguage-design.md).
The kernel's atom (`offer`, parameterized `move_type` definitions, the `actor`
pronoun) and the `round` construct are built. Every trick game (Hearts, Spades,
Getaway, Bridge, Oh Hell) plays on the trick form of the kernel `round`, the
built-in `Trick` mechanic has been retired, and `round` carries the termination
axis (an `early` predicate — Getaway's tochoo) plus round-state exposure. The
**auction form** is built too (see "The auction form of `round`"): a continuous
ring over a heterogeneous move vocabulary, with the accumulator as phase state, a
termination predicate, and a typed outcome over the bid history — Bridge's,
Pinochle's, and Tarot's auctions run on it (Tarot as a counterclockwise
single-pass ring, the ring honouring the game's `direction`), Stud's betting
runs its `priority` order, and Skat's Reizen call-and-response runs as a
role-guarded two-participant ring (see the call-and-response bullet under "The
auction form of `round`"). The
participant-filter axis is built — the ring is re-evaluated each turn, so it
shrinks as players drop out (Pinochle's passed bidders and standing high bidder,
Tarot's seats dropping after one bid). The remaining work (the challenge /
block vocabulary; promoting the shared `auction` definition
at its third instance) is the in-flight build (see [roadmap.md](roadmap.md) and
[kernel-migration.md](kernel-migration.md)).

## Surface totality

The corpus-first gate ([principles.md](principles.md), "Three implementations
before abstracting") governs *admission*: a construct or axis enters the
language only when games demonstrate the need. It does not license partial
implementation. Once a construct is admitted, its surface is **total** — every
composition the grammar accepts has an accounted outcome.

Concretely: when a construct is added or extended, enumerate its composition
points — the host production's other optional clauses, the selection modes, the
destination forms, and every executor branch that receives the node — and put
each cell in exactly one of three states:

1. **Implemented** — defined semantics, with a test.
2. **Statically rejected** — resolve/typecheck refuses the combination with a
   clear message, with a test asserting the rejection. The rejected combination
   is recorded in [roadmap.md](roadmap.md) so a future game can lift it when it
   needs the cell.
3. **Grammatically inexpressible** — the grammar itself cannot produce the
   combination.

The fourth state — parses, runs, and silently ignores the clause
("accepted-but-ignored") — is a defect, not deferred work. For the design-tool
goal it is the worst failure mode: a designer who writes a legal sentence must
get either the behavior or an error, never a silent misread. When a cell is not
worth implementing, prefer static rejection over a runtime error, and never
silence.

**An accounted outcome is not enough: the outcome must be the one the surface
plainly says.** A combination that parses to *defined but unintended*
semantics — an omitted mandatory clause silently reinterpreting an adjacent
token, a wrong-typed operand comparing as always-false — is the same defect
class as accepted-but-ignored, reached through a misread instead of a
silence. Totality is therefore checked adversarially as well as
enumeratively: every new or extended form ships with **misuse probes** — the
most plausible wrong sentences an author would write (omitted mandatory
clauses, retired spellings, wrong-typed operands in every predicate context,
out-of-scope or shadowed binders, boundary-token slips) — each proven to
produce a diagnostic, and pinned as rejection tests. Grammar work carries a
specific probe: wherever an optional clause shares a boundary token with a
mandatory one, the omitted-clause and doubled-token variants must fail to
parse or parse to the same meaning, never to a different one.

**Composition points enumerate at every consuming pass, and pairwise.** A
combination made inexpressible at the grammar layer can still reach a
semantic pass that treats all forms uniformly (a resolver loop over
references, a typechecker branch over operators, a runtime arm over value
shapes) — each pass has its own cell matrix. And a new construct's cells
compose with the *existing* constructs its values can meet: every value shape
the construct produces is enumerated against every operation that consumes
that shape. Per-construct enumeration alone misses the defects that live in
the products of constructs. The mechanized recipe for all of the above is the
`surface-totality-audit` skill (`.claude/skills/`), a mandatory gate beside
the regression checks (CLAUDE.md, "Verifying changes").

The movement production is the worked example of the matrix: the selection
modes (dealt / `chosen` / `random` / `all`), the destination forms (`to
<zone>`, `to each`, the round-robin `as-equally-as-possible to each` deal, the
gather), the `where` filter, the item noun, and the deferred clauses (the `in
<zone>` form, the `visibility =` override) compose into a grid in which every
cell is implemented (`tests/test_movement_filter_execute.py`) or statically
rejected (`tests/test_movement_combination_validity.py`) — see "The operation
vocabulary" for the enforced combinations.

## Closed-domain completeness

Surface totality's principle, applied below the grammar. The corpus-first
gate governs which *mechanisms* exist — a proof harness, a projection
emitter, an action encoder, an invariant — exactly as it governs which
constructs exist. It does not govern how completely a mechanism covers its
own domain. Once a mechanism exists, its completeness is measured against
the domain it quantifies over, never against the corpus: "every corpus game
passes" is a witness, not a definition of done, because the games exercise a
sliver of any semantic domain.

The operative distinction is **closed versus open**, not thorough versus
lazy:

- A **closed, enumerable domain** — the projection lattice, the observation
  event vocabulary, the sequence dimensions of a log (content, multiplicity,
  order, extension), both directions of a biconditional, the arms of a
  dispatch over a registry — is covered *exhaustively*, derived from the
  registry that defines it, pinned complete against that registry by a
  static test, and backstopped by a runtime refusal on anything left over.
  Hand-enumerating cases where a registry already defines the universe is
  the tell that this rule is being violated: find the registry, derive from
  it, refuse on the remainder. The worked example is the soundness matrix's
  probe table (`tests/openspiel_ready/partition.py`, `ZONE_PROBES`): the
  distinctions each projection level must show and must hide are a declared
  table, pinned complete against `ZONE_PROJECTIONS` at test time and
  enforced by a probe-time refusal, so a new emission rule cannot be
  silently under-probed.
- An **open design space** — which round axes exist, the meld model, the
  constructive world generator — stays corpus-first: generalizing from zero
  or one instance produces speculative abstractions, and waiting is cheap.
  But every deferral must be a **loud wall** (a static rejection or a
  runtime refusal, with a test), never a silent gap. Deferred-and-walled is
  corpus-first done right; deferred-and-silent is a defect.

**"Vacuously green" is a defect class of equal rank to
"accepted-but-ignored."** A check presented as a guarantee must be able to
fail: an assertion no input can reach, a perturbation that cannot alter the
observed value, a comparison that shares its code path with the thing it
checks, or coverage that quietly narrowed to nothing all read as proof
while proving nothing — the proof-layer analogue of a silently ignored
clause. A check cited as a guarantee states its quantifier (exhaustive over
what; sampled how); where it cannot cover its domain, it records the gap
(the coverage-record obligation in
[open-questions/structural-infoset-proofs.md](open-questions/structural-infoset-proofs.md))
rather than reading as if it did. The crime is never incompleteness; it is
*silent* incompleteness.

Acceptance for changes to rigor-critical machinery — anything the
information-set guarantees, the encodings, or the invariants rest on — is
therefore a stated completeness argument, not a green suite. The argument
has a fixed shape, the **completeness ledger**, shipped in the change itself
(the commit message, or the covering test module's docstring — somewhere a
reviewer sees without asking):

```
property:   <the guarantee, one line>
domain:     <what is quantified over>
registry:   <where that domain is defined in code>
covered:    <cells exhaustively handled, and by which layer>
sampled:    <cells covered by example only, and why that suffices>
residual:   <cells NOT covered — each with its wall and its roadmap.md line>
```

A residual row without both a wall and a record fails the gate; "no corpus
witness" is never by itself a reason to leave a residual cell silent, because
corpus-first governs which mechanisms exist, not how completely a mechanism
covers its own domain. A wall guards its whole class at the layer that owns
the class: an operand-compatibility rule lives in the type layer consulted by
every comparison-shaped context, not at the first site that motivated it.
The `surface-totality-audit` skill (`.claude/skills/`) operationalizes this
section and "Surface totality" as a pre-commit gate.

A wall must also speak its **layer's failure currency**: the compile
stages fail as diagnostics (`DiagnosticBag`, with a span and a
designer-readable message — a raw registry raise mid-resolve is loud in
the wrong currency and suppresses every other diagnostic in the file);
the runtime fails as typed exceptions; the proofs fail with a witness.
Loud-but-wrong-layer is a bug with the same rank as silent.

**A check lands only after naming its owner (write-time triage).** Two
tells at edit time mean information is being lost rather than defended:
*re-deriving* a fact an earlier pass already established (re-classifying
a name instead of reading the `ref_kind` the resolver stamped, re-inferring
a type the checker validated, re-computing visibility the zone-type table
declares), and *guarding* a condition that is already checked somewhere
else. Either tell stops the edit — the fix is upstream, not local. Before
it lands, the check is classified as exactly one of three things: a
**wall** (it moves to the layer that owns the class, in that layer's
currency, with a test), a **backstop** (it stays, and its comment names
the wall it shadows — and the recorded residual that makes it reachable,
if one exists), or a **missing wall** (the wall is built at the owning
layer, and the local site becomes a backstop citing it). A guard that
cannot say which of the three it is does not land. Each pass states its
contract — what it assumes, what it establishes, and what becomes illegal
after it — in a `Contract` block in its module docstring
(`cardlang/parse.py` through `cardlang/ir.py`); the owning pass's contract
decides where a check belongs.

**When a wall fails or a gap is found, sweep the class before patching
the instance.** A found defect names a class: identify the closed domain
the instance belongs to, probe every other member (the other projection
levels, the other declaration namespaces, the other malformed inputs),
and close or wall the whole class in one change. A lone patch converts a
class defect into a recurring one — the corpus's duplicate-name
shadowing sat for months as exactly this: the duplicate-move-parameter
instance was fixed while duplicate zones, state variables, move types,
and struct types kept shadowing silently until the class was swept.
