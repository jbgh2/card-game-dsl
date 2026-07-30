"""Salvo round-1 design triage: is this double solitaire?

Drives the game via `cardlang.openspiel.replay.run` directly — no pyspiel
registration needed for playout-level questions. Three policies:

- random            uniform over legal actions
- blind (greedy)    maximizes own immediate committed value; NEVER sees any
                    opponent zone; never holds voluntarily. This is the
                    commit-max hypothesis made a player.
- sighted           same value core, but reads the public opponent state
                    (armies = public; staged = COUNT ONLY, exactly the
                    HiddenPile projection a real player gets) and weights
                    commits by the per-location race: discounts overkill at
                    locations already safely won, discounts lost causes,
                    boosts close races, and holds when nothing worthwhile
                    fits. This is the smallest opponent-aware player.

The design verdicts this script feeds (DESIGN.md, "Evaluation plan"):

  Q1 commit-max dominance  -> does sighted's holding/redirecting beat
                              blind's always-commit-2?  (arena win rates)
  Q2 double solitaire      -> how big is the sighted-vs-blind gap, and how
                              often does opponent state actually change the
                              chosen action?  (decision-divergence rate)
  Q3 location liveness     -> unclaimed-tie rate, margin distributions.

Projection discipline: `Pause.rs` is the TRUE world. Policies here read only
what their information set allows — blind: own hand + locations + own
staged/armies; sighted: additionally opponent armies (public) and opponent
staged COUNTS (never identities), plus the running scalar state. Nothing
reads the deck, the opponent's hand, or opponent staged identities.

The value function mirrors salvo.cardlang's `dist`/`loc_value` exactly; if
the game file's numbers change, change VALUE_MIRROR below in the same edit.

Run:  PYTHONHASHSEED=0 python experiments/salvo/triage.py [--seeds N]
"""

from __future__ import annotations

import argparse
import json
import random
import statistics
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from cardlang.openspiel import replay
from cardlang.runtime.values import Card

HERE = Path(__file__).resolve().parent
GAME_PATH = str(HERE / "salvo.cardlang")  # rebound in main() by --curve

LOCS = ("a", "b", "c")

# One switch selects game file + value mirror + policy tuning together, so
# they cannot drift apart; the per-game mirror pin then PROVES the pairing
# (a wrong base fails the totals assertion on game one).
CURVES: dict[str, dict[str, Any]] = {
    # the adopted base game: capacity 4 + recon draw, all-positive curve.
    # Earlier configs (round-1 no-cap "full", "cap", "recon"-as-variant) are
    # retired — their game files evolved into this base; the committed
    # results_triage*.json files pin what each historical run measured.
    # knobs = tune_sighted.py's stage-B winner (REPORT.md s9): hold at the
    # interior optimum 11, no urgency boost, opponent staged cards assumed
    # strong; the wide race margins survived the sweep (tight ones collapse).
    "base": dict(
        game="salvo.cardlang",
        base=13,
        results="results_triage_base.json",
        won_margin=25.0, lost_margin=25.0, overkill_w=0.15, lostcause_w=0.2,
        urgency_w=1.0, opp_staged_est=11.0, hold_below=11.0,
    ),
    # zero-centered curve (refuted, kept as the historical variant): 6-dist
    # (+3), -6..+9 — knobs rescaled to the smaller value range
    "zc": dict(
        game="variants/salvo-zc.cardlang",
        base=6,
        results="results_triage_zc.json",
        won_margin=15.0, lost_margin=15.0, overkill_w=0.15, lostcause_w=0.2,
        urgency_w=1.3, opp_staged_est=4.0, hold_below=0.5,
    ),
}
TUN: dict[str, Any] = CURVES["base"]  # rebound in main()

# --- the value mirror (the game file's `dist` / `loc_value`) — VALUE_MIRROR


def rank_index_map(game_ast: Any) -> dict[str, int]:
    return {r: i for i, r in enumerate(game_ast.ranking)}


