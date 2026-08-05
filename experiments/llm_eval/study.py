"""Rebuild the STUDY-level summary and figure from the curated archive.

    python -m experiments.llm_eval.study

Two tiers of summary, because they answer different questions (`layout.py`):

- A RUN summary, `results/runs/<stamp>/summary.json`, records one invocation:
  what it spent, how far it got, why it stopped. Written by `run_eval`, never
  overwritten.
- The STUDY summary, `results/summary.json`, is the published result across every
  transcript in the archive. It is DERIVED, and regenerating it is this module.

Before per-run directories existed there was only the second path, and it was
produced as a side effect of whichever invocation ran last — so the committed
"study" summary was really a snapshot of one run, and after a partial 2-game run
it said the study was two games. Deriving it from the archive instead means it
cannot disagree with the transcripts it claims to summarize, and it can be
rebuilt by anyone holding the repo.

This module is CHEAT's study and says so in its output (`"study":
"cheat_llm_eval"`). It has no per-game seam — `aggregate` is called with no
`action_verbs` and no `chip_delta` — so pointing it at another game's archive
would emit a block labelled as the Cheat study, carrying neither that game's
action rates nor its chip delta, and every Cheat rate null. `main` refuses a
non-default `--results` for that reason; a second game's numbers come from
`verify.py --game`, which does have the seam.

Contract
--------
Assumes: `results/transcripts/` holds the transcripts behind the published
numbers, one file per matchup.
Establishes: `results/summary.json` and `results/figure.png`, both a pure
function of that directory.
Illegal after: treating a run's summary as the study's, or vice versa.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from . import layout
from .metrics import aggregate
from .verify import DEFAULT_RESULTS, _load, _stem, _transcripts


def study_summary(archive: Path) -> dict[str, Any]:
    """Aggregate every archived matchup into one summary payload.

    Deliberately carries no `run_totals`: spend is a property of an invocation,
    and summing it across an archive assembled over many invocations would invent
    a number no single run ever reported. Per-run spend lives in the run
    summaries; `verify.py` reads token counts straight off the transcripts.
    """
    blocks: list[dict[str, Any]] = []
    for path in _transcripts(archive):
        records = _load(path)
        if not records:
            continue
        block = aggregate(records)
        block["matchup"] = _stem(path)
        block["n_completed"] = len(records)
        block["transcript"] = str(path)
        blocks.append(block)
    if not blocks:
        raise SystemExit(f"no transcripts under {archive} — nothing to summarize")
    return {
        "study": "cheat_llm_eval",
        "source": str(archive),
        "matchups": blocks,
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__ and __doc__.splitlines()[0])
    ap.add_argument("--results", default=str(DEFAULT_RESULTS))
    ap.add_argument(
        "--figure", action="store_true", help="also re-render results/figure.png"
    )
    args = ap.parse_args(argv)

    results = Path(args.results)
    if results.resolve() != DEFAULT_RESULTS.resolve():
        raise SystemExit(
            f"{results} is not the Cheat archive, and this module is Cheat's "
            f"study: it labels its output `cheat_llm_eval` and folds without "
            f"any game's action verbs or chip delta. For another game's "
            f"numbers use\n"
            f"  python -m experiments.llm_eval.verify --game <short_name> "
            f"--dir {results / layout.ARCHIVE}"
        )
    summary = study_summary(layout.archive_dir(results))
    out = results / "summary.json"
    out.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"wrote {out} from {len(summary['matchups'])} archived matchup(s)")
    for block in summary["matchups"]:
        print(f"  {block['matchup']:38} N={block['n_completed']}")

    if args.figure:
        from .figure import render

        print(f"wrote {render(summary, results / 'figure.png')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
