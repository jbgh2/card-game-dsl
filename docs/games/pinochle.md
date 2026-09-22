# Pinochle

The companion formal file is [pinochle.cardlang](pinochle.cardlang); this is the
readable twin. Single Deck Partnership Pinochle, one 48-card pack (two copies
each of A 10 K Q J 9 per suit; 10 ranks between K and A), four players in fixed
teams sitting across. First team to **1500** wins — and when both sides pass
1500 on the same hand the game goes to the side that won the bidding, whatever
the totals. **Rules source:**
https://www.pagat.com/marriage/pinmain.html (fetched live), the page's main
account throughout — the four-card pass rather than the cutthroat variation,
and the main text's run-extras table (a run with an extra king 190, an extra
queen 190, an extra marriage 230) rather than the Variations paragraph's.

Each hand:

1. Deal 12 cards each.
2. **Auction** — an ascending bid opening at 250. A bidder names a number at
   least 10 above the standing bid, raising by ten or jumping by any larger
   multiple of ten; or leaves the auction, with or without telling partner it
   holds help. The last bidder in takes the contract and becomes the declarer,
   and if the other three leave without a bid the dealer is *under* and takes
   it at 250.
3. **Declare trump** — the declarer names any suit.
4. **Pass** — the declarer's partner passes four cards face down across the
   table, and the declarer passes four back, which may include cards just
   received. Exactly four each way.
5. **Meld** — every seat lays its meld face up and both sides score it (runs,
   marriages, dix, pinochle, and the four-around sets, with doubles scoring the
   published double values). Only the cards a piece needs are shown, so the
   twelve tricks are played with those cards known to the whole table and the
   rest of every hand still hidden.
6. **Settle or play** — a bid standing more than 250 above the declarer's own
   side's meld cannot be made, so the side is not *on the board* and the hand
   is not played. Otherwise the declarer chooses: throw the hand in, or play it
   out. Either way of ending a hand unplayed pays the same — the bidders lose
   the bid, and the defenders score their meld with nothing for tricks.
7. **Play** — twelve strict tricks: follow suit, and beat the card controlling
   the trick if you can; if void, trump and over-trump if you can. A/10/K
   captured score 10 each, and the last trick is worth 10 (250 trick points in
   all).
8. **Score** — the bidding side adds meld + tricks if it reached its bid, else
   is set back by the bid and scores nothing else. The defending side adds its
   tricks, and its meld only if it *saved* it by taking some trick point —
   a counter or the last trick. A defence that took none loses its meld, unless
   that meld was nothing but nines of trump, which save themselves.

The whole hand runs in the DSL. The ascending auction runs on the kernel
`round` (a shrinking participants ring over the `submit_bid`/`pass` vocabulary,
settling on a declarer and his bid). Trump declaration is a second, one-draw
`round offering [declare_trump_suit]` over all four suits. The exchange is two
one-seat `round offering [pass_four]` draws, the partner's and then the
declarer's, each a `move chosen 4 cards` whose count is the rule; a passer's
log names the four cards leaving and the receiver's names them arriving, while
the opponents see four cards cross the table and no identity at either end.
Meld is a forced `pinochle_meld_value(p)` Primitive query per player, credited
to his team, with a `pinochle_meld_size`/`pinochle_meld_slot` pair naming the
cards it lays face up one at a time. The concession is a one-seat `round offering [throw_in, play_on]`.
The twelve strict tricks run on the trick form of `round`, legality narrowed by
the MustFollowSuit/MustHeadTrick/MustTrumpIfVoid/MustOverTrump rule cascade —
note that the duty to beat the trick lapses once a plain-suit lead has been
trumped, because no card of the led suit can beat a trump. The meld evaluator
(`pinochle_meld_value`) is a pure Primitive (`cardlang/runtime/pinochle.py`) —
not yet the shared combination model. `winner:` ranks a game-level `result`
rather than `score`, because the bidders' win is a rule the score cannot state;
that makes the game's OpenSpiel returns a win and a loss rather than two
totals, which is the open question on
[#749](https://github.com/jbgh2/card-game-dsl/issues/749).
