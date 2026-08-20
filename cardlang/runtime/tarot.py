"""French Tarot's runtime support (pure Primitives).

The whole hand — the four-level bid (the auction [[form]] of the kernel
[[round]]), the chien handling by bid level, the eighteen atout-trump
[[trick]]s with the Excuse's special routing and the
must-follow/must-trump/must-over-trump obligations (the
`ExcuseIsExempt`/`MustFollowEffectiveSuit`/`MustTrumpIfVoid`/`MustOverTrump`
[[rule]] cascade), and the bouts-conditional threshold scoring all
run in the DSL (docs/games/french-tarot.cardlang). The trick order itself —
which cards are trumps, which class a card follows as, how strong it is, and
that the Excuse belongs to no class at all — is the game's own
`trick_order { }` declaration, so the winner, the follow demand and the
over-trump comparison read one declaration and no Python (issue #250 PR 5).
This module holds only what is not expressible there:

- `tarot_excuse_player` — which player (if any) played the Excuse in the trick
  that just completed, read off the round's exposed terminal state.
- `tarot_per_opp` — the zero-sum per-opponent settlement amount: the
  bouts-conditional threshold, the taker's doubled card points (the chien's
  too, at Garde sans le chien — the chien is never moved there, so it counts
  where it sits), the petit-au-bout adjustment, and the bid multiplier
  (verbatim monolith arithmetic: a float division then Python's banker's
  rounding).

Card points are kept in *doubled* integer units (the printed half-points
doubled; the 78 cards sum to 182). The game file declares the rank-keyed part
of that table as its `card_points { }` clause and composes it with the bout
layer inline (`if is_bout(card) then 9 else card_points(card)` — a rank-keyed
table cannot carry the petit, whose rank "1" is worth 9 in atouts and 1 in
the plain suits); `tarot_card_points` below survives as `tarot_per_opp`'s
internal helper only, and must agree with that composition — pinned by
tests/test_card_points.py::
test_tarot_settlement_table_matches_the_clause_through_the_bout_layer.
"""

from __future__ import annotations

from cardlang.runtime import reads
from cardlang.runtime.errors import OwnerGuardError
from cardlang.runtime.narrowing import EngineFacts
from cardlang.runtime.values import Card, Player

ROW = reads.row("cardlang/runtime/tarot.py", "french-tarot.cardlang")

# Bid levels, ascending, with their scoring multipliers.
_LEVELS = ("petite", "garde", "garde_sans", "garde_contre")
_MULT = {"petite": 1, "garde": 2, "garde_sans": 4, "garde_contre": 6}


def tarot_card_points(c: Card) -> int:
    """Doubled card-point value (printed value × 2, so all integers)."""
    if c.suit == "excuse":
        return 9
    if c.suit == "atouts":
        return 9 if c.rank in ("1", "21") else 1
    return {"K": 9, "Q": 7, "C": 5, "J": 3}.get(c.rank, 1)


def _is_bout(c: Card) -> bool:
    """A bout (oudler): the Excuse, the 1 of atouts (petit), or the 21. The
    DSL's own `is_bout` function (french-tarot.cardlang) computes the same
    predicate independently for the discard filter, mirroring this."""
    return c.suit == "excuse" or (c.suit == "atouts" and c.rank in ("1", "21"))


def tarot_excuse_player(
    facts: EngineFacts, gr: reads.GameReads
) -> Player | None:
    """The player who played the Excuse in the trick that just completed, or
    None if nobody did. Reads the round's exposed terminal state exactly as
    the `state` pronoun does (`mech_state[-1]` while a round is still active,
    else `last_round_state`) — the DSL calls this right after `round
    play_to_trick` returns, when the round is no longer active."""
    state = facts.round_state
    if state is None:
        # Same contract as the `state` pronoun: whether a round has run is
        # live game flow, so a premature call is the description's error, and
        # this raise is its Owner Guard.
        raise OwnerGuardError(
            "tarot_excuse_player() called with no active or just-completed "
            "round"
        )
    played: list[tuple[Player, Card]] = state["played"]
    return next((p for p, c in played if c.suit == "excuse"), None)


def tarot_per_opp(facts: EngineFacts, gr: reads.GameReads, pb: int) -> int:
    """The zero-sum per-opponent settlement amount for the hand just played:
    the bouts-conditional threshold ({3: 36, 2: 41, 1: 51, 0: 56} doubled
    points), the taker's doubled card points (`captured[taker]`, plus the
    chien's at Garde sans le chien — never moved, counted where it sits), the
    petit-au-bout adjustment `pb`, and the bid multiplier. Verbatim monolith
    arithmetic (a float division then Python's banker's rounding).

    Counts `discard[taker]` (the taker's hidden chien discards, at Petite/
    Garde) as taker cards too — the fidelity stage's discard reroute moved
    those six cards out of `captured[taker]` into their own hidden zone, so
    without this they would silently drop out of the taker's total. Their
    bouts contribution is always zero and is not added: both discard filters
    (`is_pref_discard`, `not is_bout`) exclude every bout by construction, so
    a discarded card can never BE one."""
    taker: Player = gr.state["taker"]
    level = _LEVELS[gr.state["bid_level"] - 1]  # bid_level is 1..4 (0 = no bid)
    captured = gr.families["captured"]
    chien = gr.singles["chien"]
    discard = gr.families["discard"]

    taker_doubled = sum(tarot_card_points(c) for c in captured[taker])
    taker_doubled += sum(tarot_card_points(c) for c in discard[taker])
    bouts = sum(1 for c in captured[taker] if _is_bout(c))
    if level == "garde_sans":
        taker_doubled += sum(tarot_card_points(c) for c in chien)
        bouts += sum(1 for c in chien if _is_bout(c))
    threshold = {3: 36, 2: 41, 1: 51, 0: 56}[bouts]

    pt = taker_doubled / 2 - threshold
    return round((25 + pt + pb) * _MULT[level])
