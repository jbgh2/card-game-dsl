"""The memoryless policy-aware reference at a Cheat challenge window:
P(the standing claim is a lie | the observer's information state, the
claimant's declared bluff_prob), exact and engine-free.

    python -m experiments.llm_eval.gap_policy \\
        --windows windows.jsonl --out policy.jsonl \\
        --observer-agent llm_cheap --max-depth 250

The literal posterior (`gap_sampler`) asks how often the claim is false among
the worlds the observer cannot rule out, with every hidden card choice
uniform. This reference asks the question a reader who knows the opponents'
dispositions asks instead: given what I hold, what the flip record has placed
in other hands, how many cards the claimant held, and how many it just
claimed, how likely is it that a `RuleAgent` with this `bluff_prob` was
lying? The claimant's hand is a uniform draw from the cards the observer
cannot place; each possible holding t of the claimed rank is weighted by the
likelihood the agent's count policy announces the observed count from t; the
claim is a lie exactly where t is short of it.

Memoryless, by definition: nothing the line's earlier public actions say
about the claimant's hand — its own past claims, what it picked up — is
conditioned on. `belief-calibration-spec.md` §3 names this tier beside R2,
the full policy-aware posterior, which conditions on the whole line and is
not built (issue #707). A card the observer knows to be in the pile is
likewise left in the pool.

The count policy is never restated here. `count_likelihood` drives
`RuleAgent._count` itself with a fixed coin at both of its values, so the
distribution this module weights by is the one the agent produces, and an
edit to the agent's policy moves the reference with it
(`tests/test_gap_policy.py` pins the two by simulation).

Contract
--------
Assumes: an information-state string as `cardlang.openspiel.infostate`
renders it for a four-player `standard52` Cheat line, at a window where a
play stands (`claimant` set, `claim_count` positive); a `bluff_prob` for the
claimant that is the one its `RuleAgent` was built with.
Establishes: `reference`, a probability in [0, 1] that is exactly 1.0
wherever `infostate.provably_false` fires; `record_for`, the posterior-format
record `verify_cheat_gap` scores, carrying `converged: True` and no sampler
diagnostics because nothing here is sampled.
Illegal after: reading any fact about the window from a transcript's action
ids, a `pyspiel.State` or a `RuntimeState`, or handing this reference a
claimant whose policy is not declared.
"""

from __future__ import annotations

import argparse
import json
import math
import random
import sys
from pathlib import Path
from typing import Any

from . import infostate as istate
from .agents import DecisionView, RuleAgent

#: The deck the reference integrates over: four suits of every rank.
DECK_SIZE = len(istate.RANKS) * istate.COPIES_PER_RANK

#: The window fields a record carries through to the scorer, besides the
#: reference itself.
REQUIRED_WINDOW_FIELDS: frozenset[str] = frozenset(
    {
        "matchup", "seed", "step", "observer", "observer_agent", "claimant",
        "claimant_agent", "claim_rank", "claim_count", "action", "lie",
        "r1_widened", "r0", "infostate",
    }
)


class _Coin(random.Random):
    """A generator whose `random()` is one fixed value: the agent's coin held
    at heads or tails, so each branch of its policy can be read off."""

    def __init__(self, value: float) -> None:
        super().__init__(0)
        self._value = value

    def random(self) -> float:
        return self._value


def count_likelihood(holding: int, hand_size: int, bluff_prob: float) -> dict[int, float]:
    """P(announced count | the claimant holds `holding` of the rank in a hand
    of `hand_size`), from the agent's own count method.

    The agent's count decision draws one coin against `bluff_prob` and takes
    one of two branches, so driving the method at a coin of 0 (below any
    positive `bluff_prob`) and of 1 (above any `bluff_prob` short of one)
    exposes both; the law is `bluff_prob` on the first and its complement on
    the second. Where the two branches announce the same count, that count is
    certain. A `bluff_prob` of exactly 0 or 1 makes one branch unreachable and
    the law says so by weight, never by omission.
    """
    if not 0 <= holding <= hand_size:
        raise ValueError(f"a hand of {hand_size} cannot hold {holding} of one rank")
    if not 0.0 <= bluff_prob <= 1.0:
        raise ValueError(f"bluff_prob {bluff_prob!r} is not a probability")
    view = DecisionView(
        player=0,
        infostate="",
        legal_actions=list(range(hand_size)),
        legal_strings=[str(n) for n in range(1, hand_size + 1)],
    )
    info = _holding_view(holding, hand_size)
    law: dict[int, float] = {}
    for coin, weight in ((0.0, bluff_prob), (1.0, 1.0 - bluff_prob)):
        agent = RuleAgent(seed=0, bluff_prob=bluff_prob)
        agent._rng = _Coin(coin)
        count = view.legal_actions.index(agent._count(view, info)) + 1
        law[count] = law.get(count, 0.0) + weight
    return {count: p for count, p in law.items() if p > 0.0}


#: One card per rank other than the claimed one, for a hand the count method
#: reads only the claimed rank's count of.
_RANK = istate.RANKS[0]
_OTHERS = [f"{rank}{suit}" for rank in istate.RANKS[1:] for suit in "♠♥♦♣"]


