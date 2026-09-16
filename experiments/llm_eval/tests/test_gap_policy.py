"""The memoryless policy-aware reference: P(the standing claim is a lie |
the observer's information state, the claimant's declared bluff_prob),
exact and engine-free.

`gap_policy.reference` models the claimant's hand as a uniform draw from the
cards the observer cannot place, weights each possible holding of the
claimed rank by the likelihood the `RuleAgent` count policy would have
announced the observed count, and reads the lie off the holding. It is what a
reader who knows the opponents' dispositions predicts from the claim and the
table alone; the line's earlier public actions are not conditioned on
(`belief-calibration-spec.md` §3 names it beside R2 and says what it
ignores).

property:        `count_likelihood` is the `RuleAgent` count policy — the
                 distribution `RuleAgent._count` produces, obtained by driving
                 the agent's own method with a fixed coin, never restated —
                 pinned against the agent by simulation on every cell;
                 `holdings` is the hypergeometric law, pinned against
                 exhaustive enumeration; `reference` is the hand-computed
                 value on constructed windows, exactly 1.0 wherever R1 fires,
                 and within [0, 1] on every window of a real archived game;
                 the module reaches no engine and no transcript.
domain:          holdings t over `range(COPIES_PER_RANK + 1)` crossed with
                 hand sizes around every boundary of the legal count set
                 (`HAND_SIZES`) and bluff coins {0, the shipped 0.4, 1};
                 pools of up to nine cards crossed with every copy count and
                 hand size for the enumeration; the two real fixtures (an
                 R1-fires window and an abstains window whose flip record
                 places a copy elsewhere) plus their variants; every seat-0
                 window of the committed null control's first game for the
                 real-bank pin.
registry:        `infostate.COPIES_PER_RANK`; the count policy:
                 `agents.RuleAgent._count`; the provability rule the fires
                 pin leans on: experiments/llm_eval/tests/test_infostate_widened.py
does not prove:  anything about the full policy-aware posterior (R2), which
                 conditions on the whole public line — this reference is
                 memoryless by definition, and the distance between the two
                 is not measured here (issue #707).
"""

from __future__ import annotations

import ast
import itertools
import json
import math
import random
from collections import Counter
from dataclasses import asdict
from pathlib import Path
from typing import Any

import pytest

from ..agents import DecisionView, RuleAgent
from ..gap_policy import (
    REQUIRED_WINDOW_FIELDS,
    count_likelihood,
    holdings,
    record_for,
    reference,
)
from ..infostate import COPIES_PER_RANK, parse

BLUFFS = (0.0, 0.4, 1.0)
#: Hand sizes around every boundary of the count set: one card (the smallest
#: legal count is the whole hand), each holding and one over it, the deck's
#: copies, one over that, and a full deal.
HAND_SIZES = tuple(sorted({1, 2, 3, 4, 5, COPIES_PER_RANK, COPIES_PER_RANK + 1, 13}))
RANK = "A"
FILLERS = [f"{r}{s}" for r in ("2", "3", "4", "5", "6", "7", "8", "9") for s in "♠♥♦♣"]


def _hand(t: int, size: int) -> list[str]:
    return [f"{RANK}{s}" for s in "♠♥♦♣"[:t]] + FILLERS[: size - t]


def _info(hand: list[str]) -> Any:
    cards = ",".join(hand)
    return parse(
        f"P0|deck=#0;flipped=[];pile=#0;played=#0;hand[0]=[{cards}];hand[1]=#13;"
        f"hand[2]=#13;hand[3]=#13|state:challenged=False;challenger=None;claim_count=0;"
        f"claim_rank={RANK};claimant=None;responder=None;window_open=False;"
        f"won={{0:False,1:False,2:False,3:False}}|obs:"
    )


def _cells() -> list[tuple[int, int, float]]:
    return [
        (t, size, b)
        for t in range(COPIES_PER_RANK + 1)
        for size in HAND_SIZES
        if size >= t
        for b in BLUFFS
    ]


@pytest.mark.parametrize(("t", "size", "b"), _cells())
def test_count_likelihood_is_the_agents_own_distribution(t: int, size: int, b: float) -> None:
    """Simulate the agent: the support must match exactly, the frequencies
    within sampling error, and both coin values must be the agent's own
    branches — the likelihood is read off the method, so a policy edit that
    this test does not see is one the reference does not see either."""
    view = DecisionView(
        player=0,
        infostate="",
        legal_actions=list(range(size)),
        legal_strings=[str(n) for n in range(1, size + 1)],
    )
    info = _info(_hand(t, size))
    draws = 600
    seen: Counter[int] = Counter()
    for seed in range(draws):
        agent = RuleAgent(seed=seed, bluff_prob=b)
        seen[view.legal_actions.index(agent._count(view, info)) + 1] += 1
    law = count_likelihood(t, size, b)
    assert math.isclose(sum(law.values()), 1.0)
    assert set(law) == set(seen), f"support differs: law {law} vs agent {dict(seen)}"
    for count, p in law.items():
        assert abs(seen[count] / draws - p) < 0.07, (count, p, seen[count] / draws)


