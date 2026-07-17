"""T5: declaration reorder — pairing tests, structural preconditions, and
completeness ledger.

property:   reversing `game.move_types`, `game.rules`, and every
            `StateBlock`'s `decls` (reorder.py) does not change a playout's
            observable trace or terminal result; reversing `game.zones` too,
            for the games where that is additionally sound (`_has_gather`);
            and reordering does not change which diagnostic (by message) a
            rejected program gets.
domain:     corpus games (`pairing.CORPUS`) x seeds (`pairing.SEEDS`) for the
            playout property; `tests/rejections/*.cardlang` for the
            diagnostic property.
registry:   docs/games/*.cardlang (`pairing.CORPUS`); tests/rejections/ (the
            same registry `tests/test_rejections.py` glob-pins).
covered:    every corpus game (exhaustive), every seed in `pairing.SEEDS`;
            every rejection-corpus case that PARSES (exhaustive,
            `REJECTIONS_DIR.glob` minus `_PARSE_LEVEL_CASES` — a parse-level
            case has no declaration list to permute, so it is outside the
            transform's domain by construction; the membership is pinned in
            both directions, and the case's diagnostic stays pinned by
            tests/test_rejections.py).
            Two structural PRECONDITIONS reorder.py's soundness argument
            depends on are pinned as their own tests, not assumed:
            `test_every_game_has_exactly_one_deck_zone` (zone order is
            irrelevant to `driver.py`'s `next(... "Deck" ...)` only because
            there is exactly one — this precondition matters only for the
            games where zones ARE reordered, i.e. `not _has_gather`) and
            `test_no_state_default_reads_a_sibling` (state-decl order is
            irrelevant to `_declare_state` only because no default
            expression reads a same-block sibling).
sampled:    seeds and decision depth only (CI budget) — pairing.py.
residual:   `game.phases` and phase-body statement sequences — EXCLUDED, not
            deferred: decisions.md affirmatively says phase/statement order
            IS meaningful ("Sub-phase entry and exit"), so there is no
            metamorphic property to check there. Not a gap; see reorder.py's
            module docstring. `game.zones` for the 13 corpus games with a
            "gather" movement — EXCLUDED, a REAL finding (`execute.py::
            _gather` couples a gather's observable event order to zone
            declaration order via `ZoneStore`'s dict-insertion order), not a
            defect in this transform; recorded in reorder.py's module
            docstring and the task's report, not fixed (constraints: no
            `cardlang/` changes). `test_zones_reordered_iff_no_gather` pins
            which games get which treatment so the exclusion cannot silently
            widen or narrow without a test noticing.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from cardlang.ast import nodes as n
from cardlang.diagnostics import DiagnosticError
from cardlang.parse import parse_text
from cardlang.pipeline import _check
from cardlang.resolve import _walk

from tests.metamorphic import pairing
from tests.metamorphic.reorder import plan_for, reorder_declarations

REJECTIONS_DIR = Path(__file__).parent.parent / "rejections"
REJECTION_CASES = sorted(p.stem for p in REJECTIONS_DIR.glob("*.cardlang"))

# Rejection-corpus cases whose rejection happens AT PARSE. A parse-level case
# has no tree, so declaration reorder is inapplicable to it by construction —
# it is outside this transform's domain, and its diagnostic is pinned by
# tests/test_rejections.py instead. The set is pinned BOTH ways in
# test_reorder_preserves_rejection_diagnostics: a case here that starts
# parsing, or a case not here that stops parsing, fails loudly — the
# alternative (skip on parse failure) would let a parse regression silently
# shrink the diagnostic property's domain.
_PARSE_LEVEL_CASES = frozenset({"syntax_error"})

# The corpus games with no "gather" movement (`Movement(source=None)`),
# where `game.zones` IS additionally reordered — hand-checked once (against
# `_has_gather`'s own logic, independently) so a change to either side is
# caught by `test_zones_reordered_iff_no_gather` rather than the two silently
# drifting in lockstep.
_NO_GATHER_GAMES = frozenset({"coup.cardlang", "getaway.cardlang", "go-fish.cardlang", "gops.cardlang"})


def _names_in(expr: n.Expr) -> set[str]:
    return {nd.name for nd in _walk(expr) if isinstance(nd, n.NameRef)}


@pytest.mark.parametrize("path", pairing.CORPUS, ids=lambda p: p.name)
def test_every_game_has_exactly_one_deck_zone(path: Path) -> None:
    """reorder.py's precondition for zones: `driver.py` picks `next(z.name
    for z in game.zones if z.type_ref.name == "Deck")` — order-irrelevant
    only when exactly one such zone exists."""
    game = pairing.parse_corpus_game(path)
    decks = [z.name for z in game.zones if z.type_ref.name == "Deck"]
    assert len(decks) == 1, f"{path.name}: {len(decks)} Deck-typed zones, expected 1"


@pytest.mark.parametrize("path", pairing.CORPUS, ids=lambda p: p.name)
def test_no_state_default_reads_a_sibling(path: Path) -> None:
    """reorder.py's precondition for state variables: `_declare_state`
    evaluates each default in list order, so reordering is safe only if no
    default expression reads another declaration from the SAME block."""
    game = pairing.parse_corpus_game(path)
    for nd in _walk(game):
        if not isinstance(nd, n.StateBlock):
            continue
        siblings = {d.name for d in nd.decls}
        for d in nd.decls:
            leaked = (_names_in(d.default) & siblings) - {d.name}
            assert not leaked, (
                f"{path.name}: state var '{d.name}' default reads sibling(s) "
                f"{sorted(leaked)} from the same block — reordering that "
                f"block would change evaluation order"
            )


@pytest.mark.parametrize("path", pairing.CORPUS, ids=lambda p: p.name)
def test_zones_reordered_iff_no_gather(path: Path) -> None:
    """Pins WHICH games get the zones exclusion, independently of
    `_has_gather`'s own logic (reorder.py module docstring), so a future
    corpus game landing in the wrong bucket is a loud test failure rather
    than a silent widening or narrowing of the exclusion."""
    game = pairing.parse_corpus_game(path)
    plan = plan_for(game)
    expected = path.name in _NO_GATHER_GAMES
    assert plan.zones_reordered == expected, (
        f"{path.name}: zones_reordered={plan.zones_reordered}, expected "
        f"{expected} — update _NO_GATHER_GAMES if this game's gather usage "
        f"genuinely changed, after re-verifying reorder.py's citation"
    )


@pytest.mark.parametrize("path", pairing.CORPUS, ids=lambda p: p.name)
@pytest.mark.parametrize("seed", pairing.SEEDS)
def test_reordered_game_plays_out_identically(path: Path, seed: int) -> None:
    a, b = pairing.run_pair(path, reorder_declarations, seed)
    witness = pairing.compare_traces(a, b)  # nothing renamed: identity hook
    assert witness is None, f"{path} seed={seed}: {witness}"


@pytest.mark.parametrize("case", REJECTION_CASES)
def test_reorder_preserves_rejection_diagnostics(case: str) -> None:
    """Every rejection-corpus case must still be rejected after reordering,
    with the SAME diagnostic MESSAGE (not the full `source:line:col:`
    rendering — reorder.py's module docstring explains why a duplicate-name
    case's span can legitimately move)."""
    path = REJECTIONS_DIR / f"{case}.cardlang"
    text = path.read_text()
    try:
        parsed = parse_text(text, f"{case}.cardlang")
    except DiagnosticError:
        assert case in _PARSE_LEVEL_CASES, (
            f"{case}: stopped parsing — either a parse regression, or a new "
            "parse-level rejection case; if the latter, add it to "
            "_PARSE_LEVEL_CASES (its diagnostic stays pinned by "
            "tests/test_rejections.py)."
        )
        return
    assert case not in _PARSE_LEVEL_CASES, (
        f"{case}: is registered parse-level but now parses — remove it from "
        "_PARSE_LEVEL_CASES so the reorder property covers it again."
    )

    with pytest.raises(DiagnosticError) as before:
        _check(parsed)
    reordered = reorder_declarations(parsed)
    with pytest.raises(DiagnosticError) as after:
        _check(reordered)

    assert before.value.diagnostic.message == after.value.diagnostic.message, (
        f"{case}: reordering changed the diagnostic — "
        f"before={before.value.diagnostic.message!r} "
        f"after={after.value.diagnostic.message!r}"
    )
