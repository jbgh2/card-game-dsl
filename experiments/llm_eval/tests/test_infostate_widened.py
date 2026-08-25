"""Soundness of the WIDENED provable-lie criterion, against ground truth.

The narrow criterion is arithmetic over one hand and can be proved exhaustively
(`test_infostate.py`). The widened one reasons over an event log across a whole
game, and enumeration cannot show that the reasoning tracks reality — only
execution can. So the load-bearing test here is an oracle: play many games, and
for EVERY window where the criterion fires, check against the referee's ground
truth that the play really was a lie.

A false positive would be worse than useless. `provable_lie_detection` is the
theory-of-mind headline; if the criterion can fire on a truthful claim, the
metric stops measuring detection of the provable and starts measuring detection
of the maybe-provable, and the number cannot be reported.
"""

from __future__ import annotations

from typing import Any

import pytest

from .. import infostate as istate
from ..agents import RandomAgent, RuleAgent
from ..metrics import reconstruct_plays
from ..referee import load_game, play_game

pytest.importorskip("pyspiel", reason="the OpenSpiel adapter needs the `openspiel` extra")

# Random tables lie constantly and challenge constantly, so they generate far
# more flips — and therefore far more of the evidence the widened criterion
# reasons over — than a table of competent players.
SEEDS = range(12)


def _games() -> list[Any]:
    game = load_game("cardlang_cheat")
    out: list[Any] = []
    for seed in SEEDS:
        seats: dict[int, Any] = {p: RandomAgent(seed=seed * 10 + p) for p in range(4)}
        seats[0] = RuleAgent(seed=seed, challenge_prob=0.25)
        out.append(
            play_game(game, seats, seed=seed, matchup="w", game_index=0, max_decisions=500)
        )
    return out


@pytest.fixture(scope="module")
def games() -> list[Any]:
    return _games()


def test_widened_criterion_never_fires_on_a_true_claim(games: list[Any]) -> None:
    """THE soundness oracle. Every window where `provably_false` is True is
    checked against the cards actually played, which the referee knows and the
    observer does not."""
    fired = 0
    for record in games:
        for play in reconstruct_plays([d.__dict__ for d in record.decisions]):
            for window in play.windows:
                if window["provably_false"]:
                    fired += 1
                    assert play.lied, (
                        f"UNSOUND: the criterion called P{window['responder']}'s "
                        f"window provable, but P{play.actor} truthfully played "
                        f"{play.cards} as {play.claimed_count}x{play.claim_rank}"
                    )
    assert fired >= 50, (
        f"only {fired} windows fired across {len(games)} games — the oracle is "
        f"too thin to be evidence; widen the seed range"
    )


def test_widened_is_a_strict_superset_of_hand_only(games: list[Any]) -> None:
    """Monotonicity: widening may only ADD opportunities. A window the narrow
    criterion proves must stay proved, or the change is a rewrite rather than an
    extension — and the two reported numbers would not be comparable."""
    narrow = wide = 0
    for record in games:
        for decision in record.decisions:
            facts = decision.facts
            if facts["kind"] != "window":
                continue
            if facts["provably_false_hand_only"]:
                narrow += 1
                assert facts["provably_false"], (
                    "a window provable from the hand alone is no longer provable "
                    "with MORE information — the widened criterion is not a superset"
                )
            if facts["provably_false"]:
                wide += 1
    assert narrow > 0, "no narrow-criterion windows — the comparison is vacuous"
    assert wide > narrow, (
        f"widening added nothing ({wide} vs {narrow}) — the flip evidence is not "
        f"being used, so the change is inert"
    )


