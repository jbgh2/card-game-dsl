"""Leduc poker (2 players) — OpenSpiel readiness.

Harness configuration rationale:

- `depth=2`: the greedy `legal[0]` line is `check, check` (the first street
  closes), then the board card is dealt and `check, check` again — four
  actions to TerminalNode. Depth 2 therefore pauses on P0's SECOND-street
  decision, which is both what the 2-player swap branch needs (`p == d0`,
  P0 opening both streets) and the interesting pause: a real street has
  closed, the public card is on the table, and three cards remain undealt to
  pair the opponent's hidden card against.

- `swap_axis="any"`: Leduc's recorded actions are betting vocabulary — none
  names a card — so any swap of the opponent's private card against an
  undealt one replays legally.

- `stock_zone="deck"` (the default): 6 cards, two dealt and one turned, so
  three sit hidden in the deck at the depth-2 pause.

- `adapter_terminal_steps=10`: the greedy line reaches TerminalNode in 4 steps.

`test_adapter_agrees_over_two_whole_leduc_deals` below extends the harness's
single greedy line to every node of two complete deals — the check-heavy
line the harness walks never exercises a raise, a fold, or a paired board.
"""

import random
from typing import Any

import pytest

import cardlang.ast.nodes as n
from cardlang.openspiel.encoding import _walk
from cardlang.openspiel.infostate import information_state
from cardlang.openspiel.replay import DecisionNode, ReplayChooser, load, run
from cardlang.runtime.driver import play_game

from .harness import GAMES_DIR, GameSpec, ReadinessProofs, action_strings

pyspiel = pytest.importorskip("pyspiel")

PATH = str(GAMES_DIR / "leduc-poker.cardlang")
STUD_PATH = str(GAMES_DIR / "seven-card-stud.cardlang")
SHORT_NAME = "cardlang_leduc_poker"


class TestReadiness(ReadinessProofs):
    spec = GameSpec(
        SHORT_NAME,
        "leduc-poker.cardlang",
        depth=2,
        swap_axis="any",
        adapter_terminal_steps=10,
    )


def _ids(names: list[str]) -> tuple[int, ...]:
    _, space = load(PATH)
    by_name = {space.to_string(a): a for a in range(space.num_distinct_actions)}
    return tuple(by_name[x] for x in names)


def _legal_names(r: DecisionNode) -> list[str]:
    _, space = load(PATH)
    return [space.to_string(a) for a in r.legal]


def _deal(seed: int) -> tuple[str, str, str]:
    """This seed's (P0 card, P1 card, board card). The board is only turned
    once the first street closes, so it is read from the check-check pause."""
    r0 = run(PATH, seed, ())
    assert isinstance(r0, DecisionNode)
    r2 = run(PATH, seed, _ids(["check", "check"]))
    assert isinstance(r2, DecisionNode)
    return (
        str(r0.rs.zones.instance("hand", 0).cards[0]),
        str(r0.rs.zones.instance("hand", 1).cards[0]),
        str(r2.rs.zones.single("board").cards[0]),
    )


def _seed_for(match: Any) -> int:
    for seed in range(400):
        d = _deal(seed)
        if match(d):
            return seed
    raise AssertionError("no seed produced the requested Leduc deal within 400 tries")


# --- the family-varying raise cap (the tier's second anchor edge, #143) ---


