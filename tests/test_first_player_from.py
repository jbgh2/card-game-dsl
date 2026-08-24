"""Surface-totality grid for the ring search: `the first player from <seat>
where <pred>`.

The third Merge Lane A PR of issue #249 (epic #248). The operator ruling
(point 3), the per-PR counsel, and the framing-check enumeration (both runs,
folded) live on that issue; decisions.md "Player-collection queries" carries
the settled text this grid pins.

Completeness ledger
--------------------
property:  every sentence the ring-search surface accepts scans exactly one
           inclusive lap of the seat ring from the named start, in the game's
           `direction:`, with `player` bound per candidate in the predicate
           and the start expression evaluated OUTSIDE the binder scope; the
           first satisfying seat is the value; an exhausted lap is an
           OwnerGuardError naming the form; and every plausible wrong
           sentence fails loud in its owning layer's currency (syntax errors
           for the truncated/foreign spellings, bag-collected diagnostics for
           name/type/binder defects, the existing seat Owner Guards for bad
           start values).
domain:    match position (at-start / mid-lap / wrap-to-last / composed
           exclusive with start-as-final-candidate / none) x direction
           (clockwise / counterclockwise / clause omitted) x player count
           (1 / 2 / 3 / 4 / 6) x start-slot shape (seat var, literal,
           offset_by single and chained, Integer arithmetic, Player
           arithmetic, parenthesized query, non-seat type, out-of-range
           literal and computed, binder-name, query-name absorption) x
           predicate shape (state read, zone
           emptiness, or-compound, nested card query, nested shadowing
           player query, call, non-Boolean, absorbed offset_by) x host
           (assignment, let, if-expression arm, lvalue index, turns from,
           auction/trick round from [parse shape], transfer amount, state
           default at setup, function body, library function body, choose
           bounds, piece game, postfix composition) x consuming layer
           (parse, resolve, typecheck, IR, evaluate) — plus the misuse
           sentences and the retiring hold'em unit arrangements 1:1.
registry:  the kind axis derives from the grammar's `player_query` aliases
           (scraped by test_kind_axis_is_pinned_by_grammar below) against
           the builder's kind strings; the ring itself is
           `values.Seating.turn_order_from` (one inclusive lap in the
           declared direction — the single convergence point every `from
           <leader>` clause shares) and `GAME_DIRECTIONS`; the start slot's
           static gate is the operand choke point (`_check_operand` +
           `_check_role_literal`, pinned by tests/test_operand_choke_point);
           host positions derive from the grammar's expr-reaching
           productions (the framing-check enumeration on issue #249, both
           runs).
covered:   the executed parametrizations and probes in this module — the
           lap grid (match position x direction x count through played
           games, including the ccw absolute-offset cell and the four
           retiring hold'em unit arrangements), the exhaustion cells
           (mid-phase and at-setup OwnerGuardError), the start-slot cells
           (chained offset_by, Integer arithmetic in range, Player
           arithmetic refused by the standing operator rule, literal and
           computed out-of-range through the existing Owner Guards,
           non-seat type, `players` absorbed as a NAME, `player` out of
           scope, parenthesized pick query), the predicate cells (or-compound
           semantics, nested card query, nested shadowing player query with
           the outer binder visible in the inner START slot, call predicate,
           non-Boolean, absorbed-offset_by refused in the type layer), the
           host cells (let, if-expression arm, lvalue index, turns-from
           executed end to end, transfer amount executed, state default at
           setup, function body, library function body, choose bounds
           parenthesized and unparenthesized, piece game, postfix
           composition, auction- and trick-round from at parse shape), the
           misuse probes (no-from, no-where, no-the, doubled where,
           next/after spelling, trailing direction word), the IR cells
           (conditional `start` key both ways), and the zero-ambiguity cell
           over the form's adjacency sentences.
sampled:   (a) the long tail of expression hosts (produce/run args, rule
           clauses, reveal filters, vis_clause, quantifier bodies, agg
           bodies, list literals, struct field inits): one AST node, one
           builder, one evaluator arm — every host funnels through the same
           `_check_expr`/`evaluate` walk probed here; the load-bearing
           distinct paths (setup-time evaluation, binder scopes, the round
           forms' leader slot, library bodies) each hold an executed cell.
           (b) the auction- and trick-round `from` slots run end to end
           through the rewritten hold'em corpus file (four `round offering
           ... from the first player ...` sites) and its playout suite; the
           grid pins their parse shape only.
           (c) `is`/`in`/`team_of`/zone-subscript consumption of the result:
           the result is an ordinary TPlayer value through the same infer
           arm the pick form uses; the lvalue-index and offset_by
           composition cells are the executed representatives.
residual:  (a) a runtime `bool` reaching the start slot through a gradual
           type is silently seat 1/0 — `turn_order_from`'s membership guard
           accepts `True == 1`; the class belongs to that Owner Guard and is
           shared by every `from` clause (turns/round/auction/climb), so a
           check in this form's arm would be a Shadow Guard; pre-existing,
           R4 here (needs a TAny-valued seat expression nobody writes;
           recorded, no issue — the sibling dynamic-operand class is
           issue #339). (b) the transfer amount slot is statically
           unchecked (a String or Player amount checks green; a bad one
           dies at play in a raw ValueError — executed during this grid's
           authoring); the amount slot's own standing class, R3 — its capacity
           face is issue #338 and its static-type face is named in the
           divided-by framing enumeration on issue #249; this grid pins the
           fence and the seat-as-count semantics that fall out today,
           adding reach, not cause.
           (c) concrete non-Boolean operands in an `or`/`and` predicate ARE
           rejected by the operator guards — executed during review
           response: `where mark[player] or seat` and `... or s[0]` both
           fail with "'or' expects Boolean operands, got Player/Integer"
           (the framing enumeration's folded claim of an unchecked operand
           conflated infer's unconditionally-Boolean RESULT type with the
           check side, and execution disproves it). The true residue is the
           TAny-gradual pass-through — a gradual operand in a disjunct
           checks green and decides truthiness at play — the standing
           gradual class whose owner is tests/test_operator_guards.py's
           ledger; the or-cell here pins the SEMANTICS (the disjunction is
           the predicate, never a default). (d) reject-with-replacement productions
           for `the next player after ...` and a trailing direction word
           were weighed and declined — never-in-the-language spellings get
           loud syntax errors (pinned below), and minting rejection surface
           for them is un-ruled grammar.
naming:    `the first player from ... where ...` mints no glossary entry:
           no player-collection query form carries one (the family's naming
           home is decisions.md "Player-collection queries", whose prose
           already says "the player ring"), matching the divided-by
           precedent for operator forms; `first` appears in neither
           glossary section 6 nor any NAME exclusion, and
           RESERVED_VALUE_NAMES is hand-listed so `first` stays declarable
           (pinned by the names-stay-names cells below).
red-first: authored before the implementation; the red run is recorded in
           the PR. Born-green pins carry per-pin reddening mutations
           (executed = plant, red, revert, green was run; documented = the
           mutation is named here per the divided-by precedent):
           test_kind_axis_is_pinned_by_grammar — red under: rename the
           `the_first_player_from_where` alias (EXECUTED);
           misuse no_from — red under: `[_FROM_KW sum]` optional in the
           production (EXECUTED: exactly the no_from cell reddens);
           misuse no_where — red under: `[_WHERE_KW expr]` optional
           (EXECUTED: exactly the no_where cell reddens, 1 failed 5
           passed);
           misuse no_the — red under: `[_THE_KW]` optional in the
           production (documented);
           misuse doubled_where — red under: the where clause made
           repeatable, `(_WHERE_KW expr)+` (documented);
           misuse next_after_spelling — red under: adding a
           `_THE_KW <next> _PLAYER_KW <after> sum _WHERE_KW expr`
           production with anchored next/after terminals (documented);
           misuse trailing_direction_word — red under: an optional
           trailing NAME after the predicate in the production
           (documented);
           the two discriminating lap cells carry their executed plants at
           the cell (composed_exclusive_start_is_final: lap truncation;
           test_chained_offset_by_start: offset no-op).
"""

