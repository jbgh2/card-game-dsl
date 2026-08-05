"""`ZoneStore`'s name- and key-keyed lookups fail typed — completeness ledger.

property:   every failing lookup on `ZoneStore` raises `OwnerGuardError`
            naming what it could not find and, for a key miss, the keys the
            family actually has. Never a bare `KeyError` off the underlying
            dict: the name and the instance key are equally capable of
            missing, so neither is left to raw indexing.

domain:     `ZoneStore`'s keyed lookup methods (`single`, `instance`) x their
            failure axes — `single` misses on the zone name only; `instance`
            misses on the family name or on the instance key — x, for the key
            axis, the index role that supplies the family's keys, since the
            message names that role: `player`, `team`, and the declared
            position domains (decisions.md "Position domains and positional
            zones"). Three failure cells; the key cell spans three roles.

registry:   `ZONE_INDEX_ROLES` + a game's declared `positions` block (the key
            axis), and `ZoneStore`'s own method set (the lookup axis). The
            method set is pinned below by derivation from the class rather
            than by a hand-copied list, so a fourth keyed lookup arriving on
            `ZoneStore` fails this module the day it exists.

covered:    all three failure cells and both hits; the key cell over all
            three index roles, including a position-indexed family whose
            keys are neither seats nor teams. Exhaustive over the matrix as
            declared — the index-role axis is enumerated from
            `ZONE_INDEX_ROLES` plus the position case, not sampled.

sampled:    nothing on the failure matrix. The message's key LIST is asserted
            to name the family's real keys, not pinned character-for-character
            — the wall is the currency and the named role, not the rendering.

residual:   the key branch is reachable from a checker-accepted game, not
            only from an engine bug: a zone-family subscript's index is
            checked with `types.assignable`, which admits an Integer, so a
            COMPUTED out-of-range key like `hand[0 + 9]` in a 4-player game
            type-checks and arrives here (the index-strictness residual in
            tests/test_zone_family_typing.py's ledger). An out-of-range player LITERAL
            (`hand[9]`) is now caught earlier by the static player-literal
            wall (typecheck `_check_role_literal`,
            tests/test_player_literal_range.py) — that tightened the literal
            half of the deferral; the computed half is why this is still a
            wall owing a typed error rather than a backstop. Probed below.
            Game-local primitives are outside
            this module's domain — they reach zones through
            cardlang/runtime/reads.py, whose registry and currency are
            pinned by tests/test_primitive_reads.py.
"""

from __future__ import annotations

import inspect

import pytest

from cardlang.pipeline import check_dsl
from cardlang.runtime.errors import OwnerGuardError
from cardlang.runtime.state import ZoneStore

# The lookup axis, derived from the class. A new keyed lookup lands in this
# set automatically and fails `test_the_lookup_axis_is_the_declared_pair`
# until it is given a row in the matrix above.
_KEYED_LOOKUPS: frozenset[str] = frozenset({"single", "instance"})


def _seated_store() -> ZoneStore:
    """One singleton (`deck`), one player-indexed family (`hand`), one
    team-indexed family (`captured`)."""
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
    return ZoneStore(game.zones, (0, 1, 2, 3), (0, 1))


def _positional_store() -> ZoneStore:
    """A position-indexed family, whose keys are neither seats nor teams —
    the role the key-miss message must not misdescribe."""
    game = check_dsl(
        """game G {
  players: 1
  max_length: 100
  direction: clockwise
  cards: standard52
  positions { fslot : 1..4 }
  zones { deck : Deck  foundation[fslot] : Foundation<fslot> }
  state { n[player] : Integer = 0 }
  phase p { move 1 cards from deck to foundation[1] }
  winner: highest n
}""",
        "positional.cardlang",
    )
    positions = {p.name: tuple(range(p.lo, p.hi + 1)) for p in game.positions}
    return ZoneStore(game.zones, (0,), (), positions)


# --- the lookup axis is what the ledger says it is --------------------------