def test_the_raise_cap_is_family_varying_required_state() -> None:
    """`raise_cap` carries a genuine family difference — Leduc allows two
    aggressive actions per street, Stud a bet and three raises — with the
    difference living
    ENTIRELY in each game's declared state, never in the library or on the
    `uses` line (decisions.md "Family libraries", the parameterization
    paragraph).

    The two halves: statically, the two games declare different defaults for
    the same `requires`d name; behaviourally, Leduc's cap binds — after a bet
    and a raise the third decision offers only `call` and `fold`, with `raise`
    gone from an `offering` list that names it.
    """
    def cap(path: str) -> int:
        game_ast, _ = load(path)
        caps = [
            d.default.value
            for d in _walk(game_ast)
            if isinstance(d, n.StateDecl)
            and d.name == "raise_cap"
            and isinstance(d.default, n.IntLit)
        ]
        assert len(caps) == 1, f"{path}: expected one raise_cap declaration, got {caps}"
        return caps[0]

    assert (cap(PATH), cap(STUD_PATH)) == (2, 4), (
        "the poker family's members no longer differ on raise_cap — the "
        "parameterization-rides-on-required-state claim has lost its witness"
    )

    seed = 5
    after_bet = run(PATH, seed, _ids(["bet"]))
    assert isinstance(after_bet, DecisionNode)
    assert _legal_names(after_bet) == ["call", "fold", "raise"], (
        "the first raise must be available (raises=1 < raise_cap=2)"
    )
    after_raise = run(PATH, seed, _ids(["bet", "raise"]))
    assert isinstance(after_raise, DecisionNode)
    assert _legal_names(after_raise) == ["call", "fold"], (
        "raise_cap=2 must close the street to further aggression — the "
        "imported `raise` is offered here and its guard is what filters it out"
    )

    # The cap is per-street: the second street starts a fresh `raises` count,
    # so the same two aggressive actions are available again after the board.
    second = run(PATH, seed, _ids(["bet", "raise", "call", "bet"]))
    assert isinstance(second, DecisionNode)
    assert _legal_names(second) == ["call", "fold", "raise"], (
        "the raise cap must reset per street, not accumulate across the hand"
    )


# --- the showdown ---


def test_showdown_pairs_the_board_beats_high_card_and_equal_ranks_split() -> None:
    """Leduc's whole reason for existing over Kuhn: the public card can pair
    a private one. Three frozen deals, each driven to a called showdown —
    a pair beating a strictly higher unpaired card, an unpaired high card
    winning, and two equal ranks splitting the pot back."""
    line = _ids(["bet", "call", "check", "check"])

    def returns(seed: int) -> list[float]:
        r = run(PATH, seed, line)
        assert not isinstance(r, DecisionNode), "the called line must reach a showdown"
        return r.returns

    # P0 pairs the board with a Jack; P1 holds a King and loses anyway.
    pair_seed = _seed_for(lambda d: d[0][0] == d[2][0] and d[1][0] == "K" != d[2][0])
    assert returns(pair_seed) == [3.0, -3.0]

    # Nobody pairs: the higher private card takes it.
    high_seed = _seed_for(
        lambda d: d[0][0] != d[2][0] and d[1][0] != d[2][0] and d[0][0] != d[1][0]
    )
    d = _deal(high_seed)
    order = {"J": 0, "Q": 1, "K": 2}
    expected = [3.0, -3.0] if order[d[0][0]] > order[d[1][0]] else [-3.0, 3.0]
    assert returns(high_seed) == expected, d

    # Equal ranks, unpaired board: each entrant takes their commitment back.
    tie_seed = _seed_for(lambda d: d[0][0] == d[1][0] and d[2][0] != d[0][0])
    assert returns(tie_seed) == [0.0, 0.0]


def test_the_board_is_public_and_a_folded_card_is_not() -> None:
    """The two observation shapes Leduc adds over Kuhn, confirmed positively
    (the swap-based leak-closure proofs never confirm an event's shape): the
    community card lands in a public `Discard` and BOTH players learn its
    identity, while a folded private card mucks with no identity in the
    opponent's log — and, when the fold ends the first street, no board card
    is ever dealt, so a folded holding stays unknowable even in hindsight."""
    seed = 5
    showdown = _events_for_line(seed, ["check", "check", "check", "check"])
    for observer in (0, 1):
        board_moves = [e for e in showdown[observer] if e[0] == "move" and e[3] == "board"]
        assert board_moves, f"P{observer} never observed the board card"
        assert any(
            isinstance(e[4], tuple) and len(e[4]) == 1 and isinstance(e[4][0], str)
            for e in board_moves
        ), f"P{observer} did not learn the board card's identity: {board_moves}"

    folded = _events_for_line(seed, ["bet", "fold"])
    mucks = [e for e in folded[0] if e[0] == "move" and e[1] == "hand[1]" and e[3] == "muck"]
    assert mucks, "P0 never observed the folded card leave P1's hand"
    for e in mucks:
        assert e[4] is None, f"P0 saw the folded card's identity leak to the muck: {e}"
    assert not [e for e in folded[0] if e[0] == "move" and e[3] == "board"], (
        "a first-street fold must not turn a board card — dealing one would "
        "shrink the set of hands the folder could have held"
    )


