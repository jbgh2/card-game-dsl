"""A parse failure, told in the language's own words.

A designer's first error is a syntax error: it arrives before resolve or
typecheck can say anything, and for a language whose acceptance test is "a
non-player reads the file cold" it is the worst place to answer in the parser
generator's vocabulary. This module grids answering it in the designer's
[[vocabulary]]: that every terminal the grammar defines has a word a designer
could have written, that each reachable parser failure renders into a sentence
carrying no engine noun, and that what the sentence says about the file around
the failure — which block is open, what it is called, where it opened — is read
from the source's own lexemes rather than from its characters, so a brace
inside a comment or a text value is not structure.

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
domain:     five axes. Two are crossed with each other and three stand alone,
            because only the first two interact: the structural sentence, the
            block's name and the lexeme rendering are read from the token
            stream, not from the failure kind.
            (a) parser failure kind — `lark.exceptions.UnexpectedInput`'s
            subclass closure, which is the whole set the caught base admits;
            (b) parse entry point — the `start` symbols `cardlang/parse.py`
            itself passes, reusing `tests/test_parse.py`'s scrape rather than
            re-deriving them; (a) x (b) is crossed.
            (c) the structural verdict, `cardlang.parse._StructuralVerdict` —
            the closed set of things a failure's surroundings can honestly
            say about it, which decides both the sentence and whether the
            expectation clause survives beside it.
            (d) the character class of the offending lexeme — word-shaped,
            printable ASCII, a run of word characters no single lexeme can
            end inside, and the classes that arrive by paste rather than
            by typing (a byte-order mark, a non-breaking space, a smart quote,
            a non-Latin letter), which are invisible or confusable in an editor
            and so are named as well as quoted.
            (e) where a block's own keyword sits relative to its `{` — against
            it, behind a header, on the line above, sharing a line with an
            enclosing opener, spelt inside a string or a comment, nested,
            absent from the header entirely, or separated from the `{` by a
            group that has already closed.
            The terminal axis is `_parser().terminals` entire — every terminal
            Lark compiles from `cardlang/grammar/cardlang.lark`, including the
            anonymous ones it mints for inline literals in productions.
            Outside the domain, and deliberately: WHICH terminals the grammar
            offers at a given point. That is the grammar's business and this
            module asserts nothing about it — only that whatever set is offered
            renders into designer words.
            The domain covers the RENDERING of a parse failure under all three
            entry points; WHO each entry point's sentence is addressed to is a
            separate property, and holds for two of them. A game file and a
            family library are both written by the reader the sentence
            instructs. `cardlang/stdlib/rules.cardlang` ships inside the engine
            and is parsed during resolve, so its reader is told to close a
            brace in a file that is not theirs; routing that entry point to the
            installation channel is issue #604.
registry:   failure kinds: `lark.exceptions.UnexpectedInput.__subclasses__()`,
            closed here by `_failure_kinds`. Entry points:
            `tests/test_parse.py::_parse_entry_points`, itself a scrape of
            `cardlang/parse.py`'s `parse_to_tree` call sites, and pinned there
            by `tests/test_parse.py::test_the_hint_start_axis_is_every_entry_point`.
            Structural verdicts: `cardlang.parse._StructuralVerdict`, read
            through `typing.get_args`. Block-opener words:
            `cardlang.parse._block_opener_words`, the first symbol of every
            rule in `_parser().rules` whose expansion carries the `{`
            terminal, spoken through `_designer_word` — so a block construct
            added to the grammar names itself with nothing to keep in sync.
            Terminals: `cardlang.parse._parser().terminals`. The rendering
            rules and the override table: `cardlang.parse._WORD_OVERRIDES`
            and `cardlang.parse._designer_word`. Message text for whole
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
            Nor that a block's rendered name is its construct's own keyword in
            EVERY source. The name is read from the tokens between the `{` and
            the enclosing brace, so a header that spells no block keyword — a
            `produces` arm — is named by its own first word, which is what a
            designer reads on that line; a header spelling one inside a
            subexpression (`if ... card_points(card) ... {`) is named by the
            keyword its line begins with. Measured over `docs/games/*.cardlang`
            on 2026-09-06: every `{` in the corpus named by its own
            construct's keyword, bar the `produces` arms named by their arm's
            name.
            Nor that the lexer these positions come from is the one the parse
            ran under. It is not, and cannot be: this grammar disambiguates
            its identifier-shaped terminals BY POSITION, so a context-free
            lexer types them wrongly — pinned by
            `tests/test_keyword_anchoring.py::test_basic_lexer_cannot_tokenize_the_grammar`.
            What the locator reads is therefore only what a context-free scan
            settles: each token's offset and text, and the two brace terminals,
            which no other terminal can match. A cell asserting a token's
            KIND would be asserting something false.
"""

