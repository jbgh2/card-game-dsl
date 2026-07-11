# Actionable-Now Information-Partition Checks Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the four "actionable now" information-partition checks from
`docs/open-questions/structural-infoset-proofs.md` — legal-action agreement,
per-visible-fact soundness perturbations, seed/rng non-observability, adapter
agreement — plus the witness-and-coverage reporting obligations, against the
existing swap-and-replay harness (`tests/openspiel_ready/harness.py`).

**Architecture:** All checks are *additive proof machinery* — no runtime or
info-state rendering changes, so no golden churn. A new
`tests/openspiel_ready/partition.py` holds the fact enumeration, perturbation
engine, witness helper, and coverage registry. `ReadinessProofs` in
`harness.py` gains three new proof methods (inherited by all fifteen game
modules automatically — zero per-game configuration, which is the point: the
perturbation set is enumerated from the zone declarations, not hand-picked),
and the existing swap proof gains the legal-action agreement assertion. A new
`tests/openspiel_ready/conftest.py` prints the per-game coverage record as a
pytest terminal summary and optionally dumps JSON.

**Tech Stack:** Python 3.11, pytest, mypy --strict (covers `tests/` too),
pyspiel (via `pytest.importorskip` in harness; `partition.py` must NOT import
pyspiel so root-level unit tests run without it).

## Global Constraints

- `mypy` (bare, from repo root) and `pytest -q` (full suite) must pass before any push. Non-negotiable (CLAUDE.md).
- mypy is `--strict` over BOTH `cardlang/` and `tests/` — every test helper needs full annotations.
- `tests/openspiel_ready/test_coverage.py` asserts the set of `test_*.py` modules in that package equals the registered games exactly (plus `test_coverage`). Do NOT add new `test_*.py` files there — helper module is `partition.py`, unit tests go in `tests/test_partition_helpers.py` at the tests root.
- No changes to `cardlang/` runtime or `infostate.py` rendering — checks are read-only proofs (mutate-compute-restore on the paused world only).
- Docs edits follow `docs/maintaining.md`: spec-voice, no history markers, cross-reference don't duplicate.

## Key facts about the codebase (read before coding)

- `run(path, seed, history, on_first_decision=None) -> Pause | Terminal` (`cardlang/openspiel/replay.py`). `Pause` has `.player`, `.legal` (sorted global action ids), `.rs` (live `RuntimeState`), `.obs_logs` (dict player -> list of event tuples). `run` does NOT import pyspiel.
- `information_state(player, rs, obs_log) -> str` (`cardlang/openspiel/infostate.py`) — pure function; renders ALL single zones + ALL family instances (each through `view_of`), then merged `rs.frames` (later frames shadow), then the obs log verbatim (`repr` per event, `;`-joined).
- `RuntimeState` (`cardlang/runtime/state.py`): `.zones` (`ZoneStore` with `.singles: dict[str, Zone]`, `.families: dict[str, dict[int, Zone]]`, `.zone_type: dict[str, str]`, `.zone_index: dict[str, str | None]`), `.frames: list[dict[str, Any]]`, `.rng: random.Random`, `.team_of: dict[Player, int]`. `Zone.cards` is a plain `list[Card]`.
- `Card` is `@dataclass(frozen=True, slots=True)` with `rank: str`, `suit: str`; `str(card)` renders `f"{rank}{sym}"` with `sym = f":{suit}"` for unknown suits. `Player = int`.
- Projections: `ZONE_PROJECTIONS: dict[str, ZoneVisibility]` and `zone_projection(zone_type, is_owner) -> str` in `cardlang/stdlib/zones.py`; `ZoneVisibility` has `.owner` and `.others` fields. Values: `"identity" | "count_only" | "trivial"`.
- Owner logic (reimplement independently in partition.py — the one in `cardlang/runtime/observe.py` is private): a family zone with `zone_index == "team"` is owned by observer iff `rs.team_of.get(observer) == key`; `"player"`-indexed iff `observer == key`; single zones (key None) have no owner.
- `GameSpec` per-game config lives on `TestReadiness.spec` (see `harness.py`); `_advance(path, seed, depth) -> (history, Pause)` replays greedily.
- The registered pyspiel game (`cardlang/openspiel/game.py`): root is a chance node whose action IS the seed (0..4095); `state.information_state_string(q)` returns `information_state(q, pause.rs, pause.obs_logs[q])` at a Pause and `""` at Terminal; `state.legal_actions()` returns the current pause's `legal`.
- Existing conventions for a hand-built `RuntimeState` in unit tests: see `tests/test_openspiel_infostate.py` `_rs()` (ZoneDecl tuples + `RuntimeState(Seating(2), ZoneStore(...), random.Random(0))`).

---

### Task 1: partition.py — fact enumeration, perturbation engine, witness + coverage helpers

**Files:**
- Create: `tests/openspiel_ready/partition.py`
- Create: `tests/test_partition_helpers.py`

