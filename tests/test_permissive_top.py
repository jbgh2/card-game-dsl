"""The permissive top (`TAny`) and the lookup-miss walls.

`TAny` is the type checker's top type: `types.assignable` returns true whenever
either side is `TAny`, and ~20 sites in `typecheck.py` short-circuit their
check on it. A value typed `TAny` therefore satisfies EVERY constraint —
correct for a genuine top type, catastrophic for a value the checker merely
failed to look up, because the miss then silently exempts everything below it
from every type wall. Those two meanings used to share one type, and the
second was a standing source of this repo's worst defect class
(accepted-but-ignored): two PR-review findings in one cycle were the same
shape (a move parameter whose position domain was not threaded into the binder
env typed `TAny`, so `src is hearts` passed).

The split is at the PRODUCERS, not in the type: a lookup that cannot miss now
RAISES instead of returning the top, and the sites that remain permissive are an
audited set. Consulted design: decisions.md, "The permissive top and the
lookup-miss walls".

Completeness ledger
-------------------
property:   a name/registry lookup whose domain is closed never degrades to
            the permissive top — it raises, in compiler currency (an
            `AssertionError` naming the wall or builder that guarantees it),
            so an incomplete environment surfaces as a crash at the miss
            rather than as a silently-passing type check.
domain:     every `TAny()` construction site in `cardlang/` (37 at the time of
            writing), partitioned into: lookup-miss producers (raise),
            declared-type-name positions (walled at resolve), and audited top.
registry:   the five role sets (`domains.BY_ID` vs the parser's quantifier
            spellings, `_ITERATION_ROLES`, `SIMULTANEOUS_ROLES`,
            `ZONE_INDEX_ROLES`, `_KNOWN_ROLES`); `CALL_SIGS` vs
            `STDLIB_CALL_FUNCS`; `ZONE_CONTENT` vs `LIBRARY_ZONE_TYPES`;
            `NameRef.ref_kind` vs `_name_type`'s arms; `OP_CLASSES` vs
            `infer`'s BinOp arm (pinned in tests/test_operator_walls.py).
covered:    the registry-closure pins below (each proves the corresponding
            raise is unreachable for a well-formed program, so the raise is a
            wall over a closed domain rather than a live failure mode); the
            raise-behaviour tests (each producer, exercised directly); the
            three declared-type-name walls, as rendered-diagnostic goldens in
            tests/rejections/unknown_type_{function_param,move_param,
            variant_payload}.cardlang.
sampled:    the audited-top set is asserted by ENUMERATION here (the site list
            is pinned, so a new `TAny()` producer fails this module until it
            is classified), not by exercising each site's semantics — those
            are covered by their own wall modules.
residual:   (1) MERGE-failure top: `unify` returning None in `IfExpr`/`ListLit`
            falls to `TAny` (`if c then 1 else hearts` types as the top and goes
            permissive). A distinct population from the lookup misses this
            module closes — wall recorded in roadmap.md, "Explicitly
            deferred".
            (2) `max`/`min` comprehensions type as the top though `_check_agg_body`
            already forces an Integer body — a precision loss, not a miss;
            recorded in roadmap.md alongside (1).
            (3) `type_from_name`'s unknown-name fallback stays the top because
            `struct_registry` builds structs in source order, so a FORWARD
            struct reference reaches it with a VALID name (documented Stage-2
            behaviour, exercised by `test_forward_struct_reference_is_top`).
            The three positions that reached it with an INVALID name are now
            walled at resolve.
            (4) none for the struct/function registries. They are mutually
            dependent in both directions and at arbitrary depth, so
            `struct_and_function_registries` iterates them to a FIXPOINT
            (bounded, with a loud refusal if a round is non-monotone) rather
            than running a fixed number of passes. Two earlier fixed-pass
            versions each shipped a defect an adversarial probe caught and the
            green suite did not: unequal `TStruct`s for one nominal type
            (`expects R, got R`, now closed by nominal struct comparison in
            `types.assignable`/`unify`), and a derived field frozen at the top
            when its type flowed through a function return (a LOST WALL --
            `score[p] := s.flag` accepted a Boolean into an Integer state
            variable). Both are pinned below. Corpus exposure is zero: no game
            declares a struct, which is exactly why the suite was silent.
            A third, found in review: derived bodies were typed in a BARE
            environment, so every name resolve legitimately scopes into one (a
            state variable, a zone, an enum value, a struct literal of its own
            or a later type) hit `_env_miss` and aborted the check. Swept as a
            class, not patched at the reported instance, and pinned by the two
            parametrized derived-body tests below. A fourth, also from review:
            the convergence key reduced a NESTED struct to its bare name while
            `infer`'s Member arm reads nested fields, and the loop tested
            before assigning, so a stale nested struct survived and its field
            reads typed as the top. The loop now always keeps the newer
            registry, and -- after review showed a bounded-depth key was BOTH
            unsound (a recursive path stays observable past any cutoff, so
            `r.copy.copy.copy.flag` decayed to the top) and exponential on a
            declaration DAG -- struct-typed field reads resolve through the
            REGISTRY by name (`_canonical`) instead of off the embedded
            snapshot. Nested snapshots are then never observed, so the
            fingerprint is nominal and linear again. Every defect in this
            group was found by review or adversarial probe, never by the
            suite.
"""