@pytest.mark.parametrize(
    ("pool", "copies", "size"),
    [(n, k, h) for n in range(1, 10) for k in range(0, min(n, COPIES_PER_RANK) + 1) for h in range(0, n + 1)],
)
def test_holdings_is_the_hypergeometric_law(pool: int, copies: int, size: int) -> None:
    cards = list(range(pool))
    marked = set(cards[:copies])
    seen: Counter[int] = Counter()
    for hand in itertools.combinations(cards, size):
        seen[len(marked & set(hand))] += 1
    total = sum(seen.values())
    law = holdings(pool, copies, size)
    assert set(law) == set(seen)
    for t, n in seen.items():
        assert math.isclose(law[t], n / total, rel_tol=1e-12)


#: A real window where R1 fires: the observer holds two Aces and three are
#: claimed.
FIRES = (
    "P1|deck=#0;flipped=[];pile=#0;played=#3;hand[0]=#10;hand[1]=[10♠,10♦,2♠,2♥,3♠,4♦,8♥,9♠,9♦,A♣,A♦,K♠,Q♦];"
    "hand[2]=#13;hand[3]=#13|state:challenged=False;challenger=None;claim_count=3;claim_rank=A;claimant=0;"
    "responder=1;window_open=True;won={0:False,1:False,2:False,3:False}|obs:('move', 'deck', 13, 'hand[0]', 13);"
    "('move', 'deck', 13, 'hand[1]', ('10♠', '10♦', '2♠', '2♥', '3♠', '4♦', '8♥', '9♠', '9♦', 'A♣', 'A♦', 'K♠', 'Q♦'));"
    "('move', 'deck', 13, 'hand[2]', 13);('move', 'deck', 13, 'hand[3]', 13);('announce', 0, 'play_cards');"
    "('announce', 0, 3);('move', 'hand[0]', 3, 'played', 3)"
)
#: A real abstains window: the observer holds two 2s, the flip record has put
#: a third in seat 0's hand, and seat 1 claims one 2 from a hand of thirteen.
ABSTAINS = (
    "P2|deck=#0;flipped=[];pile=#0;played=#1;hand[0]=#13;hand[1]=#12;hand[2]=[10♠,2♠,2♣,3♣,3♥,4♥,6♦,8♥,9♥,A♦,J♠,J♥,K♣];"
    "hand[3]=#13|state:challenged=False;challenger=None;claim_count=1;claim_rank=2;claimant=1;responder=2;"
    "window_open=True;won={0:False,1:False,2:False,3:False}|obs:('move', 'deck', 13, 'hand[0]', 13);"
    "('move', 'deck', 13, 'hand[1]', 13);('move', 'deck', 13, 'hand[2]', ('10♠', '2♠', '2♣', '3♣', '3♥', '4♥', '6♦', '8♥', '9♥', 'A♦', 'J♠', 'J♥', 'K♣'));"
    "('move', 'deck', 13, 'hand[3]', 13);('announce', 0, 'play_cards');('announce', 0, 2);('move', 'hand[0]', 2, 'played', 2);"
    "('announce', 1, 'call_cheat');('move', 'played', 2, 'flipped', ('2♥', 'A♠'));('move', 'flipped', ('2♥', 'A♠'), 'hand[0]', 2);"
    "('announce', 1, 'play_cards');('announce', 1, 1);('move', 'hand[1]', 1, 'played', 1)"
)


def test_the_fires_window_is_certain() -> None:
    assert reference(FIRES, bluff_prob=0.4) == 1.0
    assert reference(FIRES, bluff_prob=0.0) == 1.0


def test_the_abstains_window_is_the_hand_computed_value() -> None:
    """Pool: 52 minus the observer's 13 minus the two cards the flip placed in
    seat 0 = 37; copies of the rank left: 4 - 2 own - 1 elsewhere = 1; the
    claimant held 13 before playing one. A claim of one is forced (t = 0) or
    honest with probability 1 - b (t = 1):
    P(lie) = P(t=0) / (P(t=0) + (1-b) P(t=1)) with P(t=0) = 24/37, P(t=1) = 13/37."""
    b = 0.4
    p0, p1 = 24 / 37, 13 / 37
    assert math.isclose(reference(ABSTAINS, bluff_prob=b), p0 / (p0 + (1 - b) * p1))
    # With no bluffing a one-card claim is honest whenever it can be, so the
    # same window is less likely a lie; with certain bluffing, t = 1 never
    # claims one, so the claim is a lie for sure.
    assert reference(ABSTAINS, bluff_prob=0.0) < reference(ABSTAINS, bluff_prob=b)
    assert reference(ABSTAINS, bluff_prob=1.0) == 1.0


