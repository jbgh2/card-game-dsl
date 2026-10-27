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
            `hand` in a game where a `Card`-typed move parameter or a
            Builtin reads the zone by that spelling (decisions.md "Declared
            parameter domains", rename.py `_magic_hand_names`) — outside
            T2's domain by the spec's own words. A rule clause's `hand` is
            the trick round's Play Source, not the zone, so a game whose
            only reader is its rules renames `hand` like any other zone. `excluded_contract` is a name a family library's
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
            transform cannot rewrite. Every rename keeps each zone's place in
            sorted name order, the one meaning a zone's spelling carries (a
            gather collects in that order, decisions.md's gather paragraph),
            so an excluded zone and a renamed one holding cards at the same
            gather collect as they did; a rename that cannot keep the order
            is refused, never run.
registry:   docs/games/*.cardlang (`pairing.CORPUS`) — every corpus game.
            The declared-reads registry the coupled exclusion derives from:
            `PRIMITIVE_READS`, cardlang/runtime/reads.py, pinned in both
            directions — against each game file's declarations and against
            each module's accessor-call literals — by
            tests/test_primitive_reads.py.
does not prove:  that the property holds at every depth or from every deal.
            Seeds and decision depth are sampled to a CI budget
            (`CARDLANG_METAMORPHIC_STEPS` / `CARDLANG_METAMORPHIC_SEEDS` in
            pairing.py widen both for a deeper local run), so a divergence
            reachable only from an unsampled seed, or past the step bound,
            passes here.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.metamorphic import pairing
from tests.metamorphic.rename import (
    _order_preserving_check,
    alpha_rename,
    build_rename_plan,
    trace_rename,
)


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


@pytest.mark.parametrize("path", pairing.CORPUS, ids=lambda p: p.name)
def test_every_rename_keeps_the_zones_in_sorted_order(path: Path) -> None:
    """red under: rename targets that ignore their source's spelling (the
    `_mt_<n>` prefix scheme, which sorts every renamed zone before every
    unrenamed one)."""
    parsed = pairing.parse_corpus_game(path)
    plan = build_rename_plan(parsed)
    zones = [z.name for z in parsed.zones]
    assert sorted(zones) == sorted(zones, key=lambda z: plan.zone_map.get(z, z))


def test_a_rename_that_would_reorder_the_zones_is_refused() -> None:
    """A source name that is a prefix of another's is the one case a suffix
    cannot keep in order; the rename refuses it rather than run."""
    with pytest.raises(AssertionError, match="reorder the zones a gather collects"):
        _order_preserving_check({"pile", "pileA"}, {"pile": "pile__mt0"})