from __future__ import annotations

import ast
import inspect
from pathlib import Path

import pytest

from cardlang import domains, typecheck
from cardlang.ast import nodes as n
from cardlang.diagnostics import DiagnosticBag, DiagnosticError
from cardlang.domains import BY_ID, SIMULTANEOUS_ROLES, ZONE_INDEX_ROLES, role_type
from cardlang.pipeline import check_dsl
from cardlang.stdlib.functions import STDLIB_CALL_FUNCS
from cardlang.stdlib.signatures import CALL_SIGS, ZONE_CONTENT
from cardlang.stdlib.zones import LIBRARY_ZONE_TYPES
from cardlang.types import TAny, TBoolean, TCard, TCollection, TEnum, TInteger
from cardlang.typecheck import TypeEnv, infer

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
# Registry closure — why each raise is a wall over a closed domain
# =============================================================================


def test_every_role_set_is_a_subset_of_the_domain_registry() -> None:
    """`role_type` raises for a role outside `BY_ID`. That is only a WALL (as
    opposed to a live crash) because every surface that produces a role draws
    from a set `BY_ID` covers: the parser's four hard-coded quantifier
    spellings, and the four role sets resolve validates against."""
    from cardlang import resolve as resolve_mod

    # `getattr` rather than a direct import: mypy strict's
    # `--no-implicit-reexport` refuses the private names (same workaround as
    # tests/test_role_registry.py).
    parser_quantifier_roles = frozenset({"player", "team", "suit", "rank"})
    for label, roles in (
        ("parser quantifier spellings", parser_quantifier_roles),
        ("_ITERATION_ROLES", getattr(resolve_mod, "_ITERATION_ROLES")),
        ("SIMULTANEOUS_ROLES", SIMULTANEOUS_ROLES),
        ("ZONE_INDEX_ROLES", ZONE_INDEX_ROLES),
        ("_KNOWN_ROLES", getattr(resolve_mod, "_KNOWN_ROLES")),
    ):
        assert set(roles) <= set(BY_ID), f"{label} escapes the domain registry"


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


def test_call_signature_registry_covers_every_stdlib_call_function() -> None:
    """`infer`'s Call arm raises when a call has no signature; resolve rejects
    a call to an unknown name, so the two stdlib registries must agree."""
    assert set(STDLIB_CALL_FUNCS) == set(CALL_SIGS)


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
    with pytest.raises(AssertionError) as ei:
        role_type("nonesuch")
    assert "binder role" in str(ei.value)


