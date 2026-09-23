"""`TAny` means the top, never a failed lookup.

`TAny` is the type checker's top type: `types.coercible` returns true whenever
either side is `TAny`, and ~20 sites in `typecheck.py` short-circuit their
check on it. A value typed `TAny` therefore satisfies EVERY constraint —
correct for a genuine top type, catastrophic for a value the checker merely
failed to look up, because the miss then silently exempts everything below it
from every type guard. Those two meanings used to share one type, and the
second was a standing source of this repo's worst defect class
(accepted-but-ignored): two PR-review findings in one cycle were the same
shape (a move parameter whose position domain was not threaded into the binder
env typed `TAny`, so `src is hearts` passed).

The split is at the PRODUCERS, not in the type: a lookup that cannot miss now
RAISES instead of returning the top, and the sites that remain permissive are an
audited set. Consulted design: decisions.md, "`Any` means the top, never a
failed lookup".

Completeness ledger
-------------------
property:   a name/registry lookup whose domain is closed never degrades to
            the permissive top — it raises, in compiler channel (an
            `AssertionError` naming the guard or builder that guarantees it),
            so an incomplete environment surfaces as a crash at the miss
            rather than as a silently-passing type check.
domain:     every top-construction site in `cardlang/`, counted by
            `_count_top_constructions` under any spelling of the type's name,
            partitioned into: lookup-miss producers (raise), declared-type-name
            positions (guarded at resolve), and audited top.
            Two things sit outside, and neither is a gap. A lookup taking a
            `domains.Role` rather than a bare name cannot miss BY TYPE, so it
            has no miss branch to probe and no behaviour to write a cell for;
            what remains for those is the every-Role-has-a-row pin beside
            them (`test_every_role_carries_a_row`). And a
            MERGE-failure top is a distinct population from the lookup misses
            this module closes: `join` returning None in `IfExpr`/`ListLit`
            falls to the top (`if c then 1 else hearts` goes permissive), and
            `max`/`min` comprehensions type as the top though `_check_agg_body`
            already forces an Integer body -- a precision loss rather than a
            miss. Both are issue #116, and closing them is a guard this module
            does not own.
registry:   the role sets (`domains.Role` vs the parser's quantifier
            spellings, `_ITERATION_ROLES`, `SIMULTANEOUS_ROLES`,
            `ZONE_INDEX_ROLES`, `_KNOWN_ROLES`); `CALL_SIGS` vs
            `BUILTIN_CALL_FUNCS`; `ZONE_CONTENT` vs `LIBRARY_ZONE_TYPES`;
            `NameRef.ref_kind` vs `_name_type`'s arms; `OP_CLASSES` vs
            `infer`'s BinOp arm (pinned in tests/test_operator_guards.py).
            Declaring position x name source:
            tests/test_type_name_positions.py::test_the_type_name_grid.
            The nominal rule, shape axis derived from the `Type` union:
            tests/test_nominal_type_identity.py, which carries its own ledger.
            The `Type` consumer shaped as a DENY-list, its domain from
            `get_args(Type)`:
            tests/test_typecheck_errors.py::test_every_type_union_member_is_classified_by_the_member_arm.
does not prove:  three things, and the third is why this module exists in
            the shape it does.
            The audited-top set is a COUNT per module, not an enumeration of
            sites. A new construction fails this module until it is
            classified, but the count cannot say WHICH site moved, and a
            change that adds one site while deleting another nets to zero and
            passes.
            Three raises -- the zone-content and `CALL_SIGS` misses, and the
            `run`-site procedure `_env_miss` -- carry registry-closure pins but
            no direct behaviour test, because each is reachable only by
            mutating the registry it guards. That they cannot fire for a well-formed program is
            argued from closure, not observed.
            And a green here is about the TYPE MACHINERY, not about a game:
            every probe below builds its own fixture. The end-to-end
            exercise of a declared position domain in both parameter
            positions is tests/test_position_parameters_witness.py
            (`test_the_witness_checks_and_plays`,
            `test_the_parameter_reaches_the_score_it_computes`); the
            collection-facet question is tests/test_types.py
            (`test_nested_facets_do_not_distinguish`,
            `test_a_flag_bearing_collection_does_nest`). Neither runs here.
"""

from __future__ import annotations

import ast
import inspect
from collections.abc import Callable
from pathlib import Path

import pytest

