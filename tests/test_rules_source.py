"""Every corpus game's rulebook names the written rules the game is held to.

A rulebook twin (docs/maintaining.md, "The rulebook twin") opens with its
Rules Source line, spelled one way:

    **Rules source:** <https://...>

The URL is a document holding a written copy of the rules, and it names the
version of the game the `.cardlang` beside it is held to, so a divergence is a
defect against that document rather than against the game's name. Prose
qualifying the source (which variant on the page, what is excluded) may
follow the closing bracket.

Completeness ledger:

- property: the rulebook twin of every `docs/games/*.cardlang` carries
  exactly one Rules Source line, in its opening (before its first `## `
  heading), and no other spelling of the label anywhere in the file.
- domain: the corpus, the `docs/games/*.cardlang` glob the adapter registry
  derives from (`cardlang/openspiel/registry.py`), so a new game joins on
  arrival and reddens here until its rulebook names its source.
- held by: a Pin, this module. A rulebook is prose, and no type holds it.
- reddening mutation: delete a rulebook's line, or respell it
  `**Rules source:** [Pagat](...)`; its cell fails naming the file.
- does not prove: that the URL resolves, that the page holds the variant the
  rulebook's header names, or that the `.cardlang` plays those rules. Whether
  a game has been read against its source is epic #469's checklist, not this
  pin. ADR-0023 records the ruling.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

GAMES = Path(__file__).parent.parent / "docs" / "games"
CORPUS = sorted(GAMES.glob("*.cardlang"))

_SECTION = "docs/maintaining.md, \"The rulebook twin\""
_LINE = re.compile(r"\*\*Rules source:\*\*\s+<(?P<url>https?://[^\s<>]+)>")
_ANY_LABEL = re.compile(r"rules?\s+sources?", re.IGNORECASE)


class RulesSourceRefusal(Exception):
    """A rulebook whose Rules Source line is missing or misspelled."""


def read_rules_source(text: str) -> str:
    """The URL a rulebook's Rules Source line names; refuses any other shape."""
    lines = list(_LINE.finditer(text))
    if len(lines) > 1:
        raise RulesSourceRefusal(
            "names more than one rules source: keep one `**Rules source:** <URL>` "
            "line, the written rules this game plays, and describe any other "
            f"reference in prose ({_SECTION})"
        )
    canonical = lines[0].span() if lines else None
    for label in _ANY_LABEL.finditer(text):
        if canonical is None or not (canonical[0] <= label.start() < canonical[1]):
            raise RulesSourceRefusal(
                f"spells the rules source as {label.group(0)!r} on line "
                f"{text.count(chr(10), 0, label.start()) + 1}: write it "
                "`**Rules source:** <https://...>`, "
                f"the URL in angle brackets ({_SECTION})"
            )
    if canonical is None:
        raise RulesSourceRefusal(
            "names no rules source: add `**Rules source:** <https://...>` to its "
            f"opening, a URL holding a written copy of the rules it plays ({_SECTION})"
        )
    heading = re.search(r"^## ", text, re.MULTILINE)
    if heading is not None and heading.start() < canonical[0]:
        raise RulesSourceRefusal(
            "names its rules source after its first `## ` heading: move the "
            f"`**Rules source:**` line into the rulebook's opening ({_SECTION})"
        )
    return lines[0].group("url")


@pytest.mark.parametrize("game", CORPUS, ids=lambda p: p.stem)
def test_every_rulebook_names_its_rules_source(game: Path) -> None:
    rulebook = game.with_suffix(".md")
    if not rulebook.exists():
        pytest.fail(f"{game.name} has no rulebook: write docs/games/{rulebook.name} ({_SECTION})")
    try:
        read_rules_source(rulebook.read_text())
    except RulesSourceRefusal as refusal:
        pytest.fail(f"docs/games/{rulebook.name} {refusal}")


_OPENING = "# Game\n\nThe companion formal file is [g.cardlang](g.cardlang). "


@pytest.mark.parametrize(
    ("text", "url"),
    [
        (_OPENING + "**Rules source:** <https://example.org/g.html>.\n", "https://example.org/g.html"),
        (
            _OPENING + "**Rules source:**\n<https://en.wikipedia.org/wiki/Hex_(board_game)>, the\nmain account.\n",
            "https://en.wikipedia.org/wiki/Hex_(board_game)",
        ),
        (_OPENING + "**Rules source:** <http://example.org/g>\n\n## Play\n", "http://example.org/g"),
    ],
    ids=["one-line", "wrapped-with-qualifier", "http"],
)
def test_the_line_reads(text: str, url: str) -> None:
    assert read_rules_source(text) == url


@pytest.mark.parametrize(
    ("text", "refusal"),
    [
        (_OPENING + "Source: [Pagat](https://example.org/g.html).\n", "names no rules source"),
        (_OPENING + "**Rules source:** Pagat.\n", "spells the rules source"),
        (_OPENING + "**Rules source:** [Pagat](https://example.org/g.html).\n", "spells the rules source"),
        (_OPENING + "**Rules source:** https://example.org/g.html (fetched live).\n", "spells the rules source"),
        (_OPENING + "Rules source: <https://example.org/g.html>.\n", "spells the rules source"),
        (_OPENING + "**Rules source.** <https://example.org/g.html>.\n", "spells the rules source"),
        (_OPENING + "Rules sources, read today:\n\n- <https://example.org/g.html>\n", "spells the rules source"),
        (
            _OPENING + "\n\n## Play\n\n**Rules source:** <https://example.org/g.html>.\n",
            "after its first `## ` heading",
        ),
        (
            _OPENING
            + "**Rules source:** <https://example.org/a.html>.\n"
            + "**Rules source:** <https://example.org/b.html>.\n",
            "more than one rules source",
        ),
    ],
    ids=[
        "source-without-label",
        "label-without-url",
        "markdown-link",
        "bare-url",
        "unbolded-label",
        "period-label",
        "plural-label",
        "after-heading",
        "two-lines",
    ],
)
def test_a_misspelled_line_is_refused(text: str, refusal: str) -> None:
    with pytest.raises(RulesSourceRefusal, match=re.escape(refusal)):
        read_rules_source(text)
