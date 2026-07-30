"""Kuhn poker (2 players) — OpenSpiel readiness.

Harness configuration rationale:

- `depth=0`: Kuhn's whole tree is at most three decisions, and the harness's
  2-player swap branch needs the pause to coincide with the first decider
  (`p == d0`, so the swap never mutates a decider whose candidates were
  already computed). The greedy `legal[0]` line is `check, check` — two
  actions to Terminal — and P0's *second* decision sits only on the line
  `check, bet`, which greedy never takes (both players face the identical
  option set `[check, bet]`, so a global action-id order cannot make P0
  check and P1 bet). Every non-zero depth therefore pauses on P1. Depth 0 is
  the honest setting, not a convenience: it is the only pause the shared
  2-player branch can use.

  Depth 0 leaves the harness's `test_adapter_agrees_with_the_dsl_information
  _state` walk-and-compare loop empty (it still walks to Terminal under
  `adapter_terminal_steps` and compares returns). A depth-0 adapter proof
  that only compared returns would be the vacuously-green pattern, so
  `test_adapter_agrees_over_the_whole_kuhn_tree` below replaces it with
  something strictly stronger than the harness's single greedy line: EVERY
  node of EVERY deal — all six deals, all five lines each — with both
  players' information-state strings, the legal actions, and the terminal
  returns compared at each one.

- `swap_axis="any"`: Kuhn's recorded actions are betting vocabulary — none
  names a card — so any swap of the opponent's private card against the
  single undealt card replays legally.

- `stock_zone="deck"` (the default): after the deal, exactly one of the three
  cards is left in the deck, and that is the hidden pool the 2-player branch
  pairs the opponent's hand against.

- `adapter_terminal_steps=10`: the greedy line reaches Terminal in 2 steps.

Standing note on `test_seed_and_undrawn_randomness_are_not_observable`: Kuhn's
undealt stock is a single card, so the stock-reversal half of that proof is
vacuous here (`vacuous_stock=True` in the coverage record) — a 1-card pile has
no order to permute. The reseeding half is not vacuous and still bites.
"""

import random
from typing import Any

import pytest

from cardlang.openspiel.infostate import information_state
from cardlang.openspiel.replay import Pause, ReplayChooser, load, run
from cardlang.runtime.driver import play_game

from .harness import GAMES_DIR, GameSpec, ReadinessProofs

pyspiel = pytest.importorskip("pyspiel")

PATH = str(GAMES_DIR / "kuhn-poker.cardlang")
SHORT_NAME = "cardlang_kuhn_poker"


class TestReadiness(ReadinessProofs):
    spec = GameSpec(
        SHORT_NAME,
        "kuhn-poker.cardlang",
        depth=0,
        swap_axis="any",
        adapter_terminal_steps=10,
    )


def _deal(seed: int) -> tuple[str, ...]:
    r = run(PATH, seed, ())
    assert isinstance(r, Pause)
    return tuple(str(c) for q in range(2) for c in r.rs.zones.instance("hand", q).cards)


def _one_seed_per_deal() -> dict[tuple[str, ...], int]:
    """One representative seed per distinct deal. Kuhn deals 2 of 3 cards, so
    there are exactly 6 deals; asserting that count pins the search rather
    than letting a short scan silently under-cover the deal space."""
    seeds: dict[tuple[str, ...], int] = {}
    for seed in range(200):
        seeds.setdefault(_deal(seed), seed)
        if len(seeds) == 6:
            break
    assert len(seeds) == 6, f"only {len(seeds)} of the 6 Kuhn deals found: {sorted(seeds)}"
    return seeds


def test_adapter_agrees_over_the_whole_kuhn_tree() -> None:
    """Exhaustive adapter agreement: for every deal and every line, the
    registered pyspiel game and the DSL replay agree on the current player,
    the legal actions, BOTH players' information-state strings, and the
    terminal returns. This is the non-vacuous replacement for the harness's
    depth-0 walk (see the module docstring) and, because the pyspiel state
    re-simulates independently of these `run` calls, doubles as a
    whole-tree determinism check."""
    game = pyspiel.load_game(SHORT_NAME)
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
        if not isinstance(r, Pause):
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
        for q in range(2):
            assert state.information_state_string(q) == information_state(
                q, r.rs, r.obs_logs[q]
            ), f"seed={seed} history={history}: adapter info state for P{q} diverged"
        for a in r.legal:
            walk(seed, history + [a])

    for deal, seed in sorted(_one_seed_per_deal().items()):
        assert len(deal) == 2, deal
        walk(seed, [])
    # 6 deals x (root + P1 after check + P1 after bet + P0 after check-bet)
    # = 24 decision nodes, and 6 x 5 = 30 terminal lines.
    assert (nodes, terminals) == (24, 30), (nodes, terminals)