def test_unbound_binder_raises_rather_than_typing_as_top() -> None:
    """The headline case: a binder the statement walk failed to thread. This
    used to type as the top, so every wall below the binder passed silently."""
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


def test_unknown_struct_literal_type_raises() -> None:
    with pytest.raises(AssertionError) as ei:
        infer(n.StructLit("Nonesuch", ()), TypeEnv())
    assert "absent from `TypeEnv.structs`" in str(ei.value)


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
# The declared-type-name walls (resolve) — the reachable holes, now closed
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
    src = (
        "define d -> { won(Integar) | lost } { produce won(1) }\n"
        + _game()
    )
    with pytest.raises(DiagnosticError) as ei:
        check_dsl(src, "g.cardlang")
    assert "unknown type 'Integar'" in str(ei.value)


def test_user_type_as_move_parameter_is_rejected() -> None:
    """A DECLARED struct is a known type, but not an enumerable move-parameter
    domain — and `_param_type` builds move params without the struct registry,
    so admitting one would type it as the top. The domain gate covers it like any other
    non-enumerable spelling, so there is no second wall to keep in step."""
    with pytest.raises(DiagnosticError) as ei:
        check_dsl(
            _game(
                "type T = { a : Integer }\n"
                "move_type mv(x : T) { effect { score[actor] := 1 } }"
            ),
            "g.cardlang",
        )
    assert "unsupported parameter domain 'T'" in str(ei.value)


def test_position_domain_stays_legal_as_a_move_parameter() -> None:
    """The move-param wall must not reject the position domains `_param_type`
    genuinely types (as Integer) — the wall mirrors the builder exactly."""
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


def test_a_derived_body_calling_a_user_function_is_typed() -> None:
    """The struct/function cycle, closed. A derived field whose body calls a
    user function used to reach `infer`'s Call arm with an EMPTY function map
    (`struct_registry` ran before `_function_sigs`), so the whole derived field
    typed as the top. Both directions of the cycle must now work."""
    check_dsl(
        "type R = { a : Integer } derived { made = tag(a) }\n"
        + _game(
            decls="function tag(p : Integer) = p > 0",
            state="score[player] : Integer = 0  r : R = none",
        ),
        "g.cardlang",
    )


def test_a_function_returning_a_derived_field_keeps_its_real_type() -> None:
    """The struct/function build must not cost precision in function bodies:
    `reads()` returns the derived field's Boolean, so comparing it to a Suit is
    still rejected. Pinned because an intermediate design gave this up — it
    typed every derived field loosely while the signatures were computed, and
    silently ACCEPTED this always-false comparison: a new member of the very
    class this module exists to close. The fixpoint removed the trade, but the
    pin stays, since any future reordering of the two registries can lose it
    again."""
    src = "type R = { a : Integer } derived { made = a > 0 }\n" + _game(
        decls="function reads(x : R) = x.made",
        state="score[player] : Integer = 0  r : R = none",
    ).replace(
        "phase play { for each player p: score[p] := 1 }",
        "phase play { let bad = reads(r) is hearts }",
    )
    with pytest.raises(DiagnosticError) as ei:
        check_dsl(src, "g.cardlang")
    assert "comparing Suit with Boolean can never be equal" in str(ei.value)


def test_a_struct_type_is_nominal_not_structural() -> None:
    """A declared `type` is NOMINAL: two `R`s are the same type because both
    are named R. `TStruct` carries its fields, so dataclass equality is
    structural — and while the registries were built in a fixed number of
    passes, two of them could disagree about one derived field and yield two
    unequal `R`s. That produced diagnostics reading `expects R, got R` at eight
    separate sites and made well-typed programs unwritable. `types.assignable`
    and `types.unify` compare structs by NAME, so the class is closed at the
    layer every comparison consults rather than site by site."""
    src = (
        "type R = { a : Integer } derived { made = a > 0 }\n"
        "type S = { r : R } derived { same = pick(r) }\n"
        + _game(
            decls="function pick(x : R) = x",
            state=(
                "s : S = S { r: R { a: 3 } }  r2 : R = R { a: 4 }  "
                "score[player] : Integer = 0"
            ),
        ).replace(
            "phase play { for each player p: score[p] := 1 }",
            "phase play { r2 := s.same  if s.same is r2 { score[0] := 1 } }",
        )
    )
    check_dsl(src, "g.cardlang")  # `s.same` genuinely IS an R


