"""A movement endpoint (`from <here>` / `to <here>`) must be zone-shaped —
`resolve._bad_zone_endpoint`, the same rule-shape as the write-target wall,
one grammar position over.

The grammar already keeps literals out of endpoint position, so an endpoint is
name-rooted and its root has a classification. Most classifications cannot be
a zone, and each used to sail through the checker: `deal 1 cards from turn to
each hand` (with `turn : Integer = 0`) checked clean and died mid-playout on a
bare AssertionError inside the executor — a statically nameable error, in the
wrong currency, at the wrong time. This was found by the runtime-assert
census: `execute._move`'s `assert isinstance(source, Zone)` had no wall in
front of it.

property:   an endpoint whose root name classifies as anything that cannot
            hold a zone is rejected at resolve, with the classification named
domain:     endpoint position {from, to} × root classification {zone,
            state_var, enum_value, pronoun, local, unresolved}
            (`_classify`'s result kinds; `function`/`null`/`bool` roots
            cannot survive to this wall — an unresolved or reserved name is
            reported by the classifier first, which is also loud)
registry:   `resolve._WRITE_TARGET_KINDS` (the classification vocabulary) and
            the movement grammar's two endpoint slots
covered:    every rejected classification at both positions (parametrized);
            both legal zone shapes (a singleton/family name, a subscripted
            family); the classifier's own rejection for an unresolved root
sampled:    none
residual:   a `local` root is accepted unclassified — a binder may hold a
            zone (`let h = hand[0]`), and locals are untyped until the
            scoped-typing work lands (roadmap.md, "Locals are typed"); the
            executor's Zone check remains the loud backstop for a local
            holding a non-zone
"""

from __future__ import annotations

import pytest

from cardlang.diagnostics import DiagnosticError
from cardlang.pipeline import check_dsl


def _game(body: str) -> str:
    return f"""game G {{
  players: 4
  max_length: 100
  direction: clockwise
  cards: standard52
  zones {{ deck : Deck  hand[player] : Hand<player> }}
  state {{ n[player] : Integer = 0  turn : Integer = 0 }}
  phase p {{ {body} }}
  winner: highest n
}}"""


@pytest.mark.parametrize(
    ("body", "expected"),
    [
        (
            "deal 1 cards from turn to each hand",
            "cannot move cards from 'turn': it is a state variable",
        ),
        (
            "move 1 cards from deck to turn",
            "cannot move cards to 'turn': it is a state variable",
        ),
        (
            "deal 1 cards from hearts to each hand",
            "cannot move cards from 'hearts': it is a value of the deck",
        ),
        (
            "move 1 cards from deck to actor",
            "cannot move cards to 'actor': it is a pronoun",
        ),
        (
            "let x = 1\n    move 1 cards from deck to hand[0]\n    move all cards from tur to deck",
            "unresolved name 'tur'",  # the typo cell: the classifier itself is the wall
        ),
    ],
)
def test_a_non_zone_endpoint_is_rejected_at_resolve(body: str, expected: str) -> None:
    with pytest.raises(DiagnosticError) as excinfo:
        check_dsl(_game(body), "probe.cardlang")
    assert expected in str(excinfo.value)


def test_zone_shaped_endpoints_still_check() -> None:
    # Both legal shapes at both positions: a family gather, a subscripted
    # instance, and the deck singleton.
    check_dsl(
        _game(
            "deal 1 cards from deck to each hand\n"
            "    for each player q: move all cards from hand[q] to deck\n"
            "    move all cards from hand to deck"
        ),
        "probe.cardlang",
    )


def test_a_local_root_is_accepted_the_recorded_residual() -> None:
    # A binder may legitimately hold a zone; locals are untyped until the
    # scoped-typing work lands, so the wall lets `local` roots through and the
    # executor's Zone check stays as the loud backstop. This test pins the
    # residual's SHAPE (accepted at check time), so if locals gain types the
    # residual row and this pin both get revisited.
    check_dsl(
        _game("let h = hand[0]\n    move all cards from h to deck"),
        "probe.cardlang",
    )
