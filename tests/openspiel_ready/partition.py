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
from typing import Any, Protocol

from cardlang.domains import zone_observer_key
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
        self, player: int, rs: RuntimeState, log: list[tuple[Any, ...]], /
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


def _is_owner(rs: RuntimeState, name: str, key: int | str | None, observer: int) -> bool:
    """Mirrors runtime/observe.py::_is_owner — and reads the SAME domain-table
    column (`zone_key_of`) it does, so the proof oracle cannot drift from the
    thing it proves. This used to be a private `== "team"` copy of the
    ownership rule with a silent default-to-player else branch: a third
    indexable role would have been projected by the runtime through the table
    while the proofs silently player-keyed it — the corpus checked against a
    stale oracle."""
    index = rs.zones.zone_index[name]
    if key is None or index is None:
        return False
    return zone_observer_key(index, rs, observer) == key


def projection_for(
    rs: RuntimeState, name: str, key: int | str | None, observer: int
) -> str:
    return zone_projection(rs.zones.zone_type[name], _is_owner(rs, name, key, observer))


def zone_instances(rs: RuntimeState) -> list[tuple[str, int | str | None, Zone]]:
    """Every zone instance, in the deterministic order the info state renders."""
    singles: list[tuple[str, int | str | None, Zone]] = [
        (name, None, rs.zones.single(name)) for name in sorted(rs.zones.singles)
    ]
    fams: list[tuple[str, int | str | None, Zone]] = [
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


# The zone probe table: for every projection level a zone type can declare,
# the distinctions the information state MUST show (True) and MUST hide
# (False), per distinguishing dimension. "count" is probed by removing a card
# (or adding one to an empty zone); "content" by a count-preserving swap of
# one card for SYNTHETIC. A projection level with no entry here CANNOT be
# probed, and check_visible_facts fails loudly rather than under-probing —
# so a new emission rule (rank_only, count_by_suit, ...) forces its probe
# declaration in the same change (fail-loud: an unprobed projection would
# otherwise pass the matrix vacuously, the silent failure mode this module
# exists to kill). test_every_declared_projection_has_a_probe_set pins the
# table against cardlang.stdlib.zones.ZONE_PROJECTIONS statically.
ZONE_PROBES: dict[str, dict[str, bool]] = {
    "identity": {"count": True, "content": True},
    "count_only": {"count": True, "content": False},
    "trivial": {"count": False, "content": False},
}


def check_visible_facts(
    rs: RuntimeState,
    obs_log: list[tuple[Any, ...]],
    observer: int,
    info_fn: InfoFn = _default_info,
) -> tuple[list[FactFailure], dict[str, int]]:
    """One perturbation per fact, enumerated from the declarations, for one
    observer at a paused world — with the perturbations per zone drawn from
    the declared ZONE_PROBES table, never hand-chosen at the call site.
    Mutate -> recompute -> restore; the world is byte-identical afterwards.
    Returns (failures, counts per category)."""
    failures: list[FactFailure] = []
    counts = {f"zone_{p}": 0 for p in ZONE_PROBES}
    counts["state_vars"] = 0
    counts["obs_events"] = 0
    before = info_fn(observer, rs, obs_log)

    for name, key, zone in zone_instances(rs):
        proj = projection_for(rs, name, key, observer)
        label = name if key is None else f"{name}[{key}]"
        probes = ZONE_PROBES.get(proj)
        if probes is None:
            raise AssertionError(
                f"zone {label}: projection {proj!r} has no declared probe set — "
                f"add its distinguishing dimensions to ZONE_PROBES before the "
                f"matrix can certify it (an unprobed projection passes vacuously)"
            )
        counts[f"zone_{proj}"] += 1
        if zone.cards:
            # the "count" dimension: one card fewer
            removed = zone.cards.pop(0)
            after = info_fn(observer, rs, obs_log)
            zone.cards.insert(0, removed)
            _probe(
                f"zone {label} ({proj} to P{observer}): removed {removed}",
                probes["count"],
                before,
                after,
                failures,
            )
            # the "content" dimension: same count, one card different —
            # REQUIRED to show through identity (an identity zone rendered as
            # a bare count would pass the removal probe while over-hiding
            # every card identity), REQUIRED invisible through count_only and
            # trivial (the leak direction).
            original = zone.cards[0]
            zone.cards[0] = SYNTHETIC
            after = info_fn(observer, rs, obs_log)
            zone.cards[0] = original
            _probe(
                f"zone {label} ({proj} to P{observer}): swapped content, same count",
                probes["content"],
                before,
                after,
                failures,
            )
        else:
            # empty zone: emptiness itself is the "count" dimension's fact;
            # the "content" dimension has nothing to vary (a single possible
            # content), so it is inherently unprobeable here, not skipped.
            zone.cards.append(SYNTHETIC)
            after = info_fn(observer, rs, obs_log)
            zone.cards.pop()
            _probe(
                f"zone {label} ({proj} to P{observer}): added a card to the empty zone",
                probes["count"],
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

    # Observation events. Perfect recall is a property of the log's exact
    # sequence — multiplicity and order included — so presence alone is not
    # enough: a renderer that deduplicates identical events (repeated asks,
    # repeated announces) or canonicalizes their order would keep every
    # repr present while over-hiding the sequence. Three probes per log:
    # presence (guards truncation/summarization), one DELETION per index
    # (guards deduplication — removing one copy of a duplicated event must
    # still change the rendering), and one adjacent SWAP per distinct
    # neighbor pair (guards order canonicalization).
    for i, e in enumerate(obs_log):
        counts["obs_events"] += 1
        if repr(e) not in before:
            failures.append(
                FactFailure(
                    fact=f"observation event {e!r} of P{observer}",
                    expected="change",
                    witness="event repr absent from the information state",
                )
            )
        deleted = obs_log.pop(i)
        after = info_fn(observer, rs, obs_log)
        obs_log.insert(i, deleted)
        _probe(
            f"P{observer}'s observation log: deleted event #{i} ({e!r})",
            True,
            before,
            after,
            failures,
        )
    for i in range(len(obs_log) - 1):
        if obs_log[i] != obs_log[i + 1]:
            obs_log[i], obs_log[i + 1] = obs_log[i + 1], obs_log[i]
            after = info_fn(observer, rs, obs_log)
            obs_log[i], obs_log[i + 1] = obs_log[i + 1], obs_log[i]
            _probe(
                f"P{observer}'s observation log: swapped adjacent events #{i}/#{i + 1}",
                True,
                before,
                after,
                failures,
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
