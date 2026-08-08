"""Comparing the acting player against a name that already denotes them.

`for each player p:` binds the acting player to `p` for its body
(`domains.binds_actor`, `runtime/execute._for_each`), and the `actor` pronoun
READS the acting player — so inside that body `p` and `actor` are two names for
one value. `if p is not actor { … }` therefore has a body that never runs, and
`if p is actor { A } else { B }` has a dead `else`. Both typecheck: the operands
are both `Player`, so no type wall can see it, and no runtime check can fire on
a branch that is never taken. It is a *statically decidable* degeneracy that was
silently accepted — "an operand comparing as always-false", named as a defect in
decisions.md "Surface totality", reached here through a shadowed binder rather
than a wrong type.

The class is the ALIASING, not the `for each` spelling: every construct that
binds a seat to a name AND rebinds the acting player to that same seat makes the
pronoun an alias of the binder. Sweeping the class (decisions.md "Closed-domain
completeness") means `turns`, `each … simultaneously` and `as <name>` are cells
here beside `for each`, and so is the transitive `let me = actor` — and, on the
other side, that an INNER rebind un-aliases the outer binder, which is what
keeps the corpus idiom (`let w = actor` hoisted ABOVE the loop, then `p is w`)
legal.

Completeness ledger (decisions.md "Closed-domain completeness")
---------------------------------------------------------------
property:   an equality comparison whose two operands are NAMES that lexically
            provably denote the same acting player is refused by resolve with a
            located diagnostic; a comparison whose operands may differ at
            runtime is accepted AND plays. Every cell asserts both halves —
            accepted cells are executed (`play_game`), never merely resolved,
            since "resolves clean" is exactly the assertion that hid this
            defect.
domain:     THREE axes, each read off its own registry rather than off the wall.

            (1) The ALIAS-SOURCE axis: the `n.Stmt` union, every member
            classified as introducing an actor alias or not
            (`_ALIAS_SOURCE_KINDS` vs `_NO_ALIAS_KINDS`, pinned equal to the
            union). This axis is what puts `each … simultaneously` and the
            transitive `let` in the grid: neither was in the report that
            opened the question, both are the same defect.

            `Stmt` is the right registry for what REBINDS the acting player —
            only a statement can — but it is the wrong one for what SHADOWS an
            alias, and reading it for both is how a false positive shipped:
            `ProduceArm` belongs to neither the `Expr` nor the `Stmt` union (it
            hangs off `Produces`), so a `Stmt`-derived domain cannot see that a
            `produces:` arm binds names at all, and the sweep kept the outer
            alias inside an arm that had rebound the name. Shadowing is
            therefore derived from `_introduced_binders` over the whole `Node`
            union instead — the same registry, and the same node kind, whose
            escape `tests/test_binder_registry.py` already records.

            (2) The OPERATOR axis: the equality operators, derived from
            `typecheck.OP_CLASSES` (`OpClass.EQUALITY`) — the same registry
            the type layer's own always-false wall dispatches through — crossed
            with operand ORDER, so `actor is p` cannot pass while `p is actor`
            fails. Stopping at the equality class is a decision the registry's
            OTHER classes were checked against, not an unexamined narrowing:
            ORDERING refuses `Player` operands outright in the type layer
            (`test_ordering_two_players_is_already_a_type_error`, parametrized
            over that class), so the degeneracy is unreachable there, and
            MEMBERSHIP takes a collection on its right, so its operands are
            never two names for one player.

            (3) The SCOPE-RELATION axis: for each alias source, whether the
            comparison sits under it, under an inner rebind that un-aliases it
            (`as`, a nested seat loop), under a VALUE loop that does not rebind
            and so preserves the alias, under a binder that SHADOWS the alias
            name (a query binder, a `let` rebinding it, a `let`'s index), or
            above it entirely (the hoisted-let idiom). This axis holds the
            false positives a naive "`actor` under `for each player`" wall
            would produce — every entry in it was written because the wall got
            that cell wrong, or would have.
registry:   `n.Stmt` (alias sources); `typecheck.OP_CLASSES` (operators);
            `domains.binds_actor` / `domains.SIMULTANEOUS_ROLES` (which roles
            rebind the actor at all — a VALUE domain's binder is not an alias);
            `resolve._PRONOUNS` for the pronoun axis, whose acting-player
            member is pinned BEHAVIOURALLY (a pronoun tracks `acting_as` or it
            does not) rather than asserted, so a second acting-player pronoun
            cannot join the language unnoticed.
covered:    the two parametrized grids below — `test_provably_equal_operands_
            are_refused` (alias sources x operators x order) and
            `test_contingent_comparisons_are_accepted_and_play` (scope
            relations x operators x order) — plus the union/registry pins, the
            pronoun behaviour pin, and the misuse probes: a role no registry
            row defines must still reach the author as its OWN located
            diagnostic rather than as this sweep's registry lookup raising in
            compiler currency (`test_a_role_no_row_defines_still_gets_its_own_
            diagnostic` — the metamorphic reorder suite found that one, on a
            `for each column c` this grid had no cell for), and the procedure
            pronoun wall that bounds the residual below.
sampled:    one fixture game (2 players, `standard52`, a hand and a bid zone),
            with every cell spliced into one `as 0 { … }` block so an acting
            player exists at the top of every cell. A cell whose answer could
            depend on the SHAPE of the game rather than on the scope relation
            would be sampled by proxy here — none is known: the rule reads
            names and binding constructs only, never zones, seats or content.
residual:   an alias created by `expand`, not by the source: `run f(p, actor)`
            inside `for each player p` binds both parameters to lets in the
            caller's context, so a `q is r` inside f's body becomes a
            tautology at THAT call site and stays meaningful at others. Not
            reachable through the pronoun (a procedure body may not read
            `actor` at all — `resolve._check_procedures`, pinned by
            `test_procedure_bodies_cannot_read_the_actor_pronoun` below), so
            the surviving shape needs two parameters both bound to the acting
            player at one call site. It is interprocedural and call-site
            dependent, the sweep runs pre-expansion, and it is recorded in
            this ledger, which owns it. Deliberately NOT residual, and
            NOT a gap: a comparison whose operands are equal only through a
            call (`team_of(p) is team_of(actor)`) is outside the property
            above, which quantifies over NAMES; and a merely redundant read
            (`hand[actor]` where `hand[p]` would do) is accepted by design —
            it is redundant, not wrong, and this is a totality wall, not a
            lint.
"""