**Interfaces (produced, used by Tasks 2–6):**
- `first_divergence(a: str, b: str, context: int = 40) -> str`
- `SYNTHETIC: Card` — a card no deck contains (`Card("‡", "synthetic")`)
- `projection_for(rs: RuntimeState, name: str, key: int | None, observer: int) -> str`
- `zone_instances(rs: RuntimeState) -> list[tuple[str, int | None, Zone]]` — deterministic order (sorted singles, then sorted families × sorted keys)
- `all_hidden(rs: RuntimeState, name: str) -> bool` — no observer ever gets identity of this zone (both `ZoneVisibility` fields non-identity)
- `@dataclass FactFailure: fact: str; expected: str; witness: str`
- `check_visible_facts(rs: RuntimeState, obs_log: list[tuple[Any, ...]], observer: int) -> tuple[list[FactFailure], dict[str, int]]` — the per-visible-fact matrix for one observer; returns (failures, category counts)
- `record(game: str, proof: str, **detail: Any) -> None` + `RECORDS: list[ProofRecord]` + `summary_lines() -> list[str]` + `dump_json(path: str) -> None`

- [ ] **Step 1: Write the failing unit tests**

`tests/test_partition_helpers.py` (no pyspiel import anywhere in its chain):

```python
"""The information-partition proof machinery (tests/openspiel_ready/partition.py):
fact enumeration from the declared projections, the perturbation matrix, the
witness renderer, and the coverage registry."""

from __future__ import annotations

import json
import random
from typing import Any

from cardlang.ast import nodes as n
from cardlang.runtime.state import RuntimeState, ZoneStore
from cardlang.runtime.values import Card, Seating

from tests.openspiel_ready.partition import (
    RECORDS,
    SYNTHETIC,
    all_hidden,
    check_visible_facts,
    dump_json,
    first_divergence,
    projection_for,
    record,
    summary_lines,
    zone_instances,
)


def _rs() -> RuntimeState:
    decls = (
        n.ZoneDecl(name="deck", index=None, type_ref=n.TypeRef(name="Deck")),
        n.ZoneDecl(name="hand", index="player", type_ref=n.TypeRef(name="Hand")),
        n.ZoneDecl(name="trick_pile", index=None, type_ref=n.TypeRef(name="TrickPile")),
        n.ZoneDecl(name="muck", index=None, type_ref=n.TypeRef(name="Muck")),
    )
    rs = RuntimeState(Seating(2), ZoneStore(decls, players=(0, 1)), random.Random(0))
    rs.zones.instance("hand", 0).add(Card("Q", "spades"))
    rs.zones.instance("hand", 1).add(Card("2", "clubs"))
    rs.zones.single("trick_pile").add(Card("7", "hearts"))
    rs.zones.single("deck").add(Card("9", "diamonds"))
    rs.zones.single("muck").add(Card("4", "clubs"))
    rs.push_frame()
    rs.declare("score", indexed=False, value={0: 10, 1: 20})
    return rs


def test_first_divergence_locates_the_difference() -> None:
    a = "x" * 100 + "AAA" + "y" * 100
    b = "x" * 100 + "BBB" + "y" * 100
    w = first_divergence(a, b)
    assert "AAA" in w and "BBB" in w and "@100" in w
    assert first_divergence("same", "same") == "(identical)"


def test_projection_for_reflects_declared_visibility() -> None:
    rs = _rs()
    assert projection_for(rs, "hand", 0, 0) == "identity"      # own hand
    assert projection_for(rs, "hand", 1, 0) == "count_only"    # opponent's
    assert projection_for(rs, "trick_pile", None, 0) == "identity"
    assert projection_for(rs, "deck", None, 0) == "count_only"
    assert projection_for(rs, "muck", None, 0) == "trivial"


def test_zone_instances_deterministic_order() -> None:
    rs = _rs()
    labels = [(name, key) for name, key, _ in zone_instances(rs)]
    assert labels == [
        ("deck", None), ("muck", None), ("trick_pile", None),
        ("hand", 0), ("hand", 1),
    ]


def test_all_hidden_is_a_projection_table_fact() -> None:
    rs = _rs()
    assert all_hidden(rs, "deck")            # count_only / count_only
    assert all_hidden(rs, "muck")            # trivial / trivial
    assert not all_hidden(rs, "hand")        # identity to its owner
    assert not all_hidden(rs, "trick_pile")  # identity to everyone


def test_visible_fact_matrix_passes_on_a_correct_state() -> None:
    rs = _rs()
    log: list[tuple[Any, ...]] = [("announce", 1, "bid(3)")]
    failures, counts = check_visible_facts(rs, log, observer=0)
    assert failures == []
    # every zone got at least one perturbation; the state var and log too
    assert counts["zone_identity"] >= 2      # own hand + trick_pile
    assert counts["zone_count_only"] >= 2    # opp hand + deck
    assert counts["zone_trivial"] >= 1       # muck
    assert counts["state_vars"] == 1         # score
    assert counts["obs_events"] == 1


def test_visible_fact_matrix_restores_the_world() -> None:
    rs = _rs()
    before = {
        (name, key): list(zone.cards) for name, key, zone in zone_instances(rs)
    }
    frames_before = [dict(f) for f in rs.frames]
    log: list[tuple[Any, ...]] = [("chose", "7♥")]
    check_visible_facts(rs, log, observer=1)
    assert {
        (name, key): list(zone.cards) for name, key, zone in zone_instances(rs)
    } == before
    assert rs.frames == frames_before
    assert log == [("chose", "7♥")]


def test_visible_fact_matrix_catches_a_dropped_zone() -> None:
    # A renderer that ignores zones entirely must fail the identity facts.
    rs = _rs()
    failures, _ = check_visible_facts(
        rs, [], observer=0,
        info_fn=lambda player, rs_, log: "constant",
    )
    assert failures, "a constant info state must fail the matrix"
    assert any("hand[0]" in f.fact for f in failures)


def test_visible_fact_matrix_catches_a_leaking_renderer() -> None:
    # A renderer that shows raw hidden content must fail the no-change facts.
    rs = _rs()

    def leaky(player: int, rs_: RuntimeState, log: list[tuple[Any, ...]]) -> str:
        return ",".join(
            str(c) for _, _, z in zone_instances(rs_) for c in z.cards
        )

    failures, _ = check_visible_facts(rs, [], observer=0, info_fn=leaky)
    assert any(f.expected == "no-change" for f in failures)


def test_coverage_registry_records_and_dumps(tmp_path: Any) -> None:
    # Snapshot-and-restore: the registry is a session-global that the
    # openspiel_ready proofs may already have populated in this run, and the
    # terminal summary renders it AFTER all tests — never clear it outright.
    saved = RECORDS[:]
    RECORDS.clear()
    try:
        record("cardlang_demo", "swap", seed=5, pairs_tried=3)
        record("cardlang_demo", "facts", observers=2)
        lines = summary_lines()
        assert any("cardlang_demo" in line for line in lines)
        out = tmp_path / "report.json"
        dump_json(str(out))
        data = json.loads(out.read_text())
        assert data[0]["game"] == "cardlang_demo" and data[0]["proof"] == "swap"
        assert data[0]["detail"]["seed"] == 5
    finally:
        RECORDS[:] = saved


def test_synthetic_card_is_not_a_real_card() -> None:
    assert SYNTHETIC.suit == "synthetic"
    assert str(SYNTHETIC) == "‡:synthetic"
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd "/Users/benh/Projects/Card game DSL" && python -m pytest tests/test_partition_helpers.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'tests.openspiel_ready.partition'`

