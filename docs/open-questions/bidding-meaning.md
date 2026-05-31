# Bidding meaning

**Tier 1 — high impact, ready to commit.**

Three bidding games in the corpus, three different meanings for the
bid value:

| Game | Bidding shape | Bid value means |
| --- | --- | --- |
| Spades | inline per-player, no constraint between bids | per-team threshold tricks (≥ bid succeeds) |
| Pinochle | ascending Auction (`opening_bid` 50, increment 10) | per-team total-points target (≥ bid succeeds) |
| Oh Hell | inline per-player, dealer-hook constraint | per-player exact-tricks target (= bid succeeds) |
| Bridge | structured contract bidding (level + suit + doubling) | structured contract (Contract value, not Integer) |

The four don't share a common bid type — Bridge's contract is a
structured value, not an integer; Oh Hell's is per-player; Spades
and Pinochle differ on threshold vs total.

The proposed `bid_meaning:` parameter on Auction would only cover
Pinochle's case (the only one using Auction). Spades, Oh Hell, and
Bridge don't use Auction at all — they do per-player inline bidding
or have their own bidding mechanic. So a shared parameter wouldn't
unify across games.

**Resolution:** no shared `bid_meaning:` parameter. Each game's
scoring code declares its own interpretation explicitly. The
mechanic emits raw bid values; the scoring components consume them.
This is consistent with the corpus's broader pattern that scoring
shape is per-game (see decisions.md "Scoring composition").

What *does* generalize across Spades and Oh Hell is the
*inline per-player bidding* pattern itself — every player bids
exactly once in turn, no ascending constraint, optionally with a
hook rule for the dealer. A `PerPlayerBidding` mechanic could
extract this pattern. Worth doing once a third per-player-bid game
arrives (Wizard, Boerenbridge variant, 7-Truf).

**Ready to commit:** the resolution is "no shared bid-meaning
parameter; each game declares its own interpretation in scoring."
The per-player bidding pattern extraction is deferred until a third
game forces it.
