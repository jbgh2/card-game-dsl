"""The poker library as a guard probe loads it.

A betting street opens and closes itself (`betting_street`), so no game can
hold the library's sizes at an arbitrary mid-street state, and none should.
The grids that measure the library's move guards need exactly that state,
so this probe loads the real library text with one probe-only procedure
appended, `probe_open_street`, which takes the street's sizes and clears its
bookkeeping, and nothing else. It changes the instrument, never the library
or a game: the moves, the predicates and `betting_street` are the file's own.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from unittest import mock

from cardlang import pipeline
from cardlang.ast import nodes as n
from cardlang.libraries import load_library
from cardlang.parse import parse_library

_LIBRARY = Path(__file__).resolve().parent.parent / "docs" / "libraries" / "poker_betting.cardlang"

_OPENER = """
  procedure probe_open_street(bet_size : Integer, big_size : Integer) {
    bet_to_match := 0
    raises := 0
    limit := bet_size
    big_limit := big_size
    floor := bet_size
    level := 0
    for each player p: bet_by[p] := 0
    for each player p: acted[p] := false
  }
"""


def probe_library_text() -> str:
    """The library file with the probe's opener before its closing brace."""
    text = _LIBRARY.read_text()
    head, brace, tail = text.rpartition("}")
    assert brace and not tail.strip(), "poker_betting.cardlang no longer ends with its library's brace"
    return head + _OPENER + brace + tail


@contextmanager
def probe_betting() -> Iterator[None]:
    """Resolve `uses poker_betting` to the probe library while the block runs.
    The checker memoizes on the game's tree, which names the probe opener, so
    no verdict crosses between the real library and the probe."""
    library = parse_library(probe_library_text(), str(_LIBRARY))

    def load(name: str) -> n.Library:
        return library if name == "poker_betting" else load_library(name)

    with mock.patch("cardlang.resolve.load_library", load):
        pipeline._check.cache_clear()
        try:
            yield
        finally:
            pipeline._check.cache_clear()