- [ ] **Step 3: Write `tests/openspiel_ready/partition.py`**

```python
"""Fact-level partition proof machinery (structural-infoset-proofs, the
"actionable now" checks).

The zone declarations and their projections ARE the machine-readable
visibility specification, so the soundness perturbation set is ENUMERATED from
them rather than hand-picked: for every zone x observer the declared
projection says whether a perturbation must change the observer's information
state (identity: content; count_only: count but not same-count content;
trivial: nothing), and every public state variable and observation event must
be sensitive too. Failures carry a witness — the perturbed fact and the
information-state fragment that wrongly agrees or differs — and passing runs
record what they covered (the coverage registry; rendered by conftest's
terminal summary, dumped as JSON via CARDLANG_PARTITION_REPORT).

This module must not import pyspiel: the root-level unit tests
(tests/test_partition_helpers.py) run without it.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Callable, Protocol

from cardlang.openspiel.infostate import information_state
from cardlang.runtime.state import RuntimeState, Zone
from cardlang.runtime.values import Card
from cardlang.stdlib.zones import ZONE_PROJECTIONS, zone_projection

# A card no deck contains — safe to add to any zone as a perturbation.
SYNTHETIC = Card("‡", "synthetic")

_SENTINEL = "«perturbed»"
_SENTINEL_EVENT: tuple[Any, ...] = ("«synthetic-event»",)


class InfoFn(Protocol):
    def __call__(
        self, player: int, rs: RuntimeState, log: list[tuple[Any, ...]]
    ) -> str: ...


def _default_info(player: int, rs: RuntimeState, log: list[tuple[Any, ...]]) -> str:
    return information_state(player, rs, log)


def first_divergence(a: str, b: str, context: int = 40) -> str:
    """The witness fragment: where two information states first differ."""
    if a == b:
        return "(identical)"
    i = next(
        (k for k, (x, y) in enumerate(zip(a, b)) if x != y),
        min(len(a), len(b)),
    )
    lo = max(0, i - context)
    return (
        f"@{i}: ...{a[lo : i + context]!r} != ...{b[lo : i + context]!r}"
    )


def _is_owner(rs: RuntimeState, name: str, key: int | None, observer: int) -> bool:
    index = rs.zones.zone_index[name]
    if key is None or index is None:
        return False
    if index == "team":
        return rs.team_of.get(observer) == key
    return observer == key


def projection_for(rs: RuntimeState, name: str, key: int | None, observer: int) -> str:
    return zone_projection(rs.zones.zone_type[name], _is_owner(rs, name, key, observer))


def zone_instances(rs: RuntimeState) -> list[tuple[str, int | None, Zone]]:
    """Every zone instance, in the deterministic order the info state renders."""
    singles: list[tuple[str, int | None, Zone]] = [
        (name, None, rs.zones.single(name)) for name in sorted(rs.zones.singles)
    ]
    fams: list[tuple[str, int | None, Zone]] = [
        (name, key, rs.zones.instance(name, key))
        for name in sorted(rs.zones.families)
        for key in sorted(rs.zones.families[name])
    ]
    return singles + fams


def all_hidden(rs: RuntimeState, name: str) -> bool:
    """No observer is ever entitled to this zone's card identities — its
    content order and composition are undrawn randomness."""
    vis = ZONE_PROJECTIONS[rs.zones.zone_type[name]]
    return vis.owner != "identity" and vis.others != "identity"


@dataclass
class FactFailure:
    fact: str      # e.g. "zone hand[2] (identity to P0): removed Q♠"
    expected: str  # "change" | "no-change"
    witness: str   # first_divergence fragment (or "(identical)" for a missed change)


def _probe(
    fact: str,
    expected_change: bool,
    before: str,
    after: str,
    failures: list[FactFailure],
) -> None:
    changed = before != after
    if changed != expected_change:
        failures.append(
            FactFailure(
                fact=fact,
                expected="change" if expected_change else "no-change",
                witness=first_divergence(before, after),
            )
        )


def check_visible_facts(
    rs: RuntimeState,
    obs_log: list[tuple[Any, ...]],
    observer: int,
    info_fn: InfoFn = _default_info,
) -> tuple[list[FactFailure], dict[str, int]]:
    """One perturbation per fact, enumerated from the declarations, for one
    observer at a paused world. Mutate -> recompute -> restore; the world is
    byte-identical afterwards. Returns (failures, counts per category)."""
    failures: list[FactFailure] = []
    counts = {
        "zone_identity": 0,
        "zone_count_only": 0,
        "zone_trivial": 0,
        "state_vars": 0,
        "obs_events": 0,
    }
    before = info_fn(observer, rs, obs_log)

    for name, key, zone in zone_instances(rs):
        proj = projection_for(rs, name, key, observer)
        label = name if key is None else f"{name}[{key}]"
        counts[f"zone_{proj}"] += 1
        if zone.cards:
            # content/count perturbation: remove the first card
            removed = zone.cards.pop(0)
            after = info_fn(observer, rs, obs_log)
            zone.cards.insert(0, removed)
            _probe(
                f"zone {label} ({proj} to P{observer}): removed {removed}",
                proj != "trivial",
                before,
                after,
                failures,
            )
            if proj == "count_only":
                # count-preserving content swap must NOT be visible
                original = zone.cards[0]
                zone.cards[0] = SYNTHETIC
                after = info_fn(observer, rs, obs_log)
                zone.cards[0] = original
                _probe(
                    f"zone {label} (count_only to P{observer}): swapped content, same count",
                    False,
                    before,
                    after,
                    failures,
                )
        else:
            # empty zone: emptiness is itself the visible fact
            zone.cards.append(SYNTHETIC)
            after = info_fn(observer, rs, obs_log)
            zone.cards.pop()
            _probe(
                f"zone {label} ({proj} to P{observer}): added a card to the empty zone",
                proj != "trivial",
                before,
                after,
                failures,
            )

    # Public state variables: perturb the visible (topmost) binding of each.
    winning: dict[str, int] = {}
    for i, frame in enumerate(rs.frames):
        for var in frame:
            winning[var] = i
    for var, i in sorted(winning.items()):
        frame = rs.frames[i]
        original = frame[var]
        frame[var] = _SENTINEL
        after = info_fn(observer, rs, obs_log)
        frame[var] = original
        counts["state_vars"] += 1
        _probe(
            f"state variable '{var}' (public): replaced with sentinel",
            True,
            before,
            after,
            failures,
        )

    # Observation events: each event embedded verbatim; the log is sensitive.
    for e in obs_log:
        counts["obs_events"] += 1
        if repr(e) not in before:
            failures.append(
                FactFailure(
                    fact=f"observation event {e!r} of P{observer}",
                    expected="change",
                    witness="event repr absent from the information state",
                )
            )
    obs_log.append(_SENTINEL_EVENT)
    after = info_fn(observer, rs, obs_log)
    obs_log.pop()
    _probe(
        f"P{observer}'s observation log: appended a synthetic event",
        True,
        before,
        after,
        failures,
    )
    counts["obs_events"] += 1  # the append probe

    return failures, counts


def format_failures(game: str, observer: int, failures: list[FactFailure]) -> str:
    lines = [f"{game}: P{observer}'s information state fails {len(failures)} fact check(s):"]
    lines += [
        f"  [{f.expected} expected] {f.fact} -> {f.witness}" for f in failures
    ]
    return "\n".join(lines)


# --- coverage registry (the citable record of what a passing run covered) ---


@dataclass
class ProofRecord:
    game: str
    proof: str
    detail: dict[str, Any] = field(default_factory=dict)


RECORDS: list[ProofRecord] = []


def record(game: str, proof: str, **detail: Any) -> None:
    RECORDS.append(ProofRecord(game=game, proof=proof, detail=detail))


def summary_lines() -> list[str]:
    by_game: dict[str, list[ProofRecord]] = {}
    for r in RECORDS:
        by_game.setdefault(r.game, []).append(r)
    lines: list[str] = []
    for game in sorted(by_game):
        parts = []
        for r in by_game[game]:
            kv = ",".join(f"{k}={v}" for k, v in r.detail.items())
            parts.append(f"{r.proof}[{kv}]")
        lines.append(f"{game}: " + " ".join(parts))
    return lines


def dump_json(path: str) -> None:
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(
            [{"game": r.game, "proof": r.proof, "detail": r.detail} for r in RECORDS],
            fh,
            indent=2,
            default=str,
        )
```