def test_the_lookup_axis_is_the_declared_pair() -> None:
    """The registry pin. `ZoneStore`'s keyed lookups are derived from the
    class, so a fourth one cannot arrive without a row in the matrix above —
    the failure mode a hand-copied list would miss."""
    keyed = {
        name
        for name, member in inspect.getmembers(ZoneStore, inspect.isfunction)
        if not name.startswith("_")
        and "name" in inspect.signature(member).parameters
        and inspect.signature(member).return_annotation == "Zone"
    }
    assert keyed == _KEYED_LOOKUPS


# --- the hits ---------------------------------------------------------------


def test_single_returns_the_declared_singleton() -> None:
    assert _seated_store().single("deck") is not None


def test_instance_returns_the_declared_family_member() -> None:
    zones = _seated_store()
    assert zones.instance("hand", 2) is not None
    assert zones.instance("captured", 1) is not None


# --- the three failure cells ------------------------------------------------


def test_single_refuses_an_undeclared_zone_name() -> None:
    # `pytest.raises(OwnerGuardError)` IS the assertion, not scaffolding for
    # the message check below: a bare `KeyError` off the underlying dict is not
    # an `OwnerGuardError`, so one escaping this block fails the test here.
    # Narrower than the `RuntimeError` this used to name, which would also have
    # accepted a `PrimitiveReadError` — a different Author entirely.
    with pytest.raises(OwnerGuardError) as excinfo:
        _seated_store().single("nonesuch")
    assert "nonesuch" in str(excinfo.value)


def test_instance_refuses_an_undeclared_family_name() -> None:
    with pytest.raises(OwnerGuardError) as excinfo:
        _seated_store().instance("nonesuch", 0)
    assert "nonesuch" in str(excinfo.value)


# --- the key cell, over every index role ------------------------------------


def test_instance_refuses_a_key_a_team_family_does_not_cover() -> None:
    """`captured` is TEAM-indexed, so it covers team ids (0, 1) and not seat
    3 — the shape a caller conflating seats with teams produces."""
    with pytest.raises(OwnerGuardError) as excinfo:
        _seated_store().instance("captured", 3)
    message = str(excinfo.value)
    assert "captured" in message and "team" in message and "[0, 1]" in message


def test_instance_refuses_a_key_a_player_family_does_not_cover() -> None:
    with pytest.raises(OwnerGuardError) as excinfo:
        _seated_store().instance("hand", 9)
    message = str(excinfo.value)
    assert "hand" in message and "player" in message and "[0, 1, 2, 3]" in message


def test_instance_refuses_a_key_a_position_family_does_not_cover() -> None:
    """The role that is neither seats nor teams. A message naming the key
    domain as "seating and teams" is wrong here, and Klondike/FreeCell are
    in-corpus users of position-indexed zones."""
    with pytest.raises(OwnerGuardError) as excinfo:
        _positional_store().instance("foundation", 99)
    message = str(excinfo.value)
    assert "foundation" in message and "fslot" in message
    assert "[1, 2, 3, 4]" in message
    assert "seat" not in message and "team" not in message


# --- the recorded residual, probed ------------------------------------------


def test_a_checker_accepted_game_can_reach_the_key_wall() -> None:
    """The `residual:` cell above, made real. A zone-family index is checked
    with `types.assignable`, which admits an Integer, so `hand[0 + 9]` in a
    4-player game type-checks (the index-strictness residual in this
    module's ledger) and
    arrives here — the wall is author-reachable and owes a typed error rather
    than an assert. The index is COMPUTED (`0 + 9`), not the literal `9`: an
    out-of-range player LITERAL is caught earlier by the static wall
    (typecheck `_check_role_literal`, tests/test_player_literal_range.py),
    which tightened exactly the literal half of this residual; the computed
    half is what keeps this a reachable wall. If the index rule is tightened
    further (computed keys too), this test fails and the residual — and the
    currency argument resting on it — must be revisited."""
    game = check_dsl(
        """game G {
  players: 4
  max_length: 100
  direction: clockwise
  cards: standard52
  zones { deck : Deck  hand[player] : Hand<player> }
  state { n[player] : Integer = 0 }
  phase p { move 1 cards from deck to hand[0 + 9] }
  winner: highest n
}""",
        "reachable.cardlang",
    )
    assert game is not None  # accepted by the checker, so the key reaches the runtime
