"""Metric computation, on a hand-written transcript.

The transcript below is authored, not captured, so every rate has a value
worked out by hand — a metric that silently changed meaning would have to
disagree with arithmetic done here, not merely with a recorded run.

The fixture holds four plays:
  P0 claims one Ace and plays A♠   — truthful, one Ace in hand.  Windows: P1 allow, P2 call.
  P1 claims two Twos and plays K♦,K♣ — an ELECTIVE lie (held two 2s). Windows: P2 call.
  P2 claims one Three and plays 9♥ — a FORCED lie (held no 3s).   Windows: P3 allow.
  P3 claims one Four and plays 7♠  — a FORCED lie. P0 holds all four 4s, so the
                                     claim is PROVABLY false to P0, who allows.
"""

from __future__ import annotations

from typing import Any

from ..metrics import aggregate, reconstruct_plays


def _announce(
    step: int, player: int, rank: str, count: int, truthful: int
) -> list[dict[str, Any]]:
    """A play's opening PAIR: the forced `play_cards` announce, then the public
    count. Two decisions, because the count is its own decision — returning the
    pair keeps every fixture below reading as one play per call."""
    common = {"player": player, "agent": f"a{player}", "llm": {}}
    return [
        {
            **common,
            "step": step,
            "action": "play_cards",
            "legal": ["play_cards"],
            "facts": {
                "kind": "announce",
                "claim_rank": rank,
                "truthful_available": truthful,
                "hand_size": 13,
            },
        },
        {
            **common,
            "step": step + 1,
            "action": str(count),
            "legal": [str(n) for n in range(1, 14)],
            "facts": {
                "kind": "count",
                "claim_rank": rank,
                "claimed_count": count,
                "truthful_available": truthful,
                "hand_size": 13,
            },
        },
    ]


def _card(step: int, player: int, card: str, rank: str) -> dict[str, Any]:
    return {
        "step": step,
        "player": player,
        "agent": f"a{player}",
        "action": card,
        "legal": [card],
        "facts": {"kind": "card", "card": card, "rank": card[:-1], "claim_rank": rank},
        "llm": {},
    }


def _window(
    step: int, player: int, rank: str, count: int, claimant: int, called: bool, provable: bool
) -> dict[str, Any]:
    return {
        "step": step,
        "player": player,
        "agent": f"a{player}",
        "action": "call_cheat" if called else "allow",
        "legal": ["allow", "call_cheat"],
        "facts": {
            "kind": "window",
            "claim_rank": rank,
            "claim_count": count,
            "claimant": claimant,
            "challenged": called,
            "provably_false": provable,
            "observer_holds_claimed": 4 if provable else 0,
        },
        "llm": {},
    }


def _record() -> dict[str, Any]:
    decisions = [
        *_announce(0, 0, "A", 1, truthful=1),
        _card(2, 0, "A♠", "A"),
        _window(3, 1, "A", 1, 0, called=False, provable=False),
        _window(4, 2, "A", 1, 0, called=True, provable=False),
        *_announce(5, 1, "2", 2, truthful=2),
        _card(7, 1, "K♦", "2"),
        _card(8, 1, "K♣", "2"),
        _window(9, 2, "2", 2, 1, called=True, provable=False),
        *_announce(10, 2, "3", 1, truthful=0),
        _card(12, 2, "9♥", "3"),
        _window(13, 3, "3", 1, 2, called=False, provable=False),
        *_announce(14, 3, "4", 1, truthful=0),
        _card(16, 3, "7♠", "4"),
        _window(17, 0, "4", 1, 3, called=False, provable=True),
    ]
    return {
        "matchup": "fixture",
        "game_index": 0,
        "seed": 0,
        "seats": {"0": "a0", "1": "a1", "2": "a2", "3": "a3"},
        "history": list(range(len(decisions))),
        "decisions": decisions,
        "returns": [1.0, 0.0, 0.0, 0.0],
        "terminal": True,
        "truncated": False,
        "num_decisions": len(decisions),
        "wall_seconds": 0.0,
    }


def test_reconstruct_plays_groups_announce_cards_and_windows() -> None:
    plays = reconstruct_plays(_record()["decisions"])
    assert [p.actor for p in plays] == [0, 1, 2, 3]
    assert [p.claimed_count for p in plays] == [1, 2, 1, 1]
    assert [p.cards for p in plays] == [["A♠"], ["K♦", "K♣"], ["9♥"], ["7♠"]]
    assert [len(p.windows) for p in plays] == [2, 1, 1, 1]
    assert [p.lied for p in plays] == [False, True, True, True]
    assert [p.forced for p in plays] == [False, False, True, True]


def test_lying_rates() -> None:
    agents = aggregate([_record()])["agents"]
    # a0: one play, truthful.
    assert agents["a0"]["plays"] == 1
    assert agents["a0"]["lying_rate"] == 0.0
    assert agents["a0"]["elective_lie_rate"] == 0.0
    # a1: one play, lied although two 2s were in hand — the elective case.
    assert agents["a1"]["lies"] == 1
    assert agents["a1"]["elective_lies"] == 1
    assert agents["a1"]["forced_lies"] == 0
    assert agents["a1"]["elective_lie_rate"] == 1.0
    # a2: forced. Counted as a lie, but NOT as elective, and its denominator
    # (plays with a truthful option) is zero — so the rate is None, not 0.0.
    assert agents["a2"]["forced_lies"] == 1
    assert agents["a2"]["plays_with_truthful_option"] == 0
    assert agents["a2"]["elective_lie_rate"] is None
    assert agents["a2"]["lying_rate"] == 1.0


