"""CLI entry point: run matchups from a config, write transcripts and a summary.

    python -m experiments.llm_eval.run_eval --config experiments/llm_eval/config.yaml

Budget discipline (spec §6): a hard token/dollar cap lives in the config, the
runner stops cleanly when a matchup would cross it, and the partial N is
reported rather than the intended one. Cost is checked between games; a
per-game `max_decisions` cap bounds how much a single game can spend, since a
full Cheat episode is long enough that one game can be a material fraction of a
budget.

Each invocation writes into its own dated directory,
`results/runs/<UTC timestamp>/`, holding that run's `summary.json`, transcripts
and figure. Nothing is ever overwritten; see `layout.py` for why the curated
archive is a separate tier.

Contract
--------
Assumes: the config's matchups name models defined in the same config.
Establishes: `<run_dir>/transcripts/<matchup>.jsonl` and `<run_dir>/summary.json`,
both of which record the ACTUAL N and the reason a run stopped short.
Illegal after: reporting an intended N anywhere; writing a run's output outside
its own run directory.
"""

from __future__ import annotations

import argparse
import json
import sys
import traceback
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from . import layout
from .agents import Agent, build_agent
from .metrics import aggregate, game_key
from .prompts import parse_response
from .providers import PRICES, Provider, Usage, make_provider
from .referee import NUM_SEEDS, GameRecord, load_game, play_game


@dataclass
class Budget:
    """A hard ceiling on a run. Zero or absent means unlimited."""

    max_input_tokens: int = 0
    max_output_tokens: int = 0
    max_cost_usd: float = 0.0

    def exceeded(self, registry: dict[str, Provider]) -> str | None:
        """The name of the first cap crossed by the run's COMBINED usage, or None.

        Summed across every provider in the registry, not checked per model. Per
        model, a config naming three models had an effective ceiling of three
        times what its author wrote down: the frontier provider could reach the
        cap, and the run would carry on into a matchup using the cheap provider
        whose own counter started at zero. `max_cost_usd` is dollars, which add
        across models; the token caps are counts, which do too.
        """
        totals = Usage()
        cost = 0.0
        for provider in registry.values():
            totals.input_tokens += provider.usage.input_tokens
            totals.output_tokens += provider.usage.output_tokens
            cost += provider.usage.cost(provider.model)
        if self.max_input_tokens and totals.input_tokens >= self.max_input_tokens:
            return "max_input_tokens"
        if self.max_output_tokens and totals.output_tokens >= self.max_output_tokens:
            return "max_output_tokens"
        if self.max_cost_usd and cost >= self.max_cost_usd:
            return "max_cost_usd"
        return None


def seat_plan(
    game_index: int, num_players: int, rotate: bool, balanced: bool
) -> tuple[int, int]:
    """Which deal to draw and which seat the roster's first entry takes, as
    `(seed_offset, focus)`.

    Two schemes, because the obvious one has a confound that only bites when the
    deal matters more than the play.

    `balanced=False` — the original. `seed_offset` and `focus` are both
    `game_index`, so THE SEAT IS A FUNCTION OF THE SEED. That is fine when a
    seat's advantage comes from position (Cheat, where the deal is 13 cards and
    an episode is hundreds of decisions), and wrong when it comes from the cards
    (Kuhn, where the deal is one card and the hand is one decision): the
    adapter's seed-to-deal map is not balanced across seed parities, so seat
    rotation hands one agent systematically better cards. Measured on a real
    300-game run before this existed: the model held a King 112 times to the
    baseline's 97 and "beat" an opponent that is provably unbeatable.

    `balanced=True` — every seed is played in EVERY seating, `num_players`
    games per deal. The card advantage then cancels by construction rather than
    by averaging, which is what makes a chips-per-hand comparison between two
    agents mean anything. `n` is games, not deals, so a matchup of `n` games
    covers `n // num_players` deals.
    """
    if not rotate:
        return game_index, 0
    if balanced:
        return game_index // num_players, game_index % num_players
    return game_index, game_index % num_players


