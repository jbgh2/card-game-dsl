"""A parse failure, told in the language's own words.

A designer's first error is a syntax error: it arrives before resolve or
typecheck can say anything, and for a language whose acceptance test is "a
non-player reads the file cold" it is the worst place to answer in the parser
generator's vocabulary. This module grids the two halves of answering it in the
designer's [[vocabulary]] — that every terminal the grammar defines has a word a
designer could have written, and that each reachable parser failure renders into
a sentence carrying no engine noun.

Completeness ledger (decisions.md "Closed-domain completeness")
--------------------------------------------------------------
property:   a parse failure reaching a designer names only things they could
            have typed. Concretely, over every reachable failure kind and every
            parse entry point: the rendered diagnostic quotes the offending
            lexeme as it appears in the source, carries a source position that
            exists in the file, and contains no terminal name, no parser-theory
            noun, and no repetition of the position the span prefix already
            carries. Separately and by construction: every terminal in the
            grammar's own table renders to such a word, or the parser refuses to
            build.
domain:     three crossed axes, each derived from its own registry.
            (a) parser failure kind — `lark.exceptions.UnexpectedInput`'s
            subclass closure, which is the whole set the caught base admits;
            (b) parse entry point — the `start` symbols `cardlang/parse.py`
            itself passes, reusing `tests/test_parse.py`'s scrape rather than
            re-deriving them; (c) source brace balance, the three-valued
            property that decides which structural sentence a failure earns
            (balanced, a block left open, a surplus `}`).
            The terminal axis is `_parser().terminals` entire — every terminal
            Lark compiles from `cardlang/grammar/cardlang.lark`, including the
            anonymous ones it mints for inline literals in productions.
            Outside the domain, and deliberately: WHICH terminals the grammar
            offers at a given point. That is the grammar's business and this
            module asserts nothing about it — only that whatever set is offered
            renders into designer words.
registry:   failure kinds: `lark.exceptions.UnexpectedInput.__subclasses__()`,
            closed here by `_failure_kinds`. Entry points:
            `tests/test_parse.py::_parse_entry_points`, itself a scrape of
            `cardlang/parse.py`'s `parse_to_tree` call sites, and pinned there
            by `tests/test_parse.py::test_the_hint_start_axis_is_every_entry_point`.
            Terminals: `cardlang.parse._parser().terminals`. The rendering
            rules and the override table: `cardlang.parse._VOCABULARY_WORDS`
            and `cardlang.parse._vocabulary_word`. Message text for whole
            designer-visible diagnostics is pinned as artifacts in
            `tests/rejections/` (`tests/test_rejections.py`), which is where the
            `syntax_*` cases of this domain live; this module pins the
            properties those artifacts must share.
does not prove:  that a rendered word is the word a designer would CHOOSE. The
            grid proves each terminal has a rendering and that no rendering
            leaks an engine noun; whether "a rank name" beats "a card's rank"
            is a judgment no assertion here makes, and it is held instead by
            the rejection corpus's blessed artifacts, which a human reads on
            every change. Nor does a green here prove the grammar offers a
            SENSIBLE set at any point — an expectation clause listing three
            plausible continuations and an expectation clause listing three
            absurd ones are equally green.
"""

from __future__ import annotations

import re

import pytest
from lark.exceptions import (
    UnexpectedCharacters,
    UnexpectedEOF,
    UnexpectedInput,
    UnexpectedToken,
)

from cardlang import parse
from cardlang.diagnostics import DiagnosticError
from tests.test_parse import _parse_entry_points

# --------------------------------------------------------------------------
# Axis (a) — the parser failure kinds, from lark's own class closure.
# --------------------------------------------------------------------------


def _failure_kinds() -> tuple[type[UnexpectedInput], ...]:
    """Every `UnexpectedInput` subclass, derived from the class tree.

    Scraped rather than listed for the reason `test_keyword_anchoring.py`
    scrapes the terminal table: a listed axis is true by construction, so a
    kind lark adds arrives as an uncovered row instead of as a silence.
    """
    seen: dict[str, type[UnexpectedInput]] = {}

    def walk(cls: type[UnexpectedInput]) -> None:
        for sub in cls.__subclasses__():
            seen[sub.__name__] = sub
            walk(sub)

    walk(UnexpectedInput)
    return tuple(seen[name] for name in sorted(seen))


# The kinds this parser configuration can actually raise. `parser="earley"`
# with the dynamic lexer scans through `lark/parsers/xearley.py`, which raises
# `UnexpectedCharacters` where no terminal matches and `UnexpectedEOF` where
# input runs out; the `UnexpectedToken` site is in `earley.py`'s own scan loop,
# which xearley replaces. A designer cannot reach it, so it is a marked cell
# below rather than a covered one.
_REACHABLE = frozenset({UnexpectedCharacters, UnexpectedEOF})


