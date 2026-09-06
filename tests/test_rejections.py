"""The rejection corpus: designer-facing diagnostics as pinned artifacts.

Misuse-probe rejection tests today live scattered as inline DSL strings
across per-module test files (`grep -rl DiagnosticError tests/`), each
asserting a substring of the message. That proves a guard still fires; it
does not prove the MESSAGE a designer actually reads still reads the same
way. `tests/rejections/` is a rustc-"ui test"-style corpus that promotes the
rendered diagnostic itself to a regression-tested artifact: one deliberately
broken game per named guard class (`<case>.cardlang`), paired with a golden
of exactly what the front end prints for it (`<case>.expected`).

This module is additive. It does not migrate or delete the scattered
per-module rejection tests — those stay as the fine-grained proof that a
guard fires from the right AST shape; this corpus is the coarse-grained proof
that the message a human reads is still the message that was written.

Rendering
---------
The rendering reuses `cardlang/cli.py`'s own format rather than inventing a
second one: the primary diagnostic's `source:line:col: severity: message`
line (`Diagnostic.format()`), followed by one line per note the stage
attached (`DiagnosticError.add_note`, surfaced as `__notes__` — a stage
that collects more than one error attaches the rest of the bag as a note so
nothing is silently dropped). `check_dsl` is called with the case's own
filename as `source_name`, not its absolute path, so a golden is portable
across machines and checkout locations.

Regenerating goldens
---------------------
This is a DELIBERATE, reviewed act, not a routine part of running the
suite: set `REJECTIONS_BLESS=1` to rewrite every `.expected` file to match
the current rendering, then read the diff before committing it — a bless
can just as easily paper over a real message regression as capture an
intended one.

    REJECTIONS_BLESS=1 pytest -q tests/test_rejections.py

Completeness ledger (decisions.md "Closed-domain completeness")
-----------------------------------------------------------------
property:   every `.cardlang` file in `tests/rejections/` is rejected by
            `cardlang.pipeline.check_dsl` with a `DiagnosticError` (a case
            that passes the pipeline is itself a test failure — this corpus
            contains only rejected programs), and its rendered diagnostic
            matches its `.expected` golden byte-for-byte.
domain:     the file-pair registry — `tests/rejections/*.cardlang` paired
            with `tests/rejections/*.expected`, one pair per named guard
            class. The population it samples FROM is open rather than
            closed: every diagnostic emission site across `cardlang/parse.py`,
            `cardlang/resolve.py`, `cardlang/typecheck.py` and
            `cardlang/deckcheck.py` is a guard class, and the set grows as
            the language does — a new checker rule is a new guard, and it
            ships its own case with it (docs/building.md). Procedure
            hygiene sits in that population as ONE case rather than
            several, and that is a boundary rather than a thin spot:
            hygiene is closed BY CONSTRUCTION, with exactly one guard
            expansion cannot replace — the binder-shadow case — and both
            `cardlang/expand.py`'s docstring and tests/test_procedures.py's
            own completeness ledger state it.
registry:   the directory itself. `test_every_cardlang_case_has_a_matching_expected`
            pins both directions of the glob (mirrors the idiom in
            `tests/openspiel_ready/test_coverage.py`): an orphan `.cardlang`
            with no golden, or a golden with no source, fails the harness
            rather than being silently skipped or silently stale. The
            properties the `syntax_*` cases share —
            tests/test_parse_diagnostics.py.
does not prove:  that every diagnostic a designer can reach still reads
            the way it was written. The cases are representative guard
            classes, one seed per class over an open population, so a guard
            with no case here has no golden at all; what stands for those is
            the scattered per-module `DiagnosticError` tests, which prove
            that a guard FIRES rather than what it PRINTS.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from cardlang.diagnostics import DiagnosticError
from cardlang.pipeline import check_dsl

REJECTIONS_DIR = Path(__file__).parent / "rejections"

# A deliberate, reviewed act (see module docstring) — never flipped on by
# routine `pytest` runs.
BLESS = os.environ.get("REJECTIONS_BLESS") == "1"


def _render(exc: DiagnosticError) -> str:
    """The stable rendering: `cardlang/cli.py`'s own format, reused so the
    corpus pins exactly what `cardlang <file>` prints to a designer — the
    primary diagnostic line, then one line per attached note. Most cases
    raise a single diagnostic; the multi-error bag cases (e.g.
    missing_players_and_cards, whose stage attaches the rest of the bag as
    a note) exercise the notes branch."""
    lines = [exc.diagnostic.format()]
    notes: list[str] = list(getattr(exc, "__notes__", None) or [])
    lines.extend(notes)
    return "\n".join(lines) + "\n"


def _case_names() -> list[str]:
    return sorted(p.stem for p in REJECTIONS_DIR.glob("*.cardlang"))


def test_every_cardlang_case_has_a_matching_expected() -> None:
    """Glob<->glob pinning over the corpus directory (mirrors
    `tests/openspiel_ready/test_coverage.py`'s registry<->module pin): an
    orphan `.cardlang` with no golden, or a golden with no `.cardlang`,
    fails loud instead of being silently skipped."""
    cardlang_stems = {p.stem for p in REJECTIONS_DIR.glob("*.cardlang")}
    expected_stems = {p.stem for p in REJECTIONS_DIR.glob("*.expected")}
    assert cardlang_stems == expected_stems, (
        "tests/rejections/ .cardlang/.expected pairs disagree: "
        f"missing .expected={sorted(cardlang_stems - expected_stems)}, "
        f"orphan .expected={sorted(expected_stems - cardlang_stems)}"
    )
    # A floor, not just a pairing check: an empty (or emptied) directory
    # would make both the set-equality above AND the parametrized run below
    # vacuously green — zero cases "passing" proves nothing (decisions.md
    # "Closed-domain completeness", "vacuously green"). 12 ties this to the
    # task's stated minimum seed count, so the corpus shrinking below its
    # commissioned size fails loud instead of silently.
    assert len(cardlang_stems) >= 12, (
        f"tests/rejections/ has only {len(cardlang_stems)} case(s) — the "
        "corpus is meant to hold at least one case per named guard class "
        "(12+); an emptied or broken glob must not go unnoticed"
    )


@pytest.mark.parametrize("case", _case_names())
def test_rejection_case(case: str) -> None:
    """Every case must fail `check_dsl` with a `DiagnosticError` — a case
    that passes the pipeline is a test failure, not a silent no-op, since
    this corpus's entire premise is "every file here is rejected" — and the
    rendered diagnostic must match its golden byte-for-byte."""
    source_path = REJECTIONS_DIR / f"{case}.cardlang"
    expected_path = REJECTIONS_DIR / f"{case}.expected"
    text = source_path.read_text()

    # `pytest.raises` itself supplies the "this corpus contains only
    # rejected programs" guarantee: a case accepted by check_dsl fails here
    # with pytest's own "DID NOT RAISE" message rather than a hand-rolled one.
    with pytest.raises(DiagnosticError) as excinfo:
        check_dsl(text, f"{case}.cardlang")
    rendered = _render(excinfo.value)

    if BLESS:
        expected_path.write_text(rendered)
        return

    expected = expected_path.read_text()
    assert rendered == expected, (
        f"{case}: rendered diagnostic drifted from "
        f"tests/rejections/{case}.expected — inspect the change, then "
        "re-run with REJECTIONS_BLESS=1 if it is intended"
    )
