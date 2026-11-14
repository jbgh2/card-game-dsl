"""Resolve step: the checks that read the classified tree.

Independent checks over one tree state, run in the order this step names
them; only ``_check_kernel_answers`` and ``_check_answer_hermeticity`` feed
another (the clauses they refuse, which ``_check_unread_clauses`` reads).

Contract (decisions.md "Closed-domain completeness", write-time triage)
-----------------------------------------------------------------------
Assumes:      the classified tree, read-only; the game's own rule and
              procedure names from before the splice; the tree as written
              before instantiation; the reader clauses the declarations step
              refused.
Now illegal:  a ``state { }`` default that cannot be evaluated where it
              is written — one reading state not yet declared, calling a
              function, or containing a ``choose``
              (``_check_state_default_scope``). ``runtime/driver``'s
              ``_declare_state`` may therefore assume every default
              evaluates against the frames standing at that moment.
              An equality comparison whose two operands are names that
              provably denote the same acting player — the binder of a
              construct that rebinds ``acting_as`` against the ``actor``
              pronoun, or against a ``let`` transitively bound to either
              (``_check_actor_alias_comparisons``, decisions.md "Naming
              the acting player twice"). This is a scope fact, not a type
              fact — both operands are ``Player`` — so it is settled here
              rather than in the type layer.
              A Kernel Definition Contract answered other than by the
              game's own one definition at the row's one Card parameter, or
              an answer that is not hermetic by reach — a pronoun, a
              `choose`, a zone not public to every observer, a bare
              per-player family, a phase's state, a Primitive, a Builtin
              outside `TRICK_ORDER_ROW_CALLS`, a later Trick Order answer
              (``_check_kernel_answers``, ``_check_answer_hermeticity``); the
              presence of a Trick Order is asked of ``kernel_contracts`` and
              of nothing else.
              A game clause
              some ``_CLAUSE_GATES`` row reads (``role == "reader"``),
              written and refused by no Owner Guard of its own, that nothing
              in the written text -- the game's own text, every spliced
              definition and provided declaration, every activated library
              or stdlib rule, the clause's own body excluded -- meets with
              any of its reader rows' tests (``_check_unread_clauses``); an
              instrument read (the driver's card census, the OpenSpiel
              ranked policy's trump fallback) is no reader. Typecheck may
              therefore assume every reader clause it meets is read by
              written text.
              Beside a rule clause reading the Play Source: a zone
              named ``hand`` not kept per player, a state variable named
              ``hand``, a game that runs no trick round, and a function a
              rule clause reaches that reads bare ``hand`` or a trick
              round's source family (``_check_play_source``).
              ``runtime/evaluate``'s ``play_source`` arm and its
              ``_hermetic_ctx``, which keeps no Play Source in a function
              body, are the Shadow Guards behind them.
              An implicit decision pool -- one the kernel builds from a
              declared zone with no expression to read, the round-source and
              ``Card``-parameter rows of ``DECISION_POOLS`` -- whose family's
              type does not show its owner the cards in it
              (``_check_implicit_pools``). ``runtime/mechanics``' trick and
              climb forms and its parameter domains may therefore assume the
              deciding seat sees every card they offer from its own
              instance.
              Anywhere in what a [[hosted-poll]] body can execute — its
              own statements and every definition reachable from them by
              name (``HOSTED_REACH_POOLS``: a procedure it runs, a move type
              it offers, guard and effect, a function it calls, each
              transitively, by ``_definition_closure``) — a statement kind
              outside ``HOSTED_POLL_ALLOWED``, the ``state`` pronoun, or a call of a
              Primitive the game's namespace holds; and a Hosted Poll binder spelled like a name
              already classifiable where the clause is written
              (``_check_hosted_polls``, ``_check_hosted_binder``).
              ``runtime/mechanics``' ``run_decision_round`` may therefore
              assume a hosted body, and all it runs, moves no card, starts no
              round of the trick or climbing form, raises no outcome or jump
              out of the round, and reads no live Round State.
              Wherever the engine keys a zone family by the acting seat
              -- a bare zone ``NameRef``, a round's ``source``, a Builtin in
              ``BUILTIN_IMPLICIT_READS`` -- a family not indexed by player,
              and for such a Builtin a family the game does not declare;
              and a round's ``into`` naming a family
              (``_check_bare_family_refs``). ``runtime/evaluate``'s ``_name``,
              ``runtime/mechanics``' round forms and ``runtime/reads``'
              ``magic_hand`` may therefore assume a seat is a key of every
              family they resolve that way, and ``_check_hidden_reads`` may
              credit a bare read as the acting seat's own instance.
              A refusal that the
              Kernel Definition Contract answer walk, the play-source walk or the no-acting-seat
              walk reaches through a call from the game's text into a library
              function, that the Hosted Poll walk reaches through a call,
              `run` or offer into library text, or that a library rule the
              game activates earns from the game's rounds, carries that
              crossing (``Route``, at the node ``_library_entry`` names), and
              names the library and its definition; a statement the reached
              definition may hold in no game (``_NEVER_HELD``) carries none.
Verified by:  for the declare-time rule, the grid in
              ``tests/test_state_default_scope.py`` — which PLAYS every
              accepted cell rather than only resolving it, since
              "accepted" was exactly the assertion that hid the defect
              the grid was written for.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field, fields, is_dataclass
from typing import Protocol, cast, get_args
from cardlang.diagnostic_codes import Code
from cardlang.ast import nodes as n
from cardlang.builtins.functions import (
    ARRIVAL_RECORD_CALLS,
    BUILTIN_IMPLICIT_READS,
    CALL_FUNCS,
    BUILTIN_CALL_FUNCS,
    TRICK_ORDER_GATED_FUNCS,
    TRICK_ORDER_GATED_WINNERS,
    TRICK_ORDER_ROW_CALLS,
)
from cardlang import kernel_contracts as K
from cardlang.primitives_block import (
    call_namespace,
    declared_names,
    declaring_phases,
    phase_local_state_names,
)
from cardlang.attribution import cite_definition, cite_library, cite_named, cite_origin, cite_where
from cardlang.diagnostics import DiagnosticBag, Route, Said, Sentence, Span
from cardlang.domains import Role, role_of
from cardlang.stdlib.hosted_poll import HOSTED_POLL_ALLOWED, HOSTED_POLL_REFUSED
from cardlang.stdlib.zones import LIBRARY_ZONE_TYPES, ZONE_PROJECTIONS, identity_to_all, reveals
from cardlang.typecheck import COMBINATION_TYPE_NAME, POSITIVE_PARAM_DOMAIN
from cardlang.types import Flavor
from cardlang.resolve.walk import _child_nodes, _walk
from cardlang.resolve.binders import _BINDER_SCOPE_FIELDS, _introduced_binders
from cardlang.resolve.reserved import (
    PLAY_SOURCE_NAME,
    _CALL_SITE_PRONOUNS,
    _PLAY_SOURCE_READING,
    _PRONOUNS,
)
from cardlang.resolve.slots import (
    _NAMING_SLOTS_BY_TYPE,
    _REFERENCE_SLOTS,
    _ROUND_QUERY_REGISTRIES,
    _round_query_slot,
    slot_namespace,
    slot_strings,
)
from cardlang.resolve.declared import (
    CARD_PARAMETER_FAMILY,
    _combination_outside_a_parameter,
    _deck_known,
    _declared_type_universe,
    _direction_refusal,
    _family_shape,
    _minted_directions,
)
from cardlang.resolve.scope import (
    _DEFAULT_REFUSED_PRONOUNS,
    _bare_family_refused,
    _bare_seat_family_in_default,
    _default_reads,
    _game_state_names,
    _keyed_ids,
    _phase_scoped_names,
    _phase_state_names,
    _pronoun_refused,
    _refused_call_site_pronouns,
    _state_out_of_scope,
)
from cardlang.resolve.crossings import _LibraryEntry, _cite_in, _definition_closure, _entry_route
from cardlang.resolve.seat_aliases import _ActorAliases, _aliases_after_let, _seat_rebinding
from cardlang.resolve.clause_gates import (
    _CLAUSE_GATES,
    _ClauseGate,
    _PROCEDURE_PARAM_DOMAINS,
    _TRICK_ORDER_READERS,
    _activated_rule_names,
    _drop_trick_order,
    _position_past_end,
)
from cardlang.resolve.ranking_slots import _result_rankings, ranking_slot


def step(
    game: n.Game,
    bag: DiagnosticBag,
    *,
    own_rules: frozenset[str],
    own_procedures: frozenset[str],
    written: n.Game,
    refused_clauses: set[str],
) -> None:
    """The classified checks step, in report order."""
    _check_play_source(game, own_rules, bag)
    _check_bare_family_refs(game, bag)
    _check_declared_type_names(game, bag)
    _check_state_default_scope(game, bag)
    _check_state_scope(game, bag)
    _check_functions(game, bag)
    refused_clauses |= _check_kernel_answers(game, bag)
    # After `_check_functions`, which owns a call-site pronoun reached through
    # a designer function and the recursion of an answer's own call.
    refused_clauses |= _check_answer_hermeticity(game, bag)
    _check_unread_clauses(
        written, [r for r in game.rules if r.origin is not None], refused_clauses, bag
    )
    # After `_classify_names`: both read the `ref_kind` the classifier stamped,
    # rather than re-deriving what is or is not a zone reference.
    _check_arrival_record_pile_args(game, bag)
    _check_procedures(game, bag, own_procedures)
    _check_nested_ring_flags(game, bag)
    _check_hosted_polls(game, bag)
    _check_chooses(game, bag)
    _check_positional_index_range(game, bag)
    _check_actor_alias_comparisons(game, bag)
    _check_delegation(game, bag)
    _check_implicit_pools(game, bag)
    _check_climb_play_zones(game, bag)


def _library_entry(steps: Sequence[tuple[Span | None, object]]) -> _LibraryEntry | None:
    """The last step a route from game-written text takes into library text,
    when the route ends in library text; None when it ends in the game's.
    `steps` is each definition the route enters, in order, with the span of
    the text that names it."""
    entry: _LibraryEntry | None = None
    in_library = False
    for depth, (span, definition) in enumerate(steps, start=1):
        origin = getattr(definition, "origin", None)
        if origin is not None and not in_library:
            entry = _LibraryEntry(
                span, origin, depth, str(getattr(definition, "name", "")),
                getattr(definition, "span", None),
            )
        in_library = origin is not None
    return entry if in_library else None


def _naming_span(container: object, namespace: str, name: str) -> Span | None:
    """The span of the first node in `container` whose reference slot names
    `name` in `namespace` (a call, a `run`, an offer)."""
    for node in _child_nodes(container):
        for field_name in _NAMING_SLOTS_BY_TYPE.get(type(node), ()):
            if slot_namespace(node, field_name) == namespace and name in slot_strings(
                node, field_name
            ):
                return cast(Span | None, getattr(node, "span", None))
    return None


def _closure_steps(
    key: tuple[str, str],
    reached: dict[tuple[str, str], tuple[object, tuple[str, str] | None]],
    root: object,
) -> list[tuple[Span | None, object]]:
    """The route `_definition_closure` reached `key` by from `root`, as
    `_library_entry`'s steps."""
    chain: list[tuple[str, str]] = []
    at: tuple[str, str] | None = key
    while at is not None:
        chain.append(at)
        at = reached[at][1]
    chain.reverse()
    steps: list[tuple[Span | None, object]] = []
    caller: object = root
    for ns, name in chain:
        target = reached[(ns, name)][0]
        steps.append((_naming_span(caller, ns, name), target))
        caller = target
    return steps
_STMT_KINDS: tuple[type, ...] = get_args(n.Stmt)


