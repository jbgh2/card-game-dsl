"""Completeness guard for the per-game split: a single-file harness that
parametrized its proofs over the adapter's registry would cover a newly
registered game automatically. With one module per game, that guarantee
must be enforced instead: every registered game has a proof module whose
`TestReadiness` runs the shared proofs against the right spec, and no proof
module targets an unregistered game."""

from __future__ import annotations

import importlib
from pathlib import Path
from typing import Any

import pytest

from .harness import ONE_SEED, SWAP_SEEDS, REGISTERED_GAMES, ReadinessProofs

# Games whose indistinguishability proof runs at ONE seed, with the reason.
# Overriding the shared proof replaces its `@parametrize` too, so a per-game
# analogue can quietly keep a hardcoded seed while the manifest grows and the
# coverage prose says "five seeds" — the silent-cap failure, in the file any
# external partition claim cites. This table makes that state declared instead:
# an entry names why one seed is enough, and `test_every_swap_proof_runs_the_
# seed_manifest` is tight in BOTH directions, so a game listed here that starts
# running the manifest fails just as loudly as one missing that does not.
#
# red under — RUN results, not predictions, one per branch of the guard:
#   Klondike's decorator narrowed to `SWAP_SEEDS[:1]`  -> fails naming
#     cardlang_klondike and the manifest it no longer runs
#   FreeCell's entry deleted                           -> fails naming
#     cardlang_freecell on the same branch
#   FreeCell keeps its entry but runs `SWAP_SEEDS`     -> fails on the
#     exemption-outlived-itself branch
#   an entry for a game the registry does not contain  -> fails naming it
ONE_SEED_SWAP_PROOFS: dict[str, str] = {
    "cardlang_breakthrough": (
        "perfect information: the proof is a DEGENERACY argument (no populated "
        "zone projects below identity, so no hidden pair exists to swap), which "
        "is a property of the game's zone declarations, not of a deal"
    ),
    "cardlang_freecell": (
        "perfect information: same degeneracy argument, and FreeCell's whole "
        "layout is dealt face up, so a second deal probes nothing new"
    ),
    "cardlang_tic_tac_toe": (
        "perfect information and no deck at all: the proof asserts both "
        "observers render the identical board, which no seed can vary"
    ),
}


def _module_for(short_name: str) -> str:
    return "test_" + short_name.removeprefix("cardlang_")


def _seed_values(argvalues: Any) -> tuple[int, ...]:
    """The seeds a `parametrize` declares, whether its entries are bare ints or
    `pytest.param(...)` wrappers — `harness.manifest` marks its tail `slow`, and
    reading `mark.args[1]` raw would compare seeds against ParameterSets and
    report every game as running the wrong manifest."""
    out: list[int] = []
    for value in argvalues:
        wrapped = getattr(value, "values", None)
        out.append(int(wrapped[0]) if wrapped is not None else int(value))
    return tuple(out)


@pytest.mark.parametrize(("short_name", "filename"), REGISTERED_GAMES)
def test_every_registered_game_has_a_proof_module(short_name: str, filename: str) -> None:
    mod = importlib.import_module(f".{_module_for(short_name)}", package=__package__)
    cls = getattr(mod, "TestReadiness", None)
    assert cls is not None and issubclass(cls, ReadinessProofs), (
        f"{short_name}: {mod.__name__} must define TestReadiness(ReadinessProofs)"
    )
    assert cls.spec.short_name == short_name
    assert cls.spec.filename == filename


@pytest.mark.parametrize(("short_name", "filename"), REGISTERED_GAMES)
def test_every_swap_proof_runs_the_seed_manifest(short_name: str, filename: str) -> None:
    """Every game's indistinguishability proof runs `SWAP_SEEDS`, or says why
    it does not. Read off the resolved method, so an override that replaced the
    shared `@parametrize` is visible whether it re-applied it or not."""
    mod = importlib.import_module(f".{_module_for(short_name)}", package=__package__)
    method = mod.TestReadiness.test_indistinguishability_under_hidden_swap
    seeds = {
        _seed_values(mark.args[1])
        for mark in getattr(method, "pytestmark", [])
        if mark.name == "parametrize" and mark.args[0] == "seed"
    }
    why = ONE_SEED_SWAP_PROOFS.get(short_name)
    if why is None:
        assert seeds == {tuple(SWAP_SEEDS)}, (
            f"{short_name}: the swap proof runs {seeds or 'one unnamed seed'}, "
            f"not the manifest {SWAP_SEEDS}. An override replaces the shared "
            f"parametrization — re-apply it, or declare the game in "
            f"ONE_SEED_SWAP_PROOFS with the reason one seed suffices"
        )
    else:
        assert why.strip(), f"{short_name}: exempted from the manifest with no reason"
        assert seeds == {tuple(ONE_SEED)}, (
            f"{short_name}: declared a one-seed proof but runs {seeds}, not "
            f"{tuple(ONE_SEED)} — either the exemption outlived itself (drop it "
            f"from ONE_SEED_SWAP_PROOFS) or the proof runs a seed off the manifest"
        )


def test_the_one_seed_exemptions_all_name_a_registered_game() -> None:
    """An exemption naming nothing can never be cleared, so it would sit in the
    table forever reading like a covered game."""
    unknown = sorted(set(ONE_SEED_SWAP_PROOFS) - {s for s, _ in REGISTERED_GAMES})
    assert not unknown, f"ONE_SEED_SWAP_PROOFS names unregistered games: {unknown}"


