"""Game-clause structural walls: omission and duplication over the whole
clause domain of the `game` production.

Seeded by the fuzz finding `missing_cards_declaration` (a missing `cards:`
escaping `check_dsl` as a raw lark ``VisitError`` around a bare assert) and
swept per decisions.md "Closed-domain completeness": the fuzzer proved two
cells (`players:`/`cards:` omission); the class is every clause of the
`game` production, on both the omission and the duplication axis, plus the
game-count cells of `start` itself.

Completeness ledger (decisions.md "Closed-domain completeness")
---------------------------------------------------------------
property:   a structurally invalid game skeleton — a mandatory clause
            omitted, a single-valued clause repeated, a source with zero or
            multiple `game { }` blocks, or a `direction:` outside its value
            set — fails `check_dsl` with a located `DiagnosticError`, never
            a bare assert / raw lark error / silently different meaning.
domain:     the `?game_item` alternatives of the `game` production, times
            {omitted, duplicated}; plus the game-count axis of `start`
            (zero / one / many); plus the `direction:` value axis.
registry:   `cardlang/grammar/cardlang.lark` (`?game_item`) — scraped here
            by `_game_item_alternatives`, so a clause added to the grammar
            fails `test_game_item_registry_pin` until it is classified
            below; `GAME_DIRECTIONS` in `cardlang/runtime/values.py` for
            the direction value set.
covered:    duplication — exhaustively, every single-valued clause (all
            alternatives except `phase`), one probe each, parse-layer wall;
            omission — `players:`/`cards:` (parse wall, including the
            both-at-once bag rendering), `max_length:` and joint
            `winner:`/`loser:` (resolve walls, pinned by their own
            rejection fixtures), `state`/`zones`/`trump`/`partnerships`/
            `direction`/`ranking` omission is legal by design (probed by
            the valid BASE game here, which omits four of them);
            game-count — zero and two, parse wall.
sampled:    `ranking:` omission with rank-dependent constructs in play is
            typecheck's `has_ranking` gate (tests/test_ranking_wall.py);
            zero-`phase` games are accepted with defined degenerate
            semantics (no decisions; result read from initial state —
            verified by playout while authoring this module, not pinned
            here: the cell is "accepted", and pinning acceptance is the
            valid-BASE probe's job).
residual:   none — every cell above is either walled or legal-by-design.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

import cardlang
from cardlang.diagnostics import DiagnosticError
from cardlang.pipeline import check_dsl

GRAMMAR = (
    Path(cardlang.__file__).resolve().parent / "grammar" / "cardlang.lark"
).read_text()


def _game_item_alternatives() -> set[str]:
    """Scrape the `?game_item:` alternatives — the clause registry this
    module's domain derives from (never hand-enumerate what a registry
    already defines)."""
    match = re.search(
        r"^\?game_item:\s*(\w+)((?:\s*\n\s*\|\s*\w+)*)", GRAMMAR, re.MULTILINE
    )
    assert match is not None, "grammar lost its `?game_item` production"
    names = {match.group(1)}
    names.update(re.findall(r"\|\s*(\w+)", match.group(2)))
    return names


# grammar rule name -> the clause spelling the duplicate diagnostic names.
# `phase` is the one legitimately repeatable clause and is deliberately
# absent; `test_game_item_registry_pin` forces this mapping to be revisited
# whenever the grammar grows a clause.
SINGLE_VALUED: dict[str, str] = {
    "players": "players:",
    "direction": "direction:",
    "cards": "cards:",
    "ranking": "ranking:",
    "trump": "trump:",
    "partnerships": "partnerships:",
    "max_length": "max_length:",
    "positions": "positions { }",
    "zones": "zones { }",
    "state_block": "state { }",
    "winner": "winner:",
    "loser": "loser:",
}

# A minimal valid game (also the acceptance probe: it omits `direction:`,
# `ranking:`, `trump:`, and `partnerships:`, pinning that those omissions
# are legal). Duplication probes are built by line surgery on it.
BASE_LINES: tuple[str, ...] = (
    "game Probe {",
    "  players: 2",
    "  cards: standard52",
    "  max_length: 10",
    "  zones { deck : Deck  hand[player] : Hand<player> }",
    "  state { score[player] : Integer = 0 }",
    "  phase play {",
    "    deal 3 cards from deck to each hand",
    "  }",
    "  winner: highest score",
    "}",
)
BASE = "\n".join(BASE_LINES) + "\n"

# grammar rule name -> a clause line (or block) valid enough to parse, for
# clauses BASE does not already carry. The duplicate wall fires at parse
# time, before resolve, so these only need to be grammatical.
_EXTRA_CLAUSE: dict[str, str] = {
    "positions": "  positions { column : 1..3 }",
    "direction": "  direction: clockwise",
    "ranking": "  ranking: A K Q J 10 9 8 7 6 5 4 3 2",
    "trump": "  trump: spades",
    "partnerships": "  partnerships: [[0, 1]]",
    "loser": "  loser: active",
}


def _duplicate_probe(rule_name: str) -> str:
    """BASE with the named clause appearing twice."""
    if rule_name in _EXTRA_CLAUSE:
        line = _EXTRA_CLAUSE[rule_name]
        return BASE.replace("  max_length: 10", f"{line}\n{line}\n  max_length: 10")
    marker = {
        "players": "  players: 2",
        "cards": "  cards: standard52",
        "max_length": "  max_length: 10",
        "zones": "  zones { deck : Deck  hand[player] : Hand<player> }",
        "state_block": "  state { score[player] : Integer = 0 }",
        "winner": "  winner: highest score",
    }[rule_name]
    return BASE.replace(f"{marker}\n", f"{marker}\n{marker}\n")


# The clauses a game may legitimately write MORE THAN ONCE, each with the reason
# and with where its own repeat-abuse wall lives — a clause is not exempt from
# duplication checking just by being here, it is checked somewhere else.
#
#   phase      — a game is a sequence of phases; repetition IS the construct.
#   uses_decl  — a game uses as many family libraries as it draws on
#                (decisions.md "Family libraries"). Repeating the SAME library is
#                still a defect, and is walled in `resolve._apply_uses`, not in
#                parse: only resolve knows the library names.
REPEATABLE: dict[str, str] = {
    "phase": "a game is a sequence of phases",
    "uses_decl": "a game may use several libraries; the repeated-NAME wall is "
    "in resolve._apply_uses, which is the pass that knows library names",
}


def test_game_item_registry_pin() -> None:
    """The domain this module quantifies over IS the grammar's clause list:
    a new `?game_item` alternative must be classified here (single-valued or
    repeatable) before it can land."""
    alternatives = _game_item_alternatives()
    assert alternatives == set(SINGLE_VALUED) | set(REPEATABLE), (
        "the `game` production's clause list changed — classify the new "
        "clause in SINGLE_VALUED (or in REPEATABLE, with the reason and the "
        "location of its own repeat wall) and give it omission/duplication probes"
    )


def test_base_probe_is_accepted() -> None:
    check_dsl(BASE, "base.cardlang")


@pytest.mark.parametrize("rule_name", sorted(SINGLE_VALUED))
def test_duplicate_clause_rejected(rule_name: str) -> None:
    """Every single-valued clause, repeated, is rejected at the second
    occurrence — never silently last-wins (the parse.py `game()` wall,
    generalized from the old `state { }`-only check)."""
    with pytest.raises(DiagnosticError) as exc:
        check_dsl(_duplicate_probe(rule_name), "dup.cardlang")
    message = exc.value.diagnostic.message
    assert f"declares one `{SINGLE_VALUED[rule_name]}`" in message
    assert exc.value.diagnostic.span is not None


def test_missing_players_names_the_clause() -> None:
    text = BASE.replace("  players: 2\n", "")
    with pytest.raises(DiagnosticError) as exc:
        check_dsl(text, "probe.cardlang")
    assert "must declare `players: <n>`" in exc.value.diagnostic.message


def test_missing_cards_names_the_clause() -> None:
    text = BASE.replace("  cards: standard52\n", "")
    with pytest.raises(DiagnosticError) as exc:
        check_dsl(text, "probe.cardlang")
    assert "must declare `cards: <deck>`" in exc.value.diagnostic.message


def test_missing_players_and_cards_reports_both() -> None:
    """The bag-first idiom: a game missing both mandatory clauses hears
    about both in one failure (second as a note), not one per round-trip."""
    text = BASE.replace("  players: 2\n", "").replace("  cards: standard52\n", "")
    with pytest.raises(DiagnosticError) as exc:
        check_dsl(text, "probe.cardlang")
    assert "must declare `players: <n>`" in exc.value.diagnostic.message
    notes = getattr(exc.value, "__notes__", [])
    assert any("must declare `cards: <deck>`" in note for note in notes)


def test_no_game_block_rejected() -> None:
    """`start: top_item+` accepts a game-less source; it used to escape as
    a StopIteration inside lark's VisitError."""
    text = "rule nothing {\n  demands: actions where true\n}\n"
    with pytest.raises(DiagnosticError) as exc:
        check_dsl(text, "probe.cardlang")
    assert "declares no `game { }` block" in exc.value.diagnostic.message


def test_two_game_blocks_rejected_at_the_second() -> None:
    """A second game block used to be silently discarded (first-wins)."""
    text = BASE + BASE.replace("Probe", "Probe2")
    with pytest.raises(DiagnosticError) as exc:
        check_dsl(text, "probe.cardlang")
    assert "2 `game { }` blocks" in exc.value.diagnostic.message
    span = exc.value.diagnostic.span
    assert span is not None and span.line == len(BASE_LINES) + 1


@pytest.mark.parametrize("value", ["clockwise", "counterclockwise"])
def test_known_directions_accepted(value: str) -> None:
    text = BASE.replace("  max_length", f"  direction: {value}\n  max_length")
    check_dsl(text, "probe.cardlang")


def test_unknown_direction_rejected() -> None:
    """`direction: anticlockwise` used to be silently read as clockwise
    (driver.py's `!= "counterclockwise"` test) — the resolve wall names the
    value set instead."""
    text = BASE.replace("  max_length", "  direction: anticlockwise\n  max_length")
    with pytest.raises(DiagnosticError) as exc:
        check_dsl(text, "probe.cardlang")
    assert "unknown direction 'anticlockwise'" in exc.value.diagnostic.message
