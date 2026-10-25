"""The retired `trick_order { }` block and game-level `trump:` clause.

The grid of issue #944, authored red before the cut: the block and the clause
leave the grammar, and every spelling of them a designer would write meets a
retired-spelling twin naming what replaced it (the rulings on issues #921 and
#944).

Completeness ledger (decisions.md "Closed-domain completeness")
---------------------------------------------------------------
property:        no game text spells a Trick Order as a block or a fixed
                 trump as a game-level clause; each such spelling is refused
                 at its own line by a twin naming the replacement, and each
                 twin's fix, followed as written, checks clean.
domain:          the retired spellings: the block with each row set, the
                 colon, comma and assignment habits, the empty block, an
                 unknown key, `trump:` with a name, a number, a string,
                 `none`, an expression, the no-colon `trump spades` (the
                 round's own spelling, at game level), each written after
                 an explicit `ranking:` list and after `suit ranking:` as
                 well as after a convention; the twins' fixes applied; the
                 two spellings that stay bare syntax errors (a block whose
                 row expression is also broken, and `trump:` inside a phase,
                 which was never the language); the composed grammar's
                 game-item heads against the two unbounded name runs; the
                 type hints the Trick Order's answers carry; the library
                 trick round that reads a trump and states none.
registry:        the host: docs/games/spades.cardlang; the game-item heads:
                 the composed grammar (`cardlang.lark` and `diagnostics.lark`);
                 the unbounded runs: tests/test_game_clause_guards.py's
                 `_UNBOUNDED_RUN_TERMINALS`.
does not prove:  that every message earns its exact sentence: each cell reads
                 its refusal by needle.

Born red on 8bc479d8 (commit 3844f66c), strict-xfail: every twin cell, the
head-exclusion pin, the departure pin, the type hints and the round-clause
cell -- 34. Green at authoring, 7: the two never-one-mistake syntax errors and
the five fixes, which are sentences of the language as it stands. Every red
cell has flipped, so no mark remains.
"""

from __future__ import annotations

import re
from importlib import resources
from pathlib import Path

import pytest

from cardlang.ast import nodes as n
from cardlang.diagnostics import DiagnosticError
from cardlang.pipeline import check_dsl

SPADES = (Path(__file__).resolve().parent.parent / "docs" / "games" / "spades.cardlang").read_text()
ROUND = "winner highest_trump_or_led_suit trump spades"
BARE = "winner highest_trump_or_led_suit"
TOW = "winner highest_by_trick_order"
RANKS = "  ranking: A K Q J 10 9 8 7 6 5 4 3 2\n"
SUITS = "  suit ranking: spades hearts diamonds clubs\n"

T_ORDER = "a Trick Order is three functions, not a block"
T_TRUMP = "`trump:` is not a clause"


def _item(item: str, round_: str | None = None, *, after: str = "convention") -> str:
    """Spades with `item` written as a game item, after its ranking."""
    assert ROUND in SPADES and "  ranking: aces high\n" in SPADES
    head = {
        "convention": "  ranking: aces high\n",
        "ranks": RANKS,
        "suits": "  ranking: aces high\n" + SUITS,
    }[after]
    text = SPADES.replace("  ranking: aces high\n", head + "  " + item + "\n")
    return text.replace(ROUND, round_) if round_ is not None else text


def _diagnostics(source: str) -> str | None:
    try:
        check_dsl(source, "retired.cardlang")
    except DiagnosticError as exc:
        return "\n".join([exc.diagnostic.message, *(getattr(exc, "__notes__", []) or [])])
    return None


