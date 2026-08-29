"""The library-type -> per-observer projection table (decisions.md "Knowledge,
visibility, and the projection model"; library.md "Library zone types")."""

from __future__ import annotations

import pytest

from cardlang.openspiel.registry import GAMES, _GAMES_DIR
from cardlang.openspiel.replay import load
from cardlang.stdlib.zones import (
    LIBRARY_ZONE_TYPES,
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
    (`cardlang/openspiel/game.py::_register`), and what can contradict it.

    "Perfect iff every declared zone type projects identity to all" is the
    obvious derivation of that field, and it discriminates nothing: every game
    in the adapter's registry declares at least one below-identity zone type,
    so the rule is the constant IMPERFECT wearing a function. The comment at
    `_register` states that wall; this is the check that can redden it, on the
    day a corpus game's declared zone types alone make it perfect-information.

    Born green, and reddened by giving `Deck` an identity-to-all projection in
    `ZONE_PROJECTIONS`: the games whose only below-identity type is `Deck`
    declare no other, so their rows fail and name the `_register` site.

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
        f"-- revisit the wall stated at cardlang/openspiel/game.py::_register"
    )