def _check_state_default_scope(game: n.Game, bag: DiagnosticBag) -> None:
    """A `state { }` default is evaluated while its own block is still being
    declared, so it may only reach state that exists by then: a name declared
    earlier in the SAME block, or one in an ENCLOSING block. `_categories`
    flattens every declaration into one game-wide `state_vars` set — right for
    the rest of the language, where state is read during play and all of it is
    live — but a default runs before its block is finished, and reading a name
    from later in the block, from a sibling phase, or from a phase nested inside
    this one dies at playout on `KeyError: variable '…' not in scope`.

    The scope model is the runtime's, mirrored rather than re-derived: `driver`
    pushes a frame per phase and pops it at phase end, and finds a phase's
    nested phases by scanning `items` for `n.Phase` — so an enclosing block's
    names are live and a sibling's are not.

    This is also where a family library's provided state lands. `_apply_uses`
    splices the provided decls in FRONT of the game's own, so a provided default
    reading one of the library's `requires` names reaches a variable the game
    declares strictly later — never in scope, whatever the game does. That
    subclass is refused before the splice, to the library's own author, by
    `_check_library_encapsulation`; this Owner Guard is what owns the general class,
    and would catch it here too if the library check were removed.

    Two constructs are refused outright rather than analysed, both because a
    default runs before the world a body assumes exists:

    - a `Call`, whose state reads live in a body `_walk` never enters from a
      default — so the choice is an interprocedural scope check or a ban, and no
      default in the corpus calls anything (decisions.md "State scoping
      (lexical)" records the narrowing; ledger tests/test_state_default_scope.py);
    - a `Choose`, which needs an acting player. A default is evaluated outside
      any turn, so the runtime raised "a `choose` with no acting player" at
      declare time; for the OpenSpiel target a decision with no actor also has
      no information set to attach to.

    A read of `actor`, or a per-player zone named bare (the acting player's
    own instance), names no one in a default for the same reason, and is
    refused beside them.

    The arms are three because the domain — `n.Expr` — was swept, not because
    three defects were reported: the `Choose` cell had no witness and was found
    by running every member of the union in default position (the grid in
    `tests/test_state_default_scope.py` carries the outcome per member)."""

    zone_index = {z.name: z.index for z in game.zones}
    keyed = _keyed_ids(game)
    for decl, node, in_scope in _default_reads(game):
        if isinstance(node, n.NameRef) and _bare_seat_family_in_default(
            zone_index, node.name, node.ref_kind, id(node) in keyed
        ):
            bag.error(
                "the default of state variable " + cite_named(decl, f"'{decl.name}'") + f" "
                f"names `{node.name}` bare: a default is evaluated where it is "
                f"written, outside any player's turn, so the acting "
                f"player's `{node.name}` is no one's. Say whose: "
                f"`{node.name}[<player>]`",
                node.span or decl.span,
                code=Code.NO_PLAYER_ACTING,
            )
        elif isinstance(node, n.Choose):
            bag.error(
                "the default of state variable " + cite_named(decl, f"'{decl.name}'") + f" cannot "
                f"`choose`: a default is evaluated where it is written, "
                f"outside any player's turn, so there is no one to make "
                f"the decision — and a decision with no actor has no "
                f"information set to attach to. Move it into a phase",
                node.span or decl.span,
                code=Code.NO_PLAYER_ACTING,
            )
        elif isinstance(node, n.NameRef) and _pronoun_refused(
            node.name, node.ref_kind, _DEFAULT_REFUSED_PRONOUNS
        ):
            bag.error(
                "the default of state variable " + cite_named(decl, f"'{decl.name}'") + f" cannot "
                f"read `actor`: a default is evaluated where it is "
                f"written, outside any player's turn, so `actor` names "
                f"no one. Use a seat number, or set the variable during "
                f"play",
                node.span or decl.span,
                code=Code.NO_PLAYER_ACTING,
            )
        elif isinstance(node, n.Call):
            bag.error(
                "the default of state variable " + cite_named(decl, f"'{decl.name}'") + f" cannot "
                "call " + _cite_in(game, "function", node.func, f"'{node.func}'")
                + ": a default is evaluated while the "
                f"`state {{ }}` block is still being declared, and a "
                f"function body can reach a variable that does not "
                f"exist yet — use a literal here and compute the value "
                f"in the phase that needs it",
                node.span or decl.span,
                code=Code.OUT_OF_SCOPE,
            )
        elif isinstance(node, n.NameRef) and _state_out_of_scope(
            node.name, node.ref_kind, in_scope
        ):
            bag.error(
                "the default of state variable " + cite_named(decl, f"'{decl.name}'") + f" reads "
                f"'{node.name}', which is not declared yet: a default "
                f"can only read state declared before it — earlier in "
                f"the same `state {{ }}` block, or in an enclosing one",
                node.span or decl.span,
                code=Code.OUT_OF_SCOPE,
            )


def _check_state_scope(game: n.Game, bag: DiagnosticBag) -> None:
    """A state reference names a variable live at its lexical position.

    decisions.md "State scoping (lexical)": a variable is scoped to the phase
    that lexically encloses its declaration, reads from enclosing scopes are
    free, and writes follow the same rule — a phase may not touch a variable
    declared in a SIBLING or DESCENDANT scope, because that variable's owning
    phase may not be active. That section ends "This is statically checkable",
    and until this guard existed it was not checked: every out-of-scope
    reference passed the whole front end and died at playout on a bare
    `KeyError` out of `runtime/state.py`, with no span and no mention of the
    rule.

    `_check_state_default_scope` is the same traversal over the narrower
    declare-time question (what a `= <default>` may read, which is bounded by
    what exists *yet*). This one owns references in phase BODIES, where the
    whole block exists and only the frame stack bounds them. Their domains are
    disjoint by construction: `n.StateBlock` items are skipped here, so a bad
    default is reported once, by the guard whose rule actually decides it.

    Out of domain, deliberately: callable bodies — move types, rules,
    functions, procedures. They have no enclosing phase; a move type
    is declared once and offered from wherever a game offers it, so its
    legality is a reachability question, not a lexical one, and 112 callable
    bodies across the corpus legitimately read phase-scoped state (issue #242).
    `Turns.again` and `RequireDecl.name` are bare `str`s that never become a
    `NameRef` (issue #243); a result ranking's target (`winner:`, the Stop
    Result's ranking) is the third of that shape and is checked here directly,
    because its name is right there to read.
    """
    declared_at: dict[str, list[str]] = {}

    # Collect every declaration first, so a diagnostic can name a declaring
    # phase that appears LATER in the file than the reference it explains.
    def collect(phase: n.Phase) -> None:
        for name in sorted(_phase_state_names(phase)):
            declared_at.setdefault(name, []).append(phase.name)
        for item in phase.items:
            if isinstance(item, n.Phase):
                collect(item)

    for phase in game.phases:
        collect(phase)
    top = _game_state_names(game)

    for node, in_scope in _phase_scoped_names(game):
        if not _state_out_of_scope(node.name, node.ref_kind, in_scope):
            continue
        where = declared_at.get(node.name, [])
        # Name the declaring phase: "not in scope" alone sends the author
        # looking in the wrong place for a variable they can see on the page.
        home = " or ".join(f"phase '{w}'" for w in where) or "another scope"
        bag.error(
            f"state variable '{node.name}' is not in scope here: it is "
            f"declared in {home}, which does not enclose this reference, so "
            f"it does not exist while this runs. State is scoped to the phase "
            f"that declares it — move the declaration to a phase that encloses "
            f"both, or move this reference into {home}",
            node.span,
            code=Code.OUT_OF_SCOPE,
        )

    # A result ranking's target needs naming separately: `state_var` is a bare
    # `str` and never becomes a `NameRef` (issue #243), so the walk above cannot
    # see it. A name declared in no phase at all is `_validate_refs`'s unknown
    # variable; this refusal is for state that exists, in the wrong scope.
    for ranking in _result_rankings(game):
        target = ranking.state_var
        where = declared_at.get(target, []) if target is not None else []
        if target is not None and target not in top and where:
            home = " or ".join(f"phase '{w}'" for w in where)
            bag.error(ranking_slot(ranking).out_of_scope(target, home), ranking.span, code=Code.OUT_OF_SCOPE)


def _check_positional_index_range(game: n.Game, bag: DiagnosticBag) -> None:
    """A literal position in a collection whose length the sentence states is
    inside it. A position counts from 0 (the type layer refuses a negative or
    non-Integer one); past the last member, the read names nothing, and the
    runtime's positional Owner Guard (`evaluate._subscript`) would refuse it
    at play time instead of here. A computed position, or a collection whose
    length is runtime data, is that guard's alone."""
    for nd in _walk(game):
        past = _position_past_end(nd, game)
        if past is None:
            continue
        # A board region's position is `_BOARD_POSITION_GATE`'s test; spliced
        # from a library, `_check_library_clause_gates` has refused it first.
        assert isinstance(nd, n.Subscript)
        index, length = past
        bag.error(
            f"position {index} is past the end: this collection holds "
            f"{length}, at positions 0 .. {length - 1}",
            nd.index.span or nd.span,
            code=Code.OUT_OF_RANGE,
        )


def _check_chooses(game: n.Game, bag: DiagnosticBag) -> None:
    """Every integer `choose` must have a statically known, non-negative upper
    bound — the width the OpenSpiel action space reserves for it (decisions.md
    "The integer `choose` domain"). The bound comes from a literal upper range
    (`0 .. 13`) or an explicit `up to N` clause when the upper bound is a runtime
    expression; a runtime upper bound with no `up to` cannot be sized statically
    and is rejected here rather than papered over with a fixed constant (surface
    totality). `up to` on a literal upper bound is likewise rejected: the literal
    is already the exact ceiling, so an `up to` there is either contradictory (a
    ceiling below the literal makes the runtime range guard fail for every
    playout) or redundant (a ceiling above it mints action ids legal in no
    state) — never silently accepted. Finally, a literal lower bound above the
    ceiling (an inverted literal range like `5 .. 3`, or a literal `lo` past an
    `up to` ceiling) is rejected: the minimum candidate already exceeds every
    value the action space reserves, so no value can ever be chosen — a
    statically doomed program the runtime guard would otherwise only catch at
    playout. A literal lower bound below zero is refused the same way: the
    reserved block starts at 0, so its every value would lack an action id.

    The `excluding` clause is decided here where it is literal: an excluded
    value outside the static offerable interval — the literal `lo` (or 0, for
    a runtime `lo`) up to the ceiling — can never act, and a clause that never
    acts is accepted-but-ignored wearing a legal parse; an excluded value equal
    to a statically singleton interval always empties the choice ("No implicit
    actions"). A runtime exclusion is the runtime's to refuse when it empties
    the live range. Literal means a bare integer literal: no expression is
    folded, so `excluding 5 + 1` is runtime and acts or not at play time.

    One diagnostic per choose: the arms are ordered and the first that fires
    ends the node, so a broken range is reported without the exclusion
    diagnostics its bounds would also trip."""
    for node in _walk(game):
        if not isinstance(node, n.Choose):
            continue
        # `static_ceiling` is an `up to` INT (never negative), a literal `hi`
        # (negative through `- INT`), or None — a runtime `hi` with no `up to`.
        ceiling = n.static_ceiling(node)
        if ceiling is None:
            bag.error(
                "`choose integer` needs a statically known upper bound: either "
                "give it a literal upper bound (`0 .. 13`) or declare a ceiling "
                "with `up to N` (`0 .. hand_size up to 10`) — the OpenSpiel "
                "action space reserves that many ids up front",
                node.span,
                code=Code.CHOOSE_INTEGER_NEEDS_FIXED_CEILING,
            )
            continue
        if ceiling < 0:
            bag.error(
                f"`choose integer` upper bound ({ceiling}) is negative: values "
                f"start at 0, so the range reserves no action id and no value "
                f"can ever be chosen — raise the upper bound to 0 or more",
                node.span,
                code=Code.CHOICE_OFFERS_NO_CANDIDATE,
            )
            continue
        if node.ceiling is not None and isinstance(node.hi, n.IntLit):
            bag.error(
                f"`choose integer` has a literal upper bound ({node.hi.value}), "
                f"which is already its static ceiling — remove the `up to "
                f"{node.ceiling}` clause (it applies only when the upper bound is "
                f"a runtime expression)",
                node.span,
                code=Code.HAS_NO_EFFECT,
            )
            continue
        # A literal lower bound is the smallest value the choose could ever
        # offer; if it exceeds the ceiling, every candidate escapes the reserved
        # `0 .. ceiling` block (or the range is outright empty), so the choose
        # can never yield a value. `lo` scopes to a literal — a runtime `lo` is
        # not statically decidable and the runtime range guard covers it.
        if isinstance(node.lo, n.IntLit) and node.lo.value > ceiling:
            bag.error(
                f"`choose integer` lower bound ({node.lo.value}) exceeds its "
                f"ceiling ({ceiling}): the range is statically empty (or every "
                f"value would fall outside the reserved action block), so no "
                f"value can ever be chosen — lower the start or raise the bound",
                node.span,
                code=Code.CHOICE_OFFERS_NO_CANDIDATE,
            )
            continue
        if isinstance(node.lo, n.IntLit) and node.lo.value < 0:
            bag.error(
                f"`choose integer` lower bound ({node.lo.value}) is below the "
                f"reserved block: values start at 0, and every legal value must "
                f"have an OpenSpiel action id in 0 .. {ceiling} — raise the start",
                node.span,
                code=Code.OUT_OF_RANGE,
            )
            continue
        if isinstance(node.excluding, n.IntLit):
            low = node.lo.value if isinstance(node.lo, n.IntLit) else 0
            excluded = node.excluding.value
            if not low <= excluded <= ceiling:
                bag.error(
                    f"`choose integer` excludes {excluded}, which lies outside "
                    f"every value these bounds can offer ({low} .. {ceiling}), "
                    f"so the `excluding` clause can never act — remove it, or "
                    f"exclude a value in range",
                    node.excluding.span or node.span,
                    code=Code.HAS_NO_EFFECT,
                )
            elif low == ceiling:
                bag.error(
                    f"`choose integer` excludes {excluded}, the only value it "
                    f"can offer ({low} .. {ceiling}), so the `excluding` clause "
                    f"would always empty the choice — a choice must offer at "
                    f"least one candidate",
                    node.excluding.span or node.span,
                    code=Code.CHOICE_OFFERS_NO_CANDIDATE,
                )


def _check_actor_alias_comparisons(game: n.Game, bag: DiagnosticBag) -> None:
    """A comparison between two names that provably denote the same acting
    player is dead code, and is refused here.

    `for each player p:` binds the acting player to `p` for its body (the
    `binds_actor` column of the domain registry), and the `actor` pronoun reads
    the acting player — so `p is actor` is true for every `p`, and `p is not
    actor` guards a body that never runs. Both operands are `Player`, so no
    guard in the type layer can see it (`typecheck`'s always-false Owner Guard
    compares TYPES, and these agree); and a branch that is never taken cannot
    fail at runtime either. That leaves it silently accepted, which for a
    designer tool is the worst outcome — "an operand comparing as
    always-false", decisions.md "Surface totality".

    The class is the aliasing, not the `for each` spelling, so this sweeps
    every construct that binds a seat AND rebinds the acting player to it
    (`for each` over a `binds_actor` role, `turns`, `each … simultaneously`,
    `as <name>`), plus the transitive `let me = actor`. The innermost rebind
    wins: inside a nested `as`/seat loop the outer binder no longer denotes
    the acting player, so the corpus idiom — capture the outer actor ABOVE the
    loop (`let w = actor`), compare against `w` inside — stays legal, which is
    the whole point of hoisting it.

    Runs after `_classify_names`, so it reads the `ref_kind` the resolver
    stamped rather than re-deciding what a name is.

    One walk from the game root, rather than a list of the declaration kinds
    that hold statements: an alias can only be established by a construct with
    an arm below, so every tree starts with the pronoun alone and a declaration
    form added later is swept without being enumerated here. (Each declaration
    body is nonetheless independent, which is the correct reading: the acting
    player inside a move effect or a rule body comes from the CALL site, so
    nothing lexically above it can have bound a second name to them.)"""
    _sweep_aliases(game, _ActorAliases(), game.content_flavor, bag)