def make_loc_value(ridx: dict[str, int], base: int) -> Callable[[Card, Card], int]:
    def loc_value(c: Card, loc: Card) -> int:
        d = abs(ridx[c.rank] - ridx[loc.rank])
        return (base - d) + (3 if c.suit == loc.suit else 0)

    return loc_value


# --- world views under manual projection discipline ------------------------


def zone_cards(rs: Any, name: str, player: int | None = None) -> list[Card]:
    if player is None:
        return list(rs.zones.singles[name].cards)
    return list(rs.zones.families[name][player].cards)


def location_cards(rs: Any) -> dict[str, Card]:
    out: dict[str, Card] = {}
    for l in LOCS:
        cards = zone_cards(rs, f"location_{l}")
        assert len(cards) == 1, f"location_{l} holds {len(cards)} cards"
        out[l] = cards[0]
    return out


@dataclass
class Ctx:
    """Per-playout driver context: which location the pending card pick is
    for (set when a commit_<loc> move type is chosen), plus counters."""

    pending_loc: str | None = None
    commits: dict[int, int] = field(default_factory=lambda: {0: 0, 1: 0})
    holds: dict[int, int] = field(default_factory=lambda: {0: 0, 1: 0})
    decisions: dict[int, int] = field(default_factory=lambda: {0: 0, 1: 0})
    divergences: int = 0  # sighted chose differently than blind would have
    compared: int = 0


# --- policies ---------------------------------------------------------------
# A policy is called with (kind, pause, space, ctx, loc_value, rng) where kind
# is "offer" (move-type ids) or "pick" (card ids for the pending location).
# It returns a legal action id.

Policy = Callable[..., int]


def offer_labels(space: Any, legal: list[int]) -> dict[int, str]:
    return {aid: space._names[aid - space._name_base] for aid in legal}


def hand_of(pause: Any) -> list[Card]:
    return zone_cards(pause.rs, "hand", pause.player)


def sorted_cards(cards: list[Card], ridx: dict[str, int]) -> list[Card]:
    return sorted(cards, key=lambda c: (ridx[c.rank], c.suit))


def random_policy(kind: str, pause: Any, space: Any, ctx: Ctx, lv: Any, ridx: Any, rng: random.Random, tun: dict[str, Any] | None = None) -> int:
    return int(rng.choice(sorted(pause.legal)))


def _best_pairs(hand: list[Card], locs: dict[str, Card], lv: Any, ridx: dict[str, int]) -> list[tuple[int, str, Card]]:
    """All (value, loc, card) pairs, best first, deterministic order."""
    pairs = [
        (lv(c, locs[l]), l, c)
        for c in hand
        for l in LOCS
    ]
    pairs.sort(key=lambda t: (-t[0], t[1], ridx[t[2].rank], t[2].suit))
    return pairs


def blind_policy(kind: str, pause: Any, space: Any, ctx: Ctx, lv: Any, ridx: dict[str, int], rng: random.Random, allow_hold: bool = False, tun: dict[str, Any] | None = None) -> int:
    """Commit-max greedy: no opponent state, never holds voluntarily.
    With allow_hold=True (the `blind_hold` policy) it holds when its best
    available commit falls below the curve's hold threshold — restraint
    driven by OWN-hand value only, still zero opponent state."""
    t = tun or TUN
    hand = hand_of(pause)
    locs = location_cards(pause.rs)
    labels = offer_labels(space, sorted(pause.legal)) if kind == "offer" else {}
    if kind == "offer":
        commit_ids = {lab.removeprefix("commit_"): aid for aid, lab in labels.items() if lab.startswith("commit_")}
        hold_id = next((aid for aid, lab in labels.items() if lab == "hold"), None)
        if not commit_ids:  # hand empty or every location at capacity
            assert hold_id is not None
            return hold_id
        # only locations actually offered (capacity guards filter the rest)
        pairs = [t for t in _best_pairs(hand, locs, lv, ridx) if t[1] in commit_ids]
        best = pairs[0]
        if (
            allow_hold
            and hold_id is not None
            and best[0] < t["hold_below"]
            and _round_no(pause) < HOLD_LAST_ROUND
        ):
            return hold_id
        return commit_ids[best[1]]
    # card pick for the pending location
    assert ctx.pending_loc is not None
    target = locs[ctx.pending_loc]
    ranked = sorted(hand, key=lambda c: (-lv(c, target), ridx[c.rank], c.suit))
    for c in ranked:
        aid = space.encode(c)
        if aid in pause.legal:
            return int(aid)
    raise AssertionError("no hand card encodable among legal picks")


