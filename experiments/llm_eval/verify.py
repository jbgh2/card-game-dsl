"""Independent recomputation of every reported number, for audit.

This deliberately does NOT call `metrics.aggregate`. It re-derives the headline
statistics straight from the transcript JSONL with its own arithmetic, so a bug
in the metrics layer cannot hide behind a checker that shares its code. Where
the two disagree, the disagreement is the finding.

Two depths, selectable with `--deep`:

  LEVEL 1 (default) reads the per-decision `facts` recorded during the run.
  LEVEL 2 (`--deep`) throws those away and REPLAYS each game from its
    `(seed, history)` through the engine, recomputing every fact — including
    `provably_false` — from the information states themselves. Slower
    (re-simulation is O(n^2)), and the only check that covers the recorded
    facts rather than trusting them.

Both levels print the raw numerator/denominator behind every rate, so the
arithmetic can be redone by hand or pasted into any stats package.

    python -m experiments.llm_eval.verify
    python -m experiments.llm_eval.verify --deep --matchup llm_mid_rendered_bluffer
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any

from . import infostate as istate

ANNOUNCE_COUNTS = {"play_one": 1, "play_two": 2, "play_three": 3, "play_four": 4}


def _stem(path: Path) -> str:
    """The matchup name, with `.jsonl` or `.jsonl.gz` stripped."""
    name = path.name
    for suffix in (".jsonl.gz", ".jsonl"):
        if name.endswith(suffix):
            return name[: -len(suffix)]
    return path.stem


def _load(path: Path) -> list[dict[str, Any]]:
    """Records from `.jsonl` or `.jsonl.gz` — committed transcripts are gzipped."""
    from .metrics import iter_jsonl

    return list(iter_jsonl(str(path)))


def _transcripts(root: Path) -> list[Path]:
    """One path per matchup, preferring an uncompressed file when both exist.

    A working run writes `.jsonl`; the committed archive is `.jsonl.gz`. Globbing
    both without deduping would count a matchup twice, which would look like
    twice the data rather than an error.
    """
    by_stem: dict[str, Path] = {}
    for f in sorted(root.glob("*.jsonl.gz")):
        by_stem[f.name[: -len(".jsonl.gz")]] = f
    for f in sorted(root.glob("*.jsonl")):
        by_stem[f.stem] = f  # fresher; wins over the archived copy
    return [by_stem[k] for k in sorted(by_stem)]


def _regroup(decisions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Reconstruct plays from scratch — announce, its cards, then its windows.

    Independent of `metrics.reconstruct_plays`: same structure, written again,
    so a grouping bug has to occur identically in two places to go unnoticed.
    """
    plays: list[dict[str, Any]] = []
    i = 0
    while i < len(decisions):
        d = decisions[i]
        if d["facts"].get("kind") != "announce":
            i += 1
            continue
        count = ANNOUNCE_COUNTS[d["action"]]
        cards: list[str] = []
        i += 1
        while i < len(decisions) and len(cards) < count:
            assert decisions[i]["facts"]["kind"] == "card", "play structure broken"
            cards.append(decisions[i]["action"])
            i += 1
        windows = []
        while i < len(decisions) and decisions[i]["facts"].get("kind") == "window":
            windows.append(decisions[i])
            i += 1
        plays.append({
            "actor": d["player"],
            "claim_rank": d["facts"]["claim_rank"],
            "count": count,
            "held": d["facts"]["truthful_available"],
            "cards": cards,
            "windows": windows,
        })
    return plays