from __future__ import annotations

import random
from typing import Any, get_args

import pytest

from cardlang.ast import nodes as n
from cardlang.diagnostics import DiagnosticError
from cardlang.domains import Role, binds_actor
from cardlang.pipeline import check_dsl
from cardlang.resolve import _BINDER_SCOPE_FIELDS, _PRONOUNS, _introduced_binders
from cardlang.runtime.driver import play_game
from cardlang.runtime.evaluate import evaluate
from cardlang.runtime.state import Ctx
from cardlang.typecheck import OP_CLASSES, OpClass

# --- axis 2: the equality operators, off the type layer's own registry -------
#
# The surface spelling of each: the grammar builds `is`/`is not` into the
# internal `==`/`!=` (cardlang.lark, "Equality is the word `is` / `is not`"), so
# a grid over source text needs the map. Pinned complete against the registry
# below, rather than hand-listed here and trusted.
_EQUALITY_SURFACE: dict[str, str] = {"==": "is", "!=": "is not"}

EQUALITY_OPS: tuple[str, ...] = tuple(
    sorted(op for op, cls in OP_CLASSES.items() if cls is OpClass.EQUALITY)
)


def test_the_operator_axis_is_the_equality_class_of_the_registry() -> None:
    """The grid's operator axis is `OP_CLASSES`' equality class, not a pair of
    spellings someone remembered. A third equality operator lands here as a
    missing surface spelling instead of as a silently unswept cell.

    red under: drop the `!=` entry from `_EQUALITY_SURFACE`."""
    assert set(_EQUALITY_SURFACE) == set(EQUALITY_OPS)