Note for the implementer: `counts[f"zone_{proj}"]` — mypy accepts dynamic keys
on `dict[str, int]`; if the f-string key bothers the reviewer, use an explicit
mapping. `Callable` import is unused if you use the Protocol — remove unused
imports; run mypy early.

- [ ] **Step 4: Run the unit tests until they pass**

Run: `cd "/Users/benh/Projects/Card game DSL" && python -m pytest tests/test_partition_helpers.py -q`
Expected: all PASS.

- [ ] **Step 5: Run mypy**

Run: `cd "/Users/benh/Projects/Card game DSL" && mypy`
Expected: `Success: no issues found`. Fix any strict-mode complaints (annotations, unused imports).

- [ ] **Step 6: Verify the openspiel_ready module-set guard still passes**

Run: `python -m pytest tests/openspiel_ready/test_coverage.py -q`
Expected: PASS (partition.py is not a `test_*.py` module, so the set is unchanged).

- [ ] **Step 7: Commit**

```bash
git add tests/openspiel_ready/partition.py tests/test_partition_helpers.py
git commit -m "test(openspiel): partition proof machinery — fact enumeration, witnesses, coverage registry"
```

---

### Task 2: legal-action agreement + witness upgrade in the swap proof

**Files:**
- Modify: `tests/openspiel_ready/harness.py` (the `test_indistinguishability_under_hidden_swap` method, ~lines 178–239)

