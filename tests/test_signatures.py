"""Native type signatures stay in sync with the name sets, and known
signatures are correct (cardlang/builtins/signatures.py).

property:   the Builtin and Primitive name sets, the signature tables, and
            the runtime dispatchers are one interface — every name in a *tabled*
            registry has a signature row, every *callable* name reaches a
            dispatch arm, and for CALL_SIGS additionally the same per-name
            arity and, where an arm plainly forwards to a named helper,
            Python annotations that agree with the declared DSL types
domain:     every registry with a signature table × that table; every
            callable registry × the dispatcher(s) serving it (the climb
            lead set is served twice — by its query, and by the action
            space's codec-else-universe pair); every CALL_SIGS entry ×
            {name, arity, param annotations, return annotation}
registry:   the name sets themselves for names; the dispatch's own AST for
            what each arm consumes (derived by parsing, never hand-listed)
covered:    names (set equality both ways, every tabled registry),
            dispatchability (every callable registry, against its
            dispatcher), arity (all arms), annotations for every
            plain-forward arm and its return
sampled:    none
residual:   inline arms (an expression instead of a helper call — team_of,
            card_points, error, peg_pair/run_points) get arity-only
            coverage: there is no annotation to introspect, and the
            expression is its own statement of the types. `rank_value`
            forwards to `values.rank_strength` (the runtime Owner Guard for
            a rank outside a partial `ranking:`), but passes `args[0].rank`
            -- a computed position the mapping skips -- so it too gets
            arity plus return-annotation coverage only. TAny positions
            are deliberately loose (polymorphic suit_of argument; the typed
            object model's deferred edges) and skipped by the mapping.
            The climb sets have no signature table and no reconciliation
            cell: a climb query is named in a `round climb` slot and is
            never expression-typed, so there is no type to declare — they
            carry dispatchability only.
            LIBRARY_ZONE_TYPES has no dispatchability cell: zone types name
            data, not callables, so there is no arm to reach. Their
            projection coverage is pinned by the zone-projection and
            partition-helper tests.
            Nothing forces a NEW registry to acquire a dispatchability pin —
            the registry-to-dispatcher pairing is not derivable from code,
            so each pin below names its own registry. Deferred: issue #108.
"""

from __future__ import annotations

import ast
import dataclasses
import importlib
import inspect
import typing

from cardlang.builtins.functions import (
    BOARD_ONLY_CALL_FUNCS,
    CALL_FUNCS,
    DECK_ONLY_CALL_FUNCS,
    ANY_FLAVOR_CALL_FUNCS,
    BUILTIN_TRICK_WINNERS,
    PRIMITIVE_AUCTION_OUTCOMES,
    PRIMITIVE_EARLY_PREDICATES,
    PRIMITIVE_TRICK_WINNERS,
    TRICK_WINNER_NAMES,
    VALUE_NAMES,
)
from cardlang.builtins.signatures import (
    CALL_SIGS,
    EARLY_SIGS,
    VALUE_SIGS,
    ZONE_CONTENT,
    Sig,
)
from cardlang.runtime import narrowing
from cardlang.stdlib.zones import LIBRARY_ZONE_TYPES
from cardlang.types import TAny, TCard, TCollection, TEnum, TOptional, TPlayer, TTeam


def test_tables_reconcile_with_name_sets() -> None:
    # The declaration side is data: the signature tables must cover exactly
    # the name sets, both directions.
    assert set(CALL_SIGS) == set(CALL_FUNCS)
    assert set(VALUE_SIGS) == set(VALUE_NAMES)
    assert set(EARLY_SIGS) == set(PRIMITIVE_EARLY_PREDICATES)
    assert set(ZONE_CONTENT) == set(LIBRARY_ZONE_TYPES)
    # The two outcome namespaces partition the value-name set (the resolver
    # validates each round form against its own; the union is the bare-name
    # space), and the winner namespace is itself the disjoint union of its
    # two homes (the Builtin standard comparisons and the game-local ones).
    assert TRICK_WINNER_NAMES | PRIMITIVE_AUCTION_OUTCOMES == VALUE_NAMES
    assert TRICK_WINNER_NAMES.isdisjoint(PRIMITIVE_AUCTION_OUTCOMES)
    assert BUILTIN_TRICK_WINNERS | PRIMITIVE_TRICK_WINNERS == TRICK_WINNER_NAMES
    assert BUILTIN_TRICK_WINNERS.isdisjoint(PRIMITIVE_TRICK_WINNERS)


def test_outcome_names_are_dispatchable() -> None:
    # Each declared outcome name must resolve to a runtime callback — guards the
    # resolve namespace from drifting out of sync with the runtime dispatchers
    # (else a name passes resolve and then Assertion-fails mid-playout).
    from cardlang.runtime.primitives import auction_outcome_function, value_function

    for name in TRICK_WINNER_NAMES:
        assert callable(value_function(name))
    for name in PRIMITIVE_AUCTION_OUTCOMES:
        assert callable(auction_outcome_function(name))


