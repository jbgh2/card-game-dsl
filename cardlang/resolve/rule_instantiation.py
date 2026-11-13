"""Resolve step: rule instantiation, query nouns, and rule references.

Contract (decisions.md "Closed-domain completeness", write-time triage)
-----------------------------------------------------------------------
Assumes:      the library rules the splice held aside; the zones checked.
              The rule names it judges ``active_rules:`` against are taken
              from the tree before instantiation, which drops a local
              template that fails to instantiate.
Establishes:  Every library's rules — a family
              library's and ``library stdlib``'s — are spliced into
              ``game.rules`` only where an ``active_rules:`` reference
              names them, after the game's own.
              Every rule in ``game.rules`` is a concrete, parameter-free
              definition. The step returns the refused binder sources, for
              classification.
              A ``DomainQuery`` noun is validated here, before classification,
              so its unknown-noun refusal reports before the unresolved names
              a wrong noun would cause.
              A node whose binder source is refused binds nothing, and a
              name in its scope spelled as a binder a fix would bind is not
              told (``_refused_binder_sources``, ``_membership_capture``),
              held by Derived and Pinned: a withheld name is one lexical
              field (``withheld``), set where a binder is scoped and read by
              the one unresolved-name arm. A transition target, a rule
              reference and a template argument refused here mark their slot,
              and a mode never active, a removal of a rule never added and a
              template never instantiated mark what clears them, for
              ``DiagnosticBag.settle`` (tests/test_refusal_consequences.py).
              A bare
              ``DomainQuery`` noun names a declared position domain or, for a
              query kind in ``n.DIRECTION_QUERY_KINDS``, the direction domain the board
              minted; a Set Form's noun names a Position Domain alone, held by
              Derived and Pinned (the noun is a designer's string until this
              pass classifies it against ``game.positions``;
              tests/test_cell_set_form.py's noun grid).
Now illegal:  a subset source that
              names the same zone twice (``_check_subset_source``) -- a
              spelling fact, settled beside the other subset-shape guard.
              A rule parameter named ``hand`` (``_refuse_play_source_params``).
"""

from __future__ import annotations

from collections.abc import Mapping, Set
from dataclasses import is_dataclass, replace
from typing import assert_never
from cardlang.diagnostic_codes import Code
from cardlang.ast import nodes as n
from cardlang.board_domains import LINE_NOUN
from cardlang.attribution import cite_library, cite_named, cite_origin
from cardlang.diagnostics import DiagnosticBag, Refused, Said, Sentence, Slot, SlotKind, Span, Unless, text_slot
from cardlang.domains import CARD_AXIS_ROLES, SIMULTANEOUS_ROLES, Role, role_names
from cardlang.domains import ITERABLE_ROLES as _ITERATION_ROLES
from cardlang.runtime.values import content_noun
from cardlang.stdlib.enums import suit_names
from cardlang.stdlib.moves import KERNEL_MOVE_FORMS, LIBRARY_MOVE_TYPES, RULE_ENFORCED_MOVE_TYPE
from cardlang.types import Flavor
from cardlang.stdlib.rules import stdlib_rules
from cardlang.resolve.walk import _traverse, _walk
from cardlang.resolve.binders import _introduced_binders
from cardlang.resolve.reserved import _RESERVED_WHY, _refuse_play_source_params
from cardlang.resolve.slots import _MOVE_TYPE_SLOT_OFFERS, slot_strings
from cardlang.resolve.declared import (
    board_mints,
    _deck_known,
    _minted_directions,
    _simultaneous_role_refused,
    simultaneous_role_slot,
    _stamped_stdlib_rules,
    _unminted_direction,
)
from cardlang.resolve.classifier import _Categories, _may_be_a_membership, collection_nouns
from cardlang.resolve.classifier import _categories


def step(
    game: n.Game, library_rules: dict[str, n.RuleDef], bag: DiagnosticBag
) -> tuple[n.Game, dict[int, frozenset[str]]]:
    """The rule instantiation step. Returns the game with every rule
    concrete, and the binder sources whose query nouns it refused."""
    # Names that resolve to SOME rule template (local or library), independent
    # of whether that template ever successfully instantiates — the set
    # `active_rules names undefined rule` gates on below. Captured from the
    # ORIGINAL `game.rules` (before instantiation, which drops a local
    # template that fails to instantiate): a name is "undefined" only when no
    # template exists for it anywhere, never merely because its own
    # instantiation attempt hit some OTHER, already-separately-reported
    # mismatch (arity, missing arguments, …) — that conflation would pile a
    # spurious "undefined rule" note onto every such mismatch.
    known_rule_names: dict[str, n.RuleDef] = {
        **stdlib_rules(), **library_rules, **{r.name: r for r in game.rules}
    }

    # Library-rule splice and template instantiation: after this, every rule in
    # `game.rules` is a concrete (parameter-free) definition the runtime can
    # index by name.
    game = _instantiate_rules(game, library_rules, bag)

    # DomainQuery nouns validate BEFORE deep name resolution: a typo'd noun
    # (`any cel where square[cell] …`) changes the binder name, so the body's
    # `cell` reference would classify as unresolved first and mask the sharper
    # unknown-noun diagnostic (bag order is report order). After
    # `_instantiate_rules`, so instantiated rule bodies are covered too, and
    # before a rule's clause shapes are read, so a noun naming something else
    # is told what it names before its clause is judged by the query's shape.
    refused_binders = _refused_binder_sources(game, _categories(game), bag)

    rule_move_types = {m.name: m for m in game.move_types}
    for rule in game.rules:
        _resolve_rule(rule, rule_move_types, bag)
    _resolve_phase_level(game.phases, known_rule_names, bag)
    _check_rule_removes(game.phases, known_rule_names, bag)
    _check_rules_reach_a_trick(game, bag)
    return game, refused_binders


def _template_binders(rule: n.RuleDef, flavor: Flavor) -> set[str]:
    """Every binder a rule body introduces — a parameter sharing one of these
    names would be captured by the binder instead of substituted. A rule body
    can hold a movement, so its filter binder follows the game's flavor."""
    out: set[str] = set()
    for nd in _walk(rule):
        out.update(_introduced_binders(nd, flavor))
    return out