def test_the_failure_kind_axis_is_larks_whole_hierarchy() -> None:
    """Anti-vacuity on the scrape: a `__subclasses__` walk that stopped
    finding subclasses would shrink the axis to nothing and every cell below
    would pass by not existing.

    red under: in `_failure_kinds`, return `()` — the three parametrized cells
    disappear and pytest reports no failure, which is what this asserts against.
    """
    names = {cls.__name__ for cls in _failure_kinds()}
    assert names == {
        "UnexpectedCharacters",
        "UnexpectedEOF",
        "UnexpectedToken",
    }, names
    assert _REACHABLE <= set(_failure_kinds())


# --------------------------------------------------------------------------
# Axis (b) — the parse entry points, reused from the hint grid's own scrape.
# --------------------------------------------------------------------------

_STARTS: tuple[str, ...] = _parse_entry_points()


# A source per (failure kind, start) that provokes exactly that kind under that
# entry point. `None` marks a cell the configuration cannot reach.
def _probe(kind: type[UnexpectedInput], start: str) -> str | None:
    if kind is UnexpectedToken:
        return None
    if kind is UnexpectedEOF:
        # Input that is a legal PREFIX and then stops.
        return {
            "start": "game G {\n  players: 2\n",
            "library": "library L {\n",
            "stdlib_rules": "rule R {\n",
        }[start]
    # A character no terminal admits at that point.
    return {
        "start": "game G {\n  players: 2 @\n}\n",
        "library": "library L {\n  @\n}\n",
        "stdlib_rules": "rule R {\n  @\n}\n",
    }[start]


# --------------------------------------------------------------------------
# The engine nouns a designer-facing sentence may never contain. Each is a word
# from the parser generator or from parsing theory that names nothing in
# `docs/` — a designer meeting one has no way to look it up.
# --------------------------------------------------------------------------

_ENGINE_NOUNS = (
    "terminal",
    "parser context",
    "nonterminal",
    "token",
    "lexer",
    "grammar rule",
    "Expected one of",
    "No terminal matches",
    "Unexpected end-of-input",
)


def _render(text: str, start: str = "start", line_offset: int = 0) -> DiagnosticError:
    with pytest.raises(DiagnosticError) as excinfo:
        parse.parse_to_tree(text, "probe.cardlang", line_offset, start=start)
    return excinfo.value


_KIND_CELLS = [
    pytest.param(
        kind,
        start,
        marks=(
            []
            if kind in _REACHABLE
            else [
                pytest.mark.xfail(
                    strict=True,
                    raises=AssertionError,
                    reason=(
                        "unreachable: `parser='earley'` scans through "
                        "lark/parsers/xearley.py, which raises only "
                        "UnexpectedCharacters and UnexpectedEOF; the "
                        "UnexpectedToken site is in earley.py's own scan loop, "
                        "which xearley replaces. The renderer handles it "
                        "because UnexpectedInput is the caught base, but no "
                        "designer input reaches it, so this cell claims no "
                        "coverage"
                    ),
                )
            ]
        ),
        id=f"{kind.__name__}-{start}",
    )
    for kind in _failure_kinds()
    for start in _STARTS
]


@pytest.mark.parametrize("kind,start", _KIND_CELLS)
def test_every_reachable_failure_kind_reads_as_the_language(
    kind: type[UnexpectedInput], start: str
) -> None:
    """failure kind x parse entry point, over both derived axes.

    Every cell asserts the four properties a designer-facing parse failure
    has, so a kind or an entry point that renders through a different path
    cannot pass by rendering differently.
    """
    source = _probe(kind, start)
    assert source is not None, (
        f"{kind.__name__} is not reachable under start={start!r}; this cell "
        "is marked, and reaching this line means the mark is stale"
    )
    exc = _render(source, start=start)
    diagnostic = exc.diagnostic
    message = diagnostic.message

    assert type(exc.__cause__) is kind, (
        f"probe for {kind.__name__} under start={start!r} raised "
        f"{type(exc.__cause__).__name__} instead"
    )
    assert message.startswith("syntax error: "), message
    for noun in _ENGINE_NOUNS:
        assert noun.lower() not in message.lower(), (
            f"{kind.__name__}/{start}: the message names {noun!r}, which is "
            f"the parser generator's word, not the language's: {message}"
        )
    assert diagnostic.span is not None
    assert diagnostic.span.line >= 1, (
        f"{kind.__name__}/{start}: span line {diagnostic.span.line} is not a "
        f"position in the file: {diagnostic.format()}"
    )
    assert diagnostic.span.column >= 1, (
        f"{kind.__name__}/{start}: span column {diagnostic.span.column} is not "
        f"a position in the file: {diagnostic.format()}"
    )
    assert not re.search(r"at line \d+ col \d+", message), (
        f"{kind.__name__}/{start}: the message repeats the position the span "
        f"prefix already carries: {diagnostic.format()}"
    )