**Interfaces:**
- Consumes: `first_divergence`, `record` from `.partition` (Task 1)
- Produces: nothing new; strengthens an existing proof

- [ ] **Step 1: Extend the swap test**

In `harness.py`, add the import near the other local imports (top of file, after the `cardlang.openspiel` imports):

```python
from .partition import check_visible_facts, first_divergence, format_failures, record
```

(`check_visible_facts`/`format_failures` are used by Task 3 — add the full
import line now to avoid churn; if implementing tasks out of order, trim to
what exists.)

Replace the success branch of the swap loop (currently the `assert info_a == info_b` block followed by `return`) with:

```python
            assert isinstance(pause_b, Pause)
            info_b = information_state(p, pause_b.rs, pause_b.obs_logs[p])
            assert info_a == info_b, (
                f"{spec.short_name}: swapping hidden {x}<->{y} ({who}) "
                f"CHANGED P{p}'s information state — the info-set leaks.\n"
                f"worlds: seed={seed} depth={len(history)} swap=({x},{y})\n"
                f"witness: {first_divergence(info_a, info_b)}"
            )
            # Legal-action agreement: two worlds in the same information set
            # for the player to move must offer identical legal actions —
            # otherwise the offered moves are themselves a leak channel, one
            # OpenSpiel does not police.
            assert pause_b.player == p, (
                f"{spec.short_name}: the hidden swap moved the turn to "
                f"P{pause_b.player} — whose turn it is leaks hidden content"
            )
            assert pause_b.legal == pause_a.legal, (
                f"{spec.short_name}: same information set, different legal actions "
                f"— swap ({x},{y}) changed the offer for P{p}: "
                f"only-in-A={sorted(set(pause_a.legal) - set(pause_b.legal))} "
                f"only-in-B={sorted(set(pause_b.legal) - set(pause_a.legal))}"
            )
            record(
                spec.short_name,
                "swap",
                seed=seed,
                depth=len(history),
                axis=spec.swap_axis,
                pair=f"{x}<->{y}",
                pairs_skipped=candidates.index((x, y)),
                candidates=len(candidates),
                legal_agreement=True,
            )
            return  # one successful controlled swap proves the property
```

(`candidates.index((x, y))` is the number of pairs the replay rejected before
the one that succeeded — the sampled-coverage number the record must carry.)

- [ ] **Step 2: Run the full openspiel_ready suite**

Run: `python -m pytest tests/openspiel_ready -q`
Expected: all PASS. If a game fails the new legal-agreement assert, STOP —
that is a real finding (a leak through the offered moves); report it rather
than weakening the check.

- [ ] **Step 3: Run mypy**

Run: `mypy` — expected clean.

- [ ] **Step 4: Commit**

```bash
git add tests/openspiel_ready/harness.py
git commit -m "test(openspiel): legal-action agreement in the swap proof + witness reporting"
```

---

### Task 3: the per-visible-fact soundness matrix proof

**Files:**
- Modify: `tests/openspiel_ready/harness.py` (add a method to `ReadinessProofs`)

**Interfaces:**
- Consumes: `check_visible_facts`, `format_failures`, `record` from `.partition`

- [ ] **Step 1: Add the proof method to `ReadinessProofs`** (after `test_soundness_own_view_changes_the_state`):