def _check_template(rule: n.RuleDef, bag: DiagnosticBag, flavor: Flavor) -> bool:
    """Validate a parameterized rule's declaration (Suit-only domains,
    corpus-first — recorded in roadmap.md, "Grammar surface deferred by the
    checker"; unique names; no binder capture; no parameter spelled like the
    Play Source). Returns False when instantiation cannot proceed."""
    ok = not _refuse_play_source_params(rule, bag)
    names = [p.name for p in rule.params]
    for dup in sorted({nm for nm in names if names.count(nm) > 1}):
        bag.error(
            f"rule " + cite_named(rule, f"'{rule.name}'") + f" declares more than one parameter named "
            f"'{dup}' — substitution binds by name, so one would silently "
            f"shadow the other",
            rule.span,
            code=Code.NAME_TAKEN,
        )
        ok = False
    binders = _template_binders(rule, flavor)
    for p in rule.params:
        if p.type_name != "Suit":
            bag.unknown(
                f"rule parameter '{p.name}: {p.type_name}' has an unsupported "
                f"domain — rule parameters support Suit only (corpus-first; "
                f"extend when a game needs another)",
                p.type_name,
                ("Suit",),
                rule.span,
                code=Code.NOT_YET_SUPPORTED,
            )
            ok = False
        if p.name in binders:
            bag.error(
                f"rule " + cite_named(rule, f"'{rule.name}'") + f" introduces a binder named '{p.name}', "
                f"shadowing its own parameter — rename one",
                rule.span,
                code=Code.NAME_TAKEN,
            )
            ok = False
    return ok


def substitute(
    node: object, mapping: dict[str, n.Expr], ref_kind: n.RefKind | None = None
) -> object:
    """Immutably replace every reference to a parameter with its argument
    expression — the ONE substitution mechanism, shared by the two constructs that
    splice a body into a site: rule-template instantiation (`_instantiate_rules`,
    below) and procedure expansion (`cardlang/expand.py`).

    The two differ only in when they run, which `ref_kind` expresses. Rule
    templates instantiate PRE-classification, where every `NameRef` is unresolved
    and a bare name match is all there is (`ref_kind=None`). Procedures expand
    POST-classification, so a parameter reference in the body carries
    `ref_kind == "local"` and the match can be exact — pass `ref_kind="local"` and
    a same-named zone or state variable can never be mistaken for the parameter."""
    if (
        isinstance(node, n.NameRef)
        and node.name in mapping
        and (ref_kind is None or node.ref_kind == ref_kind)
    ):
        return mapping[node.name]
    return _traverse(node, lambda _field, v: _substitute_value(v, mapping, ref_kind))


def _substitute_value(
    value: object, mapping: dict[str, n.Expr], ref_kind: n.RefKind | None = None
) -> object:
    if is_dataclass(value) and not isinstance(value, Span):
        return substitute(value, mapping, ref_kind)
    if isinstance(value, tuple):
        return tuple(_substitute_value(item, mapping, ref_kind) for item in value)
    return value


def _instantiate_rules(
    game: n.Game, library_rules: dict[str, n.RuleDef], bag: DiagnosticBag
) -> n.Game:
    """Resolve `active_rules` references against the game's own rules first,
    then the family libraries it `uses` (`library_rules`), then the standard
    library (`library stdlib`, `cardlang/stdlib/rules.cardlang`) — one splice,
    driven by activation, for every tier:

    - a reference to a library rule the game does not define splices the
      library body into `game.rules`, after the game's own rules, in the order
      references first name them (defining a rule under a library name is
      rejected — a local copy would drift from the shared body silently); a
      library rule no reference names is not spliced, and a library template
      no reference instantiates is not an error;
    - a reference with arguments instantiates a parameterized rule (library or
      local) by substituting the arguments into the template body; the local
      template is replaced by its instance in place, so the runtime's
      name->rule index only ever sees concrete definitions.

    Every mismatch is a diagnostic, never a silent drop: args on a
    parameter-free rule, a parameterized rule referenced bare, arity/domain
    mismatches, two instantiations under one name with different arguments,
    and a local template no reference ever instantiates.

    Only `plain`/`add` refs reach any of that: the grammar gives `-NAME`
    (remove) and `override NAME` no argument list at all (cardlang.lark's
    `rule_remove`/`rule_override` productions), so neither can ever
    instantiate a template — asking one for "arguments" would be an
    unsatisfiable diagnostic (no source text repairs it). Both resolve by
    NAME alone: `remove` targets a rule a `plain`/`add` reference already
    activated in the same runtime-consulted scope (validated structurally by
    `_check_rule_removes`, since `compute_active_rules` only ever
    removes a name it finds already present); `override` has no runtime
    support yet at all and is rejected unconditionally, once, by
    `_resolve_phase_item` — this loop skips it so that is the only diagnostic
    a game ever sees for it, not a second, unsatisfiable "pass arguments"
    alongside "not yet supported"."""
    lib = _stamped_stdlib_rules()
    local = {r.name: r for r in game.rules}
    for r in game.rules:
        if r.name in lib:
            shadowed = lib[r.name]
            assert shadowed.origin is not None
            bag.error(
                f"rule " + cite_named(r, f"'{r.name}'") + f" shadows " + cite_origin(shadowed.origin, shadowed.span)
                + " — delete the local definition (`active_rules` resolves it "
                "from the library), or rename it if the body genuinely differs",
                r.span,
                code=Code.NAME_TAKEN,
            )

    def named(name: str, template: n.RuleDef) -> Said:
        """The rule a reference names: the game's by its name, a library's in
        the designer's words, standing on its text."""
        if template.origin is None:
            return cite_named(template, f"rule '{name}'")
        return cite_origin(template.origin, template.span)

    suits = suit_names(game.deck) if _deck_known(game.deck) else None
    # rule name -> (argument key, concrete instance)
    instances: dict[str, tuple[tuple[str, ...], n.RuleDef]] = {}
    lib_order: list[str] = []
    # Each DISTINCT template's declaration validates once total, however many
    # refs instantiate it (or attempt to) — never once per activating phase
    # (without the cache, a defective template referenced from two phases would
    # repeat its diagnostics; `_check_template` is also the bottom loop's
    # "never instantiated" fallback below, so the cache spans both call sites).
    template_checked: dict[str, bool] = {}
    # The slots of each template's activation arguments refused as no suit.
    refused_arguments: dict[str, set[str]] = {}

    def check_template_once(name: str, template: n.RuleDef) -> bool:
        if name not in template_checked:
            template_checked[name] = _check_template(template, bag, game.content_flavor)
        return template_checked[name]

    for nd in _walk(game):
        if not isinstance(nd, n.ActiveRules):
            continue
        for ref in nd.refs:
            if ref.delta in ("remove", "override"):
                continue
            template = local.get(ref.name, library_rules.get(ref.name, lib.get(ref.name)))
            if template is None:
                continue  # undefined name: reported by _resolve_phase_level
            if not template.params:
                if ref.args:
                    bag.error(
                        named(ref.name, template)
                        + " takes no parameters — drop the argument list",
                        ref.span,
                        code=Code.WRONG_ARGUMENT_COUNT,
                    )
                elif ref.name not in local and ref.name not in instances:
                    instances[ref.name] = ((), template)
                    lib_order.append(ref.name)
                continue
            if not ref.args:
                bag.error(
                    named(ref.name, template) + " is parameterized "
                    f"({', '.join(f'{p.name}: {p.type_name}' for p in template.params)}) "
                    "— pass arguments: " + cite_named(template, f"`{ref.name}(…)`"),
                    ref.span,
                    code=Code.WRONG_ARGUMENT_COUNT,
                )
                continue
            if len(ref.args) != len(template.params):
                bag.error(
                    named(ref.name, template) + f" takes {len(template.params)} "
                    f"argument(s), got {len(ref.args)}",
                    ref.span,
                    code=Code.WRONG_ARGUMENT_COUNT,
                )
                continue
            if not check_template_once(ref.name, template):
                continue
            args_ok = True
            for arg, p in zip(ref.args, template.params):
                if not isinstance(arg, n.NameRef) or (
                    suits is not None and arg.name not in suits
                ):
                    of: Said = "" if template.origin is None else " of " + named(ref.name, template)
                    bag.unknown(
                        f"argument for rule parameter '{p.name}: Suit'" + of
                        + " must be a suit literal (one of the deck's suits)",
                        arg.name if isinstance(arg, n.NameRef) else "",
                        suits or (),
                        ref.span,
                        code=Code.WRONG_ARGUMENT,
                        slot=None if arg.span is None else text_slot(arg.span),
                    )
                    if arg.span is not None:
                        refused_arguments.setdefault(ref.name, set()).add(text_slot(arg.span).name)
                    args_ok = False
            if not args_ok:
                continue
            key = tuple(a.name for a in ref.args if isinstance(a, n.NameRef))
            if ref.name in instances:
                if instances[ref.name][0] != key:
                    bag.error(
                        named(ref.name, template) + " is instantiated with different "
                        f"arguments elsewhere in this game — one instantiation "
                        f"per rule name (activate under distinct names when a "
                        f"game needs two)",
                        ref.span,
                        code=Code.CONFLICTING_CLAUSES,
                    )
                continue
            mapping = {p.name: a for p, a in zip(template.params, ref.args)}
            inst = substitute(replace(template, params=()), mapping)
            assert isinstance(inst, n.RuleDef)
            instances[ref.name] = (key, inst)
            if ref.name not in local:
                lib_order.append(ref.name)
    rules: list[n.RuleDef] = []
    for r in game.rules:
        if not r.params:
            rules.append(r)
        elif r.name in instances:
            rules.append(instances[r.name][1])  # instance replaces its template
        else:
            check_template_once(r.name, r)  # surface declaration defects even here
            bag.error(
                f"rule " + cite_named(r, f"'{r.name}'") + f" is parameterized but never instantiated — "
                f"reference it from `active_rules` with arguments, or delete it "
                f"(its body would otherwise go entirely unchecked)",
                r.span,
                code=Code.UNUSED_DECLARATION,
                # A misspelled activation, or its arguments, fixed.
                unless=(
                    Unless(SlotKind.RULE, frozenset({r.name})),
                    Unless(SlotKind.TEXT, frozenset(suits or ()), frozenset(refused_arguments.get(r.name, ()))),
                ),
            )
    rules += [instances[name][1] for name in lib_order]
    return replace(game, rules=tuple(rules)) if tuple(rules) != game.rules else game