from __future__ import annotations

import re
from typing import get_args

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
# Axis (c) — the structural verdict, the property that decides what a
# failure's surroundings are allowed to say about it.
# --------------------------------------------------------------------------

_VERDICTS: tuple[str, ...] = tuple(str(v) for v in get_args(parse._StructuralVerdict))

#: verdict -> (source, the fragment its sentence carries or None for silence,
#: whether the expectation clause survives beside it). A verdict whose sentence
#: names a SITE replaces the expectation, because an expectation computed under
#: a bracket context the mistake already broke invites exactly the wrong edit;
#: one that only characterises the file supplements it.
_VERDICT_SOURCES: dict[str, tuple[str, str | None, bool]] = {
    # Nothing is open at the end: no structural sentence, expectation stands.
    "balanced": (
        "game G {\n  players: 2\n  state { s : Integer : 0 }\n}\n",
        None,
        True,
    ),
    # A block open AT THE FAILURE POINT survives to the end of the file. The
    # sentence names the innermost such block and the line it opened on -- not
    # the innermost surviving to end of text, which last-opened-first-closed
    # matching leaves as the OUTERMOST block, further from the mistake than the
    # failure line itself.
    "block_open_at_failure": (
        "game G {\n  players: 2\n  zones {\n    deck : Deck\n"
        "  state { s : Integer = 0 }\n}\n",
        "the `zones {` block opened on line 3 is never closed",
        False,
    ),
    # A block is left open, but every block open at the failure closes: the
    # failure is not inside the unclosed one, so no site is named and the
    # expectation -- computed under a bracket context the mistake did NOT
    # break -- is the honest advice.
    "block_open_elsewhere": (
        "game G {\n  players: 2 @\n  zones { deck : Deck }\n"
        "  state { s : Integer = 0 }\n}\nphase p {\n",
        "a block in this file is never closed",
        True,
    ),
    # A surplus `}`: which brace is surplus is not recoverable -- every
    # candidate matches equally well -- so the sentence states the count and
    # names no line.
    "surplus_close": (
        "game G {\n  players: 2\n  zones { deck : Deck } }\n"
        "  state { s : Integer = 0 }\n}\n",
        "more `}` than `{`",
        True,
    ),
    # A `"` with no closing `"`: a lexeme, not a block. Naming the string is
    # the fix, so it replaces the expectation the way a named block does.
    "string_open_at_failure": (
        "game G {\n  players: 2\n  zones { deck : Deck }\n"
        '  state { s : String = "oops }\n}\n',
        "the quoted string opened on line 4 is never closed",
        False,
    ),
    # The scan cannot reach the end of the file, so the balance past the
    # failure is unknown: the honest sentence is none. Here a stray `@` is
    # skipped and an unterminated string beyond it stops the scan for good --
    # its body would otherwise contribute braces it does not have.
    "unscannable": (
        'game G {\n  players: 2 @\n  state { s : String = "oops\n}\n',
        None,
        True,
    ),
}


def test_the_verdict_axis_is_the_renderers_own_registry() -> None:
    """Completeness by superset: the cells are keyed by the renderer's own
    verdict type, so a verdict added there with no source here arrives as a
    failure rather than as a silence.

    red under: add a member to `parse._StructuralVerdict` -- this names it.
    """
    assert set(_VERDICT_SOURCES) == set(_VERDICTS), (
        f"cells {sorted(_VERDICT_SOURCES)} against verdicts {sorted(_VERDICTS)}"
    )
    assert len(_VERDICTS) >= 6, _VERDICTS


@pytest.mark.parametrize("verdict", sorted(_VERDICT_SOURCES))
def test_a_source_earns_the_sentence_its_structural_verdict_names(
    verdict: str,
) -> None:
    """The verdict axis, each cell with the sentence it earns and whether the
    expectation clause stands beside it.

    The verdict is read back at the position the parser itself stamped on the
    span, so the cell proves the source reaches the verdict it claims rather
    than merely producing a message that looks right.
    """
    source, fragment, expectation_stands = _VERDICT_SOURCES[verdict]
    error = _render(source)
    span = error.diagnostic.span
    assert span is not None
    assert parse._structure(source, span.start, 0).verdict == verdict, (
        f"{verdict}: the source reaches "
        f"{parse._structure(source, span.start, 0).verdict!r} instead"
    )
    message = error.diagnostic.message
    if fragment is None:
        assert "never closed" not in message, message
        assert "more `}`" not in message, message
    else:
        assert fragment in message, f"{verdict}: expected {fragment!r} in: {message}"
    assert ("; expected " in message) is expectation_stands, (
        f"{verdict}: the expectation clause "
        f"{'is missing from' if expectation_stands else 'survives in'}: {message}"
    )


