"""An executable record that IS-MCTS is unavailable through this adapter.

The spec's headline matchup was "LLM vs all-IS-MCTS". It is not buildable, and
a README sentence saying so is a claim nobody can check. This is the check.

OpenSpiel's `ISMCTSBot` determinizes by calling `state.resample_from_infostate`
— it needs to construct a sibling world consistent with the observer's
information set. `CardlangState` (`cardlang/openspiel/game.py`) does not define
it, and cannot within its own representation: the state is `(seed, history)` and
the deal is a pure function of the seed, so there is no way to hold the
observer's hand fixed while permuting the opponents'. The constructive world
generator in `tests/openspiel_ready/worlds.py` does exactly that permutation,
but only by mutating a `RuntimeState` through `replay.run`'s
`on_first_decision` hook — which is not reachable through the pyspiel `State`
API and does not yield a `State` a bot could be handed.

These tests pass while that is true and REDDEN the day the adapter grows a
`resample_from_infostate`, which is the day the IS-MCTS baseline becomes
buildable. That is the point: the gap is recorded where it fails loudly, not
only in prose.
"""

from __future__ import annotations

import pytest

pytest.importorskip("pyspiel", reason="the OpenSpiel adapter needs the `openspiel` extra")


def test_cardlang_state_has_no_resample_from_infostate() -> None:
    """The structural fact. If this fails, delete this module and build the
    IS-MCTS agent the spec asked for."""
    import pyspiel

    from cardlang.openspiel import game as _adapter  # noqa: F401  (registration)

    state = pyspiel.load_game("cardlang_cheat").new_initial_state()
    state.apply_action(0)
    with pytest.raises(pyspiel.SpielError, match="ResampleFromInfostate"):
        state.resample_from_infostate(0, lambda: 0.5)


def test_ismcts_bot_cannot_step_a_cardlang_state() -> None:
    """The consequence, at the seam the spec's matchup table needed."""
    import numpy as np
    import pyspiel
    from open_spiel.python.algorithms.ismcts import ISMCTSBot
    from open_spiel.python.algorithms.mcts import RandomRolloutEvaluator

    from cardlang.openspiel import game as _adapter  # noqa: F401  (registration)

    game = pyspiel.load_game("cardlang_cheat")
    bot = ISMCTSBot(
        game=game,
        evaluator=RandomRolloutEvaluator(1, 0),
        uct_c=2.0,
        max_simulations=2,
        random_state=np.random.RandomState(0),
    )
    state = game.new_initial_state()
    state.apply_action(0)
    # Step past the forced `play_cards` announce. ISMCTS returns a lone legal
    # action without simulating, so it never resamples at a one-action node and
    # the seam under test would not be reached — the bot must be asked a
    # question it has to search to answer.
    while len(state.legal_actions()) == 1:
        state.apply_action(state.legal_actions()[0])
    with pytest.raises(pyspiel.SpielError, match="ResampleFromInfostate"):
        bot.step(state)


def test_the_blockage_is_not_specific_to_cheat() -> None:
    """It is the general adapter's representation, not one game's — so
    retreating to a shorter game (Leduc) does not recover the baseline
    either."""
    import pyspiel

    from cardlang.openspiel import game as _adapter  # noqa: F401  (registration)

    for short_name in ("cardlang_leduc_poker", "cardlang_kuhn_poker"):
        state = pyspiel.load_game(short_name).new_initial_state()
        state.apply_action(0)
        with pytest.raises(pyspiel.SpielError, match="ResampleFromInfostate"):
            state.resample_from_infostate(0, lambda: 0.5)