def _check_rule_removes(
    phases: tuple[n.Phase, ...],
    rules: Mapping[str, n.RuleDef],
    bag: DiagnosticBag,
    inherited: frozenset[str] = frozenset(),
) -> None:
    """`-X` remove reachability, over a phase, its modes and its sub-phases.

    `-X` and (unsupported today) `override X` can never instantiate a rule
    (`_instantiate_rules`'s docstring) — they only resolve X by NAME against a
    rule a `plain`/`add` reference already activated. A reference to a name no
    `plain`/`add` ever activates in the scope the runtime actually consults is
    a structural no-op forever: `runtime/active_rules.py`'s `compute_active_rules`
    builds the set down the chain of enclosing phases, each starting from its
    parent's unconditional set (or from nothing when its own entries hold a
    plain one), applying its OWN `active_rules:` entries, and layering its
    currently-active MODES on top. This check mirrors that shape: a `remove`
    inside a phase's own list validates against what the phase inherits UNION
    its own list; a `remove` inside a mode validates against that UNION the
    mode's own. What a phase hands down is what its own list leaves
    unconditionally — its modes' deltas are conditional, so a sub-phase's
    `-X` of a mode's `+X` is refused for the reason a sibling mode's is.

    It deliberately does NOT widen the scope to sibling modes. Modes are
    independent conditions, so two of them may hold at once and one's `+X`
    genuinely can be live while another's `-X` runs — but only in orders no
    declaration site fixes, so a `-X` that depends on a sibling is a race the
    designer cannot read off the page. It also does not model order WITHIN one
    list (an add-then-remove of the same name earlier in a phase's own list
    still counts as "added" for a mode's cluster check) — an accepted
    imprecision for a construct the corpus does not use at all (issue #103
    records the residual)."""
    for phase in phases:
        own_refs = [
            ref for item in phase.items if isinstance(item, n.ActiveRules) for ref in item.refs
        ]
        base = frozenset() if any(r.delta == "plain" for r in own_refs) else inherited
        own_added = set(base) | {r.name for r in own_refs if r.delta in ("plain", "add")}
        _validate_removes(own_refs, own_added, rules, bag)

        for mode in (i for i in phase.items if isinstance(i, n.Mode)):
            mode_refs = [ref for block in mode.active_rules for ref in block.refs]
            cluster_added = own_added | {r.name for r in mode_refs if r.delta in ("plain", "add")}
            _validate_removes(mode_refs, cluster_added, rules, bag)

        # What the list leaves, applied in its own order as the runtime does: a
        # rule removed and then added again is handed down.
        kept = list(base)
        for r in own_refs:
            if r.delta in ("plain", "add"):
                kept.append(r.name)
            elif r.delta == "remove":
                kept = [name for name in kept if name != r.name]
        handed_down = frozenset(kept)
        children = tuple(i for i in phase.items if isinstance(i, n.Phase))
        _check_rule_removes(children, rules, bag, handed_down)


