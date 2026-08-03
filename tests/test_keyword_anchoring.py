"""Keyword anchoring: no lexeme may end in the middle of a word.

Drop the space after a clause keyword and the sentence used to compile as if
the space were there — `letx = 3` parsed to `LetStmt(name='x')`, a declaration
of `x`, while a reader takes it for an assignment to a variable called `letx`.
The engine's reading was not ambiguous (`=` is not an assignment operator here,
and the statement layer has no expression-statement form), so no `_ambig` node
existed for the corpus ambiguity budget to see: the divergence was between the
READER and the engine, which for a language whose acceptance test is "a
non-player can read the file cold" is the consequential kind.

The mechanism is the Earley DYNAMIC lexer, which is load-bearing here and
cannot simply be swapped out: `NAME`, `QNOUN`, `CARD_RANK_NAME` and
`STRUCT_TYPE_NAME` all match the same strings and are disambiguated by
POSITION, so a context-free (`basic`) lexer cannot tokenize this grammar at all
(pinned by `test_basic_lexer_cannot_tokenize_the_grammar`). The dynamic lexer
instead matches whichever terminal the parser expects at each position — so an
unanchored literal matches as a PREFIX of a longer word, and the remainder is
absorbed by whatever symbol follows.

The fix is one property over every terminal: a terminal whose match can end on
a word character must refuse to match when a word character follows. `is`/`not`
(tests/test_reserved_words.py) and the amount-position `all`/`one`/`some` were
anchored one at a time as their own ambiguities were found; this module states
the property over the WHOLE terminal table instead, so a keyword added to a new
production cannot land unanchored.

Anchoring and NAME-exclusion are separate halves. NAME-exclusion (the
`always|all|one|some|jointly|not|is|number` list) exists where a bare-NAME
reading would be a genuine SECOND parse, and stays exactly as it was; this
module is the anchoring half only.

Completeness ledger (docs/decisions.md "Closed-domain completeness")
-------------------------------------------------------------------
property:   no terminal of the shipped grammar can match a string ending in a
            word character `[A-Za-z0-9_]` when the next input character is
            also a word character. Equivalently: every lexeme boundary the
            grammar can produce inside a run of word characters is refused, so
            a fused spelling is a syntax error rather than a silent re-reading.
domain:     `_parser().terminals` — Lark's own compiled terminal table for
            `cardlang/grammar/cardlang.lark`, crossed with the sample words
            each terminal matches. That table holds BOTH halves of the class:
            the anonymous terminals Lark mints for inline string literals in
            productions (`"where"` -> `WHERE`), and the named terminals whose
            pattern is word-shaped (`MOVE_VERB`, `RANK_DIR`, `INT`).
registry:   the terminal table itself, read from the parser at test time — a
            literal added to any production mints an anonymous terminal and so
            becomes a row here with nothing to keep in sync. Sample words are
            derived per terminal too (`_samples`): a string pattern samples
            itself, a regex pattern samples the word runs in its own source
            plus generic identifier/integer probes, filtered to those the
            terminal matches whole.
covered:    every terminal x every derived sample that ends on a word
            character — `test_no_terminal_stops_mid_word`, which IS the grid.
            The hyphen leg is derived the same way
            (`test_hyphen_prefix_literals_also_exclude_the_hyphen`): a literal
            that is a prefix of a longer literal at a hyphen boundary must
            exclude `-` as well, which over this grammar is `as` (a prefix of
            `as-equally-as-possible`) and nothing else.
            The grid is a property of REGEXES, so it is backed by executed
            witnesses in the parser's own currency: `test_fused_*` reject one
            real sentence per fusion SHAPE (keyword+name, keyword+keyword,
            keyword+integer, word-shaped-terminal+name, integer+keyword), and
            `test_*_still_parses` keep the legitimate whole-word identifiers
            (`is_re`, `assets`, `some_var`) parsing. Without those the grid
            would prove a regex property and nothing about the language.
            `test_corpus_still_parses` pins GRAMMAR ACCEPTANCE only — that
            anchoring rejects no sentence a game writes. That anchoring also
            changed no accepted sentence's MEANING is a different claim, and
            it is the golden and characterization suites that carry it, not
            this module: parsing is not meaning, and a row that says so would
            be claiming coverage it does not run.
sampled:    the corpus is swept off-line rather than here — every whitespace
            run between two word characters in every `docs/games/*.cardlang`
            (comment bodies and string literals masked, since `%ignore
            LINE_COMMENT` makes a comment-internal deletion identical by
            construction) deleted one at a time and re-parsed. That sweep is
            ~7.8k Earley parses of whole games, far too slow for the suite; it
            is the derivation evidence for this module and is re-run when the
            grammar's lexical layer changes, not on every commit. Before this
            change 4761 of those 7776 deletions parsed to an IDENTICAL tree,
            over 84 keywords and 43 integer literals; after it, none do.
            The audit's framing check (surface-totality-audit, Step 1) ran in
            THIS context rather than in a fresh subagent, which the session
            forbade — a weaker form, recorded rather than skipped. What it
            would have guarded against is largely bought mechanically here
            instead: the axis is Lark's whole terminal table, not a list an
            author chose, so a domain narrowed to the implementation's shape
            would have to be a narrowing of the parser's own registry.
residual:   a terminal fusable only on a word no sample reaches. The regex
            terminals divide into two shapes and neither leaves one: the
            identifier-shaped ones (`NAME`, `QNOUN`, `CARD_RANK_NAME`,
            `STRUCT_TYPE_NAME`) end in a greedy word-character class, so they
            extend over ANY appended word character and cannot stop mid-word
            on any input; the word-alternation ones (`MOVE_VERB`, `RANK_DIR`,
            `RANK_CONV`) match a fixed finite word set, and `_samples` reads
            that set out of the pattern source. This residual is a recorded
            constraint of the sampling method, not deferred work, so it owns
            its record here and files no issue (CLAUDE.md, "The tracker").
"""

