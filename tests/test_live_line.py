"""A line played live past a recorded prefix, pinned against the adapter's replay.

property:        A line of play that replays recorded picks and then asks each
                 seat's Seat Policy reaches the positions the adapter's replay
                 reaches from the same seed and history: at every probed pick the
                 same Decider is asked, over the same legal action ids, holding
                 the Seat View the adapter derives there in its zones and its
                 observation log. The policy is handed that view while the phase
                 frames still stand, so it carries the phase-local state variables
                 a node has lost. A line cut at any pick and played again with the
                 same policies reaches the same line. The line refuses an answer
                 that is not one of the legal action ids, a recorded pick the
                 position does not offer, recorded picks left over when the game
                 ends, and a call for more picks than it offers. A policy that
                 raises ends the line with every pick before it kept, and is not
                 asked again while the run unwinds.
domain:          Positions: one uniform line per registered game at `_SEED`,
                 compared at each pick `_POSITIONS` names that the line reaches,
                 and at every pick of Hearts through `_HEARTS_DEEP`, which is
                 past its first two hands. Cuts: `_CUTS` of each registered game's
                 line. Answers a policy may wrongly give: `_WRONG_ANSWERS`. The
                 generator rule: every registered game. The per-pick refusal of
                 an over-long call: every route that reads a call one pick at a
                 time (a live line, the adapter's replay), beside the per-call
                 uniform chooser. Fixture games stand in for the shapes no
                 registered game has: a call for more cards than the pool holds,
                 a game with no decision, a line refused at its `max_length`, and
                 a decision inside `after_each`.
registry:        games: `cardlang.openspiel.registry.GAMES`; the generator rule:
                 `cardlang.openspiel.replay.generator_for`, over
                 `cardlang.runtime.chance.is_chance_free`; policies:
                 `cardlang.openspiel.seat_policy`; the decomposition both routes
                 read: `cardlang.runtime.chooser.sequential_decisions`; the
                 adapter's own agreement with pyspiel: tests/openspiel_ready/harness.py.
does not prove:  The decomposition. Both routes read `sequential_decisions` and
                 `ActionSpace.match`, so a fault in either moves them alike; what
                 the comparison discriminates is the live extension and the
                 generator discipline. The state variables past Hearts: a node
                 has popped its phase frames and run `after_each` (issue #612),
                 so the state is compared on Hearts alone, as a strict expected
                 failure. A decision inside `after_each`, where a node names the
                 wrong decision (issue #612): no registered game has one. Lines
                 under any policy but the uniform one, and positions outside the
                 sampled set.
"""

from __future__ import annotations

import random
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest

from cardlang.openspiel import replay
from cardlang.openspiel.infostate import SeatView, derive
from cardlang.openspiel.registry import GAMES
from cardlang.openspiel.replay import (
    DecisionNode,
    HistoryMismatch,
    LiveLine,
    ReplayChooser,
    TerminalNode,
    chance_free,
    generator_for,
    load,
    run,
)
from cardlang.openspiel.seat_policy import SeatPolicy, UniformSeatPolicy
from cardlang.runtime.chance import RefusingRandom
from cardlang.runtime.chooser import random_chooser
from cardlang.runtime.driver import play_game
from cardlang.runtime.errors import GameDescriptionError, OwnerGuardError
from cardlang.runtime.state import IllegalMove

GAMES_DIR = Path(__file__).parent.parent / "docs" / "games"

_SEED = 5
_POSITIONS = frozenset({0, 1, 2, 3, 5, 8, 13, 21, 34, 55, 89, 144})
_LAST = max(_POSITIONS)
# Hearts deals a new hand after 64 picks (a pass of three cards per seat, then
# thirteen tricks); the third hand begins at pick 128.
_HEARTS_DEEP = 140


def _path(short_name: str) -> str:
    return str(GAMES_DIR / GAMES[short_name])


class _Enough(Exception):
    """The line has run as far as the cell needs."""


@dataclass(frozen=True)
class _Ask:
    at: int
    decider: int
    legal: tuple[int, ...]
    view: SeatView
    answer: int