# --------------------------------------------------------------------------
# Axis (c) — brace balance, the property that decides the structural sentence.
# --------------------------------------------------------------------------

_BALANCE_CELLS = {
    # balanced: no structural sentence, and the expectation clause stands.
    "balanced": (
        "game G {\n  players: 2\n  state { s : Integer : 0 }\n}\n",
        None,
    ),
    # a block left open: the sentence names the innermost block open AT THE
    # FAILURE POINT and the line it opened on -- not the innermost surviving to
    # end of text, which last-opened-first-closed matching leaves as the
    # OUTERMOST block and which points further from the mistake than the
    # failure line does.
    "unclosed": (
        "game G {\n  players: 2\n  zones {\n    deck : Deck\n"
        "  state { s : Integer = 0 }\n}\n",
        "`zones {` block opened on line 3",
    ),
    # a surplus `}`: which brace is surplus is not recoverable, so the sentence
    # states the count and names no line.
    "surplus": (
        "game G {\n  players: 2\n  zones { deck : Deck } }\n"
        "  state { s : Integer = 0 }\n}\n",
        "more `}` than `{`",
    ),
}


@pytest.mark.parametrize("balance", sorted(_BALANCE_CELLS))
def test_the_structural_sentence_matches_the_sources_brace_balance(
    balance: str,
) -> None:
    """The three-valued balance axis, each with the sentence it earns.

    A sentence that names a site REPLACES the expectation clause, because an
    expectation computed under a wrong bracket context invites exactly the
    wrong edit; a sentence that only characterises the file supplements it.
    """
    source, expected_fragment = _BALANCE_CELLS[balance]
    message = _render(source).diagnostic.message
    if expected_fragment is None:
        assert "never closed" not in message, message
        assert "more `}`" not in message, message
        assert "expected " in message, (
            f"a balanced source earns the expectation clause: {message}"
        )
    else:
        assert expected_fragment in message, (
            f"balance={balance}: expected {expected_fragment!r} in: {message}"
        )


def test_a_named_site_replaces_the_expectation_clause() -> None:
    """The composition rule, asserted where it bites.

    On the unclosed-block source the parser's own expectation is `:` or `[` --
    locally true, and an invitation to add a colon to an innocent line. The
    sentence that names the unclosed block stands in its place.
    """
    source, _ = _BALANCE_CELLS["unclosed"]
    message = _render(source).diagnostic.message
    assert "never closed" in message, message
    assert "expected " not in message, (
        "the unclosed-block sentence names the fix, so the expectation clause "
        f"it would otherwise carry is withheld: {message}"
    )


def test_a_surplus_brace_keeps_the_expectation_clause() -> None:
    """The other arm of the same rule: a sentence that names no site cannot
    stand in for the expectation, so both are carried."""
    source, _ = _BALANCE_CELLS["surplus"]
    message = _render(source).diagnostic.message
    assert "more `}` than `{`" in message, message
    assert "expected " in message, message


# --------------------------------------------------------------------------
# The offending lexeme, and the line numbers a Markdown snippet reports.
# --------------------------------------------------------------------------


def test_the_offending_lexeme_is_quoted_as_the_designer_wrote_it() -> None:
    """A word-shaped lexeme is quoted whole.

    The dynamic lexer reports the first CHARACTER it cannot place, so the raw
    failure names `m` where the designer wrote `maxlength`. A single letter is
    as opaque as a terminal name; the word is what they can find in their file.
    """
    message = _render("game G {\n  players: 2\n  maxlength: 10\n}\n").diagnostic.message
    assert "`maxlength`" in message, message


def test_a_non_word_lexeme_is_quoted_as_the_single_character() -> None:
    message = _render("game G {\n  players: 2 @\n}\n").diagnostic.message
    assert "`@`" in message, message


def test_end_of_input_is_named_rather_than_quoted() -> None:
    """There is no character at end of input, and lark reports line and column
    as -1 there -- an absence, not a position. The end of the text is the
    honest span."""
    text = "game G {\n  players: 2\n"
    diagnostic = _render(text).diagnostic
    assert "end of file" in diagnostic.message, diagnostic.message
    assert diagnostic.span is not None
    assert diagnostic.span.line == text.count("\n") + 1, diagnostic.format()


