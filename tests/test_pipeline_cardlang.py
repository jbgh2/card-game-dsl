"""The checker runs end-to-end on the raw `.cardlang` Hearts file and via the
CLI — parse -> resolve -> typecheck, dispatching on the file extension.
"""

from __future__ import annotations

from pathlib import Path

from cardlang.cli import main
from cardlang.pipeline import check_source

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
        "  cards: standard52\n"
        "  zones { hand[player] : Hand<player> }\n"
        "  phase p { active_rules: [Ghost] }\n"
        "}\n"
    )
    assert main([str(bad)]) == 1


def test_cli_missing_file() -> None:
    assert main(["/no/such/file.cardlang"]) == 2