class _Recording:
    """Every seat's uniform policy, recording each ask, stopping the line once it
    holds `last + 1` picks."""

    def __init__(self, line: LiveLine, seats: int, last: int) -> None:
        self.line = line
        self.last = last
        self.asks: list[_Ask] = []
        self.policies: dict[int, SeatPolicy] = {
            seat: self._seat(seat, UniformSeatPolicy(_SEED)) for seat in range(seats)
        }

    def _seat(self, seat: int, policy: SeatPolicy) -> SeatPolicy:
        def ask(view: SeatView, legal: Sequence[int]) -> int:
            at = len(self.line.history)
            if at > self.last:
                raise _Enough
            answer = policy(view, legal)
            self.asks.append(_Ask(at, seat, tuple(legal), view, answer))
            return answer

        return ask


def _played(short_name: str, last: int, prefix: Sequence[int] = ()) -> tuple[LiveLine, _Recording]:
    path = _path(short_name)
    game, _ = load(path)
    line = LiveLine(path, _SEED, prefix)
    recording = _Recording(line, game.players.low, last)
    try:
        line.play(recording.policies)
    except (_Enough, GameDescriptionError, IllegalMove):
        # A refusal ends the line where a uniform draw took it; the picks before
        # it stand.
        pass
    return line, recording


def _divergences(short_name: str, asks: Sequence[_Ask], history: Sequence[int], positions: frozenset[int]) -> list[str]:
    """Where the adapter's replay from the same history disagrees with the line."""
    path = _path(short_name)
    found: list[str] = []
    for ask in asks:
        if ask.at not in positions:
            continue
        try:
            node = run(path, _SEED, tuple(history[: ask.at]))
        except HistoryMismatch as exc:
            found.append(f"pick {ask.at}: the replay refuses the line's own picks ({exc})")
            continue
        if not isinstance(node, DecisionNode):
            found.append(f"pick {ask.at}: the replay ended where the line asked P{ask.decider}")
            continue
        if node.player != ask.decider:
            found.append(f"pick {ask.at}: the replay asks P{node.player}, the line P{ask.decider}")
            continue
        if tuple(node.legal) != ask.legal:
            found.append(f"pick {ask.at}: legal ids {node.legal} against {list(ask.legal)}")
            continue
        replayed = derive(node.player, node.rs, node.obs_logs[node.player])
        if replayed.zones != ask.view.zones:
            found.append(f"pick {ask.at}: P{ask.decider}'s zones differ")
        if replayed.obs_log != ask.view.obs_log:
            found.append(f"pick {ask.at}: P{ask.decider}'s observation log differs")
    return found


# ---------------------------------------------------------------------------
# The generator a line runs under.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("short_name", sorted(GAMES))
def test_a_game_runs_under_the_generator_its_chance_classification_names(short_name: str) -> None:
    path = _path(short_name)
    generator = generator_for(path, 11)
    if chance_free(path):
        assert isinstance(generator, RefusingRandom)
    else:
        assert not isinstance(generator, RefusingRandom)
        assert generator.random() == random.Random(11).random()


def test_the_replay_and_a_live_line_read_one_generator_rule(monkeypatch: pytest.MonkeyPatch) -> None:
    """A second site choosing a game's generator could hand the two routes
    different deals from one seed."""

    class _Asked(Exception):
        pass

    def asked(_path: str, _seed: int) -> random.Random:
        raise _Asked

    monkeypatch.setattr(replay, "generator_for", asked)
    path = _path("cardlang_kuhn_poker")
    with pytest.raises(_Asked):
        run(path, 0, ())
    with pytest.raises(_Asked):
        LiveLine(path, 0).play({0: UniformSeatPolicy(0), 1: UniformSeatPolicy(0)})


# ---------------------------------------------------------------------------
# The continuation: past the recorded picks, a policy is asked.
# ---------------------------------------------------------------------------


def test_past_the_recorded_picks_a_line_asks_where_the_replay_pauses() -> None:
    path = _path("cardlang_kuhn_poker")
    line = LiveLine(path, 0)
    end = line.play({0: UniformSeatPolicy(0), 1: UniformSeatPolicy(0)})
    assert line.history, "the line made no pick"
    assert len(line.deciders) == len(line.history)
    assert isinstance(run(path, 0, tuple(line.history)), TerminalNode)
    assert isinstance(run(path, 0, ()), DecisionNode), "the replay without a continuation pauses"
    assert end.returns == run_returns(path, tuple(line.history))


def run_returns(path: str, history: tuple[int, ...]) -> list[float]:
    node = run(path, 0, history)
    assert isinstance(node, TerminalNode)
    return node.returns


def _answer_index(view: SeatView, legal: Sequence[int]) -> int:
    return len(legal)


