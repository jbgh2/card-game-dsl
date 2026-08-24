"""An experiment's recorded numbers are evidence, and this is what checks them.

The rigs under `experiments/` are scripts, not tests, so `pytest` never runs
them and no assertion of theirs can fire. `mypy` checks types and the suite
checks behavior; neither checks where a number came from. Two guarantees are
machine-checkable and live here: a headline measured on the deals its knobs were
chosen from is not evidence about those knobs, and a figure printed in a report
is only a citation if it equals the artifact it cites.

Completeness ledger (decisions.md "Closed-domain completeness")
---------------------------------------------------------------
property:        a policy whose knobs a sweep selected is reported only on
                 deals disjoint from that sweep; and every cell of the two
                 salvo report tables that describe the adopted game equals the
                 artifact field it cites, to the precision the cell prints.
domain:          (a) every `experiments/*/results_*.json`, classified by
                 `provenance_of` into the three arms of `Provenance` on two
                 axes — whether the artifact names its knobs, and whether it
                 names its first deal — so a rig that reports the tuned policy
                 through its own schema is reached rather than skipped. The
                 sweep is the glob, so an artifact joins it by being written,
                 and `test_the_tuned_population_is_not_empty` is what stops the
                 classification going vacuous when no artifact carries the
                 knobs. (b) every table under the two covered sections of
                 `experiments/salvo/REPORT.md`, crossed with its rows and its
                 mapped columns, with the row axis pinned to what each table is
                 bound to — `test_the_liveness_table_prints_every_bin_it_is_
                 bound_to` and `test_the_scoreboard_prints_the_rows_it_is_bound_
                 to` — so a deleted row shrinks the checked population loudly.
                 Boundaries, each a limit on this module rather than a
                 gap in the report. Only salvo's two adopted-game sections are
                 bound: §2's and §8's tables describe rounds 1-3 and want a
                 per-cell filename convention derived from
                 `experiments/salvo/triage.py` (issue #419), and
                 `test_every_table_in_the_report_is_accounted_for` holds them as
                 a named set so a table added anywhere in the report reddens
                 rather than slipping past. Only TABLE cells are bound: a figure
                 quoted in running prose is a larger and less uniform population
                 (issue #417). And the artifact axis is the `results_*.json`
                 glob, which the green-lane variant artifacts are named outside
                 of (issue #418). The table superset is over pipe tables with a
                 delimiter row, the one style this report writes; a borderless
                 or HTML table would not be seen.
registry:        the tuned knobs and the sweep's extent are read from
                 `experiments/salvo/results_tune.json` (`winner.knobs`,
                 `sweep_seeds`), never restated here, so re-tuning moves the
                 predicate with the artifact; the artifact axis is the glob in
                 `_artifacts`; the table axis is `_tables`, parsed from the
                 report; the column bindings are `_LIVENESS` with
                 `_LIVENESS_PARENTHETICAL`, and `_SCOREBOARD_VALUES`; the
                 deal-range spellings are `_SEED_START_FIELDS`. The `--seed-start`
                 default that this module's absent-means-zero reading matches:
                 `experiments/salvo/triage.py`.
does not prove:  a green here says nothing about whether the number is a good
                 measurement. Whether the sweep was fine enough, whether the
                 reference policies are strong, and whether 500 deals separate
                 the arms are judgment calls the report's own standing caveats
                 own; these two checks are the narrower thing a machine can do —
                 that a number came from the deals it says it did, and equals
                 the artifact it cites. Nor does it prove a cited figure is the
                 RIGHT field: a cell bound to the wrong field of the right file
                 passes here as soon as the two agree, and the column maps are
                 the hand-written half this module cannot derive.
"""

from __future__ import annotations

import json
import re
from collections.abc import Mapping
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parent.parent
EXPERIMENTS = ROOT / "experiments"
_SALVO = EXPERIMENTS / "salvo"
_REPORT = _SALVO / "REPORT.md"
_SELECTION = _SALVO / "results_tune.json"


