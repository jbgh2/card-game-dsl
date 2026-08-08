"""Pins `resolve._introduced_binders`, the single registry of "which AST node
kinds bind names, and which names" — the fix for a confirmed drift class: were
this match hand-written in three copies (`_categories`, `_template_binders`,
`_check_functions`), those copies would drift — as they did, two of them
missing the `Transfer`/`EpistemicOp`-with-filter arm the third had. This table
is the pin
that stops that class of drift: one row per binder-introducing node kind
(constructed directly, not parsed — a table test on the registry itself, not
on the language surface), plus a handful of ordinary node kinds asserted to
introduce nothing.

property:   every binder-introducing AST node kind is listed in
            `_introduced_binders` with the exact names it binds
domain:     every AST node kind that binds a name — which is NOT the same as
            "every dataclass in the `Expr`/`Stmt` unions". That narrower domain
            is what this file used to claim, and it is precisely how `ProduceArm`
            escaped: a `produces:` arm's payload binders (`Doubled(by, level)`)
            bind user-chosen names in the arm body, but `ProduceArm` is a member
            of neither union — it hangs off `Produces` — so a domain read from
            those two unions could never see it. The consequences were real and
            game-wide: `_check_reserved_binders` sweeps whatever this registry
            reports, so an arm binder named `actor` silently hijacked the pronoun
            (the arm body's bare `actor` classified as that local instead), and
            `_check_functions` / `_check_procedures` mistook a legitimately-bound
            arm name for an unbound reference. The lesson is the skill's own: a
            domain derived from the wrong registry measures the wall against
            itself.
registry:   `cardlang.ast.nodes.Node` — the closed union of ALL node kinds (it
            holds `ProduceArm`, which `Expr`/`Stmt` do not)
covered:    every binder-kind row below (Quantifier, Comprehension, CardQuery,
            PlayerQuery, ForEach, EachSimultaneous, Transfer [with/without
            filter], EpistemicOp [with/without filter], LetStmt [with/without
            index], ProduceArm [with/without payload binders]) plus a sample of
            non-binder kinds (NameRef, IfStmt, RepeatUntil, RotateStmt,
            StateDecl, AssignStmt); and the game-wide consequence — that an arm
            binder is now reserved-word swept like any other — is pinned by
            `test_a_produce_arm_binder_may_not_be_a_reserved_word`
sampled:    none — every node kind either introduces a binder (a row below) or
            falls to the registry's `case _: return ()` catch-all, itself
            exercised by the non-binder rows
residual:   none
"""

from __future__ import annotations

import pytest

from cardlang.ast import nodes as n
from cardlang.resolve import _introduced_binders

_CARD = n.NameRef(name="card")
_ZONE = n.NameRef(name="zone")
_FILLER_STMT = n.RotateStmt(target=n.NameRef(name="v"), values=())


def test_quantifier_binds_its_binder() -> None:
    node = n.Quantifier(kind="any", role="player", binder="p", body=n.NameRef(name="p"))
    assert _introduced_binders(node) == ("p",)


def test_comprehension_binds_its_binder() -> None:
    node = n.Comprehension(agg="sum", source=_ZONE, binder="c", body=_CARD)
    assert _introduced_binders(node) == ("c",)


def test_for_each_binds_its_binder() -> None:
    node = n.ForEach(role="player", binder="p", body=_FILLER_STMT)
    assert _introduced_binders(node) == ("p",)


def test_each_simultaneous_binds_its_role_name() -> None:
    node = n.EachSimultaneous(role="player", body=_FILLER_STMT)
    assert _introduced_binders(node) == ("player",)


def test_player_query_binds_player() -> None:
    node = n.PlayerQuery(kind="set", pred=n.NameRef(name="player"))
    assert _introduced_binders(node) == ("player",)


def test_card_query_binds_card() -> None:
    node = n.CardQuery(kind="set", source=_ZONE, pred=_CARD)
    assert _introduced_binders(node) == ("card",)


def test_card_query_binds_card_even_with_no_pred() -> None:
    # The bare `number of cards in <zone>` form: `pred` is None (nothing ever
    # references `card`), but the node still counts as introducing the
    # binder — matches the original flat classifier's unconditional add, and
    # is harmless (an unused binder scopes over nothing, since there is no
    # `pred` field for `_rewrite`'s scoping to widen).
    node = n.CardQuery(kind="count", source=_ZONE, pred=None)
    assert _introduced_binders(node) == ("card",)