```python
    def test_soundness_every_visible_fact_is_in_the_state(self) -> None:
        """Soundness, generalized (structural-infoset-proofs, 'nothing
        over-hidden'): one perturbation per visible fact, for EVERY observer,
        enumerated from the zone declarations — every zone projection the
        observer is entitled to, every public state variable, every
        observation event. The complement is checked too: a perturbation of
        content the observer is NOT entitled to (a count-preserving swap in a
        count_only zone, any change in a trivial zone) must NOT move their
        information state. Perturbations are applied to the paused world
        snapshot directly (mutate -> recompute -> restore), so no replay
        legality constraints apply; the replay-level soundness probe above
        stays as the end-to-end complement."""
        spec = self.spec
        _, pause = _advance(spec.path, 5, spec.depth)
        totals = {"zone_identity": 0, "zone_count_only": 0, "zone_trivial": 0,
                  "state_vars": 0, "obs_events": 0}
        for observer in range(len(pause.obs_logs)):
            failures, counts = check_visible_facts(
                pause.rs, pause.obs_logs[observer], observer
            )
            assert not failures, format_failures(spec.short_name, observer, failures)
            assert sum(counts.values()) > 0, (
                f"{spec.short_name}: the fact enumeration for P{observer} was empty"
            )
            for k, v in counts.items():
                totals[k] += v
        record(spec.short_name, "facts", observers=len(pause.obs_logs),
               depth=spec.depth, **totals)
```

- [ ] **Step 2: Run the openspiel_ready suite**

Run: `python -m pytest tests/openspiel_ready -q`
Expected: PASS for all fifteen games. Two possible real findings — do NOT
paper over either; stop and report:
- an `expected change` failure on a state variable or zone = a fact silently
  dropped from the information state (over-hiding — the exact defect class
  this check exists to catch);
- an `expected no-change` failure = the renderer leaks hidden content.

- [ ] **Step 3: mypy + commit**

```bash
mypy && python -m pytest tests/test_partition_helpers.py -q
git add tests/openspiel_ready/harness.py
git commit -m "test(openspiel): per-visible-fact soundness matrix, enumerated from the declarations"
```

---

### Task 4: seed and undrawn-randomness non-observability

**Files:**
- Modify: `tests/openspiel_ready/harness.py` (add a method to `ReadinessProofs`; add `random` import — already imported at top)

**Interfaces:**
- Consumes: `all_hidden`, `zone_instances`, `first_divergence`, `record` from `.partition`

- [ ] **Step 1: Add the proof method** (after the Task 3 method):

```python
    def test_seed_and_undrawn_randomness_are_not_observable(self) -> None:
        """No information state may be sensitive to the root chance seed
        beyond what dealt-and-observed cards already reveal, nor to rng draws
        not yet made — including the rules-level rng gates carrying the
        Tichu/Coup scope reductions, which draw from the same generator
        (structural-infoset-proofs, 'Seed and undrawn-randomness
        non-observability'). Two direct perturbations at a paused world:
        replace the live generator outright (a different seed's entire future
        stream), and reverse the order of every all-hidden stock (the pending
        draw order). Every player's information state must be byte-identical
        under both."""
        spec = self.spec
        _, pause = _advance(spec.path, 5, spec.depth)
        players = range(len(pause.obs_logs))
        before = {
            q: information_state(q, pause.rs, pause.obs_logs[q]) for q in players
        }

        pause.rs.rng = random.Random(0xC0FFEE)
        stocks: list[str] = []
        for name, key, zone in zone_instances(pause.rs):
            if all_hidden(pause.rs, name) and len(zone.cards) >= 2:
                zone.cards.reverse()
                stocks.append(name if key is None else f"{name}[{key}]")

        for q in players:
            after = information_state(q, pause.rs, pause.obs_logs[q])
            assert after == before[q], (
                f"{spec.short_name}: P{q}'s information state is sensitive to "
                f"undrawn randomness (reseeded rng; reversed {stocks})\n"
                f"witness: {first_divergence(before[q], after)}"
            )
        record(
            spec.short_name,
            "rng",
            depth=spec.depth,
            reseeded=True,
            stocks_reversed=len(stocks),
            vacuous_stock=(len(stocks) == 0),
        )
```

(`stocks_reversed=0` is legitimate for games that deal the whole pack —
Hearts — which is why the record carries `vacuous_stock` explicitly rather
than the check failing: the reseed probe is never vacuous.)

- [ ] **Step 2: Run + commit**

```bash
python -m pytest tests/openspiel_ready -q && mypy
git add tests/openspiel_ready/harness.py
git commit -m "test(openspiel): seed and undrawn-randomness non-observability proof"
```

---

### Task 5: adapter agreement along a replayed line

**Files:**
- Modify: `tests/openspiel_ready/harness.py` (add the final method to `ReadinessProofs`)

**Interfaces:**
- Consumes: `first_divergence`, `record` from `.partition`; `pyspiel` (already module-level), `run`, `information_state`

- [ ] **Step 1: Add the proof method:**

