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
            (d) the mode-SET shapes of one phase body;
            (e) nesting depth, since `?phase_item` includes `phase`;
            (f) for each ACCEPTED shape, what the runtime then does with it —
            a mode name is unique game-wide because the runtime keys reached
            transitions by bare name, and a source's exits die with it
registry:   `tests/mode_axes.py` — `phase_item_alternatives()` and
            `item_containers()` scrape the grammar, `mode_roles()` crosses the
            2x2 in code, `statement_alternatives()` bounds the sampled row.
            Each raises rather than returning an empty tuple, so a drifted
            scrape reddens instead of covering nothing.
covered:    - (a) test_item_in_container, 9 x 2 = 18 cells
            - (b) test_mode_placement, 1 x 4 containers
            - (c) test_mode_role, the full 2x2
            - (d) test_mode_set_shape, all 7 shapes
            - (e) test_the_role_wall_reaches_every_nesting_depth, depths 1-3
              (the corpus declares its modes at depth 3, this grid's other
              cells at depth 1)
            (f) is NOT covered — see `sampled` and `residual`.
sampled:    (f), the RUNTIME behaviour of the shapes (a)-(e) accept, is
            covered by EXAMPLE only, and the examples were retrofitted: each
            was written after a review round pointed at it, so the set is a
            record of what reviewers happened to find, not a derivation. Only
            `fan_out` has a runtime test at all; `single_pair` and
            `independent_pairs` have none, (e)x(f) is uncrossed, and the two
            mode-name pins are `check_dsl` rejections rather than runtime.
            Derived coverage of this axis is issue #271 — enumerate the mode
            graphs the grammar admits and assert the invariant, rather than
            choosing shapes by hand.

            `?phase_item`'s `statement` alternative is one grid cell, not 20:
            `?mode_item` names no `statement` alternative at all, so every
            statement form is rejected by the same absence of a production.
            Three representatives (assignment, movement, control flow) stand
            for the 20 that `statement_alternatives()` enumerates; a per-form
            crossing would test Lark's alternation, not this surface.
residual:   - three RUNTIME behaviours reachable through this surface are
              pre-existing engine semantics this change neither introduced nor
              worsened, each verified identical on the merge base: a mode is
              inert when the phase's decision site sits in a nested phase
              (`compute_active_rules` reads `ctx.current_phase` with no
              ancestor walk); `fired_transitions` clears per ITERATION of a
              `repeat until`-qualified phase, so an unrelated nested loop
              phase wipes a live ancestor's mode state; and a mode's delta
              applies for the remainder of the trick in which its condition
              ends (`trick_ctx` is computed once per trick). R2/R2/R3,
              issue #282 — walled by nothing, which is why they are here.
            - a genuine 3+ stage progression has no mode encoding and routes
              to a state variable with `applies_when`. Walled by the role 2x2's
              `both` cell with a diagnostic naming that route. R3 — a designer
              with three rule sets meets it. Growth slot, issue #266.
            - `mode` nested inside `mode` rejects (grid (b)); the growth slot
              is deliberate and shares issue #266.
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
  applies_when: state.led_suit is not none
  demands: cards in hand where card.suit is state.led_suit
  if_impossible: hand
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


# The UNION of what either container admits, not `phase_item` alone. Deriving
# from one container drops exactly the items the other one owns: the moment
# `transition_to` left `?phase_item` its "rejected in a phase body" cell would
# have disappeared from the grid — a coverage loss caused by the very change
# the grid exists to check.
@pytest.mark.parametrize(
    "item", sorted({*phase_item_alternatives(), *mode_item_alternatives()})
)
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
    # Appeared as a cell nobody wrote the moment `mode_item*` joined the
    # grammar — which is the whole reason the container axis is scraped.
    "mode": _game("    mode outer { mode inner { } }"),
}