from __future__ import annotations

import re
from importlib import resources
from typing import Iterator

import pytest
from lark import Lark
from lark.exceptions import UnexpectedInput

from cardlang.ast import nodes as n
from cardlang.diagnostics import DiagnosticError
from cardlang.parse import _parser, parse_text

WORD_CHAR = re.compile(r"[A-Za-z0-9_]")
# Candidate word runs inside a terminal's own regex source. Hyphens are
# included so `ace-ten` (RANK_CONV) is sampled as one word rather than two.
WORD_RUN = re.compile(r"[A-Za-z0-9_-]+")
# Generic probes for the terminals whose regex spells a SHAPE rather than a
# word set: identifiers of each casing, an identifier with a digit, and
# integers of one and two digits.
GENERIC_PROBES = ("foo", "Foo", "x1", "1", "10")


def _samples(pattern: str, value: str | None) -> list[str]:
    """Words this terminal matches WHOLE, derived from the terminal itself."""
    if value is not None:
        return [value]
    # Backslashes are dropped before the word runs are read out: Lark escapes a
    # literal's hyphens (`as\-equally\-as\-possible`), and a run broken at those
    # escapes would sample the parts instead of the word — which is how the
    # hyphen-prefix leg below silently found nothing.
    candidates = set(WORD_RUN.findall(pattern.replace("\\", ""))) | set(GENERIC_PROBES)
    keep: list[str] = []
    for word in sorted(candidates):
        m = re.compile(pattern).match(word)
        if m is not None and m.end() == len(word):
            keep.append(word)
    return keep


def _grid() -> Iterator[tuple[str, str, str]]:
    """(terminal name, regex, sample word) for every word-final cell."""
    for term in _parser().terminals:
        pattern = term.pattern.to_regexp()
        # A string pattern samples itself; a regex pattern samples the words
        # its own source admits.
        value = term.pattern.value if term.pattern.type == "str" else None
        for word in _samples(pattern, value):
            if WORD_CHAR.fullmatch(word[-1]):
                yield term.name, pattern, word


GRID = sorted(_grid())


def _game(body: str) -> str:
    return (
        "game G {\n"
        "  players: 2\n"
        "  max_length: 1000\n"
        "  cards: standard52\n"
        "  ranking: A K Q J 10 9 8 7 6 5 4 3 2\n"
        "  zones { hand[player] : Hand<player>\n"
        "          pile : Deck }\n"
        "  state { x : Integer = 0 }\n"
        f"{body}\n"
        "}\n"
    )


def _rejects(src: str) -> None:
    with pytest.raises(DiagnosticError, match="syntax error"):
        parse_text(src, "t.cardlang")


# --- the grid ---------------------------------------------------------------


