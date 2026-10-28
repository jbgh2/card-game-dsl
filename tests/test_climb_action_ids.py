"""Every enumerated combination action id names the cards it names today.

property:        For every corpus game whose climbing round's combo block is an
                 enumerated universe, the combo block's id -> identity table
                 (each play's sorted card ids, in id order) equals the frozen
                 table in `golden/climb_action_ids.json`, row for row.
                 A determinized replay, a stored policy or a trained network
                 keys on these ids, so an engine that re-derives the universe
                 another way must reproduce it id for id.
domain:          Every `docs/games/*.cardlang` whose action space carries
                 combo plays and no combo codec, against every game the golden
                 holds; the two sets must be equal.
registry:        the corpus glob; `ActionSpace.for_game` (the combo block).
held by:         a Pin. The table is frozen: it is written only by
                 `CARDLANG_REGEN_CLIMB_IDS=1`, and a regeneration is a
                 sanctioned id change recorded in the change that makes it.
                 Reddening mutation: put a play's kind into
                 `primitives.action_order`'s key, or drop a play from either
                 engine's universe.
does not prove:  Anything about a codec game (Tichu), whose ids are its codec's
                 and pinned by its round trips (tests/test_openspiel_encoding.py).
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from cardlang.openspiel.encoding import ActionSpace
from cardlang.pipeline import check_source
from cardlang.runtime.values import card_to_action

GAMES = Path(__file__).resolve().parent.parent / "docs" / "games"
GOLDEN = Path(__file__).resolve().parent / "golden" / "climb_action_ids.json"


def _tables() -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    for path in sorted(GAMES.glob("*.cardlang")):
        if "round climb" not in path.read_text():
            continue
        space = ActionSpace.for_game(check_source(str(path)))
        if space._combo_codec is not None or not space._combos:
            continue
        out[path.stem] = [
            " ".join(str(i) for i in sorted(card_to_action(c) for c in p.cards))
            for p in space._combos
        ]
    return out


def test_every_enumerated_combo_block_matches_its_frozen_table() -> None:
    tables = _tables()
    if os.environ.get("CARDLANG_REGEN_CLIMB_IDS") == "1":
        GOLDEN.write_text(json.dumps(tables, indent=0) + "\n")
    frozen: dict[str, list[str]] = json.loads(GOLDEN.read_text())
    assert sorted(tables) == sorted(frozen)
    for game, rows in tables.items():
        assert len(rows) == len(frozen[game]), game
        for aid, (row, want) in enumerate(zip(rows, frozen[game], strict=True)):
            assert row == want, f"{game}: combo id {aid} is {row!r}, frozen as {want!r}"
