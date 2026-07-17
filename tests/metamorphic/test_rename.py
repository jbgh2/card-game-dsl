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
                module reads (the sanctioned "game-local stdlib primitive"
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