# --- whole-tree adapter agreement ---


def test_adapter_agrees_over_two_whole_leduc_deals() -> None:
    """The harness's adapter proof walks one greedy line, which in Leduc is
    four checks: no raise, no fold, no paired board. This walks EVERY node of
    two complete deals — a paired one and an unpaired one — comparing the
    registered pyspiel game and the DSL replay on the current player, the
    legal actions, both players' information-state strings, and the terminal
    returns. Because the pyspiel state re-simulates independently of these
    `run` calls, it doubles as a determinism check over the same trees."""
    game = pyspiel.load_game(SHORT_NAME)
    seeds = [
        _seed_for(lambda d: d[0][0] == d[2][0]),
        _seed_for(lambda d: d[0][0] != d[2][0] and d[1][0] != d[2][0]),
    ]
    _, space = load(PATH)
    nodes = 0
    terminals = 0

    def walk(seed: int, history: list[int]) -> None:
        nonlocal nodes, terminals
        state = game.new_initial_state()
        assert state.is_chance_node()
        state.apply_action(seed)
        for a in history:
            state.apply_action(a)
        r = run(PATH, seed, tuple(history))
        if not isinstance(r, DecisionNode):
            terminals += 1
            assert state.is_terminal(), f"seed={seed} history={history}: DSL terminal, adapter not"
            assert state.returns() == r.returns, (
                f"seed={seed} history={history}: returns disagree — "
                f"adapter {state.returns()} != DSL {r.returns}"
            )
            return
        nodes += 1
        assert not state.is_terminal()
        assert state.current_player() == r.player
        assert state.legal_actions() == r.legal
        # ...and the rendered text agrees too. Shadow Guard; the guard is
        # `test_action_strings.py` (see `harness.action_strings`).
        assert [state.action_to_string(r.player, a) for a in state.legal_actions()] == (
            action_strings(space, r.legal)
        ), f"seed={seed} history={history}: adapter action renderings disagree"
        for q in range(2):
            assert state.information_state_string(q) == information_state(
                q, r.rs, r.obs_logs[q]
            ), f"seed={seed} history={history}: adapter info state for P{q} diverged"
        for a in r.legal:
            walk(seed, history + [a])

    for seed in seeds:
        walk(seed, [])
    # Both deals have the same betting tree (the cards affect only the
    # showdown), so the two walks visit identical counts. Per deal, one
    # street has 6 decision nodes (P0; then P1 after a check; then P0, P1
    # after check-bet-raise; then P1, P0 after bet-raise) and 9 terminal
    # street-lines, 4 of which are folds that end the hand and 5 of which
    # continue: 6 + 5*6 = 36 nodes and 4 + 5*9 = 49 lines per deal. Frozen so
    # a change to the betting shape — a lost raise, an extra one — fails
    # loudly here rather than quietly shrinking the walk.
    assert (nodes, terminals) == (2 * 36, 2 * 49), (nodes, terminals)


def _events_for_line(seed: int, names: list[str]) -> dict[int, list[tuple[Any, ...]]]:
    """Every observer's full event log for a COMPLETED hand, the line given by
    move-type name. `replay.run` discards the logs when it returns TerminalNode,
    so this drives the game directly with the same `ReplayChooser` the
    adapter uses."""
    game_ast, space = load(PATH)
    logs: dict[int, list[tuple[Any, ...]]] = {0: [], 1: []}

    def observe(player: int, event: tuple[Any, ...]) -> None:
        logs[player].append(event)

    chooser = ReplayChooser(space, _ids(names), observe)
    play_game(game_ast, random.Random(seed), chooser=chooser, observer=observe)
    return logs
