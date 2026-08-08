"""Gather order is canonical, never declaration order (cardlang/runtime/execute.py
`_gather`).

A gather (`move all cards to <zone>`) collects from every other zone, emitting
one observation event per non-empty zone and stacking the collected cards into
the destination. Both the event sequence and the resulting card order are
observable (events shape per-player logs, hence information sets; card order
feeds the next same-seed shuffle), so the collection order is part of the
construct's meaning. That meaning is **lexicographic zone-name order** —
singles and families in one sorted namespace, a family's instances in its
index domain's order — NOT the order of the `zones { }` block, which is purely
presentational everywhere in the language (decisions.md, the gather paragraph
under "Lifecycle hooks").
"""

from __future__ import annotations

import random
from typing import Any

from cardlang.ast import nodes as n
from cardlang.pipeline import check_dsl
from cardlang.runtime.execute import execute
from cardlang.runtime.state import Ctx, RuntimeState, ZoneStore
from cardlang.runtime.values import Card, Seating

Event = tuple[Any, ...]


def _mini(zones: str) -> tuple[n.Game, n.Transfer]:
    src = f"""
game Mini {{
  players: 1
  max_length: 1000
  cards: standard52
  zones {{ {zones} }}
  state {{ score[player] : Integer = 0 }}
  phase p {{
    move all cards to deck
  }}
  winner: highest score
}}
"""
    game = check_dsl(src, "mini.cardlang")
    stmt = game.phases[0].items[-1]
    assert isinstance(stmt, n.Transfer)
    return game, stmt


def _gather_events(zones: str, fill: dict[str, list[Card]]) -> tuple[list[Event], list[Card]]:
    """Run the gather over zones pre-filled per `fill` (family instances keyed
    like "hand[0]"); return player 0's observation log and the destination's
    final card order."""
    game, stmt = _mini(zones)
    rs = RuntimeState(Seating(1), ZoneStore(game.zones, (0,)), random.Random(0))
    for where, cards in fill.items():
        if "[" in where:
            fname, key = where[:-1].split("[")
            rs.zones.instance(fname, int(key)).add_all(cards)
        else:
            rs.zones.single(where).add_all(cards)
    def no_chooser(player: int, candidates: list[Any], k: int) -> list[Any]:
        raise AssertionError("a gather never consults the chooser")

    log: list[Event] = []
    ctx = Ctx(
        rs=rs,
        chooser=no_chooser,
        observer=lambda pl, ev: log.append(ev) if pl == 0 else None,
    ).acting_as(0)
    execute(stmt, ctx)
    return log, list(rs.zones.single("deck").cards)


W1, W2 = Card("A", "hearts"), Card("2", "hearts")
C1 = Card("K", "clubs")
H1 = Card("7", "spades")


def test_gather_processes_zones_in_name_order_not_declaration_order() -> None:
    # Declaration order (zpile, hand, apile) disagrees with name order
    # (apile, hand, zpile) — and the family name sorts BETWEEN the singles,
    # so this also pins that singles and families share one sorted namespace
    # rather than iterating singles-then-families.
    events, deck = _gather_events(
        "zpile : Discard  hand[player] : Hand<player>  apile : Discard  deck : Deck",
        {"zpile": [W1, W2], "hand[0]": [H1], "apile": [C1]},
    )
    moves = [e for e in events if e[0] == "move"]
    assert [e[1] for e in moves] == ["apile", "hand[0]", "zpile"]
    assert deck == [C1, H1, W1, W2]


def test_zone_declaration_order_is_meaningless_for_gather() -> None:
    # The same game with its zones block reversed: identical event log,
    # identical destination card order.
    fill = {"zpile": [W1, W2], "hand[0]": [H1], "apile": [C1]}
    a = _gather_events(
        "zpile : Discard  hand[player] : Hand<player>  apile : Discard  deck : Deck",
        fill,
    )
    b = _gather_events(
        "deck : Deck  apile : Discard  hand[player] : Hand<player>  zpile : Discard",
        fill,
    )
    assert a == b