def _sweep_aliases(
    node: object, aliases: _ActorAliases, flavor: Flavor, bag: DiagnosticBag
) -> None:
    """Walk `node`, threading the set of names that denote the acting player.

    Generic over the tree — a field walk driven by `_introduced_binders` and
    `_BINDER_SCOPE_FIELDS`, the same two registries lexical scoping already
    reads — with an arm per construct that rebinds the actor. A new binding
    construct therefore inherits correct shadowing for free, and only a
    construct that binds a SEAT needs an arm here."""
    if isinstance(node, n.BinOp):
        _check_alias_operands(node, aliases, bag)
    rebound = _seat_rebinding(node)
    match node:
        case n.ForEach() | n.EachSimultaneous() if rebound is not None:
            # A SEAT role: the body's acting player IS the binder.
            _sweep_aliases(node.body, rebound, flavor, bag)
            return
        case n.Turns() if rebound is not None:
            # leader/participants/termination evaluate OUTSIDE the turn, in the
            # enclosing scope — the binder does not exist there yet.
            for outer in (node.leader, node.participants, node.until):
                _sweep_aliases(outer, aliases, flavor, bag)
            _sweep_stmt_seq(node.body, rebound, flavor, bag)
            return
        case n.AsBlock() if rebound is not None:
            # The player expression is evaluated in the OUTER context, so it
            # sees the enclosing aliases; the body sees a new acting player.
            _sweep_aliases(node.player, aliases, flavor, bag)
            _sweep_stmt_seq(node.body, rebound, flavor, bag)
            return
        case n.LetStmt():
            # The value is evaluated in the ENCLOSING scope, before the name is
            # bound — so it sees the aliases as they stand, and `let p = p`
            # reads the old `p`. (Rebinding the name for the statements that
            # FOLLOW is `_sweep_stmt_seq`'s half of the rule.) An index binder
            # scopes to this value and nowhere else.
            index = (node.index,) if node.index is not None else ()
            _sweep_aliases(node.value, aliases.shadowed(index), flavor, bag)
            return
        case _:
            pass
    if isinstance(node, tuple) and any(_is_stmt(item) for item in node):
        _sweep_stmt_seq(node, aliases, flavor, bag)
        return
    if isinstance(node, (list, tuple)):
        for item in node:
            _sweep_aliases(item, aliases, flavor, bag)
        return
    if is_dataclass(node) and not isinstance(node, type):
        introduced = _introduced_binders(node, flavor)
        scope_fields = _BINDER_SCOPE_FIELDS.get(type(node))
        for f in fields(node):
            # `_BINDER_SCOPE_FIELDS` is not the whole scoping story: `_rewrite`
            # scopes some binder-introducing kinds itself and so leaves them out
            # of the table (a `produces:` arm's payload binders). Absent an entry, shadow the node's binders in
            # EVERY field — the safe direction, since over-shadowing can only
            # miss a degenerate comparison, while under-shadowing REFUSES a
            # sound one (`for each player p: … produces: won(p) { p is actor }`,
            # where the arm's `p` is the payload, not the acting player).
            shadowed = scope_fields is None or f.name in scope_fields
            inner = aliases.shadowed(introduced) if shadowed else aliases
            _sweep_aliases(getattr(node, f.name), inner, flavor, bag)


def _sweep_stmt_seq(
    stmts: tuple[object, ...], aliases: _ActorAliases, flavor: Flavor, bag: DiagnosticBag
) -> None:
    """A statement tuple, with `let` threading forward exactly as the runtime
    threads `ctx.locals` through a body: `let me = actor` (or `let me = p`,
    where `p` already denotes the actor) makes `me` a further name for the
    same player, for the statements that follow it (`_aliases_after_let`).
    This is the same "initializer runs in the enclosing scope" rule
    `as`'s player expression and `turns`' leader already follow; `let` needs it
    spelled out here because its name scopes forward to later siblings rather
    than to a field of its own node, which is why `_introduced_binders` and the
    generic walk do not reach it."""
    for stmt in stmts:
        _sweep_aliases(stmt, aliases, flavor, bag)
        if isinstance(stmt, n.LetStmt):
            aliases = _aliases_after_let(stmt, aliases)


def _is_stmt(node: object) -> bool:
    return isinstance(node, get_args(n.Stmt))


def _check_alias_operands(
    node: n.BinOp, aliases: _ActorAliases, bag: DiagnosticBag
) -> None:
    """Refuse `<alias> is <alias>` / `<alias> is not <alias>`: both operands
    name the acting player, so the comparison is a constant."""
    if node.op not in ("is", "is_not"):
        return
    left, right = node.left, node.right
    if not (isinstance(left, n.NameRef) and isinstance(right, n.NameRef)):
        return
    if not all(
        ref.name in aliases.names and ref.ref_kind in ("local", "pronoun")
        for ref in (left, right)
    ):
        return
    word = "is" if node.op == "is" else "is not"
    verdict = "always true" if node.op == "is" else "never true"
    where = (
        f"{aliases.origin} binds the acting player, so "
        if aliases.origin is not None
        else ""
    )
    bag.error(
        f"`{left.name} {word} {right.name}` is {verdict}: {where}"
        f"`{left.name}` and `{right.name}` are the same player here. "
        f"To compare against a DIFFERENT player, bind them outside the "
        f"construct that rebinds the acting player (`let w = actor` above the "
        f"loop, then `{left.name} is not w`); to act as one named player, use "
        f"`as <player> {{ … }}`.",
        node.span,
        code=Code.CONSTANT_CONDITION,
    )


def _check_delegation(game: n.Game, bag: DiagnosticBag) -> None:
    """The Delegated Play helpers' two Owner Guards (decisions.md "Delegated
    play"; the grid is tests/test_delegated_play.py):

    - a helper of the exact name must take exactly one Player — the routing
      contract is per-seat, and any other shape is a mis-remembered API;
    - a game defining a helper must hold a trick round somewhere for it to
      route — helpers no site consults are accepted-but-ignored, the defect
      class this repo ranks worst.

    The unrouted pool, a trick round's DECLARED source, is one of the implicit
    decision pools, whose Owner Guard is `_check_implicit_pools`. The routed
    pool's guard — the DECIDER must see it — is deliberately NOT
    here: whether a seat's pool is routed, and to whom the decision goes,
    are the helpers' values at that seat, and correlating two opaque
    expression bodies is not statically decidable (Bridge's own helper
    routes undelegated seats to their private hands, legally). The precise
    check is the runtime Owner Guard at the draw (`runtime/mechanics.py`),
    fired whenever either helper routes.
    """
    from cardlang.runtime.delegation import HELPER_NAMES

    helpers = [f for f in game.functions if f.name in HELPER_NAMES]
    if not helpers:
        return
    for fn in helpers:
        if len(fn.params) != 1 or fn.params[0].type_name != "Player":
            got = ", ".join(f"{q.name} : {q.type_name}" for q in fn.params) or "none"
            bag.error(
                f"" + cite_named(fn, f"'{fn.name}'") + f" is a Delegated Play helper and must take exactly "
                f"one Player parameter (the seat whose move is routed); it "
                f"takes ({got})",
                fn.span,
                code=Code.WRONG_SIGNATURE,
            )
    if not any(isinstance(node, n.TrickRound) for node in _walk(game)):
        names = Sentence.join(
            ", ", (cite_named(f, f.name) for f in sorted(helpers, key=lambda h: h.name))
        )
        origin = helpers[0].origin
        bag.error(
            "this game defines " + names + " but holds no trick round for the "
            f"routing to reach — the helpers would be silently ignored "
            f"(routing at other decision points is issue #458)",
            helpers[0].span,
            for_game=None if origin is None else (
                cite_origin(origin, helpers[0].span) + f" routes a trick "
                f"round's card decision, but this game holds no trick round for "
                f"the routing to reach — a game with no trick round cannot use "
                + cite_library(origin.library, helpers[0].span)
            ),
            code=Code.UNUSED_DECLARATION,
        )


def _offered_move_types(node: object) -> frozenset[str]:
    """Every move type an `offer` under `node` presents —
    the `move_type`-namespace slot of `_REFERENCE_SLOTS`, the only
    constructs that present a game's own move type to a deciding seat. A
    procedure body and a move type's effect are under the game, so an offer
    made from either counts."""
    offered: set[str] = set()
    for nd in _walk(node):
        if isinstance(nd, n.Offer):
            offered.update(nd.offering)
    return frozenset(offered)


def _check_climb_play_zones(game: n.Game, bag: DiagnosticBag) -> None:
    """A climbing round plays into a zone every seat sees the cards of.

    The Owner Guard for the standing play's visibility: each seat's offer is
    judged against the play standing in the round's play zone, so a zone whose
    type hides its cards from some seat (`stdlib.zones.identity_to_all`) offers
    that seat plays judged against cards it cannot see."""
    zone_types = {z.name: z.type_ref.name for z in game.zones}
    for node in _walk(game):
        if not isinstance(node, n.ClimbRound):
            continue
        ztype = zone_types.get(node.play_zone)
        if ztype is None or ztype not in ZONE_PROJECTIONS or identity_to_all(ztype):
            continue
        bag.error(
            f"a climb round plays into `{node.play_zone}`, a `{ztype}`, which "
            f"hides its cards from some seat — every seat's play is judged "
            f"against the play standing there, so every seat sees it. Declare "
            f"`{node.play_zone}` a type that shows every seat its cards "
            f"(`TrickPile`)",
            node.span,
            code=Code.WRONG_ZONE_VISIBILITY,
        )


def _check_implicit_pools(game: n.Game, bag: DiagnosticBag) -> None:
    """Every implicit decision pool shows its decider the cards in it.

    The Owner Guard for the pools the kernel builds from a declared zone with
    no designer expression to read (`DECISION_POOLS`' round-source and
    `Card`-parameter rows): a round's source family, whose instance the acting
    seat plays from, and the acting seat's `hand`, whose cards a `Card`
    parameter of an offered move type ranges over. The decider is the owning
    seat in both, so the family's type must show its owner the cards
    (`stdlib.zones.reveals` at `identity`); a type that does not offers a seat
    cards it cannot see, a game nobody can play, known from the declaration.
    A pool a designer expression names is `_check_hidden_reads`'. Under
    Delegated Play a trick's routed pool is judged per decision by the runtime
    Owner Guard `delegation.check_decider_sees`. A library move type's
    `Card` parameter over a `hand` the game declares carries the sentence the
    game's author reads (`attribution`)."""
    zone_types = {z.name: z.type_ref.name for z in game.zones}
    move_types = {m.name: m for m in game.move_types}

    def hidden_from_owner(family: str) -> str | None:
        ztype = zone_types.get(family)
        if ztype is None or ztype not in ZONE_PROJECTIONS or reveals(ztype, "identity", True):
            return None
        return ztype

    def fix(family: str, opens: bool = False) -> str:
        return (
            f"{'D' if opens else 'd'}eclare `{family}` a type that shows its "
            f"owner the cards in it (`Hand`, or `PublicHand`)"
        )

    for node in _walk(game):
        match node:
            case n.TrickRound() | n.ClimbRound():
                ztype = hidden_from_owner(node.source_zone)
                if ztype is not None:
                    form = "trick" if isinstance(node, n.TrickRound) else "climb"
                    bag.error(
                        f"a {form} round offers each seat the cards of its own "
                        f"`{node.source_zone}`, but `{node.source_zone}` is a "
                        f"`{ztype}`, which {_OWN_POOL_BLIND}. {fix(node.source_zone, opens=True)}",
                        node.span,
                        code=Code.WRONG_ZONE_VISIBILITY,
                    )
    family = CARD_PARAMETER_FAMILY
    offers = [nd for nd in _walk(game) if isinstance(nd, n.Offer) and nd.span is not None]
    for name in sorted(_offered_move_types(game)):
        mt = move_types.get(name)
        if mt is None:
            continue
        # The offer written in another file than the move type: the library
        # text a game's move type is offered by.
        offered_by = tuple(
            o.span for o in offers
            if name in o.offering and o.span is not None and mt.span is not None
            and o.span.source_name != mt.span.source_name
        )
        for param in mt.params:
            if param.type_name != "Card":
                continue
            ztype = hidden_from_owner(family)
            if ztype is None:
                continue
            bag.error(
                f"move type " + cite_named(mt, f"`{mt.name}`") + f"'s `{param.name} : Card` offers the "
                f"acting seat the cards of its own `{family}`, but `{family}` is a "
                f"`{ztype}`, which {_OWN_POOL_BLIND}. {fix(family, opens=True)}",
                param.span or mt.span,
                for_game=None if mt.origin is None else (
                    cite_origin(mt.origin, param.span or mt.span) + f" takes "
                    f"`{param.name} : Card`, which offers the acting seat the "
                    f"cards of its own `{family}`, but this game declares "
                    f"`{family}` a `{ztype}`, which {_OWN_POOL_BLIND} — {fix(family)}"
                ),
                stands_on=offered_by,
                code=Code.WRONG_ZONE_VISIBILITY,
            )


