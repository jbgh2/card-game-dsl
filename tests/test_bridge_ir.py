"""Bridge compiles all the way to a validated IR.

The full pipeline (parse -> resolve -> typecheck -> emit) on the real
bridge.cardlang, pinned with a golden so any change to the IR shape — in
particular the auction form of `round` (the `offering`/`until` axes) and the bid
offering — is a reviewable diff. Regenerate deliberately with
``UPDATE_GOLDEN=1 pytest``.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from cardlang.pipeline import compile_path

BRIDGE = Path(__file__).parent.parent / "docs" / "games" / "bridge.cardlang"
GOLDEN = Path(__file__).parent / "golden" / "bridge.ir.json"


def test_bridge_ir_matches_golden() -> None:
    ir = compile_path(BRIDGE)
    rendered = json.dumps(ir, indent=2) + "\n"

    if os.environ.get("UPDATE_GOLDEN"):
        GOLDEN.write_text(rendered)

    assert rendered == GOLDEN.read_text()


def test_bridge_auction_round_is_well_formed() -> None:
    ir: Any = compile_path(BRIDGE)
    # The auction phase holds a round in its auction form: a move vocabulary and a
    # termination predicate, with the trick-only card zones absent.
    rubber = ir["phases"][0]
    auction = next(
        p for p in rubber["items"] if p.get("kind") == "phase" and p["name"] == "auction"
    )
    rnd = next(i for i in auction["items"] if i["kind"] == "auction_round")
    assert rnd["offering"] == ["pass", "submit_bid", "double", "redouble"]
    assert rnd["termination"] is not None
    # The trick-only keys are not present-and-null: the auction form's IR does
    # not carry them at all.
    assert not {"move_type", "source_zone", "play_zone"} & rnd.keys()
