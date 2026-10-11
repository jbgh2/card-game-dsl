"""OpenSpiel's IS-MCTS family plays the corpus through the general adapter.

`CardlangState.resample_from_infostate` constructs a world the asking seat
cannot tell from the one being played (`cardlang.openspiel.resample`), and
OpenSpiel's own `ISMCTSBot`, which determinizes through that call at every
search, plays Kuhn poker and Hearts to terminal against uniform-random seats.

Completeness ledger (decisions.md "Closed-domain completeness"):

property:        a constructed world replays to a decision of the same seat,
                 renders the asking seat's information state byte-identically
                 and, when the asking seat is the one to move, offers the same
                 legal actions; the construction reads the true line only
                 through what the asking seat is entitled to, so two worlds it
                 cannot tell apart construct the same world from the same
                 sampler randomness; and an IS-MCTS search over such worlds
                 reaches terminal.
domain:          three axes. The games: every registered game resamples at each
                 pick of `SWEEP_AT` along one seeded uniform line, for the seat
                 to move and for the seat after it, unless `REFUSALS` pins its
                 refusal kind; an unpinned refusal, a pinned game that
                 resamples, and a game whose text commits it to a refusal its
                 entry does not name all fail. The refusals: every kind in
                 `resample.REFUSAL_KINDS` raised by a named witness, and every
                 draw kind either constructed across or refused by text. The
                 picks: every action block in `BLOCKS`, crossed
                 with whether the asking seat saw another seat's pick. Each cell
                 a swept line meets has a named witness game. Every non-card
                 decision announces its value, so the unseen non-card cells
                 have no witness, and every sweep holds the cells it meets to
                 the witnessed set.
registry:        games: `harness.REGISTERED_GAMES`; blocks:
                 `cardlang.openspiel.encoding.BLOCKS`; refusal kinds:
                 `cardlang.openspiel.resample.REFUSAL_KINDS`; draw kinds:
                 `cardlang.runtime.chance.DRAW_KINDS`, their scripting pinned in
                 tests/test_scripted_random.py; the witnesses outside the
                 registry: tests/fixtures/resample/random_selection.cardlang
                 (a random selection between two decisions) and tests/fixtures/resample/chance_free.cardlang
                 (a game that draws nothing, with an unseen pick).
does not prove:  that the constructed worlds follow the posterior's weights —
                 a green here places every world inside the information set and
                 bars the construction from reading past it, and says nothing
                 about how often each world is drawn; nor anything about picks
                 past `SWEEP_AT` outside the two games IS-MCTS plays to
                 terminal, where OpenSpiel's own key check runs at every search.
"""

from __future__ import annotations

import random
from collections.abc import Callable
from functools import cache
from pathlib import Path
from typing import Any

import numpy as np
import pytest

pyspiel = pytest.importorskip("pyspiel")

from open_spiel.python.algorithms.ismcts import ISMCTSBot
from open_spiel.python.algorithms.mcts import (
    Evaluator,
    RandomRolloutEvaluator,
)

import cardlang.openspiel.game as ogame
from cardlang.openspiel import resample as R
from cardlang.openspiel.encoding import BLOCKS
from cardlang.openspiel.infostate import information_state
from cardlang.openspiel.registry import _GAMES_DIR
from cardlang.openspiel.replay import DecisionNode, chance_free, load, run
from cardlang.runtime.chance import DRAW_KINDS

from .harness import REGISTERED_GAMES

# The picks along each game's seeded uniform line at which the sweep resamples.
SWEEP_AT = (0, 8, 16)

_FIXTURES = Path(__file__).resolve().parent.parent / "fixtures" / "resample"

# Each (block, seen) cell a swept line meets, and the game that witnesses it.
WITNESSED: dict[tuple[str, bool], str] = {
    ("card", True): "cardlang_hearts",
    ("card", False): "cardlang_hearts",
    ("combination", True): "cardlang_big_two",
    ("integer", True): "cardlang_oh_hell",
    ("name", True): "cardlang_big_two",
    ("offering", True): "cardlang_bridge",
}


