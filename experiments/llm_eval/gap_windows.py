"""Enumerate every Cheat challenge window in an archive, as the stimulus bank
`cheat_gap` scores.

A window is one `call_cheat`/`allow` decision: the observer, the standing
claim, and the ground truth the referee's own recorded card facts settle. This
module produces the population `gap_posterior.py` subsamples and
`verify_cheat_gap.py` scores against — nothing here computes a posterior or a
rate, only what a window IS.

    python -m experiments.llm_eval.gap_windows \\
        --dir experiments/llm_eval/results_cheat_gap/transcripts \\
        --out windows.jsonl

Provenance first. A transcript's `history` is a sequence of action ids,
meaningful only against the `.cardlang` source that assigned them
(`referee.game_digest`), so every record is replayed with its own recorded
digest as `expected_digest` before anything is read from it — a record
carrying no `game_digest` at all is refused the same way, since there is
nothing to check the loaded game's source against. Both refusals raise
`referee.ProvenanceError` naming the matchup, and are fatal: a transcript this
module cannot trust the action ids of is not a transcript it can enumerate
windows from.

Every other fact — the observer's action, the claim, the ground-truth lie
flag — is recomputed from the replayed view and the recorded action id rather
than read from the transcript's own `facts` or `action` fields: the same
independent-recomputation stance `verify.py --deep` takes, and for the same
reason. A transcript's `facts` are whatever the code that wrote it computed,
this is the code that scores it, and the digest authenticates the game source
and nothing written beside a decision. `metrics.decision_facts` is reused
rather than reimplemented (it is the one place `provably_false` and
`provably_false_hand_only` are already wired to an information state), and
`metrics.reconstruct_plays` is reused for the ground-truth lie flag over the
replay-derived decisions, so a play's cards are read once, by the module that
owns grouping decisions into plays.

`r0`, the declared prior, is read from an optional `<matchup>.treatment.json`
sidecar beside the transcript — the same file `promote.py` carries across and
`run_eval.treatment` writes, holding the matchup's roster verbatim. Every rule
roster entry in the corpus this module is written against shares one
`bluff_prob` per matchup (`config.yaml`), so this module does not resolve
which physical seat a roster entry rotated to: it takes the single `bluff_prob`
value common to every `kind: rule` entry in the sidecar. A roster with more
than one such value, or no sidecar at all, leaves `r0` as `null` for every
rule claimant in that matchup rather than guess — a designed limitation, not a
bug: resolving seat rotation exactly needs `run_eval`'s own seating function,
which this module does not import.

Contract
--------
Assumes: transcripts under `--dir` are `GameRecord.as_dict()` JSONL, each
carrying `game_digest`; the game they name is a four-player Cheat over
`docs/games/cheat.cardlang`, with a challenge window rendering legal moves as
`["allow", "call_cheat"]`.
Establishes: one JSONL record per challenge window, in deterministic order,
whose `infostate` field is the observer's entitled view at that window — the
input `gap_posterior.py` samples from without touching the engine again.
Illegal after: computing a rate from these records. This module counts and
classifies; it estimates nothing.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from . import infostate as istate
from .metrics import Play, decision_facts, iter_jsonl, reconstruct_plays
from .referee import ProvenanceError, load_game, replay_views


@dataclass(frozen=True)
class WindowRecord:
    """One challenge window: the standing claim, the observer's decision, and
    the ground truth. See the module docstring for how each field is derived."""

    matchup: str
    game_index: int
    seed: int
    step: int
    observer: int
    observer_agent: str
    claimant: int
    claimant_agent: str
    claim_rank: str
    claim_count: int
    window_position: int
    action: str
    lie: bool
    forced_lie: bool
    r1_widened: bool
    r1_hand_only: bool
    r0: float | None
    depth: int
    truncated: bool
    infostate: str


def _transcripts(root: Path) -> list[Path]:
    """One path per matchup stem, preferring an uncompressed file when both
    exist — the same dedup `verify._transcripts` uses, kept local so this
    module's own import list stays `referee`, `infostate`, `metrics`."""
    by_stem: dict[str, Path] = {}
    for f in sorted(root.glob("*.jsonl.gz")):
        by_stem[f.name[: -len(".jsonl.gz")]] = f
    for f in sorted(root.glob("*.jsonl")):
        by_stem[f.stem] = f
    return [by_stem[k] for k in sorted(by_stem)]


def _rule_bluff_prob(root: Path, stem: str) -> float | None:
    """The single `bluff_prob` every `kind: rule` roster entry in this
    matchup's sidecar shares, or `None` when there is no sidecar, no rule
    entry, or the roster disagrees with itself."""
    sidecar = root / f"{stem}.treatment.json"
    if not sidecar.is_file():
        return None
    treatment = json.loads(sidecar.read_text(encoding="utf-8"))
    values = {
        float(spec.get("bluff_prob", 0.0))
        for spec in treatment.get("agents", [])
        if spec.get("kind") == "rule"
    }
    return values.pop() if len(values) == 1 else None