# Curve-dependent knobs live in CURVES/TUN; this one is round-structural:
HOLD_LAST_ROUND = 5  # rounds 0-4 may hold; round 5 (last) always commits


def _status(pause: Any, me: int, l: str, lv: Any, locs: dict[str, Card], t: dict[str, Any]) -> float:
    """My committed value minus the opponent's VISIBLE committed value at l.
    Opponent staged cards enter as count * opp_staged_est (projection: the
    count is public, the identities are not)."""
    opp = 1 - me
    target = locs[l]
    mine = sum(lv(c, target) for c in zone_cards(pause.rs, f"army_{l}", me))
    mine += sum(lv(c, target) for c in zone_cards(pause.rs, f"staged_{l}", me))
    theirs = sum(lv(c, target) for c in zone_cards(pause.rs, f"army_{l}", opp))
    theirs += t["opp_staged_est"] * len(zone_cards(pause.rs, f"staged_{l}", opp))
    return float(mine - theirs)


def _round_no(pause: Any) -> int:
    for frame in pause.rs.frames:
        if "round_no" in frame:
            v = frame["round_no"]
            return int(v if not isinstance(v, list) else v[0])
    return 0


def sighted_policy(kind: str, pause: Any, space: Any, ctx: Ctx, lv: Any, ridx: dict[str, int], rng: random.Random, allow_hold: bool = True, tun: dict[str, Any] | None = None) -> int:
    """Opponent-aware: weights the race per location, holds on waste."""
    t = tun or TUN
    me = pause.player
    hand = hand_of(pause)
    locs = location_cards(pause.rs)
    weights: dict[str, float] = {}
    for l in LOCS:
        s = _status(pause, me, l, lv, locs, t)
        if s >= t["won_margin"]:
            weights[l] = t["overkill_w"]
        elif s <= -t["lost_margin"]:
            weights[l] = t["lostcause_w"]
        elif s < 0:
            weights[l] = t["urgency_w"]
        else:
            weights[l] = 1.0
    if kind == "offer":
        labels = offer_labels(space, sorted(pause.legal))
        commit_ids = {lab.removeprefix("commit_"): aid for aid, lab in labels.items() if lab.startswith("commit_")}
        hold_id = next((aid for aid, lab in labels.items() if lab == "hold"), None)
        if not commit_ids:
            assert hold_id is not None
            return hold_id
        scored = [
            (lv(c, locs[l]) * weights[l], l, c)
            for c in hand
            for l in LOCS
            if l in commit_ids  # capacity guards filter un-offered locations
        ]
        if not scored:
            assert hold_id is not None
            return hold_id
        scored.sort(key=lambda t: (-t[0], t[1], ridx[t[2].rank], t[2].suit))
        best_v, best_l, _ = scored[0]
        if allow_hold and hold_id is not None and best_v < t["hold_below"] and _round_no(pause) < HOLD_LAST_ROUND:
            return hold_id
        return commit_ids[best_l]
    assert ctx.pending_loc is not None
    target = locs[ctx.pending_loc]
    ranked = sorted(hand, key=lambda c: (-lv(c, target), ridx[c.rank], c.suit))
    for c in ranked:
        aid = space.encode(c)
        if aid in pause.legal:
            return int(aid)
    raise AssertionError("no hand card encodable among legal picks")