_OWN_POOL_BLIND = (
    "does not show its owner the cards in it, so a seat would pick cards it "
    "cannot see"
)


# The zone reference slots, by what the slot's name must denote: a source is
# the family each acting seat plays from (keyed by that seat), a play slot the
# one pile every play lands on.
_SOURCE_SLOT_FIELD = "source_zone"
_PLAY_SLOT_FIELD = "play_zone"
_ZONE_SLOTS: tuple[tuple[type, str], ...] = tuple(
    k for k, v in _REFERENCE_SLOTS.items() if v == "zone"
)
assert {f for _, f in _ZONE_SLOTS} == {_SOURCE_SLOT_FIELD, _PLAY_SLOT_FIELD}, (
    "a new zone reference slot: decide which zones its name may denote"
)


_FUNCTION_TAKES_A_CARD = (
    "keep the filter in the rule and have the function take a card: "
    "`cards in hand where follows(card, state.led_suit)`"
)


def _contracted_answer_on(
    key: tuple[str, str],
    reached: dict[tuple[str, str], tuple[object, tuple[str, str] | None]],
    roots: tuple[n.Expr, ...],
) -> n.ContractStamp | None:
    """The row a library's call of the game's answer carries (`Call.contract`)
    on the chain `_definition_closure` reached `key` by from `roots`: the
    stamp on the call that crosses into the answer, so the library named is
    the one whose text makes that call."""
    chain: list[tuple[str, str]] = []
    at: tuple[str, str] | None = key
    while at is not None and at in reached:
        chain.append(at)
        at = reached[at][1]
    callers: list[object] = [reached[callee][0] for callee in chain[1:]] + [roots]
    for (_ns, name), caller in zip(chain, callers):
        for nd in _child_nodes(caller):
            if isinstance(nd, n.Call) and nd.func == name and nd.contract is not None:
                return nd.contract
    return None


def _rule_clauses(rule: n.RuleDef) -> tuple[n.Expr, ...]:
    """The expressions a rule's clauses hold, in clause order."""
    exprs = (
        rule.applies_when.pred if rule.applies_when else None,
        rule.demands.expr if rule.demands else None,
        rule.if_impossible,
        rule.exempts,
    )
    return tuple(e for e in exprs if e is not None)


def _check_play_source(
    game: n.Game, own_rules: frozenset[str], bag: DiagnosticBag
) -> None:
    """A rule clause's bare `hand` is the Play Source (`ref_kind ==
    "play_source"`, stamped by `_rewrite`), and three sentences would give
    that one word a second reading; each is refused where the designer wrote
    it, with its fix.

    - A zone named `hand` that is not a family kept per player, or a state
      variable named `hand`: the rule could never read it by that name.
    - A game that runs no trick round, for a rule no phase activates: a rule
      is asked only at a trick round's card decision, so it would never apply.
      A climbing round binds no rule. An activated rule is refused at its
      activation (`_check_rules_reach_a_trick`).
    - A function a rule clause reaches, transitively, reading bare `hand` or
      a trick round's source family, whether or not the clauses themselves
      read `hand`: a function body runs in its own scope, where the Play
      Source does not exist. `runtime/evaluate`'s `_hermetic_ctx` keeps no
      Play Source as the Shadow Guard behind it.

    Runs after `_classify_names` and reads the stamp, never the spelling,
    for the clauses themselves."""
    reading = [
        r for r in game.rules
        if any(
            isinstance(nd, n.NameRef) and nd.ref_kind == "play_source"
            for nd in _walk(r)
        )
    ]
    sources = {
        nd.source_zone for nd in _walk(game) if isinstance(nd, n.TrickRound)
    }
    named = frozenset({PLAY_SOURCE_NAME}) | frozenset(sources)
    functions: dict[str, object] = {f.name: f for f in game.functions}
    reported: set[int] = set()
    for rule in game.rules:
        reached = _definition_closure(list(_rule_clauses(rule)), {"function": functions})
        for (_ns, fname), (fn, _via) in sorted(reached.items(), key=lambda kv: kv[0]):
            assert isinstance(fn, n.FunctionDef)
            subscripted = {id(nd.obj) for nd in _walk(fn) if isinstance(nd, n.Subscript)}
            answer = (
                None if rule.name in own_rules
                else _contracted_answer_on(("function", fname), reached, _rule_clauses(rule))
            )
            remedy = (
                _FUNCTION_TAKES_A_CARD if answer is None
                else (
                    cite_library(answer.library, answer.row_span)
                    + f" calls it under its contract "
                    f"" + cite_where(f"`{answer.row}`", answer.row_span) + f", from text this game cannot edit, so the "
                    f"filter cannot move into the rule: read the card the row "
                    f"passes, or the game's own state"
                )
            )
            entry = (
                _library_entry(_closure_steps(("function", fname), reached, _rule_clauses(rule)))
                if rule.origin is None
                else None
            )
            for nd in _walk(fn.body):
                if (
                    isinstance(nd, n.NameRef)
                    and nd.name in named
                    and nd.ref_kind in ("zone", None)
                    and id(nd) not in subscripted
                    and id(nd) not in reported
                ):
                    reported.add(id(nd))
                    # The read names provided state where a library provides
                    # the name.
                    provided_as = next(
                        (d for d in (game.state.decls if game.state is not None else ())
                         if d.name == nd.name and d.origin is not None),
                        None,
                    )
                    read: Said = (
                        f"`{nd.name}`" if provided_as is None
                        else cite_named(provided_as, f"`{nd.name}`")
                    )
                    message = (
                        "function " + cite_named(fn, f"'{fname}'")
                        + " reads " + read + ", and rule "
                        + cite_named(rule, f"'{rule.name}'") + " calls it from its clauses: "
                        f"{_PLAY_SOURCE_READING}, and a function cannot see "
                        f"which cards those are — " + remedy
                    )
                    if entry is None:
                        # A library's rule calling a library function: the
                        # game's round decides what the read names.
                        origin = rule.origin
                        bag.error(
                            message,
                            nd.span,
                            for_game=None if origin is None else (
                                cite_origin(origin, rule.span) + " calls function "
                                + cite_named(fn, f"`{fname}`") + " from its clauses, which reads "
                                + read + ", the cards this game's trick round "
                                f"plays from, and a function cannot see which cards "
                                f"those are — take " + cite_named(rule, f"'{rule.name}'") + f" out of `active_rules:`"
                            ),
                            code=Code.READS_BEYOND_PARAMETERS,
                        )
                        continue
                    inner: Said = (
                        ", then function " + cite_named(fn, f"`{fname}`")
                        if fname != entry.name else ""
                    )
                    bag.error(
                        message,
                        nd.span,
                        route=_entry_route("call", entry, rule.span),
                        for_game=(
                            f"rule " + cite_named(rule, f"'{rule.name}'") + " calls " + entry.through
                            + inner + " from its clauses, which reads " + read
                            + f": {_PLAY_SOURCE_READING}, "
                            f"and a function cannot see which cards those are — "
                            + cite_where(f"`{entry.name}`", entry.definition) + " is "
                            + cite_library(entry.origin.library, entry.definition)
                            + "'s, so "
                            f"write the filter in the rule's own clause "
                            f"(`cards in {nd.name} where ...`) instead of calling it"
                        ),
                        code=Code.READS_BEYOND_PARAMETERS,
                    )
    if not reading:
        return
    for z in game.zones:
        if z.name == PLAY_SOURCE_NAME and not (
            z.index is not None and role_of(z.index) is Role.PLAYER
        ):
            bag.error(
                f"this game declares the zone `{z.name}` "
                f"({_family_shape(z.index)}), but {_PLAY_SOURCE_READING}, so "
                f"its rules could never read this zone by that name — rename "
                f"the zone",
                z.span,
                code=Code.RESERVED_WORD,
            )
    for nd in _walk(game):
        if isinstance(nd, n.StateDecl) and nd.name == PLAY_SOURCE_NAME:
            rules = Sentence.join(" and ", (cite_named(r, f"'{r.name}'") for r in reading))
            variable = cite_named(nd, f"`{nd.name}`")
            bag.error(
                "this game declares the state variable " + variable + ", but "
                f"{_PLAY_SOURCE_READING}, so its rules could never read this "
                f"variable by that name — rename the variable",
                nd.span,
                for_game=None if nd.origin is None else (
                    cite_library(nd.origin.library, nd.span) + " provides the state variable "
                    + variable + ", but this game asks rule " + rules + ", and "
                    f"{_PLAY_SOURCE_READING}, so no rule could read the variable "
                    f"by that name — take " + rules + " out of `active_rules:`"
                ),
                code=Code.RESERVED_WORD,
            )
    if not sources:
        activated = _activated_rule_names(game)
        for rule in reading:
            # Shadows `_check_rules_reach_a_trick`, the Owner Guard of an
            # activation no trick round asks, which refuses every activating
            # phase of a game with no trick round at the activation itself. A
            # library's rule is spliced in only when activated, so what is left
            # is a rule of the game's own that no phase activates.
            if rule.name in activated:
                continue
            bag.error(
                "rule " + cite_named(rule, f"'{rule.name}'")
                + f" reads `{PLAY_SOURCE_NAME}`, the cards the "
                f"player on turn plays to a trick, but this game plays no trick "
                f"round (`round <move> from ... source ... into ...`); a rule is "
                f"asked only when a trick round offers a card, so it would "
                f"never apply — play the hand with a trick round, or delete rule "
                + cite_named(rule, f"'{rule.name}'"),
                rule.span,
                code=Code.GAME_RULE_NEVER_CONSULTED,
            )


def _check_bare_family_refs(game: n.Game, bag: DiagnosticBag) -> None:
    """Wherever the engine resolves a zone family by the acting SEAT, the family
    must be indexed by player: a bare family name (`hand`) is the acting
    player's own instance, and that reading exists only for the role whose
    members are seats. Three kinds of site key a family so: a bare zone
    `NameRef` (classified, so a binder shadowing the family name is exempt), a
    round's `source` slot, and a Builtin that reads a family by name and hands
    its keys back as seats (`BUILTIN_IMPLICIT_READS`). A round's `into` slot
    names one pile, so it must be a single zone. `to each <family>` names the
    family whole and keeps its own Owner Guard (`_validate_refs`). A Builtin
    reading a family the game does not declare at all is refused the same
    way, since it has no seat to hand back. A Builtin a library calls reads a
    family no argument names, so its refusal carries the sentence the game's
    author reads (`attribution`), unless the library's own contract names the
    family, which makes the refusal the library's.

    The runtime refusals in `evaluate._name`, `mechanics` (round sources and
    play piles) and `reads.magic_hand` are the Shadow Guards behind this Owner
    Guard."""
    index_of = {z.name: z.index for z in game.zones}

    def seat_keyed(name: str) -> bool:
        index = index_of[name]
        return index is not None and role_of(index) is Role.PLAYER

    keyed = _keyed_ids(game)
    origins = n.library_origins(game)
    for nd in _walk(game):
        index = index_of.get(nd.name) if isinstance(nd, n.NameRef) else None
        if (
            isinstance(nd, n.NameRef)
            and index is not None
            and _bare_family_refused(index_of, nd.name, nd.ref_kind, id(nd) in keyed)
        ):
            team = (
                " (`team_of(<player>)` is a player's team)"
                if role_of(index) is Role.TEAM
                else ""
            )
            bag.error(
                f"`{nd.name}` is one zone per {index}, so a bare `{nd.name}` "
                f"names none of them: say which {index}'s, "
                f"`{nd.name}[<{index}>]`{team}",
                nd.span,
                code=Code.WRONG_SUBSCRIPT,
            )
        for cls, field in _ZONE_SLOTS:
            if not isinstance(nd, cls):
                continue
            name = getattr(nd, field)
            span: Span | None = getattr(nd, "span")
            if name not in index_of:
                continue  # unknown zone: `_validate_refs` reports it
            if field == _SOURCE_SLOT_FIELD and not seat_keyed(name):
                bag.error(
                    f"a round's `source` names the zone each player plays "
                    f"from, so it must be a zone kept per player, like "
                    f"`hand[player]` -- `{name}` is "
                    f"{_family_shape(index_of[name])}",
                    span,
                    code=Code.WRONG_ZONE_SHAPE,
                )
            elif field == _PLAY_SLOT_FIELD and index_of[name] is not None:
                bag.error(
                    f"a round's `into` names the one pile every play lands "
                    f"on, so it must be a single zone, like `trick_pile` -- "
                    f"`{name}` is {_family_shape(index_of[name])}",
                    span,
                    code=Code.WRONG_ZONE_SHAPE,
                )
        if isinstance(nd, n.Call) and nd.func in BUILTIN_IMPLICIT_READS:
            family, _need = BUILTIN_IMPLICIT_READS[nd.func]
            if family in index_of and seat_keyed(family):
                continue
            origin = origins.get(id(nd))
            searches = (
                f"`{nd.func}` finds the player holding a card by searching "
                f"`{family}[player]`"
            )
            declared = (
                f"declares no `{family}`"
                if family not in index_of
                else f"declares `{family}` as {_family_shape(index_of[family])}"
            )
            kept = f"`{family}[player] : Hand<player>`"
            if origin is not None and family in origin.contracted_zones:
                # The contract fixes `hand`, so no game meeting it can answer
                # the call: the library's fact, told where it wrote the call.
                bag.error(
                    cite_library(origin.library, nd.span) + f" calls {searches}, but "
                    + cite_library(origin.library, None) + f"'s contract names "
                    f"`{family}` as {_family_shape(index_of[family])}, so no game "
                    f"meeting it can answer the call — contract `{family}` per "
                    f"player, like {kept}",
                    nd.span,
                    code=Code.WRONG_ZONE_SHAPE,
                )
                continue
            bag.error(
                f"{searches}, so `{family}` must be a zone kept per player -- "
                + (
                    f"this game declares none"
                    if family not in index_of
                    else f"this game declares it as {_family_shape(index_of[family])}"
                ),
                nd.span,
                for_game=None if origin is None else (
                    cite_origin(origin, nd.span) + f" calls {searches}, but this "
                    f"game {declared} — declare `{family}` a zone kept per "
                    f"player, like {kept}"
                ),
                code=Code.WRONG_ZONE_SHAPE,
            )


