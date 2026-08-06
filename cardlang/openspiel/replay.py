"""Generalized re-simulation engine: drive ANY fully-kernel game
action-by-action by replaying a recorded action history through ``play_game``.

The OpenSpiel ``State`` is just ``(seed, history)``. Every query re-runs the
game with a :class:`ReplayChooser` that decodes and returns the recorded
actions in order and raises ``ChooserAbort`` at the first decision beyond the
history — surfacing the current decision point with the live world and the
per-player observation logs attached. The chooser makes no RNG calls, so a run
is a pure function of ``seed``."""

from __future__ import annotations

import random
from collections.abc import Callable
from dataclasses import dataclass
from functools import cache
from pathlib import Path
from typing import Any, cast

from cardlang.ast import nodes as n
from cardlang.domains import Role, role_of
from cardlang.openspiel.encoding import ActionSpace
from cardlang.pipeline import check_source
from cardlang.runtime.driver import GameResult, play_game
from cardlang.runtime.observe import render
from cardlang.runtime.state import ChooserAbort, RuntimeState


@cache
def load(path_str: str) -> tuple[n.Game, ActionSpace]:
    """Parse + check a game and derive its action space (cached per path)."""
    game = check_source(Path(path_str))
    return game, ActionSpace.for_game(game)


@dataclass
class DecisionNode:
    """A game state where a seat must choose — the literature's decision node.

    The DYNAMIC occurrence. A *decision point* is the static thing: one chooser
    call site in the interpreter. The two are not the same concept and do not
    share a word (glossary section 4).
    """

    player: int
    legal: list[int]  # global action ids, sorted ascending
    rs: RuntimeState  # the live world at the decision
    obs_logs: dict[int, list[tuple[Any, ...]]]  # per-player observation logs


@dataclass
class TerminalNode:
    """A completed game — the literature's terminal node.

    The suffix is deliberate twice over: the single-word form collides with the
    grammar's lexer terminology, and the two-word scheme leaves room for the
    `SimultaneousNode` a native simultaneous-move export would add.
    """

    returns: list[float]


class ReplayChooser:
    """Returns recorded actions in order; aborts at the first un-recorded one.
    A chooser call requesting ``k`` picks decomposes into ``k`` sequential
    actions, so multi-card selections stay in the same global action space.

    Each consumed pick is emitted to the actor as a ``("chose", ...)`` event at
    the moment of the draw. The runtime's own aggregate `chose` (fired when the
    whole call returns) cannot cover a pause *inside* a multi-pick call — the
    picks already made would be invisible, collapsing distinct decision nodes
    into one information state (a perfect-recall violation). Per-draw emission
    keeps every replayed pick in the actor's log, and the log append-only
    across ``(seed, history)`` extensions; the runtime aggregate that follows a
    completed call is kept (it is the canonical event native playouts emit)."""

    def __init__(
        self,
        space: ActionSpace,
        history: tuple[int, ...],
        emit: Callable[[int, tuple[Any, ...]], None],
    ) -> None:
        self.space = space
        self.history = history
        self.emit = emit
        self.cursor = 0

    def __call__(self, player: int, candidates: list[Any], k: int) -> list[Any]:
        pool = list(candidates)
        picked: list[Any] = []
        for _ in range(k):
            if self.cursor >= len(self.history):
                legal = sorted({self.space.encode(c) for c in pool})
                raise ChooserAbort(player, legal)
            aid = self.history[self.cursor]
            self.cursor += 1
            choice = self.space.match(aid, pool)  # must be among the candidates
            pool.remove(choice)
            picked.append(choice)
            self.emit(player, ("chose", render(choice)))
        return picked


# The grammar's RANK_DIR terminal (`cardlang.lark`, "lowest" | "highest"),
# mapped to the sign that makes a higher return the better outcome.
# Exhaustive by construction: `returns_for` below raises loudly on any key
# not present here, and `test_rank_dir_set_is_pinned`
# (tests/test_comprehension_aggregators.py) reconciles this set against the
# grammar terminal so a new RANK_DIR token cannot land uncovered here.
RANK_DIR_TO_SIGN: dict[str, float] = {"highest": 1.0, "lowest": -1.0}


# The index roles the seat -> score-key mapping below knows how to invert.
# Reconciled against `domains.ZONE_INDEX_ROLES` by
# tests/test_openspiel_returns_keying.py, so a new seat-anchored role has to be
# handled here rather than silently read as player keying.
_RETURNS_KEYED_ROLES: frozenset[str] = frozenset({"player", "team"})


def _winner_target_index(game: n.Game) -> str | None:
    """The `winner:` target's declared index role (`score[team]` -> `"team"`),
    or None when it is unindexed or names no declaration.

    The walk covers everywhere state may be declared (`nodes.state_blocks`): a
    winner target may be declared in a nested phase block, not only at game
    level."""
    assert game.winner is not None  # callers check; keeps mypy and intent aligned
    target = game.winner.target
    for block in n.state_blocks(game):
        for decl in block.decls:
            if decl.name == target:
                return decl.index
    return None


