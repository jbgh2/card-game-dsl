"""Surface-totality grid for the card-point table clause: `card_points { ... }`.

The second Merge Lane A change of issue #249 (epic #248). The operator ruling
(points 1 and 2), the per-PR counsel, and the framing-check enumeration live
on that issue; docs/decisions.md "Scoring composition" carries the settled
text this grid pins. The Builtin renames `card_value` -> `card_points` in the
same change, and the four populated deck tables migrate into their game files
(one source: `Deck` carries no point table).

Completeness ledger
--------------------
property:  every table the clause accepts loads as the game's card points —
           the `card_points(card)` Builtin and the driver's census sum read
           the same materialized table (rank rows verbatim, unlisted ranks at
           the `else:` value, or 0 with no else row) — and every plausible
           wrong sentence fails loud in its owning layer's currency: block
           shapes as parse-layer DiagnosticErrors (the wrong spellings
           `card_points:` and `card_values` naming the one block spelling),
           key mistakes as resolve diagnostics naming the deck, the clause in
           a piece game as the noun/content agreement rejection, and the
           Builtin called with no clause declared as a resolve diagnostic
           naming the clause.
domain:    clause presence x block shape (rows, else-row states, duplicates,
           the empty block) x key kind (NAME rank, INT rank, unknown,
           duplicate, `else`-adjacent spellings) x row value (positive, zero,
           negative, spaced sign, leading zeros, and the non-literal shapes)
           x deck flavor (card / piece) x host (game body; the clause is
           grammatically inexpressible in a library, a phase, or at top
           level) x consumers (the renamed Builtin through a played game; the
           census total; the four surviving Python point tables) x the rename
           axis (`card_points` resolves, `card_value` does not).
registry:  the clause axis derives from the grammar's `?game_item`
           alternation and the `card_points_table` production (scraped from
           cardlang.lark by test_clause_axes_are_pinned below); the key
           terminal's `else` exclusion from CARD_POINTS_KEY; the Builtin's
           home from BUILTIN_CALL_FUNCS / CALL_SIGS; the key-validity set
           from the deck registry via `rank_names`; the migration tables
           from the five game runtime modules' own dicts. The enumeration
           record is the framing-check comment on issue #249; the design
           record is the per-PR counsel comment there.
covered:   the executed parametrizations and probes in this module —
           test_value_grid (NAME/INT keys, positive/zero/negative/spaced/
           leading-zero values, sparse-unlisted-0, else-row default,
           full-table-with-inert-else), the census cells (sparse and
           else-materialized totals agreeing with the Builtin through the
           same played game), the resolve cells (duplicate key, unknown
           rank naming the deck, convention-word key, `elsex` whole-word
           key, the piece-game rejection, the clause-less call, the
           call-less clause accepted), the parse cells (colon and
           `card_values` reject-with-replacement, the duplicate-clause
           wall), the misuse syntax probes, the host cells (Team-param
           function summing over a team zone family; the library / phase /
           top-level impossibilities), the IR cells (conditional key), and
           the four migration agreement pins (gin, cribbage, canasta
           directly; tarot composed through its bout layer over the whole
           78-card pack).
sampled:   (a) expression host positions for the renamed Builtin (aggregation
           bodies, movement filters, move-type `when:` guards, let values):
           one Call node through one evaluator arm — the four migration
           games and the five retirement games exercise the live positions
           end to end under their byte-identical playout suites; the value
           grid here pins the arm itself. (b) clause absorption after a
           `ranking:` enumeration and by an empty expression slot: derived
           sweeps in tests/test_game_clause_guards.py cover every clause
           including this one (the absorbable-shape scrape widened in this
           change to see entry-plus blocks and non-NAME entry heads).
           (c) `else`-value-0 rows: the same load path as the else cells
           with the default coinciding with the no-else default.
           (d) keyword anchoring and fusion for `_CARD_POINTS_KW` /
           `_CARD_VALUES_KW`: the derived grid in
           tests/test_keyword_anchoring.py mints the rows mechanically;
           tests/keyword_fusion_sweep.py re-run by hand with the change.
residual:  (a) a state variable, zone, or local spelled `card_points`
           coexists with the clause and the Builtin (three namespaces, one
           spelling): mechanically legal today — Call.func and NameRef
           classification are separate channels — and deliberately left
           undecided rather than pinned as sanctioned; the corpus witness
           (schnapsen's `card_points[player]`) renames to `points_taken` in
           this change, so no game exercises the coexistence. R4,
           auditor-only, recorded here; guarding it is a naming-hygiene
           question, not a correctness one (the channels cannot cross).
           (b) `_PARSE_HINTS` has no entry for a game clause written in a
           phase body, so the misplaced-clause probes report bare syntax
           errors rather than a repair hint — pre-existing for every game
           clause, R4, recorded here.
           (c) the census `total_value` for the five retirement games rises
           from 0 to the declared table's sum (their decks carried no
           table before), and french-tarot's census prices bouts at the
           else value (158 for the 78-card pack, not the settlement's
           doubled 182) because the bout layer is deliberately inline at
           the call sites while `tarot_per_opp` owns the settlement — a
           domain fact of the census diagnostic, asserted by no golden,
           recorded here.
           (d) `card_value(card)` after the rename is an unknown-function
           resolve diagnostic (executed below) without a
           did-you-mean-card_points hint: the reject-with-replacement
           treatment is spent on the two wrong CLAUSE spellings the counsel
           names; a call-name hint mechanism would be new machinery. R4,
           recorded here.
naming:    `card_points` joins the glossary as its own entry (the concept
           "card points" previously lived only inside the reserved word
           "value"'s compound list, citing `Deck.values` — a referent this
           change retires); the entry and the updated compound land in the
           same change. The clause keyword, the Builtin name, and the
           runtime field `rs.card_points` share the one spelling; the
           grammar rule is `card_points_table` (the card-point table, the
           phrase the corpus modules already use).
"""