def _reaches_a_trick_round(
    node: object,
    move_types: Mapping[str, n.MoveTypeDef],
    procedures: Mapping[str, n.ProcedureDef],
    followed: set[tuple[str, str]],
) -> bool:
    """Whether a trick round runs anywhere `node` reaches: in its own subtree,
    in the effect of a move type an offer in it puts in play, or in a
    procedure a `run` in it splices, followed through offers and runs within
    them. A move type's effect runs at the site that offers it, and a
    procedure's body at the `run`, so a round there is asked with that site's
    phase's rules. `legal_moves:` is configuration nothing runs, so it offers
    nothing here."""
    for nd in _walk(node):
        if isinstance(nd, n.TrickRound):
            return True
        reached: list[tuple[str, object]] = []
        if isinstance(nd, n.RunStmt) and nd.name in procedures:
            reached.append(("procedure", procedures[nd.name]))
        for (cls, field_name), puts_in_play in _MOVE_TYPE_SLOT_OFFERS.items():
            if not puts_in_play or cls is n.LegalMoves or not isinstance(nd, cls):
                continue
            reached += [
                ("move_type", move_types[name])
                for name in slot_strings(nd, field_name)
                if name in move_types
            ]
        for kind, definition in reached:
            key = (kind, getattr(definition, "name"))
            if key not in followed:
                followed.add(key)
                if _reaches_a_trick_round(definition, move_types, procedures, followed):
                    return True
    return False


def _check_rules_reach_a_trick(game: n.Game, bag: DiagnosticBag) -> None:
    """A phase's `active_rules:` and modes are asked only by a trick round: a
    rule at its card decision, a mode's condition by its plays
    (`runtime/active_rules.py`). The rounds that ask them are the ones the
    phase's subtree runs, nested phases included, since a sub-phase builds its
    set on its parent's. A phase holding either with no trick round in reach
    is refused, naming the holder: its rules would never apply. A climbing
    round asks no rule, so it does not count."""
    move_types = {m.name: m for m in game.move_types}
    procedures = {p.name: p for p in game.procedures}
    for phase in (nd for nd in _walk(game) if isinstance(nd, n.Phase)):
        slots = [
            item for item in phase.items if isinstance(item, n.ActiveRules) and item.refs
        ]
        modes = [item for item in phase.items if isinstance(item, n.Mode)]
        if not (slots or modes) or _reaches_a_trick_round(phase, move_types, procedures, set()):
            continue
        holds: list[Said] = []
        if slots:
            holds.append("turns on rules with `active_rules:`")
        if modes:
            names = Sentence.join(", ", (cite_named(m, f"'{m.name}'") for m in modes))
            holds.append(f"declares {'mode' if len(modes) == 1 else 'modes'} " + names)
        bag.error(
            f"phase '{phase.name}' " + Sentence.join(" and ", holds) + ", but no trick round "
            f"runs in it or in a phase inside it: a rule is asked, and a mode's "
            f"condition changes, only when a trick round offers a card (`round "
            f"<move> from ... source ... into ...`), so none of it would ever "
            f"apply — move it to the phase that runs the trick round, or, for a "
            f"trick played with chosen moves, filter the move instead (`where "
            f"follows_lead(card, <pile>)`), or, for a move made by an `offer`, "
            f"state the condition in the move type's `when:`",
            (slots[0] if slots else modes[0]).span,
            code=Code.GAME_RULE_NEVER_CONSULTED,
        )


def _validate_removes(
    refs: list[n.RuleRef], added: set[str], rules: Mapping[str, n.RuleDef], bag: DiagnosticBag
) -> None:
    for ref in refs:
        if ref.delta == "remove" and ref.name not in added:
            rule = rules.get(ref.name)

            def named(words: str) -> Said:
                return words if rule is None else cite_named(rule, words)

            bag.error(
                named(f"`-{ref.name}`") + " removes a rule that is never added in scope "
                "here (this phase's own `active_rules:`, an enclosing phase's, or "
                "one of this phase's modes) — add " + named(f"`{ref.name}`") + " or " + named(f"`+{ref.name}`")
                + " there, or delete this removal",
                ref.span,
                code=Code.MISSING_DECLARATION,
                # A misspelled rule added in scope, fixed.
                unless=Unless(SlotKind.RULE, frozenset({ref.name}), frozenset(a for a in added if a not in rules)),
            )


def _check_rule_reaches_a_reader(
    rule: n.RuleDef, move_types: Mapping[str, n.MoveTypeDef], bag: DiagnosticBag
) -> None:
    """Refuse a rule no decision site consults (decisions.md "Rule demand
    forms", "Surface totality"). A rule binds at the trick round's card
    decision and nowhere else, so its `constrains:` is accepted only when it
    names the move type that decision asks about, and every other target is
    refused once, naming the construct that makes the move as the place its
    condition goes: a move type the game declares, its `when:`; a family
    library's move type, the library's `when:` or a move type and offer of
    the game's own; a kernel move type, the form `KERNEL_MOVE_FORMS` records
    for it; an absent clause, the trick move type. Any other spelling is
    unknown. Each fix is applied and checked by tests/test_rule_constrains.py.

    Runs after `_instantiate_rules`, so spliced library rules and
    instantiated templates are checked on the same path as hand-written ones;
    `move_types` is the game's after the splice, a family library's included.
    """
    target = rule.constrains
    named = cite_named(rule, f"'{rule.name}'")
    trick = (
        f"a rule binds only at the trick round's card decision, which asks "
        f"about `{RULE_ENFORCED_MOVE_TYPE}`, so this rule would never fire"
    )
    if target is None:
        bag.error(
            "rule " + named + " constrains no move type (the `constrains:` clause is "
            f"absent), which no decision site consults: {trick}. Name "
            f"`{RULE_ENFORCED_MOVE_TYPE}` in its `constrains:`.",
            rule.span,
            code=Code.GAME_RULE_NEVER_CONSULTED,
        )
        return
    declared = move_types.get(target) if target != RULE_ENFORCED_MOVE_TYPE else None
    if declared is not None and declared.origin is None:
        bag.error(
            "rule " + named + " constrains " + cite_named(declared, f"`{target}`")
            + f", a move type this game declares, but {trick}: write the condition "
            f"in its `when:` instead; a condition that reads the whole position is "
            f"a function the `when:` calls",
            rule.span,
            code=Code.GAME_RULE_NEVER_CONSULTED,
        )
        return
    if declared is not None and declared.origin is not None:
        bag.error(
            "rule " + named + " constrains " + cite_named(declared, f"`{target}`")
            + ", a move type of " + cite_library(declared.origin.library, declared.span)
            + f", but {trick}. A condition every game using the library shares "
            f"belongs in that move type's `when:` in the library; for this game "
            f"alone, offer a move type of the game's own carrying the condition "
            f"in its `when:`, in place of `{target}`, writing the offer in the game "
            f"wherever the library's own procedure makes it",
            rule.span,
            code=Code.GAME_RULE_NEVER_CONSULTED,
        )
        return
    form = KERNEL_MOVE_FORMS.get(target)
    if form is None:
        bag.unknown(
            "rule " + named + f" constrains unknown move type '{target}'",
            target,
            (*move_types, *KERNEL_MOVE_FORMS),
            rule.span,
            code=Code.UNKNOWN_MOVE_TYPE,
        )
        return
    head = "rule " + named + f" constrains '{target}', which no decision site consults: {trick}. "
    match form:
        case "trick_round":
            if rule.demands is None and rule.exempts is None:
                bag.error(
                    "rule " + named + " enforces nothing: it declares neither a "
                    "`demands:` card set nor an `exempts:` set, so activating it "
                    "cannot change which cards are legal. Give it a `demands:` (with "
                    "its `if_impossible:` fallback) or an `exempts:`, or delete it — "
                    "`applies_when:` alone selects when a rule fires, not what it "
                    "does.",
                    rule.span,
                    code=Code.MISSING_DECLARATION,
                )
        case "offer":
            bag.error(
                head + f"Declare `{target}` as a move type of the game, with the "
                f"condition in its `when:`, and offer it.",
                rule.span,
                code=Code.GAME_RULE_NEVER_CONSULTED,
            )
        case "chosen_movement":
            bag.error(
                head + "A card passed from hand to hand is a chosen movement "
                "(`move chosen N cards from ... to ...`): state the condition on "
                "the movement, its `chosen N` or a `where` filter.",
                rule.span,
                code=Code.GAME_RULE_NEVER_CONSULTED,
            )
        case "number_choice":
            bag.error(
                head + "A number a player names is a `choose integer in ...`: state "
                f"the condition in its range or its `excluding`; or declare "
                f"`{target}` as a move type of the game, with the condition in its "
                f"`when:`, and offer it.",
                rule.span,
                code=Code.GAME_RULE_NEVER_CONSULTED,
            )
        case "climb_round":
            bag.error(
                head + "A climb round's play is legal by the round's `follows` "
                "function: when the game declares that function, state the "
                "condition there; a Registered Engine's `follows` fixes the "
                "legality, and the game cannot add to it.",
                rule.span,
                code=Code.GAME_RULE_NEVER_CONSULTED,
            )
        case _:
            assert_never(form)


