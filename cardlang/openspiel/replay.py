"""Generalized re-simulation engine: drive ANY fully-kernel game
action-by-action by replaying a recorded action history through ``play_game``.

The OpenSpiel ``State`` is just ``(seed, script, history)``, that seed being
the [[shuffle-seed]] and the Draw Script the outcomes of the first draws where a
resampled world gives them rather than the seed (`generator_for`). Every
query re-runs the game with a :class:`ReplayChooser`
that decodes and returns the recorded actions in order and raises
``ChooserAbort`` at the first decision beyond the history — surfacing the
current decision point with the live [[world]] and the per-player
[[observation-log]]s attached. The chooser makes no RNG calls, so a run is a
pure function of ``seed`` and ``script``.

For a Chance-Free Game the seed reaches nothing: its generator refuses every
draw (`cardlang.runtime.chance`), so a run is a pure function of ``history``
alone and `game.py` gives it a tree with no root chance node.

A :class:`LiveLine` is the same chooser given a continuation: past the recorded
history it asks each seat's [[seat-policy]] instead of pausing, so a person or
an opponent plays on from ``(seed, history)`` through the positions the
adapter's tree holds.

Contract
--------
Assumes: a checked game whose action space `ActionSpace.for_game` derives.
Establishes: one decoder of recorded action ids, whether the run then pauses
or asks a Seat Policy; one rule choosing the generator a ``(path, seed,
script)`` runs under (`generator_for`); a Seat Policy asked at a position is handed the
[[seat-view]] derived there while every phase frame stands, and its answer is
one of the legal action ids or the line refuses it; a caller passing
``picks`` receives one `RecordedPick` per recorded pick, taken before the pick is
matched, so a pick its position does not offer still leaves its offer behind,
with the decider's Seat View derived inside the Chooser call.
Illegal after: a second site choosing a game's generator; a continuation that
draws from the game's generator; a policy asked again once it has raised in
the same run; reading the game's declarations to derive its result --
`returns_for` translates the driver's `GameResult`, whose seat scores are
keyed once (`driver.seat_scores_of`)."""

from __future__ import annotations

import random
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from functools import cache
from pathlib import Path
from typing import Any, cast

from cardlang.ast import nodes as n
from cardlang.openspiel.encoding import ActionSpace
from cardlang.openspiel.infostate import SeatView, derive
from cardlang.openspiel.seat_policy import SeatPolicy
from cardlang.pipeline import check_source
from cardlang.runtime.chance import (
    Draw,
    Outcome,
    RefusingRandom,
    ScriptedRandom,
    is_chance_free,
)
from cardlang.runtime.errors import ShadowGuardError
from cardlang.runtime.chooser import sequential_decisions
from cardlang.runtime.driver import GameResult, play_game
from cardlang.runtime.state import ChooserAbort, RuntimeState


@cache
def load(path_str: str) -> tuple[n.Game, ActionSpace]:
    """Parse + check a game and derive its action space (cached per path)."""
    game = check_source(Path(path_str))
    return game, ActionSpace.for_game(game)


@cache
def chance_free(path_str: str) -> bool:
    """Whether the game at `path_str` consumes no randomness
    (`cardlang.runtime.chance`), cached per path beside its action space.

    The ONE place a consumer asks. `game.py` reads it to decide whether the
    tree carries a root chance node, and `run` below reads it to decide which
    generator the game gets; deriving it twice would let the tree shape and the
    guard disagree about the same game."""
    game, _ = load(path_str)
    return is_chance_free(game)