def _holding_view(holding: int, hand_size: int) -> istate.Info:
    hand = [f"{_RANK}{suit}" for suit in "♠♥♦♣"[:holding]] + _OTHERS[: hand_size - holding]
    if len(hand) != hand_size:
        raise ValueError(f"cannot build a hand of {hand_size} holding {holding}")
    cards = ",".join(hand)
    return istate.parse(
        f"P0|deck=#0;flipped=[];pile=#0;played=#0;hand[0]=[{cards}];hand[1]=#0;hand[2]=#0;"
        f"hand[3]=#0|state:challenged=False;challenger=None;claim_count=0;claim_rank={_RANK};"
        f"claimant=None;responder=None;window_open=False;won={{0:False}}|obs:"
    )


def holdings(pool: int, copies: int, hand_size: int) -> dict[int, float]:
    """P(a uniform `hand_size`-subset of a `pool` holding `copies` of the rank
    contains t of them), for every reachable t: the hypergeometric law."""
    if not 0 <= copies <= pool or not 0 <= hand_size <= pool:
        raise ValueError(f"pool={pool} copies={copies} hand_size={hand_size} is not a draw")
    total = math.comb(pool, hand_size)
    law = {}
    for t in range(max(0, hand_size - (pool - copies)), min(copies, hand_size) + 1):
        law[t] = math.comb(copies, t) * math.comb(pool - copies, hand_size - t) / total
    return law


def reference(infostate: str, *, bluff_prob: float) -> float:
    """P(the standing claim is a lie), memoryless and policy-aware."""
    info = istate.parse(infostate)
    claimant = info.claimant
    count = info.claim_count
    if claimant is None or count < 1:
        raise ValueError("no play stands at this window: nothing to reference a claim against")
    rank = info.claim_rank
    elsewhere = istate.cards_known_elsewhere(info, claimant)
    own = set(info.hand)
    placed = own | set(elsewhere)
    pool = DECK_SIZE - len(placed)
    copies = istate.COPIES_PER_RANK - sum(1 for c in placed if istate.rank_of(c) == rank)
    hand_size = info.hand_size(claimant) + count
    if hand_size > pool:
        raise ValueError(
            f"the claimant held {hand_size} cards but only {pool} are unplaced — "
            f"the information state is not one this reference models"
        )
    numerator = 0.0
    denominator = 0.0
    for holding, p_holding in holdings(pool, copies, hand_size).items():
        likelihood = count_likelihood(holding, hand_size, bluff_prob).get(count, 0.0)
        weight = p_holding * likelihood
        denominator += weight
        if holding < count:
            numerator += weight
    if denominator == 0.0:
        # No holding the pool allows announces this count under the policy:
        # the claim is a lie in every world the reference admits, which is
        # exactly what `provably_false` says too.
        return 1.0
    return numerator / denominator


def record_for(window: dict[str, Any]) -> dict[str, Any]:
    """The posterior-format record for one window, scored like a sampled one."""
    bluff_prob = window.get("r0")
    if bluff_prob is None:
        raise ValueError(
            f"window {window.get('matchup')!r} seed={window.get('seed')} "
            f"step={window.get('step')}: the claimant ({window.get('claimant_agent')!r}) "
            f"has no declared policy, so no policy-aware reference exists for it"
        )
    record = {k: v for k, v in window.items() if k != "infostate"}
    record.update(
        p_lie=reference(window["infostate"], bluff_prob=float(bluff_prob)),
        converged=True,
        dropped=False,
        reference="policy_memoryless",
    )
    return record


def run(
    windows: list[dict[str, Any]],
    *,
    observer_agent: str | None,
    max_depth: int | None,
) -> tuple[list[dict[str, Any]], list[str]]:
    """Records for every window of `observer_agent` inside `max_depth` whose
    claimant has a declared policy; the log names the windows left out."""
    out: list[dict[str, Any]] = []
    log: list[str] = []
    skipped = 0
    for w in windows:
        if observer_agent is not None and w["observer_agent"] != observer_agent:
            continue
        if max_depth is not None and int(w["step"]) > max_depth:
            continue
        if w.get("r0") is None:
            skipped += 1
            continue
        out.append(record_for(w))
    log.append(
        f"policy reference: {len(out)} window(s) referenced, {skipped} skipped for a "
        f"claimant with no declared policy (observer_agent={observer_agent}, "
        f"max_depth={max_depth})"
    )
    return out, log


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__ and __doc__.splitlines()[0])
    ap.add_argument("--windows", required=True, help="gap_windows' JSONL output")
    ap.add_argument("--out", required=True, help="where to write the records (JSONL)")
    ap.add_argument("--observer-agent", default=None, help="only this seat class's windows")
    ap.add_argument("--max-depth", type=int, default=None, help="only windows at or before this decision")
    args = ap.parse_args(argv)
    windows = [json.loads(line) for line in Path(args.windows).read_text().splitlines() if line.strip()]
    records, log = run(windows, observer_agent=args.observer_agent, max_depth=args.max_depth)
    with Path(args.out).open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")
    for line in log:
        print(line)
    print(f"wrote {len(records)} record(s) to {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
