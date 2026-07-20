"""Zone capacity: `ZONE_CAPACITY` (cardlang/stdlib/zones.py) and the movement
executor's overfill wall (`cardlang/runtime/execute.py::_deposit`).

property:   every LIBRARY_ZONE_TYPES row declares a capacity (an int or None
            for unbounded); every runtime append to a zone routes through the
            one capacity-checked helper, so a finite-capacity zone type
            (Cell) can never end up holding more than its declared capacity
domain:     LIBRARY_ZONE_TYPES rows (16) x the runtime's zone-append call
            sites
registry:   cardlang/stdlib/zones.py::ZONE_CAPACITY
covered:    the registry-total pin (set(ZONE_CAPACITY) == set(
            LIBRARY_ZONE_TYPES)) — NOT vacuous: red under: deleting the
            `"Cell": 1,` row from ZONE_CAPACITY (verified by hand — the pin
            failed with `AssertionError: ... Extra items in the right set:
            'Cell'`, then reverted; see also this module's registry-total
            test below); zone_capacity()'s KeyError-
            loud behavior on an unknown type; the overfill probe (2 cards
            dealt into an empty Cell — typed RuntimeError, exact message);
            both capacity-boundary probes (1 card into an empty Cell
            succeeds and leaves the zone AT capacity; one more card into
            that now-full Cell overfills); FreeCell (the corpus's one Cell-
            typed game) still typechecks clean and a random playout never
            trips the wall (its own guard, `cells[slot] is empty`, makes
            every to_cell move a no-op once the cell is full — direct
            evidence here, corroborated externally by the full
            tests/test_playout_freecell.py run recorded in the task report)

            Routed call sites, all through cardlang/runtime/execute.py's one
            `_deposit(ctx, dest, cards)` helper — the sole place any zone
            gains cards at runtime within this module's lane:
              - _movement, the `to each` distributed-parcel branch
              - _movement, the single-destination branch
              - _deal_round_robin, the unfiltered branch
              - _deal_round_robin, the filtered branch
              - _gather (the sourceless `move all cards to <zone>` form)
              - _apply_pass (the `each ... simultaneously` pass, e.g. Hearts'
                card-passing phase)
sampled:    none
residual:   the `Point` row (an unbounded stack, backgammon's witness — see
            docs/design-notes/board-topology.md) is not added until board-
            topology stage 3; docs/roadmap.md records it.

            Two zone-append call sites are NOT routed through `_deposit`,
            and are out of this task's lane (cardlang/runtime/mechanics.py):
            `TrickForm.apply`'s `ctx.rs.zones.single(self.play_zone).add(...)`
            and `ClimbForm.apply`'s `self.pile.add_all(...)`. resolve.py only
            checks that `play_zone` names a KNOWN zone, never its declared
            TYPE (cardlang/resolve.py, the `nd.play_zone not in zone_names`
            checks) — so a future game pointing a round's play zone at a
            Cell is reachable IN PRINCIPLE, not statically walled. It is not
            corpus-reachable today: every round/trick/climb form is card-
            flavored (docs/roadmap.md, "Piece-flavored games"), and Cell is
            used by exactly one corpus game (FreeCell), which uses no round
            form. This is a genuine gap, not a proven-safe exclusion.

            cardlang/runtime/driver.py:102's initial deck-seeding append
            (`rs.zones.single(rs.deck_zone).add_all(...)`) is also unrouted,
            but for a different reason: `rs.deck_zone` is selected by
            `type_ref.name == "Deck"`, which this registry always maps to
            unbounded capacity, so that append is audited-safe rather than a
            gap.
"""

from __future__ import annotations

import random
from pathlib import Path
from typing import Any

import pytest

from cardlang.ast import nodes as n
from cardlang.pipeline import check_dsl, check_source
from cardlang.runtime.driver import play_game
from cardlang.runtime.execute import execute
from cardlang.runtime.state import Ctx, RuntimeState, ZoneStore
from cardlang.runtime.values import Card, Seating
from cardlang.stdlib.zones import LIBRARY_ZONE_TYPES, ZONE_CAPACITY, zone_capacity

FREECELL = Path(__file__).parent.parent / "docs" / "games" / "freecell.cardlang"

HEARTS_A = Card("A", "hearts")
HEARTS_2 = Card("2", "hearts")


def test_zone_capacity_is_total_over_library_zone_types() -> None:
    """The registry-total pin. red under: deleting the `"Cell": 1,` row from
    ZONE_CAPACITY reddens this exact assertion (verified by hand, reverted;
    see the module docstring's `covered` entry)."""
    assert set(ZONE_CAPACITY) == set(LIBRARY_ZONE_TYPES)


