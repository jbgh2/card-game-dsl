"""Completeness guard for the per-game split: the old single-file harness
parametrized its proofs over the adapter's registry, so a newly registered
game was covered automatically. With one module per game, that guarantee
must be enforced instead: every registered game has a proof module whose
`TestReadiness` runs the four proofs against the right spec, and no proof
module targets an unregistered game."""

from __future__ import annotations

import importlib
from pathlib import Path

import pytest

from .harness import REGISTERED_GAMES, ReadinessProofs


def _module_for(short_name: str) -> str:
    return "test_" + short_name.removeprefix("cardlang_")


@pytest.mark.parametrize(("short_name", "filename"), REGISTERED_GAMES)
def test_every_registered_game_has_a_proof_module(short_name: str, filename: str) -> None:
    mod = importlib.import_module(f".{_module_for(short_name)}", package=__package__)
    cls = getattr(mod, "TestReadiness", None)
    assert cls is not None and issubclass(cls, ReadinessProofs), (
        f"{short_name}: {mod.__name__} must define TestReadiness(ReadinessProofs)"
    )
    assert cls.spec.short_name == short_name
    assert cls.spec.filename == filename


def test_no_proof_module_without_a_registered_game() -> None:
    here = Path(__file__).resolve().parent
    modules = {p.stem for p in here.glob("test_*.py")} - {"test_coverage"}
    expected = {_module_for(short) for short, _ in REGISTERED_GAMES}
    assert modules == expected, (
        "proof modules and the adapter registry disagree: "
        f"extra={sorted(modules - expected)}, missing={sorted(expected - modules)}"
    )
