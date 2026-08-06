"""The `mode { }` construct's coverage grid (issue #208).

A mode is a condition the game is in, existing to change which rules are
active (glossary, "Mode"). Before this construct existed the same job was done
by a *rule-delta sub-phase* — a nested `phase` whose body held only
configuration — and the overload cost four silent-wrong-answer defects, every
one of which `check_dsl` accepted and a playout then got wrong:

  1. a chain of three or more left an arbitrary SUBSET active (mode 2 was
     active before it was ever entered, so its transition was live from t=0);
  2. an orphan — neither targeted nor declaring a transition — was never
     active, so its `active_rules:` silently never applied;
  3. a mode with two triggers keyed its activity on the FIRST only, so the
     second fired and the condition never ended;
  4. `continue to <config-only sub-phase>` was accepted and jumped to an item
     the driver skips, because a designer reads a `phase` name as jumpable.

The invariant that removes all four: **every mode is exactly one of a
transition SOURCE or a transition TARGET** — the "before" side of one
condition, or the "after" side. A source stays active until ANY of its targets
has fired; a target is active once its own name has fired. Modes are
INDEPENDENT conditions, not an exclusive state machine: N of them may be
active at once and their rule deltas stack, which is what makes two unrelated
conditions ("hearts broken", "queen played") expressible without encoding
their product.

Completeness ledger (decisions.md "Closed-domain completeness")
--------------------------------------------------------------
property:   every combination of item x container is either implemented or
            rejected in its owning layer's currency; every mode-set shape is
            either given a defined meaning or walled
domain:     (a) `?phase_item` alternatives x {phase body, mode body};
            (b) `mode_def` x every item container in the grammar;
            (c) the per-mode role 2x2, (declares a transition) x (is targeted);
            (d) the mode-SET shapes of one phase body
registry:   `tests/mode_axes.py` — `phase_item_alternatives()` and
            `item_containers()` scrape the grammar, `mode_roles()` crosses the
            2x2 in code, `statement_alternatives()` bounds the sampled row.
            Each raises rather than returning an empty tuple, so a drifted
            scrape reddens instead of covering nothing.
covered:    - (a) test_item_in_container, 9 x 2 = 18 cells
            - (b) test_mode_placement, 1 x 4 containers
            - (c) test_mode_role, the full 2x2
            - (d) test_mode_set_shape, all 7 shapes
sampled:    `?phase_item`'s `statement` alternative is one grid cell, not 20:
            `?mode_item` names no `statement` alternative at all, so every
            statement form is rejected by the same absence of a production.
            Three representatives (assignment, movement, control flow) stand
            for the 20 that `statement_alternatives()` enumerates; a per-form
            crossing would test Lark's alternation, not this surface.
residual:   - a genuine 3+ stage progression has no mode encoding and routes
              to a state variable with `applies_when`. Walled by the role 2x2's
              `both` cell with a diagnostic naming that route. R3 — a designer
              with three rule sets meets it. Growth slot, issue #262.
            - `mode` nested inside `mode` rejects (grid (b)); the growth slot
              is deliberate and shares issue #262.
            - the mode-SET axis (d) is hand-listed, not derived: it is a
              property of a graph the grammar imposes no shape on, so it has
              no defining site to scrape. Recorded here rather than presented
              as derived coverage.
"""

from __future__ import annotations

import pytest

from cardlang.diagnostics import DiagnosticError
from cardlang.parse import parse_text
from cardlang.pipeline import check_dsl
from tests.mode_axes import (
    item_containers,
    mode_item_alternatives,
    mode_roles,
    mode_set_shapes,
    phase_item_alternatives,
)

# --------------------------------------------------------------------------
# Fixtures: one minimal game, with the item under test spliced into a body.
# --------------------------------------------------------------------------

_RULE = """
rule MustFollow {
  constrains: play_to_trick
  demands: legal_cards(hand[actor], pile)
}
"""


def _game(phase_body: str) -> str:
    return f"""
game Mini {{
  players: 2
  max_length: 1000
  cards: standard52
  ranking: A K Q J 10 9 8 7 6 5 4 3 2
  zones {{ deck : Deck  hand[player] : Hand<player>  pile : TrickPile }}
  state {{ score[player] : Integer = 0  ldr : Player = 0 }}
  phase root {{
{phase_body}
  }}
  winner: highest score
}}
{_RULE}
"""