def test_flip_knowledge_is_discarded_when_the_claimant_collects(games: list[Any]) -> None:
    """The invalidation rule is load-bearing, not decorative: a claimant who
    collects an unseen pile could hold anything, so flip-derived exclusions must
    be dropped. Checked by finding a real line where a pickup shrinks the
    exclusion set."""
    from ..referee import load_game, replay_views

    game = load_game("cardlang_cheat")
    shrank = False
    for record in games:
        views = replay_views(game, record.seed, record.history)
        previous: dict[int, int] = {}
        for view in views:
            info = istate.parse(view.infostate)
            claimant = info.claimant
            if claimant is None:
                # No play stands, so there is no claimant to exclude and the
                # exclusion set is a different quantity. Comparing it against
                # the neighbouring ones would manufacture a shrink.
                continue
            size = len(istate.cards_known_elsewhere(info, claimant))
            if view.player in previous and size < previous[view.player]:
                shrank = True
            previous[view.player] = size
        if shrank:
            break
    assert shrank, (
        "the exclusion set never shrank across any observed line — the "
        "invalidation branch is never taken, so its correctness is untested"
    )


def test_cards_known_elsewhere_excludes_the_claimant() -> None:
    """A card flipped INTO the claimant's hand is evidence FOR the claim, and
    must never be counted as an exclusion."""
    obs = (
        "('move', 'flipped', ('A♠', 'A♥'), 'hand[2]', 2)"
        ";('move', 'flipped', ('K♠',), 'hand[1]', 1)"
    )
    info = istate.Info(player=0, zones={"hand[0]": []}, state={"claimant": "2"}, obs=obs)
    known = istate.cards_known_elsewhere(info, claimant=2)
    assert known == {"K♠": 1}, "the claimant's own collected cards leaked in"


def test_pile_pickup_by_the_claimant_clears_the_evidence() -> None:
    obs_before = "('move', 'flipped', ('A♠', 'A♥'), 'hand[1]', 2)"
    obs_after = obs_before + ";('move', 'pile', 6, 'hand[2]', 6)"
    zones: dict[str, list[str] | int | None] = {"hand[0]": []}
    keep = istate.Info(player=0, zones=zones, state={}, obs=obs_before)
    drop = istate.Info(player=0, zones=zones, state={}, obs=obs_after)
    assert len(istate.cards_known_elsewhere(keep, claimant=2)) == 2
    assert istate.cards_known_elsewhere(drop, claimant=2) == {}
    # A pickup by SOMEONE ELSE does not invalidate anything.
    other = istate.Info(
        player=0, zones=zones, state={},
        obs=obs_before + ";('move', 'pile', 6, 'hand[3]', 6)",
    )
    assert len(istate.cards_known_elsewhere(other, claimant=2)) == 2


def test_widened_criterion_uses_the_flip_evidence() -> None:
    """The worked case: the observer holds two Aces and has watched the other
    two flipped into a third player's hand, so a claim of even one Ace is
    impossible — which the narrow criterion cannot see."""
    obs = "('move', 'flipped', ('A♦', 'A♣'), 'hand[1]', 2)"
    info = istate.Info(
        player=0,
        zones={"hand[0]": ["A♠", "A♥", "3♠"]},
        state={"claim_rank": "A", "claim_count": "1", "claimant": "2"},
        obs=obs,
    )
    assert istate.provably_false(info, "A", 1)
    assert not istate.provably_false_hand_only(info, "A", 1)
    # And with the same evidence, a claim by the player HOLDING those aces is
    # not proved by them.
    assert not istate.provably_false(info, "A", 1, claimant=1)


def test_parse_events_round_trips_a_real_log(games: list[Any]) -> None:
    from ..referee import load_game, replay_views

    game = load_game("cardlang_cheat")
    record = games[0]
    views = replay_views(game, record.seed, record.history)
    info = istate.parse(views[-1].infostate)
    events = istate.parse_events(info.obs)
    assert len(events) > 20
    assert all(isinstance(e, tuple) for e in events)
    assert events[0][0] == "move" and events[0][1] == "deck"


def test_parse_events_refuses_a_non_tuple_entry() -> None:
    """Loud, not skipped: a dropped event weakens the exclusion analysis into
    unsoundness-by-omission."""
    with pytest.raises(ValueError, match="not a tuple"):
        istate.parse_events("('move', 'a', 1, 'b', 1);42")


def test_zone_player_reads_only_hand_zones() -> None:
    assert istate.zone_player("hand[3]") == 3
    assert istate.zone_player("pile") is None
    assert istate.zone_player("flipped") is None