def _path(filename: str) -> str:
    return str(_GAMES_DIR / filename)


def _check(
    path: str, seed: int, history: tuple[int, ...], observer: int
) -> tuple[set[tuple[str, bool]], set[tuple[str, bool]]]:
    """Resample at one position and hold the world to the property; return the
    (block, seen) cell of every other seat's pick on the line, and the cells of
    the unseen picks the constructed world took differently."""
    _, space = load(path)
    seeds = 1 if chance_free(path) else 4096
    true = run(path, seed, history)
    assert isinstance(true, DecisionNode)
    owed = R.entitlement(path, seed, (), history, observer)
    cells = {
        (space.block_of(aid), owed.replayed[j])
        for j, aid in enumerate(history)
        if owed.deciders[j] != observer
    }
    world = R.resample(path, seed, (), history, observer, random.Random(len(history)), seeds)
    node = run(path, world.seed, world.history, script=world.script)
    assert isinstance(node, DecisionNode), "the constructed world ended where the true one paused"
    assert node.player == true.player
    if observer == true.player:
        assert node.legal == true.legal
    assert information_state(observer, node.rs, node.obs_logs[observer]) == information_state(
        observer, true.rs, true.obs_logs[observer]
    )
    # The construction reads only the information state: from the constructed
    # world, which the observer cannot tell from the true one, the same
    # sampler randomness constructs the same world. red under: an unseen pick
    # replaying the true action whenever it is legal (`_evaluate`'s `pick`) —
    # every game with an unseen card pick on its swept line fails here
    # (executed 2026-10-09).
    again = R.resample(path, world.seed, world.script, world.history, observer, random.Random(1), seeds)
    assert again == R.resample(path, seed, (), history, observer, random.Random(1), seeds)
    redrawn = {
        (space.block_of(aid), False)
        for j, aid in enumerate(history)
        if owed.deciders[j] != observer and not owed.replayed[j] and world.history[j] != aid
    }
    return cells, redrawn


@cache
def _sweep(
    short_name: str, filename: str
) -> tuple[frozenset[tuple[str, bool]], frozenset[tuple[str, bool]]]:
    """The cells one game's swept line meets, and the unseen cells some
    constructed world on it redrew."""
    path = _path(filename)
    rnd = random.Random(short_name)
    seed = 0 if chance_free(path) else rnd.randrange(4096)
    history: list[int] = []
    cells: set[tuple[str, bool]] = set()
    redrawn: set[tuple[str, bool]] = set()
    for pick in range(max(SWEEP_AT) + 1):
        node = run(path, seed, tuple(history))
        if not isinstance(node, DecisionNode):
            break
        if pick in SWEEP_AT:
            for observer in (node.player, (node.player + 1) % len(node.obs_logs)):
                met, changed = _check(path, seed, tuple(history), observer)
                cells |= met
                redrawn |= changed
        history.append(rnd.choice(node.legal))
    return frozenset(cells), frozenset(redrawn)


# The registered games no Constructed World is built for yet, each with the
# kind of its refusal (`resample.REFUSAL_KINDS`, which names the issue whose
# landing removes it). A ratchet: entries leave, and a game joins only by a
# decision recorded here. A refusal with no entry fails naming the game; an
# entry whose game resamples fails naming the entry to drop.
REFUSALS: dict[str, str] = {
    "cardlang_breakthrough": "repeated cards",
    "cardlang_canasta": "repeated cards",
    "cardlang_coup": "repeated cards",
    "cardlang_doppelkopf": "repeated cards",
    "cardlang_pinochle": "repeated cards",
    "cardlang_tic_tac_toe": "repeated cards",
}


def test_every_refusal_names_a_registered_game_and_a_declared_kind() -> None:
    """An entry naming no game could never leave the table, and would read as
    a refusal still standing."""
    assert set(REFUSALS) <= {short for short, _ in REGISTERED_GAMES}
    assert set(REFUSALS.values()) <= set(R.REFUSAL_KINDS)