def test_a_line_number_in_the_sentence_is_the_file_s_own() -> None:
    """The probe indexes the DSL text; the sentence is read against the file
    the text came from. A Markdown game file's fenced block starts partway down
    it, so a line number that skipped `line_offset` would name a line in the
    prose above the block.

    No corpus snippet fails to parse, so `tests/test_doc_snippets.py` cannot
    reach this: the cell needs its own witness.
    """
    source = (
        "game G {\n  players: 2\n  zones {\n    deck : Deck\n"
        "  state { s : Integer = 0 }\n}\n"
    )
    at_top = _render(source).diagnostic
    offset = _render(source, line_offset=20).diagnostic
    assert "opened on line 3" in at_top.message, at_top.message
    assert "opened on line 23" in offset.message, offset.message
    assert offset.span is not None and at_top.span is not None
    assert offset.span.line == at_top.span.line + 20


# --------------------------------------------------------------------------
# A large expected set is summarized, never printed raw.
# --------------------------------------------------------------------------


def test_a_large_expected_set_is_summarized() -> None:
    """Every game clause is legal after `players: 2`, which is far more than a
    designer can read. The clause names the closest few and says so."""
    message = _render("game G {\n  players: 2\n  maxlength: 10\n}\n").diagnostic.message
    assert "among others" in message, message
    assert "`max_length`" in message, (
        f"the closest spelling to what was typed leads the list: {message}"
    )
    assert message.count("`") <= 12, (
        f"a summarized clause names a few words, not the whole set: {message}"
    )


def test_a_small_expected_set_is_named_in_full() -> None:
    message = _render(
        "game G {\n  players: 2\n  state { s : Integer : 0 }\n}\n"
    ).diagnostic.message
    assert "among others" not in message, message
    assert "`=`" in message, message


# --------------------------------------------------------------------------
# The terminal axis — every terminal the grammar defines has a designer word.
# --------------------------------------------------------------------------

_TERMINALS = sorted(parse._parser().terminals, key=lambda t: t.name)


def test_the_terminal_axis_is_the_whole_compiled_table() -> None:
    """Anti-vacuity: an empty or truncated table would make the per-terminal
    cells below pass by not existing.

    red under: slice `_TERMINALS` to `[:0]` -- the parametrized rows vanish and
    this assertion is what notices.
    """
    names = {t.name for t in _TERMINALS}
    assert len(names) == len(_TERMINALS) > 100, len(_TERMINALS)
    # Both halves of the table: the terminals the grammar names, and the
    # anonymous ones Lark mints for inline literals in productions.
    assert any(n.startswith("__ANON") for n in names), names
    assert any(n.endswith("_KW") for n in names), sorted(names)[:10]


@pytest.mark.parametrize("name", [t.name for t in _TERMINALS])
def test_every_terminal_has_a_designer_word(name: str) -> None:
    """The closed-domain pin, over the grammar's own compiled terminal table.

    A terminal with no rendering is the only way an engine noun could reach a
    designer, so the domain is the table entire rather than the terminals the
    renderer happens to have met.
    """
    word = parse._vocabulary_word(name)
    assert word, f"terminal {name} renders to nothing a designer could type"
    assert name not in word, (
        f"terminal {name} renders to its own grammar name: {word!r}"
    )
    assert not re.search(r"\b[A-Z][A-Z0-9_]{2,}\b", word), (
        f"terminal {name} renders to something shaped like a terminal name: "
        f"{word!r}"
    )


def test_the_parser_refuses_a_terminal_it_cannot_render() -> None:
    """The runtime half of the closed-domain pin (decisions.md
    "Closed-domain completeness" asks for a static test AND a runtime
    refusal). Validation runs where the parser is BUILT, not where a
    diagnostic is rendered: a check reached only by an error path can go
    unrun for years, while every parse crosses this one.

    The Author of this failure is the engine maintainer who edited the
    grammar, never a designer -- so a raise is the right channel for it,
    where a raise inside a designer's syntax error would not be.

    red under: this cell IS the red-under -- it plants an unrenderable
    terminal and asserts the refusal fires and names it.
    """
    with pytest.raises(parse.UnrenderableTerminal) as excinfo:
        parse._check_every_terminal_renders(
            [*_TERMINALS, _FakeTerminal("A_TERMINAL_WITH_NO_WORD")]
        )
    assert "A_TERMINAL_WITH_NO_WORD" in str(excinfo.value)


class _FakeTerminal:
    """A terminal-shaped stand-in whose pattern matches no rendering rule."""

    def __init__(self, name: str) -> None:
        self.name = name
        self.pattern = _FakePattern()


class _FakePattern:
    value = "(?#no rule renders this)"
