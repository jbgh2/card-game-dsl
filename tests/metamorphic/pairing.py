"""T1: the metamorphic pairing harness (docs/design-notes/metamorphic-suite.md).

A transform is a pure ``Game -> Game`` function over the PARSED (pre-resolve)
AST. `run_pair` parses a corpus game once, runs the untransformed tree and
the transform's output each through the SAME pipeline stages
(`cardlang.pipeline._check` — resolve -> typecheck -> expand -> deck
capacity, the one stage order every other caller uses), plays both out under
a shared seed with a deterministic chooser, and returns the two traces for
the caller to compare with `compare_traces`.

Re-running the checkers on an already-checked tree is not an option
(`resolve._instantiate_rules` splices stdlib rules into `game.rules` and is
not idempotent — metamorphic-suite.md), so each variant is single-passed from
its own PRE-CHECK tree: both sides hand `_check` a freshly parsed tree, never
a checked one, which is the invariant that matters here. What each side gets
back may well be a shared object — `parse_text` and `_check` are both memoized
(cardlang/parse.py, Contract), and the untransformed side's key is identical
to any other caller's for the same source, so it routinely hits their entry.
That is sound for the same reason the memo is (the AST is frozen and
slotted, and no pass edits in place) and it does not weaken the pairing: the
transformed side differs in the tree itself, so it always takes a fresh key.
A transformed tree that fails the pipeline is a harness bug (the transform
produced an invalid tree), not a metamorphic finding, and fails loudly via
`AssertionError` rather than being swallowed.

The chooser. Rather than pinning `PYTHONHASHSEED` (the plan's stated approach,
for cross-process golden reproducibility), this harness sorts every candidate
list by `repr(observe.render(candidate))` before picking — `render` is the
runtime's own closed-domain, deterministic candidate rendering
(`runtime/observe.py`, already used to build the "chose"/"announce" event
payloads), so the sort key needs no new vocabulary and fails loudly (via
`render`'s own `AssertionError`) on any candidate shape it does not know. The
sort is what makes the comparison order DECLARED here rather than inherited
from the order the runtime builds — a property of this harness, holding for
whatever any decision site hands over, where a pin is a property of the
environment one run is launched in. This is a STRONGER
guarantee than hashseed-pinning: two playouts under the same seed agree
regardless of `PYTHONHASHSEED`, verified empirically (four corpus games, seed
5, hashseed 0 vs. 42, byte-identical traces) rather than merely asserted.
`PYTHONHASHSEED` is therefore not pinned by this harness; this is a
deliberate, verified deviation from the plan's literal wording, recorded here
rather than silently dropped.

Termination. A greedy/deterministic policy does not make every corpus game's
line terminate in affordable steps — the OpenSpiel readiness harness
(`tests/openspiel_ready/harness.py`, `GameSpec.adapter_terminal_steps`)
already documents this for roughly a third of the corpus under ITS greedy
policy (legal[0]), and this harness's own sorted policy was measured hitting
the SAME wall (Coup, Tichu: `play_game`'s own `max_length` `RuntimeError`
after several hundred to tens of thousands of decisions). So playouts are run
under a decision CAP (`STEP_CAP`, env-tunable via
`CARDLANG_METAMORPHIC_STEPS` for a deeper local run — the plan's "env-var
knob"), well under every corpus game's declared `max_length`; a cutoff trace
compares its recorded prefix only, never the (unreached) `GameResult`. A game
whose greedy line naturally terminates before the cap compares its
`GameResult` (scores/winner/loser) too, per the plan ("the sequence of
decisions, movements, and the final GameResult").

Contract (decisions.md "Closed-domain completeness", write-time triage)
-----------------------------------------------------------------------
Assumes:      a `Game -> Game` transform that is a pure syntactic rewrite of
              the PARSED tree (pre-resolve) — see each transform module for
              its own soundness argument.
Establishes:  two `PlayoutTrace`s, directly comparable via `compare_traces`
              once the caller's `rename` hook is applied to one side.
Now illegal:  nothing downstream — this is leaf test machinery.
Verified by:  the per-transform test modules in this package; the hashseed
              claim above by the ad hoc four-game sweep recorded in this
              docstring (not itself a pinned test — a golden-independent
              in-process comparison needs no golden to rot).
"""

from __future__ import annotations