from cardlang import domains, typecheck
from cardlang.ast import nodes as n
from cardlang.builtins.functions import BUILTIN_CALL_FUNCS
from cardlang.builtins.signatures import CALL_SIGS, ZONE_CONTENT
from cardlang.diagnostics import DiagnosticBag, DiagnosticError
from cardlang.domains import BY_ID, SIMULTANEOUS_ROLES, ZONE_INDEX_ROLES
from cardlang.pipeline import check_dsl
from cardlang.stdlib.zones import LIBRARY_ZONE_TYPES
from cardlang.typecheck import TypeEnv, infer
from cardlang.types import (
    TAny,
    TBoolean,
    TCard,
    TCollection,
    TEnum,
    TInteger,
    coercible,
    join,
)

CARDLANG_ROOT = Path(typecheck.__file__).parent


def _game(decls: str = "", state: str = "score[player] : Integer = 0") -> str:
    return f"""
game G {{
  players: 2
  max_length: 1000
  cards: standard52
  ranking: A K Q J 10 9 8 7 6 5 4 3 2
  zones {{ deck : Deck  hand[player] : Hand<player> }}
  state {{ {state} }}
  phase play {{ for each player p: score[p] := 1 }}
  winner: highest score
}}
{decls}
"""


# =============================================================================
# Registry closure — why each raise is a guard over a closed domain
# =============================================================================


def test_every_role_set_is_a_subset_of_the_domain_registry() -> None:
    """`role_type` raises for a role outside `BY_ID`. That is only a GUARD (as
    opposed to a live crash) because every surface that produces a role draws
    from a set `BY_ID` covers: the parser's four hard-coded quantifier
    spellings, and the four role sets resolve validates against."""
    from cardlang import resolve as resolve_mod

    # `getattr` rather than a direct import: mypy strict's
    # `--no-implicit-reexport` refuses the private names (same workaround as
    # tests/test_role_registry.py).
    parser_quantifier_roles = frozenset(
        {domains.Role.PLAYER, domains.Role.TEAM, domains.Role.SUIT, domains.Role.RANK}
    )
    for label, roles in (
        ("parser quantifier spellings", parser_quantifier_roles),
        ("_ITERATION_ROLES", getattr(resolve_mod, "_ITERATION_ROLES")),
        ("SIMULTANEOUS_ROLES", SIMULTANEOUS_ROLES),
        ("ZONE_INDEX_ROLES", ZONE_INDEX_ROLES),
        ("_KNOWN_ROLES", getattr(resolve_mod, "_KNOWN_ROLES")),
    ):
        assert set(roles) <= set(BY_ID), f"{label} escapes the domain registry"


def test_every_name_taking_registry_lookup_raises_on_an_unknown_role() -> None:
    """The registry lookups that still take a NAME answer a divergence the same
    way: in compiler channel, never by defaulting.

    Only three still can. `role_type`, `binds_actor` and `role_members` take a
    `domains.Role`, so an unknown role is unwritable at every call site and
    their miss branches are gone — that closure moved from these raises to the
    type, with `test_every_role_carries_a_row` below as the one residue. The
    three here take a name because their domain genuinely is open (the registry
    plus the calling game's declared position domains), so classifying the name
    is part of their answer and the raise is the guard over what is left.

    `binds_actor` is why the contract is "raise", not "return a default": it
    alone used to answer `False`, which is not an absence but a CLAIM — "this
    is a value domain", i.e. run the loop without rebinding the actor. A seat
    domain missing from the registry would have iterated with the wrong actor
    rather than failing.

    red under: return `None` instead of raising from `domains.require_role`.
    """
    sources = domains.DomainSources(positions={}, suits=(), ranks=(), players=(), teams=())

    class _Rs:
        # `zone_observer_key` consults `position_domains` before the registry;
        # an unknown role is not one, so the lookup below is what answers.
        position_domains: dict[str, object] = {}  # noqa: RUF012 -- one inline instance of a throwaway RuntimeState stub, never mutated

    lookups: dict[str, Callable[[], object]] = {
        "require_role": lambda: domains.require_role("nonrole", "binder role"),
        "role_static_members": lambda: domains.role_static_members("nonrole", sources),
        "zone_observer_key": lambda: domains.zone_observer_key(
            "nonrole", _Rs(), 0  # type: ignore[arg-type]
        ),
    }
    for label, call in lookups.items():
        with pytest.raises(AssertionError, match="nonrole"):
            call()
        assert "nonrole" not in str(BY_ID), f"{label}: probe name leaked into the registry"