from __future__ import annotations

import random
import re
from importlib import resources

import pytest
from lark import Lark

from cardlang import ir
from cardlang.ast import nodes as n
from cardlang.diagnostics import DiagnosticError
from cardlang.parse import parse_library, parse_text
from cardlang.pipeline import check_dsl
from cardlang.runtime.driver import play_game
from cardlang.runtime.errors import OwnerGuardError

# --- the shared minimal game shells ------------------------------------------


def _game(
    body: str,
    players: int = 4,
    direction: str = "",
    extra_state: str = "",
    top: str = "",
    uses: str = "",
) -> str:
    dir_clause = f"direction: {direction}" if direction else ""
    return f"""
{top}
game Mini {{
  players: {players}
  {uses}
  max_length: 1000
  {dir_clause}
  cards: standard52
  ranking: A K Q J 10 9 8 7 6 5 4 3 2
  zones {{ deck : Deck  hand[player] : Hand<player> }}
  state {{
    s[player] : Integer = 0
    mark[player] : Boolean = false
    mark2[player] : Boolean = false
    seat : Player = 0
    {extra_state}
  }}
  phase p {{
    {body}
  }}
  winner: highest s
}}
"""


def _marks(marked: tuple[int, ...], var: str = "mark") -> str:
    return "  ".join(f"{var}[{p}] := true" for p in marked)


