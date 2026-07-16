"""Stdlib type signatures stay in sync with the name sets, and known signatures
are correct (cardlang/stdlib/signatures.py).

property:   CALL_SIGS and the runtime `call()` dispatch are one interface:
            same name set, same per-name arity, and — where an arm plainly
            forwards to a named helper — Python annotations that agree with
            the declared DSL types
domain:     every CALL_SIGS entry × {name, arity, param annotations, return
            annotation}
registry:   CALL_SIGS itself for names; the dispatch's own AST for what each
            arm consumes (derived by parsing, never hand-listed)
covered:    names (set equality both ways), arity (all arms), annotations for
            every plain-forward arm and its return
sampled:    none
residual:   inline arms (an expression instead of a helper call — team_of,
            rank_value, card_value, error, peg_pair/run_points) get
            arity-only coverage: there is no annotation to introspect, and
            the expression is its own statement of the types. TAny positions
            are deliberately loose (polymorphic suit_of argument; the typed
            object model's deferred edges) and skipped by the mapping.
"""

from __future__ import annotations

import ast
import dataclasses
import importlib
import inspect
import typing

from cardlang.stdlib.functions import (
    STDLIB_AUCTION_OUTCOMES,
    STDLIB_CALL_FUNCS,
    STDLIB_EARLY_PREDICATES,
    STDLIB_TRICK_OUTCOMES,
    STDLIB_VALUE_NAMES,
)
from cardlang.stdlib.signatures import (
    CALL_SIGS,
    EARLY_SIGS,
    VALUE_SIGS,
    ZONE_CONTENT,
    Sig,
)
from cardlang.stdlib.zones import LIBRARY_ZONE_TYPES
from cardlang.types import TAny, TCard, TCollection, TEnum, TOptional, TPlayer, TTeam


def test_tables_reconcile_with_name_sets() -> None:
    # "stdlib is data": the signature tables must cover exactly the name sets.
    assert set(CALL_SIGS) == set(STDLIB_CALL_FUNCS)
    assert set(VALUE_SIGS) == set(STDLIB_VALUE_NAMES)
    assert set(EARLY_SIGS) == set(STDLIB_EARLY_PREDICATES)
    assert set(ZONE_CONTENT) == set(LIBRARY_ZONE_TYPES)
    # The two outcome namespaces partition the value-name set (the resolver
    # validates each round form against its own; the union is the bare-name space).
    assert STDLIB_TRICK_OUTCOMES | STDLIB_AUCTION_OUTCOMES == STDLIB_VALUE_NAMES
    assert STDLIB_TRICK_OUTCOMES.isdisjoint(STDLIB_AUCTION_OUTCOMES)


def test_outcome_names_are_dispatchable() -> None:
    # Each declared outcome name must resolve to a runtime callback — guards the
    # resolve namespace from drifting out of sync with the runtime dispatchers
    # (else a name passes resolve and then Assertion-fails mid-playout).
    from cardlang.runtime.stdlib import auction_outcome_function, value_function

    for name in STDLIB_TRICK_OUTCOMES:
        assert callable(value_function(name))
    for name in STDLIB_AUCTION_OUTCOMES:
        assert callable(auction_outcome_function(name))


def test_climb_queries_are_dispatchable() -> None:
    # The climbing form's combination-engine query names must each resolve to a
    # runtime callable, like the outcome names above — guards the resolve namespace
    # (STDLIB_CLIMB_LEADS / STDLIB_CLIMB_FOLLOWS) from drifting out of sync with the
    # runtime dispatchers.
    from cardlang.runtime.stdlib import climb_follow_function, climb_lead_function
    from cardlang.stdlib.functions import STDLIB_CLIMB_FOLLOWS, STDLIB_CLIMB_LEADS

    for name in STDLIB_CLIMB_LEADS:
        assert callable(climb_lead_function(name))
    for name in STDLIB_CLIMB_FOLLOWS:
        assert callable(climb_follow_function(name))