# --------------------------------------------------------------------------
# Gate 1 — no headline number is measured in-sample
# --------------------------------------------------------------------------


class Provenance(Enum):
    """What an artifact's own fields say about the deals behind its numbers."""

    UNREACHED = "makes no tuned-knob claim"
    OUT_OF_SAMPLE = "measured past the sweep the knobs were chosen on"
    IN_SAMPLE = "measured on the deals the knobs were chosen from"


def _artifacts() -> list[Path]:
    return sorted(EXPERIMENTS.glob("*/results_*.json"))


def _artifact_ids() -> list[str]:
    return [str(p.relative_to(EXPERIMENTS)) for p in _artifacts()]


# How the salvo rigs spell "the first deal behind these numbers". Declaring a
# deal range IS a provenance claim, so an artifact that records one is judged
# against the sweep even when it names no knobs — which is the only reason the
# gate reaches the rigs that run the tuned policy without writing a `tuning`
# block (`probe_liveness.py`, whose policy is `triage.CURVES["base"]`, and
# `tune_sighted.py`, whose `final.*` are tuned headlines). An artifact that
# DOES name its knobs and they are not the tuned ones is out regardless: that
# is rounds 1-3, kept as recorded.
_SEED_START_FIELDS = ("seed_start", "final_seed_start")


def _selection() -> tuple[dict[str, Any], int]:
    """The knobs a sweep SELECTED, and how many deals it selected them on."""
    doc = json.loads(_SELECTION.read_text())
    return dict(doc["winner"]["knobs"]), int(doc["sweep_seeds"])


def provenance_of(doc: object, knobs: Mapping[str, Any], sweep_seeds: int) -> Provenance:
    """Classify one artifact by what it records about its own deal range.

    An artifact reaches the in/out-of-sample question only by claiming the
    tuned knobs; one that ran other knobs, or records none, is making no claim
    this gate can check.
    """
    if not isinstance(doc, Mapping):
        return Provenance.UNREACHED
    tuning = doc.get("tuning")
    declares_knobs = isinstance(tuning, Mapping)
    if isinstance(tuning, Mapping):
        if any(tuning.get(knob) != value for knob, value in knobs.items()):
            return Provenance.UNREACHED
    recorded = [field for field in _SEED_START_FIELDS if field in doc]
    if not declares_knobs and not recorded:
        return Provenance.UNREACHED
    # A field that is present but unreadable is treated as a range starting at
    # deal zero rather than as no range at all: the fail-safe direction, since
    # the alternative is a malformed artifact quietly leaving the gate.
    readable = [
        int(doc[field])
        for field in recorded
        if isinstance(doc[field], (int, float)) and not isinstance(doc[field], bool)
    ]
    first_deal = min(readable) if readable else 0
    if first_deal >= sweep_seeds:
        return Provenance.OUT_OF_SAMPLE
    return Provenance.IN_SAMPLE


def _synthetic(kind: str, knobs: Mapping[str, Any], sweep_seeds: int) -> object:
    """One artifact of each shape the classifier must sort, built from the
    live knobs so the grid cannot drift away from the predicate it exercises."""
    tuned = dict(knobs)
    other = dict(knobs, hold_below=float(knobs["hold_below"]) + 1.0)
    shapes: dict[str, object] = {
        "list": [{"tuning": tuned, "seed_start": 0}],
        "no-knobs-no-range": {"pairings": []},
        "tuning-not-a-mapping-no-range": {"tuning": "base"},
        "other-knobs": {"tuning": other},
        "other-knobs-with-a-range": {"tuning": other, "seed_start": 0},
        "tuned-past-the-sweep": {"tuning": tuned, "seed_start": sweep_seeds + 300},
        "tuned-at-the-sweep": {"tuning": tuned, "seed_start": sweep_seeds},
        "tuned-inside-the-sweep": {"tuning": tuned, "seed_start": sweep_seeds - 1},
        "tuned-from-zero": {"tuning": tuned, "seed_start": 0},
        "tuned-no-seed-start": {"tuning": tuned},
        "tuned-with-extra-fields": {
            "tuning": dict(tuned, game="salvo.cardlang", results="x.json"),
            "seed_start": sweep_seeds,
        },
        "no-knobs-range-past-the-sweep": {"policies": {}, "seed_start": sweep_seeds},
        "no-knobs-range-from-zero": {"policies": {}, "seed_start": 0},
        "no-knobs-final-range-past-the-sweep": {"final": {}, "final_seed_start": sweep_seeds},
        "no-knobs-final-range-from-zero": {"final": {}, "final_seed_start": 0},
        "tuning-not-a-mapping-with-a-range": {"tuning": "base", "seed_start": 0},
    }
    return shapes[kind]


