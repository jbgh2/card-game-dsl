"""A misspelled keyword is refused at the word, and told the keywords it nearly spells.

A designer who writes `shufle deck` for `shuffle deck` slipped on the word that
begins the statement. Where the grammar also takes a name there, the parser
reads the slip as one and fails on a word after it, or derives the sentence
and the checker refuses the name; where it does not, it fails on the slip
itself. Each way the refusal stands on the word the designer wrote and
offers, as Near Misses (docs/glossary/near-miss.md), the keywords the grammar
accepts there that the word nearly spells and that, written there, get the
file past the refusal.

Completeness ledger (decisions.md "Closed-domain completeness")
---------------------------------------------------------------
property:        a word written where the grammar accepts a keyword it nearly
                 spells is refused with its span on that word and its Near
                 Misses carried as data (`Diagnostic.near_misses`) and
                 rendered as the one `did you mean` clause: by the parser
                 where the text does not derive, every keyword offered
                 getting the file past that refusal; by the checker's
                 unresolved-name refusal where it derives, every keyword
                 offered giving text that parses with the keyword read as
                 itself, and the refusal told as a misspelled keyword where a
                 keyword is its first Near Miss. A word whose keyword reading
                 does not get past, does not derive, or derives only as a
                 name is offered no keyword.
domain:          two grids. Block items: every element of a repetition in the
                 compiled grammar whose first words include a keyword, crossed
                 with every keyword spelling that may begin an item there,
                 each item the grammar's shortest sentence beginning with that
                 keyword inside the smallest text holding the position
                 (`HOSTS`); Lark compiles every `statement*` into one
                 repetition, so every statement list is one row. Names: every
                 keyword spelling at every position where the parser's own
                 expected set holds it beside a terminal that reads a word
                 resembling no keyword, a position being that expected set,
                 each in the shortest game-file sentence the grammar builds
                 to it, crossed with the three one-letter slips (`_SLIP_KINDS`)
                 that spell no keyword and resemble it at least as much as a
                 Near Miss must; a sentence that derives is told inside
                 `_CLEAN_HOST`, so the refusal standing on the slip is the
                 slip's. Beside the grids, the misuse probes: the keywords
                 that continue the item before the slip, a single-statement
                 slot, the clause heads of one production's fixed sequence,
                 the slips offered nothing at the parse, the names offered no
                 keyword at the checker (`_NOT_OFFERED_AS_A_NAME`), the code
                 a declared name nearer than the keyword keeps, and the two
                 issue witnesses in `docs/games/hearts.cardlang`.
registry:        block positions: `_positions` over
                 `cardlang.parse._parser().rules`; name positions:
                 `_positions_a_name_competes_at` over the same rules, narrowed
                 by `cardlang.parse._parser()`'s expected set; spellings:
                 `cardlang.parse._designer_word`; name-like terminals:
                 `_name_like` over `cardlang.parse._parser().terminals`; the
                 measure and the clause:
                 tests/test_near_misses.py::test_the_parse_layer_ranks_by_the_one_measure.
held by:         Derived and Pinned. A refusal's offer is data on one
                 `Diagnostic`, built at the parse's one site
                 (`cardlang.parse._syntax_error`) and the checker's one
                 ranking (`cardlang.diagnostics.DiagnosticBag.unknown`), but
                 which words a position takes is the grammar's, read off the
                 compiled rules at refusal time, and no type can hold it.
does not prove:  that a position is offered in every sentence holding it: a
                 cell is one sentence per position, the shortest, so a slip
                 whose reading as a name depends on words the shortest
                 sentence does not have (a call's parentheses after it) is a
                 probe's to show, not the grid's. Nor that the text checks
                 once the keyword is written, which a game whose other words
                 are clean shows only for the hearts witnesses.
"""

from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass
from functools import cache
from pathlib import Path

import pytest
from lark.exceptions import UnexpectedInput
from lark.grammar import NonTerminal, Symbol, Terminal

from cardlang import parse
from cardlang.diagnostic_codes import Code
from cardlang.diagnostics import NEAR_MISS_CUTOFF, Diagnostic, DiagnosticError, Span, resemblance
from cardlang.pipeline import check_dsl

_ROOT = Path(__file__).resolve().parent.parent
_HOLE = "@@"

# The smallest text holding each block item position, the item at `@@`, and
# the entry point that parses it.
HOSTS: dict[str, tuple[str, str]] = {
    "top_item": ("start", "@@\ngame g {\n}\n"),
    "library_item": ("library", "library l {\n  @@\n}\n"),
    "game_item": ("start", "game g {\n  @@\n}\n"),
    "phase_item": ("start", "game g {\n  phase p {\n    @@\n  }\n}\n"),
    "statement": ("start", "game g {\n  phase p {\n    before_each {\n      @@\n    }\n  }\n}\n"),
    "mode_item": ("start", "game g {\n  phase p {\n    mode m {\n      @@\n    }\n  }\n}\n"),
    "rule_clause": ("start", "rule r {\n  @@\n}\n"),
    "elif_clause": ("start", "game g {\n  phase p {\n    let y = if x then x @@ else x\n  }\n}\n"),
}