def _build_seats(
    roster: list[dict[str, Any]],
    num_players: int,
    focus: int,
    seed: int,
    providers: dict[str, Provider],
    game: str = "cheat",
) -> dict[int, Agent]:
    """Assign the roster to seats from the focus seat, filling in order around
    the table. Which seat is the focus is `seat_plan`'s decision, not this
    function's — the two schemes differ only there."""
    if len(roster) != num_players:
        raise ValueError(
            f"matchup roster has {len(roster)} agents but the game seats "
            f"{num_players}"
        )
    seats: dict[int, Agent] = {}
    for offset, spec in enumerate(roster):
        seat = (focus + offset) % num_players
        provider = providers.get(spec["model"]) if spec.get("model") else None
        # Distinct per-seat seeds so two Random seats do not play identically.
        seats[seat] = build_agent(
            spec, seed=seed * 100 + seat, provider=provider, game=game
        )
    return seats


def validate_model_refs(config: dict[str, Any], matchups: list[dict[str, Any]]) -> None:
    """Pre-flight: every model an agent names is defined, and every real one is
    priced. Constructs NOTHING — a typo dies here, before any credential is
    needed, and an offline-only run never touches the SDK."""
    for matchup in matchups:
        for spec in matchup["agents"]:
            name = spec.get("model")
            if not name:
                continue
            if name not in config.get("models", {}):
                raise ValueError(
                    f"matchup {matchup['name']!r} references model {name!r}, "
                    f"which is not defined under `models:` in the config"
                )
            model = config["models"][name]
            if model.get("kind", "anthropic") == "anthropic" and model["model"] not in PRICES:
                raise ValueError(
                    f"model {name!r} names {model['model']!r}, which has no "
                    f"published price — its cost would report as $0.00"
                )


def ensure_provider(
    config: dict[str, Any], name: str, registry: dict[str, Provider]
) -> Provider:
    """The shared provider for `name`, constructed on FIRST USE and memoized.

    Two properties ride on this, and they pull in opposite directions:

    - One instance per model for the WHOLE run, because `token_budget` is a
      budget for the run. Per-matchup providers would let a four-matchup config
      spend four times the ceiling its author wrote down.
    - Lazy, because constructing an `AnthropicProvider` imports the SDK and
      resolves a credential. Building the registry eagerly for every selected
      matchup made the offline matchup — the no-API-key acceptance path — fail
      whenever an LLM matchup was merely *also* selected, which is exactly what
      the bare `run_eval` command does.
    """
    if name not in registry:
        registry[name] = make_provider(config["models"][name])
    return registry[name]


def treatment(config: dict[str, Any], matchup: dict[str, Any]) -> dict[str, Any]:
    """Everything that must not change between the games of one matchup.

    The roster verbatim (arm, render flag, model reference, `bluff_prob`,
    `challenge_prob`), the model definitions those references resolve to, and the
    knobs that shape an episode. Recorded beside the transcript so a resume can
    prove it is continuing the same experiment rather than appending a second one.

    Deliberately NOT the whole config: `n`, `resume_from` and `results_dir` change
    legitimately between invocations of the same experiment, and including them
    would make every resume fail.
    """
    used = sorted({spec["model"] for spec in matchup["agents"] if spec.get("model")})
    return {
        "game": config.get("game", "cardlang_cheat"),
        "agents": matchup["agents"],
        "rotate": bool(matchup.get("rotate", True)),
        # Which seating scheme produced these games. It changes WHICH DEALS the
        # matchup saw and in which seatings, so appending games from the other
        # scheme to the same transcript would mix two designs into one N.
        "balanced_seating": bool(config.get("balanced_seating", False)),
        "max_decisions": int(config.get("max_decisions", 0)),
        "seed_start": int(config.get("seeds", {}).get("start", 0)),
        "models": {m: config["models"][m] for m in used},
    }


