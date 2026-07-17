"""T3: inline-vs-`run` — pairing tests and completeness ledger.

property:   splicing every `run NAME(args)` call site with the named
            procedure's body, independently reimplemented at SOURCE-TEXT
            level (inline.py — never calling `cardlang.expand`), does not
            change a playout's observable trace or terminal result.
domain:     `docs/games/coup.cardlang` — the only corpus game using
            `procedure`/`run` (pinned below, not assumed) — x seeds
            (`pairing.SEEDS`).
registry:   docs/games/*.cardlang (`pairing.CORPUS`), filtered to games
            containing the literal token `procedure` or `run` — today,
            exactly one.
covered:    the one witness game, every seed in `pairing.SEEDS`, under the
            DESCENDING chooser (`reverse=True` — "Why reverse=True" below);
            `test_procedure_bodies_are_exercised` proves all three
            procedures actually execute, not just that the (possibly
            vacuous) comparison passes.
sampled:    seeds and decision depth only (CI budget) — pairing.py.
residual:   inline.py's splice is deliberately NOT a general procedure
            inliner (its module docstring lists exactly what Coup's shape
            lets it skip: no nested `run` inside a procedure body, no
            call-site argument with side effects worth re-evaluating
            differently, every call site already brace-scoped). A second
            procedure-using corpus game would need those generalized before
            this transform covers it — not fixed here, since none exists
            today; `test_run_and_procedure_are_coup_only` fails loudly the
            day one is added, which is the trigger to generalize.

This also subsumes the plan's stated acceptance criterion for T3
("the inline-vs-`run` regression test's invariant is subsumed by transform
2's general form... the specific test stays") — `tests/test_procedures.py`'s
existing single-game regression keeps its own narrower, AST-focused
assertions; this module is the general form for the one game exercising the
construct today.

Why `reverse=True`. Coup's default (ascending) greedy chooser is a genuine
COVERAGE TRAP, not merely a slow path: every response window offers
`[challenge, allow]` and "allow" sorts first, so the ascending policy can
never choose "challenge" — `challenged` never becomes true, at ANY seed —
which means `prove_claim` and `lose_influence` (2 of the 3 procedures this
transform exists to test) are NEVER reached, and the pairing test's PASS
would be checking almost nothing (the "Vacuously green" defect class,
decisions.md "Closed-domain completeness"). Worse: "exchange" (which moves
no coins) also sorts before every coin-granting move, so play never leaves
a frozen `exchange`/"allow" loop and the greedy line never naturally
terminates either. The DESCENDING policy (`reverse=True`,
`pairing.run_variant`) is an equally deterministic, equally
hashseed-independent chooser — just one that happens to reach every
procedure body and terminate naturally for Coup. `test_procedure_bodies_are_
exercised` proves this is not merely assumed: it inspects the trace for
direct evidence each of the three procedures ran. Confirmed with a live
mutation (not kept in the tree): forcing `lose_influence`'s bound argument
to `actor` regardless of the real call-site argument made
`test_spliced_game_plays_out_identically` fail at every seed with a located
trace divergence — proof this suite's pass is not vacuous.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from cardlang.ast import nodes as n
from cardlang.resolve import _walk

from tests.metamorphic import pairing
from tests.metamorphic.inline import splice_procedures

# The construct's actual syntax, not the bare English word (which shows up
# in prose comments — including this transform's OWN explanatory comments,
# spliced verbatim from the procedure bodies they came from).
_PROCEDURE_DECL_RE = re.compile(r"\bprocedure\s+[A-Za-z_]\w*\s*\(")
_RUN_CALL_RE = re.compile(r"\brun\s+[A-Za-z_]\w*\s*\(")


def _uses_procedures(path: Path) -> bool:
    text = path.read_text()
    return bool(_PROCEDURE_DECL_RE.search(text) or _RUN_CALL_RE.search(text))


PROCEDURE_GAMES = tuple(p for p in pairing.CORPUS if _uses_procedures(p))


def test_run_and_procedure_are_coup_only() -> None:
    names = sorted(p.name for p in PROCEDURE_GAMES)
    assert names == ["coup.cardlang"], (
        f"the procedure/run domain changed: {names} — a new procedure-using "
        f"game needs inline.py generalized (its module docstring lists what "
        f"it currently assumes) before this suite's coverage claim holds"
    )


@pytest.mark.parametrize("path", PROCEDURE_GAMES, ids=lambda p: p.name)
def test_every_run_argument_is_bare(path: Path) -> None:
    """inline.py's soundness argument (module docstring) assumes every `run`
    argument is a bare identifier or bare enum literal — checked here (unlike
    "no nested run", this one is NOT a language-level wall, just true of
    Coup's text today)."""
    game = pairing.parse_corpus_game(path)
    for nd in _walk(game):
        if isinstance(nd, n.RunStmt):
            for arg in nd.args:
                assert isinstance(arg, n.NameRef), (
                    f"{path.name}: run {nd.name}(...) passes a non-bare "
                    f"argument {arg!r} — inline.py's argument handling "
                    f"assumes bare identifiers/literals; re-verify its "
                    f"soundness argument before trusting this game's result"
                )


@pytest.mark.parametrize("path", PROCEDURE_GAMES, ids=lambda p: p.name)
def test_splice_removes_every_procedure_construct(path: Path) -> None:
    """A vacuity guard: the splice must actually remove `run`/`procedure`,
    not merely leave the text (and therefore the comparison) unchanged."""
    text = path.read_text()
    spliced = splice_procedures(text)
    assert not _PROCEDURE_DECL_RE.search(spliced)
    assert not _RUN_CALL_RE.search(spliced)
    assert spliced != text


@pytest.mark.parametrize("path", PROCEDURE_GAMES, ids=lambda p: p.name)
@pytest.mark.parametrize("seed", pairing.SEEDS)
def test_procedure_bodies_are_exercised(path: Path, seed: int) -> None:
    """The second vacuity guard (module docstring, "Why reverse=True"): a
    passing pairing comparison proves nothing if the procedure bodies never
    actually ran during the playout. Every corpus procedure leaves direct
    trace evidence when it runs: `challenge_window` polls `[challenge,
    allow]` (a "challenge" `announce`/`chose`), `prove_claim` reveals a card
    (a "reveal" event), and `lose_influence` flips a card into `revealed[p]`
    (a "move" event with that destination). All three must appear — this is
    Coup-specific (the module docstring's citation for WHY the descending
    chooser is needed), not a general property inline.py could assert for
    an arbitrary procedure-using game."""
    a, _ = pairing.run_pair_source(path, splice_procedures, seed, reverse=True)
    events = [e for log in a.events.values() for e in log]
    assert any("challenge" in str(e) for e in events), "challenge_window never contested"
    assert any(e[0] == "reveal" for e in events), "prove_claim never revealed a card"
    assert any(
        e[0] == "move" and (str(e[1]).startswith("revealed") or str(e[3]).startswith("revealed"))
        for e in events
    ), "lose_influence never flipped a card into revealed[]"


@pytest.mark.parametrize("path", PROCEDURE_GAMES, ids=lambda p: p.name)
@pytest.mark.parametrize("seed", pairing.SEEDS)
def test_spliced_game_plays_out_identically(path: Path, seed: int) -> None:
    a, b = pairing.run_pair_source(path, splice_procedures, seed, reverse=True)
    witness = pairing.compare_traces(a, b)  # nothing renamed: identity hook
    assert witness is None, f"{path} seed={seed}: {witness}"
