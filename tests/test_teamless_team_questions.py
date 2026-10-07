"""A game with no `teams:` refuses every sentence that asks about teams.

With no `teams:` the team domain is empty, so a question about it has no
honest answer: `any team where ...` is false, `all teams where ...` is true,
`for each team` never runs, and `team_of(p)` has nothing to look up. None of
those is what the author meant -- the missing declaration is the mistake --
so each is refused at check time, beside the team-indexed `state` and `zone`
declarations resolve already refuses for the same reason.

Completeness ledger (decisions.md "Closed-domain completeness")
---------------------------------------------------------------
property:   in a game with no `teams:`, a sentence that ranges over the
            `team` role or calls a Builtin over `Team` is a check-time
            diagnostic naming the missing `teams:`; with `teams:` declared,
            the same sentence checks clean (`each team simultaneously`
            excepted, which is refused in every game by its own diagnostic).
domain:     {the team-asking sentences} x {a game with `teams:`, one
            without}. A Builtin call is written at three expression positions
            -- a statement's condition, a function body, a `let` binding. A
            state default cannot call a Builtin in any game. And every corpus
            game declaring `teams:`, with that line deleted, is swept: each
            team question it writes is refused.
            The other ways a team reaches a sentence are refused elsewhere: a
            team-indexed `state` or `zone`, and a team literal, which a
            teamless game's empty bound refuses at every operand. A `Team`
            annotation on a parameter, payload or scalar state asks nothing
            and is accepted. A Primitive's own reads of the partition are the
            runtime accessor's, `cardlang.runtime.values.TeamOf`.
registry:   `tests/team_question_axes.py` -- role-ranging nodes from the
            `cardlang.ast.nodes` classes with a `role` field; team Builtins
            from `CALL_SIGS` signatures mentioning `TTeam`. Their sentence
            tables are pinned against both derivations below.
            Team literals: `tests/test_player_literal_range.py`.
does not prove:  that every expression position is walked. Resolve's arm sits
            in the whole-tree walk; the grid samples three positions, and the
            corpus sweep covers every position the partnership games write.
"""

from __future__ import annotations

import random
import re
from dataclasses import replace
from pathlib import Path

import pytest

from cardlang.diagnostics import DiagnosticError
from cardlang.pipeline import check_dsl
from cardlang.runtime.driver import play_game
from cardlang.runtime.errors import OwnerGuardError, ShadowGuardError
from cardlang.runtime.narrowing import engine_facts
from cardlang.runtime.state import RuntimeState, ZoneStore
from cardlang.runtime.values import Seating, TeamOf
from tests.team_question_axes import (
    BUILTIN_CALLS,
    ROLE_SENTENCES,
    Cell,
    cells,
    role_nodes,
    team_builtins,
)

TEMPLATE = """
game G {{
  players: 4
  max_length: 1000
  cards: standard52
  {teams}
  zones {{ deck : Deck }}
  state {{ x : Integer = 0 {state} }}
  phase play {{ {body} }}
  winner: highest x_by_player
}}
{functions}
"""

TEAMS = "teams: [[0, 2], [1, 3]]"
REPO = Path(__file__).resolve().parent.parent


def _source(cell: Cell, teams: str) -> str:
    return TEMPLATE.format(
        teams=teams,
        state=cell.state,
        body=cell.phase_body,
        functions=cell.functions,
    ).replace("x : Integer = 0", "x : Integer = 0  x_by_player[player] : Integer = 0")


def _diagnostics(source: str) -> str | None:
    try:
        check_dsl(source, "t.cardlang")
    except DiagnosticError as exc:
        return str(exc)
    return None


def test_the_sentence_tables_cover_their_derivations() -> None:
    """A new role-ranging node or team Builtin reddens here before it can
    drop out of the grid."""
    assert set(ROLE_SENTENCES) == role_nodes()
    assert set(BUILTIN_CALLS) == team_builtins()