```python
    def test_adapter_agrees_with_the_dsl_information_state(self) -> None:
        """The readiness proofs run at the DSL level; the partition OpenSpiel
        algorithms actually consume is the registered game's. Walk one line
        and assert the two renderings agree at every step — current player,
        legal actions, and every player's information-state string — and that
        the terminal returns agree if reached. Because the pyspiel state
        re-simulates independently of this test's own `run` calls, the
        comparison doubles as a per-game determinism check: two independent
        replays of the same (seed, history) must render byte-identically."""
        spec = self.spec
        seed = 5
        game = pyspiel.load_game(spec.short_name)
        state = game.new_initial_state()
        assert state.is_chance_node()
        state.apply_action(seed)

        history: list[int] = []
        r = run(spec.path, seed, ())
        steps = 0
        while isinstance(r, Pause) and steps < spec.depth:
            assert not state.is_terminal()
            assert state.current_player() == r.player, (
                f"{spec.short_name}: step {steps}: adapter player "
                f"{state.current_player()} != DSL player {r.player}"
            )
            assert state.legal_actions() == r.legal, (
                f"{spec.short_name}: step {steps}: adapter legal actions disagree"
            )
            for q in range(len(r.obs_logs)):
                expected = information_state(q, r.rs, r.obs_logs[q])
                got = state.information_state_string(q)
                assert got == expected, (
                    f"{spec.short_name}: step {steps}: adapter info state for "
                    f"P{q} diverged\nwitness: {first_divergence(expected, got)}"
                )
            action = r.legal[0]
            state.apply_action(action)
            history.append(action)
            r = run(spec.path, seed, tuple(history))
            steps += 1
        if not isinstance(r, Pause):
            assert state.is_terminal(), (
                f"{spec.short_name}: DSL line terminal but adapter is not"
            )
            assert state.returns() == r.returns
        record(spec.short_name, "adapter", seed=seed, steps=steps,
               terminal=not isinstance(r, Pause))
```

- [ ] **Step 2: Run + commit**

```bash
python -m pytest tests/openspiel_ready -q && mypy
git add tests/openspiel_ready/harness.py
git commit -m "test(openspiel): adapter-agreement proof — registered game vs DSL rendering"
```

---

### Task 6: the coverage record — terminal summary + JSON dump

