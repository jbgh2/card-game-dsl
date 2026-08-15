"""Stage-1 eviction grid: the trace emitters are out of the native registry.

`coup_note_reveal` and `tichu_hand_summary` were trace emitters for the
playout harness, not game primitives (docs/design-notes/primitive-sidecars.md
§3); stage 1 of that note's sequence evicts them from the stdlib surface and
derives their facts at the harness layer instead (tests/playout_trace.py).
This module is the change's grid, authored red before the eviction (strict
xfails on every non-membership cell, flipped green with it — the red run is
the proof the grid can fail).

Completeness ledger (decisions.md "Closed-domain completeness")
---------------------------------------------------------------
property:   the two evicted names are complete non-members of every
            native-function namespace, of the runtime dispatch and
            implementing modules, and of the spec-current corpus/prose
            surface — and the trace facts they emitted derive at the
            harness layer with identical values.
domain:     evicted name {coup_note_reveal, tichu_hand_summary} x
            consulting site. The site axis was frozen by a fresh-context
            framing sweep of the whole cardlang/ package (the audit's
            Step 1): the seven name registries in builtins/functions.py,
            CALL_SIGS, the runtime dispatch arms, the implementing module
            namespaces, resolve's unknown-call and shadow guards, the
            PRIMITIVE_READS inventory, plus the lockstep docs surface
            (docs/games/*.{cardlang,md}, docs/library.md).
registry:   cardlang/builtins/functions.py (all seven name-sets, imported
            below — a new namespace joins OTHER_NAMESPACES or the import
            fails); cardlang/builtins/signatures.py CALL_SIGS;
            cardlang/runtime/primitives.py source (the dispatch's literal
            `case` arms); the docs globs.
covered:    the parametrized cells below. Cross-table sync (functions <->
            signatures <-> dispatch, set equality both ways) is the
            standing pin in tests/test_signatures.py; the reads-inventory
            consequence (Tichu's row dropped `captured`) is pinned by
            tests/test_primitive_reads.py's module-source scan; the
            rendered unknown-call diagnostic for each evicted name is the
            tests/rejections/call_evicted_trace_emitter_{coup,tichu} pair.
sampled:    reproduction equality — proven at write time by a differential
            that ran the harness derivation against the live emitters
            (Coup 8 seeds, Tichu 4 seeds, in this module until the
            eviction commit removed the emitters it compared against);
            standing coverage is the byte-identical goldens
            (tests/golden/coup_scores.json, tichu_hands.json — values
            produced BY the emitters, reproduced by the derivation on
            every suite run) and the 30-seed playout invariant
            (tests/test_playout_tichu.py).
residual:   `coup_game_summary` — a third dead-`let` trace emitter by call
            shape (docs/games/coup.cardlang binds and drops its return) —
            stays registered this stage: its `coup_game` payload
            recomputes conservation totals from engine state, not from
            movement views, so its harness reproduction is its own design
            step. Guard: the staged plan (primitive-sidecars.md §5);
            record: issue #142. The prose scan deliberately covers only
            the spec-current surface — design notes legitimately name the
            evicted names when describing this very migration.

red under (born-green cells):
- test_never_in_other_namespaces: adding "coup_note_reveal" to
  PRIMITIVE_TRICK_WINNERS reddens its cell (demonstrated and reverted).
- test_shadow_wall_still_guards_registered_names is itself the freedom
  cells' red-for-the-right-reason guard: the grid commit's probe placed
  the function inside the game block and its red was a syntax error
  wearing the designed DiagnosticError — the control row's message match
  makes that failure mode loud instead of vacuous.
- the write-time differentials were reddened by a rank_of identity
  mutation (Coup, every reveal) and by dropping TichuHands' Dog-shed
  exclusion (Tichu, a real double-victory flag flip at seed 2 hand 3);
  both demonstrated and reverted before the goldens took over.
"""

from __future__ import annotations

import importlib
from pathlib import Path

import pytest

from cardlang.builtins.functions import (
    CALL_FUNCS,
    PRIMITIVE_AUCTION_OUTCOMES,
    PRIMITIVE_CLIMB_FOLLOWS,
    PRIMITIVE_CLIMB_LEADS,
    PRIMITIVE_EARLY_PREDICATES,
    PRIMITIVE_TRICK_WINNERS,
    PRIMITIVE_VALUE_NAMES,
)
from cardlang.builtins.signatures import CALL_SIGS
from cardlang.diagnostics import DiagnosticError
from cardlang.pipeline import check_dsl