# The two axes an artifact is sorted on — does it name its knobs, and does it
# name its first deal — crossed, with the verdict each cell earns.
#
# `tuned-no-seed-start` is IN_SAMPLE rather than "unverifiable": `triage.py`'s
# `--seed-start` defaults to 0, so the absent field records a run that started
# at the sweep's first deal.
#
# The `no-knobs-*` arms are the ones that reach a rig writing no `tuning`
# block at all. Both `probe_liveness.py` and `tune_sighted.py` report the tuned
# policy through their own schema, so a gate keyed on `tuning` alone would let
# either be re-run from seed 0 — overwriting a committed headline with
# in-sample data — while staying green.
_PROVENANCE_GRID: list[tuple[str, Provenance]] = [
    ("list", Provenance.UNREACHED),
    ("no-knobs-no-range", Provenance.UNREACHED),
    ("tuning-not-a-mapping-no-range", Provenance.UNREACHED),
    ("other-knobs", Provenance.UNREACHED),
    ("other-knobs-with-a-range", Provenance.UNREACHED),
    ("tuned-past-the-sweep", Provenance.OUT_OF_SAMPLE),
    ("tuned-at-the-sweep", Provenance.OUT_OF_SAMPLE),
    ("tuned-inside-the-sweep", Provenance.IN_SAMPLE),
    ("tuned-from-zero", Provenance.IN_SAMPLE),
    ("tuned-no-seed-start", Provenance.IN_SAMPLE),
    ("tuned-with-extra-fields", Provenance.OUT_OF_SAMPLE),
    ("no-knobs-range-past-the-sweep", Provenance.OUT_OF_SAMPLE),
    ("no-knobs-range-from-zero", Provenance.IN_SAMPLE),
    ("no-knobs-final-range-past-the-sweep", Provenance.OUT_OF_SAMPLE),
    ("no-knobs-final-range-from-zero", Provenance.IN_SAMPLE),
    ("tuning-not-a-mapping-with-a-range", Provenance.IN_SAMPLE),
]


@pytest.mark.parametrize(
    ("kind", "expected"), _PROVENANCE_GRID, ids=[k for k, _ in _PROVENANCE_GRID]
)
def test_the_provenance_grid(kind: str, expected: Provenance) -> None:
    knobs, sweep = _selection()
    assert provenance_of(_synthetic(kind, knobs, sweep), knobs, sweep) is expected


def test_the_selection_artifact_still_names_its_own_sweep() -> None:
    """Both halves of the predicate are read from one artifact, so a rename or
    a schema change there would leave every cell below classifying against
    nothing. This is the pin that makes that loud rather than green.

    red under: set `sweep_seeds` to 0, or `winner.knobs` to `{}`, in
    experiments/salvo/results_tune.json. Dropping either key instead raises in
    `_selection` before this pin's own assertions run, which would be the
    module failing rather than this guard proving it can."""
    knobs, sweep = _selection()
    assert knobs, "the tuning artifact records no winning knobs"
    assert sweep > 0, f"the sweep covers {sweep} deals"