def test_every_role_carries_a_row() -> None:
    """The residue of the three closures the `Role` parameter absorbed.

    `role_type`/`binds_actor`/`role_members` index `BY_ID` with no miss branch.
    That is total exactly while every `Role` member has a row — a four-element
    obligation replacing three raises no caller can now reach.

    red under: add a member to `domains.Role` without a `Domain(...)` row (the
    module-level assert in `cardlang/domains.py` fires at import, so the whole
    suite reddens, not just this test — which is the point)."""
    assert set(BY_ID) == set(domains.Role)


def test_quantifier_role_spellings_are_still_hard_coded_in_the_parser() -> None:
    """The pin above hard-codes the parser's quantifier roles, so it must fail
    if the parser gains a role it does not list — otherwise the subset check
    above goes vacuously green against a stale copy."""
    from cardlang import parse

    src = inspect.getsource(parse)
    built = {
        node.args[1].value
        for node in ast.walk(ast.parse(src))
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "_implicit_quantifier"
        and len(node.args) >= 2
        and isinstance(node.args[1], ast.Constant)
    }
    assert built == {"player", "team", "suit", "rank"}, (
        "the parser builds quantifier roles this module does not pin — add "
        "them to `parser_quantifier_roles` above and confirm BY_ID covers them"
    )


def test_call_signature_registry_covers_every_native_call_function() -> None:
    """`infer`'s Call arm raises when a call has no signature; resolve rejects
    a call to an unknown name, so the two native registries must agree.

    `CALL_SIGS` states the BUILTIN half of that agreement. A Primitive's
    signature is a column on the implementation index
    (`primitives_block.PRIMITIVE_IMPLEMENTATIONS`), reached through
    `implementation_sig`, and the Primitive half of the agreement is carried
    by two facts this cell does not restate, each covering its own half: the
    index's own import-time assert that it is keyed exactly
    `PRIMITIVE_CALL_FUNCS` — no registered name lacks a ROW — and `sig` being
    a required field of a frozen `Implementation` — no row lacks a SIGNATURE,
    at rung 1, since such a row does not construct."""
    assert set(CALL_SIGS) == set(BUILTIN_CALL_FUNCS)


def test_zone_content_registry_covers_every_library_zone_type() -> None:
    """`env_from_game` raises for a declared zone with no content type;
    resolve rejects an unknown zone type, so the two must agree."""
    assert set(LIBRARY_ZONE_TYPES) == set(ZONE_CONTENT)


def test_name_type_handles_every_ref_kind_the_resolver_stamps() -> None:
    """`_name_type`'s default arm raises. Every `ref_kind` `_classify` can
    return must therefore have an arm — a new kind must be typed, not left to
    fall through to the permissive top."""
    from cardlang import resolve as resolve_mod

    src = inspect.getsource(resolve_mod._classify)
    stamped = {
        node.value.value
        for node in ast.walk(ast.parse(src))
        if isinstance(node, ast.Return)
        and isinstance(node.value, ast.Constant)
        and isinstance(node.value.value, str)
    }
    handled = set(
        re_findall_case_literals(inspect.getsource(typecheck._name_type))
    )
    assert stamped <= handled, (
        f"`_classify` stamps ref kinds `_name_type` does not type: "
        f"{sorted(stamped - handled)}"
    )


def re_findall_case_literals(src: str) -> list[str]:
    """The string literals of a `match`'s `case "..."` arms."""
    return [
        node.pattern.value.value
        for node in ast.walk(ast.parse(src))
        if isinstance(node, ast.match_case)
        and isinstance(node.pattern, ast.MatchValue)
        and isinstance(node.pattern.value, ast.Constant)
        and isinstance(node.pattern.value.value, str)
    ]


# =============================================================================
# The raises themselves — each producer, exercised directly
# =============================================================================


def test_unknown_role_raises_rather_than_typing_as_top() -> None:
    # `typecheck._role_type` is the producer this guards: it is where a parsed
    # role name is classified before the registry sees it, and it used to
    # return the permissive top for a name no row defines.
    with pytest.raises(AssertionError) as ei:
        getattr(typecheck, "_role_type")("nonesuch")
    assert "binder role" in str(ei.value)


