"""Eviction grid: the trace emitters are out of the native registry.

`coup_note_reveal`, `tichu_hand_summary` and `coup_game_summary` were trace
emitters for the playout harness, not game primitives
(docs/design-notes/primitive-sidecars.md §3); the note's sequence evicts them
from the native surface and derives their facts at the harness layer instead
(tests/playout_trace.py). This module is that work's grid, authored red before
each eviction (strict xfails on every non-membership cell, flipped green with
it — the red run is the proof the grid can fail).

Completeness ledger (decisions.md "Closed-domain completeness")
---------------------------------------------------------------
property:   the evicted names are complete non-members of every
            native-function namespace, of the runtime dispatch, signature
            and implementation tables, of the implementing modules, and of
            the spec-current corpus/prose surface — and the trace facts
            they emitted derive at the harness layer with identical values.
domain:     evicted name x consulting site. The site axis was frozen by a
            fresh-context framing sweep of the whole cardlang/ package (the
            audit's Step 1): the seven name registries in
            builtins/functions.py, CALL_SIGS, PRIMITIVE_IMPLEMENTATIONS,
            the runtime dispatch arms, the implementing module namespaces,
            resolve's unknown-call and shadow guards, the PRIMITIVE_READS
            inventory, plus the lockstep docs surface
            (docs/games/*.{cardlang,md}, docs/library.md).
registry:   cardlang/builtins/functions.py (all seven name-sets, imported
            below — a new namespace joins OTHER_NAMESPACES or the import
            fails); cardlang/builtins/signatures.py CALL_SIGS;
            cardlang/primitives_block.py PRIMITIVE_IMPLEMENTATIONS;
            cardlang/runtime/primitives.py source (the dispatch's literal
            `case` arms); the docs globs.
covered:    the parametrized cells below. Cross-table sync (functions <->
            signatures <-> dispatch, set equality both ways) is the
            standing pin in tests/test_signatures.py; the reads-inventory
            consequence (Tichu's row dropped `captured`) is pinned by
            tests/test_primitive_reads.py's module-source scan; the
            rendered unknown-call diagnostic for each evicted name is a
            tests/rejections/call_evicted_trace_emitter_* pair.
sampled:    reproduction equality — proven at write time by differentials
            that ran each harness derivation against the live emitter, in
            this module until the eviction commit removed the emitters they
            compared against: `coup_note_reveal` (Coup 8 seeds) and
            `tichu_hand_summary` (Tichu 4 seeds); `coup_game_summary`
            2026-09-04, 40 of 40 seeds equal on all four facts
            (`total_coins`, `total_cards`, the `coins` vector, the `alive`
            vector). Standing coverage is the byte-identical goldens
            (tests/golden/coup_scores.json, tichu_hands.json — values
            produced BY the emitters, reproduced by the derivations on
            every suite run), the 30-seed playout invariant
            (tests/test_playout_tichu.py) and Coup's 40-seed conservation
            invariant on the reader (tests/test_playout_coup.py).

red under (born-green cells):
- test_never_in_other_namespaces: adding "coup_note_reveal" to
  PRIMITIVE_TRICK_WINNERS reddens its cell (demonstrated and reverted).
- test_shadow_wall_still_guards_registered_names is itself the freedom
  cells' red-for-the-right-reason guard: the grid commit's probe placed
  the function inside the game block and its red was a syntax error
  wearing the designed DiagnosticError — the control row's message match
  makes that failure mode loud instead of vacuous.
- the write-time differentials were reddened by a rank_of identity
  mutation (Coup, every reveal), by dropping TichuHands' Dog-shed
  exclusion (Tichu, a real double-victory flag flip at seed 2 hand 3), and
  by capturing the terminal state at the first decision instead of at
  `game_end` (`coup_game_summary`, every seed, coins and alive both wrong);
  all demonstrated and reverted before the goldens took over.

take 1 (2026-09-04): the grid authored against the still-registered
`coup_game_summary`, before any eviction hunk —
`.venv/bin/pytest tests/test_trace_emitter_eviction.py tests/test_rejections.py -q`
-> 8 failed, 160 passed. The eight are this module's six non-membership
cells for the name (call registry, signature table, dispatch arm, corpus
call site, prose reference, user-function freedom), the module-absent cell
for `cardlang.runtime.coup`, and the rejection case. The differential
passed on the same run — it compares against an emitter that still exists.
"""

from __future__ import annotations

import importlib
import random
from pathlib import Path
from typing import Any

import pytest

from cardlang.builtins.functions import (
    CALL_FUNCS,
    DECLARED_ONLY_CALL_FUNCS,
    PRIMITIVE_AUCTION_OUTCOMES,
    PRIMITIVE_CLIMB_FOLLOWS,
    PRIMITIVE_CLIMB_LEADS,
    PRIMITIVE_EARLY_PREDICATES,
    PRIMITIVE_TRICK_WINNERS,
    TRICK_WINNER_NAMES,
    VALUE_NAMES,
)
from cardlang.builtins.signatures import CALL_SIGS
from cardlang.diagnostics import DiagnosticError
from cardlang.pipeline import check_dsl, check_source
from cardlang.primitives_block import PRIMITIVE_IMPLEMENTATIONS
from cardlang.runtime.driver import play_game
from tests.playout_trace import TerminalState, coup_totals

