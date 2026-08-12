"""Hearts compiles all the way to a validated IR.

The full pipeline (parse -> resolve -> typecheck -> emit) on the real
hearts.cardlang, pinned with a golden file so any change to the IR shape is a
reviewable diff. Regenerate deliberately with ``UPDATE_GOLDEN=1 pytest``.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from cardlang.pipeline import compile_path

HEARTS = Path(__file__).parent.parent / "docs" / "games" / "hearts.cardlang"
GOLDEN = Path(__file__).parent / "golden" / "hearts.ir.json"


def test_hearts_ir_matches_golden() -> None:
    ir = compile_path(HEARTS)
    rendered = json.dumps(ir, indent=2) + "\n"

    if os.environ.get("UPDATE_GOLDEN"):
        GOLDEN.write_text(rendered)

    assert rendered == GOLDEN.read_text()


def test_hearts_ir_is_well_formed() -> None:
    ir = compile_path(HEARTS)
    assert ir["cardlang_ir"] == 1 and ir["kind"] == "game"
    phases = ir["phases"]
    rules = ir["rules"]
    assert isinstance(phases, list) and len(phases) == 1
    # Four: Hearts' two own rules plus the two library rules resolve
    # splices in. `PassExactlyThreeCards` was a fifth until its
    # `demands: actions where` form was guarded as unenforceable
    # (tests/test_rule_surface_reachability.py) — the pass movement's
    # `chosen 3` is what binds that count.
    assert isinstance(rules, list) and len(rules) == 4