def test_the_tuned_population_is_not_empty() -> None:
    """`test_every_reported_headline_is_out_of_sample` quantifies over the
    artifacts that carry the tuned knobs. If a rename or a re-tune left that
    set empty, every one of its cells would pass by running none — the
    vacuously-green shape, which is the whole reason this gate exists.

    red under: change any key of `winner.knobs` in
    experiments/salvo/results_tune.json so it matches no artifact."""
    knobs, sweep = _selection()
    reached = [
        p
        for p in _artifacts()
        if provenance_of(json.loads(p.read_text()), knobs, sweep) is not Provenance.UNREACHED
    ]
    assert reached, "no committed artifact reports the tuned knobs"


def test_only_the_swept_experiment_records_a_deal_range() -> None:
    """`_SEED_START_FIELDS` reaches an artifact by its fields, not its
    directory, and the sweep it is judged against is salvo's. That is sound
    only while salvo is the one experiment recording a deal range at all — so
    the coupling is a pin rather than an assumption, and a green-lane or
    undertow rig that starts recording one reddens here for a ruling instead
    of being silently scored against a sweep that is not its own.

    red under: add a `seed_start` to any artifact outside experiments/salvo/."""
    strays = [
        p
        for p in _artifacts()
        if p.parent.name != "salvo"
        and isinstance(doc := json.loads(p.read_text()), Mapping)
        and any(field in doc for field in _SEED_START_FIELDS)
    ]
    assert not strays, (
        f"{[str(p.relative_to(EXPERIMENTS)) for p in strays]} record a deal range but "
        f"the sweep this gate compares against is salvo's"
    )


@pytest.mark.parametrize("artifact", _artifacts(), ids=_artifact_ids())
def test_every_reported_headline_is_out_of_sample(artifact: Path) -> None:
    knobs, sweep = _selection()
    verdict = provenance_of(json.loads(artifact.read_text()), knobs, sweep)
    assert verdict is not Provenance.IN_SAMPLE, (
        f"{artifact.relative_to(EXPERIMENTS)} reports the tuned knobs on deals the "
        f"sweep chose them from (seeds 0-{sweep - 1}); a policy scored on its own "
        f"selection deals is not evidence about those knobs"
    )


# --------------------------------------------------------------------------
# Gate 2 — a figure cited in the report equals the artifact it came from
# --------------------------------------------------------------------------


def cited_matches(cited: str, source: float) -> bool:
    """Does `cited`, as the report prints it, equal `source`?

    A citation carries its own tolerance: printed to one decimal it claims the
    source rounds there, so anything within half of the last printed place is
    the same number and anything beyond it is a different one. Both rounding
    directions are accepted at an exact tie, because the report was written by
    hand and `48.55` may legitimately appear as either.
    """
    printed_places = len(cited.partition(".")[2])
    half_ulp = 0.5 * 10.0**-printed_places
    return abs(float(cited) - source) <= half_ulp + 1e-9


# Cited-against-source pairs, authored before `cited_matches` existed. The
# tolerance is half of the last printed place: tight enough that a transcribed
# COMPLEMENT — `100 - 64.1 = 35.9` printed where the measured loss rate is
# `35.8` — is a mismatch, and loose enough that a liveness cell landing on an
# exact rounding tie is not.
_ROUNDING_GRID: list[tuple[str, float, bool]] = [
    ("35.8", 35.8, True),
    ("64.1", 64.1, True),
    ("35.9", 35.8, False),
    ("55.0", 55.0, True),
    ("48.5", 48.55, True),
    ("48.6", 48.55, True),
    ("16.6", 16.55, True),
    ("39.9", 39.85, True),
    ("48.5", 48.56, False),
    ("14.5", 14.53, True),
    ("15.0", 14.97, True),
    ("5.0", 5.01, True),
    ("6.11", 6.11, True),
    ("22.0", 21.97, True),
    ("22", 21.97, True),
    ("21", 21.97, False),
]


@pytest.mark.parametrize(("cited", "source", "expected"), _ROUNDING_GRID)
def test_the_rounding_grid(cited: str, source: float, expected: bool) -> None:
    assert cited_matches(cited, source) is expected


