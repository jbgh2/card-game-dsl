# Seven-Card Stud

The companion formal file is
[seven-card-stud.cardlang](seven-card-stud.cardlang); this is the readable twin.
Fixed-limit Seven-Card Stud — the corpus's first **betting** game. Source:
[Pagat](https://www.pagat.com/poker/variants/7stud.html). **Players:** 4.
**Deck:** standard 52. **Chips:** each player starts with 100 and antes 1 each
hand.

Each hand:

1. Every player antes; deal two hole cards and one upcard each.
2. The lowest upcard (ties by suit) **brings in** for 2, short of the street's
   own size. Raising it **completes** the bet to 5 rather than adding 5 to it,
   so 3rd street's ladder is 2 / 5 / 10 — a bring-in is the one forced bet the
   street has to climb back up from. The poster then makes the street's
   **first decision**: Pagat gives the opener "the option to place a full small
   bet ($5) instead of just the compulsory minimum $2", so the action starts on
   the poster, which may check (standing on the 2) or raise (completing to 5).
   Which it takes is what the seats behind it face — the page states their
   rights as a consequence of the opener's choice, so the order carries the
   rule. Called around later, that same seat holds the **option** again: it may
   raise its own post as well as check, because posting is not the same as
   having taken a turn. Pagat is silent on that *later* moment, where it spells
   the same option out for Hold'em's big blind — so the second right is **this
   file's own rule**, and the first is quoted.

3. Five betting streets — 3rd through 7th — interleaved with a dealt card each
   (an upcard on 4th/5th/6th, a face-down card on 7th, a burn before each). On
   each street a player may check, bet, call, raise (a bet and three raises
   per street where more than two players can act, uncapped heads-up;
   completing the bring-in is the bet, not a raise), or fold; the
   best poker hand showing acts first from 4th street on — multiplicities ahead
   of card values, incomplete straights and flushes not counted, ties broken on
   the suit of the highest card. The lower limit applies
   on 3rd/4th, the upper limit from 5th.
4. **Showdown** — the best five-card poker hand from each remaining player's seven
   cards wins the pot, with side pots when players are all-in.

The `.md` source is a cash game with no overall winner; to give the runtime a
terminal, the executable plays until one player holds **all** the chips and names
that player the winner. Chips are modelled as an integer `stack` per player (not
a resource-zone subsystem); the total is invariant. The whole hand runs in the
DSL: the betting — antes, deal, the bring-in post, and the five streets — on the
kernel `round`'s **ring** (the pointer advances past whoever just acted, so the
seats behind the aggressor decide before the seats its bet re-opened — poker's
continuation order), and the showdown as plain statements — a contested hand
reveals the contenders' hole cards into the
public board, each entrant collects its side-pot share via `pot_share(p)`, and
the hands leave play to the muck. The Primitives are pure reads: the
door-card seat selectors (`bring_in_seat` / `best_showing_seat`) and the
side-pot query (`pot_share`); the poker evaluator behind them is unit-tested.
From 4th street on, a pair showing opens the **big bet** to every active
player — as an option beside the small bet, so a player choosing to bet picks
between the two sizes. The street opens at both: `open_street` takes a second
size, and `bet_big` / `raise_big` are the two actions it puts at the node. 5th
street on is big-bet-only in this variant, so 4th is the only street the rule
changes. Once a big wager is *placed*, the small raise is withdrawn for the
rest of the round — the casino arm of a rule Pagat states as an option, which
this file names in its header and the library carries both arms of.

The betting state splits two ways. What Stud touches it declares itself
(`bet_to_match`, `level`, `raises`, `raise_cap`, per-player `bet_by`/`folded`/`committed`);
the pure intra-street bookkeeping — `acted`, and the street's `limit` — the
library *provides*, so Stud never names it and could not write it if it tried. A
`check`/`bet`/`call`/`raise`/`fold` move type writes both (a bet or raise is a
partial all-in when the actor can't cover it, and resets every other player's
`acted` so action re-opens). The
`until` predicate closes a street when no live player still owes or has yet to act
(or one lone contender remains, already matched). Streets 4–7 repeat 3rd
street's betting round after a burn and a dealt card.

Four of those five move types are not Stud's own. `uses poker_betting` imports
them — `check`, `bet`, `call`, `raise` and the `can_act`/`owes`/`pending` ring
predicates — from the family library shared with Kuhn and Leduc
([poker_betting](../libraries/poker_betting.cardlang),
[decisions.md](../decisions.md) "Family libraries"); the line stands in for the
rulebook sentence "betting proceeds as in standard fixed-limit poker". Stud's
own contribution is `fold`, which mucks the folder's **upcards** — a fact about
Stud's zones, and an observation opponents' information sets carry — and the
`raise_cap` it declares as required state — a bet and three raises, counted
from the street's first FULL wager, so the sub-size bring-in and the completion
that answers it spend none of them — where Leduc declares 2. Stud sets it PER
STREET rather than once, because Pagat caps only a street that began with more
than two active players and leaves a heads-up street uncapped; "uncapped" is a
bound no street can reach, derived at the third street where it is written.
Every street opens with the library's `open_street(<size>, <big>)`, which is
where Stud's 5 / 5 / 10 / 10 / 10 limits are written.
