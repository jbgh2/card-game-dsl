"""Green Lane smoke test: does the game run end-to-end through the adapter,
are the returns really zero-sum, and do the derived information states hide
what the design says is hidden? Also times the replay cost to size the
solver budget. Run:  python experiments/green-lane/smoke.py
"""

from __future__ import annotations

import random
import statistics
import time

import pyspiel

import glcommon


def random_playout(game: pyspiel.Game, rng: random.Random) -> tuple[list[float], int, list[int]]:
    state = game.new_initial_state()
    steps = 0
    branchings: list[int] = []
    while not state.is_terminal():
        if state.is_chance_node():
            state.apply_action(rng.choice([o for o, _ in state.chance_outcomes()]))
            continue
        legal = state.legal_actions()
        branchings.append(len(legal))
        state.apply_action(rng.choice(legal))
        steps += 1
    return state.returns(), steps, branchings


def show_sample_trajectory(game: pyspiel.Game, rng: random.Random) -> None:
    state = game.new_initial_state()
    state.apply_action(0)  # the single seed
    ply = 0
    printed_infostate = False
    while not state.is_terminal():
        legal = state.legal_actions()
        player = state.current_player()
        action = rng.choice(legal)
        labels = [state.action_to_string(player, a) for a in legal]
        print(f"  ply {ply:2d} P{player} legal={labels} -> {state.action_to_string(player, action)}")
        # After a few plies, dump both players' information states once, so a
        # human can eyeball what each side knows mid-game.
        if ply == 5 and not printed_infostate:
            printed_infostate = True
            for p in (0, 1):
                print(f"    infostate P{p}: {state.information_state_string(p)}")
        state.apply_action(action)
        ply += 1
    print(f"  terminal returns: {state.returns()}")


def main() -> None:
    glcommon.register_all(num_seeds=1)
    rng = random.Random(7)

    for short_name in glcommon.GAMES:
        game = pyspiel.load_game(short_name)
        print(f"== {short_name} ==")

        t0 = time.perf_counter()
        lengths: list[int] = []
        branch_all: list[int] = []
        returns_seen: list[list[float]] = []
        n_games = 200
        for _ in range(n_games):
            rets, steps, branchings = random_playout(game, rng)
            assert abs(sum(rets)) < 1e-9, f"returns not zero-sum: {rets}"
            lengths.append(steps)
            branch_all.extend(branchings)
            returns_seen.append(rets)
        dt = time.perf_counter() - t0

        p0 = [r[0] for r in returns_seen]
        print(f"  {n_games} random playouts in {dt:.1f}s ({dt / n_games * 1000:.0f} ms/game)")
        print(f"  length: mean {statistics.mean(lengths):.1f} (min {min(lengths)}, max {max(lengths)})")
        print(f"  branching: mean {statistics.mean(branch_all):.2f} (max {max(branch_all)})")
        print(
            f"  P0 return: mean {statistics.mean(p0):+.2f} sd {statistics.pstdev(p0):.2f} "
            f"(min {min(p0):+.0f}, max {max(p0):+.0f})"
        )
        print(f"  P0 win/draw/loss: {sum(r > 0 for r in p0)}/{sum(r == 0 for r in p0)}/{sum(r < 0 for r in p0)}")
        print(f"  replay memo: {glcommon.replay_memo_info()}")
        print("  sample trajectory:")
        show_sample_trajectory(game, random.Random(3))
        print()


if __name__ == "__main__":
    main()