@dataclass(frozen=True)
class Table:
    """One markdown table, with the section heading it sits under."""

    section: str
    header: tuple[str, ...]
    rows: tuple[tuple[str, ...], ...]


def _cells(line: str) -> tuple[str, ...]:
    return tuple(c.strip() for c in line.strip().strip("|").split("|"))


def _tables(md: str) -> list[Table]:
    """Every markdown table in `md`, tagged with its section.

    A heading may wrap across two `##` lines (§9 does), so the section name
    accumulates until a blank line rather than being the first line alone.
    """
    out: list[Table] = []
    lines = md.splitlines()
    section = ""
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if line.startswith("## "):
            section = line[3:].strip()
            while i + 1 < len(lines) and lines[i + 1].strip().startswith("## "):
                i += 1
                section += " " + lines[i].strip()[3:].strip()
        # Leading whitespace is stripped before every test, so an indented
        # table is found rather than passing unseen — the shape that would
        # make `test_every_table_in_the_report_is_accounted_for`'s superset
        # claim false.
        if (
            line.startswith("|")
            and i + 1 < len(lines)
            and re.fullmatch(r"\|[-|: ]+\|", lines[i + 1].strip())
        ):
            header = _cells(line)
            i += 2
            rows: list[tuple[str, ...]] = []
            while i < len(lines) and lines[i].strip().startswith("|"):
                rows.append(_cells(lines[i].strip()))
                i += 1
            out.append(Table(section, header, tuple(rows)))
            continue
        i += 1
    return out


# The report's own section names, by the substring that identifies each. The
# scoreboard's heading wraps two lines; matching on a substring keeps that
# detail out of the map.
_SCOREBOARD_SECTION = "adopted game's scoreboard"
_LIVENESS_SECTION = "10. Location liveness"

# §9: rows join `pairings[].pairing`; the `win rate` cell prints the two sides
# of that pairing in the order the label names them. `reading` is authored
# prose and cites nothing.
_SCOREBOARD_ARTIFACT = "results_triage_base.json"
_SCOREBOARD_KEY = "pairing"
_SCOREBOARD_VALUES = "win rate"
_SCOREBOARD_PROSE = ("reading",)

# §10: rows are the three bins under the `sighted` policy, which the prose
# above the table selects. The last column prints two fields in one cell.
_LIVENESS_ARTIFACT = "results_liveness.json"
_LIVENESS_KEY = "bin"
_LIVENESS_POLICY = "sighted"
_LIVENESS: dict[str, tuple[str, bool]] = {
    "cards": ("mean_cards", False),
    "card-distance": ("mean_distance", False),
    "affinity": ("affinity_rate", True),
    "margin": ("margin_mean", False),
    "unclaimed": ("unclaimed_rate", True),
    "least-contested (vs share)": ("least_contested_share", True),
}
_LIVENESS_LAST_COLUMN = "least-contested (vs share)"
_LIVENESS_PARENTHETICAL = ("appearance_share", True)

# Tables in the report that no binder claims yet, held as a named set so a
# table added to the report fails `test_every_table_in_the_report_is_accounted_
# for` instead of joining the unchecked majority. Both describe rounds 1-3 and
# want a per-cell filename convention (issue #419).
_UNBOUND_SECTIONS = ("2. Not double solitaire", "8. Round 3")


def _numbers(cell: str) -> list[str]:
    """The numeric tokens a report cell prints, in order, markup stripped."""
    # The sign is part of the number: without it a cell printing `-0.12`
    # against an artifact holding `+0.12` reads as a correct citation. The
    # lookbehind keeps a range (`5-8`) from being read as a negative.
    return re.findall(r"(?<!\d)-?\d+(?:\.\d+)?", cell.replace("**", ""))