from __future__ import annotations

import json
import random
from importlib import resources
from pathlib import Path
from typing import Any

import pytest

from cardlang import ir
from cardlang.ast import nodes as n
from cardlang.diagnostics import DiagnosticError
from cardlang.pipeline import check_dsl
from cardlang.runtime.driver import play_game

GAMES = Path(__file__).parent.parent / "docs" / "games"

# --- the shared minimal game shells ------------------------------------------


def _game(points: str, body: str = "s[0] := 0", deck: str = "standard52") -> str:
    return f"""
game Mini {{
  players: 2
  max_length: 1000
  cards: {deck}
  ranking: aces low
  {points}
  zones {{ deck : Deck  hand[player] : Hand<player> }}
  state {{ s[player] : Integer = 0 }}
  phase p {{
    {body}
  }}
  winner: highest s
}}
"""


def _accepts(src: str) -> n.Game:
    return check_dsl(src, "mini.cardlang")


def _rejects(src: str, needle: str) -> None:
    with pytest.raises(DiagnosticError) as ei:
        check_dsl(src, "mini.cardlang")
    assert needle in str(ei.value), str(ei.value)


def _scores(src: str) -> dict[int, int]:
    return play_game(check_dsl(src, "mini.cardlang"), random.Random(0)).scores


def _census(src: str) -> dict[str, int]:
    captured: dict[str, int] = {}

    def tracer(event: str, data: Any) -> None:
        if event == "game_end":
            captured.update(data)

    play_game(check_dsl(src, "mini.cardlang"), random.Random(0), tracer=tracer)
    return captured


# =============================================================================
# The clause-axis pin — grammar, key terminal, and the Builtin's home agree
# =============================================================================


def test_clause_axes_are_pinned_by_grammar_and_registries() -> None:
    """The clause axis derives from the grammar (the `card_points_table`
    production on `?game_item`, its entry-plus block shape, and the key
    terminal's whole-word `else` exclusion) and the call axis from the
    Builtin registries — reconciled here so the parametrizations below
    cannot drift past either source."""
    from cardlang.builtins.functions import BUILTIN_CALL_FUNCS, DECK_ONLY_CALL_FUNCS
    from cardlang.builtins.signatures import CALL_SIGS

    grammar = resources.files("cardlang.grammar").joinpath("cardlang.lark").read_text()
    assert "card_points_table" in grammar
    assert "card_points_entry+" in grammar  # entry-plus: the empty block is a syntax error
    assert "CARD_POINTS_KEY" in grammar
    key_terminal = next(
        line for line in grammar.splitlines() if line.startswith("CARD_POINTS_KEY")
    )
    assert "else" in key_terminal  # the else row cannot be shadowed by a rank key
    assert "card_points" in BUILTIN_CALL_FUNCS
    assert "card_value" not in BUILTIN_CALL_FUNCS
    assert "card_points" in DECK_ONLY_CALL_FUNCS
    assert "card_value" not in DECK_ONLY_CALL_FUNCS
    assert "card_points" in CALL_SIGS and "card_value" not in CALL_SIGS


