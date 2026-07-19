"""T3: inline-vs-`run` — pairing tests and completeness ledger.

property:   splicing every `run NAME(args)` call site with the named
            procedure's body, independently reimplemented at SOURCE-TEXT
            level (inline.py — never calling `cardlang.expand`), does not
            change a playout's observable trace or terminal result.
domain:     `docs/games/coup.cardlang` and `docs/games/cheat.cardlang` —
            the corpus games using `procedure`/`run` (pinned below, not
            assumed) — x seeds (`pairing.SEEDS`) x that game's policies
            (`_POLICIES`).
registry:   docs/games/*.cardlang (`pairing.CORPUS`), filtered to games
            containing the literal token `procedure` or `run` — today,
            exactly two.
covered:    both witness games, every seed in `pairing.SEEDS`, under each
            policy in `_POLICIES[game]` ("Why reverse=True" below: Coup
            needs the DESCENDING chooser to reach its procedures at all;
            Cheat runs under BOTH — descending challenges every window,
            ascending allows every one, and the two together reach every
            branch of its single procedure);
            `test_procedure_bodies_are_exercised` proves the procedure
            bodies actually execute per game, not just that the (possibly
            vacuous) comparison passes.
sampled:    seeds and decision depth only (CI budget) — pairing.py.
residual:   inline.py's splice is deliberately NOT a general procedure
            inliner (its module docstring lists exactly the shape envelope
            both pinned games sit inside: no nested `run` inside a
            procedure body — a resolve-level wall — no call-site argument
            beyond a bare identifier/literal, every call site
            brace-scoped). A game outside that envelope needs the splice
            generalized before this suite covers it — not fixed here,
            since none exists today; `test_run_and_procedure_domain_is_
            pinned` fails loudly the day one is added, which is the
            trigger to generalize.

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

# Per-game deterministic policies (the `reverse` axis of pairing's sorted
# chooser). Coup: descending only — ascending is the frozen exchange/"allow"
# loop that never reaches a procedure ("Why reverse=True", module
# docstring). Cheat: both — descending picks `call_cheat` at every window
# (every play flipped and adjudicated), ascending picks `allow` (every play
# merges unchallenged), so the pair reaches every branch of `resolve_play`.
# `test_procedure_bodies_are_exercised` holds direct evidence per (game,
# policy), so a wrong entry here fails loudly rather than passing vacuously.
_POLICIES: dict[str, tuple[bool, ...]] = {
    "coup.cardlang": (True,),
    "cheat.cardlang": (True, False),
}

_GAME_POLICY_CASES = tuple(
    pytest.param(path, reverse, id=f"{path.name}-{'desc' if reverse else 'asc'}")
    for path in PROCEDURE_GAMES
    for reverse in _POLICIES[path.name]
)


def test_run_and_procedure_domain_is_pinned() -> None:
    names = sorted(p.name for p in PROCEDURE_GAMES)
    assert names == ["cheat.cardlang", "coup.cardlang"], (
        f"the procedure/run domain changed: {names} — a new procedure-using "
        f"game needs inline.py generalized (its module docstring lists what "
        f"it currently assumes) and a `_POLICIES` entry with exercise "
        f"evidence before this suite's coverage claim holds"
    )
    assert sorted(_POLICIES) == names, (
        "_POLICIES and the pinned domain disagree — every procedure-using "
        "game declares its deterministic policies here"
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


@pytest.mark.parametrize(("path", "reverse"), _GAME_POLICY_CASES)
@pytest.mark.parametrize("seed", pairing.SEEDS)
def test_procedure_bodies_are_exercised(path: Path, reverse: bool, seed: int) -> None:
    """The second vacuity guard (module docstring, "Why reverse=True"): a
    passing pairing comparison proves nothing if the procedure bodies never
    actually ran during the playout. Every corpus procedure leaves direct
    trace evidence when it runs — per game, per policy:

    - Coup (descending): `challenge_window` polls `[challenge, allow]` (a
      "challenge" `announce`/`chose`), `prove_claim` reveals a card (a
      "reveal" event), `lose_influence` flips a card into `revealed[p]`.
    - Cheat descending: `resolve_play`'s window is contested every play (a
      "call_cheat" announce), the flip fires (a "move" into `flipped`), and
      the verdict routes the flipped cards to a hand.
    - Cheat ascending: the window passes every play (an "allow" announce)
      and the play merges face-down (a "move" from `played` to `pile`) —
      the branch the descending policy never reaches.

    This is per-game evidence (the reason `_POLICIES` exists), not a general
    property inline.py could assert for an arbitrary procedure-using game."""
    a, _ = pairing.run_pair_source(path, splice_procedures, seed, reverse=reverse)
    events = [e for log in a.events.values() for e in log]
    if path.name == "coup.cardlang":
        assert any("challenge" in str(e) for e in events), "challenge_window never contested"
        assert any(e[0] == "reveal" for e in events), "prove_claim never revealed a card"
        assert any(
            e[0] == "move" and (str(e[1]).startswith("revealed") or str(e[3]).startswith("revealed"))
            for e in events
        ), "lose_influence never flipped a card into revealed[]"
    elif path.name == "cheat.cardlang" and reverse:
        assert any(e[0] == "announce" and e[2] == "call_cheat" for e in events), (
            "resolve_play's window was never contested"
        )
        assert any(e[0] == "move" and e[3] == "flipped" for e in events), (
            "resolve_play never flipped a challenged play"
        )
        assert any(
            e[0] == "move" and e[1] == "flipped" and str(e[3]).startswith("hand[")
            for e in events
        ), "resolve_play never routed a verdict"
    elif path.name == "cheat.cardlang":
        assert any(e[0] == "announce" and e[2] == "allow" for e in events), (
            "resolve_play's window was never polled"
        )
        assert any(e[0] == "move" and e[1] == "played" and e[3] == "pile" for e in events), (
            "resolve_play never merged an unchallenged play"
        )
    else:  # a new domain member slipped past the pin — never pass silently
        raise AssertionError(f"no exercise evidence declared for {path.name}")


@pytest.mark.parametrize(("path", "reverse"), _GAME_POLICY_CASES)
@pytest.mark.parametrize("seed", pairing.SEEDS)
def test_spliced_game_plays_out_identically(path: Path, reverse: bool, seed: int) -> None:
    a, b = pairing.run_pair_source(path, splice_procedures, seed, reverse=reverse)
    witness = pairing.compare_traces(a, b)  # nothing renamed: identity hook
    assert witness is None, f"{path} seed={seed}: {witness}"
