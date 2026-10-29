# Big Two

The companion formal file is [big-two.cardlang](big-two.cardlang); this is the
readable twin. A four-player **climbing / shedding** game (also called Deuces or
Choh Dai Di) on the standard 52-card deck. The aim is to be the first to play out
your whole hand; the others lose penalty points for the cards they are caught
with. Lowest cumulative penalty wins. Rules: [Pagat](https://www.pagat.com/climbing/bigtwo.html)
(basic game), played **anticlockwise** as the page's basic game is, and **for
money** at a stake per penalty point. Pagat sets no end to a session; this file's
match ends when a player's penalty total reaches 100.

**Card order.** Two rank orders coexist, which is the heart of the game:

- For **singles, pairs, triples, four-of-a-kinds, and full houses** (and a
  flush's top card), the **2 is the highest rank**, then A, K, Q, J, 10, …, down
  to the 3. **Suits break every tie**, high to low: **♠ > ♥ > ♣ > ♦** (a single
  52-card deck, so 7♠ beats 7♥).
- For **straights**, ranks run in **natural** order: the ace is high in
  10-J-Q-K-A (the highest straight) and low in A-2-3-4-5 (the *wheel*, the lowest
  straight). There is **no wrap-around** — J-Q-K-A-2 is not a straight, and the 2
  is just an ordinary low card here.

Each hand:

1. Deal **13 cards** to each player. The holder of the **3♦** leads every hand and
   must play it, **alone or as part of any legal combination**.
2. Players **climb**: a play must have the **same number of cards** as the
   standing combination and **beat** it, or you **pass**. Passing does not lock
   you out — you may play again when the turn comes back around. A trick ends when
   the action returns to the last player who played (everyone else passed); that
   player then **leads the next trick** with anything.
3. The combinations, by size:
   - **Singles** — one card; **pairs** — two of a rank; **triples** — three of a
     rank. A higher pair/triple is one of a higher rank (suit breaks a pair tie).
   - **Five-card hands**, weakest type to strongest: **straight** < **flush**
     (five of a suit; a higher suit beats a lower one outright, then top card) <
     **full house** (ranked by its triple) < **four of a kind** (all four of a
     rank **plus a fifth kicker card**, ranked by the four) < **straight flush**
     (five in sequence and suit). A stronger *type* beats a weaker one of the same
     size, so any flush beats any straight, any full house beats any flush, and so
     on. There is **no four-card play** and no bombs — a single only follows a
     single, a five-card hand only a five-card hand.
4. The hand ends the **instant a player empties their hand** — they win it. The
   others score **penalty points** for the cards still in hand: **1 per card** for
   nine or fewer, **2 per card** for ten–twelve, **3 per card** for a full
   thirteen (39). The winner scores 0. The match ends when a player's cumulative
   penalty reaches 100 (this file's bound); the **lowest** total wins.
5. **Precautions** (the money game). When the next player holds **one card**, you
   must try to stop them going out: if **single cards** are being played, play
   your **highest card**; if it is **your lead**, lead a **combination of more
   than one card** if you can, otherwise your highest card. If you don't, and
   that player then goes out on their last card, your hand is **shown** and, if
   it held what you should have played, you **pay every loser's penalty** for the
   hand — the whole sum is yours and the other losers score nothing. A pass
   counts as ignoring the precaution when your highest card could have beaten the
   single.

The hand runs on the kernel **`round climb`** construct: one combination-climbing
trick per round, over the game's own Combination Catalogue (`combinations
big_two`, the eight shapes, with a straight all of one suit a straight flush and
never a straight or a flush) and the follows function `big_two_follows` (same
size and stronger; on each hand's opening lead, a play holding the 3♦). The
`sequence:` clause reads the ace low in A-2-3-4-5 and high in 10-J-Q-K-A. A seat
is offered **every combination its hand holds** — each suit choice of a pair or triple, every straight over its
window, every five cards of a suit, every pairing of a full house, and any kicker
with four of a kind — since which cards a seat keeps back for later tricks is a
decision of the game. The climbing loop, the pile routing, the shed-out finish,
penalty scoring and the precaution rule are DSL: the round's `before asking` hook
keeps a public record of the hand's last two asks (who was asked, the trick
pile's size and top card, the trick's lead size), and the moment a hand ends the
seat bound by the precaution has its hand shown before it is judged, so every
seat sees what decides it. Pagat's scoring variations — the doubled penalties for
many cards left or for twos held, among others — are variants this file does not
play.
