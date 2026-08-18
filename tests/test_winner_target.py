"""A `winner:` target must be a state variable a game can actually be ranked by.

`winner: <rank-dir> <name>` names the score the game is decided on. Resolve
already walls the NAME — undeclared, or declared inside a phase — but says
nothing about the DECLARATION it lands on, and two of that declaration's
properties decide whether the whole result path works:

  * **indexed or not.** `driver` builds the result with
    `dict(rs.get(game.winner.state_var))`, so a scalar target dies with a bare
    `TypeError: 'int' object is not iterable` — a Python error, not a
    diagnostic (issue #153). In a game with a `repeat until` phase it dies
    EARLIER, at the per-hand trace (`driver.py`'s `hand_end`), so which
    Python error a designer meets depends on whether their game loops.
  * **its declared type.** Nothing anywhere checked this. `Integer` and
    `Boolean` rank correctly. Everything else either crashes (`Card` and
    struct values are unorderable; an optional may hold `none`) or —
    worse — succeeds silently: a `Player`-typed target ranks fine, and
    `openspiel/replay.returns_for` then hands OpenSpiel **seat ids as
    utilities**, with no exception at any layer.

`Boolean` is accepted deliberately and is not a lenience: `cheat`
(`won[player]`) and `coup` (`alive[player]`) are ranked by one, and an
Integer-only rule would refuse two corpus games.

Completeness ledger (decisions.md "Closed-domain completeness")
---------------------------------------------------------------
property:   a `winner:` target names a game-level state variable that is
            INDEXED by an indexable role and declared with a rankable,
            non-optional type (`Integer` or `Boolean`); anything else is a
            check-time diagnostic naming the declaration, never a Python
            error at playout and never a silent ranking.
domain:     {index} x {declared type}. {index} = every `domains.Role`
            member plus the unindexed case. {declared type} = every
            `typecheck.KNOWN_TYPE_NAMES` member plus a game-declared struct
            name, each in its plain and optional form.
registry:   `tests/winner_axes.py` derives both axes in code — the index
            axis from the `Role` enum (`domains.Role`, THE definition site
            for role ids), the type axis from `typecheck.KNOWN_TYPE_NAMES`
            (itself `_SCALAR_TYPES | _ENUM_TYPES`). The grid crosses ALL of
            `Role`, not the `ZONE_INDEX_ROLES` subset a state index may
            legally take, so a role joining the indexable set arrives with
            a row already written. The default-literal table is pinned
            against `KNOWN_TYPE_NAMES` by
            `test_default_table_covers_every_declared_type`, so a new
            declared type reddens the pin instead of silently dropping its
            rows from the parametrization.
covered:    the grid below — `winner_axes.cells()` x {accepted, rejected},
            `test_winner_target_cell`, 95 rows. Each rejecting row also
            asserts WHICH BRANCH answers, through a phrase only that branch
            emits (`REFUSAL_PHRASES`): the pre-existing state-declaration
            guard for a non-indexable role, and one of the new guard's three
            branches — unindexed, optional, unrankable type — otherwise. The
            three branches share a "`winner:`" prefix, so a phrase at layer
            granularity would let a cell refused by the wrong branch read as
            covered. Plus three misuse probes,
            which vary the GAME the grid holds constant rather than the
            declaration: a target naming a zone, a target declared inside a
            phase (both refused by the name guards, with
            `_check_winner_target` silent), and a `team`-indexed target in a
            game declaring no `teams:`.
sampled:    the struct-type cell runs ONE struct shape (`Pair`), not a
            sub-axis of field shapes: a struct is unrankable whatever it
            holds, so the field list cannot vary the property under guard.
            The rank-direction axis is not crossed here — both members are
            already pinned exhaustively against the grammar terminal by
            `test_rank_dir_set_is_pinned`, and neither interacts with the
            declaration.
residual:   cells on this surface that this ledger does NOT close, each
            with its guard and its record:
            - the index axis is derived from `Role`, but `state_decl`'s
              grammar admits ANY name in the `[ ]` slot, including a
              declared position domain (`probe[column]`). That is the state
              DECLARATION guard's class, not this one's, and it is executed
              at tests/rejections/positions_state_indexed_by_position.cardlang
              — so the cell is guarded and proven, just not by a row of this
              grid. R4, this ledger owns the record.
            - the accepted `team` row ranks a team-keyed score, and the
              result path then reports a team index through a field typed as
              a player (issue #154); guard: none — the checker accepts the
              declaration, which is correct, and the defect is downstream in
              `GameResult`/`returns_for`.
            - a game declaring BOTH `winner:` and `loser:` accepts and then
              silently discards the loser clause (issue #247); guard: none
              today, which is what that issue is.
            - a `loser:` selection that is gradually typed (`TAny`) and
              evaluates to an out-of-range seat, or to a `bool` (which
              passes `isinstance(_, int)`), reaches `returns_for` and
              produces returns that do not sum to zero (issue #297);
              guard: the driver's typed raise, which the value passes.
            - a range `players:` declaration bounds seat literals by `high`
              while the game is played at `low` (issue #296); guard: the
              runtime `OwnerGuardError` on the phantom key.
            - ties in the target's values make `GameResult.winner` the
              first maximal key in insertion order, and `returns_for`
              disagrees by paying tied seats equally (issue #298); guard:
              none.
            - a target that is never written ranks every seat at its
              declared default, so the winner is whichever seat sorts
              first. NOT guarded and NOT filed: it is indistinguishable
              from a game that legitimately ends all-square, so there is no
              defect to state (R4, this ledger owns the record).
"""