def cell_mismatches(report: str) -> list[str]:
    """Every bound cell in `report` whose printed value is not its artifact's.

    Takes the report text rather than reading the file, so a probe can mutate a
    copy and prove this reports the mutation.
    """
    found: list[str] = []
    for table in _tables(report):
        if _SCOREBOARD_SECTION in table.section:
            found += _scoreboard_mismatches(table)
        elif _LIVENESS_SECTION in table.section:
            found += _liveness_mismatches(table)
    return found


def _artifact(name: str) -> Any:
    return json.loads((_SALVO / name).read_text())


def _columns(table: Table, wanted: list[str]) -> tuple[dict[str, int], list[str]]:
    index = {header: i for i, header in enumerate(table.header)}
    return index, [w for w in wanted if w not in index]


def _scoreboard_mismatches(table: Table) -> list[str]:
    """Each row names its two policies; the cell prints their two win rates in
    that order, as percentages of the artifact's fractions."""
    doc = _artifact(_SCOREBOARD_ARTIFACT)
    pairings = doc.get("pairings") if isinstance(doc, Mapping) else None
    if not isinstance(pairings, list):
        return [f"{_SCOREBOARD_ARTIFACT} records no `pairings` list"]
    by_pairing = {
        entry["pairing"]: entry
        for entry in pairings
        if isinstance(entry, Mapping) and "pairing" in entry
    }
    index, missing = _columns(table, [_SCOREBOARD_KEY, _SCOREBOARD_VALUES])
    if missing:
        return [f"the scoreboard table no longer prints {missing}"]
    found: list[str] = []
    for row in table.rows:
        if len(row) < len(table.header):
            found.append(f"a scoreboard row prints {len(row)} cells for {len(table.header)} columns")
            continue
        label = row[index[_SCOREBOARD_KEY]]
        entry = by_pairing.get(label)
        if entry is None:
            found.append(f"{label}: no pairing of that name in {_SCOREBOARD_ARTIFACT}")
            continue
        rates = entry.get("win_rate")
        if not isinstance(rates, Mapping):
            found.append(f"{label}: no win_rate recorded in {_SCOREBOARD_ARTIFACT}")
            continue
        sides = [side.strip() for side in label.split(" vs ")]
        printed = _numbers(row[index[_SCOREBOARD_VALUES]])
        if len(printed) != len(sides):
            found.append(f"{label}: cell prints {len(printed)} numbers for {len(sides)} sides")
            continue
        for side, text in zip(sides, printed):
            source = rates.get(side)
            if not isinstance(source, (int, float)):
                found.append(f"{label}: {side} has no win rate in {_SCOREBOARD_ARTIFACT}")
            elif not cited_matches(text, source * 100.0):
                found.append(f"{label}: {side} printed {text}, artifact has {source * 100:.3f}")
    return found


def _liveness_mismatches(table: Table) -> list[str]:
    """Each row is one bin of the policy the prose selects; the last column
    prints a second field in parentheses."""
    doc = _artifact(_LIVENESS_ARTIFACT)
    policies = doc.get("policies") if isinstance(doc, Mapping) else None
    bins = policies.get(_LIVENESS_POLICY) if isinstance(policies, Mapping) else None
    if not isinstance(bins, Mapping):
        return [f"{_LIVENESS_ARTIFACT} records no `{_LIVENESS_POLICY}` policy"]
    index, missing = _columns(table, [_LIVENESS_KEY, *_LIVENESS])
    if missing:
        return [f"the liveness table no longer prints {missing}"]
    found: list[str] = []
    for row in table.rows:
        if len(row) < len(table.header):
            found.append(f"a liveness row prints {len(row)} cells for {len(table.header)} columns")
            continue
        name = row[index[_LIVENESS_KEY]]
        record = bins.get(name)
        if not isinstance(record, Mapping):
            found.append(f"{name}: no bin of that name under {_LIVENESS_POLICY}")
            continue
        for header, mapped in _LIVENESS.items():
            fields = [mapped]
            if mapped[0] == _LIVENESS[_LIVENESS_LAST_COLUMN][0]:
                fields.append(_LIVENESS_PARENTHETICAL)
            printed = _numbers(row[index[header]])
            if len(printed) != len(fields):
                found.append(
                    f"{name}/{header}: prints {len(printed)} numbers for {len(fields)} fields"
                )
                continue
            for text, (field, percent) in zip(printed, fields):
                # `probe_liveness.py` writes null for a bin that appeared with
                # no cards committed, so an absent number is a shape this
                # reports rather than a shape it can assume away.
                raw = record.get(field)
                if not isinstance(raw, (int, float)) or isinstance(raw, bool):
                    found.append(f"{name}/{header}: {field} records no number")
                    continue
                source = raw * 100.0 if percent else float(raw)
                if not cited_matches(text, source):
                    found.append(f"{name}/{header}: printed {text}, {field} is {source:.3f}")
    return found


