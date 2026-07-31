"""The one figure: win rate, challenge precision/recall, and provable-lie
detection, per agent across matchups.

Bars for a metric with no opportunities are drawn as a hatched zero-height
marker rather than a zero bar — a missing denominator and a genuine zero are
different claims, and the figure is the proposal artifact.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")  # no display in a headless run
import matplotlib.pyplot as plt  # noqa: E402

PANELS: list[tuple[str, str]] = [
    ("win_rate", "Win rate"),
    ("challenge_precision", "Challenge precision"),
    ("challenge_recall", "Challenge recall"),
    ("provable_lie_detection", "Provable-lie detection"),
    ("elective_lie_rate", "Elective lie rate"),
    ("fallback_rate", "Fallback rate"),
]


def _series(summary: dict[str, Any]) -> tuple[list[str], dict[str, dict[str, float | None]]]:
    """Flatten to `(labels, {metric: {label: value}})`, one label per
    (matchup, agent) pair that actually played."""
    labels: list[str] = []
    values: dict[str, dict[str, float | None]] = {key: {} for key, _ in PANELS}
    for matchup in summary["matchups"]:
        for agent, stats in matchup["agents"].items():
            label = f"{agent}\n{matchup['matchup']}"
            labels.append(label)
            for key, _ in PANELS:
                values[key][label] = stats.get(key)
    return labels, values


def render(summary: dict[str, Any], out_path: Path) -> Path:
    labels, values = _series(summary)
    if not labels:
        raise ValueError("summary contains no agent statistics — nothing to plot")

    rows = (len(PANELS) + 1) // 2
    fig, axes = plt.subplots(rows, 2, figsize=(max(9.0, 1.3 * len(labels)), 3.2 * rows))
    flat = axes.flatten()

    for ax, (key, title) in zip(flat, PANELS, strict=False):
        series = values[key]
        heights: list[float] = [float(series[label] or 0.0) for label in labels]
        missing = [series[label] is None for label in labels]
        bars = ax.bar(range(len(labels)), heights, color="#3b6ea5")
        for i, (bar, absent) in enumerate(zip(bars, missing, strict=True)):
            if absent:
                bar.set_hatch("///")
                bar.set_color("#cccccc")
                ax.text(i, 0.02, "n/a", ha="center", fontsize=7, color="#666666")
            else:
                ax.text(
                    i, heights[i] + 0.02, f"{heights[i]:.2f}", ha="center", fontsize=7
                )
        ax.set_title(title, fontsize=10)
        ax.set_ylim(0, 1.15)
        ax.set_xticks(range(len(labels)))
        ax.set_xticklabels(labels, fontsize=7, rotation=30, ha="right")
        ax.grid(axis="y", alpha=0.25)

    for ax in flat[len(PANELS) :]:
        ax.set_visible(False)

    fig.suptitle(
        "Cheat through the cardlang OpenSpiel adapter — derived information states",
        fontsize=12,
    )
    fig.tight_layout(rect=(0, 0, 1, 0.96))
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=150)
    plt.close(fig)
    return out_path


def main(argv: list[str] | None = None) -> int:
    import argparse
    import json

    parser = argparse.ArgumentParser(description="render the summary figure")
    parser.add_argument("--summary", default="experiments/llm_eval/results/summary.json")
    parser.add_argument("--out", default="experiments/llm_eval/results/figure.png")
    args = parser.parse_args(argv)
    summary = json.loads(Path(args.summary).read_text(encoding="utf-8"))
    print(f"wrote {render(summary, Path(args.out))}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