# --------------------------------------------------------------------------
# The compiled grammar, read as data.
# --------------------------------------------------------------------------


def _rules() -> dict[str, list[list[Symbol]]]:
    by: dict[str, list[list[Symbol]]] = defaultdict(list)
    for rule in parse._parser().rules:
        by[rule.origin.name].append(list(rule.expansion))
    return by


@cache
def _first() -> dict[str, frozenset[str]]:
    """Each nonterminal's first terminals (the compiled grammar has no empty
    expansion, so a sequence's first terminals are its first symbol's)."""
    rules = _rules()
    first: dict[str, set[str]] = defaultdict(set)
    changed = True
    while changed:
        changed = False
        for origin, expansions in rules.items():
            for expansion in expansions:
                head = expansion[0]
                new = {head.name} if head.is_term else first[head.name]
                if not new <= first[origin]:
                    first[origin] |= new
                    changed = True
    return {name: frozenset(terms) for name, terms in first.items()}


def _spellings(terminal: str) -> tuple[str, ...]:
    """The words a designer types for `terminal`; none for a class of text."""
    quoted = re.findall(r"`([^`]*)`", parse._designer_word(terminal))
    return tuple(word for word in quoted if re.fullmatch(r"[A-Za-z][A-Za-z0-9_]*", word))


@cache
def _positions() -> dict[str, frozenset[str]]:
    """Every block item position: a repetition's element whose first words
    include a keyword, with those keywords' terminals."""
    found: dict[str, frozenset[str]] = {}
    for origin, expansions in _rules().items():
        if not re.fullmatch(r"__\w+_(star|plus)_\d+", origin):
            continue
        for expansion in expansions:
            head = expansion[0]
            if head.name == origin or head.is_term:
                continue
            keywords = frozenset(t for t in _first()[head.name] if _spellings(t))
            if keywords:
                found[head.name] = keywords
    return found


_SAMPLES = ("x", "A", "hearts", "1", '"s"')


@cache
def _sample(terminal: str) -> str:
    """A word `terminal` admits: its own spelling, or the first sample its
    pattern matches."""
    term = next(t for t in parse._parser().terminals if t.name == terminal)
    pattern = re.compile(term.pattern.to_regexp())
    spelled = _spellings(terminal)
    if spelled and pattern.fullmatch(spelled[0]):
        return spelled[0]
    literal = term.pattern.value if type(term.pattern).__name__ == "PatternStr" else None
    if literal is not None:
        return str(literal)
    for sample in _SAMPLES:
        if pattern.fullmatch(sample):
            return sample
    rendered = re.findall(r"`([^`]*)`", parse._designer_word(terminal))
    for candidate in rendered:
        if pattern.fullmatch(candidate):
            return str(candidate)
    raise AssertionError(f"no sample for terminal {terminal}")


@cache
def _shortest() -> dict[str, tuple[str, ...]]:
    """Each nonterminal's shortest sentence, as terminal names."""
    rules = _rules()
    best: dict[str, tuple[str, ...]] = {}
    changed = True
    while changed:
        changed = False
        for origin, expansions in rules.items():
            for expansion in expansions:
                parts: list[str] = []
                for symbol in expansion:
                    if symbol.is_term:
                        parts.append(symbol.name)
                    elif symbol.name in best:
                        parts.extend(best[symbol.name])
                    else:
                        break
                else:
                    if origin not in best or len(parts) < len(best[origin]):
                        best[origin] = tuple(parts)
                        changed = True
    return best


def _starting(symbol: Symbol, terminal: str, seen: frozenset[str]) -> tuple[str, ...] | None:
    """The shortest sentence of `symbol` whose first word is `terminal`."""
    if isinstance(symbol, Terminal):
        return (symbol.name,) if symbol.name == terminal else None
    assert isinstance(symbol, NonTerminal)
    if symbol.name in seen or terminal not in _first().get(symbol.name, frozenset()):
        return None
    shortest = _shortest()
    found: tuple[str, ...] | None = None
    for expansion in _rules()[symbol.name]:
        head = _starting(expansion[0], terminal, seen | {symbol.name})
        if head is None:
            continue
        tail: list[str] = []
        for rest in expansion[1:]:
            tail.extend((rest.name,) if rest.is_term else shortest[rest.name])
        candidate = head + tuple(tail)
        if found is None or len(candidate) < len(found):
            found = candidate
    return found


@dataclass(frozen=True)
class Cell:
    position: str
    keyword: str
    item: str
    slip: str


def _all_spellings() -> frozenset[str]:
    return frozenset(w for t in parse._parser().terminals for w in _spellings(t.name))


