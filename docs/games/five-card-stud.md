# Five-Card Stud

The companion formal file is [five-card-stud.cardlang](five-card-stud.cardlang);
this is the readable twin. Five-Card Stud in the **formal casino form**, fixed
limit. Source: [Pagat](https://www.pagat.com/poker/variants/5stud.html).
**Players:** 3. **Deck:** standard 52. **Chips:** one unit is $0.50, so Pagat's
$0.50 / $2 / $5 / $10 example ladder is exactly ante 1, bring-in 4, small bet
10, big bet 20. Each player starts with 200 units ($100).

Each hand:

1. Every player antes 1. Deal each player one card face **down** — the hole card
   — and one face **up**.
2. **First betting round**, at the small bet. The lowest up card (ties by suit,
   clubs low through spades high) **brings in** for 4, which is short of the
   street's own size. The poster then holds the round's first decision, and it
   is a real one: stand on the compulsory minimum, or **complete** to a full
   small bet of 10. Completing does not add 10 to the post — the bet climbs to
   the street's size, so the ladder is 4 / 10 / 20, not 4 / 14 / 24.
   - If the poster stands on 4, everyone behind may complete to 10, call the 4,
     or fold. Only once someone completes may anyone raise.
   - If the poster completes to 10, everyone behind may raise straight away.
3. Deal a third card face up. **Second betting round.** It is at the small bet
   unless any player shows **a pair or better**, and then the big bet becomes
   available too — to *everyone*, including players holding no pair. Both sizes
   are legal on such a street; see the departures below for the one the file
   cannot offer.
4. Deal a fourth card face up. **Third betting round**, at the big bet.
5. Deal a fifth card face up. **Fourth betting round**, at the big bet.
6. **Showdown** — the best five-card poker hand among the remaining players wins
   the pot, with side pots when players are all-in. If everyone but one player
   folds, that player takes the pot without showing the hole card.

Each betting round after the first is opened by **the best hand showing**, and
that is poker order over the up cards, not the highest card: pairs, trips, two
pair and quads count normally, so with three cards showing 3-3-3 opens ahead of
7-7-8, which opens ahead of A-K-Q. Incomplete straights and flushes do not count
at all. Ties break on the suit of the highest card.

Every round allows **one bet and three raises**, except heads-up, where the
rules cap nothing.

## Where this file departs from Pagat

Pagat's base text is the traditional home game and marks the casino rules as
departures from it. This file is the casino form throughout, which is one choice
made in three places the page names:

- the compulsory bring-in opens the first round ("now the normal rule in formal
  games hosted by American casinos") rather than the best hand showing opening
  every round;
- the last two rounds are big bets only ("the normal rule in casino hosted
  games, but not in home poker games");
- once a big bet is placed, the raises answering it are big too ("only big
  raises are allowed in that round") — the page offers the looser home rule, a
  small raise answering a big bet, as the alternative.

The fifth card is dealt **face up**, which is the page's base text. Dealing it
face down is one of the page's Variations and is a different game; so are
Lowball, High-Low, High-Low with a Buy and Sökö.

There is **no burn card** and **no dealer button**: the page has neither, and
nothing in the game reads a button, since every street's opener is chosen from
the up cards and the deck is shuffled whole each hand.

Two rules the file **cannot state**, and it is the witness for both.

The **heads-up raise cap**. Pagat caps a round at one bet and three raises "if
there were more than two active players at the start of the betting round" — so
heads-up the round is uncapped, and `raise_cap` is an Integer with no way to say
"no cap". The file writes a bound no street can reach and derives it in a
comment. The betting is identical; what is missing is the ability to say what
the rule says.
[Issue #635](https://github.com/jbgh2/card-game-dsl/issues/635) is that gap.

The **small bet on an open-pair street**. When a pair shows, Pagat *allows* the
big bet rather than requiring it, so a seat may still open for the small one —
which is why the page goes on to say what happens "after a player places a big
bet". A street in this language opens at one size, so the conditional makes the
big bet the street's only size, and the seat that would bet small into an open
pair cannot. [Issue #648](https://github.com/jbgh2/card-game-dsl/issues/648) is
that gap. It is the same shortfall
[#546](https://github.com/jbgh2/card-game-dsl/issues/546) records against
Seven-Card Stud, seen from the other side: that file never offers the big bet,
this one never offers the small.

Pagat describes a cash game with no overall winner. To give the runtime a
terminal, the executable plays a session until one player holds **all** the
chips and names that player the winner.

## How the file is built

Chips are an integer `stack` per player, not a resource-zone subsystem; the
total is invariant. The whole hand runs in the DSL — antes, the deal, the
bring-in post, the four streets on the kernel `round`'s **ring** (the pointer
advances past whoever just acted, so the seats behind an aggressor decide before
the seats its bet re-opened), and the showdown as plain statements: a contested
hand turns the hole cards face up, each entrant collects its side-pot share via
`pot_share(p)`, and the hands leave play to the muck.

The first street's ring opens **on** the bring-in poster, which is what makes
the poster's option a decision the game tree holds rather than a rule stated in
prose. A forced post is not a turn taken within the round, so the poster arrives
with its turn outstanding: `check` stands on the minimum and `raise` completes.

Three Primitives are pure reads that the language cannot express (they are
argmin / argmax over players keyed on card ranks and suits):

- `bring_in_seat` — the lowest up card;
- `best_showing_seat` — the best hand showing, in the order described above;
- `pot_share` — the side-pot settlement, argmax over poker-rank tuples per
  layer.

The poker evaluator behind the last is family-wide and unit-tested; the first
two are unit-tested against Pagat's own worked examples in
[test_stud_selectors.py](../../tests/test_stud_selectors.py).

The betting state splits two ways. What the game touches it declares itself
(`bet_to_match`, `level`, `raises`, `raise_cap`, and per-player `bet_by` /
`folded` / `committed`); the pure intra-street bookkeeping — `acted`, and the
street's `limit` — the library *provides*, so the game never names it and could
not write it if it tried.

`uses poker_betting` imports `check`, `bet`, `call`, `raise` and the
`can_act` / `owes` / `pending` ring predicates from the family library shared
with Kuhn, Leduc, Hold'em and Seven-Card Stud
([poker_betting](../libraries/poker_betting.cardlang),
[decisions.md](../decisions.md) "Family libraries"); the line stands in for the
rulebook sentence "betting proceeds as in standard fixed-limit poker". The
game's own contribution is `fold`, which mucks the folder's **up cards** — a
fact about these zones, and an observation opponents' information sets carry.

Two things the game writes rather than the library. `raise_cap` is set **per
street** from the count of seats that can act, because Pagat's cap has a
heads-up arm; and the second street's size is an expression,
`if (number of players where shows_pair(player)) > 0 then 20 else 10`, passed
straight to `open_street`. Sizing the STREET rather than one seat's move is what
makes the big bet reach every seat rather than only the seat showing the pair,
which is the half of the rule
[#546](https://github.com/jbgh2/card-game-dsl/issues/546) is about; the other
half, that the small bet stays available beside it, is
[#648](https://github.com/jbgh2/card-game-dsl/issues/648).

The `until` predicate closes a street when no live player still owes or has yet
to act, or when one lone contender remains already matched.