_RETIRED: list[tuple[str, str, str]] = [
    ("block-trump-row", _item("trick_order { trump: card.suit is spades }", TOW), T_ORDER),
    ("block-three-rows",
     _item("trick_order { trump: card.suit is spades  follow_class: card.suit  card_strength: rank_value(card) }", TOW),
     T_ORDER),
    ("block-colon", _item("trick_order: { trump: card.suit is spades }", TOW), T_ORDER),
    ("block-comma", _item("trick_order { trump: card.suit is spades, card_strength: rank_value(card) }", TOW), T_ORDER),
    ("block-trailing-comma", _item("trick_order { trump: card.suit is spades, }", TOW), T_ORDER),
    ("block-assign", _item("trick_order { trump = card.suit is spades }", TOW), T_ORDER),
    ("block-walrus-unknown-key", _item("trick_order { trumps := false }", TOW), T_ORDER),
    ("block-empty", _item("trick_order { }", TOW), T_ORDER),
    ("block-no-trump-row", _item("trick_order { card_strength: rank_value(card) }", TOW), T_ORDER),
    ("block-unknown-key", _item("trick_order { trumps: false }", TOW), T_ORDER),
    ("block-false", _item("trick_order { trump: false }", TOW), T_ORDER),
    ("block-after-ranks", _item("trick_order { trump: card.suit is spades }", TOW, after="ranks"), T_ORDER),
    ("block-after-suit-ranking", _item("trick_order { trump: card.suit is spades }", TOW, after="suits"), T_ORDER),
    ("trump-name", _item("trump: spades", BARE), T_TRUMP),
    ("trump-int", _item("trump: 3", BARE), T_TRUMP),
    ("trump-string", _item('trump: "spades"', BARE), T_TRUMP),
    ("trump-none", _item("trump: none", BARE), T_TRUMP),
    ("trump-unknown-suit", _item("trump: bogus", BARE), T_TRUMP),
    ("trump-no-colon", _item("trump spades", BARE), T_TRUMP),
    ("trump-expr", _item("trump: card.suit is spades", BARE), T_TRUMP),
    ("trump-beside-round", _item("trump: spades"), T_TRUMP),
    ("trump-hearts", _item("trump: hearts", BARE), T_TRUMP),
    ("trump-state-var", _item("trump: trump_suit", BARE), T_TRUMP),
    ("trump-after-ranks", _item("trump: spades", BARE, after="ranks"), T_TRUMP),
    ("trump-no-colon-after-ranks", _item("trump spades", BARE, after="ranks"), T_TRUMP),
    ("trump-after-suit-ranking", _item("trump: spades", BARE, after="suits"), T_TRUMP),
    ("trump-no-colon-after-suit-ranking", _item("trump spades", BARE, after="suits"), T_TRUMP),
    ("trump-beside-is_trump",
     _item("trump: spades", TOW) + "\nfunction is_trump(card : Card) = card.suit is hearts\n",
     T_TRUMP),
]


@pytest.mark.parametrize(
    ("label", "source", "needle"), _RETIRED, ids=[x[0] for x in _RETIRED]
)
def test_a_retired_spelling_meets_its_twin(label: str, source: str, needle: str) -> None:
    found = _diagnostics(source)
    assert found is not None, "the retired spelling checked clean"
    assert needle in found, found
    assert "syntax error" not in found, found


@pytest.mark.parametrize(
    "source",
    [
        _item("trick_order { trump: card.suit is }", TOW),
        SPADES.replace("      active_rules: [MustFollowSuit]\n", "      trump: spades\n      active_rules: [MustFollowSuit]\n").replace(ROUND, BARE),
    ],
    ids=["block-with-a-broken-row", "trump-inside-a-phase"],
)
def test_a_spelling_that_was_never_one_mistake_stays_a_syntax_error(source: str) -> None:
    """Two mistakes at once, and a phase-level clause that was never the
    language, die at the token the parser stops on."""
    found = _diagnostics(source)
    assert found is not None and "syntax error" in found, found


_FIXES: list[tuple[str, str]] = [
    ("round-trump", SPADES),
    ("is_trump-with-the-trick-order-winner",
     SPADES.replace(ROUND, TOW) + "\nfunction is_trump(card : Card) = card.suit is spades\n"),
    ("three-functions",
     SPADES.replace(ROUND, TOW)
     + "\nfunction is_trump(card : Card) = card.suit is spades\n"
     "function follow_class(card : Card) = card.suit\n"
     "function card_strength(card : Card) = rank_value(card)\n"),
    ("no-trumps", SPADES.replace(ROUND, TOW) + "\nfunction is_trump(card : Card) = false\n"),
    ("pasted-row-body",
     SPADES.replace(ROUND, TOW) + "\nfunction is_trump(card : Card) = card.suit is spades and card.rank is not A\n"),
]


