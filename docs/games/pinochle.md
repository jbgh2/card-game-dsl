# Pinochle

The companion formal file is [pinochle.cardlang](pinochle.cardlang); this is the
readable twin. Team Bid Pinochle, single 48-card pack (two copies each of
A 10 K Q J 9 per suit; 10 ranks between K and A), four players in fixed
teams sitting across. First team to **150** wins.

Each hand:

1. Deal 12 cards each.
2. **Auction** — an ascending bid opening at 50 and rising in 10s; players pass
   out, the last bidder takes the contract.
3. **Declare trump** — the high bidder names a suit he holds a *marriage* (K-Q)
   in. With no marriage anywhere he abandons the bid and his side is set back by
   the bid amount.
4. **Meld** — both sides score their meld combinations (runs, marriages, dix,
   pinochle, and the four-around sets — the standard single-pack values, with
   doubles scoring the published double values).
5. **Play** — twelve strict tricks: follow suit and head the led suit if you
   can; if void, trump and over-trump if you can. A/10/K captured score 10 each,
   and the last trick is worth 10 (250 trick points in all).
6. **Score** — the bidding side adds meld + tricks if it reached its bid, else is
   set back by the bid; the other side always adds its meld + tricks.

The whole hand runs in the DSL. The ascending auction runs on the kernel
`round` (a shrinking participants ring over the `submit_bid`/`pass` vocabulary,
settling on a declarer and his bid). Trump declaration is a second,
one-draw `round offering [declare_trump_suit]`, guarded by a `has_marriage`
function checked over each of the four suits (no marriage anywhere abandons
the bid with no decision offered at all). Meld is a forced
`pinochle_meld_value(p)` Primitive query per player, credited to his team. The
twelve strict tricks run on the trick form of `round`, legality narrowed by
the MustFollowSuit/MustHeadTrick/MustTrumpIfVoid/MustOverTrump rule cascade
(follow suit and head the trick if able; else trump and over-trump if
able; else anything). The meld evaluator (`pinochle_meld_value`) is a pure
Primitive (`cardlang/runtime/pinochle.py`) — not yet the shared
combination model.
