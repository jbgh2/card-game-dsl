"""The winners a trick round admits, and the refusals of the rest."""

from __future__ import annotations

from typing import Literal
from cardlang.ast import nodes as n
from cardlang.builtins.functions import (
    TRICK_ORDER_EARLY_PREDICATES,
    TRICK_ORDER_GATED_WINNERS,
    TRUMP_READING_WINNERS,
)
from cardlang import kernel_contracts as K
from cardlang.resolve.clause_gates import (
    _CARD_CONTENT_GATE,
    _ClauseGate,
    _trick_order_excluded_winners,
    _trick_order_reading_slots,
)


def _refuses(gate: _ClauseGate, node: object, game: n.Game) -> bool:
    """Whether `gate` refuses `node` in `game`: the test a downstream gate asks
    of the game's own text, the same two halves the `uses` check asks of a
    library's."""
    return gate.unmet(game) and bool(gate.needs(node, game))


def _unstated_trump_slots(node: object, game: n.Game) -> tuple[str, ...]:
    """A trick round naming a winner that reads a trump, with no `trump`
    clause of its own."""
    if (
        isinstance(node, n.TrickRound)
        and node.winner_fn in TRUMP_READING_WINNERS
        and node.trump is None
    ):
        return (f"round winner `{node.winner_fn}`",)
    return ()


#: Why a trick round refuses the winner it names, by the guard that tells it:
#: a piece game (`_check_piece_rounds`), the presence partition's winner arms
#: (`_check_trick_order_partition`), and a `trump` clause the winner ignores
#: (`_validate_refs`).
_WinnerRefusal = Literal[
    "reads a deck card",
    "reads an absent Trick Order",
    "reads an unstated trump",
    "replaced by the Trick Order",
    "early beside the Trick Order",
    "ignores the trump clause",
]


def _winner_refusals(rnd: n.TrickRound, game: n.Game) -> tuple[_WinnerRefusal, ...]:
    """Every reason `rnd` refuses its own winner, in the order its guards
    tell them: the one producer each guard dispatches on and the winner
    site's Near Misses read."""
    out: list[_WinnerRefusal] = []
    if game.content_flavor != "card":
        if _refuses(_CARD_CONTENT_GATE, rnd, game):
            out.append("reads a deck card")
    elif not K.has_trick_order(game):
        if _trick_order_reading_slots(rnd, game):
            out.append("reads an absent Trick Order")
        elif _unstated_trump_slots(rnd, game):
            out.append("reads an unstated trump")
    else:
        if _trick_order_excluded_winners(rnd, game):
            out.append("replaced by the Trick Order")
        if (
            rnd.early_termination is not None
            and rnd.early_termination not in TRICK_ORDER_EARLY_PREDICATES
            and rnd.winner_fn in TRICK_ORDER_GATED_WINNERS
        ):
            out.append("early beside the Trick Order")
    if (
        rnd.trump is not None
        and rnd.winner_fn not in TRICK_ORDER_GATED_WINNERS
        and rnd.winner_fn not in TRUMP_READING_WINNERS
    ):
        out.append("ignores the trump clause")
    return tuple(out)
