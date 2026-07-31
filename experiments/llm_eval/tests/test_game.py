"""End-to-end games through the registered adapter, offline.

These need `pyspiel` (the `openspiel` extra) and the corpus directory — the same
prerequisites the readiness proofs have. They skip rather than fail without it,
because a core install legitimately cannot run them; the skip is visible in the
run summary.
"""

from __future__ import annotations

import pytest

from ..agents import DecisionView, RandomAgent, RuleAgent, build_agent
from ..metrics import aggregate, reconstruct_plays
from ..providers import FakeProvider
from ..referee import load_game, play_game, replay_views

pytest.importorskip("pyspiel", reason="the OpenSpiel adapter needs the `openspiel` extra")


@pytest.fixture(scope="module")
def game() -> object:
    return load_game("cardlang_cheat")


def _seats(kind: str, seed: int = 0) -> dict[int, object]:
    if kind == "fake_llm":
        provider = FakeProvider(replies=['{"action": 0, "reasoning": "first legal"}'])
        focus = build_agent({"kind": "llm", "name": "fake_llm"}, seed, provider)
    else:
        focus = build_agent({"kind": kind}, seed, None)
    others = [build_agent({"kind": "random"}, seed + i, None) for i in range(1, 4)]
    return {0: focus, 1: others[0], 2: others[1], 3: others[2]}


def test_rule_vs_random_reaches_a_terminal_state(game: object) -> None:
    record = play_game(game, _seats("rule"), seed=5, matchup="t", game_index=0)  # type: ignore[arg-type]
    assert record.terminal and not record.truncated
    assert record.num_decisions > 0
    assert sum(1 for r in record.returns if r > 0) == 1, "Cheat has exactly one winner"


def test_fake_provider_game_reaches_a_terminal_state(game: object) -> None:
    """A full game driven by the fake provider — the smoke-test rung below any
    real model call (spec §6)."""
    record = play_game(
        game, _seats("fake_llm"), seed=11, matchup="t", game_index=0, max_decisions=4000  # type: ignore[arg-type]
    )
    assert record.terminal, "the canned-reply game never terminated"
    llm_decisions = [d for d in record.decisions if d.agent == "fake_llm"]
    assert llm_decisions, "the fake LLM never moved"
    assert not any(d.llm["fallback"] for d in llm_decisions), (
        "a well-formed canned reply must never fall back"
    )


def test_truncation_is_recorded_not_scored(game: object) -> None:
    record = play_game(
        game, _seats("random"), seed=0, matchup="t", game_index=0, max_decisions=10  # type: ignore[arg-type]
    )
    assert record.truncated and not record.terminal
    assert record.num_decisions == 10
    assert record.returns == [0.0, 0.0, 0.0, 0.0]
    summary = aggregate([record.as_dict()])
    assert summary["games_truncated"] == 1
    for stats in summary["agents"].values():
        assert stats["games_scored"] == 0
        assert stats["win_rate"] is None, "a truncated game must not produce a win rate"


def test_history_replays_to_the_same_views(game: object) -> None:
    """`(seed, history)` is enough to reconstruct every prompt — which is why
    transcripts need not store information states to be auditable."""
    record = play_game(
        game, _seats("rule"), seed=7, matchup="t", game_index=0, max_decisions=120,  # type: ignore[arg-type]
        store_infostates=True,
    )
    views = replay_views(game, record.seed, record.history)
    assert len(views) == len(record.decisions)
    for view, decision in zip(views, record.decisions, strict=True):
        assert view.player == decision.player
        assert view.legal_strings == decision.legal
        assert view.infostate == decision.infostate


def test_every_decision_shape_is_recognized(game: object) -> None:
    """Cheat poses exactly three decision shapes; `DecisionView.kind` raises on
    anything else, so a long random walk that never raises is the coverage
    claim — and all three must actually appear, or the walk proves nothing."""
    record = play_game(
        game, _seats("random"), seed=3, matchup="t", game_index=0, max_decisions=600  # type: ignore[arg-type]
    )
    kinds = {d.facts["kind"] for d in record.decisions}
    assert kinds == {"announce", "card", "window"}


def test_claim_cycle_order_matches_the_game(game: object) -> None:
    """`infostate.RANKS` carries Cheat's claim cycle, not the engine's aces-high
    rank order. Pinned against the cycle a live game actually walks — the
    `next_rank` function in `docs/games/cheat.cardlang` — rather than restated,
    so the two cannot drift.
    """
    from ..infostate import RANKS

    record = play_game(
        game, _seats("random"), seed=6, matchup="t", game_index=0, max_decisions=400  # type: ignore[arg-type]
    )
    claims = [
        d.facts["claim_rank"] for d in record.decisions if d.facts["kind"] == "announce"
    ]
    assert len(claims) > len(RANKS), "the walk must wrap the cycle at least once"
    for before, after in zip(claims, claims[1:], strict=False):
        assert after == RANKS[(RANKS.index(before) + 1) % len(RANKS)], (
            f"the game advanced {before} -> {after}, which is not the cycle "
            f"order this harness assumes"
        )