def _resolve_rule(
    rule: n.RuleDef, move_types: Mapping[str, n.MoveTypeDef], bag: DiagnosticBag
) -> None:
    _check_rule_reaches_a_reader(rule, move_types, bag)
    # A `demands` can filter the legal set to empty; the rule must say what
    # happens then (`if_impossible`) rather than relying on a silent default.
    if rule.demands is not None and rule.if_impossible is None:
        bag.error(
            f"rule " + cite_named(rule, f"'{rule.name}'") + f" has a card-set `demands` but no `if_impossible`: "
            f"declare the fallback when no card satisfies it (`if_impossible: hand` "
            f"to play any card, or `error(...)` to reject the move)",
            rule.span,
            code=Code.MISSING_DECLARATION,
        )


def _resolve_phase_level(
    phases: tuple[n.Phase, ...], known_rule_names: Mapping[str, n.RuleDef], bag: DiagnosticBag
) -> None:
    """Resolve a set of sibling phases, then recurse into each one's children.

    A `transition_to: Y` inside a mode names a sibling MODE of that mode — the
    modes of one phase body are one condition's sides, so the namespace a
    target resolves against is the enclosing phase's own modes.
    """
    sibling_names = {p.name for p in phases}
    for phase in phases:
        # Combination validity (decisions.md "Surface totality"): the runtime
        # declares only a phase's FIRST state block and runs the lifecycle
        # hooks only on a `repeat until` phase — reject what it would
        # silently drop.
        state_blocks = [i for i in phase.items if isinstance(i, n.StateBlock)]
        if len(state_blocks) > 1:
            bag.error(
                f"phase '{phase.name}' declares more than one `state {{ }}` "
                f"block — merge the declarations into one",
                state_blocks[1].span,
                code=Code.WRITTEN_TWICE,
            )
        if phase.qualifier is None or phase.qualifier.kind != "repeat_until":
            for hook in phase.items:
                if isinstance(hook, (n.BeforeEach, n.AfterEach)):
                    kw = "before_each" if isinstance(hook, n.BeforeEach) else "after_each"
                    bag.error(
                        f"`{kw}` runs per iteration of a `repeat until` phase; "
                        f"phase '{phase.name}' has no iteration — put the "
                        f"statements in the phase body",
                        hook.span,
                        code=Code.OUT_OF_PLACE,
                    )
        modes = tuple(i for i in phase.items if isinstance(i, n.Mode))
        mode_names = {m.name for m in modes}
        for item in phase.items:
            scope = mode_names if isinstance(item, n.Mode) else sibling_names
            _resolve_phase_item(item, scope, known_rule_names, bag)
        # After the transitions it reads are resolved, so a refused target is
        # told before any role it leaves a mode in.
        _check_modes(phase, bag)
        children = tuple(i for i in phase.items if isinstance(i, n.Phase))
        _resolve_phase_level(children, known_rule_names, bag)


def _transition_targets(mode_names: Set[str], source: str) -> frozenset[str]:
    """The modes a transition declared in `source` may name: its siblings."""
    return frozenset(mode_names) - {source}


def _target_slot(transition: n.TransitionTo) -> Slot:
    """The slot of a transition's target."""
    return Slot(SlotKind.MODE, f"{transition.span}")


def _resolve_transition(
    transition: n.TransitionTo, mode_names: set[str], source: str, bag: DiagnosticBag
) -> None:
    if transition.mode not in mode_names:
        bag.unknown(
            f"transition_to target '{transition.mode}' is not a sibling mode "
            f"of this phase — a transition ends one condition and begins "
            f"another, so its target is a `mode` declared beside this one",
            transition.mode,
            _transition_targets(mode_names, source),
            transition.span,
            code=Code.UNKNOWN_MODE,
            slot=_target_slot(transition),
        )
    if transition.event.move_type not in LIBRARY_MOVE_TYPES:
        bag.unknown(
            f"transition event names unknown move type '{transition.event.move_type}'",
            transition.event.move_type,
            ("play_to_trick",),
            transition.event.span,
            code=Code.UNKNOWN_MOVE_TYPE,
        )
    elif transition.event.move_type != "play_to_trick":
        bag.error(
            f"transitions fire from trick plays only today: the event move "
            f"type must be `play_to_trick`, not "
            f"'{transition.event.move_type}' (roadmap.md)",
            transition.event.span,
            code=Code.NOT_YET_SUPPORTED,
        )