def _accepts(src: str) -> n.Game:
    return check_dsl(src, "mini.cardlang")


def _rejects(src: str, needle: str) -> None:
    with pytest.raises(DiagnosticError) as ei:
        check_dsl(src, "mini.cardlang")
    assert needle in str(ei.value), str(ei.value)


def _scores(src: str) -> dict[int, int]:
    return play_game(check_dsl(src, "mini.cardlang"), random.Random(0)).scores


def _play_rejects(src: str, needle: str) -> None:
    game = check_dsl(src, "mini.cardlang")
    with pytest.raises(OwnerGuardError) as ei:
        play_game(game, random.Random(0))
    assert needle in str(ei.value), str(ei.value)


def _found_seat(
    start: str,
    marked: tuple[int, ...],
    players: int = 4,
    direction: str = "",
    pred: str = "mark[player]",
) -> int:
    """Run the form through a played game and return the seat it selected."""
    body = f"{_marks(marked)}\n    seat := the first player from {start} where {pred}\n    s[seat] += 1"
    scores = _scores(_game(body, players=players, direction=direction))
    winners = [p for p, v in scores.items() if v == 1]
    assert len(winners) == 1, scores
    return winners[0]


# =============================================================================
# The kind-axis pin — the grammar's player_query aliases are the kind registry
# =============================================================================


def test_kind_axis_is_pinned_by_grammar() -> None:
    """The family's kind axis derives from the grammar's `player_query`
    aliases; the cells below spell the four kinds, reconciled here so a kind
    added or renamed in the grammar cannot drift past this grid.

    red under: rename the `the_first_player_from_where` alias in the grammar
    (the scraped set loses the member this assertion demands)."""
    grammar = resources.files("cardlang.grammar").joinpath("cardlang.lark").read_text()
    block = grammar.split("player_query:")[1].split("\n\n")[0]
    aliases = set(re.findall(r"->\s*(\w+)", block))
    assert aliases == {
        "players_where",
        "the_player_where",
        "the_first_player_from_where",
        "number_players_where",
    }


def test_parse_builds_the_first_from_kind() -> None:
    game = parse_text(
        _game("seat := the first player from seat where mark[player]"), "t.dsl"
    )
    lets = [s for s in game.phases[0].items if isinstance(s, n.AssignStmt)]
    q = lets[0].value
    assert isinstance(q, n.PlayerQuery)
    assert q.kind == "first_from"
    assert q.start is not None


# =============================================================================
# The lap grid — match position x direction x player count, through played
# games (the evaluator and the real Seating, not a unit shim)
# =============================================================================