def _inner_ring_sharing(
    body: object, flag: str, procedures: Mapping[str, n.ProcedureDef], running: frozenset[str]
) -> n.Turns | None:
    """The first `turns` inside `body` -- written there, or in a procedure it
    runs, which expands in place -- that names `flag` as its go-again flag."""
    for node in _child_nodes(body):
        if isinstance(node, n.Turns) and node.again == flag:
            return node
        if isinstance(node, n.RunStmt) and node.name not in running:
            proc = procedures.get(node.name)
            if proc is not None:
                found = _inner_ring_sharing(proc.body, flag, procedures, running | {node.name})
                if found is not None:
                    return found
    return None


def _check_nested_ring_flags(game: n.Game, bag: DiagnosticBag) -> None:
    """A `turns` ring holding another that names the same go-again flag: a
    write to the flag would keep the inner turn and the outer one at once,
    and the ring that exits first consumes it for both."""
    procedures = {p.name: p for p in game.procedures}
    for ring in _walk(game):
        if not isinstance(ring, n.Turns) or ring.again is None:
            continue
        inner = _inner_ring_sharing(ring.body, ring.again, procedures, frozenset())
        if inner is not None:
            bag.error(
                f"a ring inside this ring names the same go-again flag "
                f"`{ring.again}`, so a write to it would keep the inner turn and "
                f"the outer one at once — give the inner ring its own go-again "
                f"flag",
                inner.span or ring.span,
                code=Code.NAME_TAKEN,
            )


def _check_kernel_answers(game: n.Game, bag: DiagnosticBag) -> set[str]:
    """A game function answering a [[kernel-definition-contract]] takes the
    row's parameter: exactly one Card, the card the kernel asks about. Its
    result is typecheck's, against the row (`typecheck._check_kernel_answers`).
    A lowered answer takes `card : Card` by construction. Returns the clauses
    of the answers it refused, which `_check_unread_clauses` then leaves to
    this refusal."""
    refused: set[str] = set()
    for answer in K.answers(game):
        if answer.spelled_as is not None:
            continue
        params = tuple(p.type_name for p in answer.params)
        if params == ("Card",):
            continue
        row = K.CONTRACTS[answer.name]
        bag.error(
            f"function " + cite_named(answer, f"`{answer.name}`") + f" answers the "
            f"kernel's `{row.spelled}`, so it takes exactly one Card — write "
            f"`function {answer.name}(card : Card) = …`",
            answer.span or game.span,
            code=Code.WRONG_SIGNATURE,
        )
        refused.add("card_points" if answer.name == "card_points" else "trick_order")
    return refused


class _ErrorSink(Protocol):
    def error(self, message: Said, span: Span | None, *, code: Code) -> None: ...


@dataclass(frozen=True)
class _RouteSink:
    """A walk's refusals of library text it reached through a crossing, each
    carrying that crossing for `attribution` to tell."""

    bag: DiagnosticBag
    route: Route

    def error(self, message: Said, span: Span | None, *, code: Code) -> None:
        self.bag.error(message, span, route=self.route, code=code)


@dataclass(frozen=True)
class _AnswerVoice:
    """How a refusal names a Kernel Definition Contract's answer: in the
    spelling the designer wrote. The `card_points { }` table speaks as the
    table, and a written function as itself."""

    answer: n.FunctionDef

    def subject(self) -> Said:
        if self.answer.spelled_as is None:
            return "function " + cite_named(self.answer, f"`{self.answer.name}`")
        return cite_named(self.answer, "`card_points { }`")

    @property
    def name(self) -> str:
        return self.answer.name

    def named(self) -> Said:
        """The answer's name, cited, in a sentence that already named it."""
        return cite_named(self.answer, f"`{self.answer.name}`")


def _answer_routes(
    answer: n.FunctionDef, fns: dict[str, n.FunctionDef]
) -> dict[str, list[tuple[Span | None, object]]]:
    """Each function an answer reaches, with the route it is first reached
    by: every function the route enters, from the answer's own call, with the
    call that enters it (`_library_entry`'s steps). Another answer is not
    entered: it is checked on its own, and the reference order owns the call."""
    routes: dict[str, list[tuple[Span | None, object]]] = {}
    frontier: list[tuple[object, list[tuple[Span | None, object]]]] = [(answer.body, [])]
    while frontier:
        container, steps = frontier.pop(0)
        for nd in _walk(container):
            if isinstance(nd, n.Call) and nd.func in fns and nd.func not in routes:
                route = steps + [(nd.span, fns[nd.func])]
                routes[nd.func] = route
                frontier.append((fns[nd.func].body, route))
    return routes


def _check_answer_hermeticity(game: n.Game, bag: DiagnosticBag) -> set[str]:
    """Every answer to a [[kernel-definition-contract]] is HERMETIC: a pure
    function of the card and public state. Returns the clauses
    (`trick_order`, `card_points`) whose answers it refused.

    The Owner Guard for that property, and the reason the facts can be trusted
    at all. An answer is asked from several places under different live frames
    — the legality filter (mid-decision, an actor bound), the winner slot (end
    of trick, a `winner` in scope), a hand-rolled body (any frame, or none) and
    the end-of-game card census (no phase standing) — so an answer depending on
    WHO was asking, or on how far the game had run, would give different facts
    to each. Every refusal below removes one way for that to happen:

    * no pronoun of any namespace (`_PRONOUNS`);
    * no `choose`, so an answer is a fact and never a decision site (an
      info-set leak: a decision inside a legality computation);
    * only zones that project identity to EVERY observer, and never a bare
      per-player family, so an answer cannot read a card some observer
      cannot see;
    * only the game's own `state { }`, never a phase's, since the kernel reads
      an answer where no phase frame stands;
    * only the allowed Builtins (`TRICK_ORDER_ROW_CALLS`), no Primitive, and
      among the Trick Order's answers only those BEFORE it in the reference
      order (`kernel_contracts.TRICK_ORDER_CONTRACTS`), so an answer cannot
      reach the order it helps define.

    Each refusal follows the call graph, so an answer that reaches the
    forbidden thing THROUGH a designer function is refused with the function
    named — hermeticity is a property of what an answer can reach, not of its
    own text. A call-site pronoun reached through a designer function is
    `_check_functions`' to refuse, at that function."""
    refused: set[str] = set()
    answers = list(K.answers(game))
    if not answers:
        return refused
    answer_names = {a.name for a in answers}
    fns = {f.name: f for f in game.functions if f.name not in answer_names}
    points = K.answer(game, "card_points")
    # The zone references that carry a subscript (`won[0]`). A family read is
    # BARE — the acting player's instance, which an answer does not have —
    # only when it is not one of these; identity, because two reads of the
    # same zone are distinct nodes and only one of them may be subscripted.
    subscripted = {
        id(nd.obj)
        for nd in _walk(game)
        if isinstance(nd, n.Subscript) and isinstance(nd.obj, n.NameRef)
    }
    phase_local = phase_local_state_names(game)
    for answer in answers:
        voice = _AnswerVoice(answer)
        before = len(bag.items)
        # A Trick Order answer's reach runs on through `card_points`, which it
        # may call and which may call any of the three: there the reference
        # order still binds it. Everything else in `card_points`' reach is
        # that answer's own to refuse, at itself.
        pool = (
            {**fns, points.name: points}
            if points is not None and answer.name in K.TRICK_ORDER_CONTRACTS
            else fns
        )
        routes = _answer_routes(answer, pool)
        through_points = {
            name
            for name, steps in routes.items()
            if any(d is points for _at, d in steps)
        }
        # (node, the function it was reached through, or None when direct)
        sites: list[tuple[object, str | None]] = [(nd, None) for nd in _walk(answer.body)]
        for name in routes:
            sites.extend((nd, name) for nd in _walk(pool[name].body))
        # A function reached through library text is the library's, sound
        # where the library calls it: the answer's call of it is what fails.
        entries = {
            name: entry
            for name, steps in routes.items()
            if (entry := _library_entry(steps)) is not None
        }

        def through(fn: str | None) -> Said:
            if not fn:
                return ""
            named = _cite_in(game, "function", fn, f"`{fn}`")
            entry = entries.get(fn)
            if entry is None:
                # A route back into the game's text names the library
                # definitions it crossed on the way.
                crossed = [
                    cite_origin(origin, getattr(d, "span", None))
                    for _at, d in routes.get(fn, [])[:-1]
                    if (origin := getattr(d, "origin", None)) is not None
                ]
                if crossed:
                    return (
                        " through " + Sentence.join(", then ", crossed)
                        + ", then function " + named
                    )
                return " through function " + named
            inner: Said = ", then function " + named if fn != entry.name else ""
            return " through " + entry.through + inner

        def sink(fn: str | None) -> _ErrorSink:
            entry = entries.get(fn) if fn else None
            return bag if entry is None else _RouteSink(bag, _entry_route("row", entry, answer.span))

        for nd, fn in sites:
            out = sink(fn)
            if fn in through_points and not (
                isinstance(nd, n.Call) and nd.func in K.KERNEL_CONTRACT_NAMES
            ):
                continue
            if isinstance(nd, n.NameRef) and nd.ref_kind == "pronoun":
                if fn is not None and nd.name in _CALL_SITE_PRONOUNS:
                    continue
                reason = (
                    " — the kernel asks " + voice.named() + f" from the legality "
                    f"filter, the trick's winner, a hand-rolled body and the "
                    f"end-of-game census under different live frames, so it may "
                    f"read no pronoun ({', '.join(sorted(_PRONOUNS))}); it is a "
                    f"fact of the card and public state alone"
                )
                out.error(
                    voice.subject() + f" reads the pronoun '{nd.name}'"
                    + through(fn) + reason,
                    nd.span or answer.span,
                    code=Code.TRICK_ORDER_FUNCTION_READS_BEYOND_THE_CARD,
                )
            elif isinstance(nd, n.Choose):
                reason = (
                    " — " + voice.named() + f" is a fact the kernel reads, not a "
                    f"decision: it may not choose"
                )
                out.error(
                    voice.subject() + " makes a `choose`" + through(fn) + reason,
                    nd.span or answer.span,
                    code=Code.TRICK_ORDER_FUNCTION_READS_BEYOND_THE_CARD,
                )
            elif isinstance(nd, n.NameRef) and nd.ref_kind == "zone":
                _check_answer_zone_read(
                    game, voice, nd, fn, out, through, id(nd) in subscripted
                )
            elif (
                isinstance(nd, n.NameRef)
                and nd.ref_kind == "state_var"
                and nd.name in phase_local
            ):
                home = " or ".join(
                    f"phase '{p}'" for p in sorted(declaring_phases(game, nd.name))
                )
                scoped: Said = (
                    " — the kernel reads " + voice.named() + " where no phase "
                    "frame stands (the end-of-game card census among them), so it "
                    "may read only the game's own `state { }`"
                )
                out.error(
                    voice.subject() + f" reads state variable '{nd.name}', which "
                    f"{home} declares" + through(fn) + scoped
                    + f"; declare '{nd.name}' there",
                    nd.span or answer.span,
                    code=Code.TRICK_ORDER_FUNCTION_READS_BEYOND_THE_CARD,
                )
            elif isinstance(nd, n.Call):
                _check_answer_call(game, voice, nd, fn, out, through)
        if len(bag.items) > before:
            refused.add("card_points" if answer.name == "card_points" else "trick_order")
    return refused


def _check_answer_zone_read(
    game: n.Game,
    voice: _AnswerVoice,
    nd: n.NameRef,
    fn: str | None,
    bag: _ErrorSink,
    through: Callable[[str | None], Said],
    is_subscripted: bool,
) -> None:
    decl = next((z for z in game.zones if z.name == nd.name), None)
    if decl is None:
        return
    ztype = decl.type_ref.name
    if ztype not in LIBRARY_ZONE_TYPES:
        return
    if not identity_to_all(ztype):
        reason = (
            f", which does not project identity to every observer — the "
            "kernel reads " + voice.named() + f" as a public fact of the card, so it "
            f"may read only fully public zones"
        )
        bag.error(
            voice.subject() + f" reads zone '{nd.name}' ({ztype})" + through(fn) + reason,
            nd.span or voice.answer.span,
            code=Code.TRICK_ORDER_FUNCTION_READS_BEYOND_THE_CARD,
        )
    elif (
        decl.index is not None
        and role_of(decl.index) is Role.PLAYER
        and not is_subscripted
    ):
        # Any other role read bare is `_check_bare_family_refs`'s, everywhere.
        # A bare per-player family read sugars to the ACTING player's instance
        # — and an answer has no acting player, by construction (the runtime
        # clears it, `evaluate.answer_context`). Named here rather than left to
        # that Shadow Guard so the fix is a subscript the author can write.
        # A player-typed state variable of THIS game, so the suggested
        # subscript is a name the designer can actually write.
        # Through library text there is no subscript the game can write: the
        # sink names the fix it can take instead.
        fix = ""
        if not isinstance(bag, _RouteSink):
            example = "declarer"
            if game.state is not None:
                example = next(
                    (v.name for v in game.state.decls if v.type_name == "Player"), example
                )
            fix = f"; subscript it with a player the state names (`{nd.name}[{example}]`)"
        reason = (
            " — the kernel asks " + voice.named() + f" with no acting player{fix}"
        )
        bag.error(
            voice.subject() + f" reads `{nd.name}` bare (the acting player's "
            f"instance)" + through(fn) + reason,
            nd.span or voice.answer.span,
            code=Code.TRICK_ORDER_FUNCTION_READS_BEYOND_THE_CARD,
        )