def _slip(keyword: str) -> str:
    """A deterministic one-letter slip of `keyword` that spells no keyword: a
    letter dropped from the middle, or for a short word its first doubled."""
    taken = _all_spellings()
    if len(keyword) >= 4:
        middle = len(keyword) // 2
        for at in sorted(range(1, len(keyword)), key=lambda i: abs(i - middle)):
            slip = keyword[:at] + keyword[at + 1 :]
            if slip not in taken:
                return slip
    return keyword[0] + keyword


def _cells() -> list[Cell]:
    cells: list[Cell] = []
    for position, terminals in sorted(_positions().items()):
        for terminal in sorted(terminals):
            names = _starting(NonTerminal(position), terminal, frozenset())
            assert names is not None, f"no sentence of {position} begins with {terminal}"
            tail = " ".join(_sample(name) for name in names[1:])
            for keyword in _spellings(terminal):
                cells.append(Cell(position, keyword, f"{keyword} {tail}".rstrip(), _slip(keyword)))
    return cells


def _host(position: str, item: str) -> tuple[str, str]:
    start, host = HOSTS[position]
    return start, host.replace(_HOLE, item, 1)


def _refusal(start: str, text: str) -> Diagnostic | None:
    try:
        parse.parse_to_tree(text, "probe.cardlang", start=start)
    except DiagnosticError as exc:
        return exc.diagnostic
    return None


def _assert_offered(start: str, text: str, slip: str, meant: str) -> Diagnostic:
    return _assert_offered_at(start, text, text.index(slip), slip, meant)


# --------------------------------------------------------------------------
# The grid.
# --------------------------------------------------------------------------

CELLS = _cells()


def test_every_block_item_position_has_a_host() -> None:
    """red under: adding a block (`foo { foo_item* }`) whose items begin with
    a keyword to `cardlang/grammar/cardlang.lark`."""
    assert set(HOSTS) == set(_positions())


@pytest.mark.parametrize("cell", CELLS, ids=[f"{c.position}-{c.keyword}" for c in CELLS])
def test_a_misspelled_item_keyword_is_offered_at_the_slip(cell: Cell) -> None:
    start, text = _host(cell.position, cell.item)
    if _refusal(start, text) is not None:
        pytest.fail(f"the unslipped item does not parse in its host: {cell.item!r}")
    slipped = text.replace(cell.item, cell.slip + cell.item[len(cell.keyword) :], 1)
    _assert_offered(start, slipped, cell.slip, cell.keyword)


# --------------------------------------------------------------------------
# The witness and the misuse probes.
# --------------------------------------------------------------------------


def test_the_witness_shufle_deck_in_hearts() -> None:
    text = (_ROOT / "docs/games/hearts.cardlang").read_text()
    assert "      shuffle deck\n" in text
    slipped = text.replace("      shuffle deck\n", "      shufle deck\n", 1)
    refused = _refusal("start", slipped)
    assert refused is not None
    line = slipped[: slipped.index("shufle")].count("\n") + 1
    assert refused.format() == (
        f"probe.cardlang:{line}:7: error: syntax error: unexpected `shufle`; did you mean `shuffle`?"
    )
    _assert_offered("start", slipped, "shufle", "shuffle")


_GAME = "game g {\n  phase p {\n    @@\n  }\n}\n"
_MOVE = "move_type m {\n  @@\n}\n"

# (host, the slipped text, the slip, the keyword it must offer)
_OFFERED: dict[str, tuple[str, str, str, str]] = {
    "an `else` after an `if` block": (_GAME, "if x { } esle { }", "esle", "else"),
    "a round's trailing `trump`": (
        _GAME, "round t from a over b source s into z winner w trmp hearts", "trmp", "trump"),
    "a round's trailing `early`": (
        _GAME, "round t from a over b source s into z winner w erly e", "erly", "early"),
    "an operator word ending a statement": (_GAME, "x := a adn b", "adn", "and"),
    "an operator word inside a condition": (_GAME, "if a adn b { }", "adn", "and"),
    "a statement in a single-statement slot": (
        _GAME, "for each player p: shufle x", "shufle", "shuffle"),
    "a rule reference's `override`": (_GAME, "active_rules: [overide Foo]", "overide", "override"),
    "a round's fixed `over`": (
        _GAME, "round t from a ovr b source s into z winner w", "ovr", "over"),
    "a move type's `when:`": (_MOVE, "wehn: true effect { }", "wehn", "when"),
    "a move type's `effect`": (_MOVE, "when: true efect { }", "efect", "effect"),
    "a phase clause written with a colon": (_GAME, "legl_moves: [m]", "legl_moves", "legal_moves"),
    "a keyword slipped into another keyword": (_GAME, "x produce: a { }", "produce", "produces"),
    "a primitive's `reads`": (
        "@@", "game g { primitives { f(x: Card): Boolean raeds hand } }", "raeds", "reads"),
    "a read's `in`": (
        "@@", "game g { primitives { f(x: Card): Boolean reads t inn h } }", "inn", "in"),
    "a combination's `with`": (
        "@@", "combinations c { full: 3 of a kind wth 2 of a kind }", "wth", "with"),
    "a choice's trailing `excluding`": (
        _GAME, "let y = choose integer in 0 .. h excludng 3", "excludng", "excluding"),
    "a climbing round's trailing `before`": (
        _GAME,
        "round climb t from a over b source s into z combinations c follows f until u "
        "befor asking q { }",
        "befor", "before"),
}