def _answer_card(view: SeatView, legal: Sequence[int]) -> int:
    _, space = load(_path("cardlang_kuhn_poker"))
    decoded: int = space.decode(legal[0])
    return decoded


def _answer_none(view: SeatView, legal: Sequence[int]) -> int:
    return None  # type: ignore[return-value]


def _answer_flag(view: SeatView, legal: Sequence[int]) -> int:
    assert 1 in legal
    return True


# The answers a policy author most plausibly gives in place of an action id:
# a position in the menu, the Candidate the id denotes, nothing, and a flag
# that compares equal to a legal id.
_WRONG_ANSWERS: dict[str, Callable[[SeatView, Sequence[int]], int]] = {
    "an index past the legal ids": _answer_index,
    "the decoded candidate": _answer_card,
    "no answer": _answer_none,
    "a flag equal to a legal id": _answer_flag,
}


@pytest.mark.parametrize("answer", sorted(_WRONG_ANSWERS))
def test_an_answer_that_is_not_a_legal_id_is_refused_before_it_is_played(answer: str) -> None:
    path = _path("cardlang_kuhn_poker")
    line = LiveLine(path, 0)
    wrong = _WRONG_ANSWERS[answer]
    with pytest.raises(AssertionError, match="not one of the legal action ids"):
        line.play({0: wrong, 1: wrong})
    assert line.history == [], "a refused answer must not be recorded"


_OVER_COUNT = """\
game OverCount {
  players: 2
  max_length: 20
  cards: standard52
  zones {
    deck : Deck
    hand[player] : Hand<player>
    pile : Discard
  }
  state {
    score[player] : Integer = 0
  }
  phase setup {
    shuffle deck
    deal 2 cards from deck to each hand
  }
  phase play {
    as 0 { move chosen 3 cards from hand to pile }
  }
  winner: highest score
}
"""


def _fixture(tmp_path: Path, name: str, text: str) -> str:
    path = tmp_path / f"{name}.cardlang"
    path.write_text(text)
    return str(path)


@pytest.mark.parametrize("route", ["a live line", "the adapter's replay", "the uniform chooser"])
def test_a_call_for_more_picks_than_it_offers_is_refused_on_every_route(route: str, tmp_path: Path) -> None:
    path = _fixture(tmp_path, "over_count", _OVER_COUNT)
    game, _ = load(path)
    with pytest.raises(OwnerGuardError, match="cannot choose 3 of 2 candidates"):
        if route == "a live line":
            LiveLine(path, 0).play({0: UniformSeatPolicy(0), 1: UniformSeatPolicy(0)})
        elif route == "the adapter's replay":
            # Replayed up to the pick the pool cannot cover, the call would pause
            # at a node offering nothing.
            run(path, 0, (12, 28))
        else:
            play_game(game, random.Random(0), chooser=random_chooser(random.Random(0)))


def test_a_recorded_pick_the_position_does_not_offer_is_a_history_mismatch() -> None:
    path = _path("cardlang_kuhn_poker")
    node = run(path, 0, ())
    assert isinstance(node, DecisionNode)
    offered = set(node.legal)
    stranger = next(aid for aid in range(1000) if aid not in offered)
    line = LiveLine(path, 0, (stranger,))
    with pytest.raises(HistoryMismatch, match="pick 0"):
        line.play({0: UniformSeatPolicy(0), 1: UniformSeatPolicy(0)})


def test_a_recorded_history_the_game_ends_before_is_a_history_mismatch() -> None:
    path = _path("cardlang_kuhn_poker")
    finished = LiveLine(path, 0)
    finished.play({0: UniformSeatPolicy(0), 1: UniformSeatPolicy(0)})
    overlong = LiveLine(path, 0, (*finished.history, finished.history[0]))
    with pytest.raises(HistoryMismatch, match="past the end"):
        overlong.play({0: UniformSeatPolicy(0), 1: UniformSeatPolicy(0)})


# ---------------------------------------------------------------------------
# What a policy is handed.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("short_name", sorted(GAMES))
def test_each_policy_is_asked_for_its_own_seat_over_sorted_legal_ids(short_name: str) -> None:
    line, recording = _played(short_name, _LAST)
    assert recording.asks, f"{short_name}: the line asked no policy"
    for ask in recording.asks:
        assert ask.view.player == ask.decider
        assert ask.legal and list(ask.legal) == sorted(set(ask.legal))
        assert ask.answer in ask.legal
    assert line.deciders[: len(recording.asks)] == [ask.decider for ask in recording.asks]