def _windows_of(
    record: dict[str, Any], root: Path, matchup: str, r0: float | None
) -> list[WindowRecord]:
    """Every challenge window in one game record, replayed and reclassified."""
    if "game_digest" not in record:
        raise ProvenanceError(
            f"{matchup}: game_index={record.get('game_index')} seed="
            f"{record.get('seed')} carries no game_digest — refusing to "
            f"replay a transcript this module cannot pin to the game source "
            f"its action ids were assigned against"
        )
    game = load_game(record["game"])
    try:
        views = replay_views(
            game, record["seed"], record["history"], expected_digest=record["game_digest"]
        )
    except ProvenanceError as e:
        raise ProvenanceError(f"{matchup}: {e}") from e

    # Every fact below comes from the REPLAY — the view the engine renders and
    # the action id the transcript recorded — never from the transcript's own
    # `facts` or `action` fields. Those were written by the code that ran the
    # game, and this is the code that scores it; the digest authenticates the
    # game source, not what that code wrote beside each decision.
    decisions: list[dict[str, Any]] = []
    for step, (view, action_id) in enumerate(zip(views, record["history"], strict=True)):
        if action_id not in view.legal_actions:
            raise ValueError(
                f"{matchup}: game_index={record['game_index']} step={step} "
                f"recorded action id {action_id}, which the replayed view does "
                f"not offer — the transcript and the game disagree"
            )
        chosen = view.legal_strings[view.legal_actions.index(action_id)]
        decisions.append(
            {
                "step": step,
                "player": view.player,
                "action": chosen,
                "facts": decision_facts(view, chosen, "cheat"),
            }
        )
    plays: list[Play] = reconstruct_plays(decisions)
    flat_windows: list[tuple[Play, int]] = [
        (play, position) for play in plays for position in range(len(play.windows))
    ]
    window_cursor = iter(flat_windows)

    seats: dict[str, str] = record["seats"]
    out: list[WindowRecord] = []
    for step, (view, decision) in enumerate(zip(views, decisions, strict=True)):
        if istate.decision_kind(view.legal_strings) != "window":
            continue
        facts = decision["facts"]
        claimant = facts["claimant"]
        if claimant is None:
            raise ValueError(
                f"{matchup}: game_index={record['game_index']} step={step} is a "
                f"window with no claimant — the transcript does not match "
                f"Cheat's move structure"
            )
        found = next(window_cursor, None)
        if found is None:
            raise ValueError(
                f"{matchup}: game_index={record['game_index']} step={step} is a "
                f"window the replay found but `reconstruct_plays` did not — "
                f"the two disagree on the game's move structure"
            )
        play, position = found
        out.append(
            WindowRecord(
                matchup=matchup,
                game_index=record["game_index"],
                seed=record["seed"],
                step=step,
                observer=view.player,
                observer_agent=seats[str(view.player)],
                claimant=claimant,
                claimant_agent=seats[str(claimant)],
                claim_rank=facts["claim_rank"],
                claim_count=facts["claim_count"],
                window_position=position,
                action=decision["action"],
                lie=play.lied,
                forced_lie=play.forced,
                r1_widened=facts["provably_false"],
                r1_hand_only=facts["provably_false_hand_only"],
                r0=r0 if seats[str(claimant)] == "rule" else None,
                depth=step,
                truncated=record["truncated"],
                infostate=view.infostate,
            )
        )
    return out


def enumerate_windows(root: Path, matchups: list[str] | None) -> list[WindowRecord]:
    """Every window across every selected matchup, in deterministic order."""
    stems = _transcripts(root)
    windows: list[WindowRecord] = []
    for path in stems:
        stem = path.name
        for suffix in (".jsonl.gz", ".jsonl"):
            if stem.endswith(suffix):
                stem = stem[: -len(suffix)]
                break
        if matchups is not None and stem not in matchups:
            continue
        r0 = _rule_bluff_prob(root, stem)
        for record in iter_jsonl(str(path)):
            matchup = record.get("matchup", stem)
            windows.extend(_windows_of(record, root, matchup, r0))
    return windows


def _summarize(windows: list[WindowRecord]) -> None:
    by_matchup: dict[str, list[WindowRecord]] = {}
    for w in windows:
        by_matchup.setdefault(w.matchup, []).append(w)
    for matchup in sorted(by_matchup):
        rows = by_matchup[matchup]
        games = len({(r.game_index, r.seed) for r in rows})
        by_agent: Counter[str] = Counter(r.observer_agent for r in rows)
        fires = sum(1 for r in rows if r.r1_widened)
        abstains = len(rows) - fires
        print(f"\n=== {matchup} ===")
        print(f"  games                {games}")
        print(f"  windows              {len(rows)}")
        for agent in sorted(by_agent):
            print(f"  windows[{agent}]{'':<{max(1, 15 - len(agent))}}{by_agent[agent]} / {len(rows)}")
        print(f"  r1_fires             {fires} / {len(rows)}")
        print(f"  r1_abstains          {abstains} / {len(rows)}")
    print(f"\nTOTAL windows: {len(windows)} across {len(by_matchup)} matchup(s)")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__ and __doc__.splitlines()[0])
    ap.add_argument("--dir", required=True, help="transcripts directory")
    ap.add_argument("--out", required=True, help="output windows JSONL path")
    ap.add_argument(
        "--matchup",
        action="append",
        default=None,
        help="restrict to these matchup stems (repeatable; default: all)",
    )
    args = ap.parse_args(argv)

    root = Path(args.dir)
    windows = enumerate_windows(root, args.matchup)
    windows.sort(key=lambda w: (w.matchup, w.game_index, w.seed, w.step))

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as handle:
        for w in windows:
            handle.write(json.dumps(asdict(w), ensure_ascii=False) + "\n")

    _summarize(windows)
    print(f"\nwrote {len(windows)} window(s) to {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