import os
import random
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from cardlang.ast import nodes as n
from cardlang.diagnostics import DiagnosticError
from cardlang.parse import parse_text
from cardlang.pipeline import _check
from cardlang.runtime.driver import GameResult, play_game
from cardlang.runtime.observe import render
from cardlang.runtime.state import Chooser
from cardlang.runtime.values import Player

# The corpus glob every transform's completeness ledger quantifies over
# (registry: this glob, mirroring `tests/test_typecheck_corpus.py`'s own
# `CORPUS` — the `.cardlang` files are the parseable corpus; the `.md` twins
# are their documentation rendering, not a second copy to check).
GAMES_DIR = Path(__file__).resolve().parent.parent.parent / "docs" / "games"
CORPUS: tuple[Path, ...] = tuple(sorted(GAMES_DIR.glob("*.cardlang")))

# CI budget vs. a deeper local run (metamorphic-suite.md, "Acceptance": "a
# small fixed seed set per game (tens of seconds), env-var knob for a longer
# local run"). The default is well under every corpus game's declared
# `max_length` (the smallest today is Coup's 500), deep enough that real
# decisions, movements, and (for the games whose greedy line is short) a
# natural end have all had a chance to fire.
_DEFAULT_STEP_CAP = 80
STEP_CAP = int(os.environ.get("CARDLANG_METAMORPHIC_STEPS", _DEFAULT_STEP_CAP))

# The default seed set every transform test parametrizes over. Env-tunable
# for the same "deeper local run" knob, by count (seeds 0..N-1).
_DEFAULT_SEED_COUNT = 3
SEED_COUNT = int(os.environ.get("CARDLANG_METAMORPHIC_SEEDS", _DEFAULT_SEED_COUNT))
SEEDS: tuple[int, ...] = tuple(range(SEED_COUNT))

Event = tuple[Any, ...]
Transform = Callable[[n.Game], n.Game]


class _Cutoff(Exception):
    """Raised by the capped chooser once `STEP_CAP` decisions have been made.
    Not a game error — `run_variant` catches it and reports a cutoff trace."""


def _sort_key(candidate: Any) -> str:
    # `repr`, not the rendered value directly: `render` can return `int`,
    # `str`, or a `tuple` depending on the candidate's shape (observe.render's
    # own closed-domain match), and a raw `sorted()` over a mixed-type list
    # would raise; `repr` gives one uniformly comparable, still-deterministic
    # key. Candidates within a single chooser call always share one shape (one
    # move's domain), so this never conflates two unrelated renderings.
    return repr(render(candidate))


def _capped_sorted_chooser(cap: int, *, reverse: bool = False) -> Chooser:
    calls = 0

    def choose(player: Player, candidates: list[Any], k: int) -> list[Any]:
        nonlocal calls
        calls += 1
        if calls > cap:
            raise _Cutoff()
        ordered = sorted(candidates, key=_sort_key, reverse=reverse)
        return ordered[:k]

    return choose


@dataclass(frozen=True)
class PlayoutTrace:
    """One player-indexed playout: each player's own observation log (the
    one `Ctx.observer` choke point), whether it ended by hitting `STEP_CAP`
    (in which case `result` is None — the game never reached a `GameResult`
    to compare), and the terminal result when it did end naturally."""

    events: dict[int, tuple[Event, ...]]
    cutoff: bool
    result: GameResult | None


def parse_corpus_game(path: Path) -> n.Game:
    """Parse (no resolve) one corpus game file — the PARSED tree every
    transform operates on."""
    return parse_text(path.read_text(), str(path))


def checked_variant(game: n.Game, *, label: str) -> n.Game:
    """Run `game` through the ordinary pipeline (resolve -> typecheck ->
    expand -> deck capacity). A failure here is a harness bug (an unsound
    transform), not a metamorphic finding — it fails loudly as an
    `AssertionError` naming which variant broke, never silently drops the
    comparison."""
    try:
        return _check(game)
    except DiagnosticError as e:
        raise AssertionError(
            f"{label}: the pipeline rejected this variant — either the "
            f"transform produced an invalid tree (a harness bug) or a "
            f"pre-existing corpus game regressed: {e}"
        ) from e