def tally(records: list[dict[str, Any]], who: str) -> Counter[str]:
    """Raw counts only. Every reported rate is a ratio of two of these."""
    c: Counter[str] = Counter()
    for r in records:
        seats = {int(k): v for k, v in r["seats"].items()}
        me = next((s for s, n in seats.items() if n == who), None)
        if me is None:
            continue
        c["games"] += 1
        c["terminal_games"] += bool(r["terminal"])
        c["wins"] += bool(r["terminal"] and r["returns"][me] > 0)
        c["llm_calls"] += r.get("usage", {}).get(who, {}).get("llm_calls", 0)
        c["input_tokens"] += r.get("usage", {}).get(who, {}).get("input_tokens", 0)
        c["output_tokens"] += r.get("usage", {}).get(who, {}).get("output_tokens", 0)

        for d in r["decisions"]:
            if d["player"] != me:
                continue
            c["decisions"] += 1
            c["fallbacks"] += bool(d.get("llm", {}).get("fallback"))
            if d["facts"].get("kind") == "card":
                c["card_picks"] += 1
                want = d["facts"]["claim_rank"]
                truthful_offered = any(istate.rank_of(x) == want for x in d["legal"])
                if truthful_offered and istate.rank_of(d["action"]) != want:
                    c["skipped_truthful"] += 1

        for p in _regroup(r["decisions"]):
            lied = any(istate.rank_of(x) != p["claim_rank"] for x in p["cards"])
            if p["actor"] == me:
                c["plays"] += 1
                c["lies"] += lied
                if p["held"] == 0:
                    c["forced_lies"] += lied
                else:
                    c["plays_with_truthful_option"] += 1
                    c["elective_lies"] += lied
            for w in p["windows"]:
                if w["player"] != me:
                    continue
                called = w["facts"]["challenged"]
                c["windows"] += 1
                c["challenges_made"] += called
                c["challenges_correct"] += called and lied
                if lied:
                    c["false_faced"] += 1
                    c["false_caught"] += called
                    if w["facts"]["provably_false"]:
                        c["provable_faced"] += 1
                        c["provable_caught"] += called
                    else:
                        c["improbable_faced"] += 1
                        c["improbable_caught"] += called
    return c


RATES: list[tuple[str, str, str]] = [
    ("win_rate", "wins", "terminal_games"),
    ("fallback_rate", "fallbacks", "decisions"),
    ("skip_truthful_rate", "skipped_truthful", "card_picks"),
    ("lying_rate", "lies", "plays"),
    ("elective_lie_rate", "elective_lies", "plays_with_truthful_option"),
    ("challenge_rate", "challenges_made", "windows"),
    ("challenge_precision", "challenges_correct", "challenges_made"),
    ("challenge_recall", "false_caught", "false_faced"),
    ("provable_lie_detection", "provable_caught", "provable_faced"),
    ("improbable_lie_detection", "improbable_caught", "improbable_faced"),
]


def report(label: str, c: Counter[str]) -> None:
    print(f"\n=== {label} ===")
    print(f"  {'RAW COUNTS':38}")
    for k in sorted(c):
        print(f"    {k:34} {c[k]}")
    print(f"  {'RATE':34}{'= num / den':>22}")
    for name, num, den in RATES:
        if c[den]:
            print(f"    {name:32} {c[num]:>6} / {c[den]:<6} = {c[num]/c[den]:.4f}")
        else:
            print(f"    {name:32} {c[num]:>6} / {c[den]:<6} = None (no opportunities)")


def deep_facts(record: dict[str, Any]) -> list[dict[str, Any]]:
    """Recompute every per-decision fact by replaying `(seed, history)`.

    Covers the recorded `facts` instead of trusting them: the information states
    are a pure function of that pair, so this reproduces exactly what the run
    saw, then derives the facts again with today's code.
    """
    from .agents import DecisionView
    from .metrics import decision_facts
    from .referee import load_game, replay_views

    game = load_game("cardlang_cheat")
    views = replay_views(game, record["seed"], record["history"])
    out = []
    for view, d in zip(views, record["decisions"], strict=True):
        assert view.player == d["player"], "replay diverged from the transcript"
        assert view.legal_strings == d["legal"], "replay diverged on legal actions"
        out.append({**d, "facts": decision_facts(view, d["action"])})
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__ and __doc__.splitlines()[0])
    ap.add_argument("--dir", default="experiments/llm_eval/results/transcripts")
    ap.add_argument("--matchup", action="append", help="restrict to these (repeatable)")
    ap.add_argument("--deep", action="store_true", help="replay and recompute every fact")
    args = ap.parse_args(argv)

    root = Path(args.dir)
    files = _transcripts(root)
    if args.matchup:
        files = [f for f in files if _stem(f) in args.matchup]

    print("MANIFEST")
    for f in files:
        digest = hashlib.sha256(f.read_bytes()).hexdigest()[:16]
        print(f"  {f.name:36} {f.stat().st_size:>10,} bytes  sha256:{digest}")

    for f in files:
        records = _load(f)
        if not records:
            continue
        if args.deep:
            print(f"\n[replaying {_stem(f)} — recomputing every fact from (seed, history)]")
            records = [{**r, "decisions": deep_facts(r)} for r in records]
        agents = sorted({n for r in records for n in r["seats"].values()})
        for who in agents:
            c = tally(records, who)
            report(f"{_stem(f)} :: {who}  (N={c['games']}{' DEEP' if args.deep else ''})", c)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
