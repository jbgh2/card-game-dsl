"""`ZoneStore`'s name- and key-keyed lookups fail typed — completeness ledger.

property:   every failing lookup on `ZoneStore` raises a typed `RuntimeError`
            naming what it could not find, never a bare `KeyError` off the
            underlying dict. The name and the instance key are equally
            capable of missing, so neither is left to raw indexing.

domain:     `ZoneStore`'s two keyed lookup methods (`single`, `instance`) x
            their failure axes — `single` misses on the zone name only;
            `instance` misses on the family name or on the instance key.
            Three failure cells, plus the hit on each method.

registry:   the methods themselves (`cardlang/runtime/state.py`). A third
            keyed lookup arriving on `ZoneStore` is in-domain the day it
            exists and belongs in the matrix below.

covered:    all three failure cells and both hits, exhaustively — the matrix
            IS the domain, not a sample of it. Each failure asserts the
            typed currency (`RuntimeError`) AND that a bare `KeyError` does
            not escape, so the test cannot pass vacuously if a branch is
            later replaced by raw indexing.

sampled:    nothing. The domain is closed and small enough to enumerate.

residual:   none. Game-local primitives never reach these methods — they go
            through `cardlang/runtime/reads.py`, whose own registry and
            currency are pinned by tests/test_primitive_reads.py. The
            engine-core callers that DO reach here take names off the
            resolved AST and keys from seating/teams, so these walls are
            backstops for an engine bug rather than for a game description;
            they are held to the typed currency regardless, because a raw
            `KeyError` names neither the zone nor the cause.
"""

from __future__ import annotations

import random

import pytest

from cardlang.pipeline import check_dsl
from cardlang.runtime.state import RuntimeState, ZoneStore
from cardlang.runtime.values import Seating


def _store() -> ZoneStore:
    """A live store with one singleton (`deck`), one player-indexed family
    (`hand`), and one team-indexed family (`captured`)."""
    game = check_dsl(
        """game G {
  players: 4
  partnerships: [[0, 2], [1, 3]]
  max_length: 100
  direction: clockwise
  cards: standard52
  zones { deck : Deck  hand[player] : Hand<player>  captured[team] : TeamPile<team> }
  state { n[player] : Integer = 0 }
  phase p { deal 1 cards from deck to each hand }
  winner: highest n
}""",
        "zonestore.cardlang",
    )
    rs = RuntimeState(Seating(4), ZoneStore(game.zones, (0, 1, 2, 3), (0, 1)), random.Random(0))
    return rs.zones


# --- the hits: each method returns the zone it names ------------------------


def test_single_returns_the_declared_singleton() -> None:
    assert _store().single("deck") is not None


def test_instance_returns_the_declared_family_member() -> None:
    zones = _store()
    assert zones.instance("hand", 2) is not None
    assert zones.instance("captured", 1) is not None


# --- the three failure cells ------------------------------------------------


def test_single_refuses_an_undeclared_zone_name() -> None:
    with pytest.raises(RuntimeError) as excinfo:
        _store().single("nonesuch")
    assert "nonesuch" in str(excinfo.value)
    assert not isinstance(excinfo.value, KeyError)


def test_instance_refuses_an_undeclared_family_name() -> None:
    with pytest.raises(RuntimeError) as excinfo:
        _store().instance("nonesuch", 0)
    assert "nonesuch" in str(excinfo.value)
    assert not isinstance(excinfo.value, KeyError)


def test_instance_refuses_a_key_the_family_does_not_cover() -> None:
    """The cell this module was added for. `captured` is TEAM-indexed, so it
    covers team ids (0, 1) and not seat 3 — the shape a caller conflating
    seats with teams produces. Left to raw indexing this is a bare
    `KeyError: 3`, naming neither the family nor the reason."""
    with pytest.raises(RuntimeError) as excinfo:
        _store().instance("captured", 3)
    message = str(excinfo.value)
    assert "captured" in message and "3" in message
    assert not isinstance(excinfo.value, KeyError)


def test_a_player_indexed_family_refuses_a_non_seat_key() -> None:
    """The same cell on the other index role: `hand` covers seats 0-3, so a
    key past the table is refused rather than key-erroring."""
    with pytest.raises(RuntimeError) as excinfo:
        _store().instance("hand", 9)
    assert "hand" in str(excinfo.value)
    assert not isinstance(excinfo.value, KeyError)