def read_treatment(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    loaded: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    return loaded


def run_matchup(
    config: dict[str, Any],
    matchup: dict[str, Any],
    out_dir: Path,
    registry: dict[str, Provider],
    limit: int | None = None,
    allow_overwrite: bool = False,
) -> dict[str, Any]:
    """Run one matchup end to end and return its summary block.

    `registry` is the run-wide provider cache, mutated in place: this matchup
    builds providers only for the models its OWN roster names, so an offline
    matchup selected alongside an LLM one needs no credential. Usage totals in
    the returned block are this matchup's DELTA, alongside the running total the
    budget is checked against.
    """
    name = matchup["name"]
    roster = matchup["agents"]
    n = int(matchup["n"]) if limit is None else min(int(matchup["n"]), limit)
    seed_start = int(config.get("seeds", {}).get("start", 0))
    # `resume_from: k` runs games k..n-1 and APPENDS to the existing transcript,
    # for finishing a matchup that died partway (a budget cap, a dropped
    # connection). Game index and seed are unchanged from what a full run would
    # have used, so the resumed games are bit-identical to the ones that were
    # missed — including seat rotation, which is a function of the game index.
    resume = int(matchup.get("resume_from", 0))
    if not 0 <= resume <= n:
        raise ValueError(f"resume_from {resume} is outside 0..{n} for {name!r}")
    game = load_game(config.get("game", "cardlang_cheat"))
    num_players = game.num_players()
    # How far the seed cursor actually travels, which is `n` under the original
    # scheme and `n / num_players` under balanced seating. Derived from
    # `seat_plan` rather than restated, so the guard cannot disagree with the
    # loop it is guarding.
    last_offset = (
        max(
            seat_plan(
                i,
                num_players,
                bool(matchup.get("rotate", True)),
                bool(config.get("balanced_seating", False)),
            )[0]
            for i in range(n)
        )
        if n
        else 0
    )
    if seed_start + last_offset >= NUM_SEEDS:
        raise ValueError(
            f"matchup {name!r} needs seeds {seed_start}..{seed_start + last_offset}, "
            f"but the adapter only addresses {NUM_SEEDS} deals — reduce n or the start"
        )
    # One name, derived once, used for both the agents' rules text and the
    # metrics. Deriving it from the LOADED game rather than from the config key
    # means a config naming one game cannot show the model another's rules.
    game_name = game_key(game.get_type().short_name)
    used = sorted({spec["model"] for spec in roster if spec.get("model")})
    # `m` deliberately, not `n`: `n` is the game count in this scope, and a
    # comprehension that reuses it reads like a shadow even though it is not one.
    providers = {m: ensure_provider(config, m, registry) for m in used}
    budget = Budget(**config.get("token_budget", {}))
    before = {
        m: (providers[m].usage.input_tokens, providers[m].usage.output_tokens)
        for m in used
    }

    transcripts = out_dir / "transcripts"
    transcripts.mkdir(parents=True, exist_ok=True)
    path = transcripts / f"{name}.jsonl"
    treatment_path = transcripts / f"{name}.treatment.json"

    existing: list[dict[str, Any]] = []
    if resume:
        # Refuse to append onto anything but the exact prefix this resume
        # continues. Appending to a mismatched file would silently duplicate or
        # interleave games, and the resulting transcript would still look valid.
        if not path.exists():
            archive = path.with_suffix(".jsonl.gz")
            extra = (
                f" The gzipped archive {archive.name} IS present; resume appends to "
                f"an uncompressed transcript, so gunzip it first (and re-compress "
                f"afterwards) if you mean to extend that run."
                if archive.exists()
                else ""
            )
            raise ValueError(
                f"resume_from={resume} but {path} does not exist — nothing to "
                f"resume.{extra}"
            )
        with path.open(encoding="utf-8") as fh:
            existing = [json.loads(line) for line in fh if line.strip()]
        # Derived from the SAME scheme the run loop uses, not from a bare range:
        # under balanced seating a seed appears once per seating, so an
        # ascending-and-distinct expectation would refuse every legitimate
        # resume while looking like a data-integrity check.
        balanced = bool(config.get("balanced_seating", False))
        rotating = bool(matchup.get("rotate", True))
        want = [
            seed_start + seat_plan(i, num_players, rotating, balanced)[0]
            for i in range(resume)
        ]
        got = [r["seed"] for r in existing]
        if got != want:
            raise ValueError(
                f"cannot resume {name!r} at game {resume}: {path} holds seeds "
                f"{got}, expected exactly {want}. Delete it to start over, or "
                f"set resume_from to {len(existing)}."
            )
        # Seeds agreeing is not the same as the EXPERIMENT agreeing. Change the
        # arm, the model, the rendering flag or a rule agent's `bluff_prob`
        # between invocations and the same seed sequence still passes the check
        # above, after which `aggregate(existing + records)` reports two
        # different treatments as one matchup — a silently mixed arm, which is
        # the worst outcome this harness has, because the number still looks fine.
        want_treat = treatment(config, matchup)
        got_treat = read_treatment(treatment_path)
        if got_treat is None:
            raise ValueError(
                f"cannot resume {name!r}: {treatment_path.name} is missing, so "
                f"there is no record of what treatment the existing games ran "
                f"under and no way to confirm this invocation matches. Start a "
                f"fresh run rather than appending blind."
            )
        if got_treat != want_treat:
            differing = sorted(
                k
                for k in set(got_treat) | set(want_treat)
                if got_treat.get(k) != want_treat.get(k)
            )
            raise ValueError(
                f"cannot resume {name!r}: the configuration changed since the "
                f"existing games were played. Differing: {differing}\n"
                f"  recorded: { {k: got_treat.get(k) for k in differing} }\n"
                f"  now:      { {k: want_treat.get(k) for k in differing} }\n"
                f"Appending would mix two treatments into one matchup."
            )
    elif path.exists() and path.stat().st_size and not allow_overwrite:
        # `w` would truncate it. Reachable only via `--run-dir` naming an existing
        # run, and the README's own resume command omits `--matchup` — so the
        # default selection would have silently destroyed every earlier
        # non-resuming transcript in that directory before reaching the one being
        # resumed. Transcripts hold real model responses and are NOT regenerable.
        raise ValueError(
            f"{path} already holds {sum(1 for _ in path.open(encoding='utf-8'))} "
            f"game(s) and this matchup is not resuming, so it would be "
            f"overwritten. Transcripts are not regenerable — they hold real "
            f"model responses. Use a fresh run directory (omit --run-dir), set "
            f"`resume_from`, or move the file aside deliberately."
        )

    # Written before the first game, so the record of what treatment produced a
    # transcript exists even if the run dies on game one.
    treatment_path.write_text(
        json.dumps(treatment(config, matchup), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    records: list[dict[str, Any]] = []
    stopped: str | None = None
    aborted: str | None = None
    with path.open("a" if resume else "w", encoding="utf-8") as handle:
        for i in range(resume, n):
            # Against the WHOLE registry: the cap is a ceiling for the run, so it
            # cannot be evaluated one provider at a time.
            reason = budget.exceeded(registry)
            if reason is not None:
                stopped = f"{reason} reached across the run's models"
                break

            offset, focus = seat_plan(
                i,
                num_players,
                bool(matchup.get("rotate", True)),
                bool(config.get("balanced_seating", False)),
            )
            seed = seed_start + offset
            seats = _build_seats(
                roster, num_players, focus, seed, providers, game_name
            )
            try:
                record: GameRecord = play_game(
                    game,
                    seats,
                    seed=seed,
                    matchup=name,
                    game_index=i,
                    max_decisions=int(config.get("max_decisions", 0)),
                    store_prompts=bool(config.get("store_prompts", False)),
                    store_infostates=bool(config.get("store_infostates", False)),
                )
            except Exception as exc:  # noqa: BLE001 — see below
                # A game that dies must not take the COMPLETED games' derived
                # numbers with it. Transcripts already flush per game, so the
                # raw data always survived; what an uncaught raise destroyed was
                # this matchup's summary block, and with it the aggregate for
                # every game that had already finished.
                #
                # Observed for real: a `400 — you have reached your specified API
                # usage limits` on game 9 of 10 discarded the summary for the
                # eight that had succeeded. Rebuilding from the transcript is
                # possible (`aggregate(iter_jsonl(path))`) but nobody should have
                # to know that after a multi-hour run.
                #
                # Deliberately broad: the point is that NOTHING gets past here
                # without the partial summary being written. The traceback is
                # re-printed and the caller exits non-zero, so nothing is hidden.
                aborted = f"{type(exc).__name__}: {exc}"
                print(
                    f"\n[{name}] ABORTED on game {i + 1}/{n} (seed {seed}) — "
                    f"writing the partial summary for the {len(records)} completed "
                    f"game(s) before exiting:\n",
                    file=sys.stderr,
                )
                traceback.print_exc()
                break
            as_dict = record.as_dict()
            handle.write(json.dumps(as_dict, ensure_ascii=False) + "\n")
            handle.flush()
            records.append(as_dict)
            print(
                f"[{name}] game {i + 1}/{n} seed={seed} "
                f"decisions={record.num_decisions} "
                f"{'TRUNCATED' if record.truncated else f'returns={record.returns}'} "
                f"({record.wall_seconds}s)"
            )

    summary = aggregate(existing + records, game_name)
    summary["matchup"] = name
    summary["n_requested"] = int(matchup["n"])
    summary["n_completed"] = len(existing) + len(records)
    summary["resumed_from"] = resume or None
    summary["games_this_invocation"] = len(records)
    summary["stopped_early"] = stopped
    # Set when a game raised. The caller stops the whole run on this: if the
    # cause is a dead credential or an exhausted budget, every later matchup
    # would fail the same way, slower.
    summary["aborted"] = aborted
    summary["transcript"] = str(path)
    summary["usage"] = {
        model_name: {
            **_delta(providers[model_name], before[model_name]),
            "model": providers[model_name].model,
            "params": _jsonable(providers[model_name].params),
            "run_total": providers[model_name].usage.as_dict(providers[model_name].model),
            # Dollars per game, the figure a budget decision is actually made
            # on. Denominated in games COMPLETED, never the intended N.
            "cost_usd_per_game": round(
                _delta(providers[model_name], before[model_name])["cost_usd"]
                / len(records),
                4,
            )
            if records
            else None,
        }
        for model_name in used
    }
    if stopped:
        print(f"[{name}] STOPPED EARLY: {stopped} — completed {len(records)}/{n} games")
    return summary


def _delta(provider: Provider, before: tuple[int, int]) -> dict[str, float | int]:
    """This matchup's share of a shared provider's usage."""
    spent = Usage(
        calls=0,
        input_tokens=provider.usage.input_tokens - before[0],
        output_tokens=provider.usage.output_tokens - before[1],
    )
    out = spent.as_dict(provider.model)
    del out["calls"]  # not tracked per matchup; `run_total` carries the count
    return out


def _jsonable(value: Any) -> Any:
    """Config params are plain YAML scalars/dicts already; this is a guard so a
    stray object can never make `summary.json` unwritable mid-run."""
    try:
        json.dumps(value)
    except TypeError:
        return repr(value)
    return value


def estimate(
    config: dict[str, Any],
    matchup: dict[str, Any],
    registry: dict[str, Provider],
    games: int,
) -> None:
    """Cost recon (spec §6): run a few games and extrapolate before committing
    to a full frontier run."""
    results_dir = Path(config.get("results_dir", "experiments/llm_eval/results")) / "estimate"
    # The only caller allowed to overwrite: cost recon is disposable scratch
    # (`results/.gitignore` ignores `estimate/`) and is expected to be re-run in
    # place, unlike a measurement transcript which is not regenerable.
    summary = run_matchup(
        config, matchup, results_dir, registry, limit=games, allow_overwrite=True
    )
    played = summary["n_completed"]
    print(f"\n=== cost estimate from {played} game(s) of {matchup['name']} ===")
    for model_name, usage in summary["usage"].items():
        if played == 0:
            continue
        per_game = usage["cost_usd"] / played
        print(
            f"  {model_name} ({usage['model']}): "
            f"${per_game:.3f}/game, "
            f"{usage['input_tokens'] // played} in + "
            f"{usage['output_tokens'] // played} out tokens/game"
        )
        for target in (20, 50, 100):
            print(f"      N={target:<4} -> ${per_game * target:.2f}")


def smoke(config: dict[str, Any], matchups: list[dict[str, Any]]) -> int:
    """One real call per configured model, before anything expensive.

    `FakeProvider` structurally cannot check that the request SHAPE is accepted:
    whether `thinking` and `output_config` are valid together as top-level
    kwargs for this model on the installed SDK, or that usage lands where the
    provider reads it. "Correct per the docs" and "verified against the
    installed SDK" are different claims, and the difference otherwise surfaces
    on call one of a run already hours deep. Costs well under a cent.
    """
    names = sorted({
        spec["model"]
        for matchup in matchups
        for spec in matchup["agents"]
        if spec.get("model")
    })
    if not names:
        print("no models referenced by the selected matchups — nothing to smoke")
        return 0
    registry: dict[str, Provider] = {}
    failures = 0
    for name in names:
        provider = ensure_provider(config, name, registry)
        print(f"\n--- {name} ({provider.model}) params={provider.params}")
        try:
            reply = provider.complete(
                'Reply with exactly this JSON and nothing else: '
                '{"action": 0, "reasoning": "smoke test"}'
            )
        except Exception as exc:  # noqa: BLE001 — the point is to report ANY failure
            failures += 1
            print(f"    FAILED: {type(exc).__name__}: {exc}")
            continue
        parsed = parse_response(reply.text, num_actions=1)
        print(f"    text        {reply.text[:120]!r}")
        print(f"    stop_reason {reply.stop_reason}")
        print(f"    tokens      {reply.input_tokens} in / {reply.output_tokens} out")
        print(f"    cost        ${provider.usage.cost(provider.model):.6f}")
        if parsed.ok:
            print("    parse       OK")
        else:
            failures += 1
            print(f"    parse       FAILED: {parsed.error}")
    print(f"\n{len(names) - failures}/{len(names)} model(s) usable")
    return 1 if failures else 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__ and __doc__.splitlines()[0])
    parser.add_argument("--config", default="experiments/llm_eval/config.yaml")
    parser.add_argument(
        "--matchup",
        action="append",
        help="run only this matchup (repeatable); default is every matchup",
    )
    parser.add_argument("--limit", type=int, default=None, help="cap N for every matchup")
    parser.add_argument(
        "--estimate",
        type=int,
        default=0,
        metavar="GAMES",
        help="cost recon: play this many games of each selected matchup and extrapolate",
    )
    parser.add_argument(
        "--smoke",
        action="store_true",
        help="make ONE real call per configured model to verify the request shape, then exit",
    )
    parser.add_argument("--figure", action="store_true", help="render the figure after the run")
    parser.add_argument(
        "--run-dir",
        default=None,
        help="write into THIS directory instead of a fresh timestamped one. "
        "Required with `resume_from`: a resume appends to a transcript an "
        "earlier invocation wrote, so it continues that run and belongs in that "
        "run's directory.",
    )
    args = parser.parse_args(argv)

    config = yaml.safe_load(Path(args.config).read_text(encoding="utf-8"))
    selected = [
        m
        for m in config["matchups"]
        if args.matchup is None or m["name"] in args.matchup
    ]
    if not selected:
        print(f"no matchup matched {args.matchup!r}", file=sys.stderr)
        return 2

    # Pre-flight, constructing nothing: a bad model reference dies here rather
    # than after the first matchup has already been played.
    try:
        validate_model_refs(config, selected)
    except ValueError as exc:
        print(exc, file=sys.stderr)
        return 2

    registry: dict[str, Provider] = {}

    if args.smoke:
        return smoke(config, selected)

    if args.estimate:
        for matchup in selected:
            estimate(config, matchup, registry, args.estimate)
        return 0

    results_dir = Path(config.get("results_dir", "experiments/llm_eval/results"))
    results_dir.mkdir(parents=True, exist_ok=True)
    # One directory per invocation, never overwritten. `summary.json` used to sit
    # at the top of `results/`, so every run clobbered the previous one's derived
    # numbers — a whole session's cost accounting had to be rebuilt by summing
    # transcripts by hand.
    if args.run_dir:
        out_dir = Path(args.run_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
    else:
        resuming = [m["name"] for m in selected if m.get("resume_from")]
        if resuming:
            # A fresh directory would leave the resume with nothing to append to,
            # and it fails only after the roster and providers are already up.
            print(
                f"matchup(s) {resuming} set `resume_from`, which appends to a "
                f"transcript an earlier invocation wrote — pass --run-dir naming "
                f"that run so the resumed games join it.",
                file=sys.stderr,
            )
            return 2
        out_dir = layout.new_run_dir(results_dir)
    summary_path = out_dir / "summary.json"
    print(f"run directory: {out_dir}")

    # Continuing a run must not erase what it already recorded. `summaries` holds
    # only THIS invocation, so writing it verbatim would drop every matchup block
    # the earlier invocation completed and report `run_totals` as the fresh
    # providers' counters — i.e. a resumed run would understate its own spend and
    # lose the matchups it is resuming alongside.
    prior: dict[str, Any] = {}
    if summary_path.exists():
        prior = json.loads(summary_path.read_text(encoding="utf-8"))
        kept = [m["matchup"] for m in prior.get("matchups", [])]
        print(f"continuing run {out_dir.name}: carrying forward {len(kept)} matchup "
              f"block(s) {kept} and their spend")

    def write_summary(done: list[dict[str, Any]]) -> None:
        # This invocation's block wins for a matchup it re-ran; every other prior
        # block is carried through untouched.
        blocks: dict[str, dict[str, Any]] = {
            m["matchup"]: m for m in prior.get("matchups", [])
        }
        for block in done:
            blocks[block["matchup"]] = block
        totals: dict[str, dict[str, Any]] = {
            name: dict(block) for name, block in prior.get("run_totals", {}).items()
        }
        for name, p in registry.items():
            fresh = p.usage.as_dict(p.model) | {"model": p.model}
            if name in totals:
                # Dollars and counts both add; the prior entry covers earlier
                # invocations into this directory, `fresh` covers this one.
                for key in ("calls", "input_tokens", "output_tokens", "cost_usd"):
                    fresh[key] = totals[name].get(key, 0) + fresh.get(key, 0)
            totals[name] = fresh
        payload = {
            "config": str(Path(args.config).resolve()),
            "game": config.get("game", "cardlang_cheat"),
            # Self-describing, so a summary lifted out of its directory still
            # says which run it belongs to.
            "run": out_dir.name,
            "run_dir": str(out_dir),
            "matchups": list(blocks.values()),
            # The run's whole spend, so a proposal figure is quoted from one
            # number rather than summed by hand across matchup blocks.
            "run_totals": totals,
        }
        summary_path.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8"
        )

    # Written after EVERY matchup, not once at the end: on a multi-hour
    # sequential run an auth error or a dropped connection in the last matchup
    # would otherwise discard the summary for every matchup that already
    # succeeded. Transcripts already flush per game; this gives the derived
    # numbers the same durability.
    summaries: list[dict[str, Any]] = []
    failed = False
    for matchup in selected:
        summary = run_matchup(config, matchup, out_dir, registry, args.limit)
        summaries.append(summary)
        write_summary(summaries)
        if summary["aborted"]:
            failed = True
            print(
                f"\nRUN ABORTED in matchup {summary['matchup']!r}: "
                f"{summary['aborted']}\n"
                f"{len(selected) - len(summaries)} later matchup(s) skipped — a "
                f"credential or budget failure would repeat on every one.",
                file=sys.stderr,
            )
            break
    print(f"\nwrote {summary_path}")

    if args.figure:
        from .figure import render

        # Rendered from the file just written, so the figure and the summary can
        # never disagree about what the run produced.
        out = render(
            json.loads(summary_path.read_text(encoding="utf-8")),
            out_dir / "figure.png",
        )
        print(f"wrote {out}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
