"""The observer channel and zone-type retention (SP1 spec, Pillar 1)."""

from __future__ import annotations

import random
from typing import Any

from cardlang.ast import nodes as n
from cardlang.runtime.state import Ctx, RuntimeState, ZoneStore
from cardlang.runtime.values import Seating


def _store() -> ZoneStore:
    decls = (
        n.ZoneDecl(name="deck", index=None, type_ref=n.TypeRef(name="Deck")),
        n.ZoneDecl(name="hand", index="player", type_ref=n.TypeRef(name="Hand")),
        n.ZoneDecl(name="captured", index="team", type_ref=n.TypeRef(name="TeamPile")),
    )
    return ZoneStore(decls, players=(0, 1, 2, 3), teams=(0, 1))


def test_zone_store_retains_declared_types_and_index() -> None:
    zs = _store()
    assert zs.zone_type == {"deck": "Deck", "hand": "Hand", "captured": "TeamPile"}
    assert zs.zone_index == {"deck": None, "hand": "player", "captured": "team"}


def test_locate_finds_singles_and_family_instances() -> None:
    zs = _store()
    assert zs.locate(zs.single("deck")) == ("deck", None)
    assert zs.locate(zs.instance("hand", 2)) == ("hand", 2)
    assert zs.locate(zs.instance("captured", 1)) == ("captured", 1)


def test_ctx_observer_defaults_to_none_and_observe_is_noop() -> None:
    rs = RuntimeState(Seating(4), _store(), random.Random(0))
    ctx = Ctx(rs=rs, chooser=lambda p, c, k: list(c)[:k])
    ctx.observe(0, ("announce", 1, "pass"))  # must not raise


def test_ctx_observe_delivers_to_installed_observer() -> None:
    rs = RuntimeState(Seating(4), _store(), random.Random(0))
    seen: list[tuple[int, tuple[Any, ...]]] = []
    ctx = Ctx(
        rs=rs,
        chooser=lambda p, c, k: list(c)[:k],
        observer=lambda pl, ev: seen.append((pl, ev)),
    )
    ctx.observe(2, ("chose", "Q spades"))
    assert seen == [(2, ("chose", "Q spades"))]