def sighted_nohold_policy(kind: str, pause: Any, space: Any, ctx: Ctx, lv: Any, ridx: dict[str, int], rng: random.Random, tun: dict[str, Any] | None = None) -> int:
    """Opponent-aware redirection WITHOUT holding: isolates how much of
    sighted's edge is reallocation vs commit restraint."""
    return sighted_policy(kind, pause, space, ctx, lv, ridx, rng, allow_hold=False, tun=tun)


def blind_hold_policy(kind: str, pause: Any, space: Any, ctx: Ctx, lv: Any, ridx: dict[str, int], rng: random.Random, tun: dict[str, Any] | None = None) -> int:
    """Own-value restraint with zero opponent state: holds when its best
    commit is below the curve's threshold. Separates 'the curve makes
    counting matter' from 'opponent info makes counting matter'."""
    return blind_policy(kind, pause, space, ctx, lv, ridx, rng, allow_hold=True, tun=tun)


POLICIES: dict[str, Policy] = {
    "random": random_policy,
    "blind": blind_policy,
    "blind_hold": blind_hold_policy,
    "sighted": sighted_policy,
    "sighted_nohold": sighted_nohold_policy,
}


# --- the driver -------------------------------------------------------------


@dataclass
class GameStats:
    returns: list[float]
    locs_won: list[int]
    totals: list[int]
    margins: list[int]  # per-location |pts0 - pts1|
    unclaimed: int
    commits: dict[int, int]
    holds: dict[int, int]
    decisions: int
    divergences: int
    compared: int


def playout(
    space: Any,
    seats: dict[int, str],
    seed: int,
    lv: Any,
    ridx: dict[str, int],
    measure_divergence: bool = False,
    seat_tuns: dict[str, dict[str, Any]] | None = None,
) -> GameStats:
    rng = random.Random(seed * 7919 + 13)
    history: list[int] = []
    ctx = Ctx()
    while True:
        r = replay.run(GAME_PATH, seed, tuple(history))
        if isinstance(r, replay.Terminal):
            break
        assert isinstance(r, replay.Pause)
        legal_set = set(r.legal)
        # classify the decision: move-type offer vs card pick
        name_base = space._name_base
        is_offer = all(aid >= name_base for aid in r.legal)
        kind = "offer" if is_offer else "pick"
        seat_name = seats[r.player]
        pol = POLICIES[seat_name]
        aid = pol(kind, r, space, ctx, lv, ridx, rng, tun=(seat_tuns or {}).get(seat_name))
        assert aid in legal_set, f"policy returned illegal action {aid}"
        if measure_divergence and seat_name == "sighted":
            b = blind_policy(kind, r, space, ctx, lv, ridx, rng)
            ctx.compared += 1
            if b != aid:
                ctx.divergences += 1
        if kind == "offer":
            lab = space._names[aid - name_base]
            if lab.startswith("commit_"):
                ctx.pending_loc = lab.removeprefix("commit_")
                ctx.commits[r.player] += 1
            elif lab == "hold":
                ctx.holds[r.player] += 1
        ctx.decisions[r.player] += 1
        history.append(aid)

    # settle stats from the final world: re-run to the last pause is gone, so
    # recompute from the terminal returns encoding: final = locs*1000 + total.
    ret = r.returns
    # final = locs*1000 + total, with |total| bounded far inside 500 on both
    # curves — round-decode stays exact even for negative zc totals (floor
    # division would misdecode 2000-50 as 1 location).
    locs_won = [round(x / 1000) for x in ret]
    totals = [int(x) - 1000 * lw for x, lw in zip(ret, locs_won)]
    # margins need the per-location points; recompute by replaying the final
    # world once with a fresh run that stops at terminal — the terminal world
    # is not exposed, so derive margins from a full replay via the runtime
    # state at the LAST pause plus the final committed cards. Cheaper and
    # exact: run the replay with the full history and read zones from the
    # last Pause before terminal — instead we recompute from scratch below.
    margins, unclaimed, pts = _final_margins(space, seed, tuple(history), lv)
    # Mirror pin: the Python value function must reproduce the DSL's settle
    # math exactly — locations won and grand totals recomputed from the last
    # pause's world must equal the terminal returns' encoding.
    for p in (0, 1):
        won = sum(1 for l in range(3) if pts[l][p] > pts[l][1 - p])
        assert won == locs_won[p], f"mirror drift: locs_won {won} != {locs_won[p]}"
        assert sum(pts[l][p] for l in range(3)) == totals[p], (
            f"mirror drift: totals {sum(pts[l][p] for l in range(3))} != {totals[p]}"
        )
    return GameStats(
        returns=ret,
        locs_won=locs_won,
        totals=totals,
        margins=margins,
        unclaimed=unclaimed,
        commits=dict(ctx.commits),
        holds=dict(ctx.holds),
        decisions=ctx.decisions[0] + ctx.decisions[1],
        divergences=ctx.divergences,
        compared=ctx.compared,
    )