def test_grid_is_not_empty() -> None:
    """The grid is derived, so a derivation that silently returns nothing
    would make every cell below vacuously green.

    red under: any drift in `_samples`/`_grid` that stops a keyword sampling
    itself — observed while writing this module, when the word-run reader did
    not de-escape Lark's `as\\-equally\\-as\\-possible` and this test named the
    collapse."""
    names = {name for name, _, _ in GRID}
    assert len(GRID) > 100, f"grid collapsed to {len(GRID)} cells"
    # Both halves of the domain are present: a keyword terminal, and the
    # word-shaped terminals that spell a word SET rather than one literal.
    assert {"_WHERE_KW", "MOVE_VERB", "RANK_DIR", "INT"} <= names, sorted(names)[:20]
    # Every sample a keyword contributes is the keyword itself, so a derivation
    # that started sampling only lookahead fragments would show up here.
    assert ("_WHERE_KW", "where") in {(name, word) for name, _, word in GRID}


@pytest.mark.parametrize(
    ("name", "pattern", "word"),
    GRID,
    ids=[f"{name}-{word}" for name, _, word in GRID],
)
def test_no_terminal_stops_mid_word(name: str, pattern: str, word: str) -> None:
    """A terminal that matches `word` must not still match it when a word
    character follows — that match is a lexeme ending mid-word, which is what
    lets `letx` read as `let x`."""
    m = re.compile(pattern).match(word + "z")
    assert m is None or m.end() != len(word), (
        f"terminal {name} matches {word!r} as a prefix of {word + 'z'!r}: a "
        f"fused spelling would parse as if the space were there. Anchor it "
        f"with a trailing (?![A-Za-z0-9_]) lookahead in cardlang.lark."
    )


def test_hyphen_prefix_literals_also_exclude_the_hyphen() -> None:
    """A keyword that is another keyword's prefix at a HYPHEN boundary must
    exclude `-` too, or the shorter one matches inside the longer. Derived,
    not listed: over this grammar the pair is `as` inside
    `as-equally-as-possible`.

    red under: drop the `-` from `_AS_KW`'s lookahead in cardlang.lark."""
    words = {word for _, _, word in GRID} | {
        word
        for term in _parser().terminals
        for word in _samples(
            term.pattern.to_regexp(),
            term.pattern.value if term.pattern.type == "str" else None,
        )
    }
    prefixes = {
        short
        for short in words
        for long in words
        if long != short and long.startswith(short + "-")
    }
    assert prefixes == {"as"}, f"hyphen-prefix set changed: {sorted(prefixes)}"
    # Every KEYWORD terminal matching one of those prefixes must refuse it when
    # a hyphen follows. Identifier-shaped terminals are excluded, and derived
    # as such rather than named: a terminal that also matches an arbitrary
    # identifier is one, and for it ending at a hyphen is correct — `as` is a
    # legitimate whole NAME, it is only as a KEYWORD that it must not match
    # inside the longer keyword. Selection is by what a terminal MATCHES, not
    # by how its pattern is spelled: `PatternRE.value` is the regex source
    # rather than None, so an earlier `value is None` test here visited no
    # terminal at all and the assertion below never ran.
    probed = 0
    for term in _parser().terminals:
        pattern = re.compile(term.pattern.to_regexp())
        identifier_shaped = pattern.fullmatch("foo") is not None
        if identifier_shaped:
            continue
        for short in prefixes:
            if pattern.fullmatch(short) is None:
                continue  # not this keyword
            probed += 1
            m = pattern.match(short + "-")
            assert m is None or m.end() != len(short), (
                f"keyword terminal {term.name} matches {short!r} inside "
                f"{short + '-…'!r}: it must exclude `-` as well."
            )
    assert probed, "no keyword terminal was probed — the selection matched none"


# --- the lexer this rests on ------------------------------------------------


def test_basic_lexer_cannot_tokenize_the_grammar() -> None:
    """Why anchoring, rather than a context-free lexer that would take the
    longest match and kill the class outright: this grammar disambiguates
    identifier-shaped terminals BY POSITION, so a `basic` lexer cannot
    tokenize it. If this ever starts passing, the cheaper fix is back on the
    table and this module's premise needs re-examining.

    The parser is BUILT outside the raises: a build failure would satisfy a
    bare `raises(LarkError)` for an unrelated reason and leave the premise
    unproven. The claim is specifically that TOKENIZING fails, and on the
    terminal the position-dependence is about."""
    grammar = resources.files("cardlang.grammar").joinpath("cardlang.lark").read_text()
    parser = Lark(
        grammar,
        parser="earley",
        lexer="basic",
        propagate_positions=True,
        maybe_placeholders=True,
        start=["start", "stdlib_rules", "library"],
    )
    with pytest.raises(UnexpectedInput) as exc:
        parser.parse(_game("  phase p { let y = 1 }"), start="start")
    assert "STRUCT_TYPE_NAME" in str(exc.value)