# =============================================================================
# The value grid — the Builtin reads the declared table, through played games
# =============================================================================

# (table, probe card literal, expected points). Expected values are design
# decisions authored before the implementation existed: rank rows verbatim,
# unlisted ranks read the else value, or 0 with no else row.
VALUE_CELLS: list[tuple[str, str, str, int]] = [
    ("name-key", "card_points { A: 1  K: 10 }", "A of spades", 1),
    ("int-key", "card_points { 10: 7 }", "10 of hearts", 7),
    ("zero-row", "card_points { 9: 0  A: 11 }", "9 of clubs", 0),
    ("negative-row", "card_points { A: -25 }", "A of spades", -25),
    ("spaced-negative", "card_points { A: - 25 }", "A of spades", -25),
    ("leading-zero-value", "card_points { A: 007 }", "A of spades", 7),
    ("sparse-unlisted-reads-0", "card_points { A: 1 }", "2 of clubs", 0),
    ("else-row-default", "card_points { K: 9  else: 2 }", "5 of hearts", 2),
    ("else-listed-rank-wins", "card_points { K: 9  else: 2 }", "K of hearts", 9),
    ("full-table-inert-else", "card_points { A: 1  2: 2  3: 3  4: 4  5: 5  6: 6  7: 7  8: 8  9: 9  10: 10  J: 10  Q: 10  K: 10  else: 99 }", "Q of clubs", 10),
]


@pytest.mark.parametrize(
    ("case_id", "table", "literal", "expected"),
    VALUE_CELLS,
    ids=[c[0] for c in VALUE_CELLS],
)
def test_value_grid(case_id: str, table: str, literal: str, expected: int) -> None:
    src = _game(table, body=f"s[0] := card_points({literal})")
    assert _scores(src)[0] == expected


# =============================================================================
# The census — the driver's deck-integrity sum reads the same table
# =============================================================================


def test_census_total_reads_the_sparse_table() -> None:
    # standard52: four aces at 1, everything else unlisted -> 0.
    assert _census(_game("card_points { A: 1 }"))["total_value"] == 4


def test_census_total_materializes_the_else_row() -> None:
    # Four aces at 1, the other 48 cards at the else value 2 — the census and
    # the Builtin read ONE materialized table, so the else row cannot diverge
    # between the two consumers.
    src = _game(
        "card_points { A: 1  else: 2 }",
        body="s[0] := card_points(2 of spades)",
    )
    assert _census(src)["total_value"] == 4 * 1 + 48 * 2
    assert _scores(src)[0] == 2


def test_census_total_is_zero_with_no_clause() -> None:
    # A game declaring no card points keeps the pre-change census: 0.
    assert _census(_game(""))["total_value"] == 0


# =============================================================================
# Resolve — key validity, the flavor guard, and the clause-required call
# =============================================================================


def test_duplicate_key_is_a_resolve_diagnostic() -> None:
    _rejects(_game("card_points { Q: 10  Q: 10 }"), "repeats rank")


def test_unknown_rank_names_the_deck() -> None:
    src = _game("card_points { ace: 1 }")
    with pytest.raises(DiagnosticError) as ei:
        check_dsl(src, "mini.cardlang")
    message = str(ei.value)
    assert "ace" in message and "standard52" in message, message


def test_convention_word_key_is_an_unknown_rank() -> None:
    # `aces: 1` — the ranking-position convention reservation does not apply
    # in the table's key position; the word is an ordinary unknown rank.
    _rejects(_game("card_points { aces: 1 }"), "aces")


def test_elsex_is_a_name_key_not_an_else_row() -> None:
    # The key terminal's `else` exclusion is whole-word: `elsex` lexes as a
    # NAME key and fails as an unknown rank, never as a malformed else row.
    _rejects(_game("card_points { elsex: 1 }"), "elsex")


def test_clause_in_a_piece_game_is_rejected_naming_the_kind() -> None:
    src = """
game PieceProbe {
  players: 2
  pieces: xo_marks
  card_points { A: 1 }
  max_length: 10
  state { score[player] : Integer = 0 }
  winner: highest score
}
"""
    with pytest.raises(DiagnosticError) as ei:
        check_dsl(src, "piece.cardlang")
    message = str(ei.value)
    assert "declares pieces" in message and "card_points" in message, message


