"""A `teams:` declaration partitions the game's seats.

`teams: [[0, 2], [1, 3]]` says who partners whom, and every consumer reads it
as a total, disjoint map from seat to team — built, identically, at
`runtime/driver.py` and `openspiel/replay.py` as
`{p: ti for ti, members in enumerate(game.teams) for p in members}`. Nothing
checked that the declaration is one. Three malformations were accepted and
played to completion (issue #155), and the dict comprehension makes the worst
of them silent: a seat listed in two teams is assigned the LATER one, because
a later key overwrites an earlier one.

What ranks this above a mistyped declaration is that it reaches the
information sets. A team's zone family asks `domains.zone_observer_key`
whether an observer owns an instance, and for a team that is
`rs.team_of.get(observer)` — so a seat in no team is silently a NON-OWNER of
every team family, and a zone type whose owner projection differs from its
others projection (`Hand`, `HiddenPile`, …) silently shows that seat the
count-only view of its own team's zone. The readiness proofs cannot catch
it: `tests/openspiel_ready/partition.py` asks the same
`zone_observer_key`, so oracle and runtime agree on the same wrong owner and
the soundness matrix stays green. That is the vacuously-green class
(CLAUDE.md), and it is why this guard has to sit at the declaration — no
downstream oracle can see it.

Completeness ledger (decisions.md "Closed-domain completeness")
---------------------------------------------------------------
property:   a `teams:` declaration is accepted iff it partitions the game's
            seats — every seat `0 <= s < count` appears in exactly one team,
            and no team names a non-seat. A game declaring no `teams:` is
            unaffected.
domain:     {candidate `teams:` value} x {`players:` shape}. The candidate
            axis is every way the partition property can be satisfied or
            broken; the shape axis is the reachable combinations of the
            three questions `PlayersSpec` answers about itself — written as
            a range, count actually varies, bounds well formed — NOT the two
            surface spellings, which cannot express a degenerate
            `players: 4..4` (written as a range, denotes four fixed seats).
registry:   `tests/teams_axes.py` derives both axes in code. The candidate
            axis is CLASSIFIED by `teams_axes.classify`, the one place the
            partition property is spelled out, which computes each cell's
            label from the value rather than trusting its name — that is
            not decoration: the four clauses are not independent at a fixed
            seat count (breaking one usually leaves a seat uncovered too),
            and the four candidates written to isolate a clause each had to
            be derived by running the classifier until it reported exactly
            one. Hand-naming them would have shipped four cells claiming to
            isolate a clause while each tested two. The shape axis reads
            `n.PlayersSpec`'s own `is_range` discriminator, asserted against
            the node's fields so a third form reddens it.
covered:    the grid below — `teams_axes.cells()` x `PLAYERS_SHAPES`,
            `test_teams_cell`, 20 rows. Each rejecting row asserts the
            diagnostic names the specific seat at fault, so a guard that
            fires for the right cell with an unusable message fails.
sampled:    team ARITY and COUNT are sampled, not crossed: the candidates
            include a one-team game and multi-team games, but the property
            is per-seat and does not vary with how many teams there are.
            Member magnitude is sampled at one out-of-range value; the
            check is `s < count`, so 5 and 999999 take the same branch.
residual:   cells on this surface that this ledger does NOT close, each
            with its guard and its record:
            - `team_of(p)` and the thirteen primitives reading
              `facts.team_of[p]` raise a bare `KeyError` rather than the
              runtime's own error, in a game that declares no `teams:`
              (issue #299); guard: none — this guard makes the seat-in-no-team
              trigger unreachable for a game that DOES declare teams, but
              the teamless trigger survives it.
            - a teamless game's `any team where` is silently `False`,
              `all teams where` silently vacuously true, and `for each team`
              runs zero iterations (issue #300); guard: none.
            - `teams:` beside `pieces:`/`board:` is accepted with no gate
              and no corpus witness. NOT guarded and NOT filed: a
              team-partnered board game is a coherent thing to write and
              nothing about it is known to be wrong — this is an
              unexercised cell, not a defect (R4, this ledger owns the
              record).
            - which seat count a range `players:` game's teams must cover
              is genuinely undecided (issue #296), so this grid does NOT
              guess it: the combination is REFUSED rather than given a
              meaning, and the refusal relaxes when #296 rules. Guard: the
              range rows below.
            - a `winner:` target that is unindexed, or indexed but declared
              with a type no game can be ranked by, is the sibling defect on
              the other declaration clause (issue #153); guard: none yet —
              it is its own change because 124 fixture games in this suite
              declare one.
"""