# The games whose sweep takes minutes rather than seconds, because their
# public play constrains the hidden hands tightly enough that most proposals
# are repaired rather than accepted (issue #832).
_SLOW_SWEEPS = frozenset({"cardlang_go_fish", "cardlang_french_tarot"})


def _sweep_cases() -> list[Any]:
    return [
        pytest.param(
            short_name,
            filename,
            marks=[pytest.mark.slow] if short_name in _SLOW_SWEEPS else [],
            id=short_name,
        )
        for short_name, filename in REGISTERED_GAMES
    ]


@pytest.mark.parametrize(("short_name", "filename"), _sweep_cases())
def test_every_game_resamples_or_is_a_pinned_refusal(short_name: str, filename: str) -> None:
    """red under: drop `cardlang_canasta` from `REFUSALS` — its text commits
    it to a refusal and this fails naming the game; add `cardlang_hearts` to
    it — the refusal is never raised and this fails naming the entry to drop;
    plant a `move random` past every decision in a game absent from it — no
    swept line reaches it, and the text's refusal fails here, while the same
    game pinned for it passes (executed 2026-10-10)."""
    committed = R.refusal_in_text(_path(filename))
    if committed is not None:
        assert REFUSALS.get(short_name) == committed[0], (
            f"{short_name}'s text commits it to a refusal: {committed[1]}. Pin "
            f"it in REFUSALS as {committed[0]!r}."
        )
    if short_name in REFUSALS:
        kind = REFUSALS[short_name]
        node = run(_path(filename), 0, ())
        assert isinstance(node, DecisionNode)
        try:
            R.resample(_path(filename), 0, (), (), node.player, random.Random(0), 4096)
        except R.ResampleRefusal as refused:
            assert refused.kind == kind, f"{short_name} refuses for another reason: {refused}"
        else:
            pytest.fail(
                f"{short_name} resamples now: drop its REFUSALS entry "
                f"(issue #{R.REFUSAL_KINDS[kind]})"
            )
        return
    try:
        met, _ = _sweep(short_name, filename)
    except R.ResampleRefusal as refused:
        pytest.fail(
            f"{short_name} refuses a Constructed World and is not in REFUSALS: "
            f"{refused}. Build it, or pin it in REFUSALS as {refused.kind!r}."
        )
    unwitnessed = met - set(WITNESSED)
    assert not unwitnessed, (
        f"{short_name} meets pick cells no witness covers: {sorted(unwitnessed)} — "
        f"name a witness game for each in WITNESSED"
    )


def _cell_cases() -> list[Any]:
    cases = []
    for block in BLOCKS:
        for seen in (True, False):
            marks = []
            if (block, seen) not in WITNESSED:
                marks.append(
                    pytest.mark.xfail(
                        raises=AssertionError,
                        strict=True,
                        reason=f"no corpus line poses an unseen {block} pick: every "
                        f"decision of a non-card value announces it",
                    )
                )
            cases.append(
                pytest.param(block, seen, marks=marks, id=f"{block}-{'seen' if seen else 'unseen'}")
            )
    return cases


@pytest.mark.parametrize(("block", "seen"), _cell_cases())
def test_each_pick_cell_has_a_witness(block: str, seen: bool) -> None:
    assert (block, seen) in WITNESSED
    short_name = WITNESSED[(block, seen)]
    met, redrawn = _sweep(short_name, ogame.GAMES[short_name])
    assert (block, seen) in met
    if not seen:
        # An unseen pick is redrawn, not replayed: some constructed world on
        # the witness's line takes it differently. red under: the same planted
        # leak as `_check`'s, which that pin cannot see where both worlds then
        # agree on every unseen pick (executed 2026-10-09).
        assert (block, seen) in redrawn