def test_a_policy_is_handed_the_state_variables_its_phases_declare() -> None:
    """Hearts declares `leader` and `pass_direction` in its hand phase; a node,
    unwound past that phase, has neither."""
    _, recording = _played("cardlang_hearts", 0)
    state = dict(recording.asks[0].view.state)
    assert {"leader", "pass_direction", "cumulative_score"} <= set(state)


# ---------------------------------------------------------------------------
# The load-bearing pin: a live line is the adapter's line.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("short_name", sorted(GAMES))
def test_a_live_line_reaches_the_positions_the_adapter_replays(short_name: str) -> None:
    line, recording = _played(short_name, _LAST)
    found = _divergences(short_name, recording.asks, line.history, _POSITIONS)
    assert not found, "\n".join(found[:12])


def test_a_live_line_reaches_the_adapter_positions_past_the_first_deals() -> None:
    line, recording = _played("cardlang_hearts", _HEARTS_DEEP)
    assert len(line.history) > _HEARTS_DEEP, "the line ended before its third hand"
    found = _divergences("cardlang_hearts", recording.asks, line.history, frozenset(range(_HEARTS_DEEP + 1)))
    assert not found, "\n".join(found[:12])


@pytest.mark.xfail(strict=True, raises=AssertionError, reason="issue #612")
def test_the_state_a_policy_is_handed_is_the_state_the_adapter_node_holds() -> None:
    line, recording = _played("cardlang_hearts", 3)
    path = _path("cardlang_hearts")
    for ask in recording.asks:
        node = run(path, _SEED, tuple(line.history[: ask.at]))
        assert isinstance(node, DecisionNode)
        assert derive(node.player, node.rs, node.obs_logs[node.player]).state == ask.view.state


_CUTS = (0, 1, 3, 13, 55)


@pytest.mark.parametrize("short_name", sorted(GAMES))
def test_a_line_cut_at_any_pick_and_played_again_is_the_same_line(short_name: str) -> None:
    """What undo and resume stand on: the same seed and the same picks name one
    line, whoever took them."""
    whole, _ = _played(short_name, _LAST)
    for cut in _CUTS:
        if cut > len(whole.history):
            continue
        again, _ = _played(short_name, _LAST, whole.history[:cut])
        assert again.history == whole.history, f"{short_name}: cut at pick {cut} reaches another line"


def test_the_pin_catches_policies_that_draw_from_the_game_generator(monkeypatch: pytest.MonkeyPatch) -> None:
    """The adapter's replay never draws for a pick; a line whose opponents drew
    from the game's generator would deal its later hands differently."""
    shared: list[random.Random] = []
    generator = replay.generator_for

    def sharing(path: str, seed: int) -> random.Random:
        shared[:] = [generator(path, seed)]
        return shared[0]

    policy = UniformSeatPolicy.__call__

    def drawing(self: UniformSeatPolicy, view: SeatView, legal: Sequence[int]) -> int:
        shared[0].random()
        return policy(self, view, legal)

    monkeypatch.setattr(replay, "generator_for", sharing)
    monkeypatch.setattr(UniformSeatPolicy, "__call__", drawing)
    line, recording = _played("cardlang_hearts", _HEARTS_DEEP)
    monkeypatch.undo()
    assert _divergences("cardlang_hearts", recording.asks, line.history, frozenset(range(_HEARTS_DEEP + 1)))


def test_the_cut_pin_catches_a_policy_holding_a_random_stream(monkeypatch: pytest.MonkeyPatch) -> None:
    streams: dict[int, random.Random] = {}

    def streaming(self: UniformSeatPolicy, view: SeatView, legal: Sequence[int]) -> int:
        stream = streams.setdefault(id(self), random.Random(self.seed))
        return legal[stream.randrange(len(legal))]

    monkeypatch.setattr(UniformSeatPolicy, "__call__", streaming)
    whole, _ = _played("cardlang_hearts", 30)
    streams.clear()
    again, _ = _played("cardlang_hearts", 30, whole.history[:13])
    assert again.history != whole.history


# ---------------------------------------------------------------------------
# How a line ends early.
# ---------------------------------------------------------------------------