def test_a_file_of_unspellable_characters_claims_nothing_about_its_braces() -> None:
    """The `unscannable` verdict's OTHER route, which the cell above does not
    take: a scan steps over a character no terminal admits, but only so many.

    Past `parse._RESYNC_LIMIT` it stops and the diagnostic says nothing about
    the file's braces rather than guessing at them -- a designed constraint,
    since a file with that many unspellable characters has a problem the
    failure's own sentence already names.

    red under: let the resync loop run to the end of the source instead of
    stopping at `_RESYNC_LIMIT` -- the scan then completes and the verdict is
    `block_open_at_failure`, naming the unclosed `zones {`. Raising the
    constant is NOT the plant: the stray count below is derived from it, so a
    higher limit only writes more strays. Verified 2026-09-06.
    """
    strays = "@" * (parse._RESYNC_LIMIT + 2)
    source = f"game G {{\n  players: 2 {strays}\n  zones {{\n    deck : Deck\n"
    error = _render(source)
    span = error.diagnostic.span
    assert span is not None
    assert parse._structure(source, span.start, 0).verdict == "unscannable"
    assert "never closed" not in error.diagnostic.message, error.diagnostic.message


# --------------------------------------------------------------------------
# Axis (e) — where a block's own keyword sits relative to its `{`.
# --------------------------------------------------------------------------

#: shape -> (source, the whole structural sentence the shape earns). Each
#: source leaves exactly one block open at its failure, so the sentence names
#: that block and the line its `{` sits on.
_OPENER_SHAPES: dict[str, tuple[str, str]] = {
    "keyword against its brace": (
        "game G {\n  players: 2\n  zones {\n    deck : Deck\n",
        "the `zones {` block opened on line 3 is never closed",
    ),
    "keyword behind a header": (
        "game G {\n  players: 2\n  zones { deck : Deck }\n  phase p {\n    skip\n",
        "the `phase {` block opened on line 4 is never closed",
    ),
    # The brace is what is unmatched, so the brace's line is the one to look
    # at; the keyword a line above it is what says WHICH block it opens.
    "brace on the line below its keyword": (
        "game G {\n  players: 2\n  zones\n  {\n    deck : Deck\n",
        "the `zones {` block opened on line 4 is never closed",
    ),
    "two openers sharing one line": (
        "game G { zones {\n    deck : Deck\n",
        "the `zones {` block opened on line 1 is never closed",
    ),
    # An UNMATCHED `{` inside a quoted string is part of a lexeme, not a
    # block. The string is one token, so no scan can mistake it for structure
    # -- and it sits inside the block the sentence must name, so a scan that
    # counted it would name a block opened on the string's own line instead.
    "keyword and brace spelt inside a string": (
        "game G {\n  players: 2\n  zones { deck : Deck }\n  phase p {\n"
        '    let s = "zones {"\n    skip\n',
        "the `phase {` block opened on line 4 is never closed",
    ),
    # `%ignore LINE_COMMENT` means a commented brace never becomes a token,
    # and this one is likewise inside the block that must be named.
    "keyword and brace spelt inside a comment": (
        "game G {\n  players: 2\n  zones { deck : Deck }\n  phase p {\n"
        "    // note: zones {\n    skip\n",
        "the `phase {` block opened on line 4 is never closed",
    ),
    "nested blocks, the innermost is the site": (
        "game G {\n  players: 2\n  zones { deck : Deck }\n"
        "  phase p {\n    if x > 1 {\n      skip\n",
        "the `if {` block opened on line 5 is never closed",
    ),
    # A clause whose line begins with a word that opens no block: the keyword
    # that does is found by looking back, not by reading the line's first word.
    "a nested clause under an outer one on the same line": (
        "game G {\n  players: 2\n  zones { deck : Deck }\n"
        "  phase p {\n    for each player q: if x > 1 {\n      skip\n",
        "the `if {` block opened on line 5 is never closed",
    ),
    # A `produces` arm's header spells no block keyword at all. Its own name is
    # what a designer reads on that line, so its own name is what it is called.
    "a header that spells no block keyword": (
        "game G {\n  players: 2\n  cards: standard52\n"
        "  ranking: A K Q J 10 9 8 7 6 5 4 3 2\n  zones { deck : Deck }\n"
        "  state { s : Integer = 0 }\n  phase p {\n    play produces:\n"
        "      won(x) {\n        s := 1\n        @\n",
        "the `won {` block opened on line 9 is never closed",
    ),
    # A phase body written under its outcome set: the tokens between the two
    # braces are the group that has just closed, so the header before it is
    # what names the block.
    "a brace behind a group that has already closed": (
        "game G {\n  players: 2\n  zones { deck : Deck }\n"
        "  phase auction -> outcome {\n    won(Player)\n  }\n  {\n    skip\n",
        "the `phase {` block opened on line 7 is never closed",
    ),
}