# (label, start expr, marked seats, players, direction, expected seat).
# Expected values are design decisions authored before the implementation:
# one inclusive lap from the start seat, stepping in the game's direction;
# `offset_by` is ABSOLUTE (+1 left / -1 right in either ring), so the
# exclusive spelling composes with the seat direction matching the game's
# turn direction.
LAP_CELLS: list[tuple[str, str, tuple[int, ...], int, str, int]] = [
    ("at_start_inclusive", "2", (2, 0), 4, "clockwise", 2),
    ("mid_lap_skip", "1", (3,), 4, "clockwise", 3),
    ("wrap_to_last", "2", (1,), 4, "clockwise", 1),
    # coup's composed exclusive scan: the UN-OFFSET seat is the lap's FINAL
    # candidate (seat holds its default 0; from 0 offset_by left = 1; lap
    # 1,2,3,0), and marking ONLY that final candidate makes the cell
    # discriminate lap completeness: a lap short of its final element
    # exhausts here instead of answering 0.
    # red under: truncating `Seating.turn_order_from` to `range(self.count
    # - 1)` — executed: this cell fails with the exhaustion error, alongside
    # wrap_to_last and ccw_exclusive_composes_with_right (the same full-lap
    # face, inclusive and counterclockwise sides); reverted, green.
    ("composed_exclusive_start_is_final", "seat offset_by left", (0,), 4, "clockwise", 0),
    ("direction_clockwise", "0", (1, 3), 4, "clockwise", 1),
    ("direction_counterclockwise", "0", (1, 3), 4, "counterclockwise", 3),
    ("direction_omitted_defaults_clockwise", "0", (1, 3), 4, "", 1),
    # the folded framing-check cell: offset_by stays ABSOLUTE under a
    # counterclockwise lap — from 0 offset_by left = seat 1, ccw lap
    # 1,0,3,2 — so the first of {1,3} is 1 (a direction-relative offset
    # would start at 3 and pick 3). The composed spelling visits the
    # un-offset seat SECOND here, not last: the exclusive variant of a
    # counterclockwise game is `offset_by right`.
    ("ccw_offset_by_left_is_absolute", "seat offset_by left", (1, 3), 4, "counterclockwise", 1),
    ("ccw_exclusive_composes_with_right", "seat offset_by right", (0,), 4, "counterclockwise", 0),
    ("one_player_match", "0", (0,), 1, "", 0),
    ("two_player_other_seat", "0", (1,), 2, "", 1),
    ("six_player_wrap_across_zero", "5", (0,), 6, "", 0),
]


@pytest.mark.parametrize(
    ("label", "start", "marked", "players", "direction", "expected"),
    LAP_CELLS,
    ids=[c[0] for c in LAP_CELLS],
)
def test_lap_grid(
    label: str,
    start: str,
    marked: tuple[int, ...],
    players: int,
    direction: str,
    expected: int,
) -> None:
    assert _found_seat(start, marked, players=players, direction=direction) == expected


# The four retiring hold'em unit arrangements, 1:1 (tests/test_playout_holdem
# asserted them against the primitive; the behavioral spec transfers here
# before those tests delete). 3 players, clockwise, inclusive start.
HOLDEM_CELLS: list[tuple[str, str, tuple[int, ...], int]] = [
    ("returns_the_seat_itself_when_marked", "1", (0, 1, 2), 1),
    ("skips_an_unmarked_seat", "1", (0, 2), 2),
    ("wraps_around_the_ring", "1", (0,), 0),
    ("wraps_from_the_last_seat", "2", (0,), 0),
]


@pytest.mark.parametrize(
    ("label", "start", "marked", "expected"),
    HOLDEM_CELLS,
    ids=[c[0] for c in HOLDEM_CELLS],
)
def test_holdem_unit_arrangements_transfer(
    label: str, start: str, marked: tuple[int, ...], expected: int
) -> None:
    assert _found_seat(start, marked, players=3) == expected


def test_the_issues_probe_sentence_semantics() -> None:
    """The issue's probe, in its ruled `the`-headed spelling, with hold'em's
    own state names: the big blind is the first entrant left of the small
    blind."""
    src = _game(
        """
        in_hand[0] := true  in_hand[1] := true  in_hand[2] := true
        small_blind := 2
        big_blind := the first player from small_blind offset_by left where in_hand[player]
        s[big_blind] += 1
        """,
        players=3,
        direction="clockwise",
        extra_state="in_hand[player] : Boolean = false\n    small_blind : Player = 0\n    big_blind : Player = 0",
    )
    scores = _scores(src)
    assert scores[0] == 1, scores


