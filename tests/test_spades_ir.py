"""Spades compiles all the way to a validated IR.

The full pipeline (parse -> resolve -> typecheck -> emit) on the real
spades.cardlang, pinned with a golden file so any change to the IR shape is a
reviewable diff. Regenerate deliberately with ``UPDATE_GOLDEN=1 pytest``.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from cardlang.pipeline import compile_path

SPADES = Path(__file__).parent.parent / "docs" / "games" / "spades.cardlang"
GOLDEN = Path(__file__).parent / "golden" / "spades.ir.json"


def test_spades_ir_matches_golden() -> None:
    ir = compile_path(SPADES)
    rendered = json.dumps(ir, indent=2) + "\n"

    if os.environ.get("UPDATE_GOLDEN"):
        GOLDEN.write_text(rendered)

    assert rendered == GOLDEN.read_text()


def test_spades_ir_is_well_formed() -> None:
    ir = compile_path(SPADES)
    assert ir["cardlang_ir"] == 1 and ir["kind"] == "game"
    phases = ir["phases"]
    rules = ir["rules"]
    assert isinstance(phases, list) and len(phases) == 1
    assert isinstance(rules, list) and len(rules) == 2
