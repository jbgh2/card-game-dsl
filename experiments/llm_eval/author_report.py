"""The authoring benchmark's report: the table, and every refusal a model
could not act on, each ready to file as a part of epic #1043.

    python -m experiments.llm_eval.author_report RUN_DIR

Everything printed is derived from `RUN_DIR/attempts.jsonl` and
`RUN_DIR/run.json` at print time (`author_run.followups` re-derives each
refusal's fate from the recorded rounds), so the report can be re-run on any
record and never disagrees with it.

Contract
--------
Assumes: a run directory `author_run` wrote.
Establishes: a text report on stdout; nothing is written.
Illegal after: a figure the report prints that the record cannot re-derive.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path
from typing import Any, TextIO, assert_never

from .author_check import Refusal, refusal_key
from .author_run import (
    AttemptOutcome,
    Followup,
    FollowupStatus,
    RealGameVerdict,
    followups,
)


def load(run_dir: Path) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    meta: dict[str, Any] = json.loads((run_dir / "run.json").read_text(encoding="utf-8"))
    path = run_dir / "attempts.jsonl"
    attempts = (
        [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
        if path.exists()
        else []
    )
    return meta, attempts


def outcome_words(outcome: AttemptOutcome) -> str:
    """How the table names an outcome."""
    if outcome is AttemptOutcome.GREEN:
        return "green"
    if outcome is AttemptOutcome.ROUND_LIMIT:
        return "limit"
    if outcome is AttemptOutcome.GAVE_UP:
        return "gave up"
    if outcome is AttemptOutcome.CHECKER_FAILED:
        return "CHECKER FAILED"
    if outcome is AttemptOutcome.PROVIDER_ERROR:
        return "provider error"
    if outcome is AttemptOutcome.STOPPED_BY_CEILING:
        return "stopped (ceiling)"
    if outcome is AttemptOutcome.HARNESS_ERROR:
        return "HARNESS ERROR"
    assert_never(outcome)


def real_game_words(verdict: RealGameVerdict) -> str:
    """How the table names a real-game verdict. Every verdict but
    `AGREES_ON_FACTS` and `RULES_READ_PENDING` is a failure of the run."""
    if verdict is RealGameVerdict.AGREES_ON_FACTS:
        return "agrees on facts"
    if verdict is RealGameVerdict.DIVERGES:
        return "FAIL: diverges"
    if verdict is RealGameVerdict.DOES_NOT_PLAY:
        return "FAIL: does not play"
    if verdict is RealGameVerdict.RULES_READ_PENDING:
        return "rules read pending"
    if verdict is RealGameVerdict.NOT_COMPARABLE:
        return "not comparable"
    if verdict is RealGameVerdict.NOT_REACHED:
        return "-"
    assert_never(verdict)


def table(attempts: Sequence[Mapping[str, Any]]) -> list[str]:
    header = (
        "game", "set", "model", "#", "outcome", "1st green", "fix rounds",
        "could not act on", "real game", "cost $",
    )
    rows: list[tuple[str, ...]] = [header]
    for a in attempts:
        summary = a["summary"]
        fix = summary["fix_rounds_to_green"]
        rows.append(
            (
                a["game"],
                a["held_out"],
                a["model_ref"],
                str(a["attempt"]),
                outcome_words(AttemptOutcome(a["outcome"])),
                "yes" if summary["first_draft_green"] else "no",
                "-" if fix is None else str(fix),
                str(summary["could_not_act_on"]),
                real_game_words(RealGameVerdict(a["real_game"]["verdict"])),
                f"{a['usage'].get('cost_usd', 0.0):.2f}",
            )
        )
    widths = [max(len(r[i]) for r in rows) for i in range(len(header))]
    return ["  ".join(cell.ljust(w) for cell, w in zip(r, widths)).rstrip() for r in rows]


def _excerpt(draft: str, line: int | None, around: int = 2) -> str:
    if line is None:
        return "(no line)"
    lines = draft.splitlines()
    lo, hi = max(1, line - around), min(len(lines), line + around)
    return "\n".join(
        f"{'>' if n == line else ' '} {n:4d} | {lines[n - 1]}" for n in range(lo, hi + 1)
    )


def stands(attempts: Sequence[Mapping[str, Any]]) -> list[tuple[Mapping[str, Any], Followup]]:
    found: list[tuple[Mapping[str, Any], Followup]] = []
    for a in attempts:
        for f in followups(a["rounds"]):
            if f.status is FollowupStatus.STANDS:
                found.append((a, f))
    return found


def filing(a: Mapping[str, Any], f: Followup, meta: Mapping[str, Any]) -> list[str]:
    """One refusal the model could not act on, as an issue's draft."""
    drafts = {r["round"]: r["draft"] for r in a["rounds"] if r.get("draft") is not None}
    r = f.refusal
    where = f"{r.file}:{r.line}:{r.column}" if r.line is not None else "(unlocated)"
    offers = f"; offered {', '.join(r.near_misses)}" if r.near_misses else ""
    return [
        f"Title: a model writing {a['game']} is told `{r.message}` and its next edit leaves it standing",
        "",
        "## Summary",
        "",
        f"The authoring benchmark (#1053), run {meta.get('git_head', '?')[:10]}: "
        f"{a['model']} writing {a['game']} ({a['held_out']}) was refused at "
        f"draft {f.round} with the message below, and its next draft (draft "
        f"{f.next_round}) left the line unchanged and met the same refusal "
        f"there. Kind and reachability are the filer's to set after reading "
        f"the rounds.",
        "",
        "## Detail",
        "",
        f"    {where}: {r.severity}: {r.message}{offers}",
        "",
        "Draft " + str(f.round) + ":",
        "",
        _indent(_excerpt(drafts.get(f.round, ""), r.line)),
        "",
        f"Draft {f.next_round}, refused again at the same line:",
        "",
        _indent(_excerpt(drafts.get(f.next_round or 0, ""), _next_line(a, f))),
        "",
        f"Key: `{f.key}`; anchored line: `{f.anchor}`.",
        "",
        "## Provenance",
        "",
        f"Authoring benchmark run `{meta.get('run', '?')}`, attempt "
        f"{a['game']}/{a['model_ref']}/{a['attempt']}, rounds {f.round} and {f.next_round}.",
    ]