@pytest.mark.parametrize("cell", list(cells()), ids=lambda c: c.id)
def test_a_team_question_without_teams_is_refused(cell: Cell) -> None:
    found = _diagnostics(_source(cell, teams=""))
    assert found is not None
    if cell.member == "EachSimultaneous":
        assert "simultaneous" in found, found
    else:
        assert "declares no `teams:`" in found, found


@pytest.mark.parametrize("cell", list(cells()), ids=lambda c: c.id)
def test_the_same_question_with_teams_checks(cell: Cell) -> None:
    found = _diagnostics(_source(cell, teams=TEAMS))
    if cell.member == "EachSimultaneous":
        assert found is not None and "simultaneous" in found, found
    else:
        assert found is None, found


@pytest.mark.expects_shadow_guard
@pytest.mark.parametrize(
    "cell",
    [c for c in cells() if c.member != "EachSimultaneous"],
    ids=lambda c: c.id,
)
def test_a_team_question_past_the_checker_fails_typed(cell: Cell) -> None:
    """The refusal turned off: the teamed game checks, then loses its
    partition before playing, which is what a leak in the check-time refusal
    would hand the runtime. The question then fails as the engine's gap,
    never as a bare `KeyError` or an empty domain's silent answer."""
    game = check_dsl(_source(cell, teams=TEAMS), "t.cardlang")
    with pytest.raises(ShadowGuardError, match="no `teams:`"):
        play_game(replace(game, teams=()), random.Random(0))


def test_a_primitives_team_read_without_teams_fails_typed() -> None:
    """A Primitive reads the partition through its engine facts, with no
    check-time guard in front, so the accessor is the Owner Guard. The bundle
    is a frozen copy, and the copy keeps the accessor."""
    rs = RuntimeState(Seating(4), ZoneStore((), (0, 1, 2, 3)), random.Random(0))
    facts = engine_facts(rs, None)
    with pytest.raises(OwnerGuardError, match="declares no `teams:`"):
        facts.team_of[0]


@pytest.mark.parametrize("seat", [True, -1, 4, None], ids=repr)
def test_a_non_seat_asking_its_team_fails_typed(seat: object) -> None:
    team_of = TeamOf.partition(((0, 2), (1, 3)))
    assert [team_of[p] for p in range(4)] == [0, 1, 0, 1]
    with pytest.raises(OwnerGuardError, match="not a seat of any team"):
        team_of[seat]


GAMES = REPO / "docs" / "games"
_TEAMS_LINE = re.compile(r"^\s*teams:.*\n", re.M)
_TEAM_QUESTION = re.compile(r"team_of\(|\bany team where\b|\ball teams where\b|\bfor each team\b")


def _team_games() -> list[Path]:
    return [p for p in sorted(GAMES.glob("*.cardlang")) if _TEAMS_LINE.search(p.read_text())]


def test_the_corpus_has_partnership_games() -> None:
    """The sweep below is over a glob; an empty one would pass unearned."""
    assert _team_games()


@pytest.mark.parametrize("path", _team_games(), ids=lambda p: p.stem)
def test_a_partnership_game_without_its_teams_refuses_every_team_question(path: Path) -> None:
    """A half-finished conversion: the corpus game with its `teams:` line
    deleted. Every team question the file writes -- at whatever position
    the game puts it -- is refused, one diagnostic each, beside the walls on
    its team-indexed declarations.

    red under: `resolve._TEAM_CALL_FUNCS` emptied -- every game here then
    reports fewer refusals than team questions."""
    source = path.read_text()
    code = "\n".join(line.split("//", 1)[0] for line in source.splitlines())
    sites = len(_TEAM_QUESTION.findall(code))
    with pytest.raises(DiagnosticError) as exc:
        check_dsl(_TEAMS_LINE.sub("", source), path.name)
    text = "\n".join([exc.value.diagnostic.message, *(getattr(exc.value, "__notes__", []) or [])])
    refused = len(re.findall(r"ranges over teams|asks which team", text))
    assert refused == sites, f"{path.stem}: {refused} of {sites} team questions refused"
