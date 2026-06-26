"""French Tarot compiles all the way to a validated IR.

The full pipeline (parse -> resolve -> typecheck -> emit) on the real
french-tarot.cardlang, pinned with a golden file so any change to the IR shape —
in particular the four-level bid auction `round` on the counterclockwise
single-pass ring — is a reviewable diff. Regenerate with ``UPDATE_GOLDEN=1``.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from cardlang.pipeline import compile_path

TAROT = Path(__file__).parent.parent / "docs" / "games" / "french-tarot.cardlang"
GOLDEN = Path(__file__).parent / "golden" / "french-tarot.ir.json"


def test_french_tarot_ir_matches_golden() -> None:
    ir = compile_path(TAROT)
    rendered = json.dumps(ir, indent=2) + "\n"

    if os.environ.get("UPDATE_GOLDEN"):
        GOLDEN.write_text(rendered)

    assert rendered == GOLDEN.read_text()


def test_french_tarot_ir_is_well_formed() -> None:
    ir = compile_path(TAROT)
    assert ir["cardlang_ir"] == 1 and ir["kind"] == "game"
    assert isinstance(ir["phases"], list) and len(ir["phases"]) == 1