def test_the_flip_record_narrows_the_pool() -> None:
    """Without the flip that placed 2♥ elsewhere, the claimant could hold
    two of the rank, and the reference moves."""
    stripped = ABSTAINS.replace(
        "('announce', 1, 'call_cheat');('move', 'played', 2, 'flipped', ('2♥', 'A♠'));"
        "('move', 'flipped', ('2♥', 'A♠'), 'hand[0]', 2);",
        "('announce', 1, 'allow');('announce', 2, 'allow');('announce', 3, 'allow');"
        "('move', 'played', 2, 'pile', 2);",
    ).replace("hand[0]=#13", "hand[0]=#11").replace("pile=#0", "pile=#2")
    assert reference(stripped, bluff_prob=0.4) != reference(ABSTAINS, bluff_prob=0.4)


def test_a_window_without_a_standing_claim_is_refused() -> None:
    no_claim = _info(_hand(1, 13))
    with pytest.raises(ValueError, match="claim"):
        reference(
            "P0|deck=#0;flipped=[];pile=#0;played=#0;hand[0]=[A♠];hand[1]=#13;hand[2]=#13;hand[3]=#13"
            "|state:challenged=False;challenger=None;claim_count=0;claim_rank=A;claimant=None;"
            "responder=None;window_open=False;won={0:False,1:False,2:False,3:False}|obs:",
            bluff_prob=0.4,
        )
    assert no_claim.claimant is None


def test_the_record_carries_what_the_scorer_reads() -> None:
    window = {
        "matchup": "m", "seed": 2, "step": 8, "observer": 2, "observer_agent": "llm_cheap",
        "claimant": 1, "claimant_agent": "rule", "claim_rank": "2", "claim_count": 1,
        "action": "allow", "lie": True, "r1_widened": False, "r0": 0.4, "infostate": ABSTAINS,
    }
    record = record_for(window)
    assert REQUIRED_WINDOW_FIELDS <= set(window)
    assert record["converged"] is True and record["dropped"] is False
    assert "infostate" not in record
    assert math.isclose(record["p_lie"], reference(ABSTAINS, bluff_prob=0.4))
    for key in ("matchup", "seed", "step", "observer_agent", "action", "lie", "r1_widened"):
        assert record[key] == window[key]


def test_a_window_with_no_declared_policy_is_refused() -> None:
    window = {"r0": None, "infostate": ABSTAINS, "claimant_agent": "llm_cheap"}
    with pytest.raises(ValueError, match="declared"):
        record_for(window)


def test_the_module_reaches_no_engine_and_no_transcript() -> None:
    """The reference is a function of the information-state string and the
    declared policy. Pinned the way `verify_cheat_gap` pins its independence:
    the module's imports name no engine, no sampler and no replay."""
    source = (Path(__file__).resolve().parents[1] / "gap_policy.py").read_text()
    names: set[str] = set()
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            names.add(f"{'.' * node.level}{node.module or ''}")
    forbidden = ("cardlang", "pyspiel", ".gap_sampler", ".gap_replay", ".referee", ".metrics", ".run_eval")
    assert not [n for n in names if any(n == f or n.startswith(f + ".") for f in forbidden)], names


ARCHIVE = Path(__file__).resolve().parents[1] / "results_cheat_gap" / "transcripts" / "rule_table.jsonl.gz"


def test_every_window_of_an_archived_game_is_a_probability_and_fires_is_certain() -> None:
    pytest.importorskip("pyspiel", reason="the OpenSpiel adapter needs the `openspiel` extra")
    import gzip

    from ..gap_windows import _windows_of

    with gzip.open(ARCHIVE, "rt") as f:
        record = json.loads(f.readline())
    windows = [asdict(w) for w in _windows_of(record, ARCHIVE.parent, "rule_table", 0.4)]
    assert len(windows) > 50
    fires = 0
    for w in windows:
        p = reference(w["infostate"], bluff_prob=0.4)
        assert 0.0 <= p <= 1.0
        if w["r1_widened"]:
            fires += 1
            assert p == 1.0
    assert fires > 0, "the game offered no provably-false claim to pin"
    rng = random.Random(0)
    assert rng  # the pin is deterministic; nothing here is sampled
