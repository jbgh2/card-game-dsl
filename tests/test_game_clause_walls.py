"""Game-clause structural walls: omission and duplication over the whole
clause domain of the `game` production, plus the content-clause axis
(`cards:` / `pieces:` — which component set a game plays with).

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
            multiple `game { }` blocks, a `direction:` outside its value
            set, or a content clause whose name is unknown or of the wrong
            flavor — fails `check_dsl` with a located `DiagnosticError`,
            never a bare assert / raw lark error / silently different
            meaning.
domain:     the `?game_item` alternatives of the `game` production, times
            {omitted, duplicated}; plus the game-count axis of `start`
            (zero / one / many); plus the `direction:` value axis; plus the
            content-clause axis — clause presence {cards only, pieces only,
            both, neither} at parse, times name flavor {card deck, piece
            set, unknown} at resolve.
registry:   `cardlang/grammar/cardlang.lark` (`?game_item`) — scraped here
            by `_game_item_alternatives`, so a clause added to the grammar
            fails `test_game_item_registry_pin` until it is classified
            below; `GAME_DIRECTIONS` in `cardlang/runtime/values.py` for
            the direction value set; `COMPONENT_SETS` (same module, the
            `flavor` column) for the content-clause name axis.
covered:    duplication — exhaustively, every single-valued clause (all
            alternatives except `phase`), one probe each, parse-layer wall
            (the `pieces` probe doubles as the pieces-duplicated-beside-
            `cards:` cell: BASE carries `cards:`, and the duplicate wall
            deterministically fires before the mutual-exclusion wall);
            omission — `players:`/content clause (parse wall, including the
            both-at-once bag rendering), `max_length:` and joint
            `winner:`/`loser:` (resolve walls, pinned by their own
            rejection fixtures), `state`/`zones`/`trump`/`partnerships`/
            `direction`/`ranking` omission is legal by design (probed by
            the valid BASE game here, which omits four of them);
            game-count — zero and two, parse wall;
            content clause — both-present (parse wall), each cell of the
            clause x name-flavor matrix at resolve: cross-flavor names
            rejected with the right clause named, unknown names listed
            against the clause's own flavor only (both directions probed),
            and the pieces-only acceptance cell (PIECE_BASE compiles end to
            end through IR, with the parse-stamped `content_flavor` and the
            piece-only IR key pinned).
sampled:    `ranking:` omission with rank-dependent constructs in play is
            typecheck's `has_ranking` gate (tests/test_ranking_wall.py);
            zero-`phase` games are accepted with defined degenerate
            semantics (no decisions; result read from initial state —
            verified by playout while authoring this module, not pinned
            here: the cell is "accepted", and pinning acceptance is the
            valid-BASE probe's job); both-content-clauses co-reporting with
            a missing `players:` rides the same bag the neither-present
            probe pins, not a separate probe; a Suit-parameterized rule in
            a piece game skips only the suit-membership refinement
            (resolve's `_instantiate_rules`, `suits=None`) — the argument
            name itself still fails name classification in a piece game's
            namespaces, so the cell stays loud.
residual:   `ranking:` (enumeration or convention) DECLARED in a piece
            game: membership validation and convention expansion are gated
            on `_deck_known`, which piece flavor deliberately fails, so the
            clause is currently accepted unvalidated (an enumeration flows
            through unchecked; a convention stays unexpanded). The flavor
            wall lands with the piece noun/flavor semantics — recorded in
            roadmap.md, "Piece-flavored games". Same record covers the
            runtime driver (a piece game compiles to IR but does not run).
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

import cardlang
from cardlang.diagnostics import DiagnosticError
from cardlang.ir import emit
from cardlang.parse import parse_text
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
    "pieces": "pieces:",
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
    # BASE carries `cards:`, so this probe doubles as the pieces-duplicated-
    # beside-cards cell: `once()` raises before the mutual-exclusion wall.
    "pieces": "  pieces: xo_marks",
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


def test_game_item_registry_pin() -> None:
    """The domain this module quantifies over IS the grammar's clause list:
    a new `?game_item` alternative must be classified here (single-valued or
    repeatable) before it can land."""
    alternatives = _game_item_alternatives()
    assert alternatives == set(SINGLE_VALUED) | {"phase"}, (
        "the `game` production's clause list changed — classify the new "
        "clause in SINGLE_VALUED (or document it as repeatable like `phase`) "
        "and give it omission/duplication probes"
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


def test_missing_content_clause_names_both_spellings() -> None:
    """A game with neither content clause is told about both, so the fix is
    visible whichever flavor the designer meant."""
    text = BASE.replace("  cards: standard52\n", "")
    with pytest.raises(DiagnosticError) as exc:
        check_dsl(text, "probe.cardlang")
    assert "must declare `cards: <deck>` or `pieces: <set>`" in exc.value.diagnostic.message


def test_missing_players_and_cards_reports_both() -> None:
    """The bag-first idiom: a game missing both mandatory clauses hears
    about both in one failure (second as a note), not one per round-trip."""
    text = BASE.replace("  players: 2\n", "").replace("  cards: standard52\n", "")
    with pytest.raises(DiagnosticError) as exc:
        check_dsl(text, "probe.cardlang")
    assert "must declare `players: <n>`" in exc.value.diagnostic.message
    notes = getattr(exc.value, "__notes__", [])
    assert any(
        "must declare `cards: <deck>` or `pieces: <set>`" in note for note in notes
    )


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


# --- the content-clause axis: `cards:` / `pieces:` -------------------------
# Rejection-corpus twins of these probes: tests/rejections/
# {pieces_and_cards_together, pieces_unknown_set, pieces_names_a_deck,
# cards_names_a_piece_set, duplicate_pieces_clause}.

# The piece mirror of BASE. Deliberately free of card-noun constructs
# (movements, card queries, ranking): the clause is live before the piece
# noun/flavor semantics, so this pins the surface that must already compile.
PIECE_BASE_LINES: tuple[str, ...] = (
    "game PieceProbe {",
    "  players: 2",
    "  pieces: xo_marks",
    "  max_length: 10",
    "  state { score[player] : Integer = 0 }",
    "  winner: highest score",
    "}",
)
PIECE_BASE = "\n".join(PIECE_BASE_LINES) + "\n"


def test_piece_probe_is_accepted() -> None:
    check_dsl(PIECE_BASE, "piece.cardlang")


def test_content_flavor_stamped_from_clause() -> None:
    """`Game.content_flavor` records WHICH clause appeared — stamped at
    parse, the single source resolve's flavor walls dispatch on. `Game.deck`
    holds the selected set name for both flavors."""
    assert parse_text(BASE, "base.cardlang").content_flavor == "card"
    game = parse_text(PIECE_BASE, "piece.cardlang")
    assert game.content_flavor == "piece"
    assert game.deck == "xo_marks"


def test_both_content_clauses_rejected() -> None:
    """`cards:` and `pieces:` both select the game's one component set; a
    game declaring both is rejected at parse, pointing at the later clause."""
    text = BASE.replace("  max_length", "  pieces: xo_marks\n  max_length")
    with pytest.raises(DiagnosticError) as exc:
        check_dsl(text, "probe.cardlang")
    message = exc.value.diagnostic.message
    assert "a game declares `cards:` or `pieces:`, not both" in message
    span = exc.value.diagnostic.span
    assert span is not None and span.line == BASE_LINES.index("  max_length: 10") + 1


def test_cards_naming_a_piece_set_rejected() -> None:
    """A piece-flavored name under `cards:` gets the cross-flavor wall with
    the right clause named — never the unknown-deck list (the name IS
    known, just not a deck)."""
    text = BASE.replace("cards: standard52", "cards: xo_marks")
    with pytest.raises(DiagnosticError) as exc:
        check_dsl(text, "probe.cardlang")
    message = exc.value.diagnostic.message
    assert "'xo_marks' is a piece set" in message
    assert "`pieces: xo_marks`" in message


def test_pieces_naming_a_card_deck_rejected() -> None:
    text = PIECE_BASE.replace("pieces: xo_marks", "pieces: standard52")
    with pytest.raises(DiagnosticError) as exc:
        check_dsl(text, "probe.cardlang")
    message = exc.value.diagnostic.message
    assert "'standard52' is a card deck" in message
    assert "`cards: standard52`" in message


def test_unknown_piece_set_lists_piece_sets_only() -> None:
    """The unknown-name diagnostic lists the sets of the CLAUSE'S flavor: a
    designer who wrote `pieces:` is choosing among piece sets, and the deck
    list would be noise."""
    text = PIECE_BASE.replace("pieces: xo_marks", "pieces: chess_men")
    with pytest.raises(DiagnosticError) as exc:
        check_dsl(text, "probe.cardlang")
    message = exc.value.diagnostic.message
    assert "unknown piece set 'chess_men'" in message
    assert "xo_marks" in message
    assert "standard52" not in message


def test_unknown_deck_lists_card_decks_only() -> None:
    """The card-side twin: the pre-`pieces:` message survives verbatim, and
    the piece sets never leak into its list."""
    text = BASE.replace("cards: standard52", "cards: nosuch99")
    with pytest.raises(DiagnosticError) as exc:
        check_dsl(text, "probe.cardlang")
    message = exc.value.diagnostic.message
    assert "unknown deck 'nosuch99'" in message
    assert "standard52" in message
    assert "xo_marks" not in message


def test_content_flavor_in_ir_only_for_piece_games() -> None:
    """The IR keys `content_flavor` only when it is "piece": the card-game
    IR predates the field and its goldens are byte-stable, so an absent key
    means "card". The deck key carries the selected set name for both
    flavors, unchanged."""
    card_ir = emit(check_dsl(BASE, "base.cardlang"))
    assert "content_flavor" not in card_ir
    assert card_ir["deck"] == "standard52"
    piece_ir = emit(check_dsl(PIECE_BASE, "piece.cardlang"))
    assert piece_ir["content_flavor"] == "piece"
    assert piece_ir["deck"] == "xo_marks"