REPO = Path(__file__).parent.parent
GAMES = REPO / "docs" / "games"

# The eviction set is the ratified stage-1 scope (primitive-sidecars.md §3:
# the two pure trace emitters), paired with each name's former module.
EVICTED: tuple[tuple[str, str], ...] = (
    ("coup_note_reveal", "cardlang.runtime.coup"),
    ("tichu_hand_summary", "cardlang.runtime.tichu"),
)
_NAMES = [name for name, _ in EVICTED]

# The six namespaces the evicted names never belonged to: the domain's
# boundary, pinned so "which namespace held them" stays a checked fact.
OTHER_NAMESPACES: dict[str, frozenset[str]] = {
    "PRIMITIVE_TRICK_WINNERS": PRIMITIVE_TRICK_WINNERS,
    "PRIMITIVE_AUCTION_OUTCOMES": PRIMITIVE_AUCTION_OUTCOMES,
    "PRIMITIVE_VALUE_NAMES": PRIMITIVE_VALUE_NAMES,
    "PRIMITIVE_EARLY_PREDICATES": PRIMITIVE_EARLY_PREDICATES,
    "PRIMITIVE_CLIMB_LEADS": PRIMITIVE_CLIMB_LEADS,
    "PRIMITIVE_CLIMB_FOLLOWS": PRIMITIVE_CLIMB_FOLLOWS,
}


@pytest.mark.parametrize("name", _NAMES)
def test_not_in_call_registry(name: str) -> None:
    assert name not in CALL_FUNCS


@pytest.mark.parametrize("name", _NAMES)
def test_not_in_signature_table(name: str) -> None:
    assert name not in CALL_SIGS


@pytest.mark.parametrize("name", _NAMES)
def test_no_dispatch_arm(name: str) -> None:
    # Both dispatch homes (issue #201): an evicted name reappearing in the
    # half this pin stopped reading would be evicted only on paper.
    for home in ("builtins.py", "primitives.py"):
        src = (REPO / "cardlang" / "runtime" / home).read_text()
        assert f'case "{name}"' not in src, f"{name} has a dispatch arm in {home}"


@pytest.mark.parametrize(("name", "module"), EVICTED)
def test_implementing_symbol_gone(name: str, module: str) -> None:
    assert not hasattr(importlib.import_module(module), name)


@pytest.mark.parametrize("name", _NAMES)
def test_corpus_has_no_call_site(name: str) -> None:
    corpus = sorted(GAMES.glob("*.cardlang"))
    assert corpus, "corpus glob came up empty — wrong path, not a clean corpus"
    offenders = [f.name for f in corpus if name in f.read_text()]
    assert offenders == []


@pytest.mark.parametrize("name", _NAMES)
def test_prose_has_no_reference(name: str) -> None:
    prose = sorted(GAMES.glob("*.md")) + [REPO / "docs" / "library.md"]
    offenders = [f.name for f in prose if name in f.read_text()]
    assert offenders == []


def _shadow_probe(name: str) -> str:
    """A game defining (and calling) its own function under an evicted name.
    While the name was registered, resolve's shadow guard rejected the
    definition; after the eviction the name is an ordinary user-function
    name — the strongest witness that it fully left the namespace."""
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
  phase play {{
    deal 3 cards from deck to each hand
    let noted = {name}(0)
  }}
  winner: highest score
}}
function {name}(p : Player) = 0
"""


@pytest.mark.parametrize("name", _NAMES)
def test_name_is_free_for_user_functions(name: str) -> None:
    check_dsl(_shadow_probe(name), f"shadow_probe_{name}.cardlang")


def test_shadow_wall_still_guards_registered_names() -> None:
    """The control row for the freedom cells: the same probe shape under a
    still-registered name must die on the SHADOW guard's own message. This
    pins that the probe reaches the guard — without it, a probe broken
    earlier in the pipeline (a syntax error also raises DiagnosticError)
    would make the freedom cells pass vacuously."""
    with pytest.raises(DiagnosticError, match="shadows the native function"):
        check_dsl(_shadow_probe("coup_game_summary"), "shadow_control.cardlang")


@pytest.mark.parametrize("name", _NAMES)
@pytest.mark.parametrize("namespace", sorted(OTHER_NAMESPACES))
def test_never_in_other_namespaces(name: str, namespace: str) -> None:
    assert name not in OTHER_NAMESPACES[namespace]