def test_call_with_no_clause_is_a_resolve_diagnostic() -> None:
    # Without the clause there is no table to read: the one-source design
    # deletes the deck fallback, so a clause-less call would silently price
    # every card 0 — refused at resolve, naming the clause.
    src = _game("", body="s[0] := card_points(A of spades)")
    with pytest.raises(DiagnosticError) as ei:
        check_dsl(src, "mini.cardlang")
    message = str(ei.value)
    assert "card_points" in message and "clause" in message, message


def test_clause_with_no_call_is_accepted() -> None:
    # The `ranking:` precedent: a declared-but-unread table is legal (the
    # census consumes it), never accepted-but-ignored — the census cell above
    # proves the load.
    _accepts(_game("card_points { A: 1 }"))


# =============================================================================
# Parse — the wrong spellings teach the one block spelling
# =============================================================================


def test_colon_form_rejects_with_the_replacement_spelling() -> None:
    src = _game("card_points: { A: 1 }")
    with pytest.raises(DiagnosticError) as ei:
        check_dsl(src, "mini.cardlang")
    message = str(ei.value)
    assert "card_points {" in message, message


@pytest.mark.parametrize("spelling", ["card_values { A: 1 }", "card_values: { A: 1 }"])
def test_card_values_rejects_naming_card_points(spelling: str) -> None:
    src = _game(spelling)
    with pytest.raises(DiagnosticError) as ei:
        check_dsl(src, "mini.cardlang")
    message = str(ei.value)
    assert "card_points" in message, message


def test_duplicate_clause_hits_the_one_clause_wall() -> None:
    src = _game("card_points { A: 1 }\n  card_points { K: 10 }")
    _rejects(src, "one `card_points { }` block")


# =============================================================================
# Misuse probes — the plausible wrong block shapes, each a loud syntax error
# =============================================================================


@pytest.mark.parametrize(
    ("table", "case_id"),
    [
        ("card_points { }", "empty-block"),
        ("card_points { else: 1 }", "else-only"),
        ("card_points { else: 1  A: 2 }", "else-not-last"),
        ("card_points { A: 1  else: 2  else: 3 }", "doubled-else"),
        ("card_points { A: 1, K: 10 }", "comma-rows"),
        ("card_points { A: 1.5 }", "float-value"),
        ("card_points { A: 1 + 1 }", "expression-value"),
        ("card_points { A: K }", "name-value"),
        ("card_points { A: }", "missing-value"),
        ("card_points { A: +25 }", "unary-plus-value"),
        ("card_points { -3: 5 }", "negative-key"),
        ("card_points { A 1 }", "missing-colon-in-row"),
    ],
)
def test_misuse_is_a_loud_syntax_error(table: str, case_id: str) -> None:
    """Born green (the sentences are syntax errors before the clause exists
    too); each cell names the grammar edit that would make it parse.

    red under, per cell: empty-block / else-only — relax the block to
    `card_points_entry*`; else-not-last / doubled-else — move
    `card_points_else` into the entry alternation
    (`(card_points_entry | card_points_else)+`); comma-rows — add
    `("," card_points_entry)*` to the block; float-value — the grammar has
    no FLOAT terminal, so this requires minting one; expression-value /
    name-value — widen `card_points_value` to `expr`; missing-value — make
    the value optional; unary-plus-value — add a `"+" INT` alternative;
    negative-key — admit `"-" INT` in key position; missing-colon-in-row —
    make the `":"` optional. Verified by execution on the widened-value
    edit (`card_points_value: expr`): it reddens exactly the
    expression-value and name-value cells here, every other cell green."""
    _rejects(_game(table), "syntax error")


@pytest.mark.parametrize(
    ("src", "case_id"),
    [
        (
            "game G { players: 2 cards: standard52 max_length: 10\n"
            "  zones { deck : Deck }\n"
            "  state { s[player] : Integer = 0 }\n"
            "  phase p { card_points { A: 1 } }\n"
            "  winner: highest s\n}",
            "clause-in-phase-body",
        ),
        (
            "card_points { A: 1 }\n"
            "game G { players: 2 cards: standard52 max_length: 10\n"
            "  zones { deck : Deck }\n"
            "  state { s[player] : Integer = 0 }\n"
            "  winner: highest s\n}",
            "clause-at-top-level",
        ),
    ],
)
def test_clause_outside_a_game_body_is_a_loud_syntax_error(src: str, case_id: str) -> None:
    _rejects(src, "syntax error")