# =============================================================================
# Exhaustion — OwnerGuardError naming the form, the game-author channel
# =============================================================================


def test_exhausted_lap_is_a_typed_runtime_error() -> None:
    _play_rejects(
        _game("seat := the first player from seat where mark[player]"),
        "matched no player",
    )


def test_exhaustion_message_names_the_form_and_the_lap() -> None:
    game = check_dsl(
        _game("seat := the first player from 2 where mark[player]"), "mini.cardlang"
    )
    with pytest.raises(OwnerGuardError) as ei:
        play_game(game, random.Random(0))
    msg = str(ei.value)
    assert "the first player from" in msg, msg
    assert "4-seat lap" in msg, msg
    assert "seat 2" in msg, msg


def test_exhaustion_in_a_state_default_fires_at_setup() -> None:
    _play_rejects(
        _game(
            "s[0] := 0",
            extra_state="init : Player = the first player from 0 where false",
        ),
        "matched no player",
    )


# =============================================================================
# The start slot — shapes, guards, and scope
# =============================================================================


def test_chained_offset_by_start() -> None:
    # seat = 0; left twice = seat 2; lap 2,3,0,1. Marking {1, 2} makes the
    # arrangement discriminate the CHAIN: the full chain answers 2, while a
    # dropped link (start 1: lap 1,2,3,0) or no offset at all (start 0)
    # answers 1.
    # red under: a no-op `left` in `Seating.offset_by` (`"left": 0`) —
    # executed: this cell answers 1 and fails (with the other offset-borne
    # cells guarding the same delta); reverted, green.
    assert _found_seat("seat offset_by left offset_by left", (1, 2)) == 2


def test_arithmetic_integer_start_in_range() -> None:
    # The from-slot sits at `sum` level (the epic counsel's ruled hazard
    # spec; the framing check's tighter `term` alternative is recorded in
    # the ledger): bare INTEGER arithmetic is grammatical, coerces into the
    # seat slot, and is runtime-guarded when out of range (the cell below).
    src = _game(
        "mark[1] := true\n    seat := the first player from x + 1 where mark[player]\n    s[seat] += 1",
        extra_state="x : Integer = 0",
    )
    assert _scores(src)[1] == 1


def test_player_arithmetic_start_is_the_arithmetic_diagnostic() -> None:
    # `seat + 1` is refused by the standing operator rule (equality coerces,
    # arithmetic does not): the slot inherits the guard, adding nothing.
    _rejects(
        _game("seat := the first player from seat + 1 where mark[player]"),
        "'+' expects Integer operands, got Player",
    )


def test_computed_out_of_range_start_hits_the_seat_owner_guard() -> None:
    # The runtime seat guard is Seating.turn_order_from's, the ONE
    # convergence point every `from <leader>` shares; this form adds no
    # second guard, so the message is that Owner Guard's own.
    _play_rejects(
        _game(
            "mark[0] := true  seat := the first player from x where mark[player]",
            extra_state="x : Integer = 9",
        ),
        "not a seat of this",
    )


def test_literal_out_of_range_start_is_a_static_diagnostic() -> None:
    _rejects(
        _game("seat := the first player from 9 where mark[player]"),
        "out of range",
    )


def test_non_seat_start_is_a_coercion_diagnostic() -> None:
    _rejects(
        _game("seat := the first player from (A of spades) where mark[player]"),
        "expected a Player",
    )


def test_players_in_the_from_slot_stays_a_name() -> None:
    # The from-slot cannot absorb a query: `players` is a bare NAME there
    # (resolve's unknown-name cell), and the `where` belongs to the form.
    _rejects(
        _game("seat := the first player from players where mark[player]"),
        "unresolved name 'players'",
    )


def test_binder_out_of_scope_in_the_start_slot() -> None:
    # The start expression evaluates OUTSIDE the binder scope: `player`
    # there is unresolved at top level, with the family's own hint.
    _rejects(
        _game("seat := the first player from player where mark[player]"),
        "bound only inside a player query",
    )


