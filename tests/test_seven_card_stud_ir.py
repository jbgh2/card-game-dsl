"""Seven-Card Stud compiles all the way to a validated IR.

The full pipeline (parse -> resolve -> typecheck -> emit) on the real
seven-card-stud.cardlang, pinned with a golden file so any change to the IR shape
— in particular the betting `round`s over the non-folded ring — is a reviewable
diff. Regenerate deliberately with ``UPDATE_GOLDEN=1 pytest``.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from cardlang.pipeline import compile_path

STUD = Path(__file__).parent.parent / "docs" / "games" / "seven-card-stud.cardlang"
GOLDEN = Path(__file__).parent / "golden" / "seven-card-stud.ir.json"


def test_seven_card_stud_ir_matches_golden() -> None:
    ir = compile_path(STUD)
    rendered = json.dumps(ir, indent=2) + "\n"

    if os.environ.get("UPDATE_GOLDEN"):
        GOLDEN.write_text(rendered)

    assert rendered == GOLDEN.read_text()


def test_seven_card_stud_ir_is_well_formed() -> None:
    """red under: write one of the five streets inline in seven-card-stud.cardlang
    — four spliced rings, not five."""
    ir = compile_path(STUD)
    assert ir["cardlang_ir"] == 1 and ir["kind"] == "game"
    # check / bet / call / raise / fold are game-defined betting move types.
    move_types = ir["move_types"]
    assert isinstance(move_types, list)
    names = {m["name"] for m in move_types if isinstance(m, dict)}
    assert {"check", "bet", "call", "raise", "fold"} <= names
    # The five streets are the library's `betting_street`, spliced at each
    # `run`: five `turns` rings, each offering the family's vocabulary.
    blob = json.dumps(ir)
    assert "auction_round" not in blob
    assert blob.count('"kind": "turns"') == 5