def _final_margins(
    space: Any, seed: int, history: tuple[int, ...], lv: Any
) -> tuple[list[int], int, list[list[int]]]:
    """Per-location final margins. The terminal result hides the world, so
    walk to the last pause (full history minus one action), apply the final
    action's effect implicitly by scoring armies + staged (everything staged
    at that point flips before settle; hands score nothing)."""
    r = replay.run(GAME_PATH, seed, history[:-1])
    assert isinstance(r, replay.Pause)
    locs = location_cards(r.rs)
    margins: list[int] = []
    unclaimed = 0
    # NOTE: the final action is always the last commit-window decision of
    # round 6; every card that will score is already in an army or staged
    # zone EXCEPT a final card pick still pending. Scoring armies+staged at
    # the last pause is exact unless the very last action was a card pick
    # into a staged zone — cover that by also counting the picked card via
    # the action id when it is a card id.
    pend: Card | None = None
    if history and history[-1] < space._name_base:
        pend = space.decode(history[-1])  # global 52-block when card_block is None
    pend_loc: str | None = None
    if pend is not None:
        # the pending pick's location is the last commit_<l> in the offer log;
        # find it by looking at which staged zone the previous name action named
        for aid in reversed(history[:-1]):
            if aid >= space._name_base:
                lab = space._names[aid - space._name_base]
                if lab.startswith("commit_"):
                    pend_loc = lab.removeprefix("commit_")
                break
    all_pts: list[list[int]] = []
    for l in LOCS:
        target = locs[l]
        pts = []
        for p in (0, 1):
            v = sum(lv(c, target) for c in zone_cards(r.rs, f"army_{l}", p))
            v += sum(lv(c, target) for c in zone_cards(r.rs, f"staged_{l}", p))
            if pend is not None and pend_loc == l and p == r.player:
                v += lv(pend, target)
            pts.append(v)
        all_pts.append(pts)
        margins.append(abs(pts[0] - pts[1]))
        if pts[0] == pts[1]:
            unclaimed += 1
    return margins, unclaimed, all_pts


# --- the arena --------------------------------------------------------------