# One representative sentence per `?phase_item` alternative. Keyed by the
# grammar's own alternative names so a new alternative shows up as a KeyError
# here rather than as a quietly missing grid row.
_ITEM_SNIPPET = {
    "state_block": "state { t : Integer = 0 }",
    "active_rules": "active_rules: [MustFollow]",
    "legal_moves": "legal_moves: [play_to_trick]",
    "transition_to": "transition_to: after when play_to_trick",
    "before_each": "before_each { ldr := 0 }",
    "after_each": "after_each { ldr := 0 }",
    "phase": "phase inner { ldr := 0 }",
    "statement": "ldr := 0",
    "mode_def": "mode m { transition_to: after when play_to_trick }",
}

# The two items a mode body admits. Everything else is a syntax error there:
# a mode's body IS its behavior, so anything executable in it would be a
# statement nobody runs — the accepted-but-ignored class, moved to the
# earliest layer that can own it.
_MODE_BODY_ADMITS = frozenset({"active_rules", "transition_to"})


def _parses(src: str) -> bool:
    try:
        parse_text(src, "mini.cardlang")
    except DiagnosticError as exc:
        assert "syntax error" in str(exc), f"expected a parse-layer failure, got: {exc}"
        return False
    return True


def _require_construct_exists() -> None:
    """A rejection cell is vacuous until the construct it rejects INTO parses.

    Without this, every "X is not allowed in a mode body" cell passes while
    `mode` itself is a syntax error — the snippet is blamed for the container's
    own failure, and the grid reports full coverage of a surface that does not
    exist. This is the vacuously-green class, and a grid for a not-yet-minted
    construct is exactly where it hides.
    """
    assert _parses(_game("    mode m { }")), (
        "`mode { }` does not parse, so every rejection cell below would pass "
        "for the container's reason rather than the cell's"
    )


# --------------------------------------------------------------------------
# (a) item x container
# --------------------------------------------------------------------------


@pytest.mark.parametrize("item", sorted({*phase_item_alternatives(), "mode_def"}))
@pytest.mark.parametrize("container", ["phase", "mode"])
def test_item_in_container(item: str, container: str) -> None:
    """Every phase-item alternative, in a phase body and in a mode body.

    `transition_to` is the cell that MOVES: it leaves `?phase_item` and becomes
    legal only inside a mode, which is what makes "which modes exist" a
    question with an answer at parse time rather than a structural sniff.
    """
    snippet = _ITEM_SNIPPET[item]
    if container == "phase":
        # No sibling mode here: a `transition_to`'s target need not exist to
        # PARSE, and adding one would make every phase cell fail for the
        # sibling's reason instead of its own.
        body = f"    {snippet}"
        expected = item != "transition_to"
    else:
        _require_construct_exists()
        body = f"    mode m {{ {snippet} }}"
        expected = item in _MODE_BODY_ADMITS

    assert _parses(_game(body)) is expected


def test_mode_body_admits_exactly_the_documented_items() -> None:
    """The `?mode_item` production and this module's expectation are one list.

    Pins the grid's `_MODE_BODY_ADMITS` against the grammar so a future
    alternative added to `?mode_item` cannot leave the grid silently testing
    the old, narrower surface.
    """
    assert frozenset(mode_item_alternatives()) == _MODE_BODY_ADMITS


# --------------------------------------------------------------------------
# (b) where a mode may be declared
# --------------------------------------------------------------------------

_CONTAINER_SOURCE = {
    "top": "mode m { }\n" + _game("    ldr := 0"),
    "library": "library L {\n  mode m { }\n}\n",
    "game": _game("    ldr := 0").replace("  phase root {", "  mode m { }\n  phase root {"),
    "phase": _game("    mode m { transition_to: after when play_to_trick }\n    mode after { }"),
}


@pytest.mark.parametrize("container", sorted(item_containers()))
def test_mode_placement(container: str) -> None:
    """A mode is declared in a phase body and nowhere else.

    The other three are decisions, not omissions: a game-level mode has no
    phase whose rules it could delta, and a library-level one would let a
    family library ship a condition it cannot scope. Both wait for a witness
    game (issue #262).
    """
    _require_construct_exists()
    assert _parses(_CONTAINER_SOURCE[container]) is (container == "phase")