def test_a_derived_field_reached_through_a_function_keeps_its_real_type() -> None:
    """The struct/function fixpoint, at the depth that actually bites.

    A function's RETURN type can depend on a derived field, which can depend on
    another function's return type. A FIXED pass count froze the outermost
    derived field at the permissive top, silently exempting every expression
    that read it from every wall — this module's own defect class, reintroduced
    by the fix for a different bug in the same area, and caught only by an
    adversarial probe. Both halves are pinned: the case that regressed (through
    a DERIVED field) and the control proving the wall is real (through a
    DECLARED one). Both are Integer, so both must reject the Suit."""

    def game_of(fn_body: str) -> str:
        return (
            "type R = { a : Integer  b : Integer } derived { surplus = a - b }\n"
            "type S = { r : R } derived { d = surp(r) }\n"
            + _game(
                decls=f"function surp(x : R) = {fn_body}",
                state="s : S = S { r: R { a: 9, b: 6 } }  score[player] : Integer = 0",
            ).replace(
                "phase play { for each player p: score[p] := 1 }",
                "phase play { for each player p: "
                "score[p] := (if s.d is hearts then 1 else 0) }",
            )
        )

    for body in ("x.surplus", "x.a"):
        with pytest.raises(DiagnosticError) as ei:
            check_dsl(game_of(body), "g.cardlang")
        assert "comparing Suit with Integer can never be equal" in str(ei.value), body


@pytest.mark.parametrize(
    "derived_body",
    [
        "hearts",  # an enum value
        "turn",  # a state variable
        "deck",  # a zone
        "actor",  # a pronoun
        "rank_value(2 of clubs)",  # a stdlib call
        "x + 1",  # the struct's own declared field
    ],
)
def test_a_derived_body_may_name_anything_resolve_scopes_it(derived_body: str) -> None:
    """resolve scopes a derived body as the game's names PLUS the struct's own
    fields (`_classify_type_derived`), so a body may legitimately name a state
    variable, a zone, an enum value or a pronoun.

    `struct_registry` used to type derived bodies in a BARE `TypeEnv` carrying
    only the fields, which was survivable while a lookup miss returned the
    permissive top and became a crash the moment it raised: `derived { s =
    hearts }` aborted the whole check. Found as one instance (a struct literal,
    below) in review; this is the swept class (decisions.md, "Closed-domain
    completeness" — sweep the class before patching the instance)."""
    check_dsl(
        f"type R = {{ x : Integer }} derived {{ d = {derived_body} }}\n"
        + _game(state="score[player] : Integer = 0  turn : Integer = 0"),
        "g.cardlang",
    )


@pytest.mark.parametrize(
    "types",
    [
        # its OWN type: the reported instance
        "type R = { x : Integer } derived { copy = R { x: x } }",
        # a LATER-declared type: same miss, one declaration over
        "type A = { n : Integer } derived { made = B { m: n } }\ntype B = { m : Integer }",
        # control: an EARLIER type, which the source-order map already had
        "type B = { m : Integer }\ntype A = { n : Integer } derived { made = B { m: n } }",
    ],
)
def test_a_derived_body_may_build_any_declared_struct(types: str) -> None:
    """A derived body may name a struct literal of ANY declared type, including
    its own and one declared later — resolve validates the literal against
    every declared type, so these are valid programs. `struct_registry` builds
    in source order, so the body's environment must be seeded with every
    declared type rather than only the ones already completed.

    The self-referential case additionally proves the fixpoint TERMINATES on a
    recursive type: `R`'s field map contains an `R`, so structural comparison
    would nest one level deeper every round forever. `_registry_key` compares
    nominally one level down, which is both finite and the right question."""
    check_dsl(types + "\n" + _game(), "g.cardlang")