def test_unbound_binder_raises_rather_than_typing_as_top() -> None:
    """The headline case: a binder the statement walk failed to thread. This
    used to type as the top, so every guard below the binder passed silently."""
    with pytest.raises(AssertionError) as ei:
        infer(n.NameRef("p", ref_kind="local"), TypeEnv())
    assert "absent from `TypeEnv.locals`" in str(ei.value)
    assert "never bind `TAny` here" in str(ei.value)


def test_unbound_state_var_zone_and_enum_value_raise() -> None:
    """Sweep the class: every env-backed lookup in `_name_type`, not just the
    binder one that motivated the change."""
    for kind, field in (
        ("state_var", "state_vars"),
        ("zone", "zones"),
        ("enum_value", "value_enums"),
    ):
        with pytest.raises(AssertionError) as ei:
            infer(n.NameRef("nonesuch", ref_kind=kind), TypeEnv())
        assert f"absent from `TypeEnv.{field}`" in str(ei.value)


def test_unknown_ref_kind_raises() -> None:
    with pytest.raises(AssertionError) as ei:
        infer(n.NameRef("x", ref_kind="brand_new_kind"), TypeEnv())
    assert "does not type" in str(ei.value)


def test_unresolved_name_raises() -> None:
    """`ref_kind=None` never reaches this pass (resolve raises first), and if
    it ever does it must be loud rather than permissive."""
    with pytest.raises(AssertionError):
        infer(n.NameRef("x"), TypeEnv())


def test_untyped_operator_raises() -> None:
    with pytest.raises(AssertionError) as ei:
        infer(n.BinOp("**", n.IntLit(1), n.IntLit(2)), TypeEnv())
    assert "no result type" in str(ei.value)


def test_unbound_zone_family_subscript_raises() -> None:
    """`infer`'s zone-family subscript arm has its own zone lookup, and it
    missed the same way — sweep the class, not the instance."""
    env = TypeEnv(zone_families={"hand": TInteger()})  # family known, content absent
    with pytest.raises(AssertionError) as ei:
        infer(
            n.Subscript(n.NameRef("hand", ref_kind="zone"), n.IntLit(0)),
            env,
        )
    assert "absent from `TypeEnv.zones`" in str(ei.value)


# =============================================================================
# The declared-type-name guards (resolve) — the reachable holes, now closed
# =============================================================================


def test_function_parameter_type_name_is_validated() -> None:
    """The inversion this closes: with a VALID type the body is rejected, so
    with a TYPO it must not be accepted."""
    with pytest.raises(DiagnosticError) as valid:
        check_dsl(_game("function f(x : Integer) = x is hearts"), "g.cardlang")
    assert "can never be equal" in str(valid.value)

    with pytest.raises(DiagnosticError) as typo:
        check_dsl(_game("function f(x : Integar) = x is hearts"), "g.cardlang")
    assert "unknown type 'Integar'" in str(typo.value)


def test_move_parameter_domain_is_gated_even_when_never_offered() -> None:
    """`_check_move_params` used to run only for moves reachable from an
    `offer`/round vocabulary, so a move type no vocabulary named had its
    parameter domains unchecked entirely. It now gates every DECLARED move
    type."""
    with pytest.raises(DiagnosticError) as ei:
        check_dsl(
            _game("move_type mv(x : Integar) { effect { score[actor] := 1 } }"),
            "g.cardlang",
        )
    assert "unsupported parameter domain 'Integar'" in str(ei.value)


def test_variant_payload_type_name_is_validated() -> None:
    src = _game().replace(
        "phase play { for each player p: score[p] := 1 }",
        "phase play {\n"
        "    phase d -> outcome { won(Integar) | lost } { produce won(1) }\n"
        "    d produces: won(k) { score[0] := 1 } lost { score[1] := 1 }\n"
        "  }",
    )
    with pytest.raises(DiagnosticError) as ei:
        check_dsl(src, "g.cardlang")
    assert "unknown type 'Integar'" in str(ei.value)


def test_position_domain_stays_legal_as_a_move_parameter() -> None:
    """The move-param guard must not reject the position domains `_param_type`
    genuinely types (as Integer) — the guard mirrors the builder exactly."""
    src = """
game G {
  players: 1
  max_length: 1000
  cards: standard52
  positions { column : 1..4 }
  zones { deck : Deck  pile[column] : Cascade<column> }
  state { score[player] : Integer = 0 }
  phase play { for each player p: score[p] := 1 }
  winner: highest score
}
move_type build(src : column) { effect { score[actor] := 1 } }
"""
    check_dsl(src, "g.cardlang")  # must not raise