@pytest.mark.parametrize("container", sorted(item_containers()))
def test_mode_placement(container: str) -> None:
    """A mode is declared in a phase body and nowhere else.

    The other three are decisions, not omissions: a game-level mode has no
    phase whose rules it could delta, and a library-level one would let a
    family library ship a condition it cannot scope. Both wait for a witness
    game (issue #266).
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
    # Two sources naming one target. Reads as "two conditions ending
    # together"; the runtime makes it one condition with two triggers and two
    # different deltas, so it is walled.
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

_SET_ACCEPTS = frozenset({"single_pair", "independent_pairs", "fan_out"})


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


# --------------------------------------------------------------------------
# Misuse probes (audit Step 2) — the plausible wrong sentences, each proven
# loud in its owning layer's currency.
# --------------------------------------------------------------------------


def test_retired_spelling_names_the_replacement() -> None:
    """A mode written as a `phase`, which is how every pre-#208 file spells it.

    This is the highest-traffic wrong sentence in the language after the split,
    so a bare "no terminal matches ':'" would be the wrong currency in
    practice: located, but naming neither the mistake nor the fix.
    """
    src = _game(
        "    phase hearts_not_broken {\n"
        "      transition_to: after when play_to_trick\n"
        "    }\n"
        "    mode after { }"
    )
    with pytest.raises(DiagnosticError) as ei:
        check_dsl(src, "mini.cardlang")
    assert "`transition_to:` is a mode clause" in str(ei.value)


def test_legal_moves_in_a_mode_names_the_replacement() -> None:
    """The mirror direction: a phase clause written in a mode body."""
    src = _game(
        "    mode m {\n"
        "      legal_moves: [play_to_trick]\n"
        "      transition_to: after when play_to_trick\n"
        "    }\n"
        "    mode after { }"
    )
    with pytest.raises(DiagnosticError) as ei:
        check_dsl(src, "mini.cardlang")
    assert "`legal_moves:` is a phase clause" in str(ei.value)


def test_legal_moves_delta_operator_is_a_grammar_error() -> None:
    """`legal_moves: [+ X]` — the symmetry with `active_rules` that the spec
    once claimed. The grammar admits only bare names here, so it fails at
    parse. Carried over from the wall module this grid replaced: the wall's
    own domain dissolved with `_is_rule_delta`, but this boundary-token
    probe is about `legal_moves`'s list syntax and outlives it."""
    assert not _parses(_game("    legal_moves: [+ play_to_trick]"))


def test_transition_predicate_is_typechecked_inside_a_mode() -> None:
    """A wrong-typed transition predicate must still be caught.

    The arm that checks it used to match `n.TransitionTo` as a PHASE item;
    once transitions moved inside modes, that arm stopped matching anything
    and the predicate would have gone unchecked — a wall silently emptied by
    the very change that reorganised the surface.
    """
    src = _game(
        "    mode m { transition_to: after when play_to_trick\n"
        "             where action.card.nosuch is hearts }\n"
        "    mode after { }"
    )
    with pytest.raises(DiagnosticError) as ei:
        check_dsl(src, "mini.cardlang")
    # A TYPE error specifically: an unresolved-name probe would be caught by
    # resolve and would stay green with this arm deleted, which is the shape
    # of pin that guards nothing.
    assert "has no field" in str(ei.value), str(ei.value)

    # red under: delete the `case n.Mode()` arm in `check_phase_positions`
    # (typecheck.py) and this goes green — the predicate is never typechecked.


@pytest.mark.parametrize("depth", [1, 2, 3])
def test_the_role_wall_reaches_every_nesting_depth(depth: int) -> None:
    """Modes at depth, since `?phase_item` includes `phase` and the corpus puts
    them three levels down.

    A wall written against one level is the shape that guards the fixture and
    not the games: this grid's other cells all sit at depth 1, while hearts and
    spades declare their modes at depth 3.
    """
    body = "    mode orphan { active_rules: [MustFollow] }"
    for level in range(depth - 1):
        body = f"    phase nest{level} {{\n  {body}\n    }}"
    with pytest.raises(DiagnosticError) as ei:
        check_dsl(_game(body), "mini.cardlang")
    assert "never active" in str(ei.value), str(ei.value)


# --------------------------------------------------------------------------
# (f) the runtime behaviour of an accepted shape — the cells a grid that only
# asks "does check_dsl accept?" cannot reach.
# --------------------------------------------------------------------------


def _play(src: str, seeds: range) -> list[tuple[str, ...]]:
    """Every distinct `fired_transitions` set the `root` phase is observed in."""
    import random

    from cardlang.runtime import driver, mechanics
    from cardlang.runtime import phases as ph

    seen: list[tuple[str, ...]] = []
    real = ph.compute_active_rules

    def spy(phase, rs):  # type: ignore[no-untyped-def]
        out = real(phase, rs)
        if phase is not None and phase.name == "root":
            fired = tuple(sorted(rs.fired_transitions))
            if fired not in seen:
                seen.append(fired)
        return out

    # Patching the `phases` module attribute is the whole patch: both callers
    # reach it as `phases.compute_active_rules`, neither holds its own
    # reference. (An earlier version also looped over `driver`/`mechanics`
    # guarded by `hasattr` — dead code that read as defensive breadth.)
    ph.compute_active_rules = spy
    try:
        game = check_dsl(src, "mini.cardlang")
        for seed in seeds:
            driver.play_game(game, random.Random(seed))
    finally:
        ph.compute_active_rules = real
    return seen