from __future__ import annotations

import pytest

from cardlang.diagnostics import DiagnosticError
from cardlang.pipeline import check_dsl
from cardlang.typecheck import KNOWN_TYPE_NAMES
from tests.winner_axes import DEFAULTS, STRUCT_TYPE, cells

# The roles a state variable may be indexed by. Deliberately NOT imported
# from `ZONE_INDEX_ROLES`: this is the grid's own statement of which cells
# are designed to be accepted, and reading it from the registry the guard
# consults would make the grid measure the guard against itself.
RANKABLE_INDEXES = frozenset({"player", "team"})
RANKABLE_TYPES = frozenset({"Integer", "Boolean"})

# The phrase each answering BRANCH alone can emit, keyed by verdict. The three
# `_check_winner_target` branches share a "`winner:`" prefix, two of them share
# "a game is ranked by a score", and two open "declared `" — so asserting any
# shared fragment lets a cell refused by the wrong branch read as covered,
# which is the layer-granularity claim one level down. Each phrase below is
# emitted by exactly one branch.
REFUSAL_PHRASES: dict[str, str] = {
    "reject:declaration": "not an indexable role",
    "reject:unindexed": "which is not indexed",
    "reject:optional": "an optional score may be `none`",
    "reject:type": "the target must be " + ", ".join(sorted(RANKABLE_TYPES)),
}


def test_default_table_covers_every_declared_type() -> None:
    """A new declared type must reach the grid, not vanish from it.

    red under: add a member to `typecheck._SCALAR_TYPES` (or `_ENUM_TYPES`)
    without adding its default literal to `winner_axes.DEFAULTS`.
    """
    assert set(DEFAULTS) == set(KNOWN_TYPE_NAMES)


def game_source(index: str | None, written: str, default: str) -> str:
    slot = f"[{index}]" if index else ""
    return (
        "game WinnerTarget {\n"
        "  players: 4\n"
        "  direction: clockwise\n"
        "  max_length: 40\n"
        "  teams: [[0, 2], [1, 3]]\n"
        "  cards: standard52\n"
        "  ranking: A K Q J 10 9 8 7 6 5 4 3 2\n"
        "  zones { deck : Deck  hand[player] : Hand<player> }\n"
        f"  state {{ probe{slot} : {written} = {default}  done : Boolean = false }}\n"
        "  phase setup { deal 3 cards from deck to each hand }\n"
        "  phase play {\n"
        "    turns t from 0 over all players until done {\n"
        "      offer to t one of [stop]\n"
        "    }\n"
        "  }\n"
        "  winner: highest probe\n"
        "}\n"
        f"type {STRUCT_TYPE} = {{ a : Integer }}\n"
        "move_type stop { effect { done := true } }\n"
    )


def expected_verdict(index: str | None, written: str) -> str:
    """The design decision for one cell: who accepts it, or which wall refuses.

    Authored from the property, not from the implementation — a
    non-indexable role is refused by the state DECLARATION guard that
    already exists (`resolve`'s indexable-role check), and everything else
    this module rejects is refused by one named branch of the new `winner:`
    guard. Recording which wall answers, down to the branch, is what keeps a
    cell from starting to pass for the wrong reason.

    The order below is the guard's own precedence — index, then optional,
    then declared type — so a cell that is unindexed AND optional AND
    unrankable belongs to the unindexed branch by decision rather than by
    accident.
    """
    if index is not None and index not in RANKABLE_INDEXES:
        return "reject:declaration"
    if index is None:
        return "reject:unindexed"
    if written.endswith("?"):
        return "reject:optional"
    return "accept" if written in RANKABLE_TYPES else "reject:type"