def test_zone_capacity_matches_the_declared_rows() -> None:
    assert zone_capacity("Cell") == 1
    assert all(
        zone_capacity(name) is None for name in LIBRARY_ZONE_TYPES if name != "Cell"
    )


def test_zone_capacity_is_keyerror_loud_for_an_unknown_type() -> None:
    with pytest.raises(KeyError):
        zone_capacity("NotAZoneType")


# --- the overfill wall, driven through a synthetic minimal game ---


def _dealt_chooser(player: int, candidates: list[Any], k: int) -> list[Any]:
    # Every probe below uses the default (dealt) selection mode, which never
    # calls the chooser -- present only because Ctx requires one.
    return list(candidates[:k])


def _parse(stmt_src: str) -> tuple[n.Game, n.Movement]:
    src = f"""
game Mini {{
  players: 1
  max_length: 1000
  cards: standard52
  zones {{ deck : Deck  hand[player] : Hand<player>  slot[player] : Cell<player> }}
  state {{ score[player] : Integer = 0 }}
  phase p {{
    {stmt_src}
  }}
  winner: highest score
}}
"""
    game = check_dsl(src, "mini.cardlang")
    stmt = game.phases[0].items[-1]
    assert isinstance(stmt, n.Movement)
    return game, stmt


def _ctx(
    game: n.Game, hand_cards: list[Card], slot_cards: list[Card] | None = None
) -> Ctx:
    rs = RuntimeState(Seating(1), ZoneStore(game.zones, (0,)), random.Random(0))
    rs.zones.instance("hand", 0).add_all(hand_cards)
    rs.zones.instance("slot", 0).add_all(slot_cards or [])
    return Ctx(rs=rs, chooser=_dealt_chooser).acting_as(0)


def test_two_cards_dealt_into_an_empty_cell_overfills() -> None:
    game, stmt = _parse("move 2 cards from hand[0] to slot[0]")
    ctx = _ctx(game, [HEARTS_A, HEARTS_2])
    with pytest.raises(RuntimeError) as excinfo:
        execute(stmt, ctx)
    assert str(excinfo.value) == (
        "zone 'slot[0]' is a Cell (capacity 1) and already holds 0 — the "
        "move would overfill it; guard the move (`slot[0] is empty`)"
    )


def test_one_card_into_an_empty_cell_succeeds_and_fills_it() -> None:
    game, stmt = _parse("move 1 cards from hand[0] to slot[0]")
    ctx = _ctx(game, [HEARTS_A])
    execute(stmt, ctx)
    assert ctx.rs.zones.instance("slot", 0).cards == [HEARTS_A]


def test_one_more_card_into_an_already_full_cell_overfills() -> None:
    game, stmt = _parse("move 1 cards from hand[0] to slot[0]")
    ctx = _ctx(game, [HEARTS_2], slot_cards=[HEARTS_A])
    with pytest.raises(RuntimeError) as excinfo:
        execute(stmt, ctx)
    assert str(excinfo.value) == (
        "zone 'slot[0]' is a Cell (capacity 1) and already holds 1 — the "
        "move would overfill it; guard the move (`slot[0] is empty`)"
    )
    # The destination is never touched -- the guard runs before the append.
    # (Selection already removed the card from the source by this point; that
    # is harmless, since this RuntimeError is fatal and uncaught anywhere in
    # the runtime -- no continuation could observe a card "in transit".)
    assert ctx.rs.zones.instance("slot", 0).cards == [HEARTS_A]


# --- the negative: FreeCell's honest guards keep the wall from ever firing ---


def test_freecell_corpus_game_still_typechecks_clean() -> None:
    check_source(FREECELL)  # parse -> resolve -> typecheck -> deck-capacity; must not raise


def test_freecell_playout_never_trips_the_capacity_wall() -> None:
    """FreeCell's `to_cell` move type guards on `cells[slot] is empty`, so an
    honest playout should never reach `_deposit`'s overfill branch -- a
    RuntimeError here would mean either the wall or the guard is wrong.
    Complements the full tests/test_playout_freecell.py run (its own
    per-decision `len(cell) <= 1` invariant checks), recorded as external
    evidence in the task report."""
    game = check_source(FREECELL)
    for seed in range(5):
        result = play_game(game, random.Random(seed))
        assert result.winner == 0  # the sole player, in a 1-player game