def test_reconstructed_plays_match_the_announcements(game: object) -> None:
    record = play_game(
        game, _seats("rule"), seed=9, matchup="t", game_index=0, max_decisions=400  # type: ignore[arg-type]
    )
    plays = reconstruct_plays([d.__dict__ for d in record.decisions])
    assert plays
    for play in plays:
        assert len(play.cards) == play.claimed_count
        assert 1 <= play.claimed_count <= 4


def test_rule_agent_never_lies_when_it_can_tell_the_truth(game: object) -> None:
    """The baseline's stated play policy, checked against its actual plays."""
    seats = {i: RuleAgent(seed=i, challenge_prob=0.1) for i in range(4)}
    record = play_game(game, seats, seed=13, matchup="t", game_index=0, max_decisions=600)  # type: ignore[arg-type]
    plays = reconstruct_plays([d.__dict__ for d in record.decisions])
    assert plays
    for play in plays:
        if play.truthful_available > 0:
            assert not play.lied, (
                f"rule agent lied with {play.truthful_available} "
                f"{play.claim_rank}(s) in hand: played {play.cards}"
            )
        else:
            assert play.forced and play.lied


def test_rule_agent_always_calls_a_provable_lie(game: object) -> None:
    """The challenge policy's deterministic half. The random half is separate,
    so a run where it never fires still pins this."""
    seats = {i: RuleAgent(seed=i, challenge_prob=0.0) for i in range(4)}
    # Seed 18 is chosen, not arbitrary: an all-rule table lies only when forced,
    # so a *provable* lie (the observer holding enough of the claimed rank) is
    # rare. This seed yields eight across 139 windows, so the assertion below is
    # not vacuous — hence the guard.
    record = play_game(game, seats, seed=18, matchup="t", game_index=0, max_decisions=800)  # type: ignore[arg-type]
    windows = [d for d in record.decisions if d.facts["kind"] == "window"]
    provable = [d for d in windows if d.facts["provably_false"]]
    assert len(provable) >= 5, "seed 18 no longer exercises the provable-lie branch"
    assert all(d.facts["challenged"] for d in provable)
    assert not any(
        d.facts["challenged"] for d in windows if not d.facts["provably_false"]
    ), "challenge_prob=0 must make the agent call ONLY on provable lies"


def test_agents_are_seed_reproducible(game: object) -> None:
    first = play_game(game, _seats("random", 4), seed=2, matchup="t", game_index=0)  # type: ignore[arg-type]
    second = play_game(game, _seats("random", 4), seed=2, matchup="t", game_index=0)  # type: ignore[arg-type]
    assert first.history == second.history
    assert first.returns == second.returns


def test_agents_only_ever_return_legal_actions(game: object) -> None:
    """`play_game` raises on an illegal action; a long mixed-agent walk that
    completes is the pin. Kept explicit so the guarantee has a named test."""
    seats: dict[int, object] = {
        0: RuleAgent(seed=1),
        1: RandomAgent(seed=2),
        2: RuleAgent(seed=3, challenge_prob=0.5),
        3: RandomAgent(seed=4),
    }
    record = play_game(game, seats, seed=17, matchup="t", game_index=0, max_decisions=900)  # type: ignore[arg-type]
    assert record.num_decisions > 50


def test_decision_view_rejects_an_unknown_shape() -> None:
    """The wall behind `kind()`: an unrecognized legal-move set is loud, not
    silently routed to the card branch."""
    view = DecisionView(0, "P0|", [1, 2], ["bid_three", "double"])
    with pytest.raises(ValueError, match="unrecognized decision shape"):
        view.kind()


def test_bluff_prob_defaults_to_the_truthful_policy(game: object) -> None:
    """The knob is off by default, so every result measured before it existed
    remains comparable: `bluff_prob=0.0` must reproduce the shipped baseline
    exactly, action for action."""
    def table(**kw: float) -> dict[int, object]:
        return {i: RuleAgent(seed=i, challenge_prob=0.1, **kw) for i in range(4)}  # type: ignore[arg-type]

    a = play_game(game, table(), seed=13, matchup="t", game_index=0, max_decisions=400)  # type: ignore[arg-type]
    b = play_game(game, table(bluff_prob=0.0), seed=13, matchup="t", game_index=0, max_decisions=400)  # type: ignore[arg-type]
    assert a.history == b.history


def test_bluff_prob_produces_elective_lies(game: object) -> None:
    """The knob's whole purpose: turn a truthful-when-possible opponent into a
    tunable source of detectable lies. Off => zero elective lies; on => many."""
    from ..metrics import aggregate

    def measure(bluff: float) -> float:
        seats = {i: RuleAgent(seed=i, challenge_prob=0.1, bluff_prob=bluff) for i in range(4)}
        rec = play_game(game, seats, seed=13, matchup="t", game_index=0, max_decisions=600)  # type: ignore[arg-type]
        stats = aggregate([rec.as_dict()])["agents"]["rule"]
        rate = stats["elective_lie_rate"]
        assert rate is not None, "no play had a truthful option — the seed is uninformative"
        return float(rate)

    assert measure(0.0) == 0.0
    assert measure(0.8) > 0.3, "raising bluff_prob did not produce elective lies"
