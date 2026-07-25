"""OpenSpiel returns are mapped by the score variable's OWN key domain.

`returns_for` turns a finished game's scores into one return per seat. A score
variable is keyed EITHER by player (`score[player]`) or by team
(`score[team]`) -- a team-keyed score must be handed to every member of that
team, a player-keyed one straight to its seat. Getting this wrong does not
crash: it silently pays the wrong seats, on the target the whole language exists
to hit (CLAUDE.md, "OpenSpiel is the target").

The keying was inferred from the SHAPE of the scores dict --
`set(scores) == set(range(n_players))` -- which is a guess, and it is wrong
exactly when a game's team count equals its player count: a 2-player/2-team or
4-player/4-team game has team keys `{0, 1}` / `{0, 1, 2, 3}` that are
indistinguishable from player keys, so team scores were read as player scores
and returns went to the wrong seats. Nothing about such a game is malformed --
`partnerships: [[1], [0]]` is a perfectly good partition of two seats. The
keying is now read STRUCTURALLY: the `winner:` target's own state declaration
says whether it is indexed by `team`.

Completeness ledger (decisions.md "Closed-domain completeness")
---------------------------------------------------------------
property:   for a game whose `winner:` names score variable V, every seat p
            receives `sign * scores[k(p)]`, where `k` is the identity when V is
            player-indexed and `team_of` when V is team-indexed, and `sign` is
            `RANK_DIR_TO_SIGN[winner.rank_dir]`. The mapping depends only on V's
            declared index -- never on the score dict's key set, which cannot
            distinguish the two when the counts coincide.
domain:     {V player-indexed | V team-indexed} x {team count == player count |
            != player count} x {rank_dir highest | lowest}, plus the `loser:`
            (no `winner:`) form, which has no score variable at all.
registry:   the keying comes from the `winner:` target's `StateDecl.index`
            (`nodes.state_blocks` walks the game-level block and every nested
            phase block -- a winner target may be declared in either); the sign
            axis is `replay.RANK_DIR_TO_SIGN`; `team_of` is built from
            `game.partnerships` exactly as `runtime/driver` builds it.
covered:    the grid below -- every {keying x coincidence} cell with its
            expected returns computed from the game's own structure (the
            authored decision), including the two cells the key-set guess got
            wrong; both signs; and the `loser:` form.
sampled:    the end-to-end path (a real playout reaching `returns_for` through
            `replay.run`) is exercised by the existing
            tests/test_openspiel_replay.py and the per-game proof modules in
            tests/openspiel_ready/; this grid drives `returns_for` directly so
            the score dict is controlled exactly.
residual:   none for the keying itself -- every game that REACHES `returns_for`
            is covered, because the keying axis is binary and both values are
            executed at both count relations. Adjacent, NOT closed here and
            recorded in roadmap.md instead: a `winner:` target that is a SCALAR
            (`winner: highest pot`, no index) never reaches this function at all
            -- it type-checks, then `driver` dies building the score dict
            (`dict(rs.get(target))` on an int) with a bare `TypeError`, the
            wrong currency for a checked game. Run and confirmed while writing
            this. That is a missing checker wall on the `winner:` target, not a
            returns-mapping hole.
"""
from __future__ import annotations

import pytest

from cardlang.openspiel.replay import RANK_DIR_TO_SIGN, returns_for
from cardlang.pipeline import check_dsl
from cardlang.runtime.driver import GameResult


def _team_game(*, players: int, partnerships: str, rank_dir: str = "highest") -> str:
    """A game whose `winner:` names a TEAM-indexed score variable."""
    return (
        "game T {\n"
        f"  players: {players}\n"
        f"  partnerships: {partnerships}\n"
        "  max_length: 20\n"
        "  cards: standard52\n"
        "  ranking: A K Q J 10 9 8 7 6 5 4 3 2\n"
        "  zones { deck : Deck  hand[player] : Hand<player> }\n"
        "  state { won[team] : Integer = 0 }\n"
        "  phase play {\n"
        "    turns t from 0 over all players until (any team where won[team] is 1) {\n"
        "      offer to t one of [pass]\n"
        "    }\n"
        "  }\n"
        f"  winner: {rank_dir} won\n"
        "}\n"
        "move_type pass { effect { won[team_of(actor)] := 1 } }\n"
    )


def _player_game(*, players: int, partnerships: str = "", rank_dir: str = "highest") -> str:
    """A game whose `winner:` names a PLAYER-indexed score variable. The
    `partnerships` argument is deliberately available: a game may declare teams
    and still score by player, which is the mirror of the bug -- the key-set
    guess got this cell right only by coincidence."""
    p_clause = f"  partnerships: {partnerships}\n" if partnerships else ""
    return (
        "game P {\n"
        f"  players: {players}\n"
        f"{p_clause}"
        "  max_length: 20\n"
        "  cards: standard52\n"
        "  ranking: A K Q J 10 9 8 7 6 5 4 3 2\n"
        "  zones { deck : Deck  hand[player] : Hand<player> }\n"
        "  state { score[player] : Integer = 0 }\n"
        "  phase play {\n"
        "    turns t from 0 over all players until (any player where score[player] is 1) {\n"
        "      offer to t one of [pass]\n"
        "    }\n"
        "  }\n"
        f"  winner: {rank_dir} score\n"
        "}\n"
        "move_type pass { effect { score[actor] := 1 } }\n"
    )


