"""Result rankings: the `winner:` clause and Stop Results.

A shared module: the steps read it, and it imports no step.

Contract (decisions.md "Closed-domain completeness", write-time triage)
-----------------------------------------------------------------------
Establishes:  each result ranking's slot (``ranking_slot``), read by
              every step that judges a result ranking.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import assert_never
from cardlang.ast import nodes as n


@dataclass(frozen=True, slots=True)
class RankingSlot:
    """How the ranking guards address one slot a game ranks a state variable
    in: `winner:`, and the Stop Result's ranking."""

    clause: str     # the slot as the designer wrote it
    ranks: str      # what the slot ranks: "<clause> ranks <ranks> on ..."
    unknown: str    # the unknown-variable refusal's subject
    # Why a phase's variable cannot be the target, true at the slot: a
    # `winner:` is decided once every phase has exited, while a Length Stop
    # can fall while the declaring phase still runs.
    phase_reason: str

    def out_of_scope(self, target: str, home: str) -> str:
        return (
            f"{self.clause} ranks on state variable '{target}', which is "
            f"declared in {home} and so {self.phase_reason}. Declare it at "
            f"game level"
        )


_WINNER_SLOT = RankingSlot(
    "`winner:`",
    "the game",
    "winner",
    "does not exist when the winner is decided — the phase has exited by then",
)
_STOP_SLOT = RankingSlot(
    "`at max_length:`",
    "the stopped game",
    "`at max_length:`",
    "exists only while that phase runs; the bound can stop the game in any "
    "phase, so the stop cannot be scored from it",
)


def ranking_slot(ranking: n.Winner | n.StopResult) -> RankingSlot:
    """How the ranking guards address the slot `ranking` is written in. The
    grid crossing the target's declaration with the slot is
    tests/test_winner_target.py, its slot axis reconciled against the
    grammar's productions taking `RESULT_VAR_NAME`."""
    match ranking:
        case n.Winner():
            return _WINNER_SLOT
        case n.StopResult():
            return _STOP_SLOT
        case _ as unreachable:
            assert_never(unreachable)


def _result_rankings(game: n.Game) -> tuple[n.Winner | n.StopResult, ...]:
    """The game's result rankings: its `winner:` clause, and its Stop Result
    when that is a ranking."""
    out: list[n.Winner | n.StopResult] = []
    if game.winner is not None:
        out.append(game.winner)
    if game.stop_result is not None and game.stop_result.kind == "ranking":
        out.append(game.stop_result)
    return tuple(out)
