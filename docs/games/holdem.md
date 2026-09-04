# Texas Hold'em

The companion formal file is [holdem.cardlang](holdem.cardlang); this is the
readable twin. Fixed-limit Texas Hold'em, three players — the corpus's second
**side-pot** game and its first with a **community board**. Source:
[Pagat](https://www.pagat.com/poker/variants/texasholdem.html). **Players:** 3.
**Deck:** standard 52. **Chips:** each player starts with 100.

Each hand:

1. The dealer button moves to the next seat that still has chips. The player
   to its left posts the
   **small blind** (2), the next the **big blind** (5) — these are forced bets,
   not decisions. **Heads-up the blinds reverse**: the button posts the small
   blind.
2. Burn one card, then deal each player two face-down **hole cards**. (Pagat
   burns here as well as before each community stage — four burns a hand,
   where common casino practice burns only three.)
3. **Pre-flop** betting, begun by the player to the big blind's left. A player
   may check, bet, call, raise (capped), or fold. The big blind decides last and
   holds its **option**: limped to, it may raise its own forced post as well as
   check, because posting is not the same as having taken a turn.
4. **The flop** — burn one, deal three face-up **community cards** — then a
   betting round begun by the first live player to the button's left.
5. **The turn** — burn one, deal one — then a betting round. Limits double here
   (5 becomes 10).
6. **The river** — burn one, deal one — then the last betting round.
7. **Showdown** — each remaining player makes their best five-card poker hand
   from the seven available (their two hole cards plus the five community
   cards), and the best hand wins the pot, with side pots when players are
   all-in. A hand may use both hole cards, one, or none — "playing the board".

The community cards belong to nobody and are read by **every** player's hand
evaluation. That is the interesting thing about this game for the language: the
board is declared `Discard`, the library zone type whose contents are visible to
all, so its publicness is a property of its *type* and needs no rule. Leduc's
single face-up card already used that type; Hold'em is the five-card case.

The `.md` source is a cash game with no overall winner; to give the runtime a
terminal, the executable plays until one player holds **all** the chips and names
that player the winner. Chips are modelled as an integer `stack` per player (not
a resource-zone subsystem); the total is invariant. The whole hand runs in the
DSL: the betting on the kernel `round`'s **ring** (the pointer advances past
whoever just acted, so the seats behind the aggressor decide before the seats its
bet re-opened — poker's continuation order), and the showdown as plain
statements — a contested hand reveals the contenders' hole cards, each entrant
collects its side-pot share via `holdem_pot_share(p)`,
and the hands leave play to the muck.

One Primitive, a pure read. `holdem_pot_share`, declared in the game's own
`primitives { }` block, is the side-pot query (the committed-total layering,
odd chip to the first winner in seat order, uncalled remainder to the best
contender). The seat-ring skip is the language's
own ring search — `the first player from <seat> offset_by left where
in_hand[player]` (decisions.md "Player-collection queries") — and both the
button's own rotation and the blinds go through it. Stepping the button along
the LIVE ring rather than rotating it through every physical seat is what keeps
the rotation strict: map dead seats forward instead and, heads-up, one survivor
takes the button on two hands of every three. The poker evaluator behind the settlement is
shared with Seven-Card Stud (`cardlang/runtime/poker.py`) and unit-tested: which
cards a player has available is a property of the game, how five of them compare
is not.

The betting state splits two ways. What Hold'em touches it declares itself
(`bet_to_match`, `level`, `raises`, `raise_cap`, per-player `bet_by`/`folded`/`committed`);
the pure intra-street bookkeeping — `acted`, and the street's `limit` — the
library *provides*, so Hold'em never names it and could not write it if it tried.
The `until` predicate closes a street when no live player still owes or has yet
to act (or one lone contender remains, already matched).

Four of the five betting move types are not Hold'em's own. `uses poker_betting`
imports them — `check`, `bet`, `call`, `raise` and the `can_act`/`owes`/`pending`
ring predicates — from the family library shared with Kuhn, Leduc and Stud
([poker_betting](../libraries/poker_betting.cardlang),
[decisions.md](../decisions.md) "Family libraries"). Hold'em's own contribution
is `fold`, which mucks the folder's hole cards unseen — as in Kuhn and Leduc, and
unlike Stud, whose fold mucks upcards opponents were already watching — and the
`raise_cap` it declares as required state, where Stud declares 3 and Leduc 2.
`raise_cap` counts aggressive actions *including* the opening bet, so 4 is Pagat's
"one bet plus three raises" — and Hold'em sets it **per street** rather than once,
because Pagat caps a street only when it opens with more than two active players
and lifts the cap entirely on one that opens two-handed.

Hold'em is the family library's first consumer whose street shape **differs**
from Stud's. Stud opens every street with no standing bet; Hold'em opens pre-flop
with the blinds already posted, and its action order is *positional* rather than
derived from the visible cards. Both fit `open_street(<size>)` followed by a
forced post — the pattern Stud's bring-in established — so the library needed no
change to take a fourth consumer of a new shape.

**Simplifications.** The deal starts at seat 0 rather than left of the button.
Hold'em deals clockwise from the dealer's left, and since the button rotates every
hand, that is a different seat each time; the language has no way to anchor a deal
to a seat (issue #196), and Seven-Card Stud deals seat-0-first for the same reason.
On a shuffled deck the two deals are distributionally identical, so this changes
which cards a fixed seed produces and nothing else. No-limit and pot-limit betting
are out (fixed limit only —
that is a parameterization of the betting round, not a structural change). The
"show one, show all" showdown rule is not modelled: every contender's hole cards
are revealed at a contested showdown. That rule is a per-observer move-level
projection override, which the language does not yet have — see
[open-questions/move-level-visibility.md](../open-questions/move-level-visibility.md),
whose witness this game is.