@pytest.mark.parametrize(
    "op", sorted(op for op, cls in OP_CLASSES.items() if cls is OpClass.ORDERING)
)
def test_ordering_two_players_is_already_a_type_error(op: str) -> None:
    """Why the wall stops at the equality class, stated as a check rather than
    left as an unexamined narrowing. An ORDERING comparison of two names that
    both denote the acting player would be just as statically determined (`p <
    actor` always false) — but ordering does not accept `Player` operands at
    all, so the degeneracy is unreachable through that class and the type layer
    owns the refusal. The remaining class, MEMBERSHIP, takes a collection on
    the right, so its operands are never two names for one player.

    If Player ever becomes orderable this goes red, which is the signal to
    widen `_check_alias_operands` past `("==", "!=")`.

    red under: add `TPlayer` to the operand types
    `typecheck._check_ordering_operands` admits."""
    body = f"for each player p: if p {op} actor {{ hits[p] += 1 }}"
    with pytest.raises(DiagnosticError) as exc:
        check_dsl(_game(body=body), "ordering.cardlang")
    assert "Integer" in exc.value.diagnostic.message, exc.value.diagnostic.message


# --- axis 1: which statement kinds introduce an alias of the acting player ---
#
# Derived from the `n.Stmt` union: every member is classified, so a new
# statement form that binds a seat and rebinds the actor cannot join the
# language without answering this question.
_ALIAS_SOURCE_KINDS: frozenset[str] = frozenset(
    {
        "ForEach",  # over a `binds_actor` role only — a VALUE role binds no actor
        "EachSimultaneous",  # binds the role noun (`player`) as the local
        "Turns",  # binds the turn's player
        "AsBlock",  # when its player expression is a name already denoting a seat
        "LetStmt",  # transitively: `let me = actor`, `let me = p`
    }
)

_NO_ALIAS_KINDS: frozenset[str] = frozenset(
    {
        # No lexical statement body at all: nothing of theirs can sit "inside"
        # a rebind. `Offer`/`Round` DO rebind the acting player, but they do it
        # for a move type's effect, which is a separate declaration root.
        "Offer",
        "Round",
        "Transfer",
        "EpistemicOp",
        "RotateStmt",
        "AssignStmt",
        "Produce",
        "ContinueTo",
        "SkipToNextHand",
        "RunStmt",
        # Bodies that neither bind a seat nor rebind the actor: they pass the
        # enclosing alias set through unchanged.
        "IfStmt",
        "RepeatUntil",
        "Produces",
        "Block",
    }
)


def test_every_statement_kind_is_classified_on_the_alias_axis() -> None:
    """The alias-source axis IS the `Stmt` union, not a list of the constructs
    that happened to motivate the wall. `each … simultaneously` and the
    transitive `let` are in the grid because this test put them there.

    red under: delete `"Turns"` from `_ALIAS_SOURCE_KINDS`."""
    assert _ALIAS_SOURCE_KINDS | _NO_ALIAS_KINDS == {t.__name__ for t in get_args(n.Stmt)}
    assert not (_ALIAS_SOURCE_KINDS & _NO_ALIAS_KINDS)


def test_only_a_seat_role_binder_aliases_the_actor() -> None:
    """`for each` is an alias source only over a role whose members ARE actors.
    The registry decides, not the construct: `for each suit s` binds a name and
    rebinds nothing, so an enclosing alias survives it (a grid cell below), and
    `s` itself never aliases.

    red under: return `True` unconditionally from `domains.binds_actor`."""
    assert binds_actor(Role.PLAYER)
    assert not any(
        binds_actor(role) for role in (Role.TEAM, Role.SUIT, Role.RANK)
    )


