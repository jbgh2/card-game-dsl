"""The front-end pipeline, wired end to end.

A single place that chains the stages so the CLI, the corpus harness, and
tests all run the exact same path:

    extract -> parse -> resolve -> typecheck -> emit IR

Each stage raises :class:`~cardlang.diagnostics.DiagnosticError` on failure;
callers decide how to render it.
"""

from __future__ import annotations

from pathlib import Path

from cardlang.ast.nodes import Game
from cardlang.extract import extract_single_block
from cardlang.ir import IRValue, emit
from cardlang.parse import parse_block
from cardlang.resolve import resolve
from cardlang.typecheck import typecheck


def check_markdown(markdown: str, source_name: str) -> Game:
    """Run extract -> parse -> resolve -> typecheck, returning the checked AST."""
    block = extract_single_block(markdown, source_name)
    game = parse_block(block)
    game = resolve(game)
    game = typecheck(game)
    return game


def compile_markdown(markdown: str, source_name: str) -> dict[str, IRValue]:
    """Run the full pipeline through to the validated IR."""
    return emit(check_markdown(markdown, source_name))


def compile_path(path: str | Path) -> dict[str, IRValue]:
    """Compile a game file on disk to its IR."""
    p = Path(path)
    return compile_markdown(p.read_text(), str(p))