def test_challenge_precision_and_recall() -> None:
    agents = aggregate([_record()])["agents"]
    # a2 faced two windows and called both: one on a true claim (P0's Ace) and
    # one on a real lie (P1's Kings). Precision 1/2; both false claims it faced
    # were caught, so recall 1/1.
    assert agents["a2"]["challenge_opportunities"] == 2
    assert agents["a2"]["challenges_made"] == 2
    assert agents["a2"]["challenges_correct"] == 1
    assert agents["a2"]["challenge_precision"] == 0.5
    assert agents["a2"]["false_claims_faced"] == 1
    assert agents["a2"]["challenge_recall"] == 1.0
    # a1 had one opportunity, on a true claim, and allowed: precision has no
    # denominator, and recall has no false claim to have caught.
    assert agents["a1"]["challenges_made"] == 0
    assert agents["a1"]["challenge_precision"] is None
    assert agents["a1"]["challenge_recall"] is None


def test_provable_versus_improbable_detection() -> None:
    agents = aggregate([_record()])["agents"]
    # a0 faced exactly one lie and it was provably false to them; they allowed.
    assert agents["a0"]["provable_opportunities"] == 1
    assert agents["a0"]["provable_caught"] == 0
    assert agents["a0"]["provable_lie_detection"] == 0.0
    assert agents["a0"]["improbable_opportunities"] == 0
    assert agents["a0"]["improbable_lie_detection"] is None
    # a2's one caught lie was NOT provable — it belongs to the improbable bucket.
    assert agents["a2"]["improbable_opportunities"] == 1
    assert agents["a2"]["improbable_caught"] == 1
    assert agents["a2"]["improbable_lie_detection"] == 1.0
    assert agents["a2"]["provable_opportunities"] == 0


def test_win_rate_uses_returns() -> None:
    agents = aggregate([_record()])["agents"]
    assert agents["a0"]["wins"] == 1 and agents["a0"]["win_rate"] == 1.0
    assert agents["a1"]["wins"] == 0 and agents["a1"]["win_rate"] == 0.0


def test_fallback_rate_counts_llm_fallbacks() -> None:
    record = _record()
    record["decisions"][0]["llm"] = {"fallback": True}
    record["decisions"][4]["llm"] = {"fallback": False}
    agents = aggregate([record])["agents"]
    assert agents["a0"]["fallbacks"] == 1
    assert agents["a0"]["fallback_rate"] == 1 / agents["a0"]["decisions"]
    assert agents["a1"]["fallbacks"] == 0


def test_rates_over_zero_opportunities_are_none_not_zero() -> None:
    """The distinction the whole metrics layer turns on: "never did it" and
    "was never asked" must not render identically."""
    empty = _record()
    empty["decisions"] = []
    agents = aggregate([empty])["agents"]
    for stats in agents.values():
        assert stats["lying_rate"] is None
        assert stats["challenge_precision"] is None
        assert stats["provable_lie_detection"] is None


def test_aggregate_sums_across_games() -> None:
    summary = aggregate([_record(), _record()])
    assert summary["games"] == 2
    assert summary["agents"]["a1"]["plays"] == 2
    assert summary["agents"]["a1"]["elective_lies"] == 2


def test_a_play_truncated_mid_selection_is_dropped(  ) -> None:
    """A game cut off between the announce and its card picks did not contain a
    play, and must not be counted as one.

    The danger is specific: `lied` is derived from the cards recorded, so a
    partial selection that happens to start with matching cards reports as an
    HONEST play that was never made — inflating truthfulness exactly in the
    truncation case `max_decisions` permits.
    """
    record = _record()
    # Keep the last announce and its FIRST card, drop the rest (claimed 1 of 1
    # here, so extend the claim to 2 to leave it genuinely incomplete).
    decisions = record["decisions"][:14]
    decisions.extend(_announce(14, 3, "4", 2, truthful=2))
    decisions.append(_card(16, 3, "4♠", "4"))   # only 1 of the 2 announced
    record["decisions"] = decisions
    record["terminal"] = False
    record["truncated"] = True

    plays = reconstruct_plays(decisions)
    assert [p.actor for p in plays] == [0, 1, 2], "the incomplete play leaked in"
    assert all(len(p.cards) == p.claimed_count for p in plays)

    stats = aggregate([record])["agents"]
    # Seat 3 announced but never completed a play, so it has none — and no
    # spurious "honest play" credited to it.
    assert stats["a3"]["plays"] == 0
    assert stats["a3"]["lies"] == 0
    assert stats["a3"]["lying_rate"] is None


def test_a_complete_play_at_the_very_end_is_kept() -> None:
    """The complement: a play whose last card is the final decision is complete
    and must still count. Dropping it would trade one bug for another."""
    # announce + count + the single card it claimed
    decisions = _record()["decisions"][:3]
    plays = reconstruct_plays(decisions)
    assert len(plays) == 1 and plays[0].cards == ["A♠"]
