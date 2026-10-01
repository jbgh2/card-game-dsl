"""What a [[hosted-poll]]'s body may execute — one registry and two consumers.

The body of `before asking <binder> { … }` runs between two asks of a live
climbing trick (decisions.md "Off-the-clock windows"). Resolve's
`_check_hosted_polls` is the Owner Guard: it judges the body, and everything
the body reaches by name, against these tables before the game runs. The
runtime is the Shadow Guard behind it: while a body runs (`RuntimeState.hosting`),
`execute.execute` refuses every statement these tables refuse, and the two
readers of the live round frame — the `state` pronoun's evaluation and
`narrowing.engine_facts`, through which every Primitive reads it — refuse to
read. The runtime half keys on what executes rather than on what the text
says, so an indirection the static judgement does not model is still refused
when it runs.
"""

from __future__ import annotations

from cardlang.ast import nodes as n

# The statement kinds a Hosted Poll's body may hold: decisions and state
# writes, and the scoping and control that arrange them. `Block` is what a
# `run` expands into, so it arrives only after resolve and is admitted for the
# same reason `run` is.
HOSTED_POLL_ALLOWED: frozenset[type] = frozenset(
    {
        n.IfStmt, n.LetStmt, n.AssignStmt, n.Offer, n.AuctionRound,
        n.AsBlock, n.ForEach, n.RunStmt, n.Block,
    }
)

# Every other statement kind, with the words its refusal names it by. A card
# movement would change the hands and the pile the round is reading, a nested
# trick or climbing round would start a second trick inside the first, a loop
# (`repeat`, `turns`, `each … simultaneously`) has no bound the poll's lap does
# not already give, and non-local control would unwind out of the round
# mid-trick. The two sets partition the `Stmt` union
# (tests/test_hosted_poll.py pins it).
HOSTED_POLL_REFUSED: dict[type, str] = {
    n.Transfer: "a card movement",
    n.EpistemicOp: "a reveal or forget",
    n.RotateStmt: "`rotate`",
    n.EachSimultaneous: "`each … simultaneously`",
    n.RepeatUntil: "`repeat until`",
    n.Turns: "`turns`",
    n.TrickRound: "a trick `round`",
    n.ClimbRound: "a `round climb`",
    n.Produce: "`produce`",
    n.Produces: "`produces:`",
    n.ContinueTo: "`continue to`",
    n.SkipToNextHand: "`skip to next hand`",
}

# The one admitted statement whose optional clause the body may not use: an
# auction's `outcome` produces a typed outcome, which unwinds to the enclosing
# outcome phase — out of the live climbing round, past the frame it publishes.
HOSTED_REACH_REFUSED_SLOTS: dict[tuple[type, str], str] = {
    (n.AuctionRound, "outcome_fn"): "a `round offering` with an `outcome` clause",
}