@pytest.mark.parametrize("outer_first", [True, False])
def test_a_nested_struct_field_is_typed_whatever_the_declaration_order(
    outer_first: bool,
) -> None:
    """A NESTED struct's fields are observable — `infer`'s Member arm reads
    them, so `o.inner.flag` types off the `Inner` embedded in `Outer.inner`,
    not off the registry's `Inner`. Two bugs conspired to leave that embedded
    copy stale when `Outer` was declared FIRST: the convergence key reduced a
    nested struct to its bare name, so a round that only sharpened nested
    fields looked identical; and the loop tested before assigning, so the
    round that reported convergence — built against the fullest environment —
    was thrown away. `o.inner.flag` then typed as the permissive top and a
    Boolean was silently assignable to an Integer state variable.

    Declaration order is the sharp formulation: the same program must get the
    same verdict either way round, so this asserts both orders reject."""
    outer = "type Outer = { n : Integer } derived { inner = Inner { m: n } }"
    inner = "type Inner = { m : Integer } derived { flag = m > 0 }"
    types = f"{outer}\n{inner}" if outer_first else f"{inner}\n{outer}"
    src = types + "\n" + _game(
        decls="function ask(o : Outer) = o.inner.flag",
        state="o : Outer = Outer { n: 3 }  score[player] : Integer = 0",
    ).replace(
        "phase play { for each player p: score[p] := 1 }",
        "phase play { for each player p: score[p] := ask(o) }",
    )
    with pytest.raises(DiagnosticError) as ei:
        check_dsl(src, "g.cardlang")
    assert "cannot assign Boolean to 'score' (Integer)" in str(ei.value)


@pytest.mark.parametrize("hops", [0, 1, 2, 3, 6, 12])
def test_a_recursive_struct_path_stays_typed_at_any_depth(hops: int) -> None:
    """A struct's field map holds a SNAPSHOT of each struct-typed field, and a
    recursive type has no finite unrolled form — every embedded copy is one
    round staler than the last. Reading snapshots therefore made the wall decay
    with traversal depth: `r.copy.flag` and `r.copy.copy.flag` were checked,
    `r.copy.copy.copy.flag` typed as the permissive top and a Boolean became
    assignable to an Integer.

    A bounded comparison depth cannot fix this — the path stays observable past
    any cutoff. Reads resolve through the REGISTRY by name instead
    (`_canonical`), which is exact at every depth because struct types are
    nominal. Parametrized well past any plausible cutoff for that reason."""
    path = "r" + ".copy" * hops + ".flag"
    src = (
        "type R = { x : Integer } derived { copy = R { x: x }  flag = x > 0 }\n"
        + _game(state="r : R = R { x: 3 }  score[player] : Integer = 0").replace(
            "phase play { for each player p: score[p] := 1 }",
            f"phase play {{ for each player p: score[p] := {path} }}",
        )
    )
    with pytest.raises(DiagnosticError) as ei:
        check_dsl(src, "g.cardlang")
    assert "cannot assign Boolean to 'score' (Integer)" in str(ei.value), path


def test_a_declaration_dag_does_not_blow_up_the_fixpoint() -> None:
    """Each `T_i` holds TWO fields of `T_{i-1}`, so a structural fingerprint
    revisits the shared child once per path and is exponential in the chain
    length — a modest source file could stall the checker. Reads resolving
    through the registry removed the need to fingerprint nested fields at all,
    so this is linear again. Twenty levels is far past where the exponential
    form became unusable (seconds, and a million-node fingerprint per round)."""
    types = ["type T0 = { v : Integer } derived { f0 = v > 0 }"]
    for i in range(1, 21):
        types.append(
            f"type T{i} = {{ a : T{i - 1}  b : T{i - 1} }} "
            f"derived {{ f{i} = a.f{i - 1} }}"
        )
    check_dsl("\n".join(types) + "\n" + _game(), "g.cardlang")


