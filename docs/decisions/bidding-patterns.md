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

Bid interpretation is therefore a per-game scoring concern, written as the
scoring phase's own statements — Spades, in `docs/games/spades.cardlang`:

```text
for each team t:
  if team_tricks[t] >= team_bid[t] {
    score[t] += contract_score(t) + overtricks(t)
    bags[t]  += overtricks(t)
  } else {
    score[t] -= contract_score(t)
  }
```

Oh Hell, in `docs/games/oh-hell.cardlang` — one point a trick, ten more for
hitting the bid exactly:

```text
for each player p:
  if tricks_won[p] is bid[p] { score[p] += tricks_won[p] + 10 }
  else { score[p] += tricks_won[p] }
```

Pinochle, in `docs/games/pinochle.cardlang` — the bidding team must reach
its bid or is set back by it:

```text
if team_score_in_hand(t) >= current_bid {
  score[t] += team_score_in_hand(t)
} else {
  score[t] -= current_bid
}
```

The shared *bidding mechanic* possibilities — an ascending-bid `auction`
definition, an inline per-player pattern — are extracted only when
multiple games clearly share them. Bridge's auction (doubling, redoubling, and
the structured contract outcome) is a `turns` ring of offers (see "Auctions,
polls and betting rings are `turns` plus `offer`" above), game-local until the
shared `auction` definition is promoted corpus-first.
Spades and Oh Hell both use inline per-player bidding; a
`PerPlayerBidding` mechanic could be extracted, deferred until a
third per-player-bid game (Wizard, Boerenbridge variant, 7-Truf)
arrives to confirm the shape.
