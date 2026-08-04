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
from . import layout

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


DEFAULT_RESULTS = Path("experiments/llm_eval/results")


def resolve_dir(explicit: str | None, run: str | None) -> Path:
    """Which transcripts directory to read, from the two mutually-exclusive ways
    of naming one.

    Both given is a contradiction, not a precedence question: silently honouring
    one would report a different body of data than the operator asked for, under
    a heading that names what they asked for.
    """
    if explicit and run:
        raise SystemExit("pass --dir or --run, not both — they name different data")
    if explicit:
        return Path(explicit)
    if run:
        if run == "latest":
            found = layout.latest_run(DEFAULT_RESULTS)
            if found is None:
                raise SystemExit(
                    f"no run directories under {DEFAULT_RESULTS / layout.RUNS} yet"
                )
            return found / layout.ARCHIVE
        candidate = DEFAULT_RESULTS / layout.RUNS / run
        if not candidate.is_dir():
            available = [p.name for p in layout.list_runs(DEFAULT_RESULTS)]
            raise SystemExit(f"no run named {run!r}; available: {available}")
        return candidate / layout.ARCHIVE
    return layout.archive_dir(DEFAULT_RESULTS)


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
        if len(cards) < count:
            break  # truncated mid-play; the move never happened (see metrics.py)
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
        # EVERY seat carrying this label, not the first: the shipped matchups put
        # three `rule` (or `random`) agents at the table, and counting one of them
        # would silently report a third of the baseline's plays and challenges
        # while `metrics.aggregate` counts all three. An audit that disagrees with
        # the thing it audits, for a reason invisible in the output, is worse than
        # no audit. One seat-game per seat, matching `aggregate`'s denominators.
        mine = {s for s, n in seats.items() if n == who}
        if not mine:
            continue
        for me in mine:
            c["games"] += 1
            c["terminal_games"] += bool(r["terminal"])
            c["wins"] += bool(r["terminal"] and r["returns"][me] > 0)
        # Usage is recorded per AGENT NAME, not per seat, so it is added once.
        c["llm_calls"] += r.get("usage", {}).get(who, {}).get("llm_calls", 0)
        c["input_tokens"] += r.get("usage", {}).get(who, {}).get("input_tokens", 0)
        c["output_tokens"] += r.get("usage", {}).get(who, {}).get("output_tokens", 0)

        for d in r["decisions"]:
            if d["player"] not in mine:
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
            if p["actor"] in mine:
                c["plays"] += 1
                c["lies"] += lied
                if p["held"] == 0:
                    c["forced_lies"] += lied
                else:
                    c["plays_with_truthful_option"] += 1
                    c["elective_lies"] += lied
            for w in p["windows"]:
                if w["player"] not in mine:
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


def holdem_tally(records: list[dict[str, Any]], who: str) -> Counter[str]:
    """The heads-up Hold'em recomputation, independent of `metrics.aggregate`.

    Deliberately reads the referee's OWN record of each decision — `legal` and
    `action`, written by the game loop — and never `facts["offered"]` or
    `facts["verb"]`, which `holdem_pack.decision_facts` produced. So a bug in
    the pack's facts function shows up here as a disagreement rather than being
    reproduced by an auditor that shares its input.

    Offer-conditioned throughout: a verb's denominator is the decisions where it
    was LEGAL. Over all decisions instead, `fold_rate` would silently mix
    "declined to fold" with "could not fold", and every rate would drift with
    how often the game happens to offer a free check.
    """
    c: Counter[str] = Counter()
    for record in records:
        seats = {int(k): v for k, v in record["seats"].items()}
        mine = [s for s, name in seats.items() if name == who]
        if not mine:
            continue
        c["games"] += 1
        if record["terminal"]:
            for seat in mine:
                c["terminal_games"] += 1
                net = record["returns"][seat]
                if net > 0:
                    c["wins"] += 1
                elif net == 0:
                    c["splits"] += 1
                # Chip delta, summed so the mean can be taken against
                # `terminal_games` — the metric the blinds do not swamp.
                c["net_total"] += int(net)
        for d in record["decisions"]:
            if seats[d["player"]] != who:
                continue
            c["decisions"] += 1
            if d.get("llm", {}).get("fallback"):
                c["fallbacks"] += 1
            for verb in ("check", "bet", "call", "raise", "fold"):
                if verb in d["legal"]:
                    c[f"{verb}_offered"] += 1
                    if d["action"] == verb:
                        c[f"{verb}_chosen"] += 1
    return c


