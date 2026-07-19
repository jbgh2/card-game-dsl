"""A zone-position expression — a movement endpoint (`from <here>` /
`to <here>`) or an epistemic op's target (`shuffle <here>`, `reveal …`) — must
be zone-shaped: `resolve._bad_zone_endpoint`, the same rule-shape as the
write-target wall, one grammar position over.

The grammar already keeps literals out of these positions, so each is
name-rooted and its root has a classification. Most classifications cannot be
a zone, and without this wall each would sail through the checker: `deal 1
cards from turn to each hand` and `shuffle turn` (with `turn : Integer = 0`)
would check clean and die mid-playout on the executor's non-zone guard — a
statically nameable error surfacing at play time instead of check time. The
class here is the CONSUMERS of the executor's zone guards (`execute._movement`
and `execute._epistemic` alike), not "movement statements": scoping it to
movement alone leaves the epistemic member unwalled.

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
residual:   a `local` root whose initializer types `TAny` (an `outcome`
            pronoun, an unregistered action field) is accepted — gradual
            typing's ordinary rule, not a blind spot: lets are TYPED now, so
            `let h = 3` is rejected at check time (the type half of the rule,
            `_check_movement`) while `let h = hand[0]` still passes on its
            merits. The executor's typed RuntimeError remains the backstop
            for the TAny path (tests/test_fail_loud.py pins it directly).
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
        (
            # The non-NameRef cell of the same wall: a subscripted destination
            # under `each` would slip past a wall guarding only bare names
            # and die on the executor's NameRef assert.
            "deal 1 cards from deck to each hand[0]",
            "`to each` deals into a player-indexed family named bare",
        ),
    ],
)
def test_to_each_requires_a_player_indexed_family(body: str, expected: str) -> None:
    """The arity axis of the zone-position domain. `to each X` deals one
    parcel per PLAYER (the executor iterates seats and keys X[player]), so
    without this wall a singleton and a TEAM family alike would reach the zone
    store, which serves only keys its family actually covers — player keying is
    assumed at the executor, and this wall is what checks it at the surface."""
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


def test_a_zone_valued_local_is_accepted_and_a_non_zone_one_is_not() -> None:
    # Both halves of the rule at the `local` root. Resolve's classification
    # wall lets any binder through (a binder MAY hold a zone); the type half
    # (`_check_movement`, now that lets are typed) decides by what the binder
    # actually holds.
    check_dsl(
        _game("let h = hand[0]\n    move all cards from h to deck"),
        "probe.cardlang",
    )
    with pytest.raises(DiagnosticError) as excinfo:
        check_dsl(
            _game("let h = 3\n    move all cards from h to deck"),
            "probe.cardlang",
        )
    assert "movement source must be a zone, got Integer" in str(excinfo.value)
    with pytest.raises(DiagnosticError) as excinfo:
        check_dsl(_game("let h = 3\n    shuffle h"), "probe.cardlang")
    assert "'shuffle' target must be a zone, got Integer" in str(excinfo.value)