@pytest.mark.parametrize(
    "body,expected",
    [("score", TInteger()), ("hearts", TEnum("Suit")), ("x > 0", TBoolean())],
)
def test_env_from_game_builds_derived_bodies_with_ambient_names(
    body: str, expected: object
) -> None:
    """`env_from_game(game)` — the public helper, called WITHOUT a prebuilt
    registry — must build derived bodies with the game's ambient names in
    scope, exactly as the main pipeline does.

    Its default branch used to call `struct_registry(game)` bare, which types
    derived bodies against an empty `TypeEnv`; once a lookup miss raised, that
    aborted the helper outright for a valid game. The main `typecheck` path had
    been fixed by supplying the registry, which is precisely what stopped it
    from exercising this branch — a public helper is a caller too, and its
    behaviour must not depend on which entry point reached it."""
    src = f"""
type R = {{ x : Integer }} derived {{ d = {body} }}
game G {{
  players: 2
  max_length: 1000
  cards: standard52
  ranking: A K Q J 10 9 8 7 6 5 4 3 2
  zones {{ deck : Deck  hand[player] : Hand<player> }}
  state {{ score : Integer = 0 }}
  phase play {{ score := 1 }}
  winner: highest score
}}
"""
    from cardlang.parse import parse_text
    from cardlang.resolve import resolve
    from cardlang.typecheck import env_from_game

    env = env_from_game(resolve(parse_text(src, "g.cardlang")))
    assert env.structs["R"].fields["d"] == expected


def test_env_from_game_keeps_the_signatures_it_solved() -> None:
    """The default branch solves the function signatures on its way to the
    struct registry — the two are one fixpoint — so it must return them.

    Discarding them left `TypeEnv.functions` empty, and `infer` on a call to
    any user function then raised the no-signature `AssertionError` against an
    environment that had just computed that very signature. Asserting the
    inferred TYPE rather than merely that nothing raised: an empty map is
    exactly what the old code had, and a laxer assertion would not have
    noticed it."""
    from cardlang.parse import parse_text
    from cardlang.resolve import resolve
    from cardlang.typecheck import env_from_game

    src = _game(decls="function dbl(x : Integer) = x + x", state="score : Integer = 0")
    env = env_from_game(
        resolve(parse_text(src.replace("score[p] := 1", "score := 1"), "g.cardlang"))
    )
    assert set(env.functions) == {"dbl"}
    assert infer(n.Call("dbl", (n.IntLit(2),)), env) == TInteger()


def test_env_from_game_fills_in_the_procedure_signatures() -> None:
    """Swept from the same class as the two findings above, before a fourth
    instance was reported: `env_from_game` also owed `procedures`.

    This one failed SILENTLY rather than loudly, which makes it the worse
    shape. The `run`-site check guarded with `if sig is not None`, so an env
    without procedure signatures skipped the arity and argument-type wall
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
  state { score : Integer = 0 }
  phase play { score := 1  run bump(0) }
  winner: highest score
}
procedure bump(p : Player) { score := 1 }
"""
    env = env_from_game(resolve(parse_text(src, "g.cardlang")))
    assert set(env.procedures) == {"bump"}

    bag = DiagnosticBag()
    _check_stmt_exprs(
        n.RunStmt("bump", (n.IntLit(0), n.IntLit(1), n.IntLit(2))), env, bag
    )
    assert any("expects 1 argument(s), got 3" in d.message for d in bag.items)