@pytest.mark.parametrize(
    "body,expected",
    [("score", TInteger()), ("hearts", TEnum("Suit")), ("score > 0", TBoolean())],
)
def test_env_from_game_types_function_bodies_with_ambient_names(
    body: str, expected: object
) -> None:
    """`env_from_game(game)` — the public helper, called on its own — types a
    user function's body with the game's ambient names in scope, exactly as
    the main pipeline does. A body typed against an empty `TypeEnv` would
    raise on the first state variable or enum value it names, aborting the
    helper for a valid game: a public helper is a caller too, and its
    behaviour must not depend on which entry point reached it."""
    src = f"""
function f() = {body}
game G {{
  players: 2
  max_length: 1000
  cards: standard52
  ranking: A K Q J 10 9 8 7 6 5 4 3 2
  zones {{ deck : Deck  hand[player] : Hand<player> }}
  state {{ score : Integer = 0  result[player] : Integer = 0 }}
  phase play {{ score := 1 }}
  winner: highest result
}}
"""
    from cardlang.parse import parse_text
    from cardlang.resolve import resolve
    from cardlang.typecheck import env_from_game

    env = env_from_game(resolve(parse_text(src, "g.cardlang")))
    assert env.functions["f"].ret == expected


def test_env_from_game_keeps_the_signatures_it_solved() -> None:
    """`env_from_game` returns the function signatures it solves.

    An env with an empty `TypeEnv.functions` makes `infer` on a call to any
    user function raise the no-signature `AssertionError`. Asserting the
    inferred TYPE rather than merely that nothing raised: an empty map is
    exactly the failure, and a laxer assertion would not notice it."""
    from cardlang.parse import parse_text
    from cardlang.resolve import resolve
    from cardlang.typecheck import env_from_game

    src = _game(decls="function dbl(x : Integer) = x + x")
    env = env_from_game(resolve(parse_text(src, "g.cardlang")))
    assert set(env.functions) == {"dbl"}
    assert infer(n.Call("dbl", (n.IntLit(2),)), env) == TInteger()


def test_env_from_game_fills_in_the_procedure_signatures() -> None:
    """Swept from the same class as the two findings above, before a fourth
    instance was reported: `env_from_game` also owed `procedures`.

    This one failed SILENTLY rather than loudly, which makes it the worse
    shape. The `run`-site check guarded with `if sig is not None`, so an env
    without procedure signatures skipped the arity and argument-type guard
    instead of failing — and that site is the ONLY place a procedure's
    parameter annotations bite at all (after expansion the call site is gone).
    The guard is now a raise, on the same reasoning as every other lookup here:
    resolve has established the procedure exists, so a miss is a registry
    divergence, and guarding leniently on an invariant you have just asserted
    is how a check goes dark."""
    from cardlang.parse import parse_text
    from cardlang.resolve import resolve
    from cardlang.typecheck import _check_stmt_exprs, env_from_game

    src = """
game G {
  players: 2
  max_length: 1000
  cards: standard52
  ranking: A K Q J 10 9 8 7 6 5 4 3 2
  zones { deck : Deck  hand[player] : Hand<player> }
  state { score[player] : Integer = 0 }
  phase play { score[0] := 1  run bump(0) }
  winner: highest score
}
procedure bump(p : Player) { score[p] := 1 }
"""
    env = env_from_game(resolve(parse_text(src, "g.cardlang")))
    assert set(env.procedures) == {"bump"}

    bag = DiagnosticBag()
    _check_stmt_exprs(
        n.RunStmt("bump", (n.IntLit(0), n.IntLit(1), n.IntLit(2))), env, bag
    )
    assert any("expects 1 argument(s), got 3" in d.message for d in bag.items)


# =============================================================================
# The audited top set — enumerated, so a new permissive site must be classified
# =============================================================================