def test_parenthesized_pick_query_start() -> None:
    src = _game(
        """
        mark2[3] := true
        mark[0] := true
        seat := the first player from (the player where mark2[player]) where mark[player]
        s[seat] += 1
        """
    )
    scores = _scores(src)
    assert scores[0] == 1, scores  # from 3: lap 3,0,1,2 -> first marked is 0


# =============================================================================
# The predicate — shapes, scope, and the or-compound semantics
# =============================================================================


def test_or_binds_into_the_predicate_not_a_default() -> None:
    # mark = {3}, mark2 = {1}: the compound predicate matches 1 first. A
    # default-clause misreading (`or mark2[...]` as a fallback value) would
    # scan `mark` alone and pick 3.
    src = _game(
        """
        mark[3] := true  mark2[1] := true
        seat := the first player from 0 where mark[player] or mark2[player]
        s[seat] += 1
        """
    )
    scores = _scores(src)
    assert scores[1] == 1, scores


def test_nested_card_query_predicate() -> None:
    src = _game(
        """
        shuffle deck
        deal 2 cards from deck to hand[2]
        seat := the first player from 0 where any card in hand[player] where true
        s[seat] += 1
        """
    )
    scores = _scores(src)
    assert scores[2] == 1, scores


def test_nested_player_query_shadows_the_binder() -> None:
    # The inner form's START slot sees the OUTER binder (`from player`);
    # the inner predicate rebinds `player`. With mark = {2}: the outer
    # candidate p satisfies iff the first marked seat from p IS p, i.e.
    # p = 2.
    src = _game(
        """
        mark[2] := true
        seat := the first player from 0 where (the first player from player where mark[player]) is player
        s[seat] += 1
        """
    )
    scores = _scores(src)
    assert scores[2] == 1, scores


def test_call_predicate() -> None:
    src = _game(
        "mark[1] := true\n    seat := the first player from 3 where is_marked(player)\n    s[seat] += 1",
        top="function is_marked(p : Player) = mark[p]",
    )
    scores = _scores(src)
    assert scores[1] == 1, scores  # from 3: lap 3,0,1 -> 1


def test_non_boolean_predicate_is_the_family_diagnostic() -> None:
    _rejects(
        _game("seat := the first player from seat where 3"),
        "player-query predicate",
    )


def test_absorbed_offset_by_is_refused_in_the_type_layer() -> None:
    # Unparenthesized postfix composition: the predicate extends maximally
    # right, so `mark[player] offset_by left` IS the predicate — and
    # offset_by's own operand guard refuses the Boolean left operand (it
    # fires before the family's Boolean check; either way the absorbed
    # reading is loud in the type layer, never a silent misparse).
    _rejects(
        _game("seat := the first player from 0 where mark[player] offset_by left"),
        "left operand must be a Player, got Boolean",
    )


# =============================================================================
# Hosts — each load-bearing consuming path holds an executed cell
# =============================================================================


def test_let_host() -> None:
    src = _game(
        "mark[3] := true\n    let x = the first player from 1 where mark[player]\n    s[x] += 1"
    )
    assert _scores(src)[3] == 1


def test_if_expression_arm_host() -> None:
    # hold'em's small-blind site shape: the form in the else arm.
    src = _game(
        """
        mark[0] := true  mark[2] := true
        seat := if (number of players where mark[player]) is 2
                  then seat
                  else the first player from 1 where mark[player]
        s[seat] += 1
        """
    )
    assert _scores(src)[0] == 1  # two marked -> then-arm keeps seat 0


def test_lvalue_index_host() -> None:
    src = _game(
        "mark[2] := true\n    s[the first player from 0 where mark[player]] += 5"
    )
    assert _scores(src)[2] == 5


def test_turns_from_host_runs_end_to_end() -> None:
    src = _game(
        """
        mark[2] := true
        turns t from the first player from 0 where mark[player]
              over all players
              until (number of players where s[player] > 0) > 0 {
          s[t] += 1
        }
        """
    )
    assert _scores(src)[2] == 1