def _check_answer_call(
    game: n.Game,
    voice: _AnswerVoice,
    nd: n.Call,
    fn: str | None,
    bag: _ErrorSink,
    through: Callable[[str | None], Said],
) -> None:
    span = nd.span or voice.answer.span
    if nd.func in declared_names(game):
        # A [[primitive]] this game's own `primitives { }` block declares.
        # Uncallable from an answer for the reason every registered Primitive
        # is: an answer is HERMETIC, a pure function of the card and public
        # state, and a Primitive reads whatever its `reads` clause names — a
        # concealed hand among them. The registered half is uncallable because
        # `TRICK_ORDER_ROW_CALLS` admits none of it; the declared half is not
        # in that registry at all, so it needs this arm rather than inheriting
        # the exclusion.
        reads = (
            " — " + voice.named() + f" reads the card and public state only, and "
            f"a Primitive reads whatever its `reads` clause names"
        )
        bag.error(
            voice.subject() + f" calls the declared Primitive `{nd.func}(...)`"
            + through(fn) + reads,
            span,
            code=Code.TRICK_ORDER_FUNCTION_READS_BEYOND_THE_CARD,
        )
        return
    if nd.func in K.KERNEL_CONTRACT_NAMES:
        _check_reference_order(game, voice, nd, fn, bag, through)
        return
    if nd.func in {f.name for f in game.functions}:
        # A designer function, walked on its own. Tested directly rather than
        # through the arm below's `not in CALL_FUNCS`: a declared game may
        # legally name a function after a Primitive absent from ITS namespace,
        # and that spelling is in `CALL_FUNCS` all the same.
        return
    if nd.func in TRICK_ORDER_ROW_CALLS or nd.func not in CALL_FUNCS:
        return  # allowed, or a name no native registry claims
    if nd.func in TRICK_ORDER_GATED_FUNCS:
        defines = (
            " — " + voice.named() + f" may not read the Trick Order it helps define"
        )
        bag.error(
            voice.subject() + f" calls `{nd.func}(...)`, which reads every row "
            f"of the Trick Order" + through(fn) + defines,
            span,
            code=Code.TRICK_ORDER_FUNCTION_READS_BEYOND_THE_CARD,
        )
        return
    bag.error(
        f"`{nd.func}(...)` may not be called from " + voice.subject() + through(fn)
        + " — " + voice.named() + " reads the card and public state only",
        span,
        code=Code.TRICK_ORDER_FUNCTION_READS_BEYOND_THE_CARD,
    )


def _check_reference_order(
    game: n.Game,
    voice: _AnswerVoice,
    nd: n.Call,
    fn: str | None,
    bag: _ErrorSink,
    through: Callable[[str | None], Said],
) -> None:
    """An answer's call of another answer: the Trick Order's answers read only
    the answers BEFORE them, whatever order they are written in;
    `card_points` is outside the order, callable from any answer and calling
    any. A call of an answer's own name is the recursion guard's
    (`_check_functions`)."""
    order = K.TRICK_ORDER_CONTRACTS
    caller, callee = voice.name, nd.func
    called = _cite_in(game, "function", callee, f"`{callee}(...)`")
    if caller == callee or caller not in order or callee not in order:
        return
    if order.index(callee) < order.index(caller):
        return
    names = Sentence.join(
        ", then ", (_cite_in(game, "function", c, f"`{c}`") for c in order)
    )
    bag.error(
        voice.subject() + " calls " + called + ", which comes after it in the "
        "Trick Order" + through(fn)
        + " — the Trick Order is read in one order, " + names + ", and each may "
        "call only the ones before it; spell the fact in this function, or move "
        "it to the later one",
        nd.span or voice.answer.span,
        code=Code.TRICK_ORDER_FUNCTION_CALLS_A_LATER_ONE,
    )


def _check_arrival_record_pile_args(game: n.Game, bag: DiagnosticBag) -> None:
    """Every [[arrival-record]] read names a fully public zone, STATICALLY.

    The Owner Guard for the provenance rule (issue #256's decision-context
    rule, tightened here to a static check): a winner is named from who played
    what, so the pile it reads must be one whose arrivals every observer can
    derive from their own stream. Two facts must hold, and both are decidable
    without running anything — the argument is a zone REFERENCE (not a
    computed value, whose zone nobody can name until play time), and that
    zone's declared type projects identity to all.

    Deciding them here rather than at the call is what makes the proof
    harness's provenance derivation possible: it walks the checked AST for
    these calls and reads the pile's zone name off the argument
    (`tests/openspiel_ready/harness.py`), which is only sound because the
    argument is guaranteed to BE a name. The runtime's matching guards become
    Shadow Guards behind this one."""
    zones = {z.name: z for z in game.zones}
    for nd in _walk(game):
        if not isinstance(nd, n.Call) or nd.func not in ARRIVAL_RECORD_CALLS:
            continue
        idx = ARRIVAL_RECORD_CALLS[nd.func]
        arg = nd.args[idx] if len(nd.args) > idx else None
        name: str | None = None
        if isinstance(arg, n.NameRef) and arg.ref_kind == "zone":
            name = arg.name
        elif (
            isinstance(arg, n.Subscript)
            and isinstance(arg.obj, n.NameRef)
            and arg.obj.ref_kind == "zone"
        ):
            name = arg.obj.name
        if name is None:
            bag.error(
                f"`{nd.func}` reads the Arrival Record of its pile argument, "
                f"which must name a zone (`{nd.func}(trick_pile)`); got "
                f"{_arg_shape(arg)}",
                nd.span or game.span,
                code=Code.WRONG_ARGUMENT,
            )
            continue
        decl = zones.get(name)
        if decl is None or decl.type_ref.name not in LIBRARY_ZONE_TYPES:
            continue
        ztype = decl.type_ref.name
        if not identity_to_all(ztype):
            bag.error(
                f"`{nd.func}` over '{name}' ({ztype}): the zone type does not "
                f"project identity to every observer, so its provenance is not "
                f"derivable from any observer's stream — a winner may only be "
                f"named over a fully public pile",
                nd.span or game.span,
                code=Code.WRONG_ZONE_VISIBILITY,
            )


def _arg_shape(arg: object) -> str:
    """How a rejected pile argument is described back to the author — its
    SHAPE, in the language's words, never a node class name."""
    match arg:
        case None:
            return "no argument"
        case n.IntLit() | n.StrLit():
            return "a literal"
        case n.Call() as c:
            return f"the value of `{c.func}(...)`"
        case n.CardQuery():
            return "a card query"
        case n.NameRef() as r:
            return f"'{r.name}', which is not a zone"
        case _:
            return "an expression"


def _unread_trick_order(game: n.Game, written: Sequence[object]) -> Said:
    winner = min(TRICK_ORDER_GATED_WINNERS)
    gated = Sentence.join(
        ", ",
        (_cite_in(game, "function", f, f"`{f}`") for f in sorted(_TRICK_ORDER_READERS)),
    )
    return (
        "function " + _cite_in(game, "function", "is_trump", "`is_trump`")
        + f" declares a Trick Order nothing reads — no round names {winner}, and "
        f"nothing outside the Trick Order's functions calls " + gated + f"; name "
        f"{winner} on a trick round or call it over the trick pile, or "
        f"{_drop_trick_order(game)}"
    )


def _unread_suit_ranking(game: n.Game, written: Sequence[object]) -> str:
    return (
        "suit ranking: is read by nothing — `suit_value(s)` is its one reader; "
        "call it where the game compares suits, or drop the clause"
    )


def _unread_card_points(game: n.Game, written: Sequence[object]) -> Said:
    answer = K.answer(game, "card_points")
    if answer is not None and answer.spelled_as is None:
        return (
            "function " + cite_named(answer, "`card_points`") + " is read by "
            "nothing — " + cite_named(answer, "`card_points(card)`") + " is its "
            "one reader; call it where the game counts a card's points, or drop "
            "the function"
        )
    reader: Said = (
        cite_named(answer, "`card_points(card)`") if answer is not None else "`card_points(card)`"
    )
    return (
        "card_points { } is read by nothing — " + reader + " is its one "
        "reader; call it where the game counts a card's points, or drop the table"
    )


def _trick_order_clause(game: n.Game) -> tuple[n.FunctionDef, ...] | None:
    answers = K.trick_order_answers(game)
    return answers or None


def _card_points_clause(game: n.Game) -> tuple[n.FunctionDef, ...] | None:
    answer = K.answer(game, "card_points")
    return (answer,) if answer is not None else None


# The clauses a game states by answering Kernel Definition Contracts rather
# than by an `n.Game` field: each is the answers it holds, or None. The Trick
# Order is ONE clause of up to three answers, so its own answers never read
# it.
_DEFINITION_CLAUSES: dict[str, Callable[[n.Game], tuple[n.FunctionDef, ...] | None]] = {
    "trick_order": _trick_order_clause,
    "card_points": _card_points_clause,
}


def _clause_span(game: n.Game, clause: str, value: object) -> Span | None:
    """Where an unread clause is refused: the clause as written — a block's
    own span, the `card_points { }` table, or the answering function."""
    if isinstance(value, tuple):
        first = value[0]
        assert isinstance(first, n.FunctionDef), "a definition clause is its answers"
        spelled = first.spelled_as
        if spelled is not None and spelled.span is not None:
            return spelled.span
        return first.span
    span = getattr(value, "span", None)
    return span if isinstance(span, Span) else None


# The sentence each clause some `_CLAUSE_GATES` row reads is refused in when
# nothing reads it. Keyed exactly by the reader rows' clauses (pinned equal by
# tests/test_unread_clauses.py).
_UNREAD_SENTENCES: dict[str, Callable[[n.Game, Sequence[object]], Said]] = {
    "trick_order": _unread_trick_order,
    "suit_ranking": _unread_suit_ranking,
    "card_points": _unread_card_points,
}


def _check_unread_clauses(
    written: n.Game, stamped_rules: Sequence[n.RuleDef], refused: set[str], bag: DiagnosticBag
) -> None:
    """A game clause some `_CLAUSE_GATES` row reads (`role == "reader"`) is
    read by something the game WRITES: a construct meeting one of its reader
    rows' tests, anywhere in the game's own text, every definition and
    provided declaration a library splices in, and every library or stdlib
    rule the game activates (`stamped_rules`). A clause nothing reads is
    accepted-but-ignored, and is refused at the clause.

    Written, never reached: every reader row's own gate refuses its construct
    wherever it is written, dead text included, so counting the same text here
    is what keeps a sentence from being refused both with the clause and
    without it. A clause's own body is never its reader -- a Trick Order's
    answers calling each other do not make it read -- though it may read
    another clause (an answer calling `suit_value`).

    `written` is the game before `_instantiate_rules`, which drops a local
    template that fails to instantiate along with the reader inside it.
    `refused` holds the clauses their own Owner Guards refused
    (`_resolve_suit_ranking`, `_resolve_card_points`,
    `_check_answer_hermeticity`); this law
    says nothing of those, nor of a piece game's clauses
    (`_reject_card_content_clauses`) or an unknown deck's
    (`_resolve_component_set`).

    Only game text is a reader. The driver's end-of-game card census
    (`driver._final_card_census`) and the OpenSpiel ranked policy's trump
    fallback (`openspiel/ranked.py`) read clauses as instruments, and no check
    counts them. The trick form also publishes its trump as `state["trump"]`,
    a channel a Primitive behind a trick round could read back and this law
    cannot see; no corpus Primitive reads it, so the reader model is exact
    today, and a game that revived the channel under a trump-blind winner
    would meet a false refusal here: over-reach in the safe direction, never a
    miss."""
    if written.content_flavor != "card" or not _deck_known(written.deck):
        return
    readers: dict[str, list[_ClauseGate]] = {}
    for row in _CLAUSE_GATES:
        if row.role == "reader":
            readers.setdefault(row.clause, []).append(row)
    text = [*_walk(written), *(nd for rule in stamped_rules for nd in _walk(rule))]
    for clause, rows in readers.items():
        value = (
            _DEFINITION_CLAUSES[clause](written)
            if clause in _DEFINITION_CLAUSES
            else getattr(written, clause)
        )
        if value is None or clause in refused:
            continue
        own = {
            id(nd)
            for part in (value if isinstance(value, tuple) else (value,))
            for nd in _walk(part)
        }
        nodes = [nd for nd in text if id(nd) not in own]
        if any(row.needs(nd, written) for nd in nodes for row in rows):
            continue
        span = _clause_span(written, clause, value) or written.span
        bag.error(_UNREAD_SENTENCES[clause](written, nodes), span, code=Code.UNUSED_DECLARATION)


