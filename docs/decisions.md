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

```text
phase declare_trump → outcome { trump_declared(Suit) | bid_abandoned }
```

The enclosing structure pattern-matches on the outcome:

```text
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
`taken(taker, level) | thrown_in`; the trick `round`'s `winner` function
produces a Player. (An auction with nothing to tag — Skat's Reizen, a
betting round — omits the callback and threads phase state instead.) The
enclosing structure pattern-matches on the produced value the same way it
does for phase outcomes:

```text
bidding produces:
  taker_chosen(_, level) {
    if level is Petite or level is Garde { continue to chien_visible }
    else { continue to play }
  }
  all_pass { skip to next hand }
```

A trick or climb round's selected player is also available as the bare
`winner` pronoun in the enclosing body, immediately after the `round`: Hearts
follows its trick `round` with `leader := winner`. The two paths are
disjoint — a tagged result reaches its consumer through `produces:`, never
through the pronoun, and `winner` is the only value a `round` binds.

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
- `pile_frozen` in Canasta: ZONE state (the discard pile is frozen or
  not) rather than phase state, and the criterion carries over unchanged
  — no rule's `applies_when:` reads it; it gates only the take-pile
  move's preconditions, and its operative meaning is per-side anyway (a
  team that has not melded is frozen out regardless, the
  per-player-exception shape below). Correctly a boolean.

The criterion: ask whether any rule reads the boolean in its
`applies_when:` clause. If yes, the boolean is hiding a phase
transition; refactor to sub-phases. If no, it's just data. The subject
of the boolean — a phase fact, a zone fact — doesn't change the test.

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

A sub-phase inherits its parent's `active_rules`. To modify the
inherited set, the sub-phase uses three operators inside the slot:

```text
phase parent { active_rules: [A, B, C] }

phase child_extend   { active_rules: [+ D] }            // adds D       → A, B, C, D
phase child_remove   { active_rules: [- B] }            // removes B    → A, C
phase child_override { active_rules: [override A2] }    // replaces A   → A2, B, C
```

`override X` matches by name: the parent rule with the same identifier
as `X` is replaced by `X`. If no parent rule matches the override
target, it's a compile error — there's nothing to override.

The delta operators are `active_rules`-only. `legal_moves` takes a
plain list of move-type names, stated directly in each phase that
sets it:

```text
phase parent { legal_moves: [play_to_trick] }
```

A `legal_moves:` is set only by a phase that actually runs. A mode holds
rules, never the move menu, so its body admits no `legal_moves:` at all —
the grammar rejects one, since nothing would consult it and the move menu
must never blink from a condition rather than from the step you are in.

A slot may mix operators and plain entries — a sub-phase that lists
a bare rule is shadowing inheritance with its own complete set:

```cardlang-fragment active_rules_shadowing
phase parent { active_rules: [A, B, C] }
phase child  { active_rules: [X, Y] }                   // X, Y only — parent set discarded
```

**Corpus usage.** Every existing `active_rules` delta is `+ X`. Hearts
and Spades add follow-restriction rules; Pinochle and Spades add
first-trick constraints; Tichu adds the Mahjong-wish rule. (Tichu's
`call_tichu`/`call_grand_tichu` decisions are not rule deltas — they
are `round`/`offer` moves in a poll window; see "Interactive
decisions".) `- X` and `override X` are reserved for cases where the
rulebook itself
describes a rule being struck out or replaced. The rulebook-natural
reading of every game in the current corpus uses `+ X` even when the
mechanical effect could be expressed as a removal.

The criterion for which operator to use: write the slot the way the
game's rulebook introduces the change. Rulebooks describe what
*kicks in*, not what *goes away*; the syntax follows.

## Rule demand forms

A rule's `demands:` clause names **a candidate-card set** — an expression
returning the cards a legal move may use, filtering a zone. `MustFollowSuit`'s
`demands: cards in hand where card.suit is state.led_suit` and Hearts'
`demands: cards in hand where card.suit is not hearts` are this form. The legal
move set is the intersection of every active rule's candidate set. Because that
intersection can empty — a void player cannot follow suit — a card-set
`demands` **must** declare an `if_impossible:` fallback: `hand` to play any
card, or `error(...)` to reject the move. There is no silent default (see "No
implicit actions"); a card-set rule without `if_impossible` is rejected at
resolve time.

**A rule binds at exactly one decision site: the trick round's card
decision.** Rules are consulted where card legality is computed
(`rules.legal_cards`) and nowhere else, so a rule is accepted only if it can
fire there — it must `constrains: play_to_trick`, and it must carry a
card-set `demands:` or an `exempts:`. The checker rejects the rest rather
than accepting surface it would silently drop ("Surface totality"):

- a `constrains:` naming any other move type, or omitted entirely;
- `demands: actions where <predicate>` — a predicate on the move's *shape*
  rather than on which cards it draws. There is no site that consults it;
- a rule with neither `demands:` nor `exempts:`, which cannot change what is
  legal however its `applies_when:` reads.

**State the constraint where the move is made instead.** A transfer's
`chosen N` binds a count (Hearts' pass is `transfer chosen 3 cards` — the
`3` *is* the "pass exactly three" law); a move type's `when:` guard binds
its parameters (Stud's bring-in amount). These are the enforcing forms
today, which is why no corpus game loses a constraint to the guards above.

Where rules *should* eventually bind is open — english draughts' mandatory
capture and nine men's morris's in-mill removal restriction are the
witnesses that would force a wider answer
([open-questions/rule-scope-beyond-trick-play.md](open-questions/rule-scope-beyond-trick-play.md)).
Until then the surface is deferred, not deleted (roadmap.md, "Grammar
surface deferred by the checker"): when enforcement widens, the guards
retire and the forms return with an implementation behind them.

**The move under inspection is bound as `action`.** A predicate over a
player's move — the `when <move-type> where …` triggers of sub-phase
transitions (see "Sub-phase entry and exit") and triggered scoring
components — binds that move as `action`, and its
fields expose the move's data: `action.card` (the card played),
`action.cards`, `action.card_count`, `action.actor`, `action.amount`. The
subject is always reached through `action`; there are no bare field names,
and it is never spelled `move` — `move` is the zone-transfer verb (see "The
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
trick `round` carries a `winner` function and optional `trump` / `early`
clauses, and the surrounding body does the routing. These shape *what happens
after a play* (who is selected, when the pass ends early, where the cards go);
rules shape *which plays are legal*.

The categories don't unify:

- **Rules** are filters on the candidate-move set. They attach to phases via
  `active_rules:` and are consulted before each move.
- **Round configuration** (`winner`, `early`, `trump`) and the post-round body
  routing run once per trick (or per play) and produce the trick's effect.

Getaway's first-trick-to-waste behaviour is the canonical mistake: written as a
rule (`rule FirstTrickAlwaysGoesToWaste`) it has nothing to constrain — its
effect is *where the cards go*, an ordinary body transfer after the round:

```cardlang-fragment first_trick_phase
phase first_trick {
  active_rules: [MustLeadAceOfSpadesOnFirstPlay]
  round play_to_trick from leader over all players source hand into trick_pile
        winner highest_of_led_suit
  move all cards from trick_pile to waste
}
```

Hearts' `highest_of_led_suit` is the round's `winner` function, not a rule. The
clean test: if the configuration's effect is "filter legal moves before play,"
it is a rule; if its effect is "shape the trick's resolution after play," it is
round configuration or body routing.

**Routing has two surface forms, both ordinary body statements.** When the
routing is a single unconditional transfer, it is one statement after the round
(Hearts; Getaway's first trick: `move all cards from trick_pile to waste`). When
it branches — Getaway routes the pile to the trick winner on a tochoo (pickup)
but to the waste otherwise — it is an `if` over the round's terminal state:

```cardlang-fragment play_phase
phase play {
  round play_to_trick from leader over players where not eliminated[player]
        source hand into trick_pile winner highest_of_led_suit early on_play_off_led_suit
  if state.trick_terminated_early { move all cards from trick_pile to hand[winner] }
  else { move all cards from trick_pile to waste }
}
```

The body reads the round's `winner` (the selected player) and its terminal
`state` (e.g. `state.trick_terminated_early`): a finished round's state stays
readable as `state.x` until the next round runs. Routing is just body
statements — there is no separate routing construct.

**Contextual card properties are the game's Trick Order.** Some games
interpret card properties contextually rather than from the card's intrinsic
fields: Skat's jacks are trumps regardless of printed suit, and in Doppelkopf
the queens and jacks are too. Those games declare a `trick_order { }` block
("Trick Order" below), whose three rows say what a trump is, what class a card
follows as, and how strong it is; the language mints the readers and the
winner from the declaration. A game that declares none keeps the default —
printed-suit equality, and a `trump:` suit if it has one — and the presence
partition refuses any mixture of the two vocabularies.

## Trick Order

A trick's resolution and its follow legality both rest on three facts about
each card: is it a **trump**, what **class** does it follow as, and how
**strong** is it within that class. In a plain game those fall out of the
card's printed fields and the `trump:` clause. In the big European games they
do not: Doppelkopf's queens and jacks are trumps whatever suit they are
printed, Skat's jacks likewise, 500's joker and left bower are members of a
trump suit they are not printed in, Belote reorders the ranks WITHIN its
trump suit alone, and French Tarot's Excuse belongs to no class at all. A game whose answer differs from the printed one declares it:

```cardlang-fragment trick_order
trick_order {
  trump:         card.rank is Q or card.rank is J or card.suit is diamonds
  follow_class:  if card.rank is Q then none else card.suit
  card_strength: if card.rank is Q then 200 else rank_value(card)
}
```

The block is a **define form**: it does not select among behaviours, it
*defines* the three facts, as ordinary expressions over the implicit `card`
binder (the card-query and filter convention). From the declaration the
language mints one reader per row — `is_trump(card)`, `follow_class(card)`,
`card_strength(card)` — the `card_points { }` / `card_points(card)`
precedent. A game states its order once, and every consumer reads that
statement rather than a second copy of it.

**The rows.** `trump:` is required and types Boolean; a game whose Trick Order
has no trumps writes `trump: false`, so the absence is stated rather than
inferred. `follow_class:` types `Suit?`, where `none` means class-less — a
card that neither sets the lead nor wins — and defaults to the card's printed
suit. `card_strength:` types Integer, higher beating lower, and defaults to
`rank_value(card)`, which reads `ranking:`; a game taking that default without
declaring a `ranking:` is refused. Both defaults are applied once, when the
game loads.

Rows may be written in any order. The order they are READ in is the
language's — `trump:`, then `follow_class:`, then `card_strength:` — and a
row may call the readers of the rows before it only. So a strength row may ask
`is_trump(card)`, and a trump row may not ask `card_strength(card)`; the
reference order is a property of the language, never of how a designer
happened to arrange the block.

**Rows are hermetic.** A row is asked from three places under three different
live frames: the legality filter mid-decision, the winner slot at the end of a
trick, and any hand-rolled body. An answer that varied with the asker would
not be a fact about the card, so a row may read no pronoun of any namespace,
make no `choose`, read no zone that is not fully public and no per-player zone
without naming whose, and call only the Builtins that are pure over their
arguments. Each refusal follows the call graph, so a row that reaches the
forbidden thing through a designer function is refused with the function
named. This is what makes a Trick Order a public fact, and therefore
information-set-safe: nothing it computes can depend on what any one player
knows.

**Two Builtins over the declaration.** `highest_by_trick_order` is the winner.
It is the same name in both of a winner's positions — named bare in a trick
round's `winner` slot, or called over a public pile's Arrival Record for a
hand-rolled trick. `follows_lead(card, pile)` is the winner's own candidate
test, made callable so a follow filter can ask it; legality and winning then
read one definition of the led class instead of two that can drift.

**The Effective Lead.** The card that sets a trick's class is not always the
first one played: a class-less card leads to nothing, and the next card sets
the class instead. The Effective Lead is the first arrival that is a trump or
carries a follow class. It is a different fact from the state variable a game
might keep for the literal first card's suit.

**The algorithm.** The winner is the strongest trump if any trump was played,
else the strongest card of the Effective Lead's class. Trumps are ONE class
for both following and winning, whatever suits they are printed, so a trump
never follows a plain class and a plain card never follows a trump lead.
Strength is read for candidates only: a card that can neither lead nor win is
never asked, which matters because such a card may be outside the game's
`ranking:` altogether.

**First of Equals.** When two plays compare equal, the winner is the one
played EARLIER. It is invisible in a single pack and decisive in a double one
(Doppelkopf, Pinochle), so it is stated as the kernel rule for every winner
the language ships rather than left to fall out of an implementation.

**Reading a pile mid-trick.** `highest_by_trick_order(pile)` over an
incomplete trick answers the winner SO FAR. That is designed surface, not an
edge case: nothing in the algorithm reads how many plays a trick should hold.
`follows_lead(card, pile)` on a pile with nothing led is the value `false` --
not an error — so a leader's filter is written `if any card in hand[p] where
follows_lead(card, pile) then follows_lead(c, pile) else true`, which is also
the shape that gives "void in the led class, anything goes".

**The presence partition.** A game either declares a Trick Order and uses its
vocabulary, or declares none and uses the round-configured one. With a block,
the game-level `trump:` clause, a round's `trump` clause, every other trick
winner and `highest_trump_or_led_suit(...)` are all refused — each describes a
different order from the one the block declares, and admitting both would
leave the engine quietly running one of them. Without a block, every gated
name is refused, because it would read a table the game never declared. A
block that nothing reads is refused too.

**Provenance.** Every Arrival Record read names a fully public zone,
statically: the pile argument of each of these calls is a zone reference whose
declared type projects identity to every observer, and every trick round plays
into such a zone. A winner is named from who played what, so the pile it reads
must be one whose arrivals every observer can derive from their own
observation stream ("The Arrival Record").

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

```text
round offering [<move_type>, …] from <seat> over <ring>
      [order ring] until <predicate> [outcome <fn>]
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
- **Order (`order`).** How the ring is traversed. One value exists — `ring`,
  which is also what an absent clause means: the pointer advances each turn, so
  after a player acts the next *seat* is offered, wrapping. That is poker's order
  as much as an auction's, and each half of the claim is a neighboring bullet's:
  the pointer advances, so the seats *behind* the aggressor are the next ones
  reached; the participants filter is re-evaluated each turn, so the seats a bet
  re-opened come back when the ring returns to them; and `until` is checked
  before each draw, so the ring closes mid-lap the moment nobody is pending. Bridge's, Pinochle's
  and Tarot's auctions and every poker game's betting all run on it. The clause is
  kept although it holds a single value, as the docking point a further traversal
  arrives at: the axis is closed at `ring` alone; the next value arrives with the
  game that forces it — and mints its own name.
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
  threading the survivor through phase state. The order axis stays `ring` alone.
- **Accumulator.** The decision-relevant running state (Bridge's standing level,
  strain, doubling, high bidder, pass count) is ordinary **phase state**, read and
  written by the move-type effects and read by the termination predicate. No
  separate accumulator construct.
- **Termination (`until`).** A predicate over that state, checked before each
  draw (Bridge: three passes after a bid, four with no bid).
- **Outcome (optional).** A named function over the threaded **bid history** plus
  the terminal state — the same status as a trick's `winner` callback (a
  runtime-primitive, no decisions of its own) — that produces the phase's typed
  outcome. Bridge's `bridge_auction_outcome` finds the declarer (the first player
  of the high side to have named the final strain) and produces
  `contract_finalized(declarer, level, strain, doubling) | all_pass`. The `outcome`
  clause is **omitted** when the ring produces no outcome: a betting round mutates
  shared chip/fold state directly through its move effects, so when the ring closes
  it simply returns and the surrounding body deals the next street or settles — no
  typed outcome, no `produces:` arm.

An auction's only decision points are these per-turn candidate draws; the outcome
callback consumes no randomness. So two auctions that present the same per-turn
candidate lists (same length and order) play identically under a random playout —
the property that lets a hand-written engine be re-expressed in this form without
changing behaviour.

## The `ranking:` declaration: enumeration or convention

`ranking:` declares the game's rank strength order, strongest first. It is
optional (Coup and French Tarot declare none — the rank *namespace* always
comes from the deck; `ranking:` only orders it), and an enumeration may be
a partial permutation of the deck's ranks, which narrows the `Rank`
move-parameter domain (see "Declared parameter domains").

The clause takes one of two forms:

- **An explicit enumeration** — `ranking: A K Q J 10 9 8 7 6 5 4 3 2` —
  each entry a rank of the declared deck, no repeats.
