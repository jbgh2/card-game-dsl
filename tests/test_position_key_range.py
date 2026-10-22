"""A literal key into a positional zone family lies in its declared domain.

property:   a zone family indexed by a declared integer position domain,
            subscripted with an integer literal outside that domain, is
            refused at check time, at the subscript, naming the domain and its
            range; a literal inside it checks clean and plays; a computed key
            is the runtime's (`ZoneStore.instance`).
domain:     literal key x subscript position. Keys: one below the domain,
            its two ends, one above it, and a negative literal, for the
            domain `1..3`. Positions: a deal destination, a movement source
            and an expression read. A literal passed to a function or
            procedure parameter typed by the domain is the argument position,
            marked below (issue #928). A board's cell domain is named, so an
            integer key there is a type refusal, never a range one.
registry:   position domains: `n.Game.positions` (`PositionDecl.lo`/`hi`),
            read into `TypeEnv.family_ranges`; the seat and team twins:
            tests/test_player_literal_range.py.
does not prove:  a key a `let` or a function computes: the runtime refuses it
            at the read.
"""

from __future__ import annotations

import random

import pytest

from cardlang.diagnostics import DiagnosticError
from cardlang.pipeline import check_dsl
from cardlang.runtime.driver import play_game

_HOST = """game G {{
  players: 2
  max_length: 20
  cards: standard52
  positions {{ col : 1..3 }}
  zones {{ deck : Deck  stack[col] : Cascade<col>  pile : Discard }}
  state {{ score[player] : Integer = 0 }}
  phase play {{
    shuffle deck
    {body}
  }}
  winner: highest score
}}
{defs}
"""

POSITIONS: dict[str, str] = {
    "deal destination": "deal 1 card from deck to stack[{k}]",
    "movement source": "deal 1 card from deck to stack[1]\n    move all cards from stack[{k}] to pile",
    "expression read": "score[0] := number of cards in stack[{k}]",
}
KEYS = (0, 1, 3, 4, -1)


def _in_range(k: int) -> bool:
    return 1 <= k <= 3


CELLS = [
    pytest.param(position, k, id=f"{position}-{k}") for position in POSITIONS for k in KEYS
]


@pytest.mark.parametrize(("position", "k"), CELLS)
def test_a_literal_key_lies_in_its_domain(position: str, k: int) -> None:
    src = _HOST.format(body=POSITIONS[position].format(k=k), defs="")
    if _in_range(k):
        play_game(check_dsl(src, "g.cardlang"), random.Random(0))
        return
    with pytest.raises(DiagnosticError) as exc:
        check_dsl(src, "g.cardlang")
    msg = str(exc.value)
    assert f"stack[{k}]" in msg and "col" in msg and "1..3" in msg, msg


def test_a_computed_key_is_the_runtimes() -> None:
    """Born green: the check reads literals only.

    red under: refuse every non-literal key into a position-indexed family."""
    check_dsl(_HOST.format(body="let k = 1\n    deal 1 card from deck to stack[k + 5]", defs=""), "g.cardlang")


@pytest.mark.xfail(
    strict=True,
    raises=AssertionError,
    reason="issue #928: a literal argument to a domain-typed parameter is not ranged",
)
def test_a_literal_argument_to_a_domain_typed_parameter_is_ranged() -> None:
    src = _HOST.format(
        body="score[0] := f(4)",
        defs="function f(c : col) = number of cards in stack[c]",
    )
    try:
        check_dsl(src, "g.cardlang")
    except DiagnosticError:
        return
    raise AssertionError("a literal 4 passed as a `col` checked clean")