@dataclass
class DecisionNode:
    """A game state where a seat must choose — the literature's decision node,
    one of the [[game-tree-node-kinds]].

    The DYNAMIC occurrence. A *decision point* is the static thing: one
    [[chooser]] call site in the interpreter. The two are not the same concept
    and do not share a word (the glossary's OpenSpiel boundary).
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


@dataclass(frozen=True)
class RecordedPick:
    """What one recorded pick was offered: the index of the Chooser call it
    belongs to, the seat deciding it, the legal action ids its position
    offers, sorted ascending as `DecisionNode.legal` is, and what the deciding
    seat knew as it was asked."""

    call: int
    decider: int
    legal: tuple[int, ...]
    view: SeatView


class ReplayChooser:
    """Returns recorded actions in order; aborts at the first un-recorded one.
    A chooser call requesting ``k`` cards decomposes into ``k`` sequential
    actions — `chooser.sequential_decisions`, the decomposition every route
    that walks a call one card at a time reads — so multi-card selections stay
    in the same global action space.

    Each consumed card enters the actor's log as its ``("chose", ...)`` event
    at the moment of the draw (`chooser.decide`'s recorder), so a pause
    *inside* a multi-card call surfaces the cards already taken: without them
    distinct decision nodes would collapse into one information state (a
    perfect-recall violation). A native playout records the same events, one
    per pick, so the log is the same whichever route made the picks.

    ``beyond`` is the continuation past the recorded history. Without one the
    chooser pauses the run; with one it asks ``beyond(decider, legal)`` for an
    action id, refuses an answer that is not one of ``legal``, and appends the
    id to ``taken`` as the pick is made. A continuation that raises is not
    asked again in the same run: `driver.run_phase` runs `after_each` on the way
    out of an iteration, exceptions included, and an `after_each` that decides
    would reach it a second time while the run unwinds. ``deciders`` holds the
    seat each pick was made for, recorded and live alike; ``picks``, when
    given, receives a `RecordedPick` for each recorded pick, and ``on_pick``
    hears each recorded pick's index and seat as it is consumed."""

    def __init__(
        self,
        space: ActionSpace,
        history: tuple[int, ...],
        beyond: Callable[[int, list[int]], int] | None = None,
        taken: list[int] | None = None,
        picks: list[RecordedPick] | None = None,
        view: Callable[[int], SeatView] | None = None,
        on_pick: Callable[[int, int], None] | None = None,
    ) -> None:
        self.space = space
        self.on_pick = on_pick
        self.history = history
        self.beyond = beyond
        self.cursor = 0
        self.taken: list[int] = [] if taken is None else taken
        self.deciders: list[int] = []
        self.picks = picks
        self.view = view
        self.calls = 0
        self._raised: BaseException | None = None

    def __call__(self, player: int, candidates: list[Any], k: int) -> list[Any]:
        call = self.calls
        self.calls += 1

        def decide(actor: int, pool: list[Any]) -> Any:
            if self.cursor < len(self.history):
                index = self.cursor
                aid = self.history[index]
                self.cursor += 1
                self.deciders.append(actor)
                if self.on_pick is not None:
                    self.on_pick(index, actor)
                if self.picks is not None:
                    assert self.view is not None, "recording picks needs a Seat View to record"
                    self.picks.append(
                        RecordedPick(call, actor, tuple(self._legal(pool)), self.view(actor))
                    )
                # `type`, not `isinstance`: a flag passes `decode`'s range test
                # as id 0 or 1.
                if type(aid) is not int:
                    raise HistoryMismatch(f"recorded pick {index}: {aid!r} is not an action id")
                try:
                    return self.space.match(aid, pool)
                except ValueError as exc:
                    raise HistoryMismatch(f"recorded pick {index}: {exc}") from exc
            legal = self._legal(pool)
            if self.beyond is None:
                raise ChooserAbort(actor, legal)
            if self._raised is not None:
                raise self._raised
            try:
                aid = self.beyond(actor, legal)
            except BaseException as signal:
                self._raised = signal
                raise
            if type(aid) is not int or aid not in legal:
                raise AssertionError(
                    f"the Seat Policy for seat {actor} answered {aid!r}, which is not "
                    f"one of the legal action ids {legal}"
                )
            self.taken.append(aid)
            self.deciders.append(actor)
            return self.space.match(aid, pool)

        return sequential_decisions(player, candidates, k, decide)

    def _legal(self, pool: list[Any]) -> list[int]:
        ids = [self.space.encode(c) for c in pool]
        combos = [i for i in ids if self.space.block_of(i) == "combination"]
        if len(set(combos)) != len(combos):
            # Shadow Guard of the combo codecs' injectivity (the Owner is the
            # engine's codec, `primitives.ComboCodec`, whose identity is the
            # card-set plus the wildcard value): two live combination
            # candidates sharing an id would collapse into one legal action,
            # and the second would be a play the chooser offers that no
            # pyspiel history can ever pick. The card block is exempt by
            # design: a deck declared with `copies` offers identical cards
            # that ARE one action, and the set below folds them.
            shared = sorted({i for i in combos if combos.count(i) > 1})
            raise ShadowGuardError(
                "primitives.ComboCodec (the engine's combo codec)",
                f"two combination candidates of one decision share action id(s) {shared}",
            )
        return sorted(set(ids))


# The grammar's RANK_DIR terminal (`cardlang.lark`, "lowest" | "highest"),
# mapped to the sign that makes a higher return the better outcome.
# Exhaustive by construction: `returns_for` below raises loudly on any key
# not present here, and `test_rank_dir_set_is_pinned`
# (tests/test_comprehension_aggregators.py) reconciles this set against the
# grammar terminal so a new RANK_DIR token cannot land uncovered here.
RANK_DIR_TO_SIGN: dict[str, float] = {"highest": 1.0, "lowest": -1.0}


def returns_for(game: n.Game, result: GameResult) -> list[float]:
    """General-sum returns from the game's own result (SP1 spec, component 6):
    each seat's score (`GameResult.seat_scores`, its team's for a team-keyed
    target), sign-adjusted so higher is better (negated for `lowest`
    winners). An elimination (`loser:`) game returns +1 per survivor and
    -(n-1) for the loser, which sums to zero. A translation of the driver's
    result, never a second reading of the game's declarations."""
    n_players = game.players.count
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
    return [sign * score for score in result.seat_scores]


def generator_for(
    path_str: str,
    seed: int,
    script: tuple[Outcome, ...] = (),
    on_draw: Callable[[Draw], None] | None = None,
    construct: Callable[[int, str, list[Any]], Outcome | None] | None = None,
) -> random.Random:
    """The generator the game at `path_str` plays under for `seed`, its first
    draws taking `script`'s outcomes.

    A Chance-Free Game gets one that refuses every draw; every other game gets
    a `ScriptedRandom`, which only the game draws from and which, under an
    empty script, deals exactly as `random.Random(seed)` does. The choice lives
    here because every route that plays a ``(path, seed, script)`` must make it
    the same way, or one triple would name two deals: `run` reads it, and so
    does every `LiveLine`. `construct` answers the draws past the Draw Script as
    they happen (`cardlang.openspiel.resample` building a Constructed World), and
    `on_draw` hears each draw made. A refusing generator belongs where no chooser draws
    either — the default `random_chooser`'s draws are a policy's, not the
    game's, and would make the refusal fire on a playout that is behaving
    correctly. A Draw Script for a game that never draws would name outcomes no
    draw takes, so it is refused rather than ignored."""
    if chance_free(path_str):
        if script or construct is not None:
            raise HistoryMismatch(
                f"{path_str} draws nothing, so a scripted or constructed draw "
                f"outcome has no draw to give it to"
            )
        return RefusingRandom(seed)
    return ScriptedRandom(seed, script, on_draw, construct)


class HistoryMismatch(ValueError):
    """A recorded history that does not replay in the game it is replayed in:
    a pick that is not an action id, a pick its position does not offer,
    picks left over when the game ends, or a Draw Script for a game that draws
    nothing.

    Addressed to whoever supplied the history (a saved session, a harness, a
    Constructed World), not
    to the game author: the game is sound, and the record is not its own."""


@dataclass(frozen=True)
class LiveEnd:
    """How a live line ended: the game's returns, and each seat's view at the
    terminal position (none when the game ended before any decision, since the
    engine then hands over no world to derive from)."""

    returns: list[float]
    views: dict[int, SeatView]


class LiveLine:
    """A line of play from ``(seed, history)``: the recorded picks replayed, then
    each seat's Seat Policy asked at every further decision.

    ``history`` is the recorded picks followed by every pick taken live, in the
    order taken, so it holds every pick made even when a policy's signal or a
    refusal ends the run; ``deciders`` names the seat each pick was made for.
    Played again, a line replays whatever ``history`` holds, which is how a
    line resumes, and how a truncated one takes a pick back.

    A policy is handed the Decider's Seat View derived inside the Chooser call,
    which is the view a `DecisionNode` at the same position derives."""

    def __init__(self, path_str: str, seed: int, prefix: Sequence[int] = ()) -> None:
        self.path = path_str
        self.seed = seed
        self.history: list[int] = list(prefix)
        self.deciders: list[int] = []

    def play(self, policies: Mapping[int, SeatPolicy]) -> LiveEnd:
        game, space = load(self.path)
        logs: dict[int, list[tuple[Any, ...]]] = {p: [] for p in range(game.players.count)}
        world: list[RuntimeState] = []
        views: dict[int, SeatView] = {}

        def observe(player: int, event: tuple[Any, ...]) -> None:
            logs[player].append(event)

        def ask(decider: int, legal: list[int]) -> int:
            return policies[decider](derive(decider, world[0], logs[decider]), legal)

        def trace(event: str, _data: Any) -> None:
            # `play_game` emits `game_end` before it pops the game's own frame;
            # a view taken after it returns would hold no state variable.
            if event == "game_end" and world:
                views.update({seat: derive(seat, world[0], log) for seat, log in logs.items()})

        # The chooser appends each live pick to this line's own history as the
        # pick is made, so a policy reading the line mid-run sees every pick
        # before it.
        chooser = ReplayChooser(space, tuple(self.history), ask, self.history)
        self.deciders = chooser.deciders
        result = play_game(
            game,
            generator_for(self.path, self.seed),
            trace,
            chooser=chooser,
            observer=observe,
            on_first_decision=world.append,
        )
        if chooser.cursor < len(chooser.history):
            raise HistoryMismatch(
                f"the game ended after {chooser.cursor} of the "
                f"{len(chooser.history)} recorded picks; the rest run past the end"
            )
        return LiveEnd(returns_for(game, result), views)


@dataclass(frozen=True)
class Seen:
    """An observation event as a run delivered it: the seat it reached, and
    the event."""

    player: int
    event: tuple[Any, ...]


@dataclass(frozen=True)
class Drawn:
    """A draw as a run made it."""

    draw: Draw


@dataclass(frozen=True)
class Picked:
    """A recorded pick as a run consumed it: its index in the history, and the
    seat it was made for."""

    index: int
    decider: int


# One moment of a run, as `run`'s `listen` hears it: every observation event,
# every draw and every recorded pick, in the order the run made them.
Moment = Seen | Drawn | Picked


def run(
    path_str: str,
    seed: int,
    history: tuple[int, ...],
    on_first_decision: Callable[[RuntimeState], None] | None = None,
    picks: list[RecordedPick] | None = None,
    script: tuple[Outcome, ...] = (),
    listen: Callable[[Moment], None] | None = None,
    construct: Callable[[int, str, list[Any]], Outcome | None] | None = None,
    beyond: Callable[[int, list[int]], int] | None = None,
) -> DecisionNode | TerminalNode:
    """Replay ``history`` under ``seed`` and ``script``; return the next
    decision or the result.

    ``picks`` receives what each recorded pick was offered (`ReplayChooser`);
    ``listen`` hears every `Moment` of the run as it happens; ``construct``
    answers the draws past the Draw Script (`generator_for`); ``beyond``, when
    given, is asked for each pick past the history instead of pausing there,
    and pauses the run itself by raising `ChooserAbort`."""
    game, space = load(path_str)
    logs: dict[int, list[tuple[Any, ...]]] = {
        p: [] for p in range(game.players.count)
    }

    def observe(player: int, event: tuple[Any, ...]) -> None:
        logs[player].append(event)
        if listen is not None:
            listen(Seen(player, event))

    world: list[RuntimeState] = []

    def first_decision(rs: RuntimeState) -> None:
        world.append(rs)
        if on_first_decision is not None:
            on_first_decision(rs)

    chooser = ReplayChooser(
        space,
        history,
        beyond=beyond,
        picks=picks,
        view=lambda seat: derive(seat, world[0], logs[seat]),
        on_pick=None if listen is None else (lambda i, seat: listen(Picked(i, seat))),
    )
    try:
        result = play_game(
            game,
            generator_for(
                path_str,
                seed,
                script,
                None if listen is None else (lambda draw: listen(Drawn(draw))),
                construct,
            ),
            chooser=chooser,
            observer=observe,
            on_first_decision=first_decision if picks is not None else on_first_decision,
        )
    except ChooserAbort as abort:
        assert abort.rs is not None
        return DecisionNode(abort.player, list(cast("list[int]", abort.legal)), abort.rs, logs)
    return TerminalNode(returns_for(game, result))
