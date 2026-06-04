"""The front-end pipeline, wired end to end.

A single place that chains the stages so the CLI, the corpus harness, and
tests all run the exact same path:

    (extract) -> parse -> resolve -> typecheck (-> emit IR)

Game files come in two shapes: Markdown (`.md`, DSL inside a fenced block) and
raw DSL (`.cardlang`). The extract step applies only to Markdown.

Each stage raises :class:`~cardlang.diagnostics.DiagnosticError` on failure;
callers decide how to render it.
"""

from __future__ import annotations

from pathlib import Path

from cardlang.ast.nodes import Game
from cardlang.extract import extract_single_block
from cardlang.ir import IRValue, emit
from cardlang.parse import parse_block, parse_text
from cardlang.resolve import resolve
from cardlang.typecheck import typecheck


def _check(game: Game) -> Game:
    """Run the post-parse check stages (resolve -> typecheck)."""
    game = resolve(game)
    game = typecheck(game)
    return game


def check_dsl(text: str, source_name: str) -> Game:
    """Check raw DSL text (a `.cardlang` source): parse -> resolve -> typecheck."""
    return _check(parse_text(text, source_name))


def check_markdown(markdown: str, source_name: str) -> Game:
    """Check a Markdown game file: extract -> parse -> resolve -> typecheck."""
    block = extract_single_block(markdown, source_name)
    return _check(parse_block(block))


def check_source(path: str | Path) -> Game:
    """Check a game file on disk, dispatching on its extension."""
    p = Path(path)
    text = p.read_text()
    if p.suffix == ".cardlang":
        return check_dsl(text, str(p))
    return check_markdown(text, str(p))


def compile_markdown(markdown: str, source_name: str) -> dict[str, IRValue]:
    """Run the full pipeline through to the validated IR (Markdown source)."""
    return emit(check_markdown(markdown, source_name))


def compile_path(path: str | Path) -> dict[str, IRValue]:
    """Compile a game file on disk to its IR."""
    return emit(check_source(path))
