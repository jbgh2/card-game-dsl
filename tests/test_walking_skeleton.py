"""End-to-end walking-skeleton test.

Proves the whole pipeline (extract -> parse -> resolve -> typecheck ->
emit IR) on a minimal synthetic game, and pins the IR with a golden file so
any semantic shift shows up as a reviewable diff. Regenerate the golden
deliberately with ``UPDATE_GOLDEN=1 pytest``.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from cardlang.diagnostics import DiagnosticError
from cardlang.pipeline import check_markdown, compile_markdown

FIXTURE = Path(__file__).parent / "fixtures" / "skeleton.md"
GOLDEN = Path(__file__).parent / "golden" / "skeleton.ir.json"


def test_full_pipeline_matches_golden_ir() -> None:
    ir = compile_markdown(FIXTURE.read_text(), str(FIXTURE))
    rendered = json.dumps(ir, indent=2) + "\n"

    if os.environ.get("UPDATE_GOLDEN"):
        GOLDEN.write_text(rendered)

    assert rendered == GOLDEN.read_text()


def test_unknown_zone_type_is_a_diagnostic() -> None:
    bad = """```
game Bad {
  players: 2
  max_length: 1000
  cards: standard52
  zones { x : Nonesuch }
}
```
"""
    with pytest.raises(DiagnosticError) as excinfo:
        check_markdown(bad, "bad.md")
    assert "unknown zone type 'Nonesuch'" in excinfo.value.diagnostic.message


def test_zero_players_is_a_diagnostic() -> None:
    bad = """```
game Bad {
  players: 0
  max_length: 1000
  cards: standard52
  zones { }
}
```
"""
    with pytest.raises(DiagnosticError) as excinfo:
        check_markdown(bad, "bad.md")
    assert "at least one player" in excinfo.value.diagnostic.message