@pytest.mark.parametrize("probe", sorted(_OFFERED))
def test_a_keyword_slip_beside_the_grid_is_offered(probe: str) -> None:
    host, item, slip, meant = _OFFERED[probe]
    _assert_offered("start", host.replace(_HOLE, item), slip, meant)


# (the slipped text, a keyword that must not be offered)
_NOT_OFFERED: dict[str, tuple[str, str]] = {
    # A state variable resembling a keyword, assigned with the wrong operator:
    # the keyword in its place fails at the same `=`.
    "a name resembling a keyword, assigned with `=`": ("deals = 3", "deal"),
    "a plural name resembling a keyword, assigned with `=`": ("rounds = 3", "round"),
    "a name resembling a keyword, assigned with `:`": ("deals: 3", "deal"),
    # `shuffle` takes a zone, not an argument list, so it does not get past `(`.
    "a keyword whose reading fails at the same place": ("shufle(deck)", "shuffle"),
}


@pytest.mark.parametrize("probe", sorted(_NOT_OFFERED))
def test_a_slip_whose_keyword_does_not_get_past_is_offered_nothing(probe: str) -> None:
    """Born green. red under: dropping the check in
    `cardlang.parse._past_with` that a keyword in the word's place reads past
    the word after it."""
    item, keyword = _NOT_OFFERED[probe]
    refused = _refusal("start", _GAME.replace(_HOLE, item))
    assert refused is not None
    assert keyword not in refused.near_misses, refused.format()
    assert "did you mean" not in refused.format(), refused.format()
    assert "expected " in refused.format(), refused.format()


def test_a_spelling_only_a_twin_takes_is_never_offered() -> None:
    """The game-level `trump:` is a retired clause the Diagnostic Grammar
    takes in order to refuse it; past an earlier retired block the composed
    parser reads further and its expectation holds `trump`. red under: gating
    `cardlang.parse._past_with` on the parser that raised the failure."""
    text = "game g {\n  players: 4\n  trick_order { }\n  trmp: hearts\n}\n"
    refused = _refusal("start", text)
    assert refused is not None
    assert "trump" not in refused.near_misses, refused.format()


def test_a_word_resembling_no_keyword_keeps_the_parser_s_expectation() -> None:
    """Born green. red under: setting `NEAR_MISS_CUTOFF` to 0 in
    `cardlang.diagnostics`."""
    refused = _refusal("start", _GAME.replace(_HOLE, "zzq deck"))
    assert refused is not None
    assert refused.near_misses == ()
    assert "unexpected `deck`; expected " in refused.format(), refused.format()


def test_a_slip_two_words_before_the_failure_is_offered() -> None:
    """red under: `_read_before` returning only the word just before the
    refusal."""
    _assert_offered("start", _GAME.replace(_HOLE, "let n = al players where x"), "al", "all")


def _hearts_with(line: str, slipped: str) -> tuple[str, int]:
    text = (_ROOT / "docs/games/hearts.cardlang").read_text()
    assert line in text
    changed = text.replace(line, slipped, 1)
    return changed, text.index(line)


def _located(text: str, at: int) -> str:
    return f"hearts.cardlang:{text.count(chr(10), 0, at) + 1}:{at - text.rfind(chr(10), 0, at)}"


def test_a_slip_the_grammar_derives_as_a_name_is_offered_the_keyword() -> None:
    """The issue's witness: the amount `som` is refused standing on the word
    and offered `some`, told as a misspelled keyword; `some` in its place
    parses, and is then refused as an amount `jointly` alone gives a size.
    red under: dropping `keywords=` from the unresolved-name refusal in
    `cardlang.resolve.classifier._rewrite`."""
    slipped, at = _hearts_with("deal 13 cards", "deal som cards")
    at += len("deal ")
    with pytest.raises(DiagnosticError) as refused:
        check_dsl(slipped, "hearts.cardlang")
    told = refused.value.diagnostic
    assert told.format() == (
        f"{_located(slipped, at)}: error: unresolved name 'som'; did you mean `some`?"
    ), told.format()
    assert told.code is Code.MISSPELLED_KEYWORD
    assert _refusal("start", slipped.replace("deal som cards", "deal some cards", 1)) is None


def test_the_keyword_offered_checks_clean_where_the_rest_of_the_game_is() -> None:
    """A declared name nearly spelled as well is offered beside the keyword,
    after it, and writing the keyword gives the game back clean."""
    slipped, at = _hearts_with("move all cards to deck", "move al cards to deck")
    at += len("move ")
    with pytest.raises(DiagnosticError) as refused:
        check_dsl(slipped, "hearts.cardlang")
    told = refused.value.diagnostic
    assert told.format() == (
        f"{_located(slipped, at)}: error: unresolved name 'al'; did you mean `all` or `A`?"
    ), told.format()
    assert told.code is Code.MISSPELLED_KEYWORD
    check_dsl(slipped.replace("move al cards", "move all cards", 1), "hearts.cardlang")


