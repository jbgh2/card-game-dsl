# Mechanic-internal legality

**Tier 1 — high impact, ready to commit.**

Stud's BettingRound has check/call/bet/raise/fold legality
conditions that read mechanic-internal state (`bet_to_match`,
`raises_so_far`, `bet_by`) which isn't exposed outside the
mechanic. The current rule model assumes rules read game state;
mechanic-internal state isn't reachable.

Two options:

(a) **Promote mechanic-internal state to a queryable interface**
    (`betting_round.bet_to_match`) so rules can live outside the
    mechanic. Fits the doctrine "rules are reusable named
    constraints." Pays a small surface-area cost.

(b) **Accept that some legality logic is mechanic-internal** and
    document this as a known pattern. Cheaper but inconsistent —
    some constraints are rules, some are mechanic-internal
    conditionals.

Leaning (a): a mechanic that doesn't expose its decision-relevant
state can't be reasoned about from outside, which breaks
composability. The cost of (a) is a `state { exposed { ... } }`
section in mechanics, listing the queryable subset.

**High impact:** every mechanic with action legality currently has
this issue (Auction, Trick, BettingRound).
**Ready now:** Stud is one clear case; Auction and Trick fit the
same shape if examined.