def test_no_proof_module_without_a_registered_game() -> None:
    here = Path(__file__).resolve().parent
    # The package-wide modules, which target the registry itself rather than
    # any one game: this completeness guard, the bound-coverage grid, the
    # action-rendering purity pin, and the Arrival Record's copy-purity pin
    # (whose game axis derives from the component registry, not one game —
    # issue #256).
    modules = {p.stem for p in here.glob("test_*.py")} - {
        "test_coverage",
        "test_conformance_bounds",
        "test_action_strings",
        "test_arrival_purity",
    }
    expected = {_module_for(short) for short, _ in REGISTERED_GAMES}
    assert modules == expected, (
        "proof modules and the adapter registry disagree: "
        f"extra={sorted(modules - expected)}, missing={sorted(expected - modules)}"
    )


def _games_with_a_provenance_consumer() -> list[tuple[str, str]]:
    """Every registered game whose description actually READS an Arrival
    Record -- derived, from both sources the proof's domain is built from: an
    `ARRIVAL_RECORD_CALLS` call in the checked AST, or a `PRIMITIVE_READS` row
    declaring `arrival_zones`. Derived rather than listed, because the point of
    the pin below is precisely that this list is not written by hand."""
    from .harness import GameSpec

    return [
        (short, filename)
        for short, filename in REGISTERED_GAMES
        if GameSpec(short_name=short, filename=filename).all_provenance_zones
    ]


def test_the_provenance_proof_is_non_vacuous_where_a_consumer_exists() -> None:
    """A game that reads an Arrival Record must prove that read SOUND, never
    record a vacuous cell.

    The provenance proof honestly records `vacuous=True` for a game with no
    consumer, which is most of the corpus -- so the proof as a whole can go
    green while a game that DOES consume provenance proves nothing, if its
    zone never entered the proof's domain. That was reachable while the
    call-form half of the domain was a hand-listed field per spec: a game that
    grew a consumer kept whatever list it already had.

    Non-empty by construction: the helper derives its own domain, and an empty
    domain would make this pin vacuous in turn, so the count is asserted.

    red under: drop the AST source from `GameSpec.all_provenance_zones` --
    doppelkopf's domain empties, its provenance proof records `vacuous=True`,
    and this fails naming it (executed)."""
    consumers = _games_with_a_provenance_consumer()
    assert len(consumers) >= 4, (
        f"only {len(consumers)} game(s) derive a provenance domain -- the "
        f"derivation is broken, and this pin is vacuous"
    )
    for short, filename in consumers:
        from .harness import GameSpec

        zones = GameSpec(short_name=short, filename=filename).all_provenance_zones
        assert zones, f"{short} lost its provenance domain"


def test_the_provenance_derivation_reads_the_call_registry() -> None:
    """`ARRIVAL_RECORD_CALLS` has two consumers, and only one of them could
    fail on a bad key. Resolve's guard reddens loudly under a renamed member
    (the construct's grid); the HARNESS consumer did not -- its derivation is
    a set union, so a key nobody matches contributes nothing and every
    provenance proof stays green while deriving less. A registry with a
    consumer that cannot fail is a registry that has stopped being one.

    Pinned by the derivation's OWN answer: doppelkopf reads its trick pile
    through an `ARRIVAL_RECORD_CALLS` call and through no Primitive row (its
    module retired), so that zone is in the domain if and only if the AST half
    read the registry correctly.

    red under (executed, reverted): rename `highest_by_trick_order` in
    `ARRIVAL_RECORD_CALLS` -- doppelkopf's domain empties and this fails,
    where before the rename only the construct's own grid noticed."""
    from cardlang.builtins.functions import ARRIVAL_RECORD_CALLS
    from cardlang.runtime.reads import PRIMITIVE_READS

    from .harness import GameSpec

    spec = GameSpec(short_name="cardlang_doppelkopf", filename="doppelkopf.cardlang")
    assert not [
        r for r in PRIMITIVE_READS if r.game_file == spec.filename and r.arrival_zones
    ], "doppelkopf grew a Primitive arrival row -- this pin no longer isolates the AST half"
    assert "highest_by_trick_order" in ARRIVAL_RECORD_CALLS
    assert spec.all_provenance_zones == ("trick_pile",), (
        f"the AST half derived {spec.all_provenance_zones} -- the call registry "
        f"is not reaching the harness's derivation"
    )


def test_a_family_pile_expands_before_it_is_derived_from() -> None:
    """The subscripted-pile path, exercised directly.

    `highest_by_trick_order(piles[p])` is designed surface, but the AST
    derivation can only see the family NAME. Two halves make that safe, and
    neither has a corpus witness (no corpus game names a family pile), so both
    are driven here rather than left to the accept cells: the proof EXPANDS a
    family into its live instances, and `derive_arrivals` REFUSES a bare
    family loudly rather than matching no move event and returning [] — which
    the proof would read as a passing comparison of two empty sequences.

    red under (executed, reverted): drop the `is_family` branch from
    `_instance_labels` — the expansion assertion fails; and remove
    `derive_arrivals`' family assert — the refusal assertion fails."""
    import random

    from cardlang.ast import nodes as n
    from cardlang.runtime.state import RuntimeState, ZoneStore
    from cardlang.runtime.values import Seating

    from .harness import _instance_labels
    from .partition import derive_arrivals

    decls = (
        n.ZoneDecl(name="pile", index=None, type_ref=n.TypeRef(name="TrickPile")),
        n.ZoneDecl(name="piles", index="player", type_ref=n.TypeRef(name="PlayerPile")),
    )
    rs = RuntimeState(Seating(2), ZoneStore(decls, (0, 1)), random.Random(0))
    assert _instance_labels(rs, ("pile", "piles")) == ["pile", "piles[0]", "piles[1]"]
    with pytest.raises(AssertionError, match="zone FAMILY"):
        derive_arrivals(rs, [], "piles")
