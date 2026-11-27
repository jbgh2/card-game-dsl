"""The library-type -> per-observer projection table (decisions.md "Knowledge,
visibility, and the projection model"; library.md "Library zone types")."""

from __future__ import annotations

from typing import cast

import pytest

from cardlang.openspiel.registry import GAMES, _GAMES_DIR
from cardlang.openspiel.replay import load
from cardlang.runtime.observe import _projected
from cardlang.runtime.values import Card
from cardlang.stdlib.zones import (
    LIBRARY_ZONE_TYPES,
    PROJECTION_LEVELS,
    ProjectionLevel,
    ZONE_PROJECTIONS,
    identity_to_all,
    zone_projection,
)


def test_every_library_type_has_a_projection() -> None:
    assert set(ZONE_PROJECTIONS) == set(LIBRARY_ZONE_TYPES)


def test_hand_is_identity_to_owner_count_to_others() -> None:
    assert zone_projection("Hand", is_owner=True) == "identity"
    assert zone_projection("Hand", is_owner=False) == "count_only"


def test_public_zones_are_identity_to_all() -> None:
    for t in ("PublicHand", "TrickPile", "Discard", "PlayerPile", "TeamPile"):
        assert zone_projection(t, is_owner=False) == "identity"


def test_hidden_and_dead_zones() -> None:
    for t in ("Deck", "FaceDownPile", "ChipStack"):
        assert zone_projection(t, is_owner=False) == "count_only"
    for t in ("Muck", "Burn"):
        assert zone_projection(t, is_owner=True) == "trivial"


@pytest.mark.parametrize("zone_type", sorted(ZONE_PROJECTIONS))
def test_a_zone_its_owner_sees_shows_every_other_seat_at_least_a_count(zone_type: str) -> None:
    """A chosen movement draws from a zone its decider can see, so a type
    whose owner sees identity is a source some seat picks from; every other
    seat must then see at least a count of it, or a pick there would reach a
    bystander as nothing at all. The Length Stop is a function of how many
    picks a line has made, and that is what keeps the count every seat's:
    the stop is common knowledge (docs/decisions.md, "Game length as a
    declared contract").

    red under: plant `"SecretHand": ZoneVisibility("identity", "trivial")`
    in `ZONE_PROJECTIONS`."""
    vis = ZONE_PROJECTIONS[zone_type]
    if vis.owner != "identity":
        return
    assert PROJECTION_LEVELS.index(vis.others) >= PROJECTION_LEVELS.index("count_only"), (
        f"{zone_type} shows its owner identity and every other seat {vis.others}"
    )


def test_unknown_type_fails_loudly() -> None:
    with pytest.raises(KeyError):
        zone_projection("NoSuchZoneType", is_owner=False)


@pytest.mark.parametrize(
    "short_name,filename", sorted(GAMES.items()), ids=sorted(GAMES)
)
def test_no_corpus_game_is_perfect_information_by_zone_type_alone(
    short_name: str, filename: str
) -> None:
    """The wall behind the adapter's asserted `information` field
    (`cardlang/openspiel/game.py::_plan`), and what can contradict it.

    "Perfect iff every declared zone type projects identity to all" is the
    obvious derivation of that field, and it discriminates nothing: every game
    in the adapter's registry declares at least one below-identity zone type,
    so the rule is the constant IMPERFECT wearing a function. The comment at
    `_plan` states that wall; this is the check that can redden it, on the
    day a corpus game's declared zone types alone make it perfect-information.

    Born green, and reddened by giving `Deck` an identity-to-all projection in
    `ZONE_PROJECTIONS`: the games whose only below-identity type is `Deck`
    declare no other, so their rows fail and name the `_plan` site.

    A green does not say the corpus holds no perfect-information game -- the
    proof modules under `tests/openspiel_ready/` assert the singleton
    partition for several. It says only that what makes them so is
    unreachable from zone types, being a fact about the run: their one
    count-projected zone empties before play and is populated at no decision
    node.
    """
    game, _ = load(str(_GAMES_DIR / filename))
    below = sorted(
        {z.type_ref.name for z in game.zones if not identity_to_all(z.type_ref.name)}
    )
    assert below, (
        f"{short_name} declares only identity-to-all zone types, so the "
        f"zone-type derivation of GameType.information is no longer vacuous "
        f"-- revisit the wall stated at cardlang/openspiel/game.py::_plan"
    )


# What `view_of` answers at each level the engine builds, authored from
# decisions.md's table ("Projections: what visibility controls"): the cards
# themselves in their rendering order, one integer, or nothing.
_SHAPE = {"identity": tuple, "count_only": int, "trivial": type(None)}


@pytest.mark.parametrize("level", PROJECTION_LEVELS)
def test_view_of_answers_every_built_level(level: ProjectionLevel) -> None:
    """One cell per `ProjectionLevel`: the domain is the type, so a level
    built without its expected shape here is red. red under: `_projected`'s
    `count_only` arm answering the cards."""
    cards = [Card("K", "clubs"), Card("2", "hearts")]
    view = _projected(level, cards)
    assert type(view) is _SHAPE[level]
    if level == "identity":
        assert view == tuple(sorted(cards, key=str))
    if level == "count_only":
        assert view == 2


@pytest.mark.parametrize("level", ["identity_set", "count_by_type", "existence_only"])
def test_an_unbuilt_level_is_refused_where_it_is_projected(level: str) -> None:
    """Past the type check (a value cast in), an unbuilt level is refused
    loudly by the exhaustive match rather than rendered as something else."""
    with pytest.raises(AssertionError):
        _projected(cast(ProjectionLevel, level), [Card("K", "clubs")])
