"""Design-feedback loop: how does Green Lane's equilibrium respond to the
fine parameter? Generates mini variants with fine ∈ {0, 2, 4, 8}, solves each
with CFR+, and reports the round-1 bluff/inspection frequencies, game value,
and residual exploitability. Run:
    python experiments/green-lane/sweep_fine.py [iterations]
"""

from __future__ import annotations

import json
import sys
import tempfile
import time
from pathlib import Path

import pyspiel
from open_spiel.python.algorithms import cfr, exploitability

import glcommon

FINES = (0, 2, 4, 8)
DEFAULT_ITERATIONS = 250


def make_variant(fine: int, out_dir: Path) -> Path:
    source = (glcommon.HERE / "green-lane-mini.cardlang").read_text()
    body = (
        source.replace("game GreenLaneMini {", f"game GreenLaneMiniF{fine} {{")
        .replace("-= 4", f"-= {fine}")
        .replace("+= 4", f"+= {fine}")
    )
    assert body.count(f"-= {fine}") == 2 and body.count(f"+= {fine}") == 2
    path = out_dir / f"green-lane-mini-f{fine}.cardlang"
    path.write_text(body)
    return path


def round1_strategies(
    game: pyspiel.Game, avg_policy: object
) -> tuple[dict[str, float], dict[str, float]]:
    """(merchant round-1 mixture, inspector round-1 mixture), readable labels."""
    state = game.new_initial_state()
    state.apply_action(0)  # the single seed
    merchant_probs = {
        state.action_to_string(0, a): p
        for a, p in avg_policy.action_probabilities(state).items()  # type: ignore[attr-defined]
    }
    # Advance to the inspector's response; their round-1 information set is
    # unique (the shipment is hidden), so any merchant action reaches it.
    state.apply_action(state.legal_actions()[0])
    inspector_probs = {
        state.action_to_string(1, a): p
        for a, p in avg_policy.action_probabilities(state).items()  # type: ignore[attr-defined]
    }
    return merchant_probs, inspector_probs


def main() -> None:
    iterations = int(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_ITERATIONS
    glcommon.install_replay_memo()
    glcommon.install_infostate_memo()

    out_dir = Path(tempfile.mkdtemp(prefix="greenlane_sweep_"))
    rows = []
    for fine in FINES:
        path = make_variant(fine, out_dir)
        short_name = f"greenlane_mini_f{fine}"
        glcommon.register(short_name, path.name, num_seeds=1, base_dir=path.parent)
        game = pyspiel.load_game(short_name)
        solver = cfr.CFRPlusSolver(game)
        t0 = time.perf_counter()
        for _ in range(iterations):
            solver.evaluate_and_update_policy()
        avg = solver.average_policy()
        expl = exploitability.exploitability(game, avg)
        merchant, inspector = round1_strategies(game, avg)
        dt = time.perf_counter() - t0

        ship_a = next(p for label, p in merchant.items() if label.startswith("A"))
        inspect_p = inspector.get("inspect", 0.0)
        rows.append(
            {
                "fine": fine,
                "iterations": iterations,
                "exploitability": expl,
                "round1_p_ship_ace": ship_a,
                "round1_p_inspect": inspect_p,
                "round1_merchant": merchant,
                "round1_inspector": inspector,
                "seconds": dt,
            }
        )
        print(
            f"fine={fine}: P(ship A round 1)={ship_a:.3f}  "
            f"P(inspect round 1)={inspect_p:.3f}  expl={expl:.3f}  ({dt:.0f}s)"
        )

    with open(glcommon.HERE / "results_sweep.json", "w") as fh:
        json.dump(rows, fh, indent=2)
    print("wrote results_sweep.json")


if __name__ == "__main__":
    main()