GRID = [
    pytest.param(index, written, default, id=cell_id)
    for cell_id, index, written, default, _optional in cells()
]


@pytest.mark.parametrize(("index", "written", "default"), GRID)
def test_winner_target_cell(index: str | None, written: str, default: str) -> None:
    verdict = expected_verdict(index, written)
    source = game_source(index, written, default)
    if verdict == "accept":
        check_dsl(source, "winner_target.cardlang")
        return
    with pytest.raises(DiagnosticError) as exc:
        check_dsl(source, "winner_target.cardlang")
    message = exc.value.diagnostic.message
    assert REFUSAL_PHRASES[verdict] in message, message


# --- misuse probes: the sentences the grid's fixed game context cannot reach --
#
# The grid varies the target DECLARATION against a game that is otherwise
# held constant — four seats, teams declared, a `state { }` block present.
# Three plausible wrong sentences vary the game instead, and each must still
# be refused by a named wall rather than reaching a playout.


def test_a_winner_target_naming_a_zone_is_refused_by_the_name_guard() -> None:
    """`winner: highest hand` — a zone, not a state variable.

    The grammar's `winner:` takes a bare NAME, so nothing syntactic stops an
    author naming the zone they think of as their score pile. A zone is not a
    state variable, so the refusal is `_validate_refs`' `n.Winner()` arm — the
    Owner Guard for whether the name names a state variable at ALL — and
    `_check_winner_target` stays silent, which is what its `decl is None`
    early return is for.

    Born green — the wall predates this guard — so: red under: change
    `_validate_refs`' `case n.Winner() if nd.state_var not in cats.state_vars`
    guard to `if False`. The game is then refused by the phase-scope guard
    with a message about a phase-declared variable, which is the wrong
    account of a zone name.
    """
    source = game_source("player", "Integer", "0").replace(
        "winner: highest probe", "winner: highest hand"
    )
    with pytest.raises(DiagnosticError) as exc:
        check_dsl(source, "winner_target.cardlang")
    message = exc.value.diagnostic.message
    assert "winner references unknown variable 'hand'" in message, message


def test_a_team_indexed_target_in_a_teamless_game_is_refused() -> None:
    """`winner: highest probe` on `probe[team]` where the game declares no
    `teams:`.

    The grid's `team` row is accepted, but every one of its games declares
    `teams:`. Drop that clause and the target indexes a role the game has no
    members for — the silent-answer shape of issue #300, which would rank
    over an empty team map.

    The wall that answers is the state DECLARATION guard (`_validate_refs`'
    `n.StateDecl()` team-without-`teams:` arm), NOT this module's guard: the
    declaration is wrong wherever it is read from, so refusing it at the
    `winner:` clause would name the wrong clause. Asserting that guard's own
    wording is what keeps the cell from starting to pass for a different
    reason — every candidate wall here has the word "team" in its message,
    so a bare substring check would be vacuous.

    Born green — the wall predates this guard — so: red under: add `and
    False` to `_validate_refs`' `n.StateDecl()` team-without-`teams:` arm.
    The game is then ACCEPTED outright (`DID NOT RAISE`), which is the
    silent shape this probe exists to keep refused.
    """
    source = game_source("team", "Integer", "0").replace(
        "  teams: [[0, 2], [1, 3]]\n", ""
    )
    with pytest.raises(DiagnosticError) as exc:
        check_dsl(source, "winner_target.cardlang")
    message = exc.value.diagnostic.message
    assert "is indexed by 'team' but the game declares no `teams:`" in message, message


def test_a_target_declared_inside_a_phase_is_refused_by_the_scope_guard() -> None:
    """A `winner:` naming a phase-local declaration.

    The second half of `_check_state_scope`'s class, and the other reason
    `_check_winner_target` returns early rather than speaking: the author has
    already been told the name is not visible at game level, and a second
    diagnostic about its declaration would bury that one.

    Born green — the wall predates this guard — so: red under: change
    `_check_state_scope`'s `if game.winner is not None and
    game.winner.state_var not in top:` to `if False:`. The game is then
    ACCEPTED outright (`DID NOT RAISE`).
    """
    source = game_source("player", "Integer", "0").replace(
        "  phase setup { deal 3 cards from deck to each hand }\n",
        "  phase setup { state { tally[player] : Integer = 0 }\n"
        "                deal 3 cards from deck to each hand }\n",
    ).replace("winner: highest probe", "winner: highest tally")
    with pytest.raises(DiagnosticError) as exc:
        check_dsl(source, "winner_target.cardlang")
    message = exc.value.diagnostic.message
    assert "tally" in message, message
