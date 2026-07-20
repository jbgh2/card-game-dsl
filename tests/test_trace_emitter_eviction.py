"""Stage-1 eviction grid: the trace emitters leave the stdlib registry.

`coup_note_reveal` and `tichu_hand_summary` are trace emitters for the
playout harness, not game primitives (docs/design-notes/primitive-sidecars.md
§3); stage 1 of that note's sequence evicts them from the stdlib surface and
re-derives their facts at the harness layer (tests/playout_trace.py). This
module is the change's grid, authored red before the eviction commit: the
non-membership cells carry strict xfail marks until the implementation lands,
and the two differential rows prove the harness derivation equals the live
emitters while both still exist.

Completeness ledger (decisions.md "Closed-domain completeness")
---------------------------------------------------------------
property:   the two evicted names are complete non-members of every
            stdlib-function namespace, of the runtime dispatch and
            implementing modules, and of the spec-current corpus/prose
            surface — and the trace facts they emitted derive at the
            harness layer with identical values.
domain:     evicted name {coup_note_reveal, tichu_hand_summary} x
            consulting site. The site axis was frozen by a fresh-context
            framing sweep of the whole cardlang/ package (the audit's
            Step 1): the seven name registries in stdlib/functions.py,
            CALL_SIGS, the runtime dispatch arms, the implementing module
            namespaces, resolve's unknown-call and shadow walls, the
            PRIMITIVE_READS inventory, plus the lockstep docs surface
            (docs/games/*.{cardlang,md}, docs/library.md).
registry:   cardlang/stdlib/functions.py (all seven name-sets, imported
            below — a new namespace joins OTHER_NAMESPACES or the import
            fails); cardlang/stdlib/signatures.py CALL_SIGS;
            cardlang/runtime/stdlib.py source (the dispatch's literal
            `case` arms); the docs globs.
covered:    the parametrized cells below. Cross-table sync (functions <->
            signatures <-> dispatch, set equality both ways) is the
            standing pin in tests/test_signatures.py; the reads-inventory
            consequence (Tichu's row drops `captured`) is pinned by
            tests/test_primitive_reads.py's module-source scan; the
            rendered unknown-call diagnostic for each evicted name lands
            as a tests/rejections/ pair with the eviction commit.
sampled:    reproduction equality — the differential rows here run 8 Coup
            seeds (the golden's own capture policy) and 4 Tichu seeds
            (the reference policy); they are the write-time witness and
            leave with the emitters, at which point the byte-identical
            goldens (tests/golden/coup_scores.json, tichu_hands.json —
            values produced BY the emitters, reproduced by the harness
            derivation) and the 30-seed playout invariant
            (tests/test_playout_tichu.py) become the standing coverage.
residual:   `coup_game_summary` — a third dead-`let` trace emitter by call
            shape (docs/games/coup.cardlang binds and drops its return) —
            stays registered this stage: its `coup_game` payload
            recomputes conservation totals from engine state, not from
            movement views, so its harness reproduction is its own design
            step. Wall: the staged plan (primitive-sidecars.md §4);
            record: docs/roadmap.md ("Primitive sidecars" entry, added
            with the eviction commit). The prose scan deliberately covers
            only the spec-current surface — design notes and the roadmap
            legitimately name the evicted names when describing this very
            migration.

red under (born-green cells):
- test_never_in_other_namespaces: adding "coup_note_reveal" to
  STDLIB_TRICK_OUTCOMES reddens its cell (demonstrated and reverted).
- the Coup differential: making rank_of return the raw card string fails
  every reveal comparison (demonstrated and reverted).
- the Tichu differential: dropping TichuHands' Dog-shed exclusion flips
  seed 2's hand 3 double-victory flag (demonstrated and reverted).
"""

from __future__ import annotations

import importlib
import random
from pathlib import Path
from typing import Any

import pytest

from cardlang.diagnostics import DiagnosticError
from cardlang.pipeline import check_dsl, check_source
from cardlang.runtime.driver import play_game
from cardlang.stdlib.functions import (
    STDLIB_AUCTION_OUTCOMES,
    STDLIB_CALL_FUNCS,
    STDLIB_CLIMB_FOLLOWS,
    STDLIB_CLIMB_LEADS,
    STDLIB_EARLY_PREDICATES,
    STDLIB_TRICK_OUTCOMES,
    STDLIB_VALUE_NAMES,
)
from cardlang.stdlib.signatures import CALL_SIGS
from tests.playout_trace import CoupReveals, TichuHands

REPO = Path(__file__).parent.parent
GAMES = REPO / "docs" / "games"

# The eviction set is the ratified stage-1 scope (primitive-sidecars.md §3:
# the two pure trace emitters), paired with each name's implementing module.
EVICTED: tuple[tuple[str, str], ...] = (
    ("coup_note_reveal", "cardlang.runtime.coup"),
    ("tichu_hand_summary", "cardlang.runtime.tichu"),
)
_NAMES = [name for name, _ in EVICTED]