def run_variant(
    game: n.Game, seed: int, *, step_cap: int = STEP_CAP, reverse: bool = False
) -> PlayoutTrace:
    """Play one CHECKED game out deterministically (the sorted greedy
    chooser, capped at `step_cap` decisions), recording every player's
    observation log. `reverse` picks the DESCENDING-sorted candidate instead
    of the ascending one at every decision — same determinism and freedom
    from `PYTHONHASHSEED` (module docstring), a different deterministic
    policy. Exists because the ascending policy is a genuine coverage trap
    for at least one corpus game (T3/Coup: "allow" always sorts before
    "challenge", so the ascending policy can never reach a challenged
    branch, no matter the seed) — see `test_inline.py` for where this
    matters and why."""
    logs: dict[int, list[Event]] = {p: [] for p in range(game.players.low)}

    def observe(player: Player, event: Event) -> None:
        logs[player].append(event)

    chooser = _capped_sorted_chooser(step_cap, reverse=reverse)
    try:
        result = play_game(game, random.Random(seed), chooser=chooser, observer=observe)
    except _Cutoff:
        return PlayoutTrace(
            events={p: tuple(v) for p, v in logs.items()}, cutoff=True, result=None
        )
    return PlayoutTrace(
        events={p: tuple(v) for p, v in logs.items()}, cutoff=False, result=result
    )


def run_pair_source(
    path: Path,
    text_transform: Callable[[str], str],
    seed: int,
    *,
    step_cap: int = STEP_CAP,
    reverse: bool = False,
) -> tuple[PlayoutTrace, PlayoutTrace]:
    """Like `run_pair`, but for a transform that operates on SOURCE TEXT
    rather than the parsed tree (T3's source-level splice, which must not
    share code with `cardlang.expand` — metamorphic-suite.md item 2). Parses
    the original and `text_transform`-ed text separately (so the transform
    genuinely never touches the AST) and checks/plays out each exactly like
    `run_pair`."""
    original_text = path.read_text()
    transformed_text = text_transform(original_text)
    base = checked_variant(
        parse_text(original_text, str(path)), label=f"{path.name} (untransformed)"
    )
    transformed = checked_variant(
        parse_text(transformed_text, f"{path} (T3-spliced)"),
        label=f"{path.name} (transformed)",
    )
    return (
        run_variant(base, seed, step_cap=step_cap, reverse=reverse),
        run_variant(transformed, seed, step_cap=step_cap, reverse=reverse),
    )


def run_pair(
    path: Path,
    transform: Transform,
    seed: int,
    *,
    step_cap: int = STEP_CAP,
    reverse: bool = False,
) -> tuple[PlayoutTrace, PlayoutTrace]:
    """Parse `path` once, check the untransformed and `transform`-ed trees
    (each through its own single pipeline pass — see the module docstring on
    why re-checking is not an option), and play both out under `seed`."""
    parsed = parse_corpus_game(path)
    base = checked_variant(parsed, label=f"{path.name} (untransformed)")
    transformed = checked_variant(transform(parsed), label=f"{path.name} (transformed)")
    return (
        run_variant(base, seed, step_cap=step_cap, reverse=reverse),
        run_variant(transformed, seed, step_cap=step_cap, reverse=reverse),
    )


def _result_tuple(
    r: GameResult,
) -> tuple[tuple[tuple[Player, int], ...], Player | None, Player | None]:
    return tuple(sorted(r.scores.items())), r.winner, r.loser


def compare_traces(
    a: PlayoutTrace,
    b: PlayoutTrace,
    *,
    rename: Callable[[Event], Event] = lambda e: e,
) -> str | None:
    """Compare two playout traces, side `b` passed through `rename` event by
    event first (identity for a transform that renames nothing embedded in
    events). Returns `None` when they agree; otherwise a witness string
    naming the first divergence, for a loud, located test failure."""
    if a.cutoff != b.cutoff:
        return (
            f"one side hit the {STEP_CAP}-decision cutoff and the other did "
            f"not (a.cutoff={a.cutoff} b.cutoff={b.cutoff})"
        )
    if set(a.events) != set(b.events):
        return f"player sets disagree: {sorted(a.events)} vs {sorted(b.events)}"
    for p in sorted(a.events):
        ea = a.events[p]
        eb = tuple(rename(e) for e in b.events[p])
        if ea != eb:
            for i, (xa, xb) in enumerate(zip(ea, eb)):
                if xa != xb:
                    return f"player {p} event {i} diverges: {xa!r} != {xb!r} (b renamed)"
            return f"player {p} event count diverges: {len(ea)} != {len(eb)}"
    if not a.cutoff:
        assert a.result is not None and b.result is not None
        ra, rb = _result_tuple(a.result), _result_tuple(b.result)
        if ra != rb:
            return f"terminal GameResult diverges: {ra} != {rb}"
    return None