def test_the_report_cites_its_artifacts_correctly() -> None:
    """Born green: every bound cell already equals its source. The probes below
    carry the reddening mutations, run rather than described."""
    assert cell_mismatches(_REPORT.read_text()) == []


def _row_labels(section: str) -> list[str]:
    return [
        row[0]
        for table in _tables(_REPORT.read_text())
        if section in table.section
        for row in table.rows
    ]


def test_the_liveness_table_prints_every_bin_it_is_bound_to() -> None:
    """Rows are an axis of the domain, and `cell_mismatches` walks the rows the
    REPORT prints — so a deleted row leaves the population silently and the
    citation pin stays green over what remains. The liveness table's row set is
    not a matter of taste: it is the policy's bins, so it is pinned equal to
    them rather than merely non-empty.

    red under: delete any bin row from the §10 table of
    experiments/salvo/REPORT.md."""
    bins = _artifact(_LIVENESS_ARTIFACT)["policies"][_LIVENESS_POLICY]
    assert set(_row_labels(_LIVENESS_SECTION)) == set(bins), (
        f"the liveness table prints {sorted(_row_labels(_LIVENESS_SECTION))} for bins "
        f"{sorted(bins)}"
    )


# The scoreboard quotes a chosen subset of the artifact's pairings — the five
# that carry the skill argument — so its row set is a declaration rather than
# the artifact's own. Naming it here is what makes a deleted row loud.
_SCOREBOARD_ROWS = frozenset(
    {
        "sighted vs blind",
        "sighted vs sighted_nohold",
        "sighted vs blind_hold",
        "blind_hold vs blind",
        "sighted_nohold vs blind",
    }
)


def test_the_scoreboard_prints_the_rows_it_is_bound_to() -> None:
    """red under: delete any row from the §9 table of
    experiments/salvo/REPORT.md."""
    printed = set(_row_labels(_SCOREBOARD_SECTION))
    assert printed == _SCOREBOARD_ROWS, f"the scoreboard prints {sorted(printed)}"
    recorded = {entry["pairing"] for entry in _artifact(_SCOREBOARD_ARTIFACT)["pairings"]}
    assert _SCOREBOARD_ROWS <= recorded, (
        f"{sorted(_SCOREBOARD_ROWS - recorded)} is quoted but not measured"
    )


def test_each_bound_section_names_the_artifact_its_cells_are_read_from() -> None:
    """The binder holds the filename and the section's prose tells a reader
    which file to check. Nothing makes those the same string, so the report can
    send a reader to one artifact while the gate reads another — and a citation
    reported correct would be correct about the wrong file.

    red under: change either `results_*.json` filename in the prose of §9 or
    §10 of experiments/salvo/REPORT.md."""
    report = _REPORT.read_text()
    for section, artifact in (
        (_SCOREBOARD_SECTION, _SCOREBOARD_ARTIFACT),
        (_LIVENESS_SECTION, _LIVENESS_ARTIFACT),
    ):
        start = report.index(section)
        body = report[start : start + 2500]
        assert artifact in body, f"§{section!r} never names {artifact}, which its cells come from"