from __future__ import annotations

import pytest

from cardlang.diagnostics import DiagnosticError
from cardlang.pipeline import check_dsl
from tests.teams_axes import PLAYERS_CLAUSES, PLAYERS_SHAPES, cells

SEAT_COUNT = 4


def game_source(players: str, teams: tuple[tuple[int, ...], ...]) -> str:
    clause = ""
    if teams:
        body = ", ".join("[" + ", ".join(str(s) for s in t) + "]" for t in teams)
        clause = f"  teams: [{body}]\n"
    return (
        "game Teams {\n"
        f"  {players}\n"
        "  direction: clockwise\n"
        "  max_length: 40\n"
        f"{clause}"
        "  cards: standard52\n"
        "  ranking: A K Q J 10 9 8 7 6 5 4 3 2\n"
        "  zones { deck : Deck  hand[player] : Hand<player> }\n"
        "  state { score[player] : Integer = 0  done : Boolean = false }\n"
        "  phase setup { deal 3 cards from deck to each hand }\n"
        "  phase play {\n"
        "    turns t from 0 over all players until done {\n"
        "      offer to t one of [stop]\n"
        "    }\n"
        "  }\n"
        "  winner: highest score\n"
        "}\n"
        "move_type stop { effect { done := true } }\n"
    )


GRID = [
    pytest.param(shape, name, teams, label, id=f"{shape}__{name}")
    for shape in PLAYERS_SHAPES
    for name, teams, label in cells(SEAT_COUNT)
]


@pytest.mark.parametrize(("shape", "name", "teams", "label"), GRID)
def test_teams_cell(
    shape: str, name: str, teams: tuple[tuple[int, ...], ...], label: str
) -> None:
    source = game_source(PLAYERS_CLAUSES[shape], teams)
    # A MALFORMED `players:` is typecheck's diagnostic to give, and this
    # guard must stay silent so the author is sent to the clause that is
    # actually wrong rather than to a partition complaint derived from it.
    if shape.startswith("malformed"):
        message = _reject(source)
        assert "player" in message and "teams" not in message, message
        return
    # A game declaring no `teams:` has nothing to partition, whatever its
    # player count: the guard must not fire on the 25 corpus games that
    # declare none.
    if label == "absent":
        check_dsl(source, "teams.cardlang")
        return
    # A count that VARIES has no fixed seat set for a fixed team list to
    # cover, and which count it WOULD have to cover is undecided (issue
    # #296). Refused rather than given a meaning. A degenerate range
    # (`players: 4..4`) does NOT vary and is an ordinary fixed game.
    if shape == "varying_range":
        message = _reject(source)
        assert "variable player count" in message, message
        return
    if label == "partition":
        check_dsl(source, "teams.cardlang")
        return
    message = _reject(source)
    # The diagnostic must name the seat at fault: "the teams are malformed"
    # sends a designer back to re-read a list they already believe is right.
    offenders = _offending_seats(teams, label)
    assert offenders, f"cell {name} classified {label} with no offending seat"
    assert any(f"seat {s}" in message for s in offenders), message


def _reject(source: str) -> str:
    with pytest.raises(DiagnosticError) as exc:
        check_dsl(source, "teams.cardlang")
    return exc.value.diagnostic.message


def _offending_seats(
    teams: tuple[tuple[int, ...], ...], label: str
) -> tuple[int, ...]:
    from tests.teams_axes import classify

    verdict = classify(teams, SEAT_COUNT)
    return (
        verdict.out_of_range
        + verdict.repeated_within
        + verdict.repeated_across
        + verdict.missing
    )
