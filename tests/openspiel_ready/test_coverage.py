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
    # any one game: this completeness guard, the bound-coverage grid, and the
    # action-rendering purity pin.
    modules = {p.stem for p in here.glob("test_*.py")} - {
        "test_coverage",
        "test_conformance_bounds",
        "test_action_strings",
    }
    expected = {_module_for(short) for short, _ in REGISTERED_GAMES}
    assert modules == expected, (
        "proof modules and the adapter registry disagree: "
        f"extra={sorted(modules - expected)}, missing={sorted(expected - modules)}"
    )
