"""A misspelled keyword is refused at the word, and told the keywords it nearly spells.

A designer who writes `shufle deck` for `shuffle deck` slipped on the word that
begins the statement. Where the grammar also takes a name there, the parser
reads the slip as one and fails on the word after it; where it does not, it
fails on the slip itself. Either way the refusal stands on the word the
designer wrote and offers, as Near Misses (docs/glossary/near-miss.md), the
keywords the grammar accepts there that the word nearly spells and that get
the file past the refusal.

Completeness ledger (decisions.md "Closed-domain completeness")
---------------------------------------------------------------
property:        a word written at the head of a block's item, where the
                 grammar accepts a keyword it nearly spells, is refused with
                 its span on that word and its Near Misses carried as data
                 (`Diagnostic.near_misses`) and rendered as the one `did you
                 mean` clause; every keyword offered, written in the word's
                 place, gets the file past that refusal; a word whose
                 keyword reading does not get the file past the refusal is
                 offered nothing, and the parser's own expectation stands.
domain:          every block item position -- each element of a repetition in
                 the compiled grammar whose first words include a keyword --
                 crossed with every keyword spelling that may begin an item
                 there, each item written as the grammar's shortest sentence
                 beginning with that keyword, inside the smallest text holding
                 the position (`HOSTS`). Lark compiles every `statement*` into
                 one repetition, so every statement list is one row. Beside
                 the grid, the misuse probes: the keywords that continue the
                 item before the slip (an `else`, a round's `trump`, an
                 operator word), a single-statement slot, the clause heads of
                 one production's fixed sequence (a move type's `when:` and
                 `effect`, a round's `over`), and the slips that must be
                 offered nothing. A misspelled keyword the grammar reads as
                 a name and DERIVES (`deal som cards`, `els: 2` in
                 `card_points`) raises no syntax error, and is the pass's that
                 refuses the name it reads as (tests/test_near_misses.py).
registry:        positions: `_positions` over `cardlang.parse._parser().rules`
                 (the repetition helpers' elements and their first-word
                 sets); spellings: `cardlang.parse._designer_word`; hosts:
                 `HOSTS` against `_positions`; the measure and the clause:
                 tests/test_near_misses.py::test_the_parse_layer_ranks_by_the_one_measure.
held by:         Derived and Pinned. A refusal's offer is data on one
                 `Diagnostic` built at one site (`cardlang.parse._syntax_error`),
                 but which words a position takes is the grammar's, read off
                 the compiled rules at failure time, and no type can hold it.
does not prove:  that every keyword position inside a production's fixed
                 sequence or an expression is offered, which the probes
                 sample and the grid does not enumerate.
"""

from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass
from functools import cache
from pathlib import Path

import pytest
from lark.grammar import NonTerminal, Symbol, Terminal

from cardlang import parse
from cardlang.diagnostics import Diagnostic, DiagnosticError
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
    """The refusal stands on `slip`, offers `meant`, and every keyword it
    offers gets the file past it."""
    at = text.index(slip)
    refused = _refusal(start, text)
    assert refused is not None, "the slip parses"
    assert refused.span is not None and refused.span.start == at, refused.format()
    assert meant in refused.near_misses, refused.format()
    assert refused.format().endswith("?") and "did you mean " in refused.format(), refused.format()
    for offer in refused.near_misses:
        fixed = text[:at] + offer + text[at + len(slip) :]
        later = _refusal(start, fixed)
        assert later is None or (later.span is not None and later.span.start > at), (
            f"offering `{offer}` does not get past the refusal: {later.format() if later else ''}"
        )
    return refused


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


@pytest.mark.xfail(
    strict=True,
    raises=AssertionError,
    reason="issue #1079: a slip two words before the parse failure is not considered",
)
def test_a_slip_two_words_before_the_failure_is_offered() -> None:
    _assert_offered("start", _GAME.replace(_HOLE, "let n = al players where x"), "al", "all")


@pytest.mark.xfail(
    strict=True,
    raises=AssertionError,
    reason="issue #1079: a slip the grammar derives as a name is refused as an unknown name",
)
def test_a_slip_the_grammar_derives_as_a_name_is_offered_the_keyword() -> None:
    text = (_ROOT / "docs/games/hearts.cardlang").read_text()
    assert "deal 13 cards" in text
    with pytest.raises(DiagnosticError) as refused:
        check_dsl(text.replace("deal 13 cards", "deal som cards", 1), "hearts.cardlang")
    assert "some" in refused.value.diagnostic.near_misses, refused.value.diagnostic.format()