@pytest.mark.parametrize(("label", "source"), _FIXES, ids=[x[0] for x in _FIXES])
def test_a_twins_fix_checks_clean(label: str, source: str) -> None:
    assert _diagnostics(source) is None


def _grammar(name: str) -> str:
    return resources.files("cardlang.grammar").joinpath(name).read_text()


def _keyword_words(text: str) -> dict[str, str]:
    return {
        m.group(1): m.group(2)
        for m in re.finditer(r'^(_[A-Z0-9_]+_KW):\s*"([^"]+)"', text, re.MULTILINE)
    }


def test_every_game_item_head_is_kept_out_of_the_unbounded_runs() -> None:
    """A word that heads a game item in the COMPOSED grammar, a retired
    spelling's twin included, is no rank or suit name, so `trump spades`
    written after a `ranking:` run is the twin's to refuse, not an unknown
    rank's.

    red under: drop `trump` from CARD_RANK_NAME's exclusion list."""
    main, diagnostics = _grammar("cardlang.lark"), _grammar("diagnostics.lark")
    words = _keyword_words(main) | _keyword_words(diagnostics)
    arms = re.findall(r"%extend game_item:(.*?)(?=\n%|\n\n|\Z)", diagnostics, re.DOTALL)
    heads = {
        words[kw]
        for arm in arms
        for kw in re.findall(r"(?:^|\|)\s*(_[A-Z0-9_]+_KW)", arm, re.MULTILINE)
    }
    assert {"trump", "trick_order"} <= heads, heads
    for terminal in ("CARD_RANK_NAME", "SUIT_RANKING_NAME"):
        match = re.search(rf"^{terminal}:\s*/\(\?!\(\?:([^)]+)\)", main, re.MULTILINE)
        assert match is not None
        assert heads <= set(match.group(1).split("|")), (terminal, heads)


def test_the_block_and_the_clause_left_the_language() -> None:
    """No production, node field or lowering keeps the retired spellings."""
    from dataclasses import fields
    from typing import get_args

    main = _grammar("cardlang.lark")
    assert not re.search(r"^trick_order:|^trick_order_row:|^trump:|^TRICK_ORDER_KEY:", main, re.MULTILINE)
    assert "trump" not in {f.name for f in fields(n.Game)}
    assert get_args(n.LoweredForm) == ("card_points_table",)


_HINTS: list[tuple[str, str, str]] = [
    ("is_trump-returns-a-suit",
     "function is_trump(card : Card) = card.suit",
     "for a fixed trump suit write `function is_trump(card : Card) = card.suit is clubs`"),
    ("is_trump-is-optional",
     "function is_trump(card : Card) = if card.rank is A then true else none",
     "never absent-valued"),
    ("follow_class-is-a-string",
     'function is_trump(card : Card) = false\nfunction follow_class(card : Card) = "hearts"',
     "a trump follows as a trump by `is_trump`"),
]


@pytest.mark.parametrize(("label", "defs", "needle"), _HINTS, ids=[x[0] for x in _HINTS])
def test_an_answer_of_the_wrong_type_is_told_its_fix(label: str, defs: str, needle: str) -> None:
    """The hints the Trick Order's answers carry, in the function voice."""
    found = _diagnostics(SPADES.replace(ROUND, TOW) + "\n" + defs + "\n")
    assert found is not None
    assert needle in found, found


def test_a_round_that_reads_a_trump_and_states_none_names_the_round_clause() -> None:
    """With no game-level clause to inherit, a round whose winner reads a trump
    states it on the round, and the refusal says so and offers no clause."""
    found = _diagnostics(SPADES.replace(ROUND, BARE))
    assert found is not None
    assert "reads a trump, but none is stated" in found, found
    assert "`trump: <suit>`" not in found, found