REPO = Path(__file__).parent.parent
GAMES = REPO / "docs" / "games"

# The eviction set is the ratified scope (primitive-sidecars.md §3: the trace
# emitters), paired with each name's former module.
EVICTED: tuple[tuple[str, str], ...] = (
    ("coup_note_reveal", "cardlang.runtime.coup"),
    ("tichu_hand_summary", "cardlang.runtime.tichu"),
    ("coup_game_summary", "cardlang.runtime.coup"),
)
_NAMES = [name for name, _ in EVICTED]

# A module whose last evicted name took the whole file with it: nothing to
# read a symbol out of, so its cell is the import's own absence.
GONE_MODULES: tuple[str, ...] = ("cardlang.runtime.coup",)
_SURVIVING = tuple((n, m) for n, m in EVICTED if m not in GONE_MODULES)

# The seven namespaces the evicted names never belonged to: the domain's
# boundary, pinned so "which namespace held them" stays a checked fact.
OTHER_NAMESPACES: dict[str, frozenset[str]] = {
    "PRIMITIVE_TRICK_WINNERS": PRIMITIVE_TRICK_WINNERS,
    "TRICK_WINNER_NAMES": TRICK_WINNER_NAMES,
    "PRIMITIVE_AUCTION_OUTCOMES": PRIMITIVE_AUCTION_OUTCOMES,
    "VALUE_NAMES": VALUE_NAMES,
    "PRIMITIVE_EARLY_PREDICATES": PRIMITIVE_EARLY_PREDICATES,
    "PRIMITIVE_CLIMB_LEADS": PRIMITIVE_CLIMB_LEADS,
    "PRIMITIVE_CLIMB_FOLLOWS": PRIMITIVE_CLIMB_FOLLOWS,
}


@pytest.mark.parametrize("name", _NAMES)
def test_not_in_call_registry(name: str) -> None:
    assert name not in CALL_FUNCS


@pytest.mark.parametrize("name", _NAMES)
def test_not_in_signature_table(name: str) -> None:
    # Both tables that state a Primitive's type surface: a name still keyed in
    # either would type-check and then find no implementation.
    assert name not in CALL_SIGS
    assert name not in PRIMITIVE_IMPLEMENTATIONS


@pytest.mark.parametrize("name", _NAMES)
def test_no_dispatch_arm(name: str) -> None:
    # Both dispatch homes (issue #201): an evicted name reappearing in the
    # half this pin stopped reading would be evicted only on paper.
    for home in ("builtins.py", "primitives.py"):
        src = (REPO / "cardlang" / "runtime" / home).read_text()
        assert f'case "{name}"' not in src, f"{name} has a dispatch arm in {home}"


@pytest.mark.parametrize(("name", "module"), _SURVIVING)
def test_implementing_symbol_gone(name: str, module: str) -> None:
    assert not hasattr(importlib.import_module(module), name)


@pytest.mark.parametrize("module", GONE_MODULES)
def test_implementing_module_gone(module: str) -> None:
    with pytest.raises(ModuleNotFoundError):
        importlib.import_module(module)


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
    would make the freedom cells pass vacuously.

    The control name is DERIVED from the registry rather than written here:
    a literal is a name this module would have to keep registered on its own
    account, and every eviction is a chance for it to stop being one."""
    registered = min(DECLARED_ONLY_CALL_FUNCS)
    with pytest.raises(DiagnosticError, match="shadows the native function"):
        check_dsl(_shadow_probe(registered), "shadow_control.cardlang")


@pytest.mark.parametrize("name", _NAMES)
@pytest.mark.parametrize("namespace", sorted(OTHER_NAMESPACES))
def test_never_in_other_namespaces(name: str, namespace: str) -> None:
    assert name not in OTHER_NAMESPACES[namespace]


# ---------------------------------------------------------------------------
# The write-time differential: it can only run while both the emitter and its
# replacement exist, so it leaves in the eviction commit and its dated result
# stands in the ledger's `sampled:` row.
# ---------------------------------------------------------------------------


def _coup_facts(game: Any, seed: int) -> tuple[dict[str, Any], dict[str, Any]]:
    """One Coup playout's four `coup_game` facts, twice: derived at the
    harness from the terminal world and the driver's census, and as the live
    emitter reported them."""
    terminal = TerminalState(("coins", "treasury", "alive"))
    emitted: dict[str, Any] = {}

    def tracer(event: str, data: Any) -> None:
        terminal.tracer(event, data)
        if event == "coup_game":
            emitted.update(data)

    play_game(game, random.Random(seed), tracer, on_first_decision=terminal.hold)
    derived: dict[str, Any] = dict(coup_totals(terminal))
    derived["coins"] = terminal.state["coins"]
    derived["alive"] = terminal.state["alive"]
    return derived, emitted


def test_terminal_reader_reproduces_the_live_emitter() -> None:
    """The admission test for the reader that replaces `coup_game_summary`:
    every fact the emitter reports, derived beside it over the golden's own
    width. The comparison runs after `play_game` returns, so a reader holding
    a reference into the popped frame instead of a copy would be reading a
    frame nobody owns."""
    game = check_source(GAMES / "coup.cardlang")
    for seed in range(40):
        derived, emitted = _coup_facts(game, seed)
        assert emitted, f"seed {seed}: the emitter reported nothing to compare"
        assert derived == emitted, f"seed {seed}"