# --------------------------------------------------------------------------
# (c) the per-mode role 2x2
# --------------------------------------------------------------------------


def _role_game(source: bool, target: bool) -> str:
    """A phase holding mode `m` with the requested role, plus the siblings
    needed to give it that role and nothing more."""
    m_body = "transition_to: sink when play_to_trick" if source else "active_rules: [MustFollow]"
    modes = [f"mode m {{ {m_body} }}"]
    if source:
        modes.append("mode sink { }")
    if target:
        # A sibling naming `m` is what makes `m` a target.
        modes.append("mode feeder { transition_to: m when play_to_trick }")
    return _game("\n".join(f"    {line}" for line in modes))


@pytest.mark.parametrize(("source", "target"), mode_roles())
def test_mode_role(source: bool, target: bool) -> None:
    """Exactly one of source or target. Both rejects are proven defects.

    `both` is the chain (or self-loop): before this wall, mode 2 of a
    three-mode chain was active from t=0 because its own activity was keyed on
    ITS target having fired, not on its having been entered.

    `neither` is the orphan: `_delta_active` reported a transition-less mode
    active only once its own name appeared in `fired_transitions`, which for a
    mode nobody targets never happens — so its `active_rules:` were dead.
    """
    _require_construct_exists()
    src = _role_game(source, target)
    if source ^ target:
        check_dsl(src, "mini.cardlang")  # accepts; raises on any diagnostic
        return
    with pytest.raises(DiagnosticError) as ei:
        check_dsl(src, "mini.cardlang")
    message = str(ei.value)
    if source and target:
        assert "chain" in message or "both" in message, message
    else:
        assert "never active" in message or "orphan" in message, message


# --------------------------------------------------------------------------
# (d) the mode-SET shapes of one phase body
# --------------------------------------------------------------------------

_SET_SOURCE = {
    # One condition. Hearts and spades: the entire corpus.
    "single_pair": ["mode a { transition_to: b when play_to_trick }", "mode b { }"],
    # Two unrelated conditions. Both sources live at phase entry and their
    # deltas stack — the shape exclusive-mode semantics could not express.
    "independent_pairs": [
        "mode a { transition_to: b when play_to_trick }",
        "mode b { }",
        "mode c { transition_to: d when play_to_trick }",
        "mode d { }",
    ],
    # Two conditions ending together.
    "shared_terminal": [
        "mode a { transition_to: z when play_to_trick }",
        "mode c { transition_to: z when play_to_trick }",
        "mode z { }",
    ],
    # One condition, several ways out: active until ANY target has fired.
    "fan_out": [
        "mode a { transition_to: b when play_to_trick\n            transition_to: c when play_to_trick }",
        "mode b { }",
        "mode c { }",
    ],
    "chain": [
        "mode a { transition_to: b when play_to_trick }",
        "mode b { transition_to: c when play_to_trick }",
        "mode c { }",
    ],
    "self_loop": ["mode a { transition_to: a when play_to_trick }"],
    "orphan": ["mode a { active_rules: [MustFollow] }"],
}

_SET_ACCEPTS = frozenset({"single_pair", "independent_pairs", "shared_terminal", "fan_out"})


@pytest.mark.parametrize("shape", sorted(mode_set_shapes()))
def test_mode_set_shape(shape: str) -> None:
    """How the modes of one phase body may relate to each other.

    Accepting `independent_pairs` is the load-bearing one: modes are
    independent conditions, so two sources are both active at entry and their
    deltas stack. `fan_out` is why a source is active until ANY of its targets
    has fired rather than until its first — before that, a second trigger
    fired and the condition simply did not end.
    """
    _require_construct_exists()
    src = _game("\n".join(f"    {line}" for line in _SET_SOURCE[shape]))
    if shape in _SET_ACCEPTS:
        check_dsl(src, "mini.cardlang")
        return
    with pytest.raises(DiagnosticError) as ei:
        check_dsl(src, "mini.cardlang")
    # Not a bare `raises`: a syntax error would satisfy that, so a rejected
    # shape would go green while the wall it names did not exist.
    message = str(ei.value)
    assert "syntax error" not in message, (
        f"{shape} was rejected by the parser, not by the mode-role wall: {message}"
    )
    assert "mode" in message, message