# (id, source, players, team_keyed, partnerships-as-tuples, scores)
# `team_keyed` is the AUTHORED decision for the cell -- what the language should
# do, read off the game's `winner:` target declaration by eye, never scraped
# from the implementation under test.
_CASES: list[tuple[str, str, int, bool, tuple[tuple[int, ...], ...], dict[int, int]]] = [
    (
        "player_keyed_no_teams",
        _player_game(players=2), 2, False, (), {0: 10, 1: 20},
    ),
    (
        # The mirror: teams declared, scores still per player, counts coincide.
        # The key-set guess happened to be right here; it must stay right.
        "player_keyed_teams_coincide",
        _player_game(players=2, partnerships="[[0], [1]]"), 2, False,
        ((0,), (1,)), {0: 10, 1: 20},
    ),
    (
        # The corpus shape (bridge/spades/pinochle/tichu): 4 seats, 2 teams.
        "team_keyed_counts_differ",
        _team_game(players=4, partnerships="[[0, 2], [1, 3]]"), 4, True,
        ((0, 2), (1, 3)), {0: 120, 1: 90},
    ),
    (
        # THE BUG: 2 seats, 2 teams -- team keys {0,1} look exactly like player
        # keys, and the partition is deliberately NOT the identity, so a
        # seat-vs-team mix-up changes the answer.
        "team_keyed_2p_2teams",
        _team_game(players=2, partnerships="[[1], [0]]"), 2, True,
        ((1,), (0,)), {0: 10, 1: 20},
    ),
    (
        # THE BUG, wider: 4 seats, 4 singleton teams, reversed.
        "team_keyed_4p_4teams",
        _team_game(players=4, partnerships="[[3], [2], [1], [0]]"), 4, True,
        ((3,), (2,), (1,), (0,)), {0: 10, 1: 20, 2: 30, 3: 40},
    ),
    (
        # The sign axis crossed with the broken cell.
        "team_keyed_2p_2teams_lowest",
        _team_game(players=2, partnerships="[[1], [0]]", rank_dir="lowest"), 2, True,
        ((1,), (0,)), {0: 10, 1: 20},
    ),
]


@pytest.mark.parametrize(
    "cid, source, players, team_keyed, partnerships, scores",
    _CASES,
    ids=[c[0] for c in _CASES],
)
def test_returns_follow_the_score_variables_key_domain(
    cid: str,
    source: str,
    players: int,
    team_keyed: bool,
    partnerships: tuple[tuple[int, ...], ...],
    scores: dict[int, int],
) -> None:
    game = check_dsl(source, f"{cid}.cardlang")
    assert game.partnerships == partnerships, "fixture drift: partnerships mis-parsed"
    sign = RANK_DIR_TO_SIGN[game.winner.rank_dir] if game.winner else 1
    # The expected column, computed from the game's structure and the authored
    # `team_keyed` decision -- not from `returns_for`.
    if team_keyed:
        team_of = {p: ti for ti, members in enumerate(partnerships) for p in members}
        expected = [float(sign * scores[team_of[p]]) for p in range(players)]
    else:
        expected = [float(sign * scores[p]) for p in range(players)]
    got = returns_for(
        game, GameResult(scores=scores, winner=0, loser=None, hands_played=1)
    )
    assert got == expected


def test_loser_game_returns_are_unaffected() -> None:
    """The `loser:` form has no score variable at all, so the keying question
    does not arise: +1 per survivor, -(n-1) for the loser, summing to zero."""
    src = (
        "game L {\n"
        "  players: 3\n"
        "  max_length: 20\n"
        "  cards: standard52\n"
        "  ranking: A K Q J 10 9 8 7 6 5 4 3 2\n"
        "  zones { deck : Deck  hand[player] : Hand<player> }\n"
        "  state { out[player] : Integer = 0 }\n"
        "  phase play {\n"
        "    turns t from 0 over all players until (any player where out[player] is 1) {\n"
        "      offer to t one of [quit]\n"
        "    }\n"
        "  }\n"
        "  loser: the player where out[player] is 1\n"
        "}\n"
        "move_type quit { effect { out[actor] := 1 } }\n"
    )
    game = check_dsl(src, "loser.cardlang")
    got = returns_for(
        game, GameResult(scores={}, winner=None, loser=2, hands_played=1)
    )
    assert got == [1.0, 1.0, -2.0]
    assert abs(sum(got)) < 1e-9
