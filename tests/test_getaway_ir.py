"""Golden IR for the formalized Getaway, pinning the IR shape (the second corpus
game through the toolchain). Regenerate deliberately with ``UPDATE_GOLDEN=1``."""

from __future__ import annotations

import os
from pathlib import Path

from cardlang.ir import to_json
from cardlang.pipeline import check_source

GETAWAY = Path(__file__).parent.parent / "docs" / "games" / "getaway.cardlang"
GOLDEN = Path(__file__).parent / "golden" / "getaway.ir.json"


def test_getaway_ir_matches_golden() -> None:
    rendered = to_json(check_source(GETAWAY))
    if os.environ.get("UPDATE_GOLDEN"):
        GOLDEN.write_text(rendered)
    assert rendered == GOLDEN.read_text()