def _check_modes(phase: n.Phase, bag: DiagnosticBag) -> None:
    """The mode-role invariant: every mode is exactly one of a transition
    SOURCE or a transition TARGET.

    A mode is one side of one condition — the "before", which declares the
    transitions that end it, or the "after", which a sibling names. The two
    rejected shapes are not hypothetical; both ran silently wrong before this
    Owner Guard existed, and `check_dsl` accepted both:

    - BOTH (a chain, or a self-loop): the runtime keys a mode's activity on ITS
      target having fired, not on its having been entered, so the middle mode
      of a three-mode chain is active from the very start and its transition is
      live before anything reaches it.
    - NEITHER (an orphan): a transition-less mode holds only once its own name
      has fired, which for a mode nobody targets never happens — so its
      `active_rules:` silently never apply.
    """
    modes = [i for i in phase.items if isinstance(i, n.Mode)]
    mode_names = {m.name for m in modes}
    targeted = {t.mode for m in modes for t in m.transitions if t.mode in mode_names}
    # The targets refused where they are written: fixed, each names a mode.
    refused_targets = frozenset(
        _target_slot(t).name for m in modes for t in m.transitions if t.mode not in mode_names
    )

    # A target belongs to ONE condition. Two sources naming the same target
    # read as "two conditions that happen to end together", but the runtime
    # keys a source's activity on its TARGET having fired, not on the source's
    # own identity — so either trigger ends both, and a condition can end
    # without its own event ever occurring. Rejected rather than given that
    # meaning: nobody writing two separate conditions wants one to cancel the
    # other. Lifting this means keying activity on the mode rather than the
    # target name (issue #283).
    claimed_by: dict[str, str] = {}
    for mode in modes:
        for transition in mode.transitions:
            if transition.mode not in mode_names:
                continue
            owner = claimed_by.setdefault(transition.mode, mode.name)
            if owner != mode.name:
                bag.error(
                    f"modes '{owner}' and '{mode.name}' both transition to "
                    f"'{transition.mode}' — a target is the far side of one "
                    f"condition, and sharing it makes either trigger end both. "
                    f"Give each condition its own target mode",
                    transition.span,
                    code=Code.MODES_MUST_PAIR_UP,
                )

    for mode in modes:
        is_source = bool(mode.transitions)
        is_target = mode.name in targeted
        if is_source and is_target:
            bag.error(
                f"mode '{mode.name}' is both entered by a transition and "
                f"declares one — modes are independent two-sided conditions, "
                f"not a chain. Give each condition its own pair of modes, or "
                f"use a state variable with `applies_when` for a progression "
                f"through three or more stages",
                mode.span,
                code=Code.MODES_MUST_PAIR_UP,
            )
        elif not is_source and not is_target:
            bag.error(
                f"mode '{mode.name}' is never active: nothing transitions to "
                f"it and it declares no transition of its own, so its "
                f"`active_rules:` would never apply. Have a sibling mode "
                f"`transition_to: {mode.name}`, or put these rules on the "
                f"phase itself",
                mode.span,
                code=Code.UNUSED_DECLARATION,
                unless=Unless(SlotKind.MODE, frozenset({mode.name}), refused_targets),
            )


def _resolve_phase_item(
    item: n.PhaseItem,
    sibling_names: set[str],
    known_rule_names: Mapping[str, n.RuleDef],
    bag: DiagnosticBag,
) -> None:
    if isinstance(item, n.ActiveRules):
        for ref in item.refs:
            if ref.name not in known_rule_names:
                bag.unknown(
                    f"active_rules names undefined rule '{ref.name}'",
                    ref.name,
                    known_rule_names,
                    ref.span,
                    code=Code.UNKNOWN_GAME_RULE,
                    slot=Slot(SlotKind.RULE, ref.name),
                    # A reference names a rule taking as many arguments.
                    fixes=(r for r, rule in known_rule_names.items() if len(rule.params) == len(ref.args)),
                )
            if ref.delta == "override":
                overridden = known_rule_names.get(ref.name)
                words = f"`override {ref.name}`"
                bag.error(
                    (words if overridden is None else cite_named(overridden, words))
                    + " is not yet supported by the runtime "
                    "(roadmap.md) — use `add`/`remove` deltas",
                    ref.span,
                    code=Code.NOT_YET_SUPPORTED,
                )
    elif isinstance(item, n.LegalMoves):
        for name in item.move_types:
            if name not in LIBRARY_MOVE_TYPES:
                bag.unknown(
                    f"legal_moves names unknown move type '{name}'",
                    name,
                    LIBRARY_MOVE_TYPES,
                    item.span,
                    code=Code.UNKNOWN_MOVE_TYPE,
                )
    elif isinstance(item, n.Mode):
        for block in item.active_rules:
            _resolve_phase_item(block, sibling_names, known_rule_names, bag)
        for transition in item.transitions:
            _resolve_transition(transition, sibling_names, item.name, bag)
    elif isinstance(item, (n.Phase, n.StateBlock, n.BeforeEach, n.AfterEach)):
        # Phases recurse via the level walk; state blocks resolve later; hook
        # bodies are plain statement sequences with nothing item-level to check.
        pass
    else:
        # `item` is a statement — nothing to resolve at phase-item level. The
        # annotated assignment is the exhaustiveness pin: a new PhaseItem block
        # kind falls here and fails mypy until this function decides what to do
        # with it. (No statement walk hangs off this arm: with nothing to check
        # at the leaves, a walk recursing into every body would be vacuously
        # green — checking nothing while presenting as a guarantee.)
        _only_statements_reach_here: n.Stmt = item


def _refused_binder_sources(
    game: n.Game, cats: _Categories, bag: DiagnosticBag
) -> dict[int, frozenset[str]]:
    """Validate every binder source a check refuses before names are
    classified -- a query's noun, a simultaneous block's role -- and return,
    by node, the binders the fixes of each refused source would bind. A
    collection set that may be a membership is `_rewrite`'s, which holds the
    lexical scope."""
    refused: dict[int, frozenset[str]] = {}
    for nd in _walk(game):
        if isinstance(nd, n.DomainQuery):
            if _check_domain_query(nd, game, cats, bag):
                refused[id(nd)] = _binders_a_query_takes(nd, game, cats.flavor)
        elif isinstance(nd, n.SubsetQuery):
            _check_subset_source(nd, bag)
        elif isinstance(nd, n.EachSimultaneous) and _simultaneous_role_refused(nd):
            bag.error(
                f"`each {nd.role} simultaneously` is not runnable — "
                f"simultaneous moves are per "
                f"{' or '.join(role_names(SIMULTANEOUS_ROLES))}",
                nd.span,
                code=Code.WRONG_SORT_OF_NAME,
                refuses=Refused(simultaneous_role_slot(nd), frozenset(role_names(SIMULTANEOUS_ROLES))),
            )
            refused[id(nd)] = frozenset(role_names(SIMULTANEOUS_ROLES))
    return refused


def _spelled_zone(member: n.Expr) -> str | None:
    """How a subset-source member is spelled, for the same-zone check: a bare
    name, a name with a literal index, or a name with a named index -- the
    shapes `zone_expr` admits. Two members that spell the same are the same
    zone. A computed index cannot be told apart statically and answers None,
    so it never matches."""
    match member:
        case n.NameRef():
            return member.name
        case n.Subscript(obj=n.NameRef() as base, index=n.IntLit() as idx):
            return f"{base.name}[{idx.value}]"
        case n.Subscript(obj=n.NameRef() as base, index=n.NameRef() as idx):
            return f"{base.name}[{idx.name}]"
        case _:
            return None