def test_call_funcs_are_dispatchable() -> None:
    # Each name registered in STDLIB_CALL_FUNCS must reach a real arm of
    # call()'s match — not fall through to its loud `case _` default. Unlike
    # value_function/climb_lead_function (which just return a callable
    # reference), call() dispatches AND executes in the same statement, so
    # there is no args-free way to "just look up" an arm: invoke each name
    # with no args and a minimal-but-real Ctx, and treat any exception other
    # than the default arm's AssertionError as proof the name was dispatched
    # (wrong arg count, missing runtime state, etc. all reach real code past
    # the match).
    import random

    from cardlang.ast import nodes as n
    from cardlang.runtime.state import Ctx, RuntimeState, ZoneStore
    from cardlang.runtime.stdlib import call
    from cardlang.runtime.values import Seating

    decls = (n.ZoneDecl(name="probe", index=None, type_ref=n.TypeRef(name="Hand")),)
    rs = RuntimeState(Seating(2), ZoneStore(decls, (0, 1)), random.Random(0))
    ctx = Ctx(rs=rs, chooser=lambda p, c, k: list(c[:k]))

    for name in STDLIB_CALL_FUNCS:
        try:
            call(name, [], ctx)
        except AssertionError as e:
            assert "unknown stdlib function" not in str(e), (
                f"{name!r} falls through call()'s default arm: {e}"
            )
        except Exception:
            pass  # dispatched: failed downstream for some other reason



def test_known_call_signatures() -> None:
    assert CALL_SIGS["player_holding"] == Sig((TCard(),), TPlayer())
    assert CALL_SIGS["team_of"] == Sig((TPlayer(),), TTeam())
    # suit_of is polymorphic (card OR single-card zone) -> loose arg; the return
    # is a plain Suit (an empty zone errors loudly at the cause rather than
    # yielding a silent `none` — see the CALL_SIGS row comment).
    assert CALL_SIGS["suit_of"].ret == TEnum("Suit")


# --- CALL_SIGS <-> runtime dispatch reconciliation ----------------------------
#
# CALL_SIGS states each stdlib function's interface once for the checker; the
# `call()` match in runtime/stdlib.py states it again for the runtime (how many
# `args[i]` the arm consumes, and the Python annotations of the helper it
# forwards to). Two statements of one interface, previously with no
# reconciliation: `coup_has_char` was declared `Rank?` to the DSL and
# `rank: str` to Python, so the annotation denied the `none` value the checker
# admits (and the body deliberately handles — an unset claim matches no card).
# These pins derive both facts from the dispatch's AST rather than a third
# hand-written list.


@dataclasses.dataclass(frozen=True)
class _DispatchFact:
    arity: int  # 1 + the highest args[i] the arm reads (0 if none)
    helper: "object | None"  # the resolved helper callable, if the arm is a plain forward
    helper_args: "tuple[object, ...]"  # per helper param: 'ctx', an int (args[i]), or None


def _call_dispatch_facts() -> dict[str, _DispatchFact]:
    import cardlang.runtime.stdlib as rt

    tree = ast.parse(inspect.getsource(rt))
    call_fn = next(
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == "call"
    )
    match_stmt = next(node for node in call_fn.body if isinstance(node, ast.Match))
    facts: dict[str, _DispatchFact] = {}
    for case in match_stmt.cases:
        if not (
            isinstance(case.pattern, ast.MatchValue)
            and isinstance(case.pattern.value, ast.Constant)
            and isinstance(case.pattern.value.value, str)
        ):
            continue  # the loud `case _` default
        name = case.pattern.value.value
        indices = [
            node.slice.value
            for stmt in case.body
            for node in ast.walk(stmt)
            if isinstance(node, ast.Subscript)
            and isinstance(node.value, ast.Name)
            and node.value.id == "args"
            and isinstance(node.slice, ast.Constant)
            and isinstance(node.slice.value, int)
        ]
        # The helper, when the arm is `return f(...)` on an imported or
        # module-level name; anything else (inline expressions) gets arity-only.
        imported: dict[str, str] = {}
        for stmt in case.body:
            if isinstance(stmt, ast.ImportFrom) and stmt.module is not None:
                for alias in stmt.names:
                    imported[alias.asname or alias.name] = stmt.module
        helper: object | None = None
        helper_args: tuple[object, ...] = ()
        ret = next((s for s in case.body if isinstance(s, ast.Return)), None)
        if (
            ret is not None
            and isinstance(ret.value, ast.Call)
            and isinstance(ret.value.func, ast.Name)
        ):
            fn_name = ret.value.func.id
            if fn_name in imported:
                helper = getattr(importlib.import_module(imported[fn_name]), fn_name)
            elif hasattr(rt, fn_name):
                helper = getattr(rt, fn_name)
            if helper is not None:
                shapes: list[object] = []
                for arg in ret.value.args:
                    if isinstance(arg, ast.Name) and arg.id == "ctx":
                        shapes.append("ctx")
                    elif (
                        isinstance(arg, ast.Subscript)
                        and isinstance(arg.value, ast.Name)
                        and arg.value.id == "args"
                        and isinstance(arg.slice, ast.Constant)
                    ):
                        shapes.append(arg.slice.value)
                    else:
                        shapes.append(None)  # a computed argument: skip its check
                helper_args = tuple(shapes)
        facts[name] = _DispatchFact(
            arity=(max(indices) + 1) if indices else 0,
            helper=helper,
            helper_args=helper_args,
        )
    return facts