def test_climb_queries_are_dispatchable() -> None:
    # The climbing form's combination-engine query names must each resolve to a
    # runtime callable, like the outcome names above — guards the resolve namespace
    # (PRIMITIVE_CLIMB_LEADS / PRIMITIVE_CLIMB_FOLLOWS) from drifting out of sync with the
    # runtime dispatchers.
    from cardlang.builtins.functions import (
        PRIMITIVE_CLIMB_FOLLOWS,
        PRIMITIVE_CLIMB_LEADS,
    )
    from cardlang.runtime.primitives import climb_follow_function, climb_lead_function

    for name in PRIMITIVE_CLIMB_LEADS:
        assert callable(climb_lead_function(name))
    for name in PRIMITIVE_CLIMB_FOLLOWS:
        assert callable(climb_follow_function(name))


def test_early_predicates_are_dispatchable() -> None:
    """Every declared early-termination predicate must resolve to a runtime
    callback, like the outcome and climb names above. The `early` slot shares
    `value_function` with the outcome slot (the sets stay separate — see the
    PRIMITIVE_EARLY_PREDICATES comment), so a name added to the set without a
    dispatch arm passes resolve and then Assertion-fails mid-trick.

    red under: delete the `case "on_play_off_led_suit"` arm from `value_function`
    (cardlang/runtime/primitives.py).
    """
    from cardlang.runtime.primitives import value_function

    for name in PRIMITIVE_EARLY_PREDICATES:
        assert callable(value_function(name))


def test_climb_action_space_is_derivable() -> None:
    """`ActionSpace.for_game` derives a climbing game's combo block from the
    arithmetic codec, else the enumerable universe — so the codec and universe
    registries must JOINTLY cover PRIMITIVE_CLIMB_LEADS. A lead query in neither is
    accepted by resolve and by both climb-query dispatchers above, and fails
    only when the adapter first builds the action space. Replays the adapter's
    own branch (openspiel/encoding.py) rather than a second copy of the
    mapping. Quantifier: that the branch reaches a dispatch arm — that each
    universe enumerates correctly is the per-game golden's property, not this
    pin's.

    red under: delete the `case "president_lead_options"` arm from
    `climb_universe_function` (cardlang/runtime/primitives.py).
    """
    from cardlang.builtins.functions import PRIMITIVE_CLIMB_LEADS
    from cardlang.runtime.primitives import (
        climb_codec_function,
        climb_universe_function,
    )

    for name in PRIMITIVE_CLIMB_LEADS:
        if climb_codec_function(name) is None:
            assert callable(climb_universe_function(name))


def test_call_funcs_are_dispatchable() -> None:
    # Each name registered in CALL_FUNCS must reach a real arm of
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
    from cardlang.runtime.evaluate import native_call as call
    from cardlang.runtime.state import Ctx, RuntimeState, ZoneStore
    from cardlang.runtime.values import Seating

    decls = (n.ZoneDecl(name="probe", index=None, type_ref=n.TypeRef(name="Hand")),)
    rs = RuntimeState(Seating(2), ZoneStore(decls, (0, 1)), random.Random(0))
    ctx = Ctx(rs=rs, chooser=lambda p, c, k: list(c[:k]))

    for name in CALL_FUNCS:
        try:
            call(name, [], ctx)
        except AssertionError as e:
            assert "unknown native function" not in str(e), (
                f"{name!r} falls through call()'s default arm: {e}"
            )
        except Exception:  # noqa: BLE001, S110 -- any non-AssertionError means it
            pass  # dispatched; the channel split is guarded by test_assert_triage.py


def test_deck_only_classification_partitions_call_funcs() -> None:
    # The feature classification (functions.py) partitions the call registry:
    # every native call is deck-only (rejected in a piece game), board-only
    # (rejected in a boardless game), or generic (legal everywhere), exactly
    # one, none omitted. A newly registered call absent from all three sets
    # fails here rather than silently defaulting -- the guard's domain stays
    # exactly CALL_FUNCS. (The rejection behavior itself is
    # tests/test_piece_content_guards.py.)
    assert (
        DECK_ONLY_CALL_FUNCS | BOARD_ONLY_CALL_FUNCS | ANY_FLAVOR_CALL_FUNCS
        == CALL_FUNCS
    )
    assert DECK_ONLY_CALL_FUNCS.isdisjoint(ANY_FLAVOR_CALL_FUNCS)
    assert BOARD_ONLY_CALL_FUNCS.isdisjoint(DECK_ONLY_CALL_FUNCS)
    assert BOARD_ONLY_CALL_FUNCS.isdisjoint(ANY_FLAVOR_CALL_FUNCS)