def test_auction_round_from_parse_shape() -> None:
    # The auction `from` slot fences at `over` (hold'em's four street
    # openers are the end-to-end witnesses through the corpus suite).
    game = parse_text(
        _game(
            """
        round offering [bid_a, bid_b] from the first player from seat where mark[player]
              over players where mark[player]
              until true
        """
        ),
        "t.dsl",
    )
    stmt = next(s for s in game.phases[0].items if isinstance(s, n.AuctionRound))
    assert isinstance(stmt.leader, n.PlayerQuery)
    assert stmt.leader.kind == "first_from"
    assert isinstance(stmt.participants, n.PlayerQuery)
    assert stmt.participants.kind == "set"


def test_trick_round_from_parse_shape() -> None:
    game = parse_text(
        _game(
            """
        round t from the first player from seat where mark[player]
              over players where mark[player]
              source hand into deck
              winner seat_of
        """
        ),
        "t.dsl",
    )
    stmt = next(s for s in game.phases[0].items if isinstance(s, n.TrickRound))
    assert isinstance(stmt.leader, n.PlayerQuery)
    assert stmt.leader.kind == "first_from"


def test_transfer_amount_host_fences_and_computes() -> None:
    # The form abuts the transfer's own noun and `from`: the amount is the
    # query, `cards from deck` is the transfer's machinery. The amount slot
    # is statically unchecked today (a standing residual, see the ledger);
    # the seat coerces to a count at play: seat 2 moves 2 cards.
    src = _game(
        """
        shuffle deck
        mark[2] := true
        move the first player from 0 where mark[player] cards from deck to hand[0]
        s[0] := number of cards in hand[0]
        """
    )
    assert _scores(src)[0] == 2


def test_state_default_host_evaluates_at_setup() -> None:
    src = _game(
        "s[init] += 1",
        extra_state="init : Player = the first player from 1 where true",
    )
    assert _scores(src)[1] == 1


def test_function_body_host() -> None:
    # The function's parameter feeds the start slot; the binder inside the
    # predicate is the family's own `player`.
    src = _game(
        "mark[1] := true\n    seat := nxt(3)\n    s[seat] += 1",
        top="function nxt(q : Player) = the first player from q where mark[player]",
    )
    assert _scores(src)[1] == 1  # from 3: lap 3,0,1 -> 1


def test_library_function_body_host(monkeypatch: pytest.MonkeyPatch) -> None:
    # Family libraries share the expression sublanguage (the `library` start
    # symbol), so the form is legal in a library function body. Synthetic
    # library via the test_family_libraries monkeypatch shape; the game's
    # source is unique to this test, so the check memo cannot cross-talk.
    lib = parse_library(
        "library ring_lib {\n"
        "  function libnxt(q : Player) = the first player from q offset_by left where true\n"
        "}\n",
        "ring_lib.cardlang",
    )
    monkeypatch.setattr("cardlang.resolve.library_names", lambda: frozenset({"ring_lib"}))
    monkeypatch.setattr("cardlang.resolve.load_library", lambda name: lib)
    src = _game(
        "seat := libnxt(0)\n    s[seat] += 1",
        uses="uses ring_lib",
    )
    assert _scores(src)[1] == 1


def test_choose_bounds_parenthesized() -> None:
    # The choose needs an acting-player context (the for-each shape the
    # choose harness uses); the parenthesized form is its upper bound.
    src = _game(
        """
        mark[2] := true
        for each player q: s[q] := choose integer in 0 .. (the first player from 0 where mark[player]) up to 3
        """
    )
    scores = _scores(src)
    assert all(0 <= v <= 2 for v in scores.values()), scores


def test_choose_bounds_unparenthesized_is_a_syntax_error() -> None:
    _rejects(
        _game(
            "let c = choose integer in 0 .. the first player from 0 where mark[player] up to 3"
        ),
        "syntax error",
    )


def test_piece_game_host() -> None:
    # PlayerQuery carries no flavor gate and the driver builds the seating
    # ring for every game: the form is legal and meaningful in a piece game.
    src = """
game PieceMini {
  players: 2
  max_length: 100
  board: grid(3, 3)
  pieces: xo_marks
  zones { box : Deck  square[cell] : Cell<cell> }
  state { s[player] : Integer = 0  mark[player] : Boolean = false }
  phase p {
    mark[1] := true
    s[the first player from 0 where mark[player]] += 1
  }
  winner: highest s
}
"""
    scores = play_game(check_dsl(src, "piece.cardlang"), random.Random(0)).scores
    assert scores[1] == 1


