"""Pinochle compiles all the way to a validated IR.

The full pipeline (parse -> resolve -> typecheck -> emit) on the real
pinochle.cardlang, pinned with a golden file so any change to the IR shape — in
particular the auction `round` on the shrinking participants ring — is a
reviewable diff. Regenerate deliberately with ``UPDATE_GOLDEN=1 pytest``.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from cardlang.pipeline import compile_path

PINOCHLE = Path(__file__).parent.parent / "docs" / "games" / "pinochle.cardlang"
GOLDEN = Path(__file__).parent / "golden" / "pinochle.ir.json"


def test_pinochle_ir_matches_golden() -> None:
    ir = compile_path(PINOCHLE)
    rendered = json.dumps(ir, indent=2) + "\n"

    if os.environ.get("UPDATE_GOLDEN"):
        GOLDEN.write_text(rendered)

    assert rendered == GOLDEN.read_text()


def test_pinochle_ir_is_well_formed() -> None:
    ir = compile_path(PINOCHLE)
    assert ir["cardlang_ir"] == 1 and ir["kind"] == "game"
    assert isinstance(ir["phases"], list) and len(ir["phases"]) == 1