@pytest.mark.parametrize("shape", sorted(_OPENER_SHAPES))
def test_a_block_is_named_by_the_keyword_that_opens_it(shape: str) -> None:
    """The opener axis: a block's name is read from the tokens before its `{`.

    A line's raw first word is not that name. A `{` on the line below its
    keyword has none; two blocks opening on one line share one; a keyword
    inside a string or a comment is not a keyword at all.

    Five shapes are born green, because a character scan gets them right too,
    and each names the mutation that reddens it. `keyword against its brace`
    and `keyword behind a header` fail when `_opener_word` returns None, so
    every block reads as "the block". `keyword and brace spelt inside a
    string` and `... a comment` fail when the scan reads characters instead of
    lexemes -- planted by neutering `//` and `"` in `_scan`'s input, which
    turns each commented and quoted brace into structure and names a block
    opened on the string's own line. `nested blocks, the innermost is the
    site` fails when the site becomes the OUTERMOST block open at the failure
    rather than the innermost. All verified 2026-09-06.
    """
    source, sentence = _OPENER_SHAPES[shape]
    message = _render(source).diagnostic.message
    assert sentence in message, f"{shape}: expected {sentence!r} in: {message}"


def test_the_block_opener_words_are_the_grammars_own() -> None:
    """Anti-vacuity on the derived registry.

    An empty set would not silence the cells above -- the fallback still names
    a block by its header's first word, and most headers begin with their own
    keyword -- so the collapse has to be asserted against directly. The one
    cell it WOULD redden is the nested clause under an outer one, whose line
    begins with `for`.

    red under: return `frozenset()` from `parse._block_opener_words` -- this
    cell and `a nested clause under an outer one on the same line` both fail.
    """
    words = parse._block_opener_words()
    assert {"zones", "phase", "state", "game", "if", "move_type", "else"} <= words, (
        sorted(words)
    )
    # A clause keyword that opens no block is not in the set, or a `players:`
    # line before an opener would name the block.
    assert not {"players", "cards", "winner", "ranking"} & words, sorted(words)
    assert all(word.replace("_", "").isalnum() for word in words), sorted(words)


def test_the_lexer_reads_the_same_terminals_as_the_parser() -> None:
    """The locator scans with a context-free lexer over the same grammar the
    Earley parser was built from. Two Lark objects compile that grammar, so
    the agreement is asserted rather than assumed.

    red under: point `parse._lexer` at a different grammar resource.
    """
    assert {t.name for t in parse._lexer().terminals} == {
        t.name for t in parse._parser().terminals
    }


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
    """A printable ASCII character is shown, and nothing more: the designer can
    already see it, so a Unicode gloss beside it would be noise."""
    message = _render("game G {\n  players: 2 @\n}\n").diagnostic.message
    assert message.startswith("syntax error: unexpected `@`;"), message


#: A run of word characters that begins with a digit is what a designer typed
#: as one word and what no lexeme can end inside
#: (tests/test_keyword_anchoring.py). `_offending_lexeme` does not branch on
#: the clause, so these are a WITNESS SET rather than a coverage axis: three
#: places a designer meets the same rendering, not three cells of a domain.
_DIGIT_LED_WITNESSES: dict[str, tuple[str, str]] = {
    "a player count": ("game G {\n  players: 2foo\n}\n", "`2foo`"),
    "a length bound": ("game G {\n  players: 2\n  max_length: 10x\n}\n", "`10x`"),
    "a state initializer": (
        "game G {\n  players: 2\n  state { s : Integer = 0z }\n}\n",
        "`0z`",
    ),
}