def test_known_call_signatures() -> None:
    assert CALL_SIGS["player_holding"] == Sig((TCard(),), TPlayer())
    assert CALL_SIGS["team_of"] == Sig((TPlayer(),), TTeam())
    # suit_of is polymorphic (card OR single-card zone) -> loose arg; the return
    # is a plain Suit (an empty zone errors loudly at the cause rather than
    # yielding a silent `none` — see the CALL_SIGS row comment).
    assert CALL_SIGS["suit_of"].ret == TEnum("Suit")


# --- CALL_SIGS <-> runtime dispatch reconciliation ----------------------------
#
# CALL_SIGS states each native function's interface once for the checker; the
# `call()` match (across both dispatch homes) states it again for the runtime (how many
# `args[i]` the arm consumes, and the Python annotations of the helper it
# forwards to). Two statements of one interface, which nothing else
# reconciles: a helper declared `Rank?` to the DSL but annotated `rank: str`
# to Python would deny the `none` value the checker admits (and the body
# deliberately handles — an unset claim matches no card), and the two
# statements would disagree in silence. These pins derive both facts from the
# dispatch's AST rather than a third hand-written list.


@dataclasses.dataclass(frozen=True)
class _DispatchFact:
    arity: int  # 1 + the highest args[i] the arm reads (0 if none)
    helper: object | None  # the resolved helper callable, if the arm is a plain forward
    helper_args: tuple[object, ...]  # per helper param: 'ctx', an int (args[i]), or None
    traced: bool = False  # the arm unpacks (value, events) and emits via _emit


def _call_dispatch_facts() -> dict[str, _DispatchFact]:
    """Both dispatch homes: `call` is split across the Builtins half and the
    Primitives half (issue #201), and CALL_SIGS covers their union, so a scrape
    of one home alone would report the other's whole set as undispatched."""
    import cardlang.runtime.builtins as rt_builtins
    import cardlang.runtime.primitives as rt_primitives

    facts: dict[str, _DispatchFact] = {}
    for module in (rt_builtins, rt_primitives):
        facts.update(_facts_in(ast.parse(inspect.getsource(module)), module))
    return facts


def _facts_in(tree: ast.Module, module: object) -> dict[str, _DispatchFact]:
    """`module` resolves an arm that forwards to a MODULE-LEVEL helper of its
    own home (`_lines`, `highest_of_led_suit`) rather than to a game module."""
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
        traced = False
        ret = next((s for s in case.body if isinstance(s, ast.Return)), None)
        # A NARROWED tracing arm does not `return f(...)`: it unpacks
        # `(value, events)`, emits the events, then returns the value. Find
        # the call through the assignment so the annotation check below still
        # reaches the helper — the shape this test exists to keep honest.
        call: ast.Call | None = None
        if ret is not None and isinstance(ret.value, ast.Call):
            call = ret.value
        elif ret is not None and isinstance(ret.value, ast.Name):
            for stmt in case.body:
                if (
                    isinstance(stmt, ast.Assign)
                    and isinstance(stmt.targets[0], ast.Tuple)
                    and isinstance(stmt.value, ast.Call)
                    and any(
                        isinstance(el, ast.Name) and el.id == ret.value.id
                        for el in stmt.targets[0].elts
                    )
                ):
                    call = stmt.value
                    traced = True
        if call is not None and isinstance(call.func, ast.Name):
            fn_name = call.func.id
            if fn_name in imported:
                helper = getattr(importlib.import_module(imported[fn_name]), fn_name)
            elif hasattr(module, fn_name):
                helper = getattr(module, fn_name)
            if helper is not None:
                shapes: list[object] = []
                for arg in call.args:
                    if isinstance(arg, ast.Starred):
                        # `*_bind(ctx, ROW)` expands to the two value bundles
                        # (EngineFacts, GameReads); hold their positions so the
                        # later args still line up with the helper's params.
                        shapes.extend([None, None])
                    elif isinstance(arg, ast.Name) and arg.id == "ctx":
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
            traced=traced,
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
    helper are the three inline expressions the module ledger names
    (`rank_value` left the list when it began forwarding to
    `values.rank_strength`; its argument positions are computed, so the
    helper resolves and only its return is reconciled)."""
    facts = _call_dispatch_facts()
    inline = sorted(
        name
        for name, fact in facts.items()
        if fact.helper is None or not callable(fact.helper)
    )
    assert inline == ["card_points", "error", "team_of"], (
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
            if fact.traced:
                # A tracing primitive returns (declared value, events): the
                # DECLARED type is the first element, and the second must be
                # the trace-event tuple — checked, not waved through.
                targs = typing.get_args(actual_ret)
                if len(targs) != 2 or targs[1] != tuple[narrowing.TraceEvent, ...]:
                    problems.append(
                        f"{name}: EMITS_TRACE helper must return "
                        f"(value, tuple[TraceEvent, ...]); got {actual_ret}"
                    )
                    continue
                actual_ret = targs[0]
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
