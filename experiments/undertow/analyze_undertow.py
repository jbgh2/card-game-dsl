"""Undertow probes — the large-state-space counterpart of Green Lane's exact
battery. No solve is possible (that's the design brief); instead:

  shape      random-rollout length / branching / seat balance
  liveness   how choice-rich plies stay by trick number (the design razor)
  tide       P(win next trick | you set the tide) vs baseline, tide-steal
             rate (void sluff redirects the trump), under random play
  mccfr      outcome-sampling training, then the same tide probe under
             trained self-play + a trained-seat-vs-random skill gradient

Run:  python analyze_undertow.py shape|tide|mccfr [iterations]
Everything reads/writes results_undertow.json incrementally.
"""

from __future__ import annotations

import json
import random
import re
import statistics
import sys
import time
from collections import defaultdict
from typing import Any

import pyspiel
import utcommon

N_SEEDS = 2048
RESULTS = utcommon.HERE / "results_undertow.json"


def save(section: str, data: Any) -> None:
    blob = json.loads(RESULTS.read_text()) if RESULTS.exists() else {}
    blob[section] = data
    RESULTS.write_text(json.dumps(blob, indent=2))
    print(f"[saved {section}]")


def playout(game: pyspiel.Game, rng: random.Random, policies: Any = None) -> pyspiel.State:
    """One game; policies = None (uniform) or per-seat list (None = uniform)."""
    st = game.new_initial_state()
    st.apply_action(rng.randrange(N_SEEDS))
    while not st.is_terminal():
        legal = st.legal_actions()
        pol = policies[st.current_player()] if policies else None
        if pol is None:
            st.apply_action(rng.choice(legal))
        else:
            probs = pol.action_probabilities(st)
            acts = list(probs.keys())
            st.apply_action(rng.choices(acts, weights=[probs[a] for a in acts], k=1)[0])
    return st


# --- log parsing (public events only) --------------------------------------

_PLAY = re.compile(r"^hand\[(\d)\]$")
_CAPT = re.compile(r"^captured\[(\d)\]$")


def tricks_from_log(log: list[tuple[Any, ...]]) -> list[dict[str, Any]]:
    """Reconstruct tricks: plays (player, card), tide card + its player,
    winner — all from one observer's public move events."""
    tricks: list[dict[str, Any]] = []
    cur: dict[str, Any] = {"plays": []}
    for e in log:
        if e[0] != "move":
            continue
        src, dst = e[1], e[3]
        m = _PLAY.match(str(src))
        if m and dst == "trick_pile":
            card = e[4][0] if isinstance(e[4], tuple) else None
            cur["plays"].append((int(m.group(1)), card))
            continue
        if src == "trick_pile" and dst == "tide_marker":
            cur["tide_card"] = e[2][0]
            continue
        w = _CAPT.match(str(dst))
        if w and src == "trick_pile" and len(cur["plays"]) == 4:
            # the final gather of the trick (the tide_marker gather precedes it)
            cur["winner"] = int(w.group(1))
            by_card = {c: p for p, c in cur["plays"]}
            cur["tide_setter"] = by_card.get(cur.get("tide_card"))
            cur["led_suit"] = cur["plays"][0][1][-1]
            cur["tide_suit"] = cur["tide_card"][-1] if cur.get("tide_card") else None
            tricks.append(cur)
            cur = {"plays": []}
    return tricks


def tide_stats(games: list[list[dict[str, Any]]]) -> dict[str, float]:
    win_next_given_set = 0
    set_events = 0
    steals = 0
    tricks_total = 0
    setter_won_same = 0
    for tricks in games:
        for i, t in enumerate(tricks):
            tricks_total += 1
            if t.get("tide_suit") and t["tide_suit"] != t["led_suit"]:
                steals += 1
            if t.get("tide_setter") is not None:
                if t["tide_setter"] == t["winner"]:
                    setter_won_same += 1
                if i + 1 < len(tricks):
                    set_events += 1
                    if tricks[i + 1]["winner"] == t["tide_setter"]:
                        win_next_given_set += 1
    return {
        "p_win_next_given_set_tide": win_next_given_set / max(1, set_events),
        "baseline_p_win": 0.25,
        "tide_steal_rate": steals / max(1, tricks_total),
        "p_setter_also_won_trick": setter_won_same / max(1, tricks_total),
        "tricks_parsed": tricks_total,
    }