def test_a_binder_kind_can_be_absent_from_the_scope_field_table() -> None:
    """Why the sweep shadows in EVERY field when `_BINDER_SCOPE_FIELDS` has no
    entry for a node — the combination that produced a false positive, pinned
    as two facts about the live registries rather than as a remembered story.

    A `produces:` arm binds its payload names, but `_rewrite` scopes arm bodies
    through a path of its own, so `ProduceArm` carries no row in the
    scope-field table. Reading that table as the whole scoping story left the
    arm's binder aliasing the acting player and REFUSED the sound `won(p) { p
    is actor }`. `ProduceArm` also belongs to neither the `Expr` nor the `Stmt`
    union (it hangs off `Produces`), which is how a `Stmt`-derived domain — the
    alias-source axis in this module's ledger — cannot see it at all; the same
    lesson `tests/test_binder_registry.py` records for the same node kind.

    red under: give `ProduceArm` an entry in `_BINDER_SCOPE_FIELDS` while the
    sweep's fallback stays conservative (this pin goes red where the behaviour
    cell would not, since precise and conservative agree for that node)."""
    arm = n.ProduceArm(tag="won", binders=("p",), body=())
    assert _introduced_binders(arm) == ("p",), "a produces: arm binds its payloads"
    assert n.ProduceArm not in _BINDER_SCOPE_FIELDS, (
        "`ProduceArm` gained a scope-field entry — the sweep's conservative "
        "all-fields default is no longer what shadows it; re-check the "
        "`produce_arm_binder_shadows` cell against the new entry"
    )
    assert n.ProduceArm not in get_args(n.Stmt) and n.ProduceArm not in get_args(n.Expr)
    """The pronoun axis, checked as BEHAVIOUR rather than asserted: a pronoun
    is an acting-player pronoun exactly when its value FOLLOWS `acting_as`. So
    evaluate every pronoun in two contexts that differ in nothing but the
    acting player, and collect the ones whose value moved. `actor` is the only
    one today; a second one reading `ctx.current_player` joins that set by
    behaviour, and fails here instead of shipping unswept — which a test
    asserting the name `actor` against itself could never do. Mirrors
    `test_domain_registry`'s treatment of the `binds_actor` column.

    red under: add `case "dealer": return ctx.current_player` to
    `runtime/evaluate._pronoun` and `"dealer"` to `resolve._PRONOUNS`."""
    captured: dict[str, Any] = {}
    play_game(
        check_dsl(_game(body="offer to 0 one of [mark]"), "pronoun.cardlang"),
        random.Random(0),
        on_first_decision=lambda rs: captured.setdefault("rs", rs),
    )
    base = Ctx(rs=captured["rs"], chooser=lambda p, c, k: list(c[:k]))

    def read(pronoun: str, seat: int) -> object:
        """The pronoun's value with `seat` acting — or the way it refused."""
        ref = n.NameRef(pronoun, ref_kind="pronoun")
        try:
            return evaluate(ref, base.acting_as(seat))
        except Exception as exc:  # noqa: BLE001 -- a pronoun undefined here is a stable answer; narrowing makes the grid vacuous for every pronoun that refuses
            return f"{type(exc).__name__}"

    tracking = {p for p in _PRONOUNS if read(p, 0) != read(p, 1)}
    assert tracking == {"actor"}, (
        f"the alias grid sweeps the acting-player pronoun(s); {sorted(tracking)} "
        f"track `acting_as` and each needs its own cells"
    )


# --- the fixture -------------------------------------------------------------


def _game(body: str = "hits[0] += 0", effect: str = "hits[target] += 1") -> str:
    """One 2-player game with two slots for a cell.

    `body` splices into an `as 0 { … }` block in the phase, so an acting player
    exists at the top of the cell and `actor` is readable there; `as 0` binds a
    LITERAL, so it introduces no alias of its own and the cell's own construct
    is the only alias source. `effect` splices into a move type's effect — the
    OTHER root shape, where the acting player arrives from the call site rather
    than from anything lexically above, and where the corpus idiom this wall
    must not break actually lives (docs/games/tic-tac-toe.cardlang)."""
    return f"""
game G {{
  players: 2
  max_length: 200
  cards: standard52
  zones {{ deck : Deck  hand[player] : Hand<player>  bid[player] : Hand<player> }}
  state {{ hits[player] : Integer = 0  taker : Player = 0 }}
  phase play {{
    deal 2 cards from deck to each hand
    as 0 {{ {body} }}
  }}
  winner: highest hits
}}

move_type mark(target : Player) {{
  when: true
  effect {{ {effect} }}
}}
"""


