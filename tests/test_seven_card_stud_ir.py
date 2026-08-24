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
    ir = compile_path(STUD)
    assert ir["cardlang_ir"] == 1 and ir["kind"] == "game"
    # check / bet / call / raise / fold are game-defined betting move types.
    move_types = ir["move_types"]
    assert isinstance(move_types, list)
    names = {m["name"] for m in move_types if isinstance(m, dict)}
    assert {"check", "bet", "call", "raise", "fold"} <= names
    # The betting rounds are the betting form: the default ring traversal, so the
    # emitted mode is null, and no outcome function. Pinned affirmatively AND by
    # the absence of any spelled mode — a pin that only said what the IR is not
    # would stay green on an IR that had lost the key altogether.
    blob = json.dumps(ir)
    assert '"order_mode": null' in blob
    assert '"order_mode": "' not in blob
    assert '"outcome_fn": null' in blob
