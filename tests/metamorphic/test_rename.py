"""T2: alpha-rename — pairing tests and completeness ledger.

property:   renaming every zone and state-variable declaration (a fresh,
            game-wide-unique spelling — rename.py) and every reference to it
            does not change a playout's observable trace or terminal result.
domain:     corpus games (`pairing.CORPUS`) x seeds (`pairing.SEEDS`).
registry:   docs/games/*.cardlang (`pairing.CORPUS`) — every corpus game.
covered:    every corpus game (exhaustive, parametrized below), every seed
            in `pairing.SEEDS` (widened via `CARDLANG_METAMORPHIC_SEEDS` for
            a deeper local run); `test_every_game_renames_something` pins
            that the rename is never vacuous (a game with no renamable name
            would make the pairing check trivially/silently true).
sampled:    seeds and decision depth only (CI budget) — see
            `CARDLANG_METAMORPHIC_STEPS`/`CARDLANG_METAMORPHIC_SEEDS` in
            pairing.py.
residual:   Three exclusion categories, each on its own `RenamePlan` field,
            none silent:
            (1) `unsafe` — a zone/state name locally shadowed somewhere by a
                same-spelled binder (rename.py, defense 2). EMPTY for the
                whole corpus today; `test_no_corpus_game_has_an_unsafe_name`
                pins this and fails loudly the day some future game trips
                it.
            (2) `excluded_global` — `hand`, the language-wide magic zone
                name decisions.md "Declared parameter domains" and
                `resolve.py` require for `Card`-typed move parameters. Out
                of T2's domain by the spec's own words, not a defect.
            (3) `excluded_coupled` — per-game names a game-local primitive
                module reads (the sanctioned "game-local Primitive"
                pattern, kernel-migration.md), DERIVED from the declared-
                reads registry (`PRIMITIVE_READS`,
                cardlang/runtime/reads.py) — the class this transform first
                surfaced empirically as a playout `KeyError`, since closed:
                the registry is pinned two ways by
                tests/test_primitive_reads.py (against each game file's
                declarations and against each module's accessor-call
                literals), so these names are known-coupled by
                declaration, not by hand-list. Every corpus game still has
                a nonempty safe set (`test_every_game_renames_something`),
                so no game is entirely excluded from the property this
                suite checks.
                The exclusion is REGIME-scoped, and a game that declares a
                `primitives { }` block is outside it: its Primitive reads
                are declared in its own file, so the transform renames the
                declaration along with the zone and the checker refuses a
                `reads` name that no longer resolves. What this transform
                can no longer observe for such a game is the coupling
                itself — there is nothing left to observe, because one edit
                in one file moves both sides, which is a stronger statement
                than the exclusion it replaces. The names it excludes are
                exactly those whose reading side is Python this transform
                cannot rewrite.

            A FOURTH residual, on the interaction between (3) and the
            gather rather than on any one field. `move all cards to <zone>`
            collects its sources in sorted ZONE-NAME order (decisions.md,
            the gather paragraph), and this transform renames only the
            names outside the exclusion sets — so when a game reaches a
            gather with cards in BOTH an excluded zone and a renamed one,
            the rename reorders the collection, the deck stacks
            differently, and the next shuffle diverges. The property fails
            on a game that is correct: a FALSE POSITIVE, not a missed
            defect.
            Hold'em surfaced this empirically (its `board` is
            primitive-coupled, so it is excluded, and it held the five
            community cards at the hand-end gather while `burn`/`muck` were
            renamed; `_mt_` sorts before every real name, so `board` moved
            from first to last). Hold'em no longer triggers it — it mucks
            the spent board, as Stud mucks its spent hands, which is the
            right modelling independently of this suite — and no corpus game
            triggers it today. The hazard that remains is for a FUTURE game:
            the failure names a diverging event, not a naming artifact, so
            the tempting repair is to distort the game until the transform
            is happy. Read this note first instead. Closing it properly
            means either renaming the coupled names too (they are excluded
            because a primitive module spells them, which the
            `primitives { }` block of design-notes/primitive-sidecars.md
            would make renamable) or making the gather order independent of
            spelling. Recorded as issue #194.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.metamorphic import pairing
from tests.metamorphic.rename import alpha_rename, build_rename_plan, trace_rename


@pytest.mark.parametrize("path", pairing.CORPUS, ids=lambda p: p.name)
def test_every_game_renames_something(path: Path) -> None:
    parsed = pairing.parse_corpus_game(path)
    plan = build_rename_plan(parsed)
    assert plan.name_map, f"{path}: no zone/state name was renamed — vacuous pairing"


@pytest.mark.parametrize("path", pairing.CORPUS, ids=lambda p: p.name)
def test_no_corpus_game_has_an_unsafe_name(path: Path) -> None:
    """The residual ledger row's falsifiable half: `unsafe` (a zone/state
    name locally shadowed somewhere) is empty for the whole corpus today.
    A future game tripping this is a real finding, not a defect in the
    transform — see rename.py's module docstring."""
    parsed = pairing.parse_corpus_game(path)
    plan = build_rename_plan(parsed)
    assert not plan.unsafe, (
        f"{path}: zone/state name(s) {sorted(plan.unsafe)} are locally "
        f"shadowed somewhere — excluded from this game's rename (safe), but "
        f"record it: this residual was empty until now"
    )


@pytest.mark.parametrize("path", pairing.CORPUS, ids=lambda p: p.name)
@pytest.mark.parametrize("seed", pairing.SEEDS)
def test_renamed_game_plays_out_identically(path: Path, seed: int) -> None:
    parsed = pairing.parse_corpus_game(path)
    plan = build_rename_plan(parsed)
    rename_hook = trace_rename(plan.zone_map)
    a, b = pairing.run_pair(path, alpha_rename, seed)
    witness = pairing.compare_traces(a, b, rename=rename_hook)
    assert witness is None, f"{path} seed={seed}: {witness}"
