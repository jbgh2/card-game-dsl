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
[open-questions/move-parameter-domains.md](../open-questions/move-parameter-domains.md)).
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

**Enumeration surfaces.** An `offer` statement — on its own or as a ring's
turn ("Auctions, polls and betting rings are `turns` plus `offer`," above)
— enumerates a parameterized move type the same way: every combination of its
declared domain(s), guard-filtered, folded into **one flat candidate list**
resolved by a single decision — one chooser draw, one public announce —
never an outer move-type choice followed by an inner parameter choice. Go
Fish's `ask(target : Player, rank : Rank)` is offered this way via a plain
`offer`: the declared domain is the full 4 × 13 seat-by-rank cross-product,
and the guards ("not yourself", "a rank you currently hold") mask it down,
per state, to whichever pairs are actually legal for whoever is on turn
([games/go-fish.md](../games/go-fish.md)).

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
value has no id. A **negative literal upper bound** (`n .. -1`) is rejected
whatever `lo` is: the block reserves no id at all. A runtime `lo` is not
statically decidable and is left to the runtime guard. At runtime the *range* is guarded
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
([open-questions/move-parameter-domains.md](../open-questions/move-parameter-domains.md)).