def test_movement_with_filter_binds_card() -> None:
    node = n.Transfer(
        verb="deal",
        selection_mode=None,
        amount="all",
        item="cards",
        source=_ZONE,
        dest=n.NameRef(name="pile"),
        dest_each=False,
        filter=_CARD,
    )
    assert _introduced_binders(node) == ("card",)


def test_movement_without_filter_binds_nothing() -> None:
    # The negative case within the SAME node kind: a filter-less movement
    # introduces no binder — this is the exact drift hand-written copies
    # (`_categories`, `_template_binders`/`_check_functions`) would disagree
    # about.
    node = n.Transfer(
        verb="deal",
        selection_mode=None,
        amount="all",
        item="cards",
        source=_ZONE,
        dest=n.NameRef(name="pile"),
        dest_each=False,
        filter=None,
    )
    assert _introduced_binders(node) == ()


def test_epistemic_op_with_filter_binds_card() -> None:
    node = n.EpistemicOp(op="reveal", target=_ZONE, filter=_CARD)
    assert _introduced_binders(node) == ("card",)


def test_epistemic_op_without_filter_binds_nothing() -> None:
    node = n.EpistemicOp(op="shuffle", target=_ZONE, filter=None)
    assert _introduced_binders(node) == ()


def test_let_stmt_without_index_binds_name_only() -> None:
    node = n.LetStmt(name="x", index=None, value=n.NameRef(name="v"))
    assert _introduced_binders(node) == ("x",)


def test_let_stmt_with_index_binds_name_and_index() -> None:
    node = n.LetStmt(name="base", index="p", value=n.NameRef(name="v"))
    assert _introduced_binders(node) == ("base", "p")


# --- non-binder node kinds: the registry's `case _: return ()` catch-all ---


def test_name_ref_introduces_nothing() -> None:
    assert _introduced_binders(n.NameRef(name="x")) == ()


def test_if_stmt_introduces_nothing() -> None:
    node = n.IfStmt(cond=n.NameRef(name="c"), then_body=(), else_body=None)
    assert _introduced_binders(node) == ()


def test_repeat_until_introduces_nothing() -> None:
    node = n.RepeatUntil(cond=n.NameRef(name="c"), body=())
    assert _introduced_binders(node) == ()


def test_rotate_stmt_introduces_nothing() -> None:
    assert _introduced_binders(n.RotateStmt(target=n.NameRef(name="v"), values=())) == ()


def test_state_decl_introduces_nothing() -> None:
    # State variables are a flat, game-wide declaration namespace
    # (`_categories`'s `state_vars`), not a binder any construct introduces —
    # `_introduced_binders` deliberately has no `StateDecl` arm.
    node = n.StateDecl(
        name="x", index=None, type_name="Integer", optional=False, default=n.IntLit(value=0)
    )
    assert _introduced_binders(node) == ()


def test_assign_stmt_introduces_nothing() -> None:
    node = n.AssignStmt(
        target=n.NameRef(name="x"), index=None, op=":=", value=n.NameRef(name="v")
    )
    assert _introduced_binders(node) == ()


def test_produce_arm_binds_its_payload_binders() -> None:
    node = n.ProduceArm(tag="Doubled", binders=("by", "level"), body=(_FILLER_STMT,))
    assert _introduced_binders(node) == ("by", "level")


def test_produce_arm_without_payload_binders_binds_nothing() -> None:
    node = n.ProduceArm(tag="Passed", binders=(), body=(_FILLER_STMT,))
    assert _introduced_binders(node) == ()


def test_a_produce_arm_binder_may_not_be_a_reserved_word() -> None:
    """The game-wide consequence of the registry being complete. Before `ProduceArm`
    was listed, `_check_reserved_binders` never saw arm binders, so this parsed and
    the arm body's bare `actor` resolved to the BINDER rather than the pronoun — a
    silent hijack of the call-site actor. Every other binder kind (`let`, `for
    each`, …) was already swept; this one was the hole."""
    from cardlang.diagnostics import DiagnosticError
    from cardlang.pipeline import check_dsl

    src = """
game Q {
  players: 2
  direction: clockwise
  max_length: 10
  cards: standard52
  zones { deck : Deck  hand[player] : Hand<player> }
  state { score[player] : Integer = 0 }
  phase p {
    deal 2 cards from deck to each hand
    d produces: Won(actor) { score[actor] += 1 }
  }
  winner: highest score
}
define d -> { Won(Player) } { produce Won(0) }
"""
    with pytest.raises(DiagnosticError) as excinfo:
        check_dsl(src, "probe")
    assert "reserved word" in str(excinfo.value)