@pytest.mark.parametrize("clause", sorted(_DIGIT_LED_WITNESSES))
def test_a_word_run_beginning_with_a_digit_is_quoted_whole(clause: str) -> None:
    """The digits alone are not the mistake -- the suffix is.

    `2foo` is one run of word characters and no lexeme of this grammar can end
    inside one, so quoting `2` would show a designer a fragment their file does
    not contain and would hide the thing they must delete.
    """
    source, quoted = _DIGIT_LED_WITNESSES[clause]
    message = _render(source).diagnostic.message
    assert f"unexpected {quoted}" in message, f"{clause}: {message}"


# Characters that reach a game file by paste rather than by typing. Each is
# either invisible in an editor or indistinguishable from the ASCII character
# it stands in for, so the quoted character alone shows the designer nothing.
_PASTED_CHARACTERS = {
    "byte-order mark": ("\ufeffgame G {\n  players: 2\n}\n", "u+feff"),
    "non-breaking space": ("game G {\n\u00a0 players: 2\n}\n", "u+00a0"),
    "smart quote": ("game G {\n  players: \u201c2\u201d\n}\n", "u+201c"),
    "non-latin": ("game G {\n  players: \u0414\n}\n", "u+0414"),
}


@pytest.mark.parametrize("kind", sorted(_PASTED_CHARACTERS))
def test_an_unprintable_or_confusable_character_is_named(kind: str) -> None:
    """The character-class axis: what a designer can SEE of what they pasted.

    A quoted byte-order mark renders as nothing at all, and a quoted
    non-breaking space renders as a space — so the message has to carry the
    character's own name, which is what an editor's "show invisibles" and a
    web search both key on.
    """
    source, codepoint = _PASTED_CHARACTERS[kind]
    message = _render(source).diagnostic.message
    assert codepoint in message.lower(), (
        f"{kind}: the character is quoted but not named, so an invisible one "
        f"reads as a blank: {message!r}"
    )


def test_end_of_input_is_named_rather_than_quoted() -> None:
    """There is no character at end of input, and lark reports line and column
    as -1 there -- an absence, not a position. The end of the text is the
    honest span."""
    text = "game G {\n  players: 2\n"
    diagnostic = _render(text).diagnostic
    assert "end of file" in diagnostic.message, diagnostic.message
    assert diagnostic.span is not None
    assert diagnostic.span.line == text.count("\n") + 1, diagnostic.format()


#: Every sentence that names a line, with the line it names at the top of a
#: file. Both are computed from the token scan, which is memoized on the TEXT
#: alone -- so a line number that came out of the cache unshifted would name a
#: line in the Markdown prose above the block.
_LINE_NAMING_SENTENCES = {
    "an unclosed block": (
        "game G {\n  players: 2\n  zones {\n    deck : Deck\n"
        "  state { s : Integer = 0 }\n}\n",
        3,
    ),
    "an unclosed quoted string": (
        "game G {\n  players: 2\n  zones { deck : Deck }\n"
        '  state { s : String = "oops }\n}\n',
        4,
    ),
}


@pytest.mark.parametrize("sentence", sorted(_LINE_NAMING_SENTENCES))
def test_a_line_number_in_the_sentence_is_the_file_s_own(sentence: str) -> None:
    """The probe indexes the DSL text; the sentence is read against the file
    the text came from. A Markdown game file's fenced block starts partway down
    it, so a line number that skipped `line_offset` would name a line in the
    prose above the block.

    Both renderings of the same text run in one process, so a scan cached on
    the text alone cannot carry the first call's offset into the second.

    No corpus snippet fails to parse, so `tests/test_doc_snippets.py` cannot
    reach this: the cell needs its own witness.
    """
    source, line = _LINE_NAMING_SENTENCES[sentence]
    at_top = _render(source).diagnostic
    offset = _render(source, line_offset=20).diagnostic
    assert f"opened on line {line}" in at_top.message, at_top.message
    assert f"opened on line {line + 20}" in offset.message, offset.message
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
    word = parse._designer_word(name)
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

    red under: this cell IS the red-under for the FUNCTION -- it plants an
    unrenderable terminal and asserts the refusal fires and names it. That the
    refusal is REACHED is a separate claim, and a function-grain plant cannot
    make it: measured 2026-09-06 by deleting the `NAME` row from
    `_WORD_OVERRIDES` and checking a corpus game through
    `cardlang.pipeline.check_dsl`, which raised `UnrenderableTerminal` naming
    `NAME` -- so the guard sits on the path an ordinary check takes, not only
    on a path this test can call. An unused terminal is NOT the plant to
    reach for: lark prunes terminals no production references, so one never
    enters `_parser().terminals` and could not reach a designer either.
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