def test_every_table_in_the_report_is_accounted_for() -> None:
    """Completeness by superset over the pipe tables `_tables` parses: a table
    is bound or it is named unbound, so a new one belongs to neither set and
    reddens here rather than joining the unchecked majority. The superset is
    the parser's — a borderless or HTML table is outside it, which is the
    `domain:` boundary rather than a hole this pin covers.

    red under: add a markdown table under any other section of
    experiments/salvo/REPORT.md."""
    known = (_SCOREBOARD_SECTION, _LIVENESS_SECTION, *_UNBOUND_SECTIONS)
    for table in _tables(_REPORT.read_text()):
        assert any(k in table.section for k in known), (
            f"the table under {table.section!r} is neither bound to an artifact "
            f"nor listed as unbound"
        )


def test_the_bound_tables_are_present() -> None:
    """The other half of the superset: a section renamed out from under a
    binder would leave its cells unchecked while everything above stayed green.

    red under: rename either bound section heading in
    experiments/salvo/REPORT.md."""
    sections = [t.section for t in _tables(_REPORT.read_text())]
    for name in (_SCOREBOARD_SECTION, _LIVENESS_SECTION):
        assert any(name in s for s in sections), f"no table sits under {name!r}"


def test_every_liveness_column_is_mapped() -> None:
    """The column map is hand-written — the one axis this module cannot derive
    — so a renamed column must fail rather than drop its check.

    red under: rename a column header in the §10 table of
    experiments/salvo/REPORT.md."""
    (table,) = [t for t in _tables(_REPORT.read_text()) if _LIVENESS_SECTION in t.section]
    assert set(table.header) == {_LIVENESS_KEY} | set(_LIVENESS), (
        f"the liveness table prints {sorted(table.header)}, the map covers "
        f"{sorted({_LIVENESS_KEY} | set(_LIVENESS))}"
    )


def test_every_scoreboard_column_is_mapped() -> None:
    """red under: rename a column header in the §9 table of
    experiments/salvo/REPORT.md."""
    (table,) = [t for t in _tables(_REPORT.read_text()) if _SCOREBOARD_SECTION in t.section]
    assert set(table.header) == {_SCOREBOARD_KEY, _SCOREBOARD_VALUES, *_SCOREBOARD_PROSE}


# --- misuse probes: the mutations the born-green pins above cannot run -----


def test_a_transcribed_complement_is_caught() -> None:
    """A loss rate printed as `100 - win rate` instead of the measured value.
    One tenth of a point separates the two, which is why the tolerance is half
    of the last printed place rather than a round number."""
    mutated = _REPORT.read_text().replace("**64.1 / 35.8**", "**64.1 / 35.9**")
    assert "35.9" in mutated, "the probe did not apply"
    found = cell_mismatches(mutated)
    assert any("sighted vs blind" in m for m in found), found


def test_a_wrong_field_in_a_bound_cell_is_caught() -> None:
    """A cell reading a real number from the wrong row of the right file — the
    shape that stays plausible, so no reader catches it."""
    mutated = _REPORT.read_text().replace("| 55.0 / 44.5 |", "| 58.4 / 41.1 |")
    found = cell_mismatches(mutated)
    assert any("sighted vs blind_hold" in m for m in found), found


def test_a_liveness_cell_that_drifts_is_caught() -> None:
    """The parenthesised second field of the last column is a whole column's
    worth of citation hiding inside another cell; it is checked like any other.

    The mutation is one printed place, which is what a re-run would move."""
    mutated = _REPORT.read_text().replace("| 16.6% (22.0%) |", "| 16.6% (23.0%) |")
    found = cell_mismatches(mutated)
    assert any("mid" in m for m in found), found


def test_a_row_label_matching_no_record_is_refused() -> None:
    """A row whose label stops joining its artifact must fail, not vanish from
    the population — the silent-skip shape this module exists to refuse."""
    mutated = _REPORT.read_text().replace(
        "| sighted vs blind_hold |", "| sighted vs blind_hold_10 |"
    )
    found = cell_mismatches(mutated)
    assert any("blind_hold_10" in m for m in found), found
