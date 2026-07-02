"""The library-type -> per-observer projection table (decisions.md "Knowledge,
visibility, and the projection model"; library.md "Library zone types")."""

from __future__ import annotations

import pytest

from cardlang.stdlib.zones import (
    LIBRARY_ZONE_TYPES,
    ZONE_PROJECTIONS,
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