def _repeated_cards() -> None:
    path = _path(ogame.GAMES["cardlang_canasta"])
    node = run(path, 0, ())
    assert isinstance(node, DecisionNode)
    R.resample(path, 0, (), (), node.player, random.Random(0), 4096)


def _random_selection() -> None:
    # Asked at the first discard, before the line reaches the random
    # selection: the text refuses it there all the same.
    path = str(_FIXTURES / "random_selection.cardlang")
    node = run(path, 3, ())
    assert isinstance(node, DecisionNode)
    assert len(node.rs.zones.instance("hand", 0).cards) == 3, "the selection is already behind"
    R.resample(path, 3, (), (), node.player, random.Random(0), 4096)


def _budget_spent() -> None:
    path = _path(ogame.GAMES["cardlang_hearts"])
    node = run(path, 0, ())
    assert isinstance(node, DecisionNode)
    R.resample(path, 0, (), (), node.player, random.Random(0), 4096, attempts=0)


# One call per refusal kind that raises it.
REFUSAL_WITNESSES: dict[str, Callable[[], None]] = {
    "repeated cards": _repeated_cards,
    "random selection": _random_selection,
    "budget spent": _budget_spent,
}


@pytest.mark.parametrize("kind", sorted(R.REFUSAL_KINDS))
def test_every_refusal_kind_is_raised_by_its_witness(kind: str) -> None:
    assert kind in REFUSAL_WITNESSES, f"no witness raises the refusal kind {kind!r}"
    with pytest.raises(R.ResampleRefusal) as refused:
        REFUSAL_WITNESSES[kind]()
    assert refused.value.kind == kind
    assert f"issue #{R.REFUSAL_KINDS[kind]}" in str(refused.value)


def test_the_witnesses_name_only_declared_kinds() -> None:
    assert set(REFUSAL_WITNESSES) == set(R.REFUSAL_KINDS)


def test_a_refusal_of_an_undeclared_kind_is_refused() -> None:
    with pytest.raises(AssertionError, match="unknown refusal kind"):
        R.ResampleRefusal("no such kind", "x")


def test_every_draw_kind_is_constructed_or_refused() -> None:
    """The draw kinds the construction builds across and those it refuses by
    text partition `chance.DRAW_KINDS`, so a draw kind added there is a red
    here until the construction says which it is."""
    refused = set(R._UNCONSTRUCTED)
    assert R.CONSTRUCTED_DRAW_KINDS.isdisjoint(refused)
    assert R.CONSTRUCTED_DRAW_KINDS | refused == set(DRAW_KINDS)
    assert set(R._UNCONSTRUCTED.values()) <= set(R.REFUSAL_KINDS)


def test_a_chance_free_game_redraws_only_its_unseen_picks() -> None:
    """Every corpus game that draws nothing is a board whose pieces repeat, so
    the construction's no-draw path has its witness here: the deal is fixed,
    and seat 1's unseen discard is the one thing a world may change."""
    path = str(_FIXTURES / "chance_free.cardlang")
    assert chance_free(path)
    first = run(path, 0, ())
    assert isinstance(first, DecisionNode)
    history = (first.legal[0],)
    discards = set()
    for draw in range(8):
        cells, _ = _check(path, 0, history, 0)
        assert cells == {("card", False)}
        world = R.resample(path, 0, (), history, 0, random.Random(draw), 1)
        assert world.script == () and world.seed == 0
        discards.add(world.history[0])
    assert len(discards) > 1, "the unseen discard was never redrawn"


# --- through the adapter ----------------------------------------------------


def _line(game: Any, seed: int, picks: int, rnd: random.Random) -> list[Any]:
    """The adapter states of one uniform line, chance root excluded."""
    state = game.new_initial_state()
    state.apply_action(seed)
    states: list[Any] = []
    while not state.is_terminal() and len(states) < picks:
        states.append(state.clone())
        state.apply_action(rnd.choice(state.legal_actions()))
    return states