def test_postfix_composition_parenthesized() -> None:
    src = _game(
        """
        mark[2] := true
        seat := (the first player from 0 where mark[player]) offset_by left
        s[seat] += 1
        """
    )
    assert _scores(src)[3] == 1


# =============================================================================
# Misuse probes — the plausible wrong sentences, each loud in its layer
# =============================================================================


@pytest.mark.parametrize(
    ("label", "stmt"),
    [
        ("no_from", "seat := the first player where mark[player]"),
        ("no_where", "seat := the first player from seat"),
        ("no_the", "seat := first player from seat where mark[player]"),
        (
            "doubled_where",
            "seat := the first player from seat where mark[player] where mark[player]",
        ),
        (
            "next_after_spelling",
            "seat := the next player after seat where mark[player]",
        ),
        (
            "trailing_direction_word",
            "seat := the first player from seat where mark[player] clockwise",
        ),
    ],
)
def test_misuse_is_a_loud_syntax_error(label: str, stmt: str) -> None:
    _rejects(_game(stmt), "syntax error")


def test_first_stays_a_name() -> None:
    # `first` anchors only: compounds and the bare identifier keep parsing
    # as NAMEs (RESERVED_VALUE_NAMES is hand-listed; `first` joins nothing).
    _accepts(
        _game(
            "first_out := 2  seat := first_out",
            extra_state="first_out : Player = 0",
        )
    )
    _accepts(
        _game(
            "first := 2  seat := first",
            extra_state="first : Player = 0",
        )
    )


# =============================================================================
# IR — the conditional start key
# =============================================================================


def _ir_queries(src: str) -> list[dict[str, object]]:
    game = check_dsl(src, "mini.cardlang")
    doc = ir.emit(game)
    found: list[dict[str, object]] = []

    def walk(x: object) -> None:
        if isinstance(x, dict):
            if x.get("kind") == "player_query":
                found.append(x)
            for v in x.values():
                walk(v)
        elif isinstance(x, list):
            for v in x:
                walk(v)

    walk(doc)
    return found


def test_ir_emits_conditional_start_key() -> None:
    qs = _ir_queries(
        _game(
            "mark[0] := true\n    seat := the first player from seat where mark[player]"
        )
    )
    ring = [q for q in qs if q["query"] == "first_from"]
    assert len(ring) == 1
    assert "start" in ring[0]


def test_ir_pick_form_has_no_start_key() -> None:
    qs = _ir_queries(
        _game("mark[0] := true\n    seat := the player where mark[player]")
    )
    pick = [q for q in qs if q["query"] == "pick"]
    assert len(pick) == 1
    assert "start" not in pick[0]


# =============================================================================
# Zero ambiguity — the adjacency sentences, pinned corpus-independently
# =============================================================================


def test_adjacency_sentences_parse_at_zero_ambiguity() -> None:
    grammar = resources.files("cardlang.grammar").joinpath("cardlang.lark").read_text()
    parser = Lark(
        grammar,
        parser="earley",
        propagate_positions=True,
        maybe_placeholders=True,
        start=["start", "stdlib_rules", "library"],
        ambiguity="explicit",
    )
    sentences = [
        "seat := the first player from seat offset_by left where mark[player] and hand[player] is not empty",
        "seat := the first player from seat where mark[player] or mark2[player]",
        """round offering [bid_a, bid_b] from the first player from seat offset_by left where mark[player]
              over players where mark[player] order ring until true""",
        "turns t from the first player from seat where mark[player] over all players until true { seat := t }",
        "move the first player from seat where mark[player] cards from hand[0] to hand[1]",
        """round t from the first player from seat where mark[player] over players where mark[player]
              source hand into deck winner seat_of""",
    ]
    for stmt in sentences:
        tree = parser.parse(_game(stmt), start="start")
        ambigs = sum(1 for s in tree.iter_subtrees() if s.data == "_ambig")
        assert ambigs == 0, f"{ambigs} _ambig for: {stmt[:60]}"
