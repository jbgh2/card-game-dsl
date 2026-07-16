"""A zone-position expression — a movement endpoint (`from <here>` /
`to <here>`) or an epistemic op's target (`shuffle <here>`, `reveal …`) — must
be zone-shaped: `resolve._bad_zone_endpoint`, the same rule-shape as the
write-target wall, one grammar position over.

The grammar already keeps literals out of these positions, so each is
name-rooted and its root has a classification. Most classifications cannot be
a zone, and each used to sail through the checker: `deal 1 cards from turn to
each hand` and `shuffle turn` (with `turn : Integer = 0`) checked clean and
died mid-playout on a bare AssertionError inside the executor — a statically
nameable error, in the wrong currency, at the wrong time. Found by the
runtime-assert census (`execute._move` / `execute._epistemic`'s Zone asserts
had no wall in front of them); the epistemic member of the class was found by
review after the movement member shipped alone — the class is the CONSUMERS of
the executor's Zone asserts, not "movement statements".

property:   a zone-position whose root name classifies as anything that
            cannot hold a zone is rejected at resolve, with the
            classification named
domain:     zone position {movement from, movement to, epistemic target}
            × root classification {zone, state_var, enum_value, pronoun,
            null, bool, local, unresolved} (`_classify`'s result kinds plus
            the reserved literals; a `function` root cannot survive — the
            classifier reports it as unresolved first, which is also loud);
            plus the ARITY axis for `to each` (singleton / player family /
            team family — the executor keys parcels per player, so only a
            player-indexed family is legal there)
registry:   `resolve._WRITE_TARGET_KINDS` (the classification vocabulary) and
            the grammar's zone-position slots
covered:    every rejected classification, each probed at two or more
            positions (parametrized); both legal zone shapes (a
            singleton/family name, a subscripted family); the classifier's
            own rejection for an unresolved root
sampled:    none
residual:   a `local` root is accepted unclassified — a binder may hold a
            zone (`let h = hand[0]`), and locals are untyped until the
            scoped-typing work lands (design-notes/scope-once.md; roadmap.md,
            "A `let`-bound name has no static type"); the executor's Zone
            check remains the loud backstop for a local holding a non-zone
"""

from __future__ import annotations

import pytest

from cardlang.diagnostics import DiagnosticError
from cardlang.pipeline import check_dsl


def _game(body: str) -> str:
    return f"""game G {{
  players: 4
  partnerships: [[0, 2], [1, 3]]
  max_length: 100
  direction: clockwise
  cards: standard52
  zones {{ deck : Deck  hand[player] : Hand<player>  pile : Discard
           captured[team] : TeamPile<team> }}
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
            "move 1 cards from deck to hearts",
            "cannot move cards to 'hearts': it is a value of the deck",
        ),
        (
            "move 1 cards from deck to actor",
            "cannot move cards to 'actor': it is a pronoun",
        ),
        (
            "deal 1 cards from actor to each hand",
            "cannot move cards from 'actor': it is a pronoun",
        ),
        (
            "move 1 cards from none to deck",
            "cannot move cards from 'none': it is the literal `none`",
        ),
        (
            "move 1 cards from deck to true",
            "cannot move cards to 'true': it is a boolean literal",
        ),
        (
            "shuffle turn",
            "cannot shuffle 'turn': it is a state variable, not a zone",
        ),
        (
            "reveal one card from turn",
            "cannot reveal 'turn': it is a state variable, not a zone",
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


@pytest.mark.parametrize(
    ("body", "expected"),
    [
        (
            "deal 1 cards from deck to each pile",
            "`to each pile` deals one parcel per player, but 'pile' is a "
            "singleton zone",
        ),
        (
            "deal 1 cards from deck to each captured",
            "`to each captured` deals one parcel per player, but 'captured' "
            "is a family keyed by team",
        ),
    ],
)
def test_to_each_requires_a_player_indexed_family(body: str, expected: str) -> None:
    """The arity axis of the zone-position domain. `to each X` deals one
    parcel per PLAYER (the executor iterates seats and keys X[player]), so a
    singleton used to die on a raw KeyError, and a TEAM family silently dealt
    into team slots AS IF team ids were seats before crashing — player keying
    was assumed at the executor, never checked at the surface."""
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