def _in_the_clean_host(statement: str, state: str = "") -> tuple[str, int]:
    """`statement` as the clean host's one phase statement, and the offset of
    its `@@`-marked word (the marker removed)."""
    game = _CLEAN_HOST.replace("    deal 1 cards from deck to each hand\n", f"    {statement}\n", 1)
    if state:
        game = game.replace("  state {\n", f"  state {{\n    {state}\n", 1)
    at = game.index(_HOLE)
    return game.replace(_HOLE, "", 1), at


def _the_refusal_at(game: str, at: int) -> Diagnostic:
    standing = _standing(game, at)
    assert len(standing) == 1, _refusals(game)
    return standing[0]


# (the statement with the word marked, a state declaration, a keyword that
# must not be offered)
_NOT_OFFERED_AS_A_NAME: dict[str, tuple[str, str, str]] = {
    "a keyword the grammar takes nowhere an operand stands": ("let n = @@shufle", "", "shuffle"),
    "a keyword the operand takes whose reading does not derive": ("let n = @@nott", "", "not"),
    "a keyword the grammar would read as a name": (
        "deal @@som cards from deck to each hand", "", "sum"),
    "a keyword the operand takes that needs the words after it": (
        "let n = @@nubmer", "", "number"),
}


@pytest.mark.parametrize("probe", sorted(_NOT_OFFERED_AS_A_NAME))
def test_a_name_whose_keyword_could_not_stand_there_is_not_offered_it(probe: str) -> None:
    """Born green but for the name-read row. red under: for the name-read
    row, `cardlang.parse._derives_reading` returning True for any tree; for
    the two rows whose keyword reading does not derive, returning True where
    the parse is refused."""
    statement, state, keyword = _NOT_OFFERED_AS_A_NAME[probe]
    game, at = _in_the_clean_host(statement, state)
    told = _the_refusal_at(game, at)
    assert keyword not in told.near_misses, told.format()
    if not set(told.near_misses) & _all_spellings():
        assert told.code is Code.UNKNOWN_NAME, told.format()


def test_a_declared_name_nearer_than_the_keyword_keeps_the_unknown_name_code() -> None:
    """Both are offered, the nearer first, and the code follows the first.
    red under: telling `MISSPELLED_KEYWORD` in `DiagnosticBag.unknown`
    wherever a keyword is offered."""
    game, at = _in_the_clean_host(
        "deal @@somx cards from deck to each hand", "somxs : Integer = 1")
    told = _the_refusal_at(game, at)
    assert told.near_misses[:2] == ("somxs", "some"), told.format()
    assert told.code is Code.UNKNOWN_NAME, told.format()


def test_a_keyword_nearer_than_a_declared_name_is_told_as_a_misspelled_keyword() -> None:
    game, at = _in_the_clean_host("deal @@som cards from deck to each hand", "son : Integer = 1")
    told = _the_refusal_at(game, at)
    assert told.near_misses[:2] == ("some", "son"), told.format()
    assert told.code is Code.MISSPELLED_KEYWORD, told.format()


@pytest.mark.xfail(
    strict=True,
    raises=AssertionError,
    reason="issue #TBD-keyword: a call's unknown function is refused with no keyword offered",
)
def test_a_slip_read_as_a_call_is_offered_the_keyword() -> None:
    game, at = _in_the_clean_host(
        "deal chosen some cards from deck where @@jointy (x) to each hand")
    told = _the_refusal_at(game, at)
    assert "jointly" in told.near_misses, told.format()


def test_a_name_in_library_text_reads_no_game_text() -> None:
    """A span outside the source offers nothing, whatever the text at its
    offsets. red under: dropping the source-name check from
    `cardlang.parse.keywords_in_place_of`."""
    text = _GAME.replace(_HOLE, "deal som cards from deck to each hand")
    at = text.index("som")
    elsewhere = Span("library.cardlang", at, at + 3, 1, 1)
    assert parse.keywords_in_place_of(parse.SourceText("probe.cardlang", text), elsewhere) == ()
    here = Span("probe.cardlang", at, at + 3, 1, 1)
    assert parse.keywords_in_place_of(parse.SourceText("probe.cardlang", text), here) == ("some",)


# --------------------------------------------------------------------------
# The grid of keywords a name competes with.
#
# A position is what the parser takes at a word: the expected set the
# compiled grammar reports there. Each keyword the grammar takes at a
# position where it also takes a name-like terminal is slipped three ways,
# in the smallest sentence that holds the position.
# --------------------------------------------------------------------------


def _name_like() -> frozenset[str]:
    """The terminals that read a word resembling no keyword."""
    return frozenset(
        t.name
        for t in parse._parser().terminals
        if type(t.pattern).__name__ == "PatternRE" and re.fullmatch(t.pattern.to_regexp(), "zzq")
    )


