"""T5: declaration reorder — pairing tests, structural preconditions, and
completeness ledger.

property:   reversing `game.zones`, `game.move_types`, `game.rules`, and
            every `StateBlock`'s `decls` (reorder.py) does not change a
            playout's observable trace or terminal result; and reordering
            does not change which diagnostic (by message) a rejected program
            gets.
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
            there is exactly one) and
            `test_no_state_default_reads_a_sibling` (state-decl order is
            irrelevant to `_declare_state` only because no default
            expression reads a same-block sibling). Plus one ANTI-VACUITY
            pin, `test_reorder_actually_changes_every_game`: reversal is the
            identity on a list of length <= 1, so a game small enough would
            pair against an equal tree — the same object once `_check` is
            memoized — and pass for free. The zones axis covers
            every game: a gather visits zones in canonical sorted-name order
            (`execute.py::_gather`; decisions.md "Loop lifecycle"), the
            canonicalization that retired this suite's original gather-order
            finding and its per-game exclusion.
sampled:    seeds and decision depth only (CI budget) — pairing.py.
residual:   `game.phases` and phase-body statement sequences — EXCLUDED, not
            deferred: decisions.md affirmatively says phase/statement order
            IS meaningful ("Sub-phase entry and exit"), so there is no
            metamorphic property to check there. Not a gap; see reorder.py's
            module docstring.
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
from tests.metamorphic.reorder import reorder_declarations

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
_PARSE_LEVEL_CASES = frozenset(
    {
        "syntax_error",
        # The game-skeleton walls in parse.py's `game()`/`start()` builders
        # (missing/duplicated single-valued clauses, content-clause mutual
        # exclusion, game-count errors) — rejected before any tree exists to
        # reorder.
        "missing_cards_declaration",
        "missing_players_declaration",
        "missing_players_and_cards",
        "duplicate_game_clause",
        "duplicate_pieces_clause",
        "board_duplicate_clause",
        "pieces_and_cards_together",
        "no_game_block",
        "two_game_blocks",
        # The collection-quantifier register has no `number of <noun> in
        # <expr> where ...` production -- a raw grammar dead end, not a
        # resolve wall (roadmap.md "Positional zones -- walled residuals").
        "cell_count_in_collection_not_admitted",
    }
)

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
def test_reorder_actually_changes_every_game(path: Path) -> None:
    """The anti-vacuity pin `test_rename.py::test_every_game_renames_something`
    and `test_inline.py::test_splice_removes_every_procedure_construct` already
    have, and reorder lacked.

    Reversal is the identity on a list of length <= 1, so a game with at most
    one zone, move type, rule, and state decl per block would reorder to an
    EQUAL tree. Since `parse_text`/`_check` are memoized (cardlang/parse.py,
    Contract), an equal tree is the SAME checked object, and that game's
    pairing case would compare a thing to itself and pass for free —
    "vacuously green" in decisions.md's sense, and invisible in a green run.
    Today the corpus minimum is 3 zones, so this holds with room; it is pinned
    because the pairing harness's docstring claims the transformed side ALWAYS
    takes a fresh key, and "always" is a wall or it is nothing."""
    game = pairing.parse_corpus_game(path)
    assert reorder_declarations(game) != game, (
        f"{path.name}: reorder is the identity on this game — its pairing case "
        "compares the tree to itself and cannot fail"
    )


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