def _next_line(a: Mapping[str, Any], f: Followup) -> int | None:
    """The line the standing refusal was reported at in the next draft."""
    for r in a["rounds"]:
        if r["round"] == f.next_round and r.get("check"):
            for refusal in r["check"]["refusals"]:
                if refusal_key(Refusal.from_dict(refusal)) == f.key and refusal["line"] is not None:
                    draft = r["draft"].splitlines()
                    line = refusal["line"]
                    if 1 <= line <= len(draft) and draft[line - 1].strip() == f.anchor:
                        return int(line)
    return None


def _indent(text: str) -> str:
    return "\n".join("    " + line for line in text.splitlines())


def report(run_dir: Path, out: TextIO) -> None:
    meta, attempts = load(run_dir)
    meta.setdefault("run", run_dir.name)

    def write(line: str = "") -> None:
        print(line, file=out)

    write(f"Authoring benchmark, run {run_dir.name} (commit {meta.get('git_head', '?')})")
    write(f"checker: {' '.join(meta.get('checker', {}).get('argv', []))} "
          f"[{meta.get('checker', {}).get('form', '?')} form]")
    if meta.get("stopped"):
        write(f"RUN STOPPED: {meta['stopped']}")
    write()
    for line in table(attempts):
        write(line)
    found = stands(attempts)
    write()
    write(f"Refusals a model could not act on: {len(found)}")
    for index, (a, f) in enumerate(found, start=1):
        write()
        write(f"--- {index} " + "-" * 60)
        for line in filing(a, f, meta):
            write(line)
    others = _status_counts(f for a in attempts for f in followups(a["rounds"]))
    write()
    write("Every refusal's fate at the next draft: " + ", ".join(f"{k} {v}" for k, v in others.items()))
    gaps = [a for a in attempts if a["outcome"] == AttemptOutcome.GAVE_UP.value]
    if gaps:
        write()
        write("Rules a model said the language cannot express (language-gap candidates):")
        for a in gaps:
            write(f"  {a['game']}/{a['model_ref']}/{a['attempt']}: {a['detail']}")
    crashes = [a for a in attempts if a["outcome"] == AttemptOutcome.CHECKER_FAILED.value]
    if crashes:
        write()
        write("Checker failures (each draft is a witness):")
        for a in crashes:
            write(f"  {a['game']}/{a['model_ref']}/{a['attempt']} round {len(a['rounds'])}: {a['detail'][:300]}")


def _status_counts(items: Iterable[Followup]) -> dict[str, int]:
    counts = {status.value: 0 for status in FollowupStatus}
    for f in items:
        counts[f.status.value] += 1
    return counts


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="print an authoring benchmark run's report")
    parser.add_argument("run_dir")
    args = parser.parse_args(argv)
    report(Path(args.run_dir), sys.stdout)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