@cache
def _follow() -> dict[str, frozenset[str]]:
    rules = _rules()
    first = _first()
    follow: dict[str, set[str]] = defaultdict(set)
    for start in parse._parser().options.start:
        follow[start].add("$END")
    changed = True
    while changed:
        changed = False
        for origin, expansions in rules.items():
            for expansion in expansions:
                for at, symbol in enumerate(expansion):
                    if symbol.is_term:
                        continue
                    if at + 1 == len(expansion):
                        new = set(follow[origin])
                    else:
                        after = expansion[at + 1]
                        new = {after.name} if after.is_term else set(first[after.name])
                    if not new <= follow[symbol.name]:
                        follow[symbol.name] |= new
                        changed = True
    return {name: frozenset(terms) for name, terms in follow.items()}


def _seq(symbols: list[Symbol]) -> tuple[str, ...]:
    shortest = _shortest()
    out: list[str] = []
    for symbol in symbols:
        out.extend((symbol.name,) if symbol.is_term else shortest[symbol.name])
    return tuple(out)


@cache
def _contexts() -> dict[str, tuple[tuple[str, ...], tuple[str, ...]]]:
    """Each nonterminal's shortest surroundings in a game file."""
    found: dict[str, tuple[tuple[str, ...], tuple[str, ...]]] = {"start": ((), ())}
    changed = True
    while changed:
        changed = False
        for origin, expansions in _rules().items():
            if origin not in found:
                continue
            left, right = found[origin]
            for expansion in expansions:
                for at, symbol in enumerate(expansion):
                    if symbol.is_term:
                        continue
                    candidate = (left + _seq(expansion[:at]), _seq(expansion[at + 1 :]) + right)
                    best = found.get(symbol.name)
                    if best is None or len(candidate[0]) + len(candidate[1]) < len(best[0]) + len(best[1]):
                        found[symbol.name] = candidate
                        changed = True
    return found


@cache
def _endings() -> dict[str, dict[str, tuple[str, ...]]]:
    """For each nonterminal, the shortest sentence of it whose last part is
    a repetition, by the repetition: after it, the parser still takes the
    repetition's next element."""
    rules = _rules()
    repeating = {o for o, expansions in rules.items() if any(e[0].name == o for e in expansions)}
    ends: dict[str, dict[str, tuple[str, ...]]] = defaultdict(dict)
    for name in repeating:
        ends[name][name] = _shortest()[name]
    changed = True
    while changed:
        changed = False
        for origin, expansions in rules.items():
            for expansion in expansions:
                last = expansion[-1]
                if last.is_term:
                    continue
                for repetition, tail in list(ends[last.name].items()):
                    candidate = _seq(expansion[:-1]) + tail
                    best = ends[origin].get(repetition)
                    if best is None or len(candidate) < len(best):
                        ends[origin][repetition] = candidate
                        changed = True
    return ends


def _statically_open(origin: str, expansion: list[Symbol], at: int) -> bool:
    """Whether a name-like terminal may stand where `expansion[at]` does: by
    an alternative sharing the prefix, the origin's follow where the prefix
    is complete, or a repetition the prefix ends with. A superset, which the
    parser's own expected set then narrows."""
    first, follow, names = _first(), _follow(), _name_like()
    prefix = [s.name for s in expansion[:at]]
    taken: set[str] = set()
    for other in _rules()[origin]:
        if [s.name for s in other[:at]] != prefix:
            continue
        if len(other) > at:
            head = other[at]
            taken |= {head.name} if head.is_term else first[head.name]
        else:
            taken |= follow[origin]
    if at and not expansion[at - 1].is_term:
        for repetition in _endings()[expansion[at - 1].name]:
            for other in _rules()[repetition]:
                if other[0].name == repetition and len(other) > 1:
                    head = other[1]
                    taken |= {head.name} if head.is_term else first[head.name]
    return bool(taken & names)


def _expected_at(text: str, at: int) -> frozenset[str]:
    try:
        parse._parser().parse(text[:at] + "\x00", start="start")
    except UnexpectedInput as stopped:
        if getattr(stopped, "pos_in_stream", None) != at:
            return frozenset()
        names = getattr(stopped, "allowed", None) or getattr(stopped, "expected", None) or ()
        return frozenset(str(getattr(t, "name", t)) for t in names)
    return frozenset()


_SLIP_KINDS = ("dropped", "doubled", "swapped")


def _slipped(keyword: str, kind: str) -> str | None:
    """`keyword` with one letter dropped, doubled or swapped with the next,
    nearest the middle and past the first letter; None where every such
    slip spells a keyword or resembles the keyword less than a Near Miss
    must."""
    taken = _all_spellings()
    middle = len(keyword) // 2
    for at in sorted(range(1, len(keyword)), key=lambda i: abs(i - middle)):
        if kind == "dropped":
            slip = keyword[:at] + keyword[at + 1 :]
        elif kind == "doubled":
            slip = keyword[:at] + keyword[at] + keyword[at:]
        else:
            if at + 1 >= len(keyword) or keyword[at] == keyword[at + 1]:
                continue
            slip = keyword[:at] + keyword[at + 1] + keyword[at] + keyword[at + 2 :]
        if slip and slip not in taken and resemblance(slip, keyword) >= NEAR_MISS_CUTOFF:
            return slip
    return None