def _arm_game(filled: str) -> str:
    """A `produces:` arm nested under a seat loop, its payload binder REUSING
    the loop binder's name. The arm's `p` is the produced player, not the
    acting one, so a comparison against `actor` inside it is contingent."""
    return f"""
define pick -> {{ won(Player) }} {{
  produce won(0)
}}
game G {{
  players: 2
  max_length: 200
  cards: standard52
  zones {{ deck : Deck  hand[player] : Hand<player>  bid[player] : Hand<player> }}
  state {{ hits[player] : Integer = 0  taker : Player = 0 }}
  phase play {{
    as 0 {{
      for each player p:
        pick produces:
          won(p) {{ {filled} }}
    }}
  }}
  winner: highest hits
}}
"""


def _spliced(slot: str, filled: str) -> str:
    """The fixture with `filled` in the named slot."""
    if slot == "arm":
        return _arm_game(filled)
    return _game(body=filled) if slot == "body" else _game(effect=filled)


def _cmp(left: str, right: str, op: str) -> str:
    return f"{left} {_EQUALITY_SURFACE[op]} {right}"


# --- grid 1: provably-equal operands, refused --------------------------------
#
# Each entry is (slot, template with a `{cmp}` hole, the two names that provably
# denote the acting player where the hole sits).
_REFUSED_SITES: dict[str, tuple[str, str, str, str]] = {
    "for_each_player": (
        "body",
        "for each player p: if {cmp} {{ hits[p] += 1 }}",
        "p",
        "actor",
    ),
    "turns": (
        "body",
        "turns t from 0 over all players until hits[0] > 0 {{ if {cmp} {{ hits[t] += 1 }} }}",
        "t",
        "actor",
    ),
    "each_simultaneously": (
        "body",
        ("each player simultaneously: "
         "move chosen 1 card from hand[player] where {cmp} to bid[player]"),
        "player",
        "actor",
    ),
    "as_name": (
        "body",
        "let q = 0  as q {{ if {cmp} {{ hits[q] += 1 }} }}",
        "q",
        "actor",
    ),
    # A `let` reads its value in the scope BEFORE it binds, so `let p = p`
    # re-binds `p` to the very player it already named. The mirror of
    # `let_rebinds_the_alias_name` in the accepted grid: same statement, and
    # only the right-hand side decides.
    "let_rebinds_itself": (
        "body",
        "for each player p: if true {{ let p = p  if {cmp} {{ hits[0] += 1 }} }}",
        "p",
        "actor",
    ),
    # The transitive cell: `me` denotes the actor, and inside the loop so does
    # `p` — neither operand is the pronoun, and the comparison is still dead.
    "let_alias_vs_binder": (
        "body",
        "for each player p: if true {{ let me = actor  if {cmp} {{ hits[p] += 1 }} }}",
        "p",
        "me",
    ),
    # A VALUE loop binds a name but rebinds no actor, so the enclosing alias
    # passes through it intact.
    "alias_survives_a_value_loop": (
        "body",
        "for each player p: for each suit s: if {cmp} {{ hits[p] += 1 }}",
        "p",
        "actor",
    ),
    # The innermost rebind is the one that counts: `q` aliases here, `p` does
    # not (that cell is in the accepted grid).
    "inner_seat_loop_binder": (
        "body",
        "for each player p: for each player q: if {cmp} {{ hits[q] += 1 }}",
        "q",
        "actor",
    ),
    # Both operands the pronoun itself: the degenerate limit of the same rule,
    # and it falls out rather than being special-cased.
    "pronoun_against_itself": (
        "body",
        "if {cmp} {{ hits[0] += 1 }}",
        "actor",
        "actor",
    ),
    # The other root: a move type's effect, whose acting player comes from the
    # call site. The loop rebinds it there exactly as it does in a phase.
    "move_effect_loop": (
        "effect",
        "for each player p: if {cmp} {{ hits[p] += 1 }}",
        "p",
        "actor",
    ),
}