def test_a_derived_field_reached_through_a_function_is_assignment_checked() -> None:
    """The same defect at an assignment rather than a comparison: `s.flag` is a
    Boolean reached through a function, and a Boolean may not be written to an
    Integer-declared state variable. Before the fixpoint this checked clean AND
    ran to completion in a playout, writing booleans into the score."""
    src = (
        "type R = { a : Integer } derived { made = a > 0 }\n"
        "type S = { r : R } derived { flag = ask(r) }\n"
        + _game(
            decls="function ask(x : R) = x.made",
            state="s : S = S { r: R { a: 3 } }  score[player] : Integer = 0",
        ).replace(
            "phase play { for each player p: score[p] := 1 }",
            "phase play { for each player p: score[p] := s.flag }",
        )
    )
    with pytest.raises(DiagnosticError) as ei:
        check_dsl(src, "g.cardlang")
    assert "cannot assign Boolean to 'score' (Integer)" in str(ei.value)


def test_forward_struct_reference_is_top_not_a_wall() -> None:
    """The one reachable `type_from_name` fallback that is legitimately the top:
    `struct_registry` builds in source order, so a field typed by a LATER
    struct resolves to the permissive top. Documented Stage-2 behaviour — this
    pins it so the fallback is not "fixed" into a raise, which would reject a
    valid program."""
    check_dsl(
        _game("type A = { b : B }\ntype B = { x : Integer }"), "g.cardlang"
    )  # must not raise


# =============================================================================
# The audited top set — enumerated, so a new permissive site must be classified
# =============================================================================

# Every module that may construct `TAny()`, with the number of construction
# sites in it. A change to any count is a change to the permissive surface and
# must be justified in this module's ledger. The classification of each
# surviving site, so a count change can be checked against an argument rather
# than just re-blessed:
#
# typecheck.py (13)
#   legitimate top (no better type exists) — 5:
#     `type_from_name`'s unknown name (a FORWARD struct reference, ledger
#     residual 3); pronoun member access (deferred shape); a non-`actor`
#     pronoun; a bare function NAME in value position; a procedure `Sig.ret`
#     (a procedure is a statement — the field is never read).
#   gradual propagation, downstream of a wall that already fired — 4:
#     a subscript of a non-collection (`subscriptable`), a comprehension
#     element off a bad source (`_check_card_source`), an unknown struct field
#     and an unknown Card field (both rejected in `_check_expr`). Each is
#     reached only with an error already in the bag, or with a top receiver.
#   recorded residual, merge failure — 3: `ListLit` and the two `IfExpr` arms,
#     where `unify` returns None (ledger residual 1).
#   recorded residual, precision — 1: `max`/`min` (ledger residual 2).
#   deliberate, cycle-breaking — 1: `_provisional_structs` types derived
#     fields as the top so function signatures can be built before them (ledger
#     residual 4). Written at the site that introduces it, not reached as
#     a fallback.
# types.py (2)
#   `unify`'s top absorption, and the sticky-key merge — both ARE the top
#   semantics, not lookups.
# stdlib/signatures.py (11)
#   the audited dynamic-signature set: `suit_of`'s polymorphic argument,
#   `error()`'s return (it diverges, so it must type in any context), the
#   trick-winner and auction-outcome callbacks whose real type the `Sig` model
#   cannot express, and the `ChipStack` resource zone's element.
AUDITED_TOP_SITES: dict[str, int] = {
    "typecheck.py": 14,
    "types.py": 2,
    "stdlib/signatures.py": 11,
}


def _count_top_constructions(path: Path) -> int:
    tree = ast.parse(path.read_text())
    return sum(
        1
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "TAny"
    )


def test_the_permissive_top_surface_is_pinned() -> None:
    """`TAny()` may only be constructed at audited sites. This is the
    vacuously-green guard for the whole module: without it, a future lookup
    miss could quietly reintroduce a permissive fallback and every test above
    would still pass."""
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
    from cardlang.types import unify

    assert unify(TCollection(TAny()), TCollection(TCard())) is not None
