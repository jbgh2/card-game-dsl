## Trick Order

A trick's resolution and its follow legality both rest on three facts about
each card: is it a **trump**, what **class** does it follow as, and how
**strong** is it within that class. In a plain game those fall out of the
card's printed fields and the trump suit the round names. In the big European games they
do not: Doppelkopf's queens and jacks are trumps whatever suit they are
printed, Skat's jacks likewise, 500's joker and left bower are members of a
trump suit they are not printed in, Belote reorders the ranks WITHIN its
trump suit alone, and French Tarot's Excuse belongs to no class at all. A game whose answer differs from the printed one declares it, as three functions:

```cardlang-fragment trick_order
function is_trump(card : Card) = card.rank is Q or card.rank is J or card.suit is diamonds
function follow_class(card : Card) = if card.rank is Q then none else card.suit
function card_strength(card : Card) = if card.rank is Q then 200 else rank_value(card)
```

The three are **Kernel Definition Contracts**: signatures the kernel states
and only the game answers, by writing `function <name>` with the contract's
signature — the shape a family library's `requires` row has, with the kernel
as the party requiring. The game answers by the name alone, with no marker;
the signature check does the work a marker would. A game states its order
once, and every consumer reads that statement rather than a second copy of it.
The order has this one spelling. A block of rows over an implicit `card`
would be a second spelling of the same three answers, one a designer learns
twice and every refusal speaks in two voices, so a `trick_order { }` block is
refused naming the three functions, and a game-level `trump:` is refused
naming the round's `trump` clause and `is_trump`. ADR-0007 records the
ruling, the block that lost and the table that stays.

**The contracts.** `is_trump(card : Card) : Boolean` has no default: a game
with a Trick Order answers it, and one with no trumps writes
`function is_trump(card : Card) = false`, so the absence is stated rather than
inferred. Answering it is what declares a Trick Order. `follow_class(card :
Card) : Suit?`, where `none` means class-less — a card that neither sets the
lead nor wins — defaults to the card's printed suit. `card_strength(card :
Card) : Integer`, higher beating lower, defaults to `rank_value(card)`, which
reads `ranking:`; a game taking that default without declaring a `ranking:`
is refused. Both defaults are applied once, when the game loads. An answer
takes exactly one Card and returns exactly the contract's type: Boolean and
Integer compare by equality, so no optional slips in, and the permissive top
is refused. An answer to `follow_class` or `card_strength` in a game that
answers no `is_trump` is refused, naming `= false`.

The functions may be written in any order. The order they are READ in is the
language's — `is_trump`, then `follow_class`, then `card_strength` — and each
may call the ones before it only. So `card_strength` may ask `is_trump(c)`,
and `is_trump` may not ask `card_strength(c)`; the reference order is a
property of the language, never of how a designer happened to arrange the
text.

**Answers are hermetic.** An answer is asked from several places under
different live frames: the legality filter mid-decision, the winner slot at
the end of a trick, any hand-rolled body, and the end-of-game card census. An
answer that varied with the asker would not be a fact about the card, so an
answer may read no pronoun of any namespace, make no `choose`, read no zone
that is not fully public and no per-player zone without naming whose, read no
state but the game's own `state { }`, and call only the Builtins that are
pure over their arguments. Each refusal follows the call graph, so an answer
that reaches the forbidden thing through a designer function is refused with
the function named. This is what makes a Trick Order a public fact, and
therefore information-set-safe: nothing it computes can depend on what any
one player knows. The same law holds for the fourth contract,
`card_points` ("Scoring has no constructs of its own").

**Two registries, never meeting.** The native names split in two. A
**Builtin** is the language's own definition, and a game may never define a
callable Builtin's name; a value Builtin's name (a trick winner a round's
slot names) is refused to a game function where one of the game's own round
slots names it ("Named functions"). A **Kernel Definition Contract** is never
the language's to define and always the game's to answer. The two registries
are pinned disjoint, and a family library may define no contract's name: a
library that needs the fact writes the contract's row in its `requires`.

**Two Builtins over the Trick Order.** `highest_by_trick_order` is the winner.
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
vocabulary, or declares none and uses the round-configured one. With a Trick
Order, a round's `trump` clause, every other
trick winner and `highest_trump_or_led_suit(...)` are all refused — each
describes a different order from the one the Trick Order declares, and
admitting both would leave the engine quietly running one of them. Without
one, every gated name — the two Builtins and the three contracts' names — is
refused, because it would read an order the game never declared. A Trick
Order that nothing reads is refused too ("Surface totality", "A clause
nothing reads is refused"); its own three answers are one clause, and never
each other's readers. The round-configured order states its trump as
`is_trump` does: a round whose winner reads a trump
(`highest_trump_or_led_suit`) names it in its own `trump` clause, and a
round without one is refused, wherever it is written, since it would play
no-trump without saying so; a library names no suit, so its round names one the
game supplies through the library's `requires`. A no-trump trick names a winner
that reads none.

**Provenance.** Every Arrival Record read names a fully public zone,
statically: the pile argument of each of these calls is a zone reference whose
declared type projects identity to every observer, and every trick round plays
into such a zone. A winner is named from who played what, so the pile it reads
must be one whose arrivals every observer can derive from their own
observation stream ("The Arrival Record").
