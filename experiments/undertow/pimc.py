"""Determinized-Monte-Carlo (PIMC) bot for Undertow, over fast_sim, plus its
benchmark battery. The bot's information discipline is enforced by the
function signature: `decide` receives only the deciding player's own hand
and the public state — never the other hands. Worlds are sampled uniformly
over completions consistent with hand counts, the cards already seen, and
the voids players revealed by failing to follow.

Run:  python pimc.py bench [n_games]    strength vs random + latency
      python pimc.py tide  [n_games]    tide probe under 4xPIMC self-play
      python pimc.py adapter [n_games]  cross-check through the real runtime
Results accumulate in results_pimc.json.
"""

from __future__ import annotations

import json
import random
import statistics
import sys
import time

import fast_sim
from fast_sim import Sim, voids_from_history

RESULTS = "results_pimc.json"


def save(section: str, data: object) -> None:
    from pathlib import Path

    p = Path(__file__).resolve().parent / RESULTS
    blob = json.loads(p.read_text()) if p.exists() else {}
    blob[section] = data
    p.write_text(json.dumps(blob, indent=2))
    print(f"[saved {section}]")


# --- consistent-world sampling --------------------------------------------


def sample_world(
    me: int,
    my_hand: list[int],
    history: list[list[tuple[int, int]]],
    trick: list[tuple[int, int]],
    hand_sizes: list[int],
    rng: random.Random,
    tries: int = 200,
) -> list[list[int]] | None:
    """Assign the unseen cards to the other players, respecting counts and
    observed voids. Randomized constructive fill with retry."""
    seen = set(my_hand)
    for t in history:
        seen.update(c for _, c in t)
    seen.update(c for _, c in trick)
    unseen = [c for c in range(52) if c not in seen]
    voids = voids_from_history(history + ([trick] if trick else []))
    others = [p for p in range(4) if p != me]
    for _ in range(tries):
        rng.shuffle(unseen)
        hands: list[list[int]] = [[] for _ in range(4)]
        hands[me] = list(my_hand)
        ok = True
        pool = list(unseen)
        # most-constrained-first: fewest allowed suits with largest need
        order = sorted(others, key=lambda p: (len(voids[p]), -hand_sizes[p]), reverse=True)
        for p in order:
            need = hand_sizes[p]
            take: list[int] = []
            rest: list[int] = []
            for c in pool:
                if len(take) < need and (c // 13) not in voids[p]:
                    take.append(c)
                else:
                    rest.append(c)
            if len(take) < need:
                ok = False
                break
            hands[p] = take
            pool = rest
        if ok and not pool:
            return hands
    return None


# --- rollout policies ------------------------------------------------------
# 'random': uniform legal (the measured First Mate). 'heuristic': the Grizzled
# Captain's opponent model — simulated players play PURPOSEFULLY: win the
# trick as cheaply as possible, otherwise duck low; leads half-cash a long
# suit's top card; 25% noise keeps the estimate honest. Mirrored line-for-line
# in the artifact's JS (parity by construction: same constants, same order).


def _beats(c: int, best: int, led: int, trump: int | None) -> bool:
    cs, bs = c // 13, best // 13
    if trump is not None:
        if cs == trump:
            return bs != trump or (c % 13) > (best % 13)
        if bs == trump:
            return False
    if cs == led:
        return bs != led or (c % 13) > (best % 13)
    return False


def heuristic_move(sim: Sim, rng: random.Random) -> int:
    lg = sim.legal()
    if len(lg) == 1 or rng.random() < 0.25:
        return rng.choice(lg)
    if sim.trick:
        led = sim.trick[0][1] // 13
        best = sim.trick[0][1]
        for _, c in sim.trick[1:]:
            if _beats(c, best, led, sim.trump):
                best = c
        winning = [c for c in lg if _beats(c, best, led, sim.trump)]
        if winning:
            return min(winning, key=lambda c: c % 13)
        return min(lg, key=lambda c: c % 13)
    if rng.random() < 0.5:
        by_suit: dict[int, list[int]] = {}
        for c in lg:
            by_suit.setdefault(c // 13, []).append(c)
        suit = max(by_suit, key=lambda s: max(cc % 13 for cc in by_suit[s]))
        return max(by_suit[suit], key=lambda c: c % 13)
    return rng.choice(lg)


def rollout(sim: Sim, rng: random.Random, policy: str) -> list[int]:
    if policy == "random":
        return sim.rollout_random(rng)
    while not sim.terminal():
        sim.apply(heuristic_move(sim, rng))
    return sim.tricks_won


# --- the bot ---------------------------------------------------------------


def decide(
    me: int,
    my_hand: list[int],
    history: list[list[tuple[int, int]]],
    trick: list[tuple[int, int]],
    trump: int | None,
    leader: int,
    hand_sizes: list[int],
    tricks_won: list[int],
    rng: random.Random,
    worlds: int = 16,
    rollouts: int = 3,
    policy: str = "random",
) -> int:
    """Pick a card: average final own-tricks over sampled worlds x rollouts
    (uniform-random or heuristic opponents), per candidate; argmax."""
    # legality mirrors the engine
    if trick:
        led = trick[0][1] // 13
        follow = [c for c in my_hand if c // 13 == led]
        cands = follow if follow else list(my_hand)
    else:
        cands = list(my_hand)
    if len(cands) == 1:
        return cands[0]

    totals = {c: 0.0 for c in cands}
    n = 0
    for _ in range(worlds):
        hands = sample_world(me, my_hand, history, trick, hand_sizes, rng)
        if hands is None:
            continue
        base = Sim(hands, leader=leader)
        base.trump = trump
        base.to_play = me
        base.trick = list(trick)
        base.tricks_won = list(tricks_won)
        base.history = [list(t) for t in history]
        n += 1
        for c in cands:
            for _ in range(rollouts):
                s = base.copy()
                s.apply(c)
                won = rollout(s, rng, policy)
                totals[c] += won[me]
    if n == 0:  # sampler starved (shouldn't happen); play safe
        return rng.choice(cands)
    best = max(totals.values())
    return rng.choice([c for c, v in totals.items() if v >= best - 1e-9])


def decide_from_sim(
    sim: Sim, me: int, rng: random.Random, worlds: int, rollouts: int,
    policy: str = "random",
) -> int:
    """Adapter for self-play: extracts EXACTLY the deciding player's view."""
    return decide(
        me,
        list(sim.hands[me]),
        sim.history,
        list(sim.trick),
        sim.trump,
        sim.leader,
        [len(h) for h in sim.hands],
        list(sim.tricks_won),
        rng,
        worlds,
        rollouts,
        policy,
    )


def random_deal(rng: random.Random) -> list[list[int]]:
    deck = list(range(52))
    rng.shuffle(deck)
    return [deck[i * 13 : (i + 1) * 13] for i in range(4)]


# --- benches ---------------------------------------------------------------


def bench(n_games: int) -> None:
    rng = random.Random(7)
    means = []
    latencies: list[float] = []
    for seat in range(4):
        tot = 0.0
        for g in range(n_games // 4):
            sim = Sim(random_deal(rng))
            while not sim.terminal():
                if sim.to_play == seat:
                    t0 = time.perf_counter()
                    c = decide_from_sim(sim, seat, rng, worlds=16, rollouts=3)
                    latencies.append(time.perf_counter() - t0)
                    sim.apply(c)
                else:
                    sim.apply(rng.choice(sim.legal()))
            tot += sim.tricks_won[seat]
        means.append(tot / (n_games // 4))
        print(f"  seat {seat}: PIMC mean tricks {means[-1]:.3f} (random baseline 3.25)")
    overall = sum(means) / 4
    out = {
        "pimc_vs_3_random_mean_tricks": round(overall, 3),
        "by_seat": [round(m, 3) for m in means],
        "baseline": 3.25,
        "n_games": n_games,
        "worlds": 16,
        "rollouts": 3,
        "ms_per_decision": round(1000 * statistics.mean(latencies), 1),
    }
    print(json.dumps(out, indent=1))
    save("bench_vs_random", out)


def tide(n_games: int) -> None:
    rng = random.Random(23)
    win_next = 0
    set_events = 0
    steals = 0
    tricks_total = 0
    for _ in range(n_games):
        sim = Sim(random_deal(rng))
        setters: list[int | None] = []
        while not sim.terminal():
            me = sim.to_play
            c = decide_from_sim(sim, me, rng, worlds=10, rollouts=2)
            before = len(sim.history)
            sim.apply(c)
            if len(sim.history) > before:
                t = sim.history[-1]
                led = t[0][1] // 13
                low = min(cc % 13 for _, cc in t)
                tide_card = next(cc for _, cc in t if cc % 13 == low)
                setter = next(q for q, cc in t if cc == tide_card)
                setters.append(setter)
                tricks_total += 1
                if tide_card // 13 != led:
                    steals += 1
        # winners recomputed per trick from history (trump of trick i+1 is
        # the tide of trick i)
        for i in range(len(sim.history) - 1):
            set_events += 1
            nxt_winner = sim_winner(sim.history[i + 1], trump_of(sim.history[: i + 1]))
            if setters[i] == nxt_winner:
                win_next += 1
    out = {
        "p_win_next_given_set_tide": round(win_next / max(1, set_events), 4),
        "baseline_p_win": 0.25,
        "tide_steal_rate": round(steals / max(1, tricks_total), 4),
        "tricks": tricks_total,
        "n_games": n_games,
        "worlds": 10,
        "rollouts": 2,
    }
    print(json.dumps(out, indent=1))
    save("tide_pimc_selfplay", out)


def trump_of(history: list[list[tuple[int, int]]]) -> int | None:
    if not history:
        return None
    t = history[-1]
    low = min(c % 13 for _, c in t)
    return next(c for _, c in t if c % 13 == low) // 13


def sim_winner(trick: list[tuple[int, int]], trump: int | None) -> int:
    led = trick[0][1] // 13
    if trump is not None and any(c // 13 == trump for _, c in trick):
        return max((qc for qc in trick if qc[1] // 13 == trump), key=lambda qc: qc[1] % 13)[0]
    return max((qc for qc in trick if qc[1] // 13 == led), key=lambda qc: qc[1] % 13)[0]


def adapter_crosscheck(n_games: int) -> None:
    """Play PIMC (seat rotates) vs 3 randoms THROUGH THE REAL RUNTIME. The
    bot's own hand comes from its own information state; everything else it
    tracks is public (plays, tricks, tide) stepped from action labels."""
    import re as _re

    import pyspiel
    import utcommon

    utcommon.register(num_seeds=2048)
    game = pyspiel.load_game(utcommon.SHORT_NAME)
    rng = random.Random(31)
    tot = 0.0
    for g in range(n_games):
        seat = g % 4
        st = game.new_initial_state()
        st.apply_action(rng.randrange(2048))
        my_hand: list[int] | None = None
        history: list[list[tuple[int, int]]] = []
        trick: list[tuple[int, int]] = []
        tricks_won = [0, 0, 0, 0]
        trump: int | None = None
        while not st.is_terminal():
            p = st.current_player()
            legal = st.legal_actions()
            if p == seat:
                if my_hand is None:
                    m = _re.search(
                        rf"hand\[{seat}\]=\[([^\]]*)\]",
                        st.information_state_string(seat),
                    )
                    assert m is not None
                    my_hand = [fast_sim.parse_label(x) for x in m.group(1).split(",") if x]
                sizes = [
                    13
                    - sum(1 for t in history for q, _ in t if q == pp)
                    - sum(1 for q, _ in trick if q == pp)
                    for pp in range(4)
                ]
                c = decide(
                    seat, list(my_hand), history, trick, trump,
                    trick[0][0] if trick else seat, sizes, tricks_won,
                    rng, worlds=12, rollouts=2,
                )
                a = next(
                    aa for aa in legal
                    if fast_sim.parse_label(st.action_to_string(p, aa)) == c
                )
                my_hand.remove(c)
            else:
                a = rng.choice(legal)
            card = fast_sim.parse_label(st.action_to_string(p, a))
            trick.append((p, card))
            if len(trick) == 4:
                w = sim_winner(trick, trump)
                low = min(cc % 13 for _, cc in trick)
                trump = next(cc for _, cc in trick if cc % 13 == low) // 13
                tricks_won[w] += 1
                history.append(trick)
                trick = []
            st.apply_action(a)
        tot += st.returns()[seat]
    out = {"adapter_pimc_vs_random_mean_tricks": round(tot / n_games, 3),
           "n_games": n_games, "baseline": 3.25}
    print(json.dumps(out, indent=1))
    save("adapter_crosscheck", out)


def levels_bench() -> None:
    """Measured claims for the artifact's difficulty ladder. Drunken Deckhand
    is uniform random (3.25 by definition); First Mate is the already-measured
    16/3 random-rollout player (5.40); this benches the other two rungs plus
    the ladder's top step head-to-head."""
    rng = random.Random(41)
    out: dict[str, object] = {}

    def vs_random(tag: str, worlds: int, rollouts: int, policy: str, n_games: int) -> None:
        tot = 0.0
        t0 = time.perf_counter()
        lat: list[float] = []
        for g in range(n_games):
            seat = g % 4
            sim = Sim(random_deal(rng))
            while not sim.terminal():
                if sim.to_play == seat:
                    t1 = time.perf_counter()
                    c = decide_from_sim(sim, seat, rng, worlds, rollouts, policy)
                    lat.append(time.perf_counter() - t1)
                    sim.apply(c)
                else:
                    sim.apply(rng.choice(sim.legal()))
            tot += sim.tricks_won[seat]
        out[tag] = {
            "mean_tricks_vs_3_random": round(tot / n_games, 3),
            "worlds": worlds, "rollouts": rollouts, "policy": policy,
            "n_games": n_games, "ms_per_decision": round(1000 * statistics.mean(lat), 1),
        }
        print(tag, json.dumps(out[tag]), f"({time.perf_counter() - t0:.0f}s)")

    vs_random("bosun", 2, 1, "random", 200)
    vs_random("captain", 32, 3, "heuristic", 160)

    # the top step of the ladder, head-to-head: one captain vs three mates
    tot = 0.0
    n_h2h = 120
    t0 = time.perf_counter()
    for g in range(n_h2h):
        seat = g % 4
        sim = Sim(random_deal(rng))
        while not sim.terminal():
            p = sim.to_play
            if p == seat:
                c = decide_from_sim(sim, p, rng, 32, 3, "heuristic")
            else:
                c = decide_from_sim(sim, p, rng, 16, 3, "random")
            sim.apply(c)
        tot += sim.tricks_won[seat]
    out["captain_vs_3_mates"] = {
        "captain_mean_tricks": round(tot / n_h2h, 3),
        "baseline_equal_play": 3.25, "n_games": n_h2h,
    }
    print("captain_vs_3_mates", json.dumps(out["captain_vs_3_mates"]),
          f"({time.perf_counter() - t0:.0f}s)")
    save("levels", out)


def main() -> None:
    mode = sys.argv[1] if len(sys.argv) > 1 else "bench"
    n = int(sys.argv[2]) if len(sys.argv) > 2 else (240 if mode == "bench" else 100)
    if mode == "bench":
        bench(n)
    elif mode == "tide":
        tide(n)
    elif mode == "adapter":
        adapter_crosscheck(n)
    elif mode == "levels":
        levels_bench()
    else:
        raise SystemExit(f"unknown mode {mode}")


if __name__ == "__main__":
    main()