def _score_key_by_seat(game: n.Game, n_players: int) -> list[int]:
    """Seat -> the key that seat's score lives under in `result.scores`.

    `driver` builds that dict from the `winner:` target (`rs.get(target)`), so
    the variable's DECLARED index is the keying. It is never inferred from the
    shape of the dict, which cannot distinguish the two: a game whose team count
    equals its player count has team keys (`{0, 1}`) indistinguishable from
    player keys, so a key-set test read team scores as player scores and paid the
    wrong seats — silently, nothing about `teams: [[1], [0]]` on two seats
    being malformed.

    Dispatched over the role and LOUD for one it does not handle, the same
    contract as `domains.zone_observer_key`. `ZONE_INDEX_ROLES` is DERIVED from
    the domain registry (a row with a `zone_key_of`), so the day a new
    seat-anchored role is added, resolve and the zone store accept and key it —
    and reading it here as player-keyed would silently pay the wrong seats again.
    That is precisely the per-consumer role drift `zone_key_of` was introduced to
    end (domains.py), so an unhandled role raises instead of defaulting."""
    name = _winner_target_index(game)
    # UNINDEXED is answered before classification, and the two must not be
    # folded together: `role_of` returns None both for "no index" and for "a
    # name the registry does not know", so a single `role is None` arm would
    # send an unrecognized index down the player branch — silently reading
    # those seats' returns as player-keyed, which is the exact failure the
    # raise below exists to prevent.
    if name is None:
        # A scalar target never reaches here at all (`driver` fails building a
        # dict from an int first; issue #153), so this is the unindexed case:
        # the seat IS its own key.
        return list(range(n_players))
    role = role_of(name)
    # An ALLOW-LIST: the arms below enumerate what this mapping inverts, the
    # fallback RAISES for anything else, and `_RETURNS_KEYED_ROLES` is
    # reconciled against ZONE_INDEX_ROLES by
    # tests/test_openspiel_returns_keying.py. Adding a role reddens that pin.
    if role is Role.PLAYER:
        return list(range(n_players))
    if role is Role.TEAM:  # the second arm of the same allow-list
        team_of = {
            p: ti for ti, members in enumerate(game.teams) for p in members
        }
        return [team_of[p] for p in range(n_players)]
    raise AssertionError(
        f"returns_for: the `winner:` target is indexed by '{name}', which this "
        f"mapping does not invert (it handles {sorted(_RETURNS_KEYED_ROLES)}) — "
        f"those seats' returns would be silently read as player-keyed. Add the "
        f"role here, mapping a seat to its key as that domain's `zone_key_of` "
        f"does (cardlang/domains.py)"
    )


def returns_for(game: n.Game, result: GameResult) -> list[float]:
    """General-sum returns from the game's own result (SP1 spec, component 6):
    true scores, sign-adjusted so higher is better (negated for `lowest`
    winners); team-keyed scores map each player to their team's score. An
    elimination (`loser:`) game returns +1 per survivor and -(n-1) for the
    loser, which sums to zero."""
    n_players = game.players.low
    if game.winner is None:
        assert result.loser is not None
        return [
            float(-(n_players - 1)) if p == result.loser else 1.0
            for p in range(n_players)
        ]
    if game.winner.rank_dir not in RANK_DIR_TO_SIGN:
        # Internal invariant, not a user diagnostic: the grammar's RANK_DIR
        # terminal and this mapping are out of sync.
        raise AssertionError(
            f"returns_for: unhandled RANK_DIR value {game.winner.rank_dir!r} — add "
            "it to RANK_DIR_TO_SIGN"
        )
    sign = RANK_DIR_TO_SIGN[game.winner.rank_dir]
    scores = result.scores
    # One score per KEY of the target's index domain — its own seat for a
    # player-indexed score, its team's for a team-indexed one (Bridge, Spades),
    # so every member of a team receives that team's score.
    return [sign * scores[key] for key in _score_key_by_seat(game, n_players)]


def run(
    path_str: str,
    seed: int,
    history: tuple[int, ...],
    on_first_decision: Callable[[RuntimeState], None] | None = None,
) -> DecisionNode | TerminalNode:
    """Replay ``history`` under ``seed``; return the next decision or the result."""
    game, space = load(path_str)
    logs: dict[int, list[tuple[Any, ...]]] = {
        p: [] for p in range(game.players.low)
    }

    def observe(player: int, event: tuple[Any, ...]) -> None:
        logs[player].append(event)

    chooser = ReplayChooser(space, history, observe)
    try:
        result = play_game(
            game,
            random.Random(seed),
            chooser=chooser,
            observer=observe,
            on_first_decision=on_first_decision,
        )
    except ChooserAbort as abort:
        assert abort.rs is not None
        return DecisionNode(abort.player, list(cast("list[int]", abort.legal)), abort.rs, logs)
    return TerminalNode(returns_for(game, result))
