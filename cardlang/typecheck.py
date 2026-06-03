"""Typecheck stage.

Walking-skeleton subset: the player count must be sensible (at least one
player; a range's upper bound must not precede its lower bound). The full
typed object model — zone parameterization, the ``<>`` value-parameter rule,
rule-clause types, outcome exhaustiveness — lands in Phase C.

Like :mod:`cardlang.resolve`, this annotates rather than rewrites: the
(unchanged) :class:`Game` flows on, and the IR stays at the resolved-AST
level.
"""

from __future__ import annotations

from cardlang.ast.nodes import Game
from cardlang.diagnostics import DiagnosticBag, DiagnosticError


def typecheck(game: Game) -> Game:
    bag = DiagnosticBag()

    players = game.players
    if players.low < 1:
        bag.error(f"a game needs at least one player, got {players.low}", players.span)
    if players.high is not None and players.high < players.low:
        bag.error(
            f"player range upper bound {players.high} precedes lower bound {players.low}",
            players.span,
        )

    if bag.has_errors:
        error = DiagnosticError(bag.items[0])
        if len(bag.items) > 1:
            error.add_note(bag.format())
        raise error
    return game
