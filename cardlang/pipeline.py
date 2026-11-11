"""The front-end pipeline, wired end to end.

A single place that chains the stages so the CLI, the corpus harness, and
tests all run the exact same path:

    (extract) -> parse -> resolve -> typecheck -> expand -> deck-capacity (-> emit IR)

`expand` [[splice]]s every procedure body into its `run` sites. It sits after
typecheck because a procedure's parameter types can only be enforced while the
call site still exists (cardlang/expand.py), and before deck-capacity because
every stage downstream of it — capacity, IR, runtime, OpenSpiel — is entitled to
assume a procedure-free tree.

Game files come in the shapes `GAME_FILE_SHAPES` names, each by its
extension: raw DSL (`.cardlang`) and Markdown (`.md`, DSL inside a fenced
block). The extract step applies only to Markdown. `check_source` is the Owner
Guard for a game file's name: a file with any other extension is refused, its
Near Misses among the extensions offered, before its text is read.

Each stage raises :class:`~cardlang.diagnostics.DiagnosticError` on failure;
callers decide how to render it.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from functools import cache
from pathlib import Path

from cardlang.ast.nodes import Game
from cardlang.deckcheck import check_capacity
from cardlang.diagnostics import DiagnosticBag, DiagnosticError
from cardlang.expand import expand
from cardlang.extract import extract_single_block
from cardlang.ir import IRValue, emit
from cardlang.parse import parse_block, parse_text
from cardlang.resolve import resolve
from cardlang.typecheck import typecheck


@cache
def _check(game: Game) -> Game:
    """Run the post-parse stages (resolve -> typecheck -> expand -> deck capacity).

    Memoized on the parsed tree, which composes with `parse_text`'s own memo:
    the same source text yields the same `Game` object, so a repeat check is a
    dict lookup. Sound for the same reason the parse memo is — the AST is
    frozen and each stage rebinds a new tree (cardlang/parse.py, Contract) —
    and hashing a `Game` costs two orders of magnitude less than re-running
    the stages. Note this deliberately does NOT make the stages idempotent:
    `resolve` still may not be applied to its own output (metamorphic-suite.md),
    and the memo never does so, since it is keyed on the PRE-check tree."""
    game = resolve(game)
    game = typecheck(game)
    game = expand(game)
    game = check_capacity(game)
    return game


def check_dsl(text: str, source_name: str) -> Game:
    """Check raw DSL text (a `.cardlang` source): parse -> resolve -> typecheck."""
    return _check(parse_text(text, source_name))


def check_markdown(markdown: str, source_name: str) -> Game:
    """Check a Markdown game file: extract -> parse -> resolve -> typecheck."""
    block = extract_single_block(markdown, source_name)
    return _check(parse_block(block))


# The game file shapes the checker reads, keyed by the extension that names
# each, with the words that describe the shape to a designer.
GAME_FILE_SHAPES: dict[str, tuple[str, Callable[[str, str], Game]]] = {
    ".cardlang": ("the DSL itself", check_dsl),
    ".md": ("Markdown with the DSL in one fenced block", check_markdown),
}


def extensions_read() -> str:
    """The extensions `check_source` reads, each with its shape, as a designer
    reads them."""
    named = [f"{ext} ({words})" for ext, (words, _check) in GAME_FILE_SHAPES.items()]
    return ", ".join(named[:-1]) + " or " + named[-1]


def check_source(path: str | Path) -> Game:
    """Check a game file on disk, dispatching on its extension.

    The extension is compared as typed, on every platform, as every glob that
    collects game files compares it; the refusal names the file rather than a
    place in its text."""
    p = Path(path)
    shape = GAME_FILE_SHAPES.get(p.suffix)
    if shape is None:
        named = f"{p} ends in {p.suffix}" if p.suffix else f"{p} has no extension"
        bag = DiagnosticBag()
        bag.unknown(
            f"{named}, and a game file's name ends in {extensions_read()}",
            p.suffix,
            GAME_FILE_SHAPES,
        )
        raise DiagnosticError(bag.items[0])
    _words, check = shape
    return check(p.read_text(), str(p))


def compile_markdown(markdown: str, source_name: str) -> dict[str, IRValue]:
    """Run the full pipeline through to the validated IR (Markdown source)."""
    return emit(check_markdown(markdown, source_name))


def compile_path(path: str | Path) -> dict[str, IRValue]:
    """Compile a game file on disk to its IR."""
    return emit(check_source(path))


def game_identity(game: Game) -> str:
    """Which game a checked game is, for a file replayed against one.

    A digest of the game's IR: the checked program, with every definition a
    `uses` library splices in, and none of the file's layout, comments or path.
    So a copy reformatted or moved keeps its identity, and an edit that reaches
    the program moves it, a library's included — which the bytes of the game's
    own file could not show. A saved session carries it and is refused against
    a game whose identity differs."""
    text = json.dumps(emit(game), sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()
