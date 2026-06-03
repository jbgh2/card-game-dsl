"""Tests for the Markdown fenced-block extractor.

The extractor is the only stage that knows games live inside Markdown. It
must preserve the 1-based line where each block's content starts, so spans
reported by later stages point at the real game file.
"""

from __future__ import annotations

import pytest

from cardlang.diagnostics import DiagnosticError
from cardlang.extract import FencedBlock, extract_blocks, extract_single_block

HEARTS_LIKE = """# Hearts

Some prose describing the game.

```
game Hearts {
  players: 4
}
```
"""

TWO_BLOCKS = """# Title

```
game A {}
```

middle prose

```
rule R {}
```
"""

INFO_STRING = """intro

```dsl
game B {}
```
"""


def test_single_block_text_and_start_line() -> None:
    block = extract_single_block(HEARTS_LIKE, "hearts.md")
    assert isinstance(block, FencedBlock)
    assert block.source_name == "hearts.md"
    assert block.text == "game Hearts {\n  players: 4\n}\n"
    # The opening fence is line 5; content begins on line 6.
    assert block.start_line == 6


def test_multiple_blocks_are_separated_with_line_offsets() -> None:
    blocks = extract_blocks(TWO_BLOCKS, "two.md")
    assert len(blocks) == 2
    assert blocks[0].text == "game A {}\n"
    assert blocks[0].start_line == 4
    assert blocks[1].text == "rule R {}\n"
    assert blocks[1].start_line == 10


def test_info_string_on_opening_fence_is_not_content() -> None:
    block = extract_single_block(INFO_STRING, "b.md")
    assert block.text == "game B {}\n"
    assert block.start_line == 4


def test_no_fenced_block_is_an_error_for_single() -> None:
    with pytest.raises(DiagnosticError):
        extract_single_block("# Just prose, no code.\n", "empty.md")


def test_multiple_blocks_is_an_error_for_single() -> None:
    with pytest.raises(DiagnosticError):
        extract_single_block(TWO_BLOCKS, "two.md")


def test_empty_markdown_yields_no_blocks() -> None:
    assert extract_blocks("", "x.md") == []