@pytest.mark.parametrize("site", sorted(_REFUSED_SITES))
@pytest.mark.parametrize("op", EQUALITY_OPS)
@pytest.mark.parametrize("swap", [False, True], ids=["alias_left", "alias_right"])
def test_provably_equal_operands_are_refused(site: str, op: str, swap: bool) -> None:
    """The wall. Every construct that makes the acting player reachable under
    two names, crossed with both equality operators and both operand orders."""
    slot, template, left, right = _REFUSED_SITES[site]
    if swap:
        left, right = right, left
    filled = template.format(cmp=_cmp(left, right, op))
    with pytest.raises(DiagnosticError) as exc:
        check_dsl(_spliced(slot, filled), "alias.cardlang")
    assert exc.value.diagnostic.span is not None, "the diagnostic must be located"
    message = exc.value.diagnostic.message
    assert "same player" in message, message
    # The message names the construct that did the binding, so the fix is
    # readable off the diagnostic rather than inferred.
    assert left in message and right in message, message


# --- grid 2: contingent comparisons, accepted and played ---------------------

_ACCEPTED_SITES: dict[str, tuple[str, str, str, str]] = {
    # The corpus idiom (docs/games/tic-tac-toe.cardlang), in the root it
    # actually appears in: the outer actor is captured ABOVE the loop, so `w`
    # and `p` genuinely differ for one seat. This cell is why the IR goldens
    # stay byte-identical.
    "hoisted_let_above_the_loop": (
        "effect",
        "let w = actor  for each player p: if {cmp} {{ hits[p] += 1 }}",
        "p",
        "w",
    ),
    # An inner `as` rebinds the actor to something else, so the outer binder
    # stops aliasing. The false positive a naive wall would produce.
    "inner_as_block_un_aliases": (
        "body",
        "for each player p: as taker {{ if {cmp} {{ hits[p] += 1 }} }}",
        "p",
        "actor",
    ),
    # Same, via a nested seat loop: inside it `actor` is `q`, so `p` is free.
    "inner_seat_loop_un_aliases": (
        "body",
        "for each player p: for each player q: if {cmp} {{ hits[q] += 1 }}",
        "p",
        "actor",
    ),
    # A state variable is mutable, so `taker` is not PROVABLY the actor even
    # directly under `as taker` — a body write makes it differ. Conservative by
    # decision: the wall refuses only what it can prove.
    "as_a_mutable_state_var": (
        "body",
        "as taker {{ if {cmp} {{ hits[taker] += 1 }} }}",
        "taker",
        "actor",
    ),
    # An ordinary meaningful guard, the reason `for each player p` stays in the
    # language at all.
    "binder_against_a_state_var": (
        "body",
        "for each player p: if {cmp} {{ hits[p] += 1 }}",
        "p",
        "taker",
    ),
    # A move parameter against the actor: Go Fish's "not yourself" guard
    # (docs/games/go-fish.cardlang), the most common shape in the corpus.
    "move_param_against_actor": (
        "effect",
        "if {cmp} {{ hits[target] += 1 }}",
        "target",
        "actor",
    ),
    # A `produces:` arm binder shadows the alias: the arm's `p` is the produced
    # PAYLOAD, which need not be the acting player. Its scope lives outside
    # `_BINDER_SCOPE_FIELDS` (name classification handles arms specially), so
    # this cell is the witness for the sweep's conservative default — under the
    # table alone the sound comparison was refused.
    "produce_arm_binder_shadows": (
        "arm",
        "if {cmp} {{ hits[p] += 1 }}",
        "p",
        "actor",
    ),
    # A `let` REBINDING an alias name drops it: after `let p = taker`, `p` is
    # the taker, and comparing it against the actor is an ordinary test again.
    # The mirror image of the transitive `let` in the refused grid — the same
    # statement form, opposite answer, decided by what it is bound TO.
    "let_rebinds_the_alias_name": (
        "body",
        "for each player p: if true {{ let p = taker  if {cmp} {{ hits[0] += 1 }} }}",
        "p",
        "actor",
    ),
    # Same rule for a let's INDEX binder, which scopes to its own value only.
    "let_index_binder_shadows": (
        "body",
        ("for each player p: if true {{ let seen[p] = (if {cmp} then 1 else 0)  "
         "if seen[0] > 0 {{ hits[0] += 1 }} }}"),
        "p",
        "actor",
    ),
    # An inner binder REUSING an alias name shadows it: inside the query's
    # predicate `player` is the query's own binder, not the simultaneous
    # block's seat (docs/games/schnapsen.cardlang writes this comparison).
    # Shadowing falls out of `_introduced_binders`, so this cell is what
    # proves the wall reads that registry rather than matching on the name.
    "inner_binder_shadows_the_alias": (
        "body",
        ("each player simultaneously: move chosen 1 card from hand[player] "
         "where (the player where {cmp}) is not taker to bid[player]"),
        "player",
        "actor",
    ),
}