def collect_logs(game: pyspiel.Game, n: int, rng: random.Random, policies: Any = None) -> list[list[dict[str, Any]]]:
    from cardlang.openspiel import replay

    out = []
    path = str(utcommon.HERE / utcommon.FILENAME)
    for _ in range(n):
        st = playout(game, rng, policies)
        # A Terminal result carries no logs, so replay to one action before
        # the end: every trick parses fully except the last, which drops out
        # of the stats (12 of 13 tricks per game is plenty for the probes).
        r = replay.run(path, st._seed, tuple(st._history_ids[:-1]))
        logs = r.obs_logs[0] if hasattr(r, "obs_logs") else []
        tricks = tricks_from_log(logs)
        out.append([t for t in tricks if "winner" in t])
    return out


def phase_shape(game: pyspiel.Game) -> None:
    rng = random.Random(11)
    lengths, rets = [], []
    branch_by_trick: dict[int, list[int]] = defaultdict(list)
    live_by_trick: dict[int, list[int]] = defaultdict(list)
    t0 = time.perf_counter()
    n = 300
    for _ in range(n):
        st = game.new_initial_state()
        st.apply_action(rng.randrange(N_SEEDS))
        ply = 0
        while not st.is_terminal():
            legal = st.legal_actions()
            trick = ply // 4
            branch_by_trick[trick].append(len(legal))
            live_by_trick[trick].append(1 if len(legal) > 1 else 0)
            st.apply_action(rng.choice(legal))
            ply += 1
        lengths.append(ply)
        rets.append(st.returns())
    dt = time.perf_counter() - t0
    seat = [statistics.mean(r[p] for r in rets) for p in range(4)]
    shape = {
        "n_games": n,
        "ms_per_game": round(dt / n * 1000),
        "decisions_per_game": statistics.mean(lengths),
        "seat_mean_tricks": [round(s, 3) for s in seat],
        "branching_by_trick": {
            t: round(statistics.mean(v), 2) for t, v in sorted(branch_by_trick.items())
        },
        "live_share_by_trick": {
            t: round(statistics.mean(v), 3) for t, v in sorted(live_by_trick.items())
        },
    }
    print(json.dumps(shape, indent=1))
    save("shape", shape)


def phase_tide(game: pyspiel.Game) -> None:
    rng = random.Random(23)
    games = collect_logs(game, 400, rng)
    stats = tide_stats(games)
    print("tide under RANDOM play:", json.dumps(stats, indent=1))
    save("tide_random", stats)


def phase_mccfr(game: pyspiel.Game, iterations: int) -> None:
    from open_spiel.python.algorithms import outcome_sampling_mccfr

    rng = random.Random(31)
    solver = outcome_sampling_mccfr.OutcomeSamplingSolver(game)
    t0 = time.perf_counter()
    for it in range(iterations):
        solver.iteration()
        if (it + 1) % 10_000 == 0:
            print(f"  mccfr {it + 1}/{iterations} ({time.perf_counter() - t0:.0f}s)")
    pol = solver.average_policy()
    print(f"trained {iterations} iterations in {time.perf_counter() - t0:.0f}s")

    # skill gradient: trained seat s vs uniform-random others, rotating s
    per_seat = []
    n_eval = 400
    for s in range(4):
        tot = 0.0
        for g in range(n_eval // 4):
            policies = [pol if p == s else None for p in range(4)]
            st = playout(game, rng, policies)
            tot += st.returns()[s]
        per_seat.append(tot / (n_eval // 4))
    gradient = {
        "trained_seat_mean_tricks_by_seat": [round(x, 3) for x in per_seat],
        "trained_seat_mean_tricks": round(sum(per_seat) / 4, 3),
        "baseline_random": 3.25,
        "iterations": iterations,
        "eval_games": n_eval,
    }
    print("skill gradient:", json.dumps(gradient, indent=1))
    save("mccfr_gradient", gradient)

    games = collect_logs(game, 300, rng, policies=[pol] * 4)
    stats = tide_stats(games)
    print("tide under TRAINED self-play:", json.dumps(stats, indent=1))
    save("tide_trained", stats)


def main() -> None:
    phase = sys.argv[1] if len(sys.argv) > 1 else "shape"
    utcommon.register(num_seeds=N_SEEDS)
    game = pyspiel.load_game(utcommon.SHORT_NAME)
    if phase == "shape":
        phase_shape(game)
    elif phase == "tide":
        phase_tide(game)
    elif phase == "mccfr":
        phase_mccfr(game, int(sys.argv[2]) if len(sys.argv) > 2 else 100_000)
    else:
        raise SystemExit(f"unknown phase {phase}")


if __name__ == "__main__":
    main()