- **A convention keyword** — one of the closed set `aces high`, `aces low`,
  `ace-ten`, `twos high`. A convention means *this deck's ranks in the
  standard French order, with the named adjustment*: `aces high` is
  A K Q … 2, `aces low` moves the ace to the bottom, `ace-ten` promotes the
  10 between ace and king (the Ace-Ten family: Skat, Schnapsen, Pinochle,
  Doppelkopf, Belote's non-trump order), and `twos high` moves the 2 to the
  top (the climbing-game order). The template is **filtered to the declared
  deck**, so one convention serves every French-ranked deck: `aces high`
  means A K Q J 10 9 8 7 on skat32. A convention is always a *complete*
  ranking of its deck. A deck with any rank outside the standard A..2 set
  (tarot78's atouts, tichu56's specials, coup15's characters) admits no
  convention — the resolver rejects it, naming the offending ranks, and the
  game enumerates explicitly instead.

The convention spellings are **reserved in ranking position**: an
enumeration whose entries spell exactly a convention name is read as the
convention (no deck names ranks `aces`/`high`, so nothing real is
shadowed). The resolver expands the convention into the operative tuple;
everything downstream — the Rank enum, the move-parameter domain, the
runtime's `rank_index`, the OpenSpiel action space — consumes the expanded
order and never sees the keyword. The registry is
`cardlang/runtime/values.py::RANKING_CONVENTIONS`, derived from the one
canonical `RANKS` tuple and reconciled against the grammar in both
directions by `tests/test_ranking_conventions.py`; suit-contextual orders
(trump promotions, Euchre's bowers) are out of this declaration's scope: a
game whose strength depends on the trick's context declares a
`trick_order { }` with a `card_strength:` row instead ("Trick Order"), and
`ranking:` stays the deck's one context-free order. What the block does not
answer — a card whose IDENTITY changes with context, Tichu's Phoenix — stays
open ([open-questions/special-cards-declaration.md](open-questions/special-cards-declaration.md)).

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
  else in the runtime (the trick form, filtered transfers), so a deck-order
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
the follower's plain transfer pick; `num_distinct_actions` does not grow with
the parameter. (Minting per-card vocabulary ids instead would give one card
play two representations.) This is also why at most one Card-parameterized
move may appear per vocabulary: the card id alone must name the move.

**The card block itself is reserved only where a decision can reach it.** It
is the home of every content-item id, so a game none of whose decisions can
offer one — a betting game that deals cards and never plays them, a climbing
game whose every play is a combination, a board game deciding by cell —
reserves no card block, and its ids begin at the next block. The presence is
derived from the game's own decision-bearing constructs rather than declared,
so `num_distinct_actions` — OpenSpiel's action dimension, and therefore the
width of any policy head trained on the game — is not padded by a block the
game has no construct for. The derivation reads the tree, not reachability, so
a game whose only card decision sits behind a condition that never holds still
reserves the block. The derivation over-approximates deliberately: a block reserved and
never used costs ids, while a block missing under a live decision would leave
that decision with no id at all, so encoding a content item against an absent
block is refused rather than numbered into the neighbouring block.

### The integer `choose` domain

`choose integer in <lo> .. <hi> [up to <N>] [excluding <e>]` is the
numeric decision form (a bid — Spades' `0 .. 13`, Oh Hell's `0 .. hand_size`).
Its domain is a bounded integer interval, and it satisfies the same
closed-contract-plus-mask rule as the fixed domains above: the OpenSpiel action
space reserves a fixed block of ids `0 .. ceiling` up front, and the live
`lo .. hi` range masks it per state (the runtime offers exactly
`range(lo, hi + 1)`, less the one value an `excluding` clause names — below).
Every operand — `lo`, `hi`, `e` — is an Integer, checked at typecheck; a
non-Integer value that reaches the evaluator through the permissive top is
refused at play time, never coerced. The **ceiling is a declared, checked
static bound**, never inferred from the deck or a runtime value:

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
no value can ever be chosen. A **literal lower bound below zero** (`-1 .. 5`)
is rejected for the mirror reason: the block starts at 0, so its smallest
value has no id. A runtime `lo` is not statically decidable and is
left to the runtime guard. At runtime the *range* is guarded
where `hi` is evaluated (`lo >= 0` and `hi <= ceiling`): a live range that
escaped its declared domain would offer a legal value with no action id, and a
value-only check would pass whenever the chooser happened to draw inside the
reserved block. The OpenSpiel integer block is sized to the game's **largest**
declared ceiling (one shared block; a game has at most one `choose` per decision
point today), so `num_distinct_actions` reflects the declared bounds — not a
fixed deck-sized constant.

**`excluding <e>` removes one value from the live range as the choice is
made.** The clause is a set difference over the candidates: `e` evaluates at
choice time to an Integer, and the chooser is offered `lo .. hi` less that one
value (Oh Hell's dealer: `choose integer in 0 .. hand_size up to 10 excluding
hand_size - total_bid` — the rulebook's constraint on the number a player may
say, on the number's own construct). Because the exclusion filters the
candidates **before** the draw, the offered action set, the announced value,
and the value the game scores are one number; a correction applied after the
draw is silent while the announcement is public, and so is a different game.
The exclusion is a single value, not a predicate: the corpus witness
needs exactly "not this one number", and a predicate form would multiply
cells for no game. An `e` outside the live range excludes nothing — the
dealer whose table has already over-bid the hand bids freely — and the
clause is a no-op by design, not an error. Resolve rejects the exclusions
that can never act or always empty the choice, since a clause that never
acts is accepted-but-ignored wearing a legal parse: a literal `e` outside
the static offerable interval — from the literal `lo` (or `0`, for a runtime
`lo`) to the ceiling — and a literal `e` that empties a statically singleton
interval (`3 .. 3 excluding 3`, or a literal `lo` equal to the ceiling).
Literal means a bare integer literal, as for the bounds: nothing is folded,
so `excluding 5 + 1` is a runtime `e`. A
runtime `e` is not statically decidable; at play time an exclusion that
empties the live range is an error ("No implicit actions"), reported with
the excluded value. A literal `e` inside a literal range (`0 .. 13 excluding
7`) is accepted, and its id is reserved and legal in no state: unlike an
`up to` above a literal `hi`, which is a sizing declaration and is refused
for that reason, the exclusion is a rule of the game, and the one dead id
is its cost. The clause order is fixed — `up to` before `excluding`.
`choose` sits at the top of the expression grammar beside the query forms,
never inside an operand chain, so its trailing operand — the range's `hi`,
or the exclusion — extends as far right as possible and
`excluding hand_size - total_bid` has one derivation; a choose used as an
operand of any construct — an operator, a comparison, a ring search's seat,
an aggregation's default, another choose's bound — is parenthesized,
`(choose integer in 0 .. 5) + 1`, as a bare query is. The
OpenSpiel block is unchanged by the clause: the excluded value's id,
`int_base + e`, is simply absent from the state's legal mask, the way a
value above the live `hi` already is. Like the range bounds, the exclusion
is the author's to keep over state the chooser can see: an exclusion over
a hidden zone makes two histories the chooser cannot tell apart offer
different legal sets, and no pass refuses it — for a corpus game the
per-observer legal-action-agreement proof is the evidence, and for any
other game nothing is.

The still-open sibling is the bounded-`Integer`
*parameter* domain (signed `delta`), which fits neither this `0 .. ceiling` id
scheme nor any corpus game yet
([open-questions/move-parameter-domains.md](open-questions/move-parameter-domains.md)).

## The climbing form of `round`

Combination-climbing games (Big Two, Tichu) run on a third
configuration of the kernel `round`. A climbing trick plays like a trick, but each
play is a *combination* (a computed set of cards), not a single card:

```text
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
for a trick.

**The named leader need not be a participant.** `from` and `over` are
independent expressions, so in a game where going out does not end the hand
(President, Tichu) the trick winner can shed their last card on the winning
play and still be named as the next leader. That is a normal state: the ring
starts at the first participant at or after them in turn order, exactly as the
trick, auction, and `turns` forms treat the same clause pair. A game therefore
writes the natural `leader := winner` and needs no hand-authored "skip to the
next player still holding cards" fallback. Only an **empty** `over` set is an
error — there is then no one to lead and no one to follow. Like the trick form, the climbing form exposes its terminal state to
the body (`mech_state` → `last_round_state`, read as `state.x`):
`state.lead_ended_trick`, and `state.shed_first` / `state.shed_second` — the
first two players who played their last cards this trick, in play order, from
which a finishing-order game (Tichu: double victory, first-out routing, call
payouts) folds its global out-order without any extra chooser draw.

Two decisions distinguish it from the trick and auction forms:

- **The combination engine is a named query, not a DSL value.** A combination play
  moves a *specific computed card-set* — the cards of the chosen combination — and
  the transfer vocabulary moves cards *by count* (`all` / `one` / `N cards`), never
  a named set. So a combination play cannot be a DSL `move_type` effect the way a
  bet is, and there is no DSL-visible `Combination` value. Instead the engine is two
  **game-local Primitive queries** named on the round — `combinations` (lead options)
  and `follows` (legal follows) — and the climb form performs the card transfer itself.
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
the migrated scope), that randomness is a game-local Primitive drawing on
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

## The `turns` form

The turn loop beneath the round forms — for games whose turn is a *body of
statements* rather than one flat candidate list (the dividing line from the
round family: a single-list turn is an auction-form configuration; `turns` is
for draw-then-discard shapes, ask-and-resolve shapes, anything with statement
structure per turn):

```text
turns <binder> from <leader> over <participants>
      until <pred> [again <state-var>] { <statements> }
```

The binder names the current player, who is also the acting player — exactly
`for each`'s per-iteration binding, one player at a time — so a `chosen`
transfer or `offer` in the body is attributed to the turn-holder without a
cursor variable. The form owns what every hand-rolled turn loop re-implements
(and where the stress-sweep's runtime failures clustered): **rotation**
(advance in game direction to the next seat satisfying the participants
predicate, re-evaluated per advance, so elimination falls out), **termination
placement** (`until` is checked at each turn boundary, before the first turn
too — the zero-iteration run always exists), and the **go-again axis**
(`again` names a declared Boolean state variable the body's move effects
write; a turn ending with it true repeats the same player — Go Fish's
hit-or-matching-draw. The form CONSUMES the flag, resetting it to false as it
reads it at the boundary, so a stale write buys at most one repeat and can
never silently monopolize the loop — only a write during the turn keeps the
turn). The leader expression is read once, at the first turn, and must name a
real seat — a non-seat value (an out-of-range Integer, a loose pronoun) is a
typed runtime error at the bind, the same seat guard `as` and `offer` carry. A
full lap finding no eligible participant is a loud runtime error, the `offer`
no-legal-move rule one construct up; a decisionless body that never
terminates hits the same iteration guard as `repeat until`.

```cardlang-fragment turns_form
turns t from 0 over players where not eliminated[player]
      until (number of players where not eliminated[player]) is 0 {
  score[t] += 1
  eliminated[t] := true
}
```

Gin Rummy's draw-discard cycle is the strict-alternation anchor; Go Fish is
the go-again anchor (its move effect writes `went_again` instead of mutating
a cursor). Schnapsen's leader loop stays on the auction form — its turn IS
one flat candidate list. A `direction` override clause is deliberately not
grammar: no corpus user ([roadmap.md](roadmap.md), "Grammar surface deferred
by the checker"). The form emits no observations of its own — the body's
decisions emit through their own sites, and rotation is derivable from
state — so information sets are unchanged by construction.

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
- **The acting player is never defaulted.** A choice or chosen transfer made with
  no acting player is an error ("who is choosing?"), not a silent attribution to
  player 0 — wrap it in a per-player context (`as <player>` for one named decider,
  `for each player p` or the simultaneous pass for everyone) so the chooser knows
  who decides.

## Single-actor decisions: the `as` block

When one *named* player decides — a chosen discard, a follower's answer to a led
card, a victim flipping one of their own cards — the binder is `as`:

```cardlang-fragment as_taker
as taker {
  move chosen 6 cards from hand[taker] where is_pref_discard(card) to discard[taker]
}
```

`as <player-expr> { … }` evaluates its player expression in the **outer** context,
binds the acting player to that one player, and runs its body **once** as a block
scope (its `let`s do not escape; state writes and card moves persist). It is the
statement-level companion to `for each player` (everyone decides) and the
simultaneous pass — the form for exactly one decider. The player expression must be
a `Player`; anything else is a type error.

It exists because a `chosen` transfer needs an acting player, and binding one
belongs in the construct that says *who decides*, not in a loop that iterates
everyone. Pressed into service for a single decider, `for each player p: if p
is <who> { … }` carries two latent failures `as` forecloses (the same `for
each` stays correct — and stays in the language — for genuine per-player work,
a scoring pass or a deal to everyone):

- **It captures `actor`.** `for each player p:` rebinds the acting player for its
  body, and `actor` *reads* the acting player, so `if p is actor { … }` would be
  true for **every** `p` — which is why the comparison is refused outright (see
  "Naming the acting player twice", below). `as` evaluates its player *before* the
  rebind, so `as actor { … }` is idempotent and `as challenger { … }` reads the
  state variable — neither can be captured.
- **It re-reads its guard mid-pass.** When the body mutates the guard variable, a
  later player in the same pass re-matches and takes a second turn — an
  order-dependent double-execution. `as` runs its body once, so one written turn is
  one turn. This one no Owner Guard can catch — whether the body writes the guard is a
  question about paths, not names — so it remains the reason to reach for `as`
  even where the comparison would be legal.

`as` uses the same actor-binding runtime path the loop reached indirectly, so it
emits no new observations. Its gain for the OpenSpiel target is that the decision
node's chooser is **statically** readable — one named player at the statement —
rather than recoverable only by evaluating a predicate. Reading a procedure
parameter inside an `as` block is safe for the same reason it is inside any
actor-rebinding body: arguments are evaluated once in the caller's context
([Named procedures](#named-procedures)), so Coup's `lose_influence(victim)` runs
`as victim { … }` with no capture.

## Naming the acting player twice

A construct that binds a seat *and* makes that seat the acting player gives the
same player two names: its own binder, and the `actor` pronoun. Inside such a
body the two are interchangeable, so an equality comparison between them is a
constant — `p is actor` always true, `p is not actor` guarding a body that never
runs. **Both operands naming the acting player is refused at resolve time.**

The rule is about *provable identity*, not about the `for each` spelling, so it
covers every construct that binds the acting player to a name — `for each` over a
seat role (the `binds_actor` column of the domain registry), `turns`, `each …
simultaneously`, and `as <name>` — and the transitive `let me = actor`, which
merely adds a third name for the same seat. Both equality operators and both
operand orders are refused alike, since the degeneracy is in the operands rather
than in the spelling.

Binding is the only thing that grants a name, and it is also the only thing that
takes one away: a name rebound by an inner construct — a query binder, a
`produces:` arm's payload, a `let` assigning it something else — stops denoting
the acting player from that point, and comparing it becomes ordinary again. A
binding's right-hand side is read *before* it takes effect, as everywhere else
in the language, so `let p = p` re-binds `p` to the player it already named and
keeps the comparison refused.

The **innermost** binding is the one that counts, and that is what keeps the
useful idioms legal:

```cardlang-fragment actor_alias
let w = actor
for each player p:
  if p is w { result[p] := 1 } else { result[p] := -1 }
```

Capturing the acting player *above* the loop is the way to compare against them
*inside* it: `w` is bound before the rebind, so it still names the player who
acted while `p` walks the seats. Written inside the loop the same `let` would
name whichever seat the loop had just bound, and the comparison would be refused
along with the direct one. Symmetrically, a nested rebind frees the outer
binder — inside `for each player p: as <someone> { … }`, `actor` is that someone,
so `p is actor` is an ordinary contingent test again.

Two boundaries are deliberate. A **state variable** is never treated as provably
the actor, even directly inside `as taker { … }`: the body may reassign it, so
the comparison can genuinely differ, and the guard refuses only what it can prove.
And a merely **redundant** read is not an error — `hand[actor]` where `hand[p]`
would do is accepted, because it does exactly what it says. The defect being
refused is a comparison whose answer is fixed before the game runs, not a
roundabout way of writing a correct one.

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
may not be active.

Reads and writes are both refused at resolve
(`resolve._check_state_scope`), which also owns the game-level
`winner:` clause: it is evaluated after every phase has exited, so it
ranks on game-level state only. One reference position is outside that
guard's reach — a move type, rule, function, procedure or define body
has no enclosing phase, so whether its state reads are live depends on
which phase invokes it rather than on where it is written. That is a
reachability question, not a lexical one, and it is tracked rather than
enforced (issue #242).

**A default reads only what is already declared.** The free-reads rule
above is about a body running inside the phase, when the whole block
exists. A `= <default>` is evaluated earlier than that — while its own
block is still being declared, top to bottom — so it sees the enclosing
scopes and the declarations *above it in its own block*, and nothing
else. A default naming a variable from later in its block, from itself,
from a sibling phase, or from a phase nested inside its own reaches a
variable that does not exist yet, and is refused
(`resolve._check_state_default_scope`). Without the rule these all
passed every front-end pass and died at playout on a bare `KeyError` out
of `runtime/state.py`.

A default may not **call**, either. A call's state reads live in the
callee's body, so admitting one would mean chasing the declare-time
reachability of every function a default can reach. Refusing the call
outright costs nothing measured — across the whole corpus and every
library, defaults hold integer and enum literals, and not one reads a
state variable — and it keeps the surface total rather than leaving a
check that silently stops at the call boundary. Compute the value in
the phase that needs it.

Nor may a default **`choose`**. A default is evaluated outside any
player's turn, so there is no one to make the decision; the runtime
raised "a `choose` with no acting player" at declare time, and for the
OpenSpiel target a decision with no actor has no information set to
attach to. This is the same rule as the two above and not a separate
one: what a default may do is bounded by how little of the game exists
when it runs.

**A default must fit its declared type.** `v : Integer = "s"` is refused,
not silently stored: the default's inferred type must be assignable to the
variable's declared type — the same `assignable` relation an ordinary
assignment uses (`typecheck._check_state_default_type`, the initial-value
Shadow Guard of `_check_assign`). For an indexed variable the default is checked
against the element type, since `score[player] : Integer = 0` broadcasts
one value to every key. The check is as sharp as the inferencer and no
sharper: a default whose type the inferencer leaves as the permissive top
is accepted whatever the declaration, which is the type system's design
rather than a hole here — no corpus default is untyped.

**Example: Bridge state declarations.**

```text
game Bridge {
  // No game-level state in Bridge.

  phase rubber repeat until (any team where games_won[team] >= 2) {
    state {
      games_won[team]              : Integer = 0
      above_line[team]             : Integer = 0
      below_line_current_game[team]: Integer = 0
    }

    phase hand_sequence {
      state {
        contract       : Contract? = none
        declarer       : Player?   = none
        dummy          : Player?   = none
        tricks_taken[team] : Integer = 0
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
lists what *is* published. The guard is what keeps a form's working memory out of
the language: without it, a round's private ring cursor is nameable, type-checks,
runs, and silently changes the game. The declared types carry the same weight — an
untyped `state.x` is contagiously `Any`, and every comparison guard is dark behind
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
every guard answers the same for the bound name as for the inline
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
stand in a transfer endpoint or an epistemic target — narrowing a
transfer is the `where` filter's job, not a laundered query's. An initializer the checker deliberately
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
  `max_game_length` is measured in (decisions, i.e. actions), a
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

```cardlang-fragment before_each
before_each {
  move all cards to deck
  shuffle deck
  deal 13 cards from deck to each hand
  rotate pass_direction through [left, right, across, hold]
}
```

`move all cards to deck` is a destination-only **gather** transfer (no `from`):
it collects every card from all other zones into the named zone. A `Deck`-typed
zone is initialized at game start holding the deck's cards, so the first
`before_each` gather is a no-op and the deal is well-defined.

A gather collects zones in **lexicographic zone-name order** — singleton zones
and indexed families in one sorted namespace, a family's instances in its index
domain's order (players in seating order, teams in team order). The collection
order is observable twice over: each non-empty zone emits its own transfer
event (shaping every player's observation log, hence information sets), and the
collected cards stack into the destination in collection order (feeding the
next same-seed shuffle). Making the order canonical is what keeps the `zones { }`
block a pure declaration: its order is presentational everywhere in the
language, and reordering it never changes a playout.

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

The language has a typed object model with built-in types,
user-defined types declared per-game, and convenience sugar that
rewrites to underlying forms.

**Built-in types:**

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
- `Team` — declared in the game header; indexable as a key into
  per-team state.
- `Seating` — derived from `players` + `teams`; exposes
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
  ([roadmap.md](roadmap.md), "Grammar surface deferred by the checker").
- Phase outcomes — tagged-union values; pattern-matched, not
  dot-accessed.

**User-definable types.** Games declare struct-like types that the
language treats as first-class values:

```text
type Contract = {
  level        : Integer
  strain       : Suit?
  doubled_mult : Integer
}

type HandResult = {
  tricks_actual   : Integer
  tricks_required : Integer
} derived {
  made = tricks_actual >= tricks_required
}
```

A field's type is a single type name (`Integer`, `Suit?`, another
declared type); a field is not a place for range or union constraints.
Derived fields are computable functions of declared fields. They're
accessed identically to declared fields (`result.made`) but are
stored nowhere; the compiler inlines them.

A user-defined type is not parameterized: `type_def` takes a name and a
field list, and the field list is where a game varies what the type
holds. They are the language's extension
point for genuine record types. The current corpus models its
structured values with flat state variables and functions instead —
Bridge's contract is `contract_level : Integer`, `trump_suit : Suit?`,
`doubled_mult : Integer`; a poker pot is a chip zone plus an
eligibility set — so no corpus game declares a `type` yet. The surface
exists for the game that needs a true record, and the DSL doesn't ship
a vocabulary covering every possible game.

**Angle brackets: the head fixes the argument.** `Name<Arg>` means one of two
things, and which is decided by the head, not by the reader:

- A **zone-type head** (`Hand`, `TeamPile`, `Cascade` — the kernel's zone
  types) takes an **index domain**: a lower-case domain id, equal to the
  declaration's own index. `hand[player] : Hand<player>` reads "a hand per
  player", and the checker refuses any disagreement between the two brackets.
  The argument says who the family is keyed by, never what the zone holds —
  the zone type's own name already fixes that.
- A **value-constructor head** (`Collection`, the only one) takes an **element
  type**: a Title Case name from the declarable set. `cards : Collection<Card>`
  reads "a collection of cards". It is spellable in a `primitives { }` entry's
  two type slots and nowhere else, because a set of cards anywhere else in a
  game is a zone; every other type position teaches that placement rather than
  reporting a shape error (see "The `primitives { }` block").

Case does the disambiguating on the page — an index domain is a lower-case id,
an element type is a Title Case name — and both cross-confusions are refused
by name. `?` suffixes a **value** type only: never a zone, never a collection
(an absence inside a set has no rulebook reading, and `is empty` is a
collection's absence). There are no type variables anywhere in the language: no
declaration takes one, no Builtin is polymorphic, and no rulebook says "for any
type T".

**Optional types and the `none` literal.** A type written `T?` is optional: it
holds a `T` or the absence value `none`. `none` is the language's single
absence literal, used by every optional (`leader : Player? = none`, `contract :
Contract? = none`, `state.led_suit is none`) — it is not a member of any enum.
Where a game needs a value that reads like "nothing happens" but is a real
domain choice — Hearts' no-pass hand — it gets its *own* enum value
(`SeatDirection = {left, right, across, hold}`), never `none`. This keeps `none`
unambiguously "no value": a `Player` that is `none` is unset, not the string
`"none"`.

`true` and `false` are the two boolean literals, the values a `Boolean` field
takes (`eliminated[player] : Boolean = false`, `eliminated[p] := true`). Like
`none`, they are language literals rather than enum members, so a game never
declares them.

**Deck declaration.** The `cards:` line names the deck a game uses.
The deck is a constant from the closed kernel table (`DECKS` in
`cardlang/runtime/values.py`): a game selects one by name and does not
spell out its cards.

```cardlang-fragment cards_line
cards: standard52
```

Each registered deck defines its own card set — the standard 52-card
deck, Pinochle's doubled 48, Skat's 32, and the decks whose suits do
not share a single rank list: French Tarot's 78 (four 14-card suits, a
21-card trump suit, and the Excuse) and Tichu's 56 (the standard 52
plus the four special cards Mahjong, Dog, Phoenix, Dragon). Those
compositions live in the registry, not in per-game syntax;
[library.md](library.md) "Built-in component sets" catalogues them
(decks are its card-flavored entries), and adding a deck is a kernel-table
registry addition. Tichu's non-(suit, rank) specials
are a separate question from the registry itself; see
[open-questions/special-cards-declaration.md](open-questions/special-cards-declaration.md).

Per-card mutable attributes (tapping, counters, status effects) are
not part of the surface — the oriented- and CCG-style card state they
would serve is deferred ([roadmap.md](roadmap.md), "Out of scope").

**Convenience sugar (rewrites that compile away):**

- `state.foo` → `foo` (just a disambiguating prefix)
- `card.tapped` → `card.attributes[tapped]`

Sugar is documented; the underlying form is what the compiler
manipulates.

**Access discipline.** The bracket form is the only indexed
access: `hand[player]`, `captured[team_of(winner)]`,
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

## `Any` means the top, never a failed lookup

`Any` is the type checker's top: it is compatible with every type in
both directions, and every operand guard short-circuits on it. That is
correct for a value whose type genuinely cannot be narrowed, and it is
the mechanism that keeps typing *gradual* — an unrefined corner of the
object model must not manufacture errors in expressions that touch it.

The same permissiveness is a defect when it stands for "the checker
failed to look this up". A value that satisfies every constraint
silently exempts everything below it from every guard, so a single
missed lookup turns a whole subtree's type checking off and the checker
still reports success. This is the "accepted-but-ignored" class
(see "Surface totality") in its most damaging form, because it is
invisible: nothing in the program looks wrong.

**The two roles are separated at the producers, not in the type.** There
is one `Any`, and it means the top. A lookup whose domain is closed does not
fall back to it:

- **A closed-registry lookup raises.** Binder roles, native call
  signatures, zone content types, struct types, operator result types,
  and `ref_kind` dispatch each have a registry that an earlier pass
  validates against. A miss is a divergence between two registries —
  a compiler bug, not a program error — so it fails in the compiler's
  failure channel (an `AssertionError` naming the guard or builder that
  guarantees it), exactly as the runtime's `role_members` and
  `zone_observer_key` already did.
- **An environment lookup raises.** A name resolve classified but the
  type environment does not bind means the environment was built
  incompletely — most often a binder a statement walk failed to
  thread. The fix is always to thread the binding in the pass that owns
  the scope; binding `Any` at the failing site to quiet it restores the
  hole.
- **A declared type name is validated where it is declared.** Every
  position that declares a type is checked by the resolver, at the
  declaration rather than at some use. There are nine, and they are
  derived from the grammar rather than listed by hand — the productions
  referencing `type_name` or `payload_type`, plus the struct literal's
  head — because a hand-listed enumeration of them was twice found
  incomplete: state variables, struct fields, move parameters, procedure
  parameters, rule-template parameters, function parameters, `define`
  payloads, phase-outcome payloads, and struct literals. The grid that
  crosses them against every source a name can come from is
  `tests/test_type_name_positions.py`. Otherwise a mere typo maps to the top and *widens* what
  the checker accepts: the misspelled program passes where the
  correctly-spelled one is rejected. Exactly one Owner Guard owns each
  position, and it is the tightest one that applies — a move parameter
  answers to the enumerable-domain gate (which subsumes name validity,
  since an unknown name is not an enumerable domain), a procedure
  parameter to its own domain set, and the remaining positions to a
  plain name check. Each position's allowed set mirrors exactly what
  its type builder can resolve, so a name the guard admits is never one
  the builder still maps to the top, and no defect is reported twice in
  two channels.

  A gate belongs to the DECLARATION, not to the uses that reach it: a
  gate run from the vocabulary sites that name a move would leave a move
  type nothing offers ungated entirely, and would report one named twice
  as two defects. Declaring a construct is what makes its parts real.

**What stays permissive is a small audited set**, enumerated and pinned by a
test so a new permissive site must be classified rather than added:
values with no better type (a diverging `error()`, context-dependent
native returns the signature model cannot express, deferred pronoun
shapes, a forward struct reference), and propagation downstream of a
guard that already fired. Gradual typing is preserved — the top still flows
and still suppresses errors where it is deliberate.

The general rule this instantiates: **a fallback is only legitimate
when no better answer exists.** A fallback standing in for an answer
the program *does* have is a silent wrong answer, and belongs upstream
as an Owner Guard (see "Closed-domain completeness", write-time triage).

## Resource amount syntax

A resource quantity in a `transfer` is written `<count> <type>` — the
count (an integer expression, or `all`) followed by the resource type
name:

```text
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

```text
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

```text
// Coup steal — take 2, or 1 if that's all the target has:
let amount = min(2, coins[target].amount_of(coin))
transfer amount coins from coins[target] to coins[actor]
```

```text
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

## Move, Transfer, and what `move_type` is called

A **Move** is one played instance of a Move Type bound to its Parameters; a
**Transfer** is one relocation between zones. They are independent, and the
trick game hid that by making them coincide: a card play is one of each. A
capture is one Move and two Transfers, a pass is one Move and none, and setup
is Transfers with no Move at all — so a single fused word cannot describe a
board game. The cardinality table is in [model.md](model.md), "Moves and
Transfers".

The keyword stays **`move_type`**. With "move" owning the player-action family
it reads as compositional English, and `action_type` would manufacture a false
friend against the Interop sense of "action" — the translation to OpenSpiel
stays one-directional, which is what keeps `action` usable as the scoped
pronoun for the candidate Move under consideration.

The surface verb `move` also stays, and is deliberately not the engine word for
a Transfer: in solitaire the verb and the Move genuinely coincide, and the
surface reads like the rulebook. The engine word is Transfer; its verbs
(`deal`/`draw`/`move`/`burn`/`muck`/`transfer`) are sugar over the one
primitive, and a future board family mints its own (`place`, `capture`) as
registry rows rather than as new syntax.

## The operation vocabulary

Games relocate cards and resources, reveal and hide them, shuffle and
rotate. These operations are a small, closed vocabulary in three families,
not an open-ended set of verbs. The surface reads like a rulebook, but each
verb lowers to one of a few semantic primitives — the same
small-core/rich-library split that makes the trick a `round` configuration
rather than syntax ([principles.md](principles.md)).

**Transfer** — relocating items between two places. One primitive underlies
every transfer verb: `deal`, `transfer`, `move`, `burn`, `muck`, and `draw`
are sugar that differ only in defaults, not in kind. A transfer carries a
selection (`all`, a count, or a `chosen`/`random` amount), an item noun, a
source place, and a destination (a single zone or `to each` recipient). The
item noun is `cards`/`card` today; the noun stays open in the grammar so a
resource transfer (coins, chips) can one day be the *same* construct as a
card deal rather than separate syntax — but resource transfers and the
grammar's per-transfer `visibility =` override are deferred surface, rejected
by the checker ([roadmap.md](roadmap.md), "Grammar surface deferred by the checker")
rather than left for the runtime to silently ignore.

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
deferred ([roadmap.md](roadmap.md), "Grammar surface deferred by the checker").

**Transfer `where` filter.** The `from` form of a transfer (any destination
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
leaving non-matching cards in the source. An unfiltered transfer is
unaffected — the filter is a genuinely separate code path
(`execute.py::_select_filtered`), not a generalization of the unfiltered one,
so no existing game's card-selection behaviour changed when this clause was
added.

French Tarot's chien discard is the corpus's first use: the discard is six
chosen plain non-Kings (`cards in hand where is_pref_discard(card)`), and
when fewer than six exist the forced top-up draws from the non-bout atouts
alone (`where card.suit is atouts and not is_bout(card)`) — a per-card
predicate over which cards a decision may even draw from, distinct from the
*count* a plain `chosen N cards` transfer already expressed.

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

A new rulebook verb is presumed an instance of an existing family — transfer
sugar or an epistemic op — until a game proves it is genuinely none of them.
Adding a fourth family is a deliberate act, not the default response to a new
word.

## Joint-predicate selection

A transfer's per-card `where` filter tests each candidate alone —
`chosen K cards where <pred>` can never say "these K cards *together* form a
valid group," which is the load-bearing test of every meld-family game. The
joint form binds **`cards`** — the candidate *set*, a card collection — and
the selection becomes ONE decision over the source's satisfying subsets:

```cardlang-fragment jointly_selection
as arranger {
  move chosen some cards from hand[arranger]
       where jointly (number of cards in cards) >= 3 to waste
}
```

The amount picks the subset sizes: `some` (any non-empty size — the joint
predicate owns the size constraint), an expression (exactly that size), or
the degenerate `one`/`all` (size 1 / the whole source). Subset sizes are
always at least one — a zero-card "choice" is not a decision — so a
non-positive count, and `all` over an empty source, fall to the same loud
no-satisfying-subset error `some` gives. (Transfer amounts generally are
guarded at evaluation: a negative amount is a typed runtime error everywhere
— a Python slice would otherwise silently move the rest — and a zero
`chosen` amount is a vacuous decision node, also refused.) `jointly`
requires `chosen` — the selection is a player decision over subsets; a
dealt joint selection has no decider and a `random` one has no corpus user
(both rejected loudly, recorded in
[roadmap.md](roadmap.md), "Grammar surface deferred by the checker") — `some`
requires `jointly`, and `to each` is rejected under `jointly` (it would
silently make every destination seat its own subset decider; recorded).
Enumeration is deterministic (sizes ascending, combinations in source
order) and bounded: a source pool past 16 cards is a loud runtime refusal,
not a hang. No satisfying subset is the no-implicit-actions error: guard
the transfer so it is only reached when one exists.

For the OpenSpiel target, joint candidates are card subsets — the combo
what the block deals in, exactly like climb combination plays — and the subset
universe comes from a **registered per-predicate codec**
(`joint_codec_function`, the climb-engine codec pattern: the predicate's
root call names it, `gin_arrange_ok` → the 329-meld universe of
standard52). A joint predicate with no registered codec is refused loudly at
action-space construction, never silently absent from the space.

Gin Rummy's showdown arrangements are the anchor: the knocker declares
melds one joint selection at a time, each guarded so the remaining hand
still arranges to a legal knock — every reachable arrangement stays legal,
random play included, while equal-deadwood arrangement *choices* (which
change what the defender can lay off) remain real decisions. Persistent
meld *objects* (shared growing team piles, per-group scoring) are not a
construct at all — see "Meld groups: flattened zone families" below.

## Meld groups: flattened zone families

There is no first-class meld-group object. A game's persistent card groups
— shared, growing, keyed, typed, scored as objects — flatten onto existing
machinery, and two rummy-family games prove the two halves:

- **The key flattens into zone-family names.** A group keyed by a small
  static domain declares one zone family per key value: Canasta's
  per-team per-rank melds are eleven team-indexed `TeamPile`
  families (`meldA[team] … meld4[team]`), plus the black-three going-out
  group and the red-three row; Gin's three arrangement slots are
  `meldA/B/C[player]`. The one index a zone family carries is the *owner*
  (a `zone_key_of` domain — a seat or a team); every other key is spelled
  in the name. Statement-level routing on a runtime key value is an
  if-dispatch over the key domain in the move's effect
  ([games/canasta.cardlang](games/canasta.cardlang), `close_meld`), closed
  by construction because the key domain is the declared (possibly
  partial) `ranking:`.
- **Growth is ordinary transfer.** Either partner extends a standing meld
  with a plain guarded transfer on any of their turns; nothing about the
  group persists outside its zone.
- **Typed state is derived from composition, never stored.** Natural vs
  mixed, canasta-completion, wild-count legality are pure functions of the
  pile's contents, evaluated at every read by the game's own functions and
  game-local primitives (the guards at extension time, the scorers at hand
  end). Storing group state beside the cards would create a second source
  of truth.
- **Per-group scoring reads each zone as an object.** Canasta's hand
  settlement scores every meld pile by its own composition
  (`canasta_canasta_bonus`); the group *is* the zone.
- **Joint formation legality** is either a joint selection ("Joint-predicate
  selection" above — Gin's one-shot arrangements) or, where the action
  space cannot carry subset ids (a duplicate-card deck's multisets —
  [roadmap.md](roadmap.md), "Grammar surface deferred by the checker"),
  an announce-then-stage decomposition whose
  per-card guards keep a legal completion reachable from every offered
  state (Canasta's `stage_card`/`close_meld`, the arrange-guard totality
  trick per card).

The forcing function this decision waited for was Canasta's shared growing
pile, and the flattening carried it without new surface. A first-class
group object becomes worth designing only if a game arrives whose group
key domain is *not* statically declarable (unboundedly many groups, or
keys outside any declared enumeration) — Cassino's builds are the nearest
candidate ([games/_candidates.md](games/_candidates.md)).

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
and the per-line verbosity cost would be the largest in the language. One
carve-out, the `offset_by` precedent: domain arithmetic goes word-spelled
when the symbol would mislead — rounded division is `divided by … rounded
up|down` (below), because no symbol spells a division that must name its
rounding. `is`,
`not`, and `number` are reserved words — no state variable, zone, function,
or binder may take one of these names.

**Every keyword is a whole word.** A keyword never matches inside a longer
run of word characters, in either direction: `letx = 3` is a syntax error
rather than a declaration of `x`, and `1and`, `up to10` and `moveall` are
refused for the same reason. Names that merely begin with a keyword stay
ordinary names — `letter`, `is_re`, `assets`, `some_var`. The rule exists
because the alternative is not an ambiguity a parser could report but a
*misreading*: the fused spelling has exactly one parse, and it is not the
one a reader takes from the page. A dropped space is therefore a diagnostic,
never a silently different sentence. This is separate from, and larger than,
the reserved-word question above: reservation says a word may not name a
value, whole-word matching says no word may be cut in half.

**Equality is `is` / `is not`** — plain equality, with no identity/equality
split to trip over. `a is not b` is a single operator, never `a is (not b)`.
The right-hand keywords `none` and `empty` are a closed set dispatching to
the absence and emptiness checks (`led_suit is none`, `hand[p] is not
empty`); every other operand is ordinary equality. `==`/`!=` are not part of
the language; the checker rejects them with the replacement spelling.

**Rounded division is `divided by … rounded up|down`** — a `term`-level
operator (the `offset_by` shape: `working_bid divided by base rounded up`),
Integer operands and result, with the rounding direction mandatory: there is
no bare quotient to misread as exact. `rounded down` floors toward negative
infinity and `rounded up` ceilings toward positive infinity — the English
words' own directions, whatever the operands' signs — and a zero divisor is
a typed runtime error. `*` binds tighter on both sides (`2 * bid divided by
base rounded up` divides the product); multiplying a quotient takes parens
(`(bid divided by base rounded up) * 2`). `/` and `%` are not part of the
language; the checker rejects them with the replacement spelling. `//`
cannot even be rejected: it introduces a comment, so a floor-division habit
written `a // b` reads as `a` with the rest of the line commented out —
write the word form.

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

**Transfer and reveal filters** are ordinary predicates with `card` bound
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

```text
function <name>(<param> : <type>, …) = <expr>
```

declared at the top level alongside the `move_type`s. A call `<name>(<arg>, …)`
evaluates the body with the parameters bound to the arguments. Seven-Card Stud's
betting ring uses three: `can_act(p)` (not folded, still holds chips), `owes(p)`
(still owes the standing bet), and `pending(p) = can_act(p) and (not acted[p] or
owes(p))` (the ring/termination predicate). The `over` filter and the `until`
terminator both name `pending(player)`, so they cannot drift out of step — a
correctness property, not only brevity.

`acted[p]` is the turn taken *within* the round, and **a forced post placed
before the round begins is not one: the posting seat stays pending until it
acts.** Hold'em's big blind and Stud's bring-in poster match the standing bet
without having spoken, so `pending`'s `not acted[p]` arm is what keeps them in
the ring — keyed on debt alone it would deal the hand out around a live seat.
The same reading decides which moves are legal and not only who is asked:
`poker_betting`'s `raise` is offered against a standing bet to a seat that
either still owes it or has not yet taken a turn, which is Pagat's option for
the big blind — *"The big blind player acts last, and may raise even if no one
else has done any more than call."* Pagat is silent on the bring-in poster's
same moment, so Seven-Card Stud's file pins that treatment as the variant's own
rule rather than citing an authority for it.

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

```text
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

```text
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
assignments and card transfers persist, of course — a procedure acts on the game.
Only its `let`s are local, which is the whole difference between a procedure and a
paste: without it, a body that binds `target` would silently capture a caller's own
`target`, read *after* the `run` site.

Together these mean the caller cannot corrupt the body and the body cannot corrupt
the caller, *by construction* — so there is no capture guard to remember, and none
to get wrong. One guard does remain, because expansion cannot fix it: a body binder
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
loud guard with a recorded deferral (issue #134); none is silently
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

```text
identity > identity_set > count_by_type > count_only > existence_only > trivial
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

Each zone type fixes a per-observer projection — a mapping from
observer to the level at which it sees the zone's contents. This is
the model a zone type encodes:

```text
public_zone   : Zone<Card>     { composition: identity to all }
private_hand  : Zone<Card>     { composition: identity to owner, count_only to others }
hidden_deck   : Zone<Card>     { composition: count_only to all }
catan_hand    : Zone<Resource> { composition: count_by_type to owner, count_only to others }
```

The set of zone types is a closed kernel table (`ZONE_PROJECTIONS`
in `cardlang/stdlib/zones.py`, wrapped as the named aliases in
[library.md](library.md), "Library zone types"). A game does not write
a `composition` block or declare a new zone type — it selects a named
type in its `zones {}` block, and the type carries the projection
(`hand[player] : Hand<player>`). Adding a projection profile is a
kernel-table addition, not a surface a game reaches.

### Per-observer visibility on moves

Visibility derives from the declared zone types: a move is observed
through each endpoint's projection (below), and the current language
has no per-move override. The grammar admits a `visibility:` clause on
a transfer, but the type checker rejects it — "visibility derives from
the declared zone types" — reserving the design for
[open-questions/move-level-visibility.md](open-questions/move-level-visibility.md),
which asks when a move's epistemic effect must differ from what its
zones imply (a card passed face-down, a resource stolen and shown only
to the pair). No corpus game needs it yet.

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

### Native memory-affecting operations

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
eventual compilation pass (see issue #139).

A game whose text draws nothing — a Chance-Free Game, see
[glossary/chance-free-game.md](glossary/chance-free-game.md) — compiles with no
root chance node at all: it registers as `DETERMINISTIC`, declares no chance
outcomes, and opens on its first decision, so its information state is
available at the root rather than after a seed nobody chose. The licence is
derived from the game rather than declared by its author, and it is guarded
both ways: the classification names every drawing construct and refuses one it
does not know, and the run installs a generator that refuses every draw, so a
missed construct stops the game where it draws instead of yielding a tree that
silently omits real chance.

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

### The Arrival Record

The kernel performs every movement, and it retains what it performed: each
zone carries an **Arrival Record** — per card now in the zone, the deciding
actor (`None` when no seat decided), the card value, and the source zone
address, in arrival order (`state.Zone`). "Who played this card" is two
facts, deliberately: the attributed actor and the source zone's owner — one
seat spelled twice, and kept the SAME seat under Delegated Play: a delegated
play's record stays the source owner's (Bridge's dummy), because every
observer derives a play's seat from the movement's source label while the
`chose` event is the [[decider]]'s alone, so a decider stored in the record
would be provenance no observer's stream entails. The decider's record is
the decision node and its private recall ("Delegated play"). Consumers read the record in place of
re-deriving attribution: a trick winner's pairing of seat against card is a
read, never a zip of seat order against pile contents, and participation is
nothing to declare — it derives from who acted, so a contract's dead seat is
stated exactly once, in the movement structure the game file already has.

The record is engine truth, mediated exactly as zone contents are: it enters
no observation event and no information state, and any surface that reads it
per-observer is bounded to zones whose type projects identity to every
observer (`PrimitiveReads.arrival_zones`, refused loud otherwise; the
`highest_trump_or_led_suit` call form guards the same predicate) — a
concealed zone's provenance is not derivable from any observer's stream, so
nothing may range over it, legality contexts included. Per-observer
provenance is therefore **derived from the observation stream, never stored
and then stripped**: a fact about an observed play persists exactly as long
as observation entails it, and washing is an invariance rather than an
operation — the record stores values only, so observationally equivalent
duplicate copies produce equal entries and every projection is invariant
under permuting them. The readiness proofs carry the executable form: the
provenance soundness rows (the engine record equals what every observer's
own log derives, per consumed zone), the wash pin (hidden-stock permutation
moves no information state), and the copy-purity pin (two replays of one
world serialize the record identically, so no per-object identity can hide
in it).

## Position domains and positional zones

Solitaire layouts (and any game whose rules address *places* — columns,
cells, piles-by-location) are described with **declared position
domains**: per-game, finite, integer-keyed value domains, declared in a
game-level `positions { }` block:

```text
positions {
  column : 1..7      // Klondike's seven tableau columns
}
```

Each entry mints a domain usable in exactly two surface slots:

- **Zone-family index**: `tableau_up[column] : Cascade<column>` — one
  zone instance per member, subscripted by any integer-valued expression
  (`tableau_up[c]`, `tableau_up[3]`). The declaration's type argument
  names the same domain as the index, like `Hand<player>`.
- **Move-parameter domain**: `move_type build(src : column, dst :
  column)` — enumerated into the guard-filtered cross-product like
  `Suit`/`Rank`/`Player` ("Declared parameter domains"), with one
  OpenSpiel vocabulary action id per combination. The runtime and the
  static action space enumerate the same declared `lo..hi` members by
  construction.

The bounds are non-negative integer literals with `lo <= hi`, and a
domain holds at most 256 members (a layout wider than that is a
declaration error, not an action-space explosion). A declared name may
not collide with a built-in domain id or type name (`player`, `suit`,
`Rank`, `Card`, `Integer`, …) — the built-in registry and the declared
block are reconciled by rejection, so the two sources can never disagree
about a name. A `board:` clause mints a **named-member** domain (`cell`,
string members) on this same substrate — same collision guard, same cap,
same two surface slots — detailed in "Boards and cells" below.

**Positions are unowned.** No observer *is* a column, so a
position-indexed family has no owner: every observer receives the zone
type's `others` projection. Consequently a zone type whose owner and
others projections differ (`Hand`, `HiddenPile` — any row with two
distinct projections) cannot be indexed by a position; the checker
rejects it, because its owner projection would be silently unreachable.
Uniform-projection types (`Cascade`, `HiddenStack`, `Foundation`,
`Cell`, `PlayerPile`, …) may.

**Iteration and state-indexing reject loudly; quantification is admitted.**
A position domain is not a seat and not an iteration role: `for each
column c`, `each column simultaneously`, a position-indexed `state`
variable, and a position-typed `state` declaration are all rejected with
diagnostics (deferred, recorded in issue #111). Quantifiers
range over a position domain's members like any other quantifiable
domain — `any column where …`, `all columns where …`, `number of columns
where …`; for a board's `cell` domain the register adds two collection
forms over lines and cells, detailed with `lines(k)` in "Boards and
cells" below (tests/test_cell_queries.py). A position-indexed family
must always be subscripted — the bare-family
actor sugar (`hand` = the acting player's hand) is meaningless for an
unowned family and is rejected.

**Mixed-facing piles are two zones.** Per-position visibility inside one
physical pile (Klondike's columns: face-down below, face-up above) is
represented by *zone decomposition*, never by per-card facing state: a
`HiddenStack<column>` family under a `Cascade<column>` family, with the
flip written as an ordinary transfer between them. The flip's observation
event derives from the two declared projections (count from the hidden
side, identity from the open side) exactly like every other transfer —
per-position visibility adds **nothing** to the projection model. The
analysis and the rejected alternatives are in
[design-notes/positional-zones.md](design-notes/positional-zones.md).

**Sequence orientation.** A zone's contents are a sequence: arrivals
append at the end (placing on top of a face-up pile — `top_of` reads the
end, `bottom_of` the front), and the dealt take (`draw`/`deal` with no
`where`) removes from the front (FIFO). For a shuffled stock the ends are
indistinguishable; where order is observable the FIFO contract is the
physical one — Klondike's unshuffled redeal (`move all cards from waste
to deck`) cycles the stock in exactly the order the last pass drew.
Filtered transfer selects in source order and appends in source order,
which is what moves a cascade's run as an intact unit ("stack movement"
is a usage pattern of the existing transfer verb — a rank filter denotes
the suffix — not new surface). Sequence *knowledge* is derived, not
declared: an identity-entitled observer saw every arrival event, so order
falls out of the observation log under perfect recall.

`top_of(z)` / `bottom_of(z)` are native functions over any card
collection; on an empty collection they fail loudly at runtime (guard
first — `Z is not empty`). Their use in a move *guard* is subject to the
same discipline as every guard expression: legality must not read
information the decider is not entitled to, which the per-game
legal-action-agreement proofs police (`tests/openspiel_ready/`).

## Component sets: cards and pieces

A game's individuated zone content is declared with exactly one head
clause — `cards: <deck>` (a card deck) or `pieces: <set>` (a piece set)
— naming one entry of the closed component-set registry
([library.md](library.md), "Built-in component sets"). The two are
mutually exclusive and one is required; a game declaring both, or
neither, is rejected (no game has witnessed needing both).

The individuated content kind is the **Piece**: an identity of two
enumerable axes (with per-set declared names) times multiplicities, plus
the per-game attributes and optional facing of the typed object model
("Typed object model"; "Knowledge, visibility, and the projection
model"). A **Card is the deck specialization of a Piece** — a component
set whose two axes are named `suit` and `rank` and which carries the
card-only conventions (`ranking:`, the follow/trump rule family,
hand-order enumeration, the `Card` move-parameter domain). A piece set
names its own two axes and carries none of them; `xo_marks`
(tic-tac-toe's marks) names them `side` (`x`/`o`) and `kind` (`mark`).

The axes bind positionally: a piece's first axis occupies the slot a
card's `suit` occupies, its second the `rank` slot. Field access types
against the game's declared axis names — `card.suit`/`card.rank` in a
card game, `piece.side`/`piece.kind` in a piece game — each axis a
distinct enum, so a cross-axis comparison (`piece.side is mark`) is
rejected exactly as `card.rank is spades` is. The axis values (`x`, `o`,
`mark`) enter the enum-value namespace exactly as a deck's suits and
ranks do.

**Noun/content agreement is a typecheck Owner Guard.** Every surface that
spells card-content vocabulary demands the deck flavor and, in a piece
game, is rejected with a diagnostic naming the game's declared kind
("this game declares pieces ('xo_marks')") — and symmetrically the
`piece`/`pieces` noun is rejected in a card game. The guarded surfaces
are the transfer/reveal item noun, the filter binder, `.suit`/`.rank`
field access, the card-query and aggregation forms, the `ranking:`,
`trump:`, and `card_points { }` clauses, the `suit`/`rank` quantifier and
iteration roles, the `Card`/`Suit`/`Suit?`/`Rank` move-parameter domains,
the deck-reading native calls, and card literals. Each rejection sits at the layer that
owns the operand-kind class (the typechecker), naming the kind rather
than parsing the construct and silently giving it card meaning — the
"accepted-but-ignored" failure this guard exists to prevent.

```text
pieces: xo_marks                        // axes: side = [x, o], kind = [mark]; 5 x + 4 o
move all pieces from box where piece.side is x to reserve[0]
```

**Seeding reuses the Deck-typed-zone rule** — the one existing "initial
contents" concept, one spelling per concept. A game's `Deck`-typed zone
is seeded with its component set at game start; tic-tac-toe names that
zone `box` and drains it in setup. A piece game with no `shuffle`
consumes no randomness — every seed yields the identical game.

The acceptance property for `Card`-as-a-specialization-of-`Piece` is
that **the card corpus cannot tell**: every card game keeps `cards:`,
its card queries, and byte-identical behavior. Piece Shadow Guards of the
card-query and aggregation forms are deliberately absent from the
grammar (a piece game counts and aggregates through the generic
collection surfaces a card game shares); the deferred declaration-site
and rule-system guards are recorded in issue #114.

## Zone capacity

Each library zone type carries a **capacity** — a column of the
zone-type registry ([library.md](library.md), "Library zone types"),
total over every row. `Cell` (the one-card holding space) has capacity
1; every other library zone type is unbounded.

A transfer whose destination would exceed its type's finite capacity
fails loudly at runtime with a typed error naming the zone, its type,
the capacity, and the guard to write:

```text
zone 'slot[0]' is a Cell (capacity 1) and already holds 1 — the move
would overfill it; guard the move (`slot[0] is empty`)
```

The Owner Guard **stands behind** the game's own guards; the registry owns the
capacity class, so the check lives at the single transfer-executor
append rather than being re-derived per move type. An honest game guards
its placements (FreeCell's `cells[slot] is empty`, tic-tac-toe's
`square[at] is empty`), so the Owner Guard never fires on a correct game — it
converts a rules bug into a loud failure at the overfilling move, not a
silently dropped card. The `Point` row (an unbounded stack) is deferred
to its witness; see issue #118.

## Boards and cells

A game with a spatial board declares it with a `board: <family>(<args>)`
clause: it selects a family from the closed `BOARDS` registry
([library.md](library.md), "Built-in boards") and gives its integer
arguments.

```text
board: grid(3, 3)
```

The `grid` family builds a rectangular board; unknown family, wrong
arity, or out-of-bounds arguments are resolve diagnostics (the registry
declares each family's arity and bounds). A `board:` clause **requires
`pieces:`** — a board holds pieces, not cards — so `board:` in a card
game is rejected, and the board-plus-`cards:` combination waits on a
witnessed need.

**The board mints one named-member position domain, `cell`.** It rides
the same substrate declared position domains do ("Position domains and
positional zones"): the minted domain is injected alongside any
`positions { }` block and flows through every surface an integer
position domain flows through — zone-family index, move-parameter
domain, the unowned projection, the action space, the IR — under the
same collision guard, the same 256-member cap, and the same
"always subscripted" rule. What differs is the member kind: a board's
members are **string cell names** (`a1`, `b1`, …, row-major from `a1`;
the file letter is the column from the left, the number the row from the
bottom — `grid(3, 3)`'s nine cells are `a1 b1 c1 a2 b2 c2 a3 b3 c3`),
not an integer range. The names and their order are the board entry's,
fixed in the registry.

```text
zones {
  square[cell]    : Cell<cell>          // nine one-card cells, keyed a1..c3
  reserve[player] : PlayerPile<player>
}
move_type place(at : cell) { when: square[at] is empty  effect { … } }
```

**Cells type as `TCell`, distinct from `TInteger`.** A parameter, `let`
binder, or subscript key over the `cell` domain carries `TCell`; a zone
family indexed by a named-member domain (`square[cell] : Cell<cell>`)
subscripts only with `TCell`-typed expressions (`square[at]`, never
`square[7]`), while an integer-keyed family keeps the `TInteger` rule
(`cascade[3]`) — one mechanism, both member kinds, each rejecting the
other's key. Two cells compare by equality (`at is at2`); a cell against
an integer (`at is 3`), cell ordering (`at < at2`), and cell arithmetic
(`at + 1`) are type errors — a cell name is an opaque member, with no
order, successor, or arithmetic (adjacency, where a game needs it,
arrives as declared board data, not an algebra on cell names —
[design-notes/positional-zones.md](design-notes/positional-zones.md),
"Adjacency"). `place(at : cell)` enumerates one placement action per
cell, in member order, exactly as an integer position parameter
enumerates its range.

**The cell/line query register.** The bare quantifier forms range a
binder over any declared position domain ("Position domains and
positional zones"); the board adds two collection forms and the
`lines(k)` call that feeds them. A bare form's noun is the domain name,
validated against the game's declared domains (a board's `cell`, an
integer `positions { }` name), with `any` taking the singular noun and
`all`/`number of` the plural:

```text
any cell where square[cell] is empty
all cells where square[cell] is not empty
number of cells where <pred>
```

An unknown noun is a diagnostic naming the declared domains; a
boardless, positionless game naming `cell` is guided to the collection
escape instead. Where a collection value exists, two collection forms
iterate it: `any line in <lines> where <pred>` walks a collection of
lines (binder `line`, type `TLine`), and `all cells in <line> where
<pred>` walks the cells of one line (binder `cell`, type `TCell`).
`lines(k)` is the native call the board's declared length-`k` lines are
read through — every straight run of `k` cells along a row, column, or
diagonal — returning a collection of `TLine`, each an ordered tuple of
cells; `grid(3, 3)`'s `lines(3)` is the eight tic-tac-toe lines. A
literal `k` outside the board's span is a resolve error; `lines(…)` in a
boardless game is rejected naming `board:`.

```text
any line in lines(3) where all cells in line where square[cell] is not empty
```

Tic-tac-toe is the corpus witness
([games/tic-tac-toe.md](games/tic-tac-toe.md)): `board: grid(3, 3)`,
`pieces: xo_marks`, the nine `square[cell]` cells, `place(at : cell)`,
and the win test `any line in lines(3) where all cells in line where …`.

### Transfer: directions, frames, and the class-1 verbs

Where tic-tac-toe only *places* pieces, a game whose pieces *move*
declares a move parameterized by a **movement direction** as well as a
cell. A grid mints a second named-member domain, `dir`, whose members
are the seat-relative forward directions `ahead`, `ahead_left`,
`ahead_right`:

```text
move_type step(from : cell, along : dir) { when: … effect { … } }
```

`dir` is a **move-parameter domain only** — a separate source from the
`positions { }` union, so it never reaches the zone-index, quantifier, or
`for each` surfaces (a direction is not a position). It types as `TDir`,
distinct from `TCell`: `along is a1` (direction against cell), `along is
3`, `along < along2`, and `along[…]` are all type errors, and a direction
member is not expression-nameable — naming `ahead` in an expression is an
unknown name, exactly as a cell name is (the meaning of a direction is
read through the verbs below, never a literal). `step(from : cell, along
: dir)` enumerates one action per (cell, direction) pair, in member
order.

**Per-player frames.** A grid's directions are seat-relative: `ahead` is
one player's forward and the other's backward, because the second seat's
frame is the 180-degree rotation of the first's — one shared board, a
declared per-player transform, never a second board. The transform is
folded into the class-1 verbs, which take the acting player and resolve
the direction in that player's frame. Five closed Builtin verbs read the
board entry (rejected in a boardless game naming `board:`, the `lines(k)`
Shadow Guards):

- `neighbor(from, along, player)` — the cell one step along `along` in
  `player`'s frame, a `TCell`. It is **total**: an off-board step is a
  guarded contract, not a return value, so a guard demands `has_step`
  before reading `neighbor` (`and` short-circuits, so `neighbor` is never
  evaluated off the board).
- `has_step(from, along, player)` — whether that step stays on the board.
- `is_diagonal(along)` — whether a step along `along` changes file (the
  capturing directions on a grid, where straight steps do not capture).
- `home(player)` and `far_row(player)` — a player's back-two-ranks setup
  region and the opposite edge (its reach-to-win goal), each a
  `Collection<Cell>` the cell membership and quantifier forms consume.

**`for each cell` and cell membership.** Setup that fills a region
iterates it: `for each cell c: <stmt>` runs the body once per board cell,
binding `c` as a `TCell`, and a membership guard narrows it to a region.
This lifts the `for each <position>` gap for a board's named-member
domain only — an integer `positions { }` domain (`for each column`) stays
guarded, the split being named-member versus integer:

```text
for each cell c: if c in home(0) { move one piece from reserve[0] to square[c] }
```

**Displacement capture and reach.** Capture is two ordinary kernel
transfers — the captured piece to a `captured[player]` pile, then the
mover — so it emits through the existing observation sites with no new
machinery. A reach-to-win test reads the just-moved piece's destination
against `far_row(actor)`; a wipe-out win reads the opponent's piece
count. **The opponent of the actor is a game `function`, e.g.
`function opponent_of(p : Player) = if p is 0 then 1 else 0`, not a `for
each player p: if p is not actor` guard: inside a `for each player` body
the acting player IS the bound seat `p`, so `p is not actor` compares the
actor against a second name for the actor** — refused at resolve as an
always-false comparison ("Naming the acting player twice"), which is why a
"the other seats" idiom names a seat directly (`opponent_of`) or captures
the actor first (`let w = actor`, tic-tac-toe's spelling). Breakthrough is the corpus witness
([games/breakthrough.md](games/breakthrough.md)): 8x8, sixteen pieces a
side, `step` with diagonal-only capture, and the two termini its oracle
names.

**Guards stated as behavior.** A bare cell name in an expression (`a1`),
and now a direction name (`ahead`), is an unknown name, not a literal —
named only through a parameter or a quantifier binder; naming a specific
cell in a setup or rule waits on its witness (issue #111).
A position domain is still not a declarable `state` type or a state
index, and an integer position domain is still not a `for each` role.
The remaining board-topology surface — the `HiddenCell` and `Point`
zone-type rows, double-indexed families, `roll` chance, probes,
`reachable`, in-file boards — is guarded per rung of the board-topology
ladder ([design-notes/board-topology.md](design-notes/board-topology.md);
issue #124).

## Game result: `winner:` and `loser:`

A game declares its terminal result with exactly one top-level clause,
evaluated against the final state when the phase tree finishes:

```cardlang-fragment winner_loser
winner: lowest cumulative_score      // Hearts — rank a score variable
loser:  the player where hand[player] is not empty   // Getaway — select directly
```

The two forms reflect two shapes of game. A *scored* game accumulates a
score each member holds and the result is whoever ranks first by it, so
`winner: <lowest|highest> <score-var>` names the rank direction and the
variable. The variable it names is a game-level `state` declaration
indexed by player or by team (`cumulative_score[player]`) and declared
`Integer` or `Boolean` — a per-member value is what there is to rank, and
those values are what the game hands OpenSpiel as its returns. A
`Boolean` target ranks `true` above `false`, so a game decided by a flag
ranks on it directly (`winner: highest alive`). A target that is scalar,
optional, or of any other declared type is refused at check time with a
diagnostic naming the declaration: an unindexed one has no per-member
value, an optional one may hold `none`, and the rest either cannot be
compared or compare fine and mean nothing (a `Player`-typed target would
deliver seat ids as utilities). See [Winner](glossary/winner.md).

An *elimination* game has no score: players drop out until one
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

Four expression forms query the player ring by a predicate:

```text
players where <pred>                        // the set of matching players
the player where <pred>                     // the unique matching player (errors if not exactly one)
the first player from <seat> where <pred>   // the ring search: the first satisfying seat of one lap
number of players where <pred>              // how many match
```

The predicate is evaluated once per player with `player` bound to the
candidate, so it reads like the per-player indexing used everywhere else:
`players where not eliminated[player]`, `the player where hand[player] is
not empty`, `number of players where hand[player] is not empty`. The
binder is the fixed name `player` (the canonical seating role), not a
user-chosen variable — these are filters over a single known ring, not
general comprehensions, so there is nothing to name.

Like the quantifier (`any player where …`), aggregation (`sum of … over
… as …`) and integer `choose` forms, a player query sits at the top of the
expression grammar: its `where <pred>` body extends as far right as
possible, giving one canonical parse. To compare a count, parenthesize it:
`(number of players where not eliminated[player]) > 1`.

`the player where <pred>` is the singular selection a `loser:` clause
uses; it is an error at runtime for the predicate to match zero or
several players, since it names exactly one.

**The ring search** scans exactly one lap of the seat ring in the game's
`direction:`, starting AT the named seat — the kernel's own "at or after"
ring-start convention (see "The climbing form of `round`") — and yields the
first seat whose predicate holds: `the first player from leader where
hand[player] is not empty` is Tichu's post-trick lead advance read aloud.
The start is any seat-valued expression, evaluated OUTSIDE the binder
scope; it sits below the query forms in the grammar, so a query used as
the start parenthesizes (`from (the player where …) where …`). The
exclusive variant is spelled by composition — `from dealer offset_by left
where in_hand[player]`, Hold'em's button advance — and because `offset_by`
is a seat direction (absolute), the exclusive spelling composes with the
seat direction that matches the game's turn direction: `offset_by left` in
a clockwise game, `offset_by right` in a counterclockwise one. There is no
default clause and no per-form direction clause; a full lap with no
satisfying seat is a typed runtime error naming the form, exactly as `the
player where` errors off its premise — a game whose ring can legitimately
empty writes the guard it means (`if any player where … { … }`, Tichu's
own post-trick spelling).

`is not empty` is the negation of `is empty` (a zone predicate), paired
for elimination games that select the player who *still* holds cards.

## Scoring composition

> **Status: designed, not yet built.** No game runs this subsystem — the runtime
> has no `apply_components:` construct, and `ScoreDelta`/`triggered_by:` are not
> implemented. It is the intended shape for composed scoring; the corpus scores
> through game-local statements and Primitives today (Bridge and Spades
> inline; Pinochle's `pinochle_meld_value`, Tarot's `tarot_per_opp`, Cribbage's
> pegging/show primitives). The components named here and in the sibling sections
> are the proposed decomposition, promoted corpus-first when the subsystem lands.

Scoring composes from named components. The scoring phase of a game
declares which components apply:

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

Each component takes the hand result and returns a `ScoreDelta` — a
structured value carrying per-team (or per-player)
contributions. The scoring phase sums the deltas across all
components and applies the result atomically.

This composes by summation: the order of components in the list
does not affect the result (per "Mutation semantics" above, batched
mutation). Each component reads pre-batch state; all components
contribute to a single applied write.

**Structured-score shapes are per-game, not generalized.** Bridge's
`ScoreDelta { above_line, below_line }` has two channels per
team because the game-win threshold cares specifically about
below-the-line accumulation. Stud has a different shape: a list of
pots with per-pot eligibility, length data-dependent on all-in
history. The games whose score is a single integer per player
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

**Per-card points: a rank-keyed table is the `card_points { }`
clause; everything richer stays an inline expression or a
per-game helper.** A game whose card points are a function of
rank declares them as a block clause beside `cards:`, rows in
`ranking:`'s key position (a NAME or a bare INT), values static
signed integer literals, with one optional trailing `else:` row
for the everything-else value:

```text
card_points {
  A: 1
  2: 2  3: 3  4: 4  5: 5  6: 6  7: 7  8: 8  9: 9  10: 10
  J: 10  Q: 10  K: 10
}
```

Rows are whitespace-separated like every block clause; the empty
block is a syntax error (at least one rank row); a duplicate rank
key and a key that is not a rank of the declared deck are resolve
errors naming the deck. Unlisted ranks read the `else:` value, or
0 with no else row (Tichu's sparse table prices five ranks; the
rest read 0). Negative rows are ordinary (`Phoenix: -25`). The
`card_points(card)` Builtin reads the declared table, and calling
it in a game that declares no clause is a resolve error — the
table has ONE source, the game's own clause: the deck registry
carries composition only, never points (`values.Deck`), so one
deck serves games that price it differently, and a piece game is
refused the clause outright (the noun/content agreement guard,
"Component sets: cards and pieces").

The clause deliberately carries no more than the rank-keyed
table. Card points that vary by more than rank stay inline or in
a per-game `function`, composed OVER the clause where a table
carries part of the fact: Hearts scores `if card.suit is hearts
then 1 elif card is Q of spades then 13 else 0` inline; French
Tarot declares `card_points { K: 9  Q: 7  C: 5  J: 3  else: 1 }`
and wraps its bouts inline (`if is_bout(card) then 9 else
card_points(card)` — a rank-keyed table cannot carry the petit,
whose rank "1" is worth 9 in the atouts and 1 in the plain
suits); Belote's trump-dependent pricing is a per-game function
with no table at all. A declarative rank-keyed `counters: { ... }`
block on the CARD definition was considered and stays rejected —
it re-attaches a scoring fact to the component, and only cleanly
handles the pure-rank shape; the game-level clause carries that
shape, and inline conditionals scale to the rest. Lift to a
per-game helper function when the composition is large enough to
repay the indirection (Canasta's twelve-pile meld sum,
`canasta_meld_points`, is an example).

## Triggered scoring components

> Part of the `scoring_component` subsystem — designed, not yet built (see
> "Scoring composition" above).

Some scoring fires in response to a specific event rather than as
part of an `apply_components:` batch. Bridge's GameBonus fires when
a team's below-the-line score crosses 100; RubberBonus fires
when `games_won` reaches 2; Spades' bag-overflow fires when
`bags >= 10`. These
share one shape, distinct from the batched per-hand composition:
fire on an event, evaluate a predicate, contribute a `ScoreDelta`.

A scoring component declares the trigger with a `triggered_by:`
clause analogous to a rule's `applies_when:`:

```text
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

**Corpus usage.** The corpus's triggered components are Bridge's
GameBonus and RubberBonus and Spades' BagOverflow. All fit the shape above.

## `choose` as expression

`choose` elicits an integer decision from the acting player. Its one
form names an inclusive range, optionally capped, optionally less one
value:

```text
bid[p] := choose integer in 0 .. 13
```

Oh Hell caps the range — `choose integer in 0 .. hand_size up to 10` —
so the action space stays bounded when `hand_size` is large, and its
dealer's bid adds `excluding hand_size - total_bid`, the one number the
rulebook forbids (the clause's semantics: "The integer `choose` domain").
`choose`
is an expression: it appears wherever an `Integer` is expected — the
right-hand side of an assignment, a move argument — and, like the query
forms, it is parenthesized when it is an operator's operand. It emits a public
observation of the chosen value, and the chooser is the acting player
of the surrounding decision.

`choose` covers integer decisions only. The other decisions a game
elicits are not `choose`. Selecting which move to make is
`offer to <player> one of [move, …]`; the structured interactive forms
(an auction, a poll, trick play) are the `round` construct — see
"Interactive decisions: a kernel and an in-DSL standard library". A
decision that routes cards to a chosen recipient runs as one of those
move selections and reads its result through an ordinary function:
Pinochle's trump declaration is `round offering [declare_trump_suit]`,
and Tichu's Dragon gift is
`offer to outcome one of [dragon_to_left, dragon_to_right]`, not an
inline "chooses" subexpression.

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

The games above don't share a common bid type or interpretation.
Bridge's contract is a structured value rather than an integer;
Oh Hell's bid is per-player; Spades and Pinochle differ on
threshold vs total-points. A `bid_meaning:` parameter on Auction
would only cover Pinochle's case, since Spades/Oh Hell/Bridge don't
use the Auction mechanic.

Bid interpretation is therefore a per-game scoring concern. Each
game's `scoring_component`s declare what counts as making the bid:

```text
// Spades (ContractScoring):
if result.tricks_won[t] >= non_nil_bid:           // threshold
  delta_score[t] += 10 * non_nil_bid
```

```text
// Oh Hell (TricksAndExactBonus):
if result.tricks_won[p] is result.bid[p]:         // exact
  delta[p] += 10
```

```text
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

```text
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

The mechanism: the kernel round loop consults an optional `chooser_for`
helper that defaults to the identity function (the actor chooses for
themselves), and a parallel `play_source_for` helper routes the actor's
move-source zone. Both live as ordinary per-game functions; the seat a
helper yields is the [[decider]] — the `chose` observation and the
OpenSpiel decision node are the Decider's, while the trace, the movement,
the Arrival Record, and the trick stay the actor's: the record never
stores the Decider, whose provenance no observer's stream entails ("The
Arrival Record").
The trick form is the routed form; the other decision points refuse the
helpers by name rather than ignore them (`runtime/delegation.py` classifies
every chooser call site, and issue #458 records what lifting a refusal
takes). Three Owner Guards ride the helpers: at resolve, a helper takes
exactly one Player, and a game defining helpers must hold a trick round
for them to reach; at the draw, a delegated decision's pool must project
full identity to its Decider — legal actions must be a function of the
Decider's own information state, and whether a seat's pool is delegated
depends on both helpers' values at that seat, which is not statically
decidable over two opaque expression bodies. A routing condition read
from a hidden zone is issue #458's recorded deferral.

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

```cardlang-fragment passing_phase
phase passing when pass_direction is not hold {
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
not the atomic-effect block: serializing responders in seat order is
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
  transfers are simultaneous by construction —
  [games/tichu.cardlang](games/tichu.cardlang).)
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

```text
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
  *closed* set of axes: participants (actor / others / ring / list), order, an
  accumulator threaded across steps, a termination predicate, and a typed
  outcome. Auctions, betting,
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

The kernel's atom (`offer`, parameterized `move_type` definitions, the `actor`
pronoun) and the `round` construct are built. Every trick game (Hearts, Spades,
Getaway, Bridge, Oh Hell) plays on the trick form of the kernel `round`, the
built-in `Trick` mechanic has been retired, and `round` carries the termination
axis (an `early` predicate — Getaway's tochoo) plus round-state exposure. The
**auction form** is built too (see "The auction form of `round`"): a continuous
ring over a heterogeneous move vocabulary, with the accumulator as phase state, a
termination predicate, and a typed outcome over the bid history — Bridge's,
Pinochle's, and Tarot's auctions run on it (Tarot as a counterclockwise
single-pass ring, the ring honouring the game's `direction`), the poker family's
betting runs on the plain ring, and Skat's Reizen call-and-response runs as a
role-guarded two-participant ring (see the call-and-response bullet under "The
auction form of `round`"). The
participant-filter axis is built — the ring is re-evaluated each turn, so it
shrinks as players drop out (Pinochle's passed bidders and standing high bidder,
Tarot's seats dropping after one bid). The remaining work (the challenge /
block vocabulary; promoting the shared `auction` definition
at its third instance) is the in-flight build (see issue #140 and
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
   gets a tracker record — a GitHub issue, cited in the ledger as
   `issue #N` — so a future game can lift it when it needs the cell.
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

The transfer production is the worked example of the matrix: the selection
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
  static test, and backed by a runtime refusal on anything left over.
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
  But every deferral must be a **loud guard** (a static rejection or a
  runtime refusal, with a test), never a silent gap. Deferred-and-guarded is
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
rather than reading as if it did. A check born green — a pin over behavior
already correct when the pin was written — additionally records and
demonstrates the one-line mutation that turns it red (`red under: <the
edit>` in its docstring), the mutation planting the fault in the code
under guard — never in the pin's own assertions or expected values; a
guarantee whose author cannot name a reddening edit, or can name only an
edit to the pin itself, is this defect class wearing a test's name. The crime is never
incompleteness; it is *silent* incompleteness.

Acceptance for changes to rigor-critical machinery — anything the
information-set guarantees, the encodings, or the invariants rest on — is
therefore a stated completeness argument, not a green suite. For an
enumerable domain the argument's canonical form is the **grid**: the
domain's axes derived in code from their defining registries — an axis with
no defining site gets its derivation built as the change's first
deliverable, because a hand-listed axis is complete only by luck and goes
stale silently when a parallel change extends the surface — crossed into a
parametrized test whose expected-outcome column is authored **before the
implementation exists** and run red first. Every cell is a design decision
(accept, or reject with a named diagnostic), so a cell that flips
uncommanded is a regression caught at write time, and a commanded cell that
stays green means the test does not reach the behavior. A cell whose
correct outcome is not yet decided is never guessed into the grid — a
guess pinned by a passing row carries the authority of a decision nobody
made; it goes to the tracker with its guard. An undecided outcome is an
open question, not a coverage gap, and no mark can carry one — `xfail`
asserts a failure nobody has decided on, and `skip` asserts nothing and
goes on asserting nothing.
The grid pins decisions that have been made; it is not a device for making
them. The grid IS the coverage record, so no row of the ledger restates
what it runs.

**Unsure is a legal state everywhere in this process; the silent guess is
not.** Every mandate above names its uncertainty exit: an undecided cell
goes to the tracker with its guard, an open design question to its
open-questions/ file, a
guard that cannot be classified does not land until it can, a review
claim rests at PLAUSIBLE without executed evidence. The imperatives here
prohibit manufactured certainty, never hesitation — a stated "not
decided" with a guard is the process working; a guessed answer wearing a
green row is the defect. The tie-breaker runs the same way: when unsure
whether a gate applies, it applies — the superset is cheap, the guess is
not. The
judgment columns ship as the **completeness ledger** in the grid module's
docstring:

```text
property:        <the guarantee, one line>
domain:          <what is quantified over, and what is deliberately
                  outside it — the boundary stated positively>
registry:        <where each axis is derived in code, and where a property
                  this module leans on is proven elsewhere — locators only>
does not prove:  <what a green here does NOT establish, and why>
```

**`registry:` is the locator row; the other three are claim rows.** Every
entry in it points into code and none of them asserts coverage. Two kinds
of locator live there: where each axis is derived, and — when a property
this module depends on is pinned in another module — that module's test id.
The second is what keeps [maintaining.md](maintaining.md)'s
cross-reference-don't-duplicate rule payable at all: cite the sibling pin
rather than re-copying its enumeration, which is the duplication that
drifts. Write it in locator register, a label and the id with no assertion
verb, because "the partition is pinned at X" is a coverage claim wearing a
pointer's clothes, and no row of this format holds a coverage claim.

The division is by failure mode, which is how prose should be ranked: not
by how likely it is to be wrong but by **what being wrong licenses a reader
not to do.** A wrong claim licenses inaction — a row asserting something is
tested is a reason not to test it, so a stale one leaves a gap open and
says it is closed. A wrong locator sends the reader to a place that is not
there, and `tests/test_ledger_referents.py` reddens on it.

**Only `does not prove:` carries a caution**; the other three state the
guarantee, its scope, and where to look. The row is named for the one thing
it may hold, because a catch-all noun catches all — deferred work, an
uncovered cell, a domain boundary and a designed constraint make four
different demands on a reader, and each has a home that acts on it. A slot
named for what it holds cannot take the others:

| what you have | where it goes | a row? |
|---|---|---|
| Deferred work | the tracker: `issue #N`, cited beside the guard | no |
| An uncovered cell | `skip`/`xfail` in the grid, with its reason | no |
| A domain boundary — nothing missing | `domain:`, stated positively | no |
| A designed constraint — never to be fixed | the spec, or a comment at the construct | no |
| An instrument limit — what a green does *not* prove | `does not prove:` | **yes** |
| Nothing | nothing; omit the row | no |

Three of the six are not instrument limits at all. The slot name does the
sorting, so mis-filing stops at the point of writing rather than at review.

A **history** is none of the six. A residual row often accumulates the
story of how something came to be fixed -- which defects escaped, who found
them, what the fix replaced -- and none of that describes the guarantee
today. Route it the way the rest of the spec is routed: the design it argues
for goes to the construct and is stated there as the design, in the present
tense, never as the story of what it replaced -- a docstring says what the
code does and why it is shaped that way, not what went wrong before. The
narrative goes nowhere ([maintaining.md](maintaining.md), spec not
history). It is
specifically NOT an instrument limit. Writing "a green here is no evidence
about X" because X once went wrong states something false the moment X is
pinned, and the row that says so is read in the present tense.

Deferred work records **beside the guard that makes it loud**, never in a
row — the ledger is not where a reader learns that something is unbuilt, the
refusal is. Where the deferral also *bounds what the module covers*, the
boundary additionally gets its positive sentence in `domain:`, citing the
same issue: a form that has not been written yet is a real limit on the
domain today, and stating it there is not a duplicate of the guard but the
scope it implies. Most deferred work bounds nothing — a cell that ought to
be covered and is not — and inventing a boundary sentence for it would
manufacture a scope limit that does not exist.

Between the two marks, prefer **`xfail(strict=True, raises=...)`**: strict
reddens the moment the cell starts passing, so an implementation that
satisfies the case cannot land unnoticed, and `raises=` keeps a harness
crash from impersonating the designed red. **`skip` runs nothing and says
nothing, forever** — a skipped cell is enumerated-but-never-run, the defect
this section names, wearing a mark. Reserve it for a cell the harness
genuinely *cannot* execute here (an absent optional dependency, a platform
gate): that is a fact about the environment, and it belongs in `domain:`
as a boundary as well. A cell that could run and is merely unwritten is
`xfail`, or it is an issue.

The gate follows the routing: an uncovered cell without both a guard and a
record fails it — the record being the mark's reason or `issue #N` — and a
`does not prove:` row holding deferred work fails it equally, because the
row's name is the thing that was supposed to stop that. "No corpus witness"
is never by itself a reason to leave a cell silent, because corpus-first
governs which mechanisms exist,
not how completely a mechanism covers its own domain — and when the
construct itself has no corpus witness, the change ships a minimal witness
fixture (a complete game exercising the construct end to end): a corpus
hole is an integration blind spot, not an exemption. A guard guards its
whole class at the layer that owns the class: an operand-compatibility rule
lives in the type layer consulted by every comparison-shaped context, not
at the first site that motivated it. The `surface-totality-audit` skill
(`.claude/skills/`) operationalizes this section and "Surface totality" as
a pre-commit gate, including the red-first order (axes -> framing check ->
expected column -> red -> implement -> green) and the
`xfail(strict=True, raises=...)` mechanism — each mark constrained to the
cell's designed failure, so a harness crash cannot impersonate the red
run — that keeps the pre-push checks green while the red-to-green
transition stays visible in the diff.

**Every reference a ledger writes resolves.** A ledger names things — a
test id, a tracked file, a module attribute — and a name goes stale in
silence: a rename moves a test out from under the row citing it, and the
row goes on reading as authoritative forever. A format with no coverage row concentrates
rather than removes this hazard, because the weight it does carry is
locators, and a locator's whole value is that it resolves.
`tests/test_ledger_referents.py` sweeps every completeness ledger in the
tree and holds every reference, in every row, to resolving. What no matcher
reaches is a row naming a real test that does not test what the row says;
that stays the reviewer's, and that module's own ledger records the reach
rather than leaving it implied.

No mechanism polices the prose of the surviving rows, and the reason is
measured rather than assumed. Requiring a quantified sentence to name its
set beside it fires only on ordinary English here: pointed at any row of
this format it flags eight sentences across the tree, all eight of them
correct prose (measured 2026-08-20, 90 ledgers). Prose written to satisfy a matcher is
worse prose, and a row naming its set in good English is the goal, not the
violation. The class ledger keeps its own `covered:` row and the rule with
it — there `members:` is the named set, derived on the line above. The
completeness ledger holds no row a matcher should read.

**Prose names the registry, never the cardinality.** A ledger row — or any
spec sentence — states what it quantifies over, not how many members that
set holds today. "Every registry with a signature table" stays true as
registries are added; "the four registries" is false the moment one is,
and a stale tally is indistinguishable from a fresh one, so it rots in
silence where a broken path or a failing pin would announce itself. That
silence is what makes it the same defect as a row claiming coverage it
does not have, one layer out: the count is a second statement of a fact the code already
holds, and the two drift (`decisions.md` is not exempt from
[maintaining.md](maintaining.md)'s cross-reference-don't-duplicate rule).
Where the set is worth naming, name the registry that defines it — the
prose-only game Shadow Guards are `PROSE_ONLY_TWINS`, not "six Shadow Guards" — so a
reader can count it and a change that grows it cannot leave the sentence
behind. Identifiers in prose carry the same hazard for the same reason:
nothing checks that a backticked name still resolves, so one naming a
deleted registry reads as authoritative forever. Numbers that are facts
about the *domain* rather than the repo — four suits, thirteen ranks, a
two-card trick — are not tallies and are unaffected.

**The test is whether the count can go stale in silence.** A sentence
counting the language's own designed surface — a sub-phase's three exit
forms, the two shapes of a `demands:` clause, the four suits — is safe,
and this rule does not touch it: adding a fourth exit form *is* a spec
edit, so the sentence is revisited by the very change that would falsify
it. What rots is a count of a set that accumulates through routine work —
registry entries, corpus games, deferred cells, review findings — because
nothing about adding one prompts anyone to revisit the prose, and the
count and the set drift apart unwitnessed. Count a designed surface
freely; never count an accumulating one. Read the other way, this rule
applied bluntly would strip the spec of sentences that state the design,
which is the opposite of what it is for.

**Scope is the tense, not the document.** The rule binds any doc making a
present-tense claim about the repo — `docs/`, design notes, and module
docstrings alike — because a reader acts on the present tense wherever it
appears, and a proposal's supporting evidence misleads exactly as a spec
sentence does once it stops being true. The exemption is therefore not a
document class but an explicit date: a measurement framed as a snapshot
(the mutation sweep's operator and seed counts, now carried by issue #109)
is a historical record and stays as written,
because it claims only what was true when it ran. A live claim that would
be correct if dated should be dated, not deleted — the figures are
evidence, and deleting them to satisfy this rule would cost the argument
its support.

An Owner Guard must also speak its **layer's failure channel**: the compile
stages fail as diagnostics (`DiagnosticBag`, with a span and a
designer-readable message — a raw registry raise mid-resolve is loud in
the wrong channel and suppresses every other diagnostic in the file);
the runtime fails as typed exceptions; the proofs fail with a witness.
Loud-but-wrong-layer is a bug with the same rank as silent. "Channel" is
never bare: a game's scoring channels, the observation channel and a
library's feeding channel are different things (see the glossary's
reserved words).

**A check lands only after naming its owner (write-time triage).** Two
tells at edit time mean information is being lost rather than defended:
*re-deriving* a fact an earlier pass already established (re-classifying
a name instead of reading the `ref_kind` the resolver stamped, re-inferring
a type the checker validated, re-computing visibility the zone-type table
declares), and *guarding* a condition that is already checked somewhere
else. Either tell stops the edit — the fix is upstream, not local. Before
it lands, the check is classified as exactly one of three things: an
**Owner Guard** (it moves to the layer that owns the class, in that layer's
failure channel, with a test), a **Shadow Guard** (it stays, and its comment names
the Owner Guard it shadows — and the recorded gap that makes it reachable,
if one exists), or a **missing Owner Guard** (the Owner Guard is built at the owning
layer, and the local site becomes a Shadow Guard citing it). A guard that
cannot say which of the three it is does not land. Each pass states its
contract — what it assumes, what it establishes, and what becomes illegal
after it — in a `Contract` block in its module docstring
(`cardlang/parse.py` through `cardlang/ir.py`); the owning pass's contract
decides where a check belongs. For the runtime packages the triage is
mechanized: `tests/test_assert_triage.py` scrapes every assert-channel
site in `cardlang/runtime/` and `cardlang/stdlib/` and fails the build on
any site whose attached text names neither a dispatch fallthrough nor the
Owner Guard it shadows.

**When an Owner Guard fails or a gap is found, sweep the class before patching
the instance.** A found defect names a class: identify the closed domain
the instance belongs to, probe every other member (the other projection
levels, the other declaration namespaces, the other malformed inputs),
and close or guard the whole class in one change. A lone patch converts a
class defect into a recurring one — the corpus's duplicate-name
shadowing sat for months as exactly this: the duplicate-move-parameter
instance was fixed while duplicate zones, state variables, move types,
and struct types kept shadowing silently until the class was swept. The
sweep binds at find time, not fix time: a *report* of one cell of a
crossable product is an incomplete report — cross the product and report
the pattern, whoever holds the finding.

**The sweep is hardest, and most often skipped, when someone else holds
the finding.** Self-found gaps get swept because finding one already
required asking what the domain was. A finding that ARRIVES — from a
reviewer, a bot, a bug report — arrives pre-scoped, and its scope is the
thing most likely to be wrong about it: it names a line, so the line reads
as the job; it lands while the work is closing a loop rather than opening a
problem; and its specificity reads as a specification, so "at minimum
handle X and Y" gets answered with exactly X and Y. This rule was read and
violated three times in a single branch on exactly that path — each fix
correct about the instance named, silent about the class, and each reopened
by the next reviewer.

Prose did not prevent that, so the rule carries an artifact. A change
answering a finding on a closed-domain mechanism writes a **class ledger**
before the fix — `finding` / `class` / `members` / `covered` / `residual`,
with `members` DERIVED from the registry that defines them (the
`surface-totality-audit` skill owns the form). It cannot be satisfied by
intending to sweep: a `members` line narrower than its own `class` line is
visibly wrong on the page, which is the one thing the exhortation could
never be. State `class` as the position or property — "every way a role id
is consulted" — never as the syntax the finding happened to use, because
the narrow spelling is how the next member escapes. A class of exactly one
member is a legitimate answer; an unexamined class is not.

**A check's comment names the downstream contract, never the downstream
exception type.** A guard is most naturally justified by what goes wrong
without it, and the temptation is to name the crash: "without this guard,
`to each hand[0]` would die on the executor's `NameRef` assert". That
couples the comment to another module's current implementation — the one
detail a reader editing *this* file never sees, and the one most likely to
move. The failure channel is deliberately mobile here: a bare `KeyError`
becomes a typed `RuntimeError`, a Shadow Guard assert becomes an Owner Guard one layer
up. Every comment naming the old type is then confidently wrong while still
reading as precise, which is worse than vague. Name instead what the
downstream layer *requires* — the thing that actually justifies the guard:
"without this guard, it would reach the executor, which requires a zone in
this position and refuses anything else at play time". The warning survives
a change of channel; the coupling does not. The exception type is
load-bearing in two places. The first is an argument *about* the failure channel
("a typed error, not a bare `KeyError`"), where the type is the subject
rather than incidental colour. The second is a type that carries a guard's
ROLE — `OwnerGuardError` and `ShadowGuardError` (glossary/owner-guard.md, glossary/shadow-guard.md) — where
the type IS the classification rather than a report of it. Mobility still runs
in the direction this rule was written for: bare to typed is an upgrade in
specificity, and it stays free. What is no longer free is a guard changing
ROLE, which now changes its type, and deliberately so — a guard moving from
authoritative to redundant, or one layer to another, is a design change, and
the type is what makes it visible instead of silent.

State the consequence in the subjunctive — "would check clean and die" —
not as a past event ("checked clean and died") and not as a present claim
("checks clean and dies"). The past tense is unfalsifiable: it stays
literally true after the behaviour it describes is gone, so it rots into a
misleading implication that nothing can catch. The subjunctive says
something about the code as it stands, which means a reader can check it
and the claim can be found wrong — the same reason guards beat prose
everywhere else in this document.

### Allow-list, never deny-list

A consumer of a closed domain enumerates the members it **handles** and
makes everything else fail loudly. It never enumerates the members it
treats specially and lets the rest fall through to a default. The first is
an allow-list; the second is a deny-list, and a deny-list over a closed
domain is prohibited.

The reason is an asymmetry in what happens when the registry grows, which
is the only moment either shape is tested:

- Under an **allow-list**, a new member breaks every consumer that has not
  been extended, by name, at build time. The cost is a loud failure in
  code someone is already editing.
- Under a **deny-list**, a new member silently acquires the default's
  behaviour at every consumer at once. Nothing fails; the game runs; the
  answer is wrong. The author of the registry change never learns which
  consumers assumed something about the members that existed when they
  were written.

This is not a preference between equally valid styles. A deny-list encodes
"every member I did not name behaves like this one" — a claim about
members that do not exist yet, which no author is in a position to make.

**Enforcement follows the domain's visibility to the type checker.** Where
a closed domain is a Python union, the allow-list is a type error: every
consumer dispatches with a structural `match` ending in
`typing.assert_never`, so under `mypy --strict` adding a node without
handling it everywhere fails to compile (docs/building.md, "Typed-AST
discipline"). Where the domain is a registry of strings — the stdlib
registries — the type checker cannot see it, so a pin substitutes for it:
`tests/test_operand_choke_point.py` requires every operand coercion to
route through one check, deriving its axes from the registry it guards so
it widens with that registry rather than going stale. Visibility is
itself a choice, not a fact of nature: a string domain the checker cannot
see can usually be promoted to one it can (see "Prefer the guard you
cannot need"), and the pin is the right mechanism only where that
promotion is genuinely priced and declined. The domain table's role ids
are the worked example of the promotion: they are `domains.Role`, a plain
`Enum` every consumer dispatches over, so comparing a role against a
string literal is a type error and the marker scrape that used to ask for
a reason is gone. What `tests/test_role_comparison_pin.py` still holds is
the residue the type cannot see — strings that merely SPELL a role
(`player` as an unresolved name, `suit` as a component-set axis) — guarded
per module so a new one must be looked at. A closed
domain with neither an `assert_never` nor a pin is unenforced, whatever
its consumers currently do.

### Pin the derivation, not just the instance

Deriving a fact from a registry is half the rule. The other half is that
the derivation must be **pinned**, because a registry only prevents drift
in the consumers that actually consult it, and nothing stops the next
consumer from re-spelling the fact locally.

The evidence is this repo's own history. `domains.zone_key_of` was
introduced to replace an `== "team"` re-spelling at five consumer sites,
"each of which silently defaulted every non-team role to player keying".
That cleanup fixed five instances and left no guard — so the class
regenerated: a per-site enumeration of Player positions with no pin (the
positions the enumeration missed went unchecked), an empty team domain read
as an unknown bound (the check skipped itself), and a sixth `== "team"` in
a new consumer (every future role read as player-keyed). Three findings,
one shape — the deny-list above, three times. Five separate files carry
comments narrating earlier rounds of the same cleanup, which is what a
convention without a mechanism looks like.

So a closed domain gets both halves:

- **Derive** the fact from the registry wherever a consumer can.
- **Pin** it where a consumer cannot. A consumer that legitimately
  implements one row reconciles itself against the registry beside the
  branch, so widening the table fails *there*, by name —
  `runtime/execute.py` pins its player-only simultaneous executor against
  `SIMULTANEOUS_ROLES`; `resolve` pins its empty-domain guards against
  `ZONE_INDEX_ROLES`; `runtime/mechanics.py` pins the auction form's single
  traversal against `ROUND_ORDER_MODES`; `openspiel/replay` pins its returns
  keying against the same set as `resolve` and raises for a role it cannot invert, exactly as
  `domains.zone_observer_key` does rather than guessing player keying.
  The practising sites are enumerated in code, not here: the census in
  `tests/test_registry_guard_witnesses.py` derives them and demands a witness
  for each, so a site added without one fails there rather than going unlisted.

**The boundary is closed versus open, and it is load-bearing.** Everything
above applies to a domain whose membership is enumerable — a union, a
registry, a table. Over an OPEN domain the same shape is a defect in the
other direction: an allow-list there would refuse values the language is
deliberately permissive about, and a guard that manufactures an error is
exactly what the gradual-typing promise forbids (see "`Any` means the top,
never a failed lookup", which owns that case — `TAny` passes, and a
*lookup miss* against a table the program does have raises rather than
falling back). The two rules meet at the same principle: a fallback
standing in for an answer the program could have looked up is a silent
wrong answer. Deciding which side a domain sits on is therefore the first
question, not an afterthought — and "unsure" resolves to closed, because
an unnecessary loud failure is cheap and a silent default is not.

### Prefer the guard you cannot need

Enforcement has a ladder, and each rung down costs more to hold:

1. **Unrepresentable** — the illegal state cannot be written: a union the
   type checker dispatches over, a grammar that cannot produce the
   combination, a fact derived from one defining site so a second copy
   cannot exist.
2. **Derived and pinned** — the fact has one source; consumers derive from
   it, and a pin catches the consumer that re-spells it.
3. **A born-green pin with its witness** — behavior already correct,
   guarded by a check that names its reddening mutation.
4. **Review-enforced prose** — an authoring rule, held by whoever happens
   to read it.

Every claim on a lower rung is machinery that must itself be kept honest —
markers need reasons, reasons need vocabularies, scrapes need manifests —
and that maintenance is where enforcement findings breed. So a proposed
pin carries one more line in its ledger: **why the fact cannot live a rung
higher.** "The domain is strings the checker cannot see" is an answer only
after asking whether the strings should be a union the checker can see —
a registry of role ids is a closed domain by definition, which is exactly
the shape an enum holds for free. A pin whose fact could have been a type
is built on the wrong rung, and the findings it later generates are the
interest on that choice.

The rung is a design decision and gets recorded like one: when rung 3 or 4
is chosen over an available rung 1 or 2, the ledger says why (a subtype
relation the type system deliberately lacks, a migration priced and
deferred with its tracker record) — so the next reader finds a decision,
not a default.

### The machinery is guarded once

These rules bind the shipping surface — grammar, checker, registries,
runtime, the adapter — and the rigor-critical machinery the
information-set guarantee rests on: the proof harness, the projections,
the encodings, the invariants. For those, completeness is measured against
the domain, as this whole section says.

Enforcement *scaffolding* — the pins, scrapes, hygiene tests, and audit
tooling built to hold the rules above — is a different case, and the
difference is load-bearing: every layer of guarding is itself a closed
domain, so applying this section to its own machinery recurses without a
base case, and each layer added is new surface for the next audit to find
wanting. The base case is: **scaffolding carries exactly one level of
guarding** — a grid's red run, a pin's `red under:` witness — and receives
no preemptive machinery of its own. A defect *in* scaffolding is fixed
when it bites (a finding it should have caught and did not), or in a named
integrity sweep with its own scope, and is filed with its reachability
stated — never as routine finding fodder. This is corpus-first applied to
the machine: the witness for meta-machinery is a failure, and waiting for
it is cheap because the shipping surface underneath is still guarded.

The test for which side something is on: if it fails silently, is a wrong
game trusted, or a wrong *audit* trusted? The first is rigor-critical.
The second is scaffolding.

The cap prices the process as well as the artifacts. A change wholly on
the scaffolding side of that test — no refusal, no runtime step, no proof
obligation changes — still ships its grid, but takes one review round and
no standalone adversarial claim-audit. The full cadence is reserved for
deltas a designer, the corpus, or a proof can meet. Scaffolding misjudged
is caught the way scaffolding is guarded: when it bites.

### Reachability ranks the work

Severity says what kind of defect; reachability says who can meet it.
Every finding, uncovered cell, and tracker issue states one:

- **R1 — corpus-reachable.** A game in `docs/games/` (or anything trained
  or proven against one) meets it today.
- **R2 — designer-reachable.** A checker-green sentence a designer could
  plausibly write meets it. The design-tool promise binds here: R2 silence
  is how a designer ships a wrong game.
- **R3 — witness-gated.** Reaching it requires surface the language does
  not yet accept — a cell deferred behind a guard, lifted only when its
  named witness lands. A construct that is accepted today but unused by
  the corpus is R2, not R3: the corpus gates which mechanisms exist, not
  what a designer may write.
- **R4 — auditor-only.** Reaching it requires planting a mutation,
  widening a registry, or editing the machinery itself.

The tags are exclusive by precedence: assign the lowest-numbered tag
whose condition holds — reachability names the *closest* party who can
meet the defect, never the typical one.

The tag names who can TRIGGER the defect, never who ultimately suffers
it. Every defect in a design tool eventually reaches a designer, so
transitive harm raises no tag — reasoned transitively, everything is R2
and the axis orders nothing. And the tag ranks reach, not worth: a
bitten R4 can sit at the top of the ordering while a speculative R2
waits, so R4 is a fact about who can meet the cell, never a demotion of
the work that closes it.

Disposition follows the tag: R1 is fixed now; R2 is fixed or filed with a
kind; R3 is a marked cell with its guard and its record, per the gate
above; R4 is recorded in the owning ledger and files an issue only when the
guarded guarantee is rigor-critical. And effort follows it the same way:
a fix whose size is out of proportion to its reachability routes to
record-and-file, not to fix-now — the proportionality call is made in
planning, out loud, not discovered in review.

## Family libraries

A **library** is the import tier between game-local definitions and the stdlib.
It holds exactly the definition forms a game already holds — move_types, rules,
functions, procedures, types, defines — plus the two state clauses `state` and
`requires`, and it lives in
`docs/libraries/<name>.cardlang`, beside the corpus and maintained with it. The
stdlib is the part maintained with the *language*; that boundary is the one
[design-notes/primitive-sidecars.md](design-notes/primitive-sidecars.md) exists
to defend, and the tier exists so a family of related games need neither paste
shared machinery per game nor promote domain knowledge into the stdlib.

A game names one whole library at a time:

```text
game SevenCardStud {
  uses poker_betting
  ...
}
```

Whole-library, never a named-definitions manifest: the line stands in for the
rulebook sentence it replaces ("betting proceeds as in standard poker" is
Pagat's own practice), and that is what keeps the read-cold acceptance test
intact — the readable unit becomes the game file plus its *named* libraries. A
game may `uses` several libraries; repeating one is an error, because the
repeat imports nothing further.

Resolution is flat and two-level: game, then the named libraries, then the
stdlib. There is no library-imports-library. Imports are pure name resolution —
`resolve` splices each named library's definitions into the game before any
other name check runs, so what flows on is one flat game and no later pass knows
imports exist. That is what makes an import carry no runtime and no
information-set implication, and the splice is the whole of the reason: nothing
is added, and the game's own declarations are what run. In particular it is NOT
because a library cannot name a zone. A contract can name one, and a zone type
fixes the per-observer projection, so a library CAN say what its definitions
were written against — `HiddenPile` rather than `PublicHand`. That constrains
which games may import it; it changes nothing about the game that does.

**`uses` imports; it does not inherit.** A game-local definition under an
imported name is an error, not an override, and so is the same name from two
libraries. Import-with-override would make the tier inheritance, and would put a
game's meaning at the mercy of a silent redefinition — the accepted-but-ignored
defect class at file granularity. Nor is there a second, override-shaped
mechanism waiting behind it: there is no variant-delta construct and will not be
one ([principles.md](principles.md), "Composition over inheritance"). Variants
are sibling games over a shared core, which is this tier — so `uses` is not one
of two ways to relate games, it is the way, and the no-override rule is
unconditional rather than provisional.

That decision sets the open question for this tier: **what may a library
contain?** Siblings can only share what a library can hold, so anything two
variants have in common and a library cannot express comes back as duplication.
Today a library holds definitions (move types, rules, functions, procedures,
types, defines) and state, and no other game structure. Poker forced state; a
pair of variants sharing a phase tree would force phases. Grow it corpus-first,
one forcing game at a time — but do not describe a library as "a vocabulary, not
a game", because that framing assumed a delta mechanism would cover the rest, and
none is coming.

**State reaches a library two ways, and the difference is ownership.** A library
`requires` state the including GAME owns, and `state`s the state the LIBRARY
owns. Both are checked at the `uses` line, so an unmet contract or a collision
is reported to the game's author rather than as an undeclared name inside
spliced library text they never typed.

```text
requires {
  stack[player] : Integer   // the game declares it, sets it, writes it
  raise_cap     : Integer
}

state {
  acted[player] : Boolean = false   // the library's own; the game may read it
  limit         : Integer = 0
}
```

`requires` is deliberately a `state_decl` minus the `= <default>`: the initial
value is the game's to choose, and a library that could set one would be
configuring the game rather than contracting with it. Provided `state` carries
its default for the mirror-image reason — the library owns the variable, so it
owns the value the variable starts at.

**Provided state is read-only to the game.** It splices into the game's own
`state { }` and the game may read it, but an assignment from game text is an
error, reported in the GAME (the game's author wrote the assignment) and naming
both the variable and the library that owns it. The rule is what makes
"provided" mean anything: a variable the library maintains and the game may also
write is not owned by either, and the library's invariants over it would hold
only by the game's good manners. It is enforced across every write form the
language has — `:=`/`+=`/`-=`, `rotate`, and a `turns … again <flag>`, whose flag
the runtime clears at each turn boundary — because a rule that covered only the
obvious one would be two thirds of a guarantee.

**Nor may the game shadow provided state with a name of its own.** Read-only
governs writing; this governs reading. A binder or a declaration parameter the
game introduces — `for each player limit:`, `function f(limit : Integer)`, a
`let`, a `produces:` payload, a struct field — may not be spelled like a
provided variable, because wherever that name is in scope the bare word is the
binder and the provided variable cannot be read there at all. A struct field is
in the list for a narrower reason and the rule keeps it deliberately: its scope
is the type's `derived { }` bodies, so a struct without one scopes the spelling
nowhere, and the refusal is the conservative one — adding a single derived field
makes the shadow live, and the author who would add it is the one who cannot see
the other half. It is the same visibility
asymmetry the injection rule below turns on, arriving from the other side: the
base language lets a binder shadow a same-named declaration precisely because
the author wrote both and can see both, and that reasoning does not survive a
declaration in a file they never open. A name the library merely `requires`
stays shadowable — the game declared it, so the author did write both. So does a
spelling the game already binds at declaration level, which the injection rule
refuses first: one clash draws one refusal.

Which fix the refusal prescribes follows the binder, and turns on one question:
is the spelling the author's to choose? Where they picked it, renaming the binder
is the fix. Where they did not — `any player where` always binds `player`, an
aggregation always binds `card`, a transfer filter binds the game's content noun
— there is nothing at the refusal site to rename, so the library's variable is
what must change instead. Both are reported in the GAME, which is where the
shadow is written and the file the author has open.

A Primitive's parameters are the one declaration parameters the rule does not
reach, and not by exemption: they label the Python signature and key the entry's
`reads` binders, so no DSL text sits inside their scope and there is nothing for
them to shadow.

**A provided default may not read the contract.** Provided state splices in
front of the game's own, so a `requires` name — which only the game can declare
— is never in scope where a provided default runs. This is the declare-order
rule of "State scoping (lexical)" landing on the tier, and the general guard
would catch it after the splice; it is refused before the splice as well,
against the library alone, because the splice destroys the distinction the
author needs. Post-splice a required name is just a variable declared later,
and "declare it earlier" is advice a library author cannot take. Give the
provided variable a literal default and set it from the contract in a phase.

**A contract names state or zones, and the type says which.** A `requires`
entry's type is read against two registries — the state types, and the stdlib
zone types — and they are disjoint, so which of the game's declaring blocks
answers an entry is derived rather than declared:

```text
requires {
  hand[player]      : Hand<player>        // answered from the game's `zones { }`
  shipment[player]  : HiddenPile<player>
  merchant          : Player              // answered from its `state { }`
  raise_cap         : Integer
}
```

The two spellings do not cross. A zone type carries the `<owner>` argument and
never a `?`; a state type carries the `?` and never an argument. Both crosses
are refused against the LIBRARY ALONE, before any game is consulted, because
they name a shape no `zones { }` or `state { }` line could answer — as are an
owner argument disagreeing with the index, an owned zone type with no index, and
an index that is a position domain rather than a seat or team. A library
declares no `positions { }` and cannot name one, so a position-indexed zone
family cannot be contracted at all.

That the derivation IS a derivation rests on a guard: a declared `type` and a
per-game `positions { }` name may not take a kernel zone type's spelling. Without
it `type Hand = { … }` would make `requires { x : Hand }` mean two things, and
the classification would silently pick one.

A contracted zone is the game's zone. The game declares it, writes it, and owns
its projection; the contract only says which shape the library's definitions were
written against. That is the reverse of provided state, and deliberately so —
there are no library-owned zones, because every zone a family shares is written
by game text somewhere (a deal, a settlement, a game-local move), and a variable
the library owns and the game may also write is owned by neither.

**There is no visibility system beyond this, and that is a decision, not a
gap.** No `private`/`public` marker on a definition, no export list, no scoped
namespace. Two surveys over the two multi-member families in hand measured what
sharing actually needs (recorded under "The evidence" below), and read-only
provided state plus ordinary procedures covered every case: the variables no
game reads become the library's, the boundary writes that remain become a
procedure the game runs. Nothing in either family wanted a definition hidden
from its importer. Adding a marker system now would be designing against
imagined pressure, and this paragraph exists so the question is not silently
reopened — reopen it when a family produces a case these two mechanisms cannot
express, and name that case.

A requirement's own index is checked first, and reported to the LIBRARY's author:
`requires { seen[rank] : Integer }` is refused where the library wrote it,
because an index must be a role a state variable can be keyed by
(player/team) and no game could answer such a requirement. That is the
library Shadow Guard of the state-index guard, and the difference is
who can fix it — an unmet contract is a fact about the importing game, a
malformed index is wrong in the library's own text. A mismatch between a
well-formed requirement and the game's declaration names both roles
(`per-team` against `per-player`), never the presence or absence of an
index.

What the `requires` contract checks is that **exactly one**
declaration of the name exists somewhere in the game, at the library's arity and
type. Which `state { }` block holds it is not checked: a phase's block is the
natural home for state that resets on phase re-entry, which is what per-hand
betting state is, and Seven-Card Stud declares all seven of `poker_betting`'s
requirements inside `phase play`. That is weaker than "the library's definitions
can read it where they run" — a declaration in a phase the library never runs in
satisfies the contract and then fails at play time — and the shortfall is not the
import tier's to close: a plain game with no library reproduces it, one phase
declaring what another reads. It is recorded in issue #138.

Cross-block shadowing is legal for game-private state and refused for a
`requires`d name: the two shadowed declarations answer different questions, and
no fixed tie-break picks correctly, since a shadow in the phase where the
library's definitions run and a shadow in some other phase want opposite winners.
Because the spelling is the interface, a `requires`d name is not game-private:
the metamorphic rename transform excludes it for the same reason.

**The contract is meant to be sufficient, not advisory.** A library's
definitions may reach only its `requires` contract, its own definitions, the
stdlib, and the pronouns and binders any body has anyway — checked against the
library alone, before any game is consulted. Without that the contract would be
a suggestion: a body reading past it resolves against a game that happens to
declare the extra name and fails against a game meeting the contract in full,
reporting an unresolved-name error inside library text the game's author never
wrote. That is the misaddressed failure `requires` exists to prevent, arriving by
the back door, and it is why the check reports to the LIBRARY's author — the
library author is the only one who can fix it. The same rule makes a library
deck-agnostic: it names no rank, no suit and no card, because those exist only
once an including game names a deck, and a family's members do not share one
(Kuhn's holds three cards).

The check enforces this for every name the resolver classifies **and** for every
name a construct holds as a bare string instead — a `turns … again <var>`, a
`round`'s source and play zones, a struct type name, `state.<var>`. The second
half runs off the **reference-slot registry**: one table classifying every
string-typed field of every AST node as a declaration, a binder, a reference
into a named namespace, a keyword, opaque text, a classified name, or pass
metadata. The table's key set is derived from the AST and pinned to it, so a
field added to a node is classified or the build fails; what each slot MEANS is
authored, because no annotation carries it.

The registry is what makes the boundary statable. A namespace a library can
reach is either swept against what the library itself has, or carries a written
reason why reaching it is not a channel — a closed kernel table or domain registry
identical either side, or a name owned by a declaration that IS swept. There is
no third state, and no consumer keeps a list of the slots it remembered.

**Name collisions on state are guarded the same way collisions on definitions
are.** A library may not both provide and require one name — the two clauses
point opposite ways, so no reading satisfies both. Two libraries may not provide
one name, because resolution is flat and picking by `uses` order would make a
game's meaning depend on the order of its import lines. A game may not declare
what a library provides: that is the state face of "`uses` imports, it does not
inherit". And a requirement is answered by the game's own declaration, never by
another library's provision, which would couple two libraries through a name
neither mentions the other in. Two libraries requiring the same name is fine —
one game declaration answers both contracts.

**A library may not inject a name the game already uses for anything — in any
namespace, not just the same kind.** The collision guards above catch a library
definition landing on a game definition of the SAME kind (function over
function) and a provided name landing on the game's own state. The remaining
cases are the silent ones: a provided name, or a library definition, coinciding
with the game's zone, a suit or rank or direction value of its deck, a position
domain, or a definition of a DIFFERENT kind. Each is a trap because a `uses`
import adds names without overriding and the game's author never opens the
library file — so a bare `hearts` the author writes meaning the suit resolves to
the library's variable instead, or a `pile` they declared as a zone is shadowed
by a provided one they cannot see. This is where the tier parts company with the
base language, which lets a GAME reuse one name across its own namespaces: there
the author wrote and can see both declarations, and the precedence that resolves
the reference is theirs to know. The refusal is deliberately conservative — a
coincidence is refused even where precedence would make it harmless — because the
rule a designer must hold is "a library may not bring in a name you already use",
not a table of safe pairs. It is reported naming the library, since that is the
half the author cannot see. The game-level face of the same clash is left to
the author deliberately, and is not deferred work: `state { pile }` beside
`zones { pile }`, a state variable spelled like a suit, or a function named
after a rank all resolve by `_classify`'s precedence (state variable over
zone over deck value over function), which makes the loser unreachable by
that spelling with no diagnostic. That is the ordinary block shadowing every
language allows, and a game-level uniqueness rule would be a far larger,
higher-risk change than the corpus has forced. The library guard turns on
INVISIBILITY — a name the author cannot see — so it would be wrong to apply
to names they wrote; if a designer is ever surprised by their own
cross-namespace shadow, the fix is to lift the same sweep to the game's own
declarations and measure the corpus cost.

**What a library holds, and what stays game-local.** A library holds definitions
and the state its definitions own — but no zones and no phases — because that is
as far as the corpus has forced it, not because a library is a lesser kind of
thing than a game. The boundary moves as sibling games need to share more.
Within today's boundary the corpus forced a sharper line, and the line is about
VARIATION rather than about zones: **the move that differs across the family
stays game-local; the library holds what every member holds identically.**

`poker_betting` holds check, bet, call, raise and the `can_act`/`owes`/`pending`
ring predicates — all of which move chips and nothing else, over the reading of
`acted` in "Named functions" above — and omits `fold`,
the one betting move that touches cards. Which cards a fold disposes of, and
where they go, is a property of the game: Stud sends the folder's upcards to the
muck the instant they fold, and opponents' information sets carry that
observation. Each game defines its own `fold` and offers it alongside the
imported four in one vocabulary list.

`smuggling` draws the same line one family over, and the measurement is what
draws it. Across the twelve smuggling files `commit_shipment` and `wave` are
byte-identical and both move cards, so both are in the library; `inspect` has ten
distinct bodies and is game-local. Those ten decompose into three orthogonal
deltas — the fine (a per-game constant), the contraband predicate (a card
predicate), and the bounty (an added statement) — and only the first is
something a declaration could carry. So "touches a zone" was never the criterion:
a move touching a CONTRACTED zone belongs in the library, and a move that varies
does not, however zone-free it is.

**Parameterization rides on state and on procedure arguments, not on the
import.** Family members differ by constants, and where the constant lives
follows what it is a property of. A per-GAME constant is required state the game
declares: Stud allows three raises per street and Leduc two, so `raise_cap` is
`requires`d. A per-OCCASION constant belongs to the occasion, so it is a
procedure argument: a poker bet size is a property of a street, not of a game
(Stud runs 5/5/10/10/10), so `limit` is provided state that the library's
`open_street(bet_size)` sets, and each street names its own size where the street
is written. Neither difference reaches the import surface, which stays a bare
name.

The test for which of the two a constant is: could one declaration in the game
carry it? `raise_cap` yes, `limit` no. A value that varies within a game was
never a declaration's to hold, and making it one is how `limit := 5` came to be
repeated at five sites that were otherwise identical.

**A second family was measured against this rule and did not break it, but it
did narrow what the rule is about.** The smuggling family's members differ in
three ways, and only one is parameterization at all: a fine (a per-game
constant, which required state carries), a contraband predicate, and an added
statement. The last two are not constants of any kind, so no clause on the
import would carry them either — a `with` clause is not what that family wants.
What it wants, if anything, is a contract over DEFINITIONS: a required function
would let the varying predicate be the game's while the move stayed shared, and
a required move type would let the family share the offer step that is already
byte-identical in every member. That is issue #189, and it is a different
question from #178's — a definition is a NAME, in a namespace `requires` does
not reach, where #178 asks whether a contract can express a capability at all.
Recorded here so the next reader does not re-derive a `with` clause from the
same evidence.

**A member offers a subset of the family vocabulary, at no cost.** Importing a
library is not a commitment to use all of it: Kuhn's `offering` list is
`[check, bet, call, fold]`, so the imported `raise` is never offered — standard
Kuhn has no raise. That costs nothing at the OpenSpiel target, because the
action space is derived from the `offering` / `offer` lists, never from the
game's move-type table, so an imported-but-unoffered move type mints no action
id and cannot widen `num_distinct_actions`. This is what makes whole-library
import affordable for a small family member, and it is pinned rather than
assumed (`tests/openspiel_ready/test_kuhn_poker.py`). It is not a licence to
leave a move type dead by accident: a game's own definitions are still subject
to the ordinary totality rule above — the exemption is for *imported* text the
author did not write, whose unused parts are the price of naming a family
rather than a manifest.

**The evidence.** Two surveys sized what a library must hold, and they are
recorded here because the shape of this tier is an empirical claim rather than a
deduction.

*Survey 1, over the three poker games.* Every game write to `poker_betting`'s
state is at a street boundary, with one exception: `folded`, written mid-street
by each game's own `fold`. Four of the nine required variables — `acted`,
`raises`, `limit`, `raise_cap` — were never READ by any of the three games. (Nine is what the
contract held then; it holds seven now, which is what the survey bought.) And
all five street-reset sites (one in Leduc, four in Stud) were one shape differing
in a single integer. That is what forced provided state and `open_street`: writes
that cluster at boundaries are absorbable by a procedure, and a variable no game
reads or writes has no business in a contract. Only two of the four moved,
though, and the two that did not are as informative as the two that did —
`raise_cap` is a per-game constant so no single provided default fits it, and
Stud's bring-in genuinely writes `raises`, a boundary write no *shared* procedure
absorbs because only one game in the family has a bring-in.

*Survey 2, over the smuggling family* (`experiments/green-lane/`, an experiment
rather than corpus). Run as a survey first and then EXECUTED, and the two
answers differ, which is why the executed one is what stands.

The survey said the shared material a library could not hold was irreducibly
zones plus state declarations. Building the library found the first half was a
missing mechanism rather than a boundary — hence zone contracts — and the second
half stands: state declarations are shared by being contracted, never by being
held, so each member still writes its own.

What the build measured, over all twelve files: `zones { }`, `commit_shipment`
and `wave` are byte-identical everywhere; `state { }` varies in one default and
one added variable; `phase play` varies in two lines; `phase scoring` in four;
and `inspect` has ten bodies. The library ends up holding the commit, the wave
and a four-entry contract — about an eighth of each file. The family shares
roughly nine tenths of its text, so **most of what these siblings have in common
is material this tier cannot hold at all**: zones (contracted, not shared),
state declarations (likewise), the phase tree, and the varying move.

Phases were NOT forced, and for a reason worth keeping: the shared phase material
reduced to statements a procedure covers. A separate constraint capped how far
that goes — a procedure may not invoke another (expansion is a single splice,
not a call graph) — so shared material reachable only from inside a game's own
procedure has to be lifted to a phase to be shareable at all.

The second survey carries a caveat that bounds how far it generalizes. Green
Lane's variants are a **delta lattice** — v4 is v1 composed with v3, and each
delta edits disjoint rule text — so the family shares a great deal by
construction. A family whose members are siblings rather than deltas may share a
different *shape* of material. Read Survey 2 as "phases were not forced by this
family", not as "phases are settled".

The tier's completeness gate is `tests/test_family_libraries.py`, whose ledger
records the one deliberate non-cell: kernel move types and a game's `move_type`
definitions are disjoint consult paths that never share a namespace, so there is
no collision there to guard against.