**Files:**
- Create: `tests/openspiel_ready/conftest.py`
- Modify: `tests/openspiel_ready/harness.py` (update the module docstring's proof list)

- [ ] **Step 1: Write `tests/openspiel_ready/conftest.py`:**

```python
"""Render the partition-coverage record after a run (structural-infoset-proofs:
'a passing run must record what it covered ... that record is what any
external claim about the partition cites'). Printed as a pytest terminal
summary whenever any readiness proof ran; dumped as JSON when
CARDLANG_PARTITION_REPORT names a path.

Deliberately import-light: partition.py does not import pyspiel, so collection
works even where open_spiel is absent (the proofs themselves importorskip)."""

from __future__ import annotations

import os
from typing import Any

from tests.openspiel_ready.partition import RECORDS, dump_json, summary_lines


def pytest_terminal_summary(terminalreporter: Any, exitstatus: int, config: Any) -> None:
    if not RECORDS:
        return
    terminalreporter.section("openspiel_ready partition coverage")
    for line in summary_lines():
        terminalreporter.write_line(line)
    out = os.environ.get("CARDLANG_PARTITION_REPORT")
    if out:
        dump_json(out)
        terminalreporter.write_line(f"partition coverage record written to {out}")
```

- [ ] **Step 2: Update the harness module docstring** — the numbered proof
list at the top of `harness.py` currently names four proofs. Extend it:

```
1. pyspiel API conformance (random_sim_test, or a bounded random API walk ...)
2. INDISTINGUISHABILITY: two worlds differing only in cards hidden from P
   yield byte-identical information states for P — and offer P identical
   legal actions (legal-action agreement).
3. Soundness converse: perturbing what P CAN see changes P's state — the
   replay-level own-hand probe plus the per-visible-fact matrix enumerated
   from the zone declarations (partition.check_visible_facts).
4. Perfect recall: each player's observation log is append-only along a game.
5. Seed/undrawn-randomness non-observability: reseeding the generator and
   permuting all-hidden stocks leaves every information state byte-identical.
6. Adapter agreement: the registered pyspiel game renders the same partition
   the DSL-level proofs certify.

Passing runs record their coverage (partition.RECORDS; see conftest.py);
failing checks report their witness — the perturbed fact and the
information-state fragment that wrongly agrees or differs.
```

- [ ] **Step 3: Verify the summary renders**

Run: `python -m pytest tests/openspiel_ready/test_hearts.py -q 2>&1 | tail -20`
Expected: tests pass; the "openspiel_ready partition coverage" section shows a
`cardlang_hearts: swap[...] facts[...] rng[...] adapter[...]` line.

Run: `CARDLANG_PARTITION_REPORT=/tmp/partition.json python -m pytest tests/openspiel_ready/test_hearts.py -q && python -c "import json; print(len(json.load(open('/tmp/partition.json'))))"`
Expected: a non-zero record count.

- [ ] **Step 4: mypy + commit**

```bash
mypy
git add tests/openspiel_ready/conftest.py tests/openspiel_ready/harness.py
git commit -m "test(openspiel): partition coverage record — terminal summary + JSON dump"
```

---

### Task 7: docs — coverage annotations, roadmap, CLAUDE.md

**Files:**
- Modify: `docs/open-questions/structural-infoset-proofs.md`
- Modify: `docs/open-questions/_index.md` (the structural-infoset-proofs entry)
- Modify: `docs/roadmap.md` ("Suggested next steps" — step 1 is built)
- Modify: `CLAUDE.md` (the "four-proof harness" phrase)

Follow `docs/maintaining.md`: spec voice, no "now covered as of this change"
history markers — state present coverage plainly.

- [ ] **Step 1: Update the certification checklist** in
`structural-infoset-proofs.md` ("What any resolution must certify"): rewrite
the coverage sentence of each of these items (keep each item's obligation
text):
- **Soundness, generalized** — replace "*The biggest gap:* ... hand-picked
  rather than enumerated" wording with: covered at the snapshot level — one
  perturbation per visible fact for every observer, enumerated from the zone
  declarations (the per-visible-fact matrix in `tests/openspiel_ready/
  partition.py`, run per game by the shared harness), including the converse
  (count-preserving and trivial-zone perturbations must NOT move the state);
  the replay-level probe still perturbs only the observer's own hand.
- **Seed and undrawn-randomness non-observability** — replace "*Gap:* never
  asserted directly ..." with: asserted directly per game — reseeding the
  live generator and reversing every all-hidden stock at a paused world
  leaves every information state byte-identical (the rules-level rng gates
  draw from the same generator).
- **Legal-action agreement** — replace "*Gap:* ... never compares their
  `legal` lists" with: covered — the swap proof asserts the paired worlds
  pause on the same player and offer identical legal actions.
- **Adapter agreement** — replace "One assertion closes the door ..." with:
  covered per game — a replayed line asserts the registered pyspiel rendering
  (current player, legal actions, every player's information-state string,
  terminal returns) equals the DSL-level rendering, which doubles as a
  per-game determinism check across independent replays.
- The witness/coverage paragraph ("Two obligations on the *proof machinery*
  itself") — state that both hold: failing checks report the perturbed fact
  and the first-divergence fragment; passing runs record coverage per game
  (`partition.RECORDS`, rendered as a pytest terminal summary; JSON via
  `CARDLANG_PARTITION_REPORT`).
- **"### Actionable now"** — rewrite: these checks are built (name them and
  where they live); only the constructive world generator remains blocked on
  the compound hidden-function probe. The question stays open on that.

- [ ] **Step 2: Update `_index.md`** — in the structural-infoset-proofs
entry, change "with today's coverage per item and the checks buildable now;
only the constructive world generator is blocked" to reflect that the
buildable checks are built and only the constructive world generator is
blocked.

- [ ] **Step 3: Update `docs/roadmap.md`** — delete step 1 (built), renumber
2–6 to 1–5, and fix the two forward references: step 2's "a natural first
exercise for step 1's checks" → "a natural first exercise for the
partition checks (legal-action agreement, the per-visible-fact matrix,
seed/rng non-observability, adapter agreement)"; step 4's "the step-1 checks
are their acceptance bar" → "the partition checks are their acceptance bar".

- [ ] **Step 4: Update CLAUDE.md** — the parenthetical "(one proof module per
game over a shared four-proof harness)" no longer counts four; change to
"(one proof module per game over a shared proof harness)" and extend the
proof list "proves indistinguishability (hidden-card swaps leave a player's
information state byte-identical), soundness, and perfect recall" to
"...proves indistinguishability (hidden-card swaps leave a player's
information state byte-identical, and offer identical legal actions),
soundness (a per-visible-fact perturbation matrix enumerated from the zone
declarations), seed/rng non-observability, adapter agreement, and perfect
recall for each".

- [ ] **Step 5: Investigate whether `rs.mech_state` belongs in the
information state** (a possible NEW open question, not a code change):
`infostate.py` renders `rs.frames` but not `rs.mech_state` (active `round`
state) or `rs.last_round_state`. Check `docs/decisions.md` ("Hidden
information lives only in zones; state is public" and the round-state
exposure notes) for whether mechanic-internal round state is *declared*
public state. If the docs don't settle it, add
`docs/open-questions/mech-state-in-infostate.md` (both directions are live:
rendering it could leak — round bodies may compute over hidden zones;
omitting it could over-hide if a round variable ever carries entitled
information not already in the observation log) and list it in `_index.md`
under Tier 3 or 4 with the data point that would settle it. If decisions.md
already settles it, do nothing.

- [ ] **Step 6: Commit**

```bash
git add docs/open-questions/ docs/roadmap.md CLAUDE.md
git commit -m "docs: partition-check coverage — the actionable-now checks are built"
```

---

### Task 8: full verification + PR

- [ ] **Step 1:** `mypy` (bare) — clean.
- [ ] **Step 2:** `pytest -q` (FULL suite) — all pass. Some exact-score tests pin `PYTHONHASHSEED=0`; run as CI does.
- [ ] **Step 3:** Push branch `feat/partition-checks`, open a PR titled
"test(openspiel): the actionable-now information-partition checks" whose body
maps each check to its obligation in structural-infoset-proofs.md.