@pytest.mark.parametrize("site", sorted(_ACCEPTED_SITES))
@pytest.mark.parametrize("op", EQUALITY_OPS)
@pytest.mark.parametrize("swap", [False, True], ids=["alias_left", "alias_right"])
def test_contingent_comparisons_are_accepted_and_play(site: str, op: str, swap: bool) -> None:
    """The other half of the property. A comparison whose operands can differ
    at runtime survives the wall — and is PLAYED, because a cell that only
    resolved would pass on exactly the defect this file exists to close."""
    slot, template, left, right = _ACCEPTED_SITES[site]
    if swap:
        left, right = right, left
    filled = template.format(cmp=_cmp(left, right, op))
    play_game(check_dsl(_spliced(slot, filled), "alias.cardlang"), random.Random(0))


def test_the_grid_commands_both_outcomes() -> None:
    """A guard on the grid itself: the two parametrizations must disagree, or a
    wall that refused everything (or nothing) would read as green.

    red under: move any `_ACCEPTED_SITES` entry into `_REFUSED_SITES`."""
    assert _REFUSED_SITES and _ACCEPTED_SITES
    assert not (set(_REFUSED_SITES) & set(_ACCEPTED_SITES))


@pytest.mark.parametrize(
    "body,expected",
    [
        # A declared position domain is not a seat role, and `for each column c`
        # is refused above this sweep — but into the SAME diagnostic bag, so the
        # sweep still walks the tree holding it.
        ("for each column c: hits[0] += 1", "unknown `for each` role"),
        # The simultaneous form's role set is narrower than the iterable one.
        (
            "each suit simultaneously: move chosen 1 card from hand[0] to bid[0]",
            "simultaneous",
        ),
    ],
    ids=["position_domain_role", "value_role_simultaneous"],
)
def test_a_role_no_row_defines_still_gets_its_own_diagnostic(
    body: str, expected: str
) -> None:
    """A malformed role must reach the author as the located diagnostic that
    names it, never as this sweep's registry lookup raising in compiler
    currency — which would suppress every other diagnostic in the file
    (decisions.md "Closed-domain completeness", failure currency).

    Found by `tests/metamorphic/test_reorder.py::…[positions_for_each]` when
    the sweep called `domains.binds_actor` before testing membership.

    red under: drop the `node.role in _ITERATION_ROLES` guard from
    `resolve._sweep_aliases`."""
    source = _game(body=body).replace(
        "state {", "positions { column : 1..7 }\n  state {"
    )
    with pytest.raises(DiagnosticError) as exc:
        check_dsl(source, "role.cardlang")
    assert exc.value.diagnostic.span is not None
    assert expected in exc.value.diagnostic.message.lower(), exc.value.diagnostic.message


def test_procedure_bodies_cannot_read_the_actor_pronoun() -> None:
    """The residual's boundary, pinned: the cross-call-site alias cannot be
    reached through the pronoun, because a procedure body may not name it at
    all. Without this, the ledger's residual row would be wider than the
    language actually allows.

    red under: drop the `_CALL_SITE_PRONOUNS` arm from
    `resolve._check_procedures`."""
    source = _game(body="for each player p: run bump(p)") + """
procedure bump(q : Player) {
  if q is not actor { hits[q] += 1 }
}
"""
    with pytest.raises(DiagnosticError) as exc:
        check_dsl(source, "proc.cardlang")
    assert "call-site pronoun 'actor'" in exc.value.diagnostic.message