@dataclass(frozen=True)
class NameCell:
    keyword: str
    position: str
    words: tuple[str, ...]
    at: int
    kind: str
    slip: str

    def text(self, word: str) -> tuple[str, int]:
        """The host with `word` at the cell's position, and its offset."""
        before = " ".join(self.words[: self.at])
        offset = len(before) + 1 if before else 0
        return " ".join((*self.words[: self.at], word, *self.words[self.at + 1 :])), offset


@cache
def _positions_a_name_competes_at() -> dict[tuple[str, frozenset[str]], tuple[str, tuple[str, ...], int]]:
    """Every keyword the grammar takes where it also takes a name-like
    terminal, by the expected set there, with the smallest sentence holding
    it: (position label, words, index of the keyword)."""
    contexts = _contexts()
    names = _name_like()
    found: dict[tuple[str, frozenset[str]], tuple[str, tuple[str, ...], int]] = {}
    for origin, expansions in sorted(_rules().items()):
        if origin not in contexts:
            continue
        left, right = contexts[origin]
        for expansion in expansions:
            for at, symbol in enumerate(expansion):
                if not _statically_open(origin, expansion, at):
                    continue
                heads = {symbol.name} if symbol.is_term else _first()[symbol.name]
                prefixes = [_seq(expansion[:at])]
                if at and not expansion[at - 1].is_term:
                    prefixes += [
                        _seq(expansion[: at - 1]) + tail
                        for tail in _endings()[expansion[at - 1].name].values()
                    ]
                for terminal in sorted(heads):
                    if not _spellings(terminal):
                        continue
                    sentence = _starting(symbol, terminal, frozenset())
                    assert sentence is not None
                    for prefix in prefixes:
                        terms = left + prefix + sentence + _seq(expansion[at + 1 :]) + right
                        index = len(left) + len(prefix)
                        words = tuple(_sample(t) for t in terms)
                        offset = len(" ".join(words[:index])) + (1 if index else 0)
                        expected = _expected_at(" ".join(words), offset)
                        if terminal not in expected or not expected & names:
                            continue
                        for keyword in _spellings(terminal):
                            placed = words[:index] + (keyword,) + words[index + 1 :]
                            key = (keyword, expected)
                            if key not in found or len(placed) < len(found[key][1]):
                                found[key] = (f"{origin}.{at}", placed, index)
    return found


def _name_cells() -> list[NameCell]:
    cells: list[NameCell] = []
    labels: dict[str, int] = defaultdict(int)
    for (keyword, _expected), (position, words, at) in sorted(
        _positions_a_name_competes_at().items(), key=lambda kv: (kv[0][0], kv[1][0], kv[1][1])
    ):
        labels[f"{keyword}-{position}"] += 1
        label = f"{position}~{labels[f'{keyword}-{position}']}"
        for kind in _SLIP_KINDS:
            slip = _slipped(keyword, kind)
            if slip is not None:
                cells.append(NameCell(keyword, label, words, at, kind, slip))
    return cells


# A clean game the grid's sentences are told inside: a top-level item is
# written before it, a game's item inside it.
_CLEAN_HOST = """game host {
  players: 2
  max_length: 10
  cards: standard52
  zones {
    deck : Deck
    hand[player] : Hand<player>
  }
  state {
    points[player] : Integer = 0
  }
  phase play {
    deal 1 cards from deck to each hand
  }
  winner: highest points
}
"""


def _told_inside_a_clean_game(text: str, at: int) -> tuple[str, int]:
    opener = "game x { "
    if text.startswith(opener) and text.endswith(" }"):
        head = _CLEAN_HOST.index("{") + 1
        body = text[len(opener) : -2]
        return _CLEAN_HOST[:head] + "\n" + body + _CLEAN_HOST[head:], at - len(opener) + head + 1
    return text + "\n" + _CLEAN_HOST, at


def _assert_offered_at(start: str, text: str, at: int, slip: str, meant: str) -> Diagnostic:
    """The parse refusal stands on the slip at `at`, offers `meant`, and every
    keyword it offers gets the file past it."""
    refused = _refusal(start, text)
    assert refused is not None, "the slip parses"
    assert refused.span is not None and refused.span.start == at, refused.format()
    assert meant in refused.near_misses, refused.format()
    assert refused.format().endswith("?") and "did you mean " in refused.format(), refused.format()
    assert refused.code is Code.MISSPELLED_KEYWORD, refused.format()
    for offer in refused.near_misses:
        fixed = text[:at] + offer + text[at + len(slip) :]
        later = _refusal(start, fixed)
        assert later is None or (later.span is not None and later.span.start > at), (
            f"offering `{offer}` does not get past the refusal: {later.format() if later else ''}"
        )
    return refused