def _python_type(t: object) -> object | None:
    """The Python annotation a DSL type corresponds to at the runtime boundary;
    None where the correspondence is loose (TAny) or unmapped — those positions
    are skipped, not asserted."""
    from cardlang.types import TBoolean, TInteger, TString

    match t:
        case TPlayer() | TTeam() | TInteger():
            return int
        case TBoolean():
            return bool
        case TString() | TEnum():
            return str
        case TCard():
            from cardlang.runtime.values import Card

            return Card
        case TOptional():
            inner = _python_type(t.inner)
            return None if inner is None else (inner | None)  # type: ignore[operator]
        case _:
            return None  # TAny and collection shapes: deliberately loose


def test_the_dispatch_parse_actually_resolves_helpers() -> None:
    """The annotation reconciliation silently skips arms whose helper it cannot
    resolve, so a mechanical dispatch refactor (a helpers dict, attribute
    calls, keyword arguments) could decay it to checking nothing while staying
    green. Pin the residual exactly: the only arms without an introspectable
    helper are the four inline expressions the module ledger names."""
    facts = _call_dispatch_facts()
    inline = sorted(
        name
        for name, fact in facts.items()
        if fact.helper is None or not callable(fact.helper)
    )
    assert inline == ["card_value", "error", "rank_value", "team_of"], (
        f"arms with no introspectable helper: {inline} — if the dispatch shape "
        "changed, teach _call_dispatch_facts the new shape rather than letting "
        "the annotation check silently skip these"
    )


def test_call_sigs_arity_matches_the_dispatch() -> None:
    """Every CALL_SIGS entry consumes exactly its declared parameter count in
    the runtime match — an arm reading args[2] for a two-parameter signature
    (or ignoring a declared parameter) is the interface disagreeing with
    itself."""
    facts = _call_dispatch_facts()
    assert set(facts) == set(CALL_SIGS)
    mismatched = {
        name: (len(sig.params), facts[name].arity)
        for name, sig in CALL_SIGS.items()
        if len(sig.params) != facts[name].arity
    }
    assert not mismatched, (
        f"declared param count vs args[i] consumed by call(): {mismatched}"
    )


def test_helper_annotations_agree_with_call_sigs() -> None:
    """Where a dispatch arm plainly forwards to a named helper, the helper's
    Python annotations must agree with the declared DSL types at every mappable
    position (including the return). This is the pin that catches a helper
    annotated `str` for a `Rank?` parameter — a lie mypy then enforces against
    the body, denying a `none` the checker admits."""
    facts = _call_dispatch_facts()
    problems: list[str] = []
    for name, sig in CALL_SIGS.items():
        fact = facts[name]
        if fact.helper is None or not callable(fact.helper):
            continue  # inline arm: arity is pinned above; nothing to introspect
        hints = typing.get_type_hints(fact.helper)
        params = [p for p in inspect.signature(fact.helper).parameters]
        for pos, shape in enumerate(fact.helper_args):
            if not isinstance(shape, int):
                continue  # ctx, or a computed argument
            expected = _python_type(sig.params[shape])
            if expected is None:
                continue
            actual = hints.get(params[pos])
            if actual != expected:
                problems.append(
                    f"{name}: helper param '{params[pos]}' annotated {actual}, "
                    f"CALL_SIGS declares {sig.params[shape]} (~ {expected})"
                )
        expected_ret = _python_type(sig.ret)
        if expected_ret is not None:
            actual_ret = hints.get("return")
            if actual_ret != expected_ret:
                problems.append(
                    f"{name}: helper returns {actual_ret}, CALL_SIGS declares "
                    f"{sig.ret} (~ {expected_ret})"
                )
    assert not problems, "\n".join(problems)


def test_zone_contents() -> None:
    # `zone=True` throughout: these types describe values that ARE zones at
    # runtime, which is what the movement/epistemic zone-position checks key
    # on — a card query types Collection<Card> too but evaluates to a list.
    assert ZONE_CONTENT["Hand"] == TCollection(TCard(), zone=True)
    assert ZONE_CONTENT["TeamPile"] == TCollection(TCard(), zone=True)
    assert ZONE_CONTENT["ChipStack"] == TCollection(TAny(), zone=True)  # resource zone, loose
    assert all(
        isinstance(t, TCollection) and t.zone for t in ZONE_CONTENT.values()
    )