# Every module that may construct `TAny()`, with the number of construction
# sites in it. A change to any count is a change to the permissive surface and
# must be justified in this module's ledger. The classification of each
# surviving site, so a count change can be checked against an argument rather
# than just re-blessed:
#
# typecheck.py (15)
#   legitimate top (no better type exists) — 4:
#     pronoun member access (deferred shape); a non-`actor` pronoun; a bare
#     function NAME in value position; a procedure `Sig.ret` (a procedure is a
#     statement — the field is never read).
#   gradual propagation, downstream of a guard that already fired — 6:
#     `type_from_name`'s unknown name (every declared-type-name position is
#     refused at resolve for a name no registry holds, so a resolved game
#     reaches this branch with none); a subscript of a non-collection
#     (`subscriptable`), a comprehension element off a bad source
#     (`_check_card_source`), an unknown item/Card field (rejected in
#     `_check_expr`), and the two `DomainQuery` binder-type lookups (a bare
#     position-domain binder, a `line`/`cell` collection binder), each reached
#     only after resolve's `_check_domain_query` validated the noun. Each is
#     reached only with an error already in the bag, or with a top receiver.
#   recorded residual, merge failure — 3: `ListLit` and the two `IfExpr` arms,
#     where `join` returns None (issue #116).
#   recorded residual, precision — 2: the order aggregators of BOTH
#     aggregation registers — `max`/`min` over a zone's cards, and the same
#     two over its subsets. Each takes its result type from the body, which
#     `infer` does not compute, and `_check_agg_body` is the guard that makes
#     the looseness safe rather than the type (issue #116).
# types.py (2)
#   `join`'s top absorption, and the sticky-key merge — both ARE the top
#   semantics, not lookups.
# builtins/signatures.py (13)
#   the audited dynamic-signature set: `suit_of`'s polymorphic argument, the
#   ZONE argument of all three Arrival-Record calls — `highest_trump_or_led_suit`
#   (issue #256), and `highest_by_trick_order` / `follows_lead` (issue #250) —
#   which carry the same polymorphic shape for the same reason: the runtime
#   needs the Zone handle so the Arrival Record rides along, and each is probed
#   in tests/test_native_call_boundary.py beside suit_of's. Their WHICH-argument
#   is `ARRIVAL_RECORD_CALLS`, and resolve now decides each statically, so the
#   top here is a value-shape looseness the checker no longer has to carry
#   alone. Plus `error()`'s return (it diverges, so it must type in any
#   context), the trick-winner and auction-outcome callbacks whose real type
#   the `Sig` model cannot express — `highest_by_trick_order`'s VALUE_SIGS row
#   among them — and the `ChipStack` resource zone's element.
AUDITED_TOP_SITES: dict[str, int] = {
    "typecheck.py": 15,
    "types.py": 2,
    "builtins/signatures.py": 13,
}


def _top_aliases(tree: ast.Module) -> set[str]:
    """Every local name in this module that denotes the top type.

    A count keyed on the literal spelling `TAny` is defeated by one import
    line (`from cardlang.types import TAny as _Top`), so the alias set is
    derived from the module's own imports and assignments rather than assumed.
    """
    aliases = {"TAny"}
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            aliases |= {a.asname or a.name for a in node.names if a.name == "TAny"}
        elif isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and (
                    (isinstance(node.value, ast.Name) and node.value.id in aliases)
                    or (
                        isinstance(node.value, ast.Attribute)
                        and node.value.attr == "TAny"
                    )
                ):
                    aliases.add(target.id)
    return aliases


def _count_top_constructions(path: Path) -> int:
    """Sites in one module that construct — or defer constructing — the top.

    Counts every CALL form: `TAny()`, an aliased `_Top()`, and the qualified
    `types.TAny()`. What it cannot see: a top obtained without calling the
    type — `field(default_factory=TAny)`, or returning an existing top-valued
    object. Those are covered by the behavioural raise tests above, not here.
    """
    tree = ast.parse(path.read_text())
    aliases = _top_aliases(tree)

    def denotes_top(node: ast.expr) -> bool:
        return (isinstance(node, ast.Name) and node.id in aliases) or (
            isinstance(node, ast.Attribute) and node.attr == "TAny"
        )

    return sum(
        1 for node in ast.walk(tree)
        if isinstance(node, ast.Call) and denotes_top(node.func)
    )