def _check_subset_source(sq: n.SubsetQuery, bag: DiagnosticBag) -> None:
    """The same zone named twice in one subset source (`[table, table]`).
    The pool is the members' contents concatenated, so the sentence
    would count every card twice and say nothing a designer meant; it is
    refused naming the spelling. A name fact -- two members spell the same --
    settled here beside the other subset-shape guard, not in the type layer:
    whether each member IS a zone or a card collection is the type layer's
    per-member Owner Guard (`typecheck._check_card_source`)."""
    seen: set[str] = set()
    for member in sq.source:
        spelled = _spelled_zone(member)
        if spelled is None:
            continue
        if spelled in seen:
            bag.error(
                f"`{spelled}` appears twice in one subset source — name each "
                f"zone once; a card is counted once per zone it is drawn from",
                member.span,
                code=Code.WRITTEN_TWICE,
            )
        seen.add(spelled)


def _bare_noun_refusal(
    nd: n.DomainQuery, head: str, game: n.Game, cats: _Categories, universe: str
) -> str | None:
    """The refusal of a bare position query whose noun is a name of another
    kind, in words that say what the name is and a sentence for it that
    checks; None for a name resolve does not know, which the caller refuses
    as an unknown position domain. The kinds are resolve's own: the name
    categories `_classify` reads, the definitions, the reserved words
    (`_RESERVED_WHY`), and the binders the language fixes."""
    reach = (
        "gathers the members of a position domain"
        if nd.kind not in n.DIRECTION_QUERY_KINDS
        else "ranges over a position domain"
    )
    for name in dict.fromkeys((nd.binder, nd.spelled)):
        said = _what_a_bare_noun_names(name, nd.kind, game, cats)
        if said is not None:
            what, fix = said
            return f"`{head}` {reach}, and `{name}` is {what} -- {fix or universe}"
    return None


def _what_a_bare_noun_names(
    name: str, kind: n.DomainQueryKind, game: n.Game, cats: _Categories
) -> tuple[str, str | None] | None:
    """What `name` is to resolve, and the sentence that says what a bare query
    over it meant, when one exists (else None, and the caller names the
    position domains)."""
    zone = next((z for z in game.zones if z.name == name), None)
    if zone is not None:
        ref = name if zone.index is None else f"{name}[…]"
        what = "a zone" if zone.index is None else "a zone family"
        if cats.flavor == "piece":
            return what, (
                f"a piece game reads a zone's pieces in a movement's `where` "
                f"filter (`move all pieces from {ref} where <pred> to <zone>`)"
            )
        return what, f"the cards in it satisfying a predicate are `cards in {ref} where <pred>`"
    if name == n.SUBSET_BINDER and cats.flavor == "card":
        return "the subset binder", (
            "subsets are asked with `of`: "
            "`number of subsets of <n> [or more] cards in <zone> where <pred>`"
        )
    if name == "piece" and cats.flavor == "piece":
        return "the piece binder of a movement's `where` filter", (
            "a movement filters pieces: `move all pieces from <zone> where <pred> to <zone>`"
        )
    if name == "seat":
        return "a player's place in the turn ring", (
            f"the seats are the players: write "
            f"`{_player_register_spelling(kind)} where <pred>`"
        )
    if name in _RESERVED_WHY:
        return f"a reserved word ({_RESERVED_WHY[name]})", None
    if name in cats.state_vars:
        return "a state variable", None
    if name in cats.ranks and cats.flavor == "card":
        return "a rank", None
    if name in cats.suits and cats.flavor == "card":
        return "a suit", None
    if name in cats.enums | cats.ranks | cats.suits:
        return "an enum value", None
    for label, defs in (
        ("a function", game.functions),
        ("a procedure", game.procedures),
        ("a move type", game.move_types),
        ("a rule", game.rules),
        ("a phase", game.phases),
    ):
        if any(d.name == name for d in defs):
            return label, None
    return None


def _player_register_spelling(kind: n.DomainQueryKind) -> str:
    """The player register's head for the same kind of query."""
    match kind:
        case "any":
            return "any player"
        case "all":
            return "all players"
        case "count":
            return "number of players"
        case "set":
            return "players"
        case unreachable:
            assert_never(unreachable)