HOLDEM_RATES: list[tuple[str, str, str]] = [
    # Chips first: it is the metric that survives the blinds. A player can win a
    # minority of hands and still finish ahead, and the first version of this
    # game's baseline did exactly that.
    ("mean_net_chips", "net_total", "terminal_games"),
    ("win_rate", "wins", "terminal_games"),
    ("fallback_rate", "fallbacks", "decisions"),
    ("check_rate", "check_chosen", "check_offered"),
    ("bet_rate", "bet_chosen", "bet_offered"),
    ("call_rate", "call_chosen", "call_offered"),
    ("raise_rate", "raise_chosen", "raise_offered"),
    ("fold_rate", "fold_chosen", "fold_offered"),
]

# The recomputation and its rate table, per game. A game absent here has no
# audit path and `main` refuses it, rather than printing Cheat's rates over
# another game's transcript — every one of which would read `0 / 0 = None` and
# look like a clean result.
AUDITS: dict[str, tuple[Any, list[tuple[str, str, str]]]] = {}


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


AUDITS.update(
    {
        "cardlang_cheat": (tally, RATES),
        "cardlang_holdem_heads_up": (holdem_tally, HOLDEM_RATES),
    }
)


def report(label: str, c: Counter[str], rates: list[tuple[str, str, str]]) -> None:
    print(f"\n=== {label} ===")
    print(f"  {'RAW COUNTS':38}")
    for k in sorted(c):
        print(f"    {k:34} {c[k]}")
    print(f"  {'RATE':34}{'= num / den':>22}")
    for name, num, den in rates:
        if c[den]:
            print(f"    {name:32} {c[num]:>6} / {c[den]:<6} = {c[num]/c[den]:.4f}")
        else:
            print(f"    {name:32} {c[num]:>6} / {c[den]:<6} = None (no opportunities)")


def arm_audit(records: list[dict[str, Any]], who: str) -> Counter[str]:
    """Whether a response-format arm is doing what it claims, from raw replies.

    Three things no behavioural metric can show, all of which invalidate an arm
    rather than merely degrading it:

    KEY ORDER. `json.loads` discards it, so the `reason_first` arm and the
    default parse identically and the entire manipulation lives in what the
    model generated first. This counts, over successfully-parsed replies
    carrying both keys, how often `reasoning` really precedes `action` in the
    raw text. Near 1.0 means the arm exists; near 0.5 means it measured nothing
    and the N does not matter.

    TRUNCATION. `stop_reason == "max_tokens"` says the model ran out of budget
    mid-reply. In the default arm that costs the justification; in an arm where
    reasoning comes first it costs the ACTION, and the reply becomes
    unparseable. This is the leading indicator of the failure that made the
    neutral arm unusable, where the fallback rate is the lagging one.

    RETRY PRESSURE. Calls per decision. The neutral arm's 1.85 is what exposed
    that 46% of its decisions had been shown a retry note contradicting the arm.
    """
    c: Counter[str] = Counter()
    for record in records:
        seats = {int(k) for k, v in record["seats"].items() if v == who}
        for d in record["decisions"]:
            if d["player"] not in seats:
                continue
            llm = d.get("llm") or {}
            if not llm:
                continue
            c["decisions"] += 1
            c["fallbacks"] += bool(llm.get("fallback"))
            if llm.get("arm"):
                c[f"arm:{llm['arm']}"] += 1
            for attempt in llm.get("attempts", []):
                c["calls"] += 1
                c["output_tokens"] += int(attempt.get("output_tokens", 0))
                if attempt.get("stop_reason") == "max_tokens":
                    c["stop_max_tokens"] += 1
                if attempt.get("error"):
                    c["parse_errors"] += 1
                    continue
                text = attempt.get("response") or ""
                # Both keys present, so the comparison is meaningful. An arm
                # asking for one key contributes nothing here, which is why the
                # denominator is counted rather than assumed.
                where_r, where_a = text.find('"reasoning"'), text.find('"action"')
                if where_r < 0 or where_a < 0:
                    continue
                c["ordered_pairs"] += 1
                c["reasoning_first"] += where_r < where_a
    return c