# Whether ONE play can satisfy more than one of a mode's exits is its own
# axis, and the pin was blind to it at first: two mutually exclusive
# predicates cannot both match a single card, so only the across-plays half
# of the defect was reachable. Overlapping exits are the other half.
@pytest.mark.parametrize(
    ("label", "low_pred", "high_pred"),
    [
        ("disjoint", ' where action.card.rank is "2"', ' where action.card.rank is "9"'),
        ("overlapping", "", ""),
    ],
)
def test_a_fan_out_reaches_exactly_one_of_its_targets(
    label: str, low_pred: str, high_pred: str
) -> None:
    """A source mode's remaining exits die with it.

    `fan_out` is ACCEPTED by the grid above, and acceptance is all that grid
    can see — it asks whether `check_dsl` takes the sentence, never what the
    runtime then does with it. Before this pin, the flattened transition list
    dropped which mode owned each exit, so a source whose first target had
    fired kept its second exit live: both targets were reached and two
    mutually alternative "after" modes held at once, rule deltas stacked.

    red under (disjoint): drop the `_mode_active` filter in
    `runtime/phases.py::active_mode_exits`.
    red under (overlapping): drop the `break` in
    `runtime/mechanics.py::_fire_transitions` — the filter alone cannot see a
    mode that goes inactive between two exits of the SAME play.
    """
    src = _game(
        "    deal 4 cards from deck to each hand\n"
        "    mode start {\n"
        # Ranks, not suits: an undealt deck is not shuffled, so the first
        # eight cards are all clubs and a suit predicate could never match —
        # the probe would run, observe nothing, and pass.
        f"      transition_to: went_low when play_to_trick{low_pred}\n"
        f"      transition_to: went_high when play_to_trick{high_pred}\n"
        "    }\n"
        "    mode went_low { }\n"
        "    mode went_high { }\n"
        "    repeat until (all players where hand[player] is empty) {\n"
        "      round play_to_trick from ldr over all players source hand into pile\n"
        "            winner highest_of_led_suit\n"
        "      move all cards from pile to deck\n"
        "      ldr := winner\n"
        "    }"
    )
    reached = _play(src, range(1, 40))
    # Anti-vacuity: `[()]` is truthy, so "did we observe anything" is not the
    # question — "did any transition ever fire" is. Without this the probe
    # passes while proving nothing, which is how it first shipped.
    assert any(fired for fired in reached), (
        f"no transition ever fired, so this proves nothing about fan-out: {reached}"
    )
    both = [f for f in reached if len(f) > 1]
    assert not both, f"mutually alternative exits both reached: {both}"


def test_a_mode_name_is_unique_game_wide_not_merely_per_phase() -> None:
    """Two phases may not both declare a `done`.

    The runtime keys reached transitions by BARE mode name in one set that is
    cleared per hand, not per phase — so a same-named mode in another phase
    reads the first phase's transition as its own and starts life in its
    "after" mode. Uniqueness is game-wide precisely because the runtime's key
    is, which is the same reason `check("phase", …)` walks the whole game.

    red under: scope `check("mode", modes)`'s collection to one phase's items.
    """
    src = _game(
        "    mode fresh { transition_to: done when play_to_trick }\n"
        "    mode done { }\n"
        "    phase later {\n"
        "      mode unseen { transition_to: done when play_to_trick }\n"
        "      mode done { }\n"
        "    }"
    )
    with pytest.raises(DiagnosticError) as ei:
        check_dsl(src, "mini.cardlang")
    assert "mode 'done'" in str(ei.value), str(ei.value)


def test_two_sibling_modes_may_not_share_a_name() -> None:
    """The same wall at its narrowest scope: one reference cannot name two
    declarations, and activating both stacks deltas nobody asked for."""
    src = _game(
        "    mode fresh { transition_to: done when play_to_trick }\n"
        "    mode done { }\n"
        "    mode done { active_rules: [MustFollow] }"
    )
    with pytest.raises(DiagnosticError) as ei:
        check_dsl(src, "mini.cardlang")
    assert "mode 'done'" in str(ei.value), str(ei.value)


def test_a_parse_hint_never_diagnoses_the_author_s_position() -> None:
    """A hint says where the clause BELONGS, never where the author is.

    The parser reports a line, not an enclosing construct, so one entry fires
    both for a misplaced clause and for a correctly placed one with a bad
    argument list. An earlier wording asserted the container — and told a
    designer whose only mistake was a trailing comma, inside a perfectly good
    phase, to move `legal_moves:` into a phase.

    red under: reword either `_PARSE_HINTS` entry to name a container
    ("belongs to a `phase`, not a `mode`").
    """
    with pytest.raises(DiagnosticError) as ei:
        # A trailing comma. The clause is exactly where it belongs.
        check_dsl(_game("    legal_moves: [play_to_trick,]"), "mini.cardlang")
    message = str(ei.value)
    assert "`legal_moves:` is a phase clause" in message, message
    assert "not a `mode`" not in message, (
        f"the hint diagnosed a container it cannot observe: {message}"
    )