def _check_functions(game: n.Game, bag: DiagnosticBag) -> None:
    """Functions are hermetic and non-recursive: a body may reference only its own
    parameters, binders it introduces (`number of players where …`), and game/phase
    state — not a name the flat classifier tagged `local` from some unrelated binder,
    and not the call-site pronouns (`_CALL_SITE_PRONOUNS` — the runtime clears
    them); and the call graph must be acyclic (a cycle would loop forever at runtime).
    A function may not reuse a native call name: a call would type-check against the
    native signature but dispatch to the user function at run time. Nor may it take a
    name one of the game's round slots writes: the slot runs the native, so the
    function would never be what it means there."""
    fn_names = {f.name for f in game.functions}
    calls: dict[str, set[str]] = {
        f.name: {c.func for c in _walk(f.body) if isinstance(c, n.Call) and c.func in fn_names}
        for f in game.functions
    }
    native = call_namespace(game)
    # The names this game's own rounds write in a slot: a function sharing one
    # is never what that slot runs, while a function no slot here names is
    # simply called (the native arm's rule: the game's namespace, not the
    # corpus-wide registry).
    slot_written = {
        name
        for nd in _walk(game)
        for form, field_name in _ROUND_QUERY_REGISTRIES
        if isinstance(nd, form)
        for name in slot_strings(nd, field_name)
    }
    for fn in game.functions:
        # The GAME's namespace, not the corpus-wide registry: a Primitive this
        # game cannot call shadows nothing here, and refusing the name anyway
        # would make the declared regime narrower than the legacy one it
        # replaces — the opposite of the isolation it promises.
        if fn.name in native:
            bag.error(
                f"function " + cite_named(fn, f"'{fn.name}'") + f" shadows the native function of the same name; "
                f"rename it (a call would type-check against the native signature but "
                f"run this function instead)",
                fn.span,
                code=Code.NAME_TAKEN,
            )
        elif fn.name in slot_written and (slot := _round_query_slot(fn.name)) is not None:
            bag.error(
                f"function " + cite_named(fn, f"'{fn.name}'") + f" has the name of the "
                f"language's own `{fn.name}`, which {slot} names; that slot always runs "
                f"the language's `{fn.name}` and never calls this function — rename it",
                fn.span,
                code=Code.NAME_TAKEN,
            )
        allowed = {p.name for p in fn.params}
        for nd in _walk(fn.body):  # binders the body itself introduces are in scope
            allowed.update(_introduced_binders(nd))
        for nd in _walk(fn.body):
            if not isinstance(nd, n.NameRef):
                continue
            if nd.ref_kind == "local" and nd.name not in allowed:
                bag.error(
                    f"function " + cite_named(fn, f"'{fn.name}'") + f" references '{nd.name}', which is not one of "
                    f"its parameters or a binding in its body",
                    nd.span,
                    code=Code.READS_BEYOND_PARAMETERS,
                )
            elif _pronoun_refused(nd.name, nd.ref_kind, _refused_call_site_pronouns(fn)):
                # An answer's pronoun is `_check_answer_hermeticity`'s, which
                # refuses every pronoun in it. The list is RENDERED from the
                # registry, not spelled out: a
                # hand-written enumeration goes stale the next time the pronoun set
                # moves, and a diagnostic that names the wrong words misdirects the
                # designer it is meant to repair.
                bag.error(
                    f"function " + cite_named(fn, f"'{fn.name}'") + f" reads the call-site pronoun '{nd.name}'; a "
                    f"function is hermetic and may not read "
                    f"{'/'.join(sorted(_CALL_SITE_PRONOUNS))} — "
                    + (
                        _contracted_remedy(fn.contracts)
                        if fn.contracts
                        else "pass the value in as a parameter"
                    ),
                    nd.span,
                    code=Code.READS_BEYOND_PARAMETERS,
                )
        if _reaches(fn.name, fn.name, calls):
            library_functions = {f.name: f for f in game.functions if f.origin is not None}
            _report_recursion(fn, calls, library_functions, bag)


def _contracted_remedy(contracts: tuple[n.ContractStamp, ...]) -> Said:
    """The fix for a definition answering a Definition Contract that reads a
    call-site pronoun. Its call sites are in the text of every library whose
    row it answers, which the game's author cannot edit, so the fix named is
    one they can take."""
    callers = Sentence.join(" and ", (
        cite_library(c.library, c.row_span) + f" calls it under its contract " + cite_where(f"`{c.row}`", c.row_span)
        for c in contracts
    ))
    return (
        callers + ", from text this game cannot edit, so no argument can "
        "be added there: read the value from the parameter the row passes, or "
        "from the game's own state"
    )


def _report_recursion(
    fn: n.FunctionDef,
    calls: dict[str, set[str]],
    library_functions: dict[str, n.FunctionDef],
    bag: DiagnosticBag,
) -> None:
    """A recursive function, told to the Author who closed the cycle. A cycle
    that crosses the splice — a library function calling a contracted game
    function that calls back into the library — is in neither file alone: the
    game's function is what closed it, so the game's author is told, at each
    game function on the cycle, and the library's members stay quiet."""
    cycle = {fn.name} | {
        other
        for other in calls
        if _reaches(fn.name, other, calls) and _reaches(other, fn.name, calls)
    }
    imported = sorted(name for name in cycle if name in library_functions)
    if not imported or len(imported) == len(cycle):
        bag.error(
            f"function " + cite_named(fn, f"'{fn.name}'") + f" is recursive; functions must be non-recursive",
            fn.span,
            code=Code.RECURSIVE_FUNCTION,
        )
        return
    if fn.name in library_functions:
        return
    through = Sentence.join(", ", (
        cite_origin(origin, library_functions[name].span)
        for name in imported
        if (origin := library_functions[name].origin) is not None
    ))
    bag.error(
        f"function " + cite_named(fn, f"'{fn.name}'") + f" is recursive through " + through + ", which calls it "
        "back; functions must be non-recursive, and this game's definition "
        "closes the cycle",
        fn.span,
        code=Code.RECURSIVE_FUNCTION,
    )


def _check_declared_type_names(game: n.Game, bag: DiagnosticBag) -> None:
    """A function parameter's and an outcome payload's declared type name names
    a real type: a value type, a declared position domain, or the direction
    domain the board minted (`_minted_directions`); a `dir` no board minted is
    refused naming what the game lacks (`_unminted_direction`).

    Validating a declared type name is resolve's job: `StateDecl` is guarded
    in `_validate_refs` and move parameters have their own domain gate, and
    this owns function parameters and outcome payloads.
    `typecheck.type_from_name` maps an unknown name to the permissive `TAny`,
    so a mere TYPO exempted the annotated value from every downstream guard —
    `function f(x : Integar) = x is hearts` was accepted while the
    correctly-spelled `Integer` version was rejected. Making a type name worse
    must never make the checker more permissive (decisions.md "Surface
    totality"; "`Any` means the top, never a failed lookup").

    The other declaring positions are deliberately absent, each already owned
    by an Owner Guard at least as tight: move parameters by `_check_move_params`
    (which additionally requires an ENUMERABLE domain, and now runs for every
    declared move type), procedure parameters by `_PROCEDURE_PARAM_DOMAINS`, and
    rule-template parameters by `_check_template`'s Suit-only gate. Adding a
    second name check over any of them would report one defect twice, in two
    channels.
    """
    # A declared position domain is a legal annotation here: the parameter or
    # payload carries an integer member of the declared range, and the type
    # builder resolves it to that Integer. Omitting it rejected a name
    # declared in the same file as "unknown" while the same name stayed legal
    # on a move parameter.
    position_names = {p.name for p in game.positions}
    known = _declared_type_universe(game) | position_names | _minted_directions(game)
    # A function parameter is the one position a climbing play is named in.
    parameter_known = known | {COMBINATION_TYPE_NAME}

    def base_of(type_name: str) -> str:
        # A trailing `?` marks a nullable domain/payload (`Suit?`), not part of
        # the name — strip it before the lookup, never by a blanket rstrip.
        return type_name.removesuffix("?")

    for fn in game.functions:
        for p in fn.params:
            refusal = _direction_refusal(game, base_of(p.type_name))
            if refusal is not None:
                bag.error(
                    f"parameter '{p.name}' of function " + cite_named(fn, f"'{fn.name}'")
                    + f" is typed `{p.type_name}`, " + refusal,
                    fn.span,
                    code=Code.CHECKER_TYPE_NOT_ALLOWED_HERE,
                )
            elif base_of(p.type_name) not in parameter_known:
                bag.unknown(
                    f"unknown type '{p.type_name}' in parameter '{p.name}' of "
                    f"function " + cite_named(fn, f"'{fn.name}'"),
                    base_of(p.type_name),
                    parameter_known,
                    fn.span,
                    code=Code.UNKNOWN_CHECKER_TYPE,
                )
    for phase in _walk(game):
        if not isinstance(phase, n.Phase) or not phase.outcome_cases:
            continue
        for case in phase.outcome_cases:
            for payload in case.payload_types:
                refused = _combination_outside_a_parameter(payload, "an outcome's payload")
                if refused is not None:
                    bag.error(refused, case.span or phase.span, code=Code.CHECKER_TYPE_NOT_ALLOWED_HERE)
                elif (refusal := _direction_refusal(game, base_of(payload))) is not None:
                    bag.error(
                        f"the payload of case '{case.tag}' is typed `{payload}`, " + refusal,
                        case.span or phase.span,
                        code=Code.CHECKER_TYPE_NOT_ALLOWED_HERE,
                    )
                elif base_of(payload) not in known:
                    bag.unknown(
                        f"unknown type '{payload}' in payload of case "
                        f"'{case.tag}'",
                        base_of(payload),
                        known,
                        case.span or phase.span,
                        code=Code.UNKNOWN_CHECKER_TYPE,
                    )


# POSITION-DEPENDENT STATEMENTS: the closed class a procedure body may not hold.
#
# A procedure body is written once and spliced into many sites. Any statement whose
# VALIDITY depends on where it sits is therefore unsound in one — the checker sees
# it once, at the declaration, where the surrounding context does not exist yet, and
# the copies it is checked as are never checked again (expansion runs after
# typecheck, which is what makes the parameter types enforceable).
#
# The class is closed by enumerating the checks that are themselves
# position-dependent, not by intuition:
#
#   `_check_outcome_scope`         a `produces:` consumer must name an EARLIER-executed
#                                  sibling phase; `continue to` a LATER one; `skip to
#                                  next hand` must sit inside a hand loop
#   `_check_single_outcome_consumer`  a phase outcome has exactly ONE consumer — a
#                                  count, which a second `run` changes
#   `_check_misplaced_produce`     `produce` terminates the enclosing outcome phase
#   outcome binding                a `round` binds its own `outcome` for the statements
#                                  after it, which the body's pronoun guard cannot tell
#                                  from the caller's call-site `outcome`
#
# Every statement those checks govern is rejected in a body. The two remaining
# position-sensitive passes — `deckcheck.check_capacity` and the OpenSpiel action
# space — both run AFTER expansion and so see the real, spliced tree.
_NON_LOCAL_STMTS = (n.Produce, n.ContinueTo, n.SkipToNextHand)
# The round forms, each of which binds `winner` for the statements after it.
_WINNER_BINDING_STMTS = (n.TrickRound, n.ClimbRound)


# What a Hosted Poll's body can EXECUTE, beyond its own text: the definitions
# it names whose bodies then run, by the reference namespace that names them
# (namespace -> the `n.Game` field holding them). A procedure it runs, a move
# type it offers — by `offer`, guard and effect alike —
# and a function it calls, each followed transitively. Pinned against every
# naming slot on a statement or expression node by tests/test_hosted_poll.py,
# with `HOSTED_REACH_INERT_SLOTS` beside it.
HOSTED_REACH_POOLS: dict[str, str] = {
    "procedure": "procedures",
    "move_type": "move_types",
    "function": "functions",
}

# The naming slots on statement and expression nodes that name nothing whose
# DSL text runs: a deck value, a role, a field name (the `state` pronoun is
# refused wherever it stands, by its own arm), a position binder. Every other
# such slot is followed above, sits on a statement `HOSTED_POLL_REFUSED`
# names, or is refused below.
HOSTED_REACH_INERT_SLOTS: frozenset[tuple[type, str]] = frozenset(
    {
        (n.CardLiteral, "rank"),
        (n.CardLiteral, "suit"),
        (n.ForEach, "role"),
        (n.Quantifier, "role"),
        (n.Member, "field"),
        (n.DomainQuery, "binder"),
        # The go-again flag a `turns` ring consumes: a declared state variable,
        # read and reset by the form itself, running no text of the game's.
        (n.Turns, "again"),
    }
)

_HOSTED_REACH_VERB = {"procedure": "run", "move_type": "offered", "function": "called"}
_HOSTED_REACH_NOUN = {"procedure": "procedure", "move_type": "move type", "function": "function"}

# The parts of a reached definition a diagnostic names apart, by field.
_HOSTED_REACH_PART: dict[tuple[type, str], str] = {
    (n.MoveTypeDef, "when"): "its `when:`",
    (n.MoveTypeDef, "params"): "its parameters",
}