def report_arm(label: str, c: Counter[str]) -> None:
    print(f"\n=== {label} ===")
    for k in sorted(c):
        print(f"    {k:34} {c[k]}")
    pairs, calls, decisions = c["ordered_pairs"], c["calls"], c["decisions"]
    print(f"  {'RATE':34}{'= num / den':>22}")
    if pairs:
        print(
            f"    {'reasoning_before_action':32} {c['reasoning_first']:>6} / "
            f"{pairs:<6} = {c['reasoning_first'] / pairs:.4f}"
        )
    else:
        print(
            f"    {'reasoning_before_action':32} {'—':>6}   "
            f"(no reply carried both keys; this arm asks for one)"
        )
    if calls:
        print(
            f"    {'truncated_at_max_tokens':32} {c['stop_max_tokens']:>6} / "
            f"{calls:<6} = {c['stop_max_tokens'] / calls:.4f}"
        )
        print(
            f"    {'parse_error_rate':32} {c['parse_errors']:>6} / "
            f"{calls:<6} = {c['parse_errors'] / calls:.4f}"
        )
        print(f"    {'output_tokens_per_call':32} {c['output_tokens'] / calls:>13.1f}")
    if decisions:
        print(
            f"    {'fallback_rate':32} {c['fallbacks']:>6} / "
            f"{decisions:<6} = {c['fallbacks'] / decisions:.4f}"
        )
        print(f"    {'calls_per_decision':32} {calls / decisions:>13.4f}")


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
    ap.add_argument(
        "--dir",
        default=None,
        help="transcripts directory (default: the curated archive, "
        "experiments/llm_eval/results/transcripts)",
    )
    ap.add_argument(
        "--run",
        default=None,
        metavar="NAME",
        help="audit a run directory under results/runs instead of the archive. "
        "`latest` picks the most recent. The DEFAULT stays the archive on "
        "purpose: the documented audit command must keep covering the published "
        "evidence, not whichever run happened to finish last.",
    )
    ap.add_argument("--matchup", action="append", help="restrict to these (repeatable)")
    ap.add_argument(
        "--game",
        default="cardlang_cheat",
        choices=sorted(AUDITS),
        help="which game's recomputation to run. Defaults to Cheat so the "
        "documented audit command keeps covering the published evidence; a "
        "transcript of another game needs its own flag, because a game's rate "
        "table run over a different game prints `0 / 0 = None` for every rate "
        "and reads like a clean audit.",
    )
    ap.add_argument("--deep", action="store_true", help="replay and recompute every fact")
    ap.add_argument(
        "--order",
        action="store_true",
        help="audit the response-format arm from the raw replies (key order, "
        "truncation, retry pressure) instead of the behavioural metrics",
    )
    args = ap.parse_args(argv)

    root = resolve_dir(args.dir, args.run)
    print(f"reading {root}")
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
            if args.game != "cardlang_cheat":
                raise SystemExit(
                    f"--deep replays through `deep_facts`, which reconstructs "
                    f"CHEAT's per-decision facts; it has no counterpart for "
                    f"{args.game}. Drop --deep: the level-1 recomputation below "
                    f"already reads the referee's own `legal`/`action` record "
                    f"rather than the pack's facts, so it does not trust the "
                    f"layer it audits."
                )
            print(f"\n[replaying {_stem(f)} — recomputing every fact from (seed, history)]")
            records = [{**r, "decisions": deep_facts(r)} for r in records]
        agents = sorted({n for r in records for n in r["seats"].values()})
        for who in agents:
            if args.order:
                c = arm_audit(records, who)
                if c["decisions"]:
                    report_arm(f"{_stem(f)} :: {who}  ARM AUDIT (N={len(records)})", c)
                continue
            audit, rates = AUDITS[args.game]
            c = audit(records, who)
            report(
                f"{_stem(f)} :: {who}  (N={c['games']}{' DEEP' if args.deep else ''})",
                c,
                rates,
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