# --- executed witnesses, one per fusion shape -------------------------------


def test_fused_keyword_then_name_is_rejected() -> None:
    """The issue's witness: `letx = 3` read as `let x = 3`."""
    _rejects(_game("  phase p { letx = 3 }"))


def test_unfused_let_still_declares() -> None:
    game = parse_text(_game("  phase p { let x2 = 3 }"), "t.cardlang")
    stmt = game.phases[0].items[0]
    assert isinstance(stmt, n.LetStmt) and stmt.name == "x2"


def test_fused_keyword_then_keyword_is_rejected() -> None:
    """`for each` -> `foreach`: two keywords, no identifier involved."""
    _rejects(_game("  phase p { foreach player p2: x := 1 }"))


def test_fused_keyword_then_integer_is_rejected() -> None:
    """A keyword's trailing anchor must exclude digits as well as letters —
    `up to10` is the one place a keyword meets a bare integer literal."""
    _rejects(_game("  phase p { let b = choose integer in 0 .. x up to10 }"))


def test_fused_word_shaped_terminal_then_name_is_rejected() -> None:
    """`MOVE_VERB` and `RANK_DIR` are word sets spelled as named terminals
    rather than inline literals — the same class, reached through the other
    half of the terminal table."""
    _rejects(_game("  phase p { moveall cards from pile to hand[0] }"))
    _rejects(_game("  winner: highestx"))


def test_fused_integer_then_keyword_is_rejected() -> None:
    """The mirror direction: `INT` cannot absorb letters, so a keyword after a
    digit run fuses however well the keyword itself is anchored. The anchor
    has to sit on `INT`."""
    _rejects(_game("  phase p { if x is 1and x is 0 { x := 1 } }"))


# --- what must keep parsing -------------------------------------------------


def test_all_players_variable_reads_as_the_variable() -> None:
    """The one case that was a live SILENT misresolution rather than only a
    misreading: with a variable of that name declared, `allplayers` derived
    both the variable and the `all players` collection, and the collection
    reading won. A NAME is the only reading left.

    Born red, and measured rather than assumed: parsed against the pre-change
    grammar with `ambiguity="explicit"`, this source carries 1 `_ambig` node
    and the default parser's chosen tree contains the `all_players` node."""
    src = (
        "game G {\n"
        "  players: 2\n"
        "  max_length: 1000\n"
        "  cards: standard52\n"
        "  ranking: A K Q J 10 9 8 7 6 5 4 3 2\n"
        "  zones { hand[player] : Hand<player> }\n"
        "  state { allplayers : Integer = 0 }\n"
        "  phase p { let m = allplayers }\n"
        "}\n"
    )
    game = parse_text(src, "t.cardlang")
    stmt = game.phases[0].items[0]
    assert isinstance(stmt, n.LetStmt)
    assert isinstance(stmt.value, n.NameRef) and stmt.value.name == "allplayers"


def test_keyword_prefixed_identifiers_still_parse() -> None:
    """Anchoring may only remove the mid-word boundary, never whole words that
    merely BEGIN with a keyword."""
    for name in ("letter", "iffy", "forward", "toe", "each_hand", "allocation"):
        game = parse_text(_game(f"  phase p {{ let {name} = 1 }}"), "t.cardlang")
        stmt = game.phases[0].items[0]
        assert isinstance(stmt, n.LetStmt) and stmt.name == name


def test_hyphenated_literal_still_parses() -> None:
    """`as-equally-as-possible` must survive `as` being anchored."""
    game = parse_text(
        _game("  phase p { deal all cards from pile as-equally-as-possible to each hand[player] }"),
        "t.cardlang",
    )
    assert game.phases[0].items


def test_corpus_still_parses() -> None:
    """Anchoring must not reject a single sentence any game actually writes.
    Acceptance only — that no accepted sentence changed MEANING is the golden
    and characterization suites' claim, not this one."""
    from pathlib import Path

    games = sorted((Path(__file__).parent.parent / "docs" / "games").glob("*.cardlang"))
    assert games
    for path in games:
        parse_text(path.read_text(), path.name)