# The codes the unresolved-name refusal tells.
_NAME_REFUSALS = (Code.UNKNOWN_NAME, Code.MISSPELLED_KEYWORD)


def _refusals(game: str) -> tuple[Diagnostic, ...]:
    try:
        check_dsl(game, "probe.cardlang")
    except DiagnosticError as refused:
        return tuple(told.diagnostic for told in refused.told)
    return ()


def _standing(game: str, offset: int) -> list[Diagnostic]:
    return [d for d in _refusals(game) if d.span is not None and d.span.start == offset]


def _assert_told_the_keyword(text: str, at: int, slip: str, meant: str) -> Diagnostic:
    """A refusal standing on the slip, in a game whose other refusals are
    elsewhere, offers `meant`; every keyword it offers, written in the slip's
    place, gives text that parses; and the unresolved-name refusal is told as
    a misspelled keyword where a keyword is its first offer."""
    game, offset = _told_inside_a_clean_game(text, at)
    assert game[offset : offset + len(slip)] == slip
    standing = _standing(game, offset)
    assert standing, f"no refusal stands on `{slip}`: {_refusals(game)}"
    offering = [d for d in standing if meant in d.near_misses]
    assert offering, "; ".join(d.format() for d in standing)
    told = offering[0]
    keywords = _all_spellings()
    for offer in told.near_misses:
        if offer in keywords:
            fixed = game[:offset] + offer + game[offset + len(slip) :]
            assert _refusal("start", fixed) is None, offer
            unread = [d for d in _standing(fixed, offset) if d.code in _NAME_REFUSALS]
            assert not unread, f"`{offer}` is read as a name: {unread[0].format()}"
    if told.code in _NAME_REFUSALS:
        expected = Code.MISSPELLED_KEYWORD if told.near_misses[0] in keywords else Code.UNKNOWN_NAME
        assert told.code is expected, told.format()
    return told


NAME_CELLS = _name_cells()

_QUERY_NOUN = "issue #TBD-keyword: a query noun's refusal stands on its query, not on the noun"
_AFTER_A_RANKING = (
    "issue #TBD-keyword: a word after a ranking list is read as one more rank, "
    "refused at the clause, not at the word"
)
# The positions whose refusal another site of the checker tells, by keyword
# and position.
_TOLD_ELSEWHERE: dict[tuple[str, str], str] = {
    **{
        (noun, "quantifier.1~1"): _QUERY_NOUN
        for noun in ("player", "players", "rank", "ranks", "suit", "suits", "team", "teams")
    },
    ("else", "card_points_table.3~1"): (
        "issue #TBD-keyword: a card_points key is refused as an unknown rank, "
        "which offers no keyword"
    ),
    ("suit", "__game_star_4.1~1"): _AFTER_A_RANKING,
    ("suit", "__game_star_4.1~2"): _AFTER_A_RANKING,
    ("uses", "__game_star_4.1~1"): _AFTER_A_RANKING,
    ("uses", "__game_star_4.1~2"): _AFTER_A_RANKING,
}


def _name_cell_param(cell: NameCell) -> object:
    reason = _TOLD_ELSEWHERE.get((cell.keyword, cell.position))
    marks = [pytest.mark.xfail(strict=True, raises=AssertionError, reason=reason)] if reason else []
    return pytest.param(cell, id=f"{cell.keyword}-{cell.position}-{cell.kind}", marks=marks)


def test_every_position_told_elsewhere_is_a_cell() -> None:
    """A renamed position leaves no mark on a cell that no longer exists.
    red under: renaming a key of `_TOLD_ELSEWHERE`."""
    cells = {(c.keyword, c.position) for c in NAME_CELLS}
    assert set(_TOLD_ELSEWHERE) <= cells, set(_TOLD_ELSEWHERE) - cells


def test_every_grid_keyword_competes_with_a_name_somewhere() -> None:
    """The derivation reaches the positions the issue's witnesses stand at.
    red under: dropping the repetition endings from `_statically_open`."""
    reached = {(c.keyword, c.position.split("~")[0]) for c in NAME_CELLS}
    for keyword in ("some", "all", "else", "jointly", "number", "sum"):
        assert any(k == keyword for k, _ in reached), keyword
    assert any(k == "else" and p.startswith("card_points_table") for k, p in reached)


@pytest.mark.parametrize("cell", [_name_cell_param(c) for c in NAME_CELLS])
def test_a_keyword_slip_read_as_a_name_is_offered_the_keyword(cell: NameCell) -> None:
    text, at = cell.text(cell.slip)
    if _refusal("start", cell.text(cell.keyword)[0]) is not None:
        pytest.fail(f"the unslipped sentence does not parse: {cell.text(cell.keyword)[0]!r}")
    if _refusal("start", text) is not None:
        _assert_offered_at("start", text, at, cell.slip, cell.keyword)
    else:
        _assert_told_the_keyword(text, at, cell.slip, cell.keyword)