def test_clause_in_a_library_is_grammatically_inexpressible() -> None:
    from cardlang.parse import parse_library

    with pytest.raises(DiagnosticError) as ei:
        parse_library("library L {\n  card_points { A: 1 }\n}", "L.cardlang")
    assert "syntax error" in str(ei.value), str(ei.value)


# =============================================================================
# The rename — `card_points` resolves everywhere `card_value` did; the old
# spelling does not survive
# =============================================================================


def test_card_value_is_an_unknown_function_after_the_rename() -> None:
    src = _game("card_points { A: 1 }", body="s[0] := card_value(A of spades)")
    _rejects(src, "card_value")


# =============================================================================
# Hosts — the Team-param function shape canasta's rewrite stands on
# =============================================================================


def test_team_param_function_sums_card_points_over_a_team_zone_family() -> None:
    src = """
function team_points(t : Team) = sum of card_points(card) over cards in pile[t]

game Mini {
  players: 2
  teams: [[0], [1]]
  max_length: 1000
  cards: standard52
  ranking: aces low
  card_points { A: 5  K: 3 }
  zones { deck : Deck  hand[player] : Hand<player>  pile[team] : TeamPile<team> }
  state { s[team] : Integer = 0 }
  phase p {
    move all cards from deck where card.rank is A to pile[0]
    move all cards from deck where card.rank is K to pile[1]
    for each team t: s[t] := team_points(t)
  }
  winner: highest s
}
"""
    scores = play_game(check_dsl(src, "mini.cardlang"), random.Random(0)).scores
    assert scores[0] == 20 and scores[1] == 12  # 4 aces x 5; 4 kings x 3


# =============================================================================
# IR — the table is a conditional key, so clause-less goldens stay byte-stable
# =============================================================================


def test_ir_emits_the_table_only_when_declared() -> None:
    with_clause = _accepts(_game("card_points { A: 1  else: 2 }"))
    blob = json.dumps(ir.emit(with_clause))
    assert '"card_points_table"' in blob
    assert '"A"' in blob
    without = _accepts(_game(""))
    assert '"card_points' not in json.dumps(ir.emit(without))


# =============================================================================
# The migration agreement pins — the surviving Python tables equal the clause
# =============================================================================
#
# Four game runtime modules keep an internal point table because a staying
# primitive consumes it (gin's deadwood optimizer, cribbage's show scorers,
# canasta's meld-attempt core, tarot's settlement). Each is now a second copy
# of a fact the game file declares; these pins are the coupling declaration,
# the test_primitive_reads.py shape applied to values. Red before the
# migration (the game files declare no clause yet); after it, red under any
# one-sided edit to either copy.


def _declared_table(game_file: str) -> tuple[dict[str, int], int | None]:
    game = check_dsl((GAMES / game_file).read_text(), game_file)
    table = game.card_points
    assert table is not None, f"{game_file} declares no card_points clause"
    return {e.rank: e.value for e in table.entries}, table.else_value


def test_gin_deadwood_table_matches_the_declared_clause() -> None:
    from cardlang.runtime.gin import _POINTS

    rows, else_value = _declared_table("gin-rummy.cardlang")
    assert rows == _POINTS and else_value is None


def test_cribbage_show_table_matches_the_declared_clause() -> None:
    from cardlang.runtime.cribbage import _VALUE

    rows, else_value = _declared_table("cribbage.cardlang")
    assert rows == _VALUE and else_value is None


def test_canasta_meld_core_table_matches_the_declared_clause() -> None:
    from cardlang.runtime.canasta import POINTS

    rows, else_value = _declared_table("canasta.cardlang")
    assert rows == POINTS and else_value is None


def test_tarot_settlement_table_matches_the_clause_through_the_bout_layer() -> None:
    # tarot's per-card points are not rank-functional (the petit): the game
    # file composes the clause with the inline bout layer, and the settlement
    # keeps the Python helper. Equality is asserted the only honest way —
    # over every card of the pack, through the same composition the game
    # text uses: `if is_bout(card) then 9 else card_points(card)`.
    from cardlang.runtime.tarot import _is_bout, tarot_card_points
    from cardlang.runtime.values import build_deck

    rows, else_value = _declared_table("french-tarot.cardlang")
    assert else_value is not None
    for card in build_deck("tarot78"):
        composed = 9 if _is_bout(card) else rows.get(card.rank, else_value)
        assert composed == tarot_card_points(card), card