@pytest.mark.parametrize(
    ("short_name", "deals", "stride"),
    [("cardlang_kuhn_poker", 6, 1), ("cardlang_hearts", 1, 3)],
)
def test_resample_from_infostate_keeps_the_seats_view(
    short_name: str, deals: int, stride: int
) -> None:
    game = pyspiel.load_game(short_name)
    rnd = random.Random(short_name)
    redrawn = 0
    for deal in range(deals):
        for state in _line(game, 11 + deal, 30, rnd)[::stride]:
            for player in range(game.num_players()):
                world = state.resample_from_infostate(
                    player, pyspiel.UniformProbabilitySampler(deal * 100 + player, 0.0, 1.0)
                )
                assert world.information_state_string(player) == state.information_state_string(
                    player
                )
                assert world.current_player() == state.current_player()
                if player == state.current_player():
                    assert world.legal_actions() == state.legal_actions()
                clone = world.clone()
                assert clone.information_state_string(player) == world.information_state_string(
                    player
                )
                assert str(clone) == str(world)
                redrawn += any(
                    world.information_state_string(other) != state.information_state_string(other)
                    for other in range(game.num_players())
                )
    assert redrawn, f"no resample of {short_name} changed what any other seat holds"


def test_resample_at_the_chance_root_is_the_root() -> None:
    root = pyspiel.load_game("cardlang_hearts").new_initial_state()
    world = root.resample_from_infostate(0, pyspiel.UniformProbabilitySampler(0, 0.0, 1.0))
    assert world.is_chance_node() and str(world) == str(root)


class _ValueFree(Evaluator):  # type: ignore[misc]
    """Values every leaf at zero under a uniform prior: the search is OpenSpiel's
    own, determinizing through `resample_from_infostate` at every simulation,
    with no rollout to pay for."""

    def evaluate(self, state: Any) -> Any:
        return np.zeros(state.num_players())

    def prior(self, state: Any) -> list[tuple[int, float]]:
        legal = state.legal_actions()
        return [(a, 1.0 / len(legal)) for a in legal]


def _play(game: Any, bot: Any, seat: int, rnd: random.Random) -> Any:
    state = game.new_initial_state()
    while not state.is_terminal():
        if state.is_chance_node():
            state.apply_action(rnd.randrange(len(state.chance_outcomes())))
        elif state.current_player() == seat:
            state.apply_action(bot.step(state))
        else:
            state.apply_action(rnd.choice(state.legal_actions()))
    return state


def test_ismcts_plays_kuhn_poker_to_terminal() -> None:
    """OpenSpiel's bot, unmodified: it determinizes through the state's own
    `resample_from_infostate` with its own sampler."""
    game = pyspiel.load_game("cardlang_kuhn_poker")
    for deal in range(12):
        bot = ISMCTSBot(
            game=game,
            evaluator=RandomRolloutEvaluator(2, np.random.RandomState(deal)),
            uct_c=2.0,
            max_simulations=20,
            random_state=np.random.RandomState(deal),
        )
        state = _play(game, bot, deal % 2, random.Random(deal))
        assert state.is_terminal() and sum(state.returns()) == 0


@pytest.mark.slow
def test_ismcts_plays_hearts_to_terminal() -> None:
    """A whole match, to 100 points. The bot's sampler is seeded through
    `set_resampler` so the line is the same on every run; the call it makes is
    still the state's `resample_from_infostate`."""
    game = pyspiel.load_game("cardlang_hearts")
    bot = ISMCTSBot(
        game=game,
        evaluator=_ValueFree(),
        uct_c=2.0,
        max_simulations=2,
        max_world_samples=1,
        random_state=np.random.RandomState(0),
    )
    draws = iter(range(1, 10**6))
    bot.set_resampler(
        lambda state, player: state.resample_from_infostate(
            player, pyspiel.UniformProbabilitySampler(next(draws), 0.0, 1.0)
        )
    )
    state = _play(game, bot, 0, random.Random(0))
    assert state.is_terminal()
    assert max(-r for r in state.returns()) >= 100