def test_the_permissive_top_surface_is_pinned() -> None:
    """The top may only be constructed at audited sites.

    A tripwire over the whole package, not a proof: it catches a new
    construction site under any spelling of the type's name — including an
    aliased import, which defeated an earlier version of this counter — but it
    cannot see a fallback that never names the type. The guarantee that a
    lookup MISS raises rather than falling back is behavioural and lives in the
    raise tests above; this pin's job is to force a new construction site to be
    classified in the ledger rather than added quietly.

    red under: add `TAny()` anywhere in `cardlang/` (or an aliased `_Top()`,
    which an earlier spelling-keyed version of this counter missed).
    """
    found = {
        str(p.relative_to(CARDLANG_ROOT)): _count_top_constructions(p)
        for p in sorted(CARDLANG_ROOT.rglob("*.py"))
        if _count_top_constructions(p)
    }
    assert found == AUDITED_TOP_SITES, (
        "the permissive-top surface changed. A NEW `TAny()` site must be "
        "classified in this module's ledger as a legitimate top (no better type "
        "exists) or replaced by a raise (a lookup that cannot miss); a REMOVED "
        "one should decrement the count here. Found: " + repr(found)
    )


def test_the_audited_top_still_flows_where_it_is_legitimate() -> None:
    """The top is still permissive where it is deliberate — the split removed the
    lookup-miss population, it did not make `TAny` strict."""
    env = TypeEnv().with_local("loose", TAny())
    # a deliberately-loose binder compares against anything, without error
    check_dsl(
        _game(state="score[player] : Integer = 0  flag : Boolean = false"),
        "g.cardlang",
    )
    assert infer(n.NameRef("loose", ref_kind="local"), env) == TAny()
    # and a chip-stack-shaped collection still unifies with a card collection
    from cardlang.types import join

    assert join(TCollection(TAny()), TCollection(TCard())) is not None


def test_every_type_consumer_fails_closed_on_an_unfamiliar_type() -> None:
    """The generalization of the Member-arm classification pin
    (tests/test_typecheck_errors.py): that one proves every `Type` union member
    earns a dot-form arm; this one proves the REST of the `Type` consumers need
    no such enumeration, because they are allow-lists that reject a type they
    have never seen rather than deny-lists that fall through to acceptance.

    The distinction is the whole reason the Member arm was the one that leaked:
    it enumerated what to REJECT, so an unenumerated type reached no arm and
    inferred the permissive top with no diagnostic. `subscriptable`,
    `coercible` and `join` instead enumerate what to ACCEPT, so an unfamiliar
    type is refused by construction -- no arm to forget. Equality still carries
    the same-type cases, so failing closed costs them no legitimate answer.

    Pinned because that safety is structural, not declared: nothing stops a
    later change from "fixing" a spurious rejection by giving one of these a
    permissive default, which would reopen the leak everywhere at once and
    without a diagnostic. An unfamiliar type -- deliberately outside the union,
    which is what a not-yet-classified new type behaves like -- is the probe.

    red under: three, each run and observed, then reverted --
      * `subscriptable` given a permissive default
        (`return not isinstance(t, (TInteger, TBoolean))`);
      * `coercible`'s FINAL `return False` flipped to `return True`;
      * `join`'s FINAL `return None` flipped to `return a`.
    "Final" is load-bearing in the last two: `join` has an earlier `return
    None` inside its optional branch, and mutating THAT leaves this pin green --
    a plant that never armed. A replay must hit the fall-through (the last
    `return` in the function), or it proves nothing.
    """
    from dataclasses import dataclass
    from typing import cast

    from cardlang.types import Type, subscriptable

    @dataclass(frozen=True, slots=True)
    class TUnfamiliar:
        """Stands in for a type a later change adds to the union but has not
        yet threaded through the consumers."""

    # `cast` is the point of the probe, not a workaround: the checker's own
    # types say this cannot happen, and the pin exists for the moment it does.
    unknown = cast(Type, TUnfamiliar())

    # Refused by construction, with no arm naming it.
    assert subscriptable(unknown) is False
    assert coercible(unknown, TInteger()) is False
    assert coercible(TInteger(), unknown) is False
    assert join(unknown, TInteger()) is None
    assert join(TInteger(), unknown) is None

    # ...while the same-type cases equality already covers still answer, so
    # failing closed is conservative rather than wrong.
    assert coercible(unknown, unknown) is True
    assert join(unknown, unknown) == unknown

    # And rendering degrades gracefully: a diagnostic naming an unfamiliar type
    # still reads, rather than crashing the checker mid-report.
    assert typecheck._type_name(unknown) == "Unfamiliar"