def test_a_policy_that_raises_ends_the_line_with_the_picks_before_it_kept() -> None:
    path = _path("cardlang_hearts")
    line = LiveLine(path, _SEED)

    class _Stop(Exception):
        pass

    uniform = UniformSeatPolicy(_SEED)

    def stopping(view: SeatView, legal: Sequence[int]) -> int:
        if len(line.history) == 7:
            raise _Stop
        return uniform(view, legal)

    with pytest.raises(_Stop):
        line.play({seat: stopping for seat in range(4)})
    assert len(line.history) == 7 and len(line.deciders) == 7


_DECISION_IN_AFTER_EACH = """\
game AfterEachDecision {
  players: 2
  max_length: 60
  cards: standard52
  zones {
    deck : Deck
    hand[player] : Hand<player>
    pile : Discard
  }
  state {
    score[player] : Integer = 0
    rounds : Integer = 0
  }
  phase setup {
    shuffle deck
    deal 5 cards from deck to each hand
  }
  phase play repeat until rounds >= 2 {
    as 0 { move chosen 1 card from hand to pile }
    after_each {
      rounds += 1
      as 1 { move chosen 1 card from hand to pile }
    }
  }
  winner: highest score
}
"""


def test_a_policy_that_raised_is_not_asked_again_while_the_run_unwinds(tmp_path: Path) -> None:
    """`after_each` runs on the way out of an iteration, exceptions included, and
    this one decides: the unwind reaches the Chooser a second time."""
    path = _fixture(tmp_path, "after_each_decision", _DECISION_IN_AFTER_EACH)
    asked: list[int] = []

    class _Stop(Exception):
        pass

    def stopping(view: SeatView, legal: Sequence[int]) -> int:
        asked.append(view.player)
        raise _Stop

    with pytest.raises(_Stop):
        LiveLine(path, 5).play({0: stopping, 1: stopping})
    assert asked == [0]


_SHORT = """\
game ShortLength {
  players: 2
  max_length: 4
  cards: standard52
  zones {
    deck : Deck
    hand[player] : Hand<player>
    pile : Discard
  }
  state {
    score[player] : Integer = 0
    rounds : Integer = 0
  }
  phase setup {
    shuffle deck
    deal 5 cards from deck to each hand
  }
  phase play repeat until rounds >= 3 {
    as 0 { move chosen 1 card from hand to pile }
    as 1 { move chosen 1 card from hand to pile }
    rounds += 1
  }
  winner: highest score
}
"""


def test_a_game_refusal_ends_the_line_with_the_picks_before_it_kept(tmp_path: Path) -> None:
    path = _fixture(tmp_path, "short_length", _SHORT)
    line = LiveLine(path, 0)
    with pytest.raises(OwnerGuardError, match="max_length"):
        line.play({0: UniformSeatPolicy(0), 1: UniformSeatPolicy(0)})
    assert len(line.history) == 4


# ---------------------------------------------------------------------------
# The terminal position.
# ---------------------------------------------------------------------------


def test_the_terminal_views_hold_the_game_state_the_game_ended_with() -> None:
    """`play_game` pops the game frame before it returns, so a view taken after
    it would hold no state variable at all."""
    path = _path("cardlang_kuhn_poker")
    game, _ = load(path)
    end = LiveLine(path, 0).play({0: UniformSeatPolicy(0), 1: UniformSeatPolicy(0)})
    declared = {decl.name for decl in game.state.decls} if game.state is not None else set()
    assert declared, "the witness game declares game-level state"
    assert set(end.views) == {0, 1}
    for seat, view in end.views.items():
        assert view.player == seat
        assert declared <= {name for name, _ in view.state}


_NO_DECISION = """\
game NoDecision {
  players: 2
  max_length: 20
  cards: standard52
  zones {
    deck : Deck
    hand[player] : Hand<player>
  }
  state {
    score[player] : Integer = 0
  }
  phase setup {
    shuffle deck
    deal 2 cards from deck to each hand
  }
  winner: highest score
}
"""


def test_a_game_with_no_decision_ends_with_no_views(tmp_path: Path) -> None:
    """No decision means the engine handed over no world to derive from."""
    path = _fixture(tmp_path, "no_decision", _NO_DECISION)
    line = LiveLine(path, 0)
    end = line.play({0: UniformSeatPolicy(0), 1: UniformSeatPolicy(0)})
    assert line.history == [] and end.views == {}
    assert end.returns == run_returns(path, ())