# The six namespaces the evicted names never belonged to: the domain's
# boundary, pinned so "which namespace held them" stays a checked fact.
OTHER_NAMESPACES: dict[str, frozenset[str]] = {
    "STDLIB_TRICK_OUTCOMES": STDLIB_TRICK_OUTCOMES,
    "STDLIB_AUCTION_OUTCOMES": STDLIB_AUCTION_OUTCOMES,
    "STDLIB_VALUE_NAMES": STDLIB_VALUE_NAMES,
    "STDLIB_EARLY_PREDICATES": STDLIB_EARLY_PREDICATES,
    "STDLIB_CLIMB_LEADS": STDLIB_CLIMB_LEADS,
    "STDLIB_CLIMB_FOLLOWS": STDLIB_CLIMB_FOLLOWS,
}

EVICTION_RED = pytest.mark.xfail(
    strict=True,
    raises=AssertionError,
    reason="stage-1 grid: red until the eviction commit lands",
)


@EVICTION_RED
@pytest.mark.parametrize("name", _NAMES)
def test_not_in_call_registry(name: str) -> None:
    assert name not in STDLIB_CALL_FUNCS


@EVICTION_RED
@pytest.mark.parametrize("name", _NAMES)
def test_not_in_signature_table(name: str) -> None:
    assert name not in CALL_SIGS


@EVICTION_RED
@pytest.mark.parametrize("name", _NAMES)
def test_no_dispatch_arm(name: str) -> None:
    dispatch_src = (REPO / "cardlang" / "runtime" / "stdlib.py").read_text()
    assert f'case "{name}"' not in dispatch_src


@EVICTION_RED
@pytest.mark.parametrize(("name", "module"), EVICTED)
def test_implementing_symbol_gone(name: str, module: str) -> None:
    assert not hasattr(importlib.import_module(module), name)


@EVICTION_RED
@pytest.mark.parametrize("name", _NAMES)
def test_corpus_has_no_call_site(name: str) -> None:
    corpus = sorted(GAMES.glob("*.cardlang"))
    assert corpus, "corpus glob came up empty — wrong path, not a clean corpus"
    offenders = [f.name for f in corpus if name in f.read_text()]
    assert offenders == []


@EVICTION_RED
@pytest.mark.parametrize("name", _NAMES)
def test_prose_has_no_reference(name: str) -> None:
    prose = sorted(GAMES.glob("*.md")) + [REPO / "docs" / "library.md"]
    offenders = [f.name for f in prose if name in f.read_text()]
    assert offenders == []


def _shadow_probe(name: str) -> str:
    """A game defining (and calling) its own function under an evicted name.
    While the name is registered, resolve's shadow wall rejects the
    definition; after eviction the name is an ordinary user-function name."""
    return f"""
game ShadowProbe {{
  players: 2
  max_length: 1000
  cards: standard52
  ranking: A K Q J 10 9 8 7 6 5 4 3 2
  zones {{
    deck : Deck
    hand[player] : Hand<player>
  }}
  state {{ score[player] : Integer = 0 }}
  function {name}(p : Player) = 0
  phase play {{
    deal 3 cards from deck to each hand
    let noted = {name}(0)
  }}
  winner: highest score
}}
"""


@pytest.mark.xfail(
    strict=True,
    raises=DiagnosticError,
    reason="stage-1 grid: red until the eviction commit lands",
)
@pytest.mark.parametrize("name", _NAMES)
def test_name_is_free_for_user_functions(name: str) -> None:
    check_dsl(_shadow_probe(name), f"shadow_probe_{name}.cardlang")


@pytest.mark.parametrize("name", _NAMES)
@pytest.mark.parametrize("namespace", sorted(OTHER_NAMESPACES))
def test_never_in_other_namespaces(name: str, namespace: str) -> None:
    assert name not in OTHER_NAMESPACES[namespace]


# --- write-time differentials (deleted with the emitters) -------------------
#
# While the emitters still run, the harness derivation is proven equal to
# their live output. These rows leave in the eviction commit; the
# byte-identical goldens take over as the standing witness (see the ledger).


def test_coup_reveal_derivation_matches_live_trace() -> None:
    game = check_source(GAMES / "coup.cardlang")
    for seed in range(8):
        log = CoupReveals()
        emitted: list[list[int | str]] = []

        def tracer(event: str, data: Any, _out: list[list[int | str]] = emitted) -> None:
            if event == "coup_reveal":
                _out.append([data[0], data[1]])

        play_game(game, random.Random(seed), tracer, observer=log.observer)
        assert emitted == log.reveals, f"seed {seed}"


def test_tichu_hand_derivation_matches_live_trace() -> None:
    from tests.test_playout_tichu import tichu_reference_policy

    game = check_source(GAMES / "tichu.cardlang")
    team_of = {
        p: ti for ti, members in enumerate(game.partnerships) for p in members
    }
    for seed in range(4):
        log = TichuHands(team_of)
        emitted: list[list[int]] = []
        derived: list[list[int]] = []

        def tracer(
            event: str,
            data: Any,
            _e: list[list[int]] = emitted,
            _d: list[list[int]] = derived,
            _log: TichuHands = log,
        ) -> None:
            if event == "tichu_hand":
                _e.append([int(data["double_victory"]), data["card_points"]])
            elif event == "hand_end":
                _d.append(_log.hand_summary())

        rng = random.Random(seed)
        play_game(game, rng, tracer, tichu_reference_policy(rng), observer=log.observer)
        assert emitted == derived, f"seed {seed}"