def _check_hosted_polls(game: n.Game, bag: DiagnosticBag) -> None:
    """The Owner Guard of what a Hosted Poll's body can execute (decisions.md
    "Off-the-clock windows"), judged over the closure of the body: its own
    statements and every definition reachable from them by name
    (`HOSTED_REACH_POOLS`, followed by `_definition_closure`). Across all of
    it, every statement is one `HOSTED_POLL_ALLOWED` names; the `state`
    pronoun stands nowhere, since it evaluates to the live round frame
    wherever it stands
    (a `let` or an argument carries the frame on to a later read); and
    nothing calls a Primitive, whose game module reads the live round frame
    through `EngineFacts.round_state`. Those two are every route from an
    expression to the frame. The round's frame is live and unpublished while
    the body runs, and every card and every signal the body could raise
    would land inside a trick in progress. After `_classify_names`, so a
    pronoun is recognized by the `ref_kind` the classifier stamped."""
    pools: dict[str, dict[str, object]] = {
        ns: {d.name: d for d in getattr(game, field)}
        for ns, field in HOSTED_REACH_POOLS.items()
    }
    # The Primitives a call here can name: the game's own native namespace
    # less the Builtins. A designer function is never among them — a call
    # dispatches to the designer's function first, and `_check_functions`
    # refuses a function spelled like a name in this same namespace — so a
    # function spelled like another game's Primitive is followed as a
    # function, never refused as a Primitive.
    primitives = set(call_namespace(game) - BUILTIN_CALL_FUNCS)
    for poll in (nd for nd in _walk(game) if isinstance(nd, n.HostedPoll)):
        clause = f"the Hosted Poll (`before asking {poll.binder}`)"
        reached = _definition_closure([poll], pools)

        def path(key: tuple[str, str] | None, part: str) -> Said:
            segments: list[Said] = []
            while key is not None:
                ns, name = key
                target = reached[key][0]
                origin = getattr(target, "origin", None)
                noun = f"{_HOSTED_REACH_NOUN[ns]} '{name}'"
                named: Said = (
                    cite_named(target, noun) if origin is None
                    else cite_definition(origin.library, noun, getattr(target, "span", None))
                )
                segments.append(named + f" ({_HOSTED_REACH_VERB[ns]})")
                key = reached[key][1]
            text = Sentence.join(" → ", reversed(segments))
            return ", reached through " + text + (", " + part if part else "")

        units: list[tuple[object, Said, _ErrorSink, object]] = [(poll.body, "", bag, poll)]
        for key, (target, _via) in reached.items():
            # Library text the poll reaches is sound where the library runs
            # it: the poll's reach into it is what fails.
            entry = _library_entry(_closure_steps(key, reached, poll))
            out: _ErrorSink = (
                bag if entry is None
                else _RouteSink(bag, _entry_route("hosted_poll", entry, poll.span))
            )
            for f in fields(cast(n.Node, target)):
                part = _HOSTED_REACH_PART.get((type(target), f.name), "")
                units.append((getattr(target, f.name), path(key, part), out, target))
        for unit, via, sink, holder in units:
            never = _NEVER_HELD.get(type(holder), ())
            for nd in _child_nodes(unit):
                # A statement the holding definition may not hold anywhere is
                # its author's fault in every game, told where it is written.
                at = bag if isinstance(nd, never) else sink
                _check_hosted_node(nd, clause, via, primitives, at)


# The statements a definition kind may hold in no game, by kind: a procedure's
# are `_check_procedures`' refusals, a move type effect's are the type layer's
# (`typecheck._check_misplaced_produce` and its `continue to` arm).
_NEVER_HELD: dict[type, tuple[type, ...]] = {
    n.ProcedureDef: _NON_LOCAL_STMTS + _WINNER_BINDING_STMTS,
    n.MoveTypeDef: _NON_LOCAL_STMTS,
}


def _check_hosted_node(
    nd: object, clause: str, via: Said, primitives: set[str], bag: _ErrorSink
) -> None:
    """One node of a Hosted Poll's closure against the four refusals."""
    why_live = (
        "it runs between two asks of a live climbing trick, where only "
        "decisions and state writes may happen"
    )
    if isinstance(nd, _STMT_KINDS) and type(nd) not in HOSTED_POLL_ALLOWED:
        bag.error(
            f"{clause} may not hold {HOSTED_POLL_REFUSED[type(nd)]}" + via + f": {why_live}",
            cast(n.Stmt, nd).span,
            code=Code.HOSTED_POLL_READS_UNPUBLISHED_ROUND_STATE,
        )
        return
    if isinstance(nd, n.NameRef) and nd.name == "state" and nd.ref_kind == "pronoun":
        bag.error(
            f"{clause} may not read `state`" + via + ": the round's state is "
            "published only once the round has ended",
            nd.span,
            code=Code.HOSTED_POLL_READS_UNPUBLISHED_ROUND_STATE,
        )
    elif isinstance(nd, n.Call) and nd.func in primitives:
        bag.error(
            f"{clause} may not call the Primitive `{nd.func}`" + via + ": a game "
            f"module reads the round's live, unpublished state through its "
            f"engine facts",
            nd.span,
            code=Code.HOSTED_POLL_READS_UNPUBLISHED_ROUND_STATE,
        )


def _check_procedures(
    game: n.Game, bag: DiagnosticBag, own: frozenset[str] | None = None
) -> None:
    """A procedure body must read as the statements it becomes. Hermeticity is the
    same as a function's — a body references only its own parameters, the binders
    it introduces, and game/phase state, never the caller's locals and never the
    call-site pronouns, so its meaning cannot depend on where it is run from.

    Only ONE hygiene Owner Guard lives here, because `expand` makes the rest unnecessary
    by construction: it binds each argument to a `let` in the CALLER's context
    before the body runs (so nothing in the body can capture an argument, and an
    argument naming the actor cannot be re-read under a construct that rebinds it),
    and it wraps the body in a block (so the body's own bindings cannot leak into
    the caller). What expansion cannot fix is a body binder sharing a PARAMETER's
    name: classification tags both `local`, so substitution cannot tell them apart.
    That one is rejected outright.
    """
    known = {p.name: p for p in game.procedures}
    outcome_phases = {
        nd.name for nd in _walk(game) if isinstance(nd, n.Phase) and nd.outcome_cases
    }
    for proc in game.procedures:
        params = {p.name for p in proc.params}

        names = [p.name for p in proc.params]
        for dup in sorted({nm for nm in names if names.count(nm) > 1}):
            bag.error(
                f"procedure " + cite_named(proc, f"'{proc.name}'") + f" declares more than one parameter named "
                f"'{dup}' — substitution binds by name, so one would silently "
                f"shadow the other",
                proc.span,
                code=Code.NAME_TAKEN,
            )
        for p in proc.params:
            refused = _combination_outside_a_parameter(p.type_name, "a procedure's parameter")
            if refused is not None:
                bag.error(refused, p.span, code=Code.CHECKER_TYPE_NOT_ALLOWED_HERE)
            elif p.type_name not in _PROCEDURE_PARAM_DOMAINS:
                bag.unknown(
                    f"procedure parameter '{p.name}: {p.type_name}' has an "
                    f"unsupported domain — procedure parameters support "
                    f"{', '.join(sorted(_PROCEDURE_PARAM_DOMAINS))} only "
                    f"(corpus-first; extend when a game needs another)",
                    p.type_name,
                    _PROCEDURE_PARAM_DOMAINS,
                    p.span,
                    code=Code.NOT_YET_SUPPORTED,
                )

        # Binders the body introduces, and the name-capture Owner Guard: a binder
        # sharing a parameter's name would capture it instead of substituting.
        # A procedure body can hold a movement, so its filter binder follows
        # the game's flavor (a piece game's `piece`, not `card`).
        binders: set[str] = set()
        for nd in _walk(proc):
            binders.update(_introduced_binders(nd, game.content_flavor))
        for p in proc.params:
            if p.name in binders:
                bag.error(
                    f"procedure " + cite_named(proc, f"'{proc.name}'") + f" introduces a binder named "
                    f"'{p.name}', shadowing its own parameter — rename one",
                    proc.span,
                    code=Code.NAME_TAKEN,
                )

        if not proc.body:
            bag.error(
                f"procedure " + cite_named(proc, f"'{proc.name}'") + f" has an empty body — it would splice "
                f"nothing at every site that runs it; give it statements or delete it",
                proc.span,
                code=Code.HAS_NO_EFFECT,
            )

        allowed = params | binders
        for stmt in proc.body:
            for nd in _walk(stmt):
                if isinstance(nd, _NON_LOCAL_STMTS):
                    what = {
                        n.Produce: "`produce`",
                        n.ContinueTo: "`continue to`",
                        n.SkipToNextHand: "`skip to next hand`",
                    }[type(nd)]
                    bag.error(
                        f"procedure " + cite_named(proc, f"'{proc.name}'") + f" uses {what}, which unwinds past "
                        f"the statement it is written at; a procedure body is "
                        f"spliced into its call sites, which may sit in different "
                        f"enclosing constructs, so it may not contain non-local "
                        f"control flow",
                        nd.span,
                        code=Code.OUT_OF_PLACE,
                    )
                elif isinstance(nd, _WINNER_BINDING_STMTS):
                    bag.error(
                        f"procedure " + cite_named(proc, f"'{proc.name}'") + f" contains a `round`, which binds "
                        f"its own `winner` for the statements after it; a "
                        f"procedure body may not yet hold one, because the body's "
                        f"`winner` Owner Guard cannot distinguish a round-local binding "
                        f"from the caller's call-site pronoun (procedures.md)",
                        nd.span,
                        code=Code.NOT_YET_SUPPORTED,
                    )
                elif isinstance(nd, n.Produces) and nd.phase in outcome_phases:
                    bag.error(
                        f"procedure " + cite_named(proc, f"'{proc.name}'") + f" consumes the phase outcome of "
                        f"'{nd.phase}'. A phase outcome's consumer must be an "
                        f"EARLIER-executed sibling of the producing phase, and there "
                        f"must be exactly ONE of them — both are facts about where "
                        f"the statement sits, and a procedure body is spliced into "
                        f"sites the checker cannot see when it checks the body. "
                        f"Running it before '{nd.phase}', or running it twice, would "
                        f"pass here and then fail at play time. Consume the outcome "
                        f"at the site",
                        nd.span,
                        code=Code.OUTCOME_READ_BEFORE_PRODUCED,
                    )
                elif isinstance(nd, n.RunStmt):
                    bag.error(
                        f"procedure " + cite_named(proc, f"'{proc.name}'") + " runs procedure "
                        + _cite_in(game, "procedure", nd.name, f"'{nd.name}'") + "; a "
                        f"procedure may not invoke another (v1 — expansion is a "
                        f"single splice, not a call graph)",
                        nd.span,
                        code=Code.NOT_YET_SUPPORTED,
                    )
                elif isinstance(nd, n.NameRef):
                    if nd.ref_kind == "local" and nd.name not in allowed:
                        bag.error(
                            f"procedure " + cite_named(proc, f"'{proc.name}'") + f" references '{nd.name}', which "
                            f"is not one of its parameters or a binding in its body",
                            nd.span,
                            code=Code.READS_BEYOND_PARAMETERS,
                        )
                    elif _pronoun_refused(nd.name, nd.ref_kind, _refused_call_site_pronouns(proc)):
                        remedy = (
                            _contracted_remedy(proc.contracts)
                            if proc.contracts
                            else "pass the value in as a parameter (`run "
                            + cite_named(proc, proc.name) + f"({nd.name})`)"
                        )
                        bag.error(
                            f"procedure " + cite_named(proc, f"'{proc.name}'") + f" reads the call-site pronoun "
                            f"'{nd.name}'; a procedure body is spliced into call "
                            f"sites that need not share a call-site context — "
                            + remedy,
                            nd.span,
                            code=Code.READS_BEYOND_PARAMETERS,
                        )

    # Call sites: the procedure must exist, every declared procedure must be
    # invoked — an uninvoked body is spliced nowhere, so nothing downstream ever
    # sees it (the same reasoning `_instantiate_rules` gives an uninstantiated
    # rule template) — and no argument may be captured by a binder in the body.
    invoked: set[str] = set()
    for nd in _walk(game):
        if isinstance(nd, n.RunStmt):
            invoked.add(nd.name)
            if nd.name not in known:
                bag.unknown(f"run of unknown procedure '{nd.name}'", nd.name, known, nd.span, code=Code.UNKNOWN_PROCEDURE)
            else:
                _check_positive_arguments(known[nd.name], nd, bag)
    # Only the game's OWN procedures: a library's are its own to define, and
    # a game that imports one and runs it nowhere has not made an error — the
    # rule `_check_unoffered_move_types` keeps for a library's move types.
    for proc in game.procedures:
        if proc.name not in invoked and (own is None or proc.name in own):
            bag.error(
                f"procedure " + cite_named(proc, f"'{proc.name}'") + " is never run — invoke it with `run "
                + cite_named(proc, proc.name) + "(…)`, or delete it (its body would otherwise be "
                f"spliced nowhere, and go entirely unchecked downstream)",
                proc.span,
                code=Code.UNUSED_DECLARATION,
            )


def _check_positive_arguments(
    proc: n.ProcedureDef, run: n.RunStmt, bag: DiagnosticBag
) -> None:
    """The `Positive` domain [[owner-guard]]: an argument bound to a `Positive`
    parameter is a written whole number of 1 or more. Expansion splices the
    argument as a plain binding and rejects nothing, so a computed value would
    reach play unchecked; the written number is the one form whose membership
    is decided here. A missing or surplus argument is typecheck's arity check,
    so `zip` leaving it alone is that guard's case, not a gap."""
    for param, arg in zip(proc.params, run.args):
        if param.type_name != POSITIVE_PARAM_DOMAIN:
            continue
        head = (
            f"`run {run.name}` passes its `{param.name}`, which "
            + cite_named(proc, f"'{proc.name}'")
            + " takes as a Positive number"
        )
        if not isinstance(arg, n.IntLit):
            bag.error(
                head + " — write the number itself (`2`, `10`): a Positive "
                "parameter takes a whole number of 1 or more written at the "
                "run, so the check can see it before play",
                arg.span,
                code=Code.WRONG_ARGUMENT,
            )
        elif arg.value < 1:
            bag.error(
                head + f" — {arg.value} is not one: a Positive parameter takes "
                "a whole number of 1 or more, so write 1 or more",
                arg.span,
                code=Code.OUT_OF_RANGE,
            )


def _reaches(start: str, target: str, calls: dict[str, set[str]]) -> bool:
    """Whether `target` is reachable from `start` through the call graph."""
    seen: set[str] = set()
    stack = list(calls.get(start, ()))
    while stack:
        cur = stack.pop()
        if cur == target:
            return True
        if cur in seen:
            continue
        seen.add(cur)
        stack.extend(calls.get(cur, ()))
    return False