def arena(
    space: Any, a: str, b: str, n_seeds: int, lv: Any, ridx: dict[str, int],
    tuns: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """n_seeds games with a in seat 0, and n_seeds seat-swapped. `tuns`
    optionally assigns per-POLICY-NAME knob dicts (tuning sweeps)."""
    wins = {a: 0, b: 0, "draw": 0}
    locs_a: list[int] = []
    margins: list[int] = []
    unclaimed = 0
    commits = {a: [], b: []}  # type: dict[str, list[int]]
    holds = {a: [], b: []}  # type: dict[str, list[int]]
    div, comp = 0, 0
    for swap in (False, True):
        seats = {0: b, 1: a} if swap else {0: a, 1: b}
        for seed in range(n_seeds):
            gs = playout(space, seats, seed, lv, ridx, measure_divergence=("sighted" in (a, b)), seat_tuns=tuns)
            ia = 1 if swap else 0
            ra, rb = gs.returns[ia], gs.returns[1 - ia]
            if ra > rb:
                wins[a] += 1
            elif rb > ra:
                wins[b] += 1
            else:
                wins["draw"] += 1
            locs_a.append(gs.locs_won[ia])
            margins.extend(gs.margins)
            unclaimed += gs.unclaimed
            commits[a].append(gs.commits[ia])
            commits[b].append(gs.commits[1 - ia])
            holds[a].append(gs.holds[ia])
            holds[b].append(gs.holds[1 - ia])
            div += gs.divergences
            comp += gs.compared
    games = 2 * n_seeds
    out = {
        "pairing": f"{a} vs {b}",
        "games": games,
        "win_rate": {k: round(v / games, 4) for k, v in wins.items()},
        "mean_locs_won": {a: round(statistics.mean(locs_a), 3)},
        "margin_mean": round(statistics.mean(margins), 2),
        "margin_median": statistics.median(margins),
        "unclaimed_rate_per_loc": round(unclaimed / (games * 3), 4),
        "mean_commits": {k: round(statistics.mean(v), 2) for k, v in commits.items()},
        "mean_holds": {k: round(statistics.mean(v), 2) for k, v in holds.items()},
    }
    if comp:
        out["sighted_divergence_rate"] = round(div / comp, 4)
    return out


def main() -> None:
    global GAME_PATH, TUN
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", type=int, default=150, help="seeds per seating per pairing")
    ap.add_argument("--curve", choices=sorted(CURVES), default="base", help="config: value curve / game variant")
    ap.add_argument("--hold-below", type=float, default=None, help="override the hold threshold (sensitivity sweeps); suffixes the results filename")
    ap.add_argument("--probes-only", action="store_true", help="run only the four commit-count probe pairings (for sweeps)")
    args = ap.parse_args()

    TUN = dict(CURVES[args.curve])
    if args.hold_below is not None:
        TUN["hold_below"] = args.hold_below
        stem, dot, ext = TUN["results"].rpartition(".")
        TUN["results"] = f"{stem}_hb{args.hold_below:g}.{ext}"
    elif args.probes_only:
        # never clobber a full-pairing results file with a probe subset
        stem, dot, ext = TUN["results"].rpartition(".")
        TUN["results"] = f"{stem}_probes.{ext}"
    GAME_PATH = str(HERE / TUN["game"])
    game_ast, space = replay.load(GAME_PATH)
    ridx = rank_index_map(game_ast)
    lv = make_loc_value(ridx, TUN["base"])

    pairings = [
        ("random", "random"),
        ("blind", "random"),
        ("sighted", "random"),
        ("sighted", "blind"),
        ("sighted_nohold", "blind"),
        ("sighted", "sighted_nohold"),
        ("blind", "blind"),
        ("sighted", "sighted"),
    ]
    # the commit-count probes: does restraint pay, and does own-value
    # restraint alone capture it?
    pairings += [("blind_hold", "blind"), ("sighted", "blind_hold")]
    if args.probes_only:
        pairings = [
            ("blind_hold", "blind"),
            ("sighted", "sighted_nohold"),
            ("sighted", "blind_hold"),
            ("sighted", "blind"),
        ]
    results = []
    for a, b in pairings:
        res = arena(space, a, b, args.seeds, lv, ridx)
        results.append(res)
        print(json.dumps(res))
        sys.stdout.flush()

    out_path = HERE / TUN["results"]
    out_path.write_text(
        json.dumps(
            {"curve": args.curve, "seeds_per_seating": args.seeds, "tuning": TUN, "pairings": results},
            indent=2,
        )
    )
    print(f"wrote {out_path}")


if __name__ == "__main__":
    main()
