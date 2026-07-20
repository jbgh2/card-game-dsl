"""The checker runs end-to-end on the raw `.cardlang` Hearts file and via the
CLI — parse -> resolve -> typecheck, dispatching on the file extension.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from cardlang.cli import main
from cardlang.diagnostics import DiagnosticError
from cardlang.pipeline import check_dsl, check_source

HEARTS = Path(__file__).parent.parent / "docs" / "games" / "hearts.cardlang"


def test_check_source_on_raw_cardlang() -> None:
    game = check_source(HEARTS)
    assert game.name == "Hearts"


def test_cli_checks_hearts_clean() -> None:
    assert main([str(HEARTS)]) == 0


def test_cli_reports_structural_error(tmp_path: Path) -> None:
    bad = tmp_path / "bad.cardlang"
    bad.write_text(
        "game B {\n"
        "  players: 2\n"
        "  max_length: 1000\n"
        "  cards: standard52\n"
        "  zones { hand[player] : Hand<player> }\n"
        "  phase p { active_rules: [Ghost] }\n"
        "}\n"
    )
    assert main([str(bad)]) == 1


def test_cli_missing_file() -> None:
    assert main(["/no/such/file.cardlang"]) == 2


# ---------------------------------------------------------------------------
# `_check` memoization. It composes with `parse_text`'s memo (cardlang/parse.py,
# Contract): same text -> same parsed tree -> same checked tree. Both halves
# get a probe, since a memo that never hits and a memo that swallows a
# rejection fail in opposite, equally silent ways.
# ---------------------------------------------------------------------------


def test_repeated_check_returns_the_identical_object() -> None:
    assert check_source(HEARTS) is check_source(HEARTS)


def test_a_rejected_game_is_re_checked_every_time() -> None:
    # The typecheck/resolve rejection corpus asserts on live diagnostics; a
    # memoized raise would replay a stale object instead. `lru_cache` stores
    # nothing on an exception — this pins that we rely on it.
    bad = (
        "game Ghosted {\n"
        "  players: 2\n"
        "  max_length: 1000\n"
        "  cards: standard52\n"
        "  zones { hand[player] : Hand<player> }\n"
        "  phase p { active_rules: [Ghost] }\n"
        "}\n"
    )
    with pytest.raises(DiagnosticError) as first:
        check_dsl(bad, "ghosted.cardlang")
    with pytest.raises(DiagnosticError) as second:
        check_dsl(bad, "ghosted.cardlang")
    assert first.value is not second.value
