"""Pull DSL out of Markdown fenced code [[block]]s.

A Markdown game file is prose plus one or more fenced code blocks holding
the DSL. This is the only stage that knows about
Markdown; everything downstream consumes a :class:`FencedBlock`. Each block
records the 1-based line where its content starts so later stages can map
spans back to the real file.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from cardlang.diagnostics import Diagnostic, DiagnosticError, Severity, Span

# A fence is a line whose first non-whitespace content is a run of three or
# more backticks. The opening fence may carry an info string (e.g. ```dsl);
# the closing fence is bare. This is the CommonMark-ish subset the corpus uses.
_FENCE = re.compile(r"^(\s*)(`{3,})(.*)$")


@dataclass(frozen=True, slots=True)
class FencedBlock:
    """One fenced code block, with its origin line preserved."""

    source_name: str
    text: str
    start_line: int  # 1-based line of the first content line inside the fence
    info: str = ""  # the opening fence's info string, stripped (e.g. "cardlang")


def extract_blocks(markdown: str, source_name: str) -> list[FencedBlock]:
    """Return every fenced code block in ``markdown``, in document order."""
    blocks: list[FencedBlock] = []
    lines = markdown.split("\n")

    open_fence: str | None = None  # the backtick run that opened the current block
    content_start: int = 0  # 1-based line of the first content line
    buffer: list[str] = []
    info = ""

    for i, line in enumerate(lines, start=1):
        match = _FENCE.match(line)
        if open_fence is None:
            if match is not None:
                open_fence = match.group(2)
                info = match.group(3).strip()
                content_start = i + 1
                buffer = []
            continue

        # Inside a block: a fence with at least as many backticks closes it.
        if match is not None and len(match.group(2)) >= len(open_fence):
            blocks.append(
                FencedBlock(
                    source_name=source_name,
                    text="\n".join(buffer) + ("\n" if buffer else ""),
                    start_line=content_start,
                    info=info,
                )
            )
            open_fence = None
        else:
            buffer.append(line)

    return blocks


def extract_single_block(markdown: str, source_name: str) -> FencedBlock:
    """Return the one fenced block, erroring if there is not exactly one.

    A game file is a single DSL unit; multiple or missing blocks are a
    structural problem the caller should surface loudly rather than guess at.
    """
    blocks = extract_blocks(markdown, source_name)
    if len(blocks) == 1:
        return blocks[0]

    span = Span(source_name, 0, 0, 1, 1)
    if not blocks:
        message = "no fenced code block found; a game file must contain its DSL in one block"
    else:
        message = (
            f"expected exactly one fenced code block, found {len(blocks)}; "
            "a game file's DSL must live in a single block"
        )
    raise DiagnosticError(Diagnostic(Severity.ERROR, message, span))
