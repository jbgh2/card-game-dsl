"""Bridge compiles all the way to a validated IR.

The full pipeline (parse -> resolve -> typecheck -> emit) on the real
bridge.cardlang, pinned with a golden so any change to the IR shape — in
particular the auction's `turns` ring (its `over`/`until` clauses) and the bid
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


def test_bridge_auction_ring_is_well_formed() -> None:
    """red under: add a second statement to the ring's body in bridge.cardlang
    — the body is no longer one `offer`."""
    ir: Any = compile_path(BRIDGE)
    # The auction phase holds a `turns` ring whose body is one `offer` of the
    # bid vocabulary, terminated by a predicate, and then `produce`s the
    # contract from the phase body.
    rubber = ir["phases"][0]
    auction = next(
        p for p in rubber["items"] if p.get("kind") == "phase" and p["name"] == "auction"
    )
    ring = next(i for i in auction["items"] if i["kind"] == "turns")
    assert ring["until"] is not None
    assert [s["kind"] for s in ring["body"]] == ["offer"]
    assert ring["body"][0]["offering"] == ["pass", "submit_bid", "double", "redouble"]
    assert any(i["kind"] == "if" for i in auction["items"] if isinstance(i, dict))
    assert "auction_round" not in json.dumps(ir)
