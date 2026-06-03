"""Emit stage: type-annotated AST -> validated IR.

The IR is the resolved, type-annotated AST rendered as a plain JSON-able
dict — not desugared (docs/building.md, "The AST↔IR seam"). Library
constructs are preserved as tagged nodes. Spans are a front-end diagnostic
concern and are deliberately omitted, so the IR is stable under reformatting
of the source and suitable for golden-file snapshots.

Every node carries a ``kind`` tag so downstream consumers (the future
interpreter, the OpenSpiel adapter) can dispatch without re-deriving shape.
"""

from __future__ import annotations

import json
from typing import TypeAlias

from cardlang.ast.nodes import Game, PlayersSpec, TypeRef, ZoneDecl

IR_VERSION = 1

# A JSON value, as far as the emitter is concerned.
IRValue: TypeAlias = "dict[str, IRValue] | list[IRValue] | str | int | bool | None"


def emit(game: Game) -> dict[str, IRValue]:
    """Lower a validated :class:`Game` to the IR dict."""
    return {
        "cardlang_ir": IR_VERSION,
        "kind": "game",
        "name": game.name,
        "players": _players(game.players),
        "deck": game.deck,
        "zones": [_zone(z) for z in game.zones],
    }


def to_json(game: Game) -> str:
    """Serialize the IR with stable, diff-friendly formatting."""
    return json.dumps(emit(game), indent=2) + "\n"


def _players(players: PlayersSpec) -> IRValue:
    return {
        "kind": "players",
        "low": players.low,
        "high": players.high,
    }


def _zone(zone: ZoneDecl) -> IRValue:
    return {
        "kind": "zone",
        "name": zone.name,
        "index": zone.index,
        "type": _type_ref(zone.type_ref),
    }


def _type_ref(ref: TypeRef) -> IRValue:
    return {
        "kind": "type_ref",
        "name": ref.name,
        "args": [arg.name for arg in ref.args],
    }
