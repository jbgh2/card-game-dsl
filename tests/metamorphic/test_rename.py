"""T2: alpha-rename — pairing tests and completeness ledger.

property:   renaming every zone and state-variable declaration (a fresh,
            game-wide-unique spelling — rename.py) and every reference to it
            does not change a playout's observable trace or terminal result.
domain:     corpus games (`pairing.CORPUS`) x seeds (`pairing.SEEDS`).
            Four classes of name sit outside the rename, each on its own
            `RenamePlan` field and none of them silent, and none a gap in
            the property. `unsafe` is a zone/state name some binder in the
            same game shadows locally (rename.py, defense 2); it is empty
            across the corpus, and a game that trips it renames everything
            else and leaves that one name alone. `excluded_global` is
            `hand`, the language-wide magic zone name decisions.md
            "Declared parameter domains" and `resolve.py` require for
            `Card`-typed move parameters — outside T2's domain by the spec's
            own words. `excluded_contract` is a name a family library's
            `requires` block declares, where the spelling IS the interface
            (decisions.md "Family libraries"). `excluded_coupled` is the
            per-game names a game-local primitive module reads, DERIVED from
            the declared-reads registry rather than hand-listed. That last
            one is REGIME-scoped, and a game declaring a `primitives { }`
            block is outside it: its Primitive reads are declared in its own
            file, so the transform renames the declaration along with the
            zone and the checker refuses a `reads` name that resolves to
            nothing — one edit in one file moves both sides. The names it
            excludes are exactly those whose reading side is Python this
            transform cannot rewrite.
registry:   docs/games/*.cardlang (`pairing.CORPUS`) — every corpus game.
            The declared-reads registry the coupled exclusion derives from:
            `PRIMITIVE_READS`, cardlang/runtime/reads.py, pinned in both
            directions — against each game file's declarations and against
            each module's accessor-call literals — by
            tests/test_primitive_reads.py.
does not prove:  two things.
            That the property holds at every depth or from every deal.
            Seeds and decision depth are sampled to a CI budget
            (`CARDLANG_METAMORPHIC_STEPS` / `CARDLANG_METAMORPHIC_SEEDS` in
            pairing.py widen both for a deeper local run), so a divergence
            reachable only from an unsampled seed, or past the step bound,
            passes here.
            That a FAILURE of the pairing property is a defect. `move all
            cards to <zone>` collects its sources in sorted ZONE-NAME order
            (decisions.md, the gather paragraph) and this transform renames
            only the names outside the exclusion sets, so a game reaching a
            gather with cards in BOTH an excluded zone and a renamed one has
            its collection reordered, its deck stacked differently and its
            next shuffle diverged — the property fails on a game that is
            correct. The failure names a diverging event rather
            than a naming artifact, which makes the tempting repair
            distorting the game until the transform is happy; the fix is
            upstream of the game, in the transform or the gather, never in
            the game file.
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
    """The `domain:` row's falsifiable half: `unsafe` (a zone/state
    name locally shadowed somewhere) is empty for the whole corpus today.
    A future game tripping this is a real finding, not a defect in the
    transform — see rename.py's module docstring."""
    parsed = pairing.parse_corpus_game(path)
    plan = build_rename_plan(parsed)
    assert not plan.unsafe, (
        f"{path}: zone/state name(s) {sorted(plan.unsafe)} are locally "
        f"shadowed somewhere — excluded from this game's rename (safe), but "
        f"record it: this set is empty for every corpus game"
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