def _check_domain_query(
    nd: n.DomainQuery, game: n.Game, cats: _Categories, bag: DiagnosticBag
) -> bool:
    """Validate a positional-quantifier noun (decisions.md "Boards and cells"),
    True where the noun is refused.

    A BARE form (`source is None`) ranges over a declared position domain,
    and a query kind in `n.DIRECTION_QUERY_KINDS` also over the direction
    domain the board minted (`_minted_directions`); such a query naming a
    `dir` no board minted is refused naming what it lacks
    (`_unminted_direction`), and the Set Form, which gathers positions alone,
    is refused naming the direction domain wherever `dir` is not a declared
    position domain. A COLLECTION form (`in <expr>`) ranges over the members
    of one of the game's position domains or over the board's lines
    (`LINE_NOUN`); a bare `line` noun on a board is offered the collection
    form. A noun naming a name of another kind is refused saying what it is
    (`_bare_noun_refusal`). The collection set whose noun is a name the game
    binds is left to `_rewrite`, which holds the lexical scope and refuses an
    unparenthesized membership there. The plural convention is a resolve
    Owner Guard, not a grammar one: `any` takes the singular noun,
    `all`/`number of`/the Set Form the plural (singular + "s"); a singular
    where the plural is required is guided to the plural spelling, an unknown
    noun to the declared universe.

    suit/rank quantifiers never reach here: QNOUN excludes those spellings, so
    `any suit where …` is the fixed `Quantifier` form (guarded in a piece game
    by the CARD_AXIS_ROLES case below) -- the noun exclusion IS that guard."""
    phrase = n.DOMAIN_QUERY_KIND_PHRASE[nd.kind]
    declared = {p.name for p in game.positions}
    lack = _unminted_direction(game, nd.binder)
    universe = (
        f"declared position domains: {', '.join(sorted(declared))}"
        if declared
        else "this game declares no position domains"
    )
    if nd.source is None:
        head = n.domain_query_head(nd.kind, nd.spelled)
        if nd.kind in n.DIRECTION_QUERY_KINDS:
            directions = _minted_directions(game)
        else:
            # The Set Form gathers positions; the direction domain is not one.
            directions = frozenset()
            if nd.binder not in declared and (
                nd.binder in _minted_directions(game) or lack is not None
            ):
                bag.error(_direction_is_no_position(nd.kind, head, nd.binder, universe), nd.span, code=Code.WRONG_SORT_OF_NAME)
                return True
        if lack is not None:
            bag.error(f"`{head}` ranges over the board directions, but {lack}", nd.span, code=Code.MISSING_DECLARATION)
            return True
        if directions:
            universe += (
                "; the board direction domain: "
                + ", ".join(sorted(directions))
            )
        if nd.binder == LINE_NOUN and nd.binder not in declared and game.board is not None:
            # A bare `any line where …`: lines are quantified from a
            # collection, so the designer dropped the `in <collection>`.
            universe += (
                f" (a `{nd.binder}` is quantified from a collection: "
                f"`{n.collection_query_head(nd.kind, nd.spelled)} in <collection> where ...`)"
            )
        target_ok = nd.binder in declared or nd.binder in directions
        noun_kind = "position domain"
    else:
        head = f"{n.collection_query_head(nd.kind, nd.spelled)} in …"
        if cats.flavor == "card" and (
            nd.binder == n.SUBSET_BINDER or nd.spelled == n.SUBSET_BINDER + "s"
        ):
            # `subset` names a real domain in the language, just not this
            # form's: `in` iterates a collection's MEMBERS, and subsets are
            # spelled with `of`. Calling the word unknown would be false, and
            # would send a designer looking for a declaration to add.
            bag.error(_subset_refusal(nd.kind, head), nd.span, code=Code.WRONG_SPELLING)
            return True
        if nd.binder not in declared and (
            nd.binder in _minted_directions(game) or lack is not None
        ):
            bag.error(_direction_is_no_position(nd.kind, head, nd.binder, universe), nd.span, code=Code.WRONG_SORT_OF_NAME)
            return True
        if game.board is not None:
            universe += f"; the board's lines: `{LINE_NOUN}`"
        target_ok = nd.binder in collection_nouns(game)
        noun_kind = "collection noun"
        if _may_be_a_membership(nd, cats):
            # `x in <noun>s where …` with no parentheses: `_rewrite`, which
            # holds the lexical scope, tells a membership from a noun.
            return False
        if not target_ok:
            zone = _zone_source(nd.source, game)
            if zone is not None and cats.flavor == "card":
                bag.unknown(
                    f"`{head}` ranges over a position domain's members, and "
                    f"`{nd.binder}` is no position domain of this game; `{zone}` is "
                    f"a zone -- the cards in it satisfying a predicate are "
                    f"`cards in {zone} where <pred>`",
                    nd.spelled,
                    _nouns_a_query_takes(nd, game, cats.flavor),
                    nd.span,
                    code=Code.UNKNOWN_POSITION_DOMAIN,
                )
                return True
    if not target_ok:
        named = _bare_noun_refusal(nd, head, game, cats, universe)
        if named is not None:
            bag.error(named, nd.span, code=Code.WRONG_SORT_OF_NAME)
            return True
    if nd.kind != "any" and not nd.spelled.endswith("s"):
        # A singular noun under `all`/`number of`/the Set Form: guide to the
        # plural if the singular names a real target, else fall through to
        # unknown-noun.
        if target_ok:
            plural = nd.spelled + "s"
            fixed = (
                n.domain_query_head(nd.kind, plural)
                if nd.source is None
                else f"{n.collection_query_head(nd.kind, plural)} in …"
            )
            bag.error(f"`{head}` needs the plural noun -- write `{fixed}`", nd.span, code=Code.WRONG_SPELLING)
            return True
        refused: str | None = nd.spelled
    else:
        refused = None if target_ok else nd.binder
    if refused is None:
        return False
    bag.unknown(
        f"unknown {noun_kind} '{refused}' -- {universe}",
        nd.spelled,
        _nouns_a_query_takes(nd, game, cats.flavor),
        nd.span,
        code=Code.UNKNOWN_POSITION_DOMAIN,
        unless=board_mints(nd.binder),
    )
    return True


def _nouns_a_query_takes(nd: n.DomainQuery, game: n.Game, flavor: Flavor) -> frozenset[str]:
    """The nouns a query of `nd`'s form and kind may begin with, spelled as
    that kind spells them -- singular after `any`, plural otherwise: the
    game's position domains; in the bare form, the board directions where the
    kind ranges over them and the keyword nouns the grammar gives `any` and
    `all` (player, team, suit, rank), `players` alone for the others; in the
    collection form, the board lines and the content noun."""
    return frozenset(
        noun if nd.kind == "any" else noun + "s" for noun in _binders_a_query_takes(nd, game, flavor)
    )


def _binders_a_query_takes(nd: n.DomainQuery, game: n.Game, flavor: Flavor) -> frozenset[str]:
    """The singular of every noun `_nouns_a_query_takes` names: the binder a
    query of `nd`'s form and kind binds for each."""
    nouns = {p.name for p in game.positions}
    if nd.source is None:
        if nd.kind in n.DIRECTION_QUERY_KINDS:
            nouns |= _minted_directions(game)
        roles = _ITERATION_ROLES - (CARD_AXIS_ROLES if flavor == "piece" else frozenset())
        nouns |= set(role_names(roles) if nd.kind in ("any", "all") else [Role.PLAYER.value])
    else:
        nouns |= collection_nouns(game) | {content_noun(flavor, plural=False)}
    return frozenset(nouns)


def _subset_refusal(kind: n.DomainQueryKind, head: str) -> str:
    """A subset query written with `in`: subsets are spelled with `of`, and
    the subset register has no set, so the set is told the forms it has."""
    tail = "of <n> [or more] cards in <zone> where <pred>"
    match kind:
        case "any":
            form = f"`any subset {tail}`"
        case "all":
            form = f"`all subsets {tail}`"
        case "count":
            form = f"`number of subsets {tail}`"
        case "set":
            return (
                f"`{head}` iterates a collection's members; subsets are spelled "
                f"with `of`, and are asked about or counted, never gathered -- "
                f"write `any subset {tail}` or `number of subsets {tail}`"
            )
        case unreachable:
            assert_never(unreachable)
    return (
        f"`{head}` iterates a collection's members; subsets are spelled with "
        f"`of` -- write {form}"
    )


def _direction_is_no_position(
    kind: n.DomainQueryKind, head: str, binder: str, universe: str
) -> str:
    reach = (
        "gathers the members of a position domain"
        if kind not in n.DIRECTION_QUERY_KINDS
        else "ranges over a position domain's members"
    )
    return (
        f"`{head}` {reach}, and `{binder}` is the board direction domain, not a "
        f"position domain -- {universe}"
    )


def _zone_source(source: n.Expr, game: n.Game) -> str | None:
    """How a collection form's source is spelled when it names a zone."""
    root = source.obj if isinstance(source, n.Subscript) else source
    if isinstance(root, n.NameRef) and any(z.name == root.name for z in game.zones):
        return n.short_spelling(source)
    return None