def test_the_imported_raise_is_absent_from_the_action_space() -> None:
    """Whole-library import does NOT inflate the action space (the family-
    library tier's first anchor edge, issue #143). `raise` arrives with `uses
    poker_betting` and lands in the game's move-type table, but Kuhn's
    `offering` list omits it — and the OpenSpiel action space is derived from
    the `offering`/`offer` lists, never from the move-type table
    (`encoding.ActionSpace.for_game`). So the imported-but-unoffered move
    contributes no id, and it is never legal at any node either (the whole
    tree is walked above; here the space itself is checked)."""
    game_ast, space = load(PATH)
    assert "raise" in {m.name for m in game_ast.move_types}, (
        "the library's `raise` should be spliced into the game's move types"
    )
    strings = {space.to_string(a) for a in range(space.num_distinct_actions)}
    assert "raise" not in strings, (
        "an imported-but-unoffered move type minted an action id — whole-library "
        "import is inflating the action space"
    )
    # 52 card-block slots (the standard grid every deck maps onto) plus the
    # four offered move types, and nothing else.
    assert space.num_distinct_actions == 52 + 4
    assert {space.to_string(a) for a in range(52, 56)} == {"check", "bet", "call", "fold"}


def test_a_fold_never_reveals_the_folded_card_but_a_showdown_does() -> None:
    """The positive shape of Kuhn's information structure, which the
    swap-based leak-closure proofs never confirm: the two terminal routes
    differ in exactly what the opponent learns.

    A fold mucks the folded card (a `Muck` — trivial to EVERY observer, its
    owner included), so the opponent's log carries the movement with no card
    identity at all. A showdown flips both private cards into `PublicHand`s,
    so each player's log carries the other's card by name.
    """
    seed = _one_seed_per_deal()[("J♠", "K♠")]

    # Fold route: P0 bets, P1 folds. P1's card mucks unseen by P0.
    fold_events = _events_for_line(seed, ["bet", "fold"])
    muck_moves = [
        e for e in fold_events[0]
        if e[0] == "move" and e[1] == "hand[1]" and e[3] == "muck"
    ]
    assert muck_moves, "P0 never observed the folded card leave P1's hand"
    for e in muck_moves:
        assert e[4] is None, f"P0 saw the folded card's identity leak to the muck: {e}"

    # Showdown route: check, check. Both cards land in PublicHands by name.
    show_events = _events_for_line(seed, ["check", "check"])
    for observer, owner in ((0, 1), (1, 0)):
        reveals = [
            e for e in show_events[observer]
            if e[0] == "move" and e[3] == f"shown[{owner}]"
        ]
        assert reveals, f"P{observer} never observed P{owner}'s showdown reveal"
        assert any(
            isinstance(e[4], tuple) and len(e[4]) == 1 and isinstance(e[4][0], str)
            for e in reveals
        ), f"P{observer} did not learn P{owner}'s card at the showdown: {reveals}"


def _events_for_line(seed: int, names: list[str]) -> dict[int, list[tuple[Any, ...]]]:
    """Every observer's full event log for a COMPLETED hand, the line given by
    move-type name. `replay.run` discards the logs when it returns Terminal,
    so this drives the game directly with the same `ReplayChooser` the
    adapter uses."""
    game_ast, space = load(PATH)
    by_name = {space.to_string(a): a for a in range(space.num_distinct_actions)}
    logs: dict[int, list[tuple[Any, ...]]] = {0: [], 1: []}

    def observe(player: int, event: tuple[Any, ...]) -> None:
        logs[player].append(event)

    chooser = ReplayChooser(space, tuple(by_name[n] for n in names), observe)
    play_game(game_ast, random.Random(seed), chooser=chooser, observer=observe)
    return logs
