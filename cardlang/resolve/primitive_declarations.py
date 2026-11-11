"""Resolve step: the `primitives { }` block and its scoped reads.

Contract (decisions.md "Closed-domain completeness", write-time triage)
-----------------------------------------------------------------------
Assumes:      the board has minted its domains, since an entry's type slot
              may spell any of the game's position domains; ``expand`` has
              not run, so every ``run`` site a procedure body is judged at
              still stands.
Establishes:  every `primitives { }` entry's
              declared types are SHAPES the block's registries admit — the
              head from `declarable_type_names`, a collection's element from
              `COLLECTION_ELEMENT_NAMES`.
Now illegal:  an entry's collection element outside the block's allow-list
              reaching the type layer.
              A ``primitives { }`` entry whose ``reads`` clause names a
              declaration the game states in more than one of the four
              namespaces such a name can be declared in — the game's own
              ``state { }``, a phase's, an indexed ``zones { }`` declaration,
              an unindexed one (``_check_primitive_reads``, over
              ``primitives_block``'s three collision predicates). Every name
              reaching ``classify_read`` is therefore single-membership,
              which is what lets ``runtime/driver``'s materialization call
              the same classifier with no refusal of its own.
              For a read carrying a [[phase-scoped-read]]'s ``in <phase>``
              tail: the tail names a real phase of the game, that phase's own
              ``state { }`` declares the name, no STRICT DESCENDANT of it
              re-declares the name, the phases ONE entry's clause names lie on
              one ancestor path — so their subtrees nest and the entry's
              REGION is the innermost's subtree, which is the intersection of
              the named subtrees — and every call of that entry sits inside
              that region, or in a game move type every offering mention of
              which does, or at a ``run`` site that does
              (``_check_read_tail``, ``_check_read_tails_nest``,
              ``_check_scoped_read_containment``). Like
              the actor-alias rule this is a SCOPE fact, not a type fact, so
              it is settled here; and necessarily before ``expand``, which
              erases the ``run`` sites a procedure body is judged at.
              ``runtime/driver`` may therefore assume EVERY named phase's
              frame stands, and holds its name, at every call this pass
              admits, and defends a scoped read with nothing but an
              Owner-naming [[shadow-guard]].
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import assert_never
from cardlang.diagnostic_codes import Code
from cardlang.ast import nodes as n
from cardlang.builtins.functions import BUILTIN_CALL_FUNCS
from cardlang import kernel_contracts as K
from cardlang.primitives_block import (
    BINDABLE_READ_KINDS,
    PRIMITIVE_IMPLEMENTATIONS,
    InvocationContract,
    ReadKind,
    classify_read,
    COLLECTION_ELEMENT_NAMES,
    COLLECTION_TYPE_CONSTRUCTOR,
    states_declared_in,
    ambiguous_read_names,
    declaring_phases,
    descendant_redeclarations,
    phase_chain,
    phase_local_state_names,
    phase_names,
    phase_paths,
    phase_state_zone_names,
    shadowed_state_names,
    declarable_type_names,
    engine_fact_names,
    unimplemented,
    walled_namespace_of,
)
from cardlang import primitives_block
from cardlang.attribution import cite_named, cite_origin
from cardlang.diagnostics import DiagnosticBag, Said
from cardlang.resolve.walk import _child_nodes, _walk
from cardlang.resolve.slots import _MOVE_TYPE_SLOT_OFFERS, slot_strings
from cardlang.resolve.crossings import _cite_in


def step(game: n.Game, bag: DiagnosticBag) -> None:
    """The primitive declarations step."""
    # AFTER the board has minted its `cell` domain, because an entry's type
    # slot may spell any of the game's position domains and `_resolve_board` is
    # the one site that adds one. Validating earlier refused a name the rest of
    # the pipeline accepts — the signature builder maps the resolved
    # named-member position to `TCell`. Still before `_validate_refs`, which
    # resolves calls against the namespace the block defines: a game whose
    # block is wrong should hear about the block rather than about every call
    # that then fails to resolve.
    _check_primitives_block(game, bag)
    # After the block is validated whole, because it asks a different question
    # — where the game CALLS a scoped entry — and it must run before `expand`
    # erases the `run` sites a procedure body is judged at.
    _check_scoped_read_containment(game, bag)


def _check_primitives_block(game: n.Game, bag: DiagnosticBag) -> None:
    """The `primitives { }` block, validated whole.

    Everything a declaration can be wrong about is settled here, in the compile
    stage's own channel, because every one of them is a fact about the game
    text against a registry the front end holds: the entry's name against the
    game's other namespaces and the implementation index, its declared types
    against the spellable set, and each `reads` name against the game's own
    `zones { }` and `state { }`. What is deliberately NOT settled here is
    whether a declared read SUFFICES for the implementation — that is a fact
    about Python, and only running the game shows it."""
    if game.primitives is None:
        return
    declarable = declarable_type_names(game)
    own_definitions = (
        {f.name for f in game.functions}
        | {p.name for p in game.procedures}
        | {m.name for m in game.move_types}
        | {r.name for r in game.rules}
    )
    # The four name-membership sets, computed ONCE for the block: each is a
    # walk of the game's declarations, so the question they answer is about the
    # game — the same answer for every entry and every read in it.
    collisions = _ReadCollisions(
        ambiguous=ambiguous_read_names(game),
        shadowed=shadowed_state_names(game),
        phase_zone=phase_state_zone_names(game),
        phase_local=phase_local_state_names(game),
    )
    seen: set[str] = set()
    for decl in game.primitives.decls:
        _check_primitive_name(game, decl, own_definitions, seen, bag)
        seen.add(decl.name)
        for slot, type_name in [("return type", decl.return_type)] + [
            (f"parameter `{p.name}`", p.type_name) for p in decl.params
        ]:
            _check_primitive_type(game, decl, slot, type_name, declarable, bag)
        _check_primitive_reads(game, decl, collisions, bag)


def _check_primitive_type(
    game: n.Game,
    decl: n.PrimitiveDecl,
    slot: str,
    type_name: str,
    declarable: frozenset[str],
    bag: DiagnosticBag,
) -> None:
    """One entry type slot, against the block's own registries.

    A SHAPE question, in two parts the grammar has already separated: the head
    is the declarable set's, and a collection's ELEMENT is the block's element
    allow-list. Each refusal names the ruled spelling rather than calling a
    word the language knows unknown — the designer wrote a real type in the
    wrong shape, and the message that helps is the right shape."""
    spelled = primitives_block.decompose_type(type_name)
    if not spelled.is_collection:
        if spelled.base == COLLECTION_TYPE_CONSTRUCTOR:
            bag.error(
                f"`{decl.name}`'s {slot} names `{COLLECTION_TYPE_CONSTRUCTOR}`,"
                f" which takes an element type — write "
                f"`{COLLECTION_TYPE_CONSTRUCTOR}<Card>`",
                decl.span,
                code=Code.WRONG_PRIMITIVE_TYPE,
            )
        elif spelled.base not in declarable:
            bag.error(
                f"`{decl.name}`'s {slot} names `{spelled.base}`, which a "
                f"`primitives` entry may not spell — a declared signature "
                f"is what freezes the arguments, so its types are the "
                f"declared-type names ({', '.join(sorted(declarable))}) and "
                f"a collection of them (issue #547 tracks the shapes that "
                f"have no spelling)",
                decl.span,
                code=Code.WRONG_PRIMITIVE_TYPE,
            )
        return
    element = spelled.element
    assert element is not None  # `is_collection` is exactly this
    if spelled.base != COLLECTION_TYPE_CONSTRUCTOR:
        bag.error(
            f"`{decl.name}`'s {slot} names `{type_name}`, and "
            f"`{spelled.base}` takes no element type — "
            f"`{COLLECTION_TYPE_CONSTRUCTOR}` is the one type an entry writes "
            f"with angle brackets; a zone's are a `zones {{ }}` line's",
            decl.span,
            code=Code.WRONG_PRIMITIVE_TYPE,
        )
    elif element in COLLECTION_ELEMENT_NAMES:
        return
    elif element in declarable:
        bag.error(
            f"`{decl.name}`'s {slot} names `{type_name}`, and no registered "
            f"Primitive has an implementation taking it — a `primitives` "
            f"entry spells collections of "
            f"{', '.join(sorted(COLLECTION_ELEMENT_NAMES))} (issue #547 "
            f"reopens this when one takes another element)",
            decl.span,
            code=Code.WRONG_PRIMITIVE_TYPE,
        )
    else:
        bag.error(
            f"`{decl.name}`'s {slot} names `{type_name}`, and `{element}` is "
            f"not an element type — a zone's angle brackets take an index "
            f"domain (`Hand<player>`), a collection's take what it holds; "
            f"write `{COLLECTION_TYPE_CONSTRUCTOR}<Card>`",
            decl.span,
            code=Code.WRONG_PRIMITIVE_TYPE,
        )


def _check_primitive_name(
    game: n.Game,
    decl: n.PrimitiveDecl,
    own_definitions: set[str],
    seen: set[str],
    bag: DiagnosticBag,
) -> None:
    """One entry's NAME, against every namespace it could collide with and
    against the implementation index. Ordered so the most specific reason
    speaks: a walled namespace before an unknown name, because the name IS a
    Primitive and "nothing implements it" would be false."""
    if decl.name in seen:
        bag.error(
            f"`primitives` declares one `{decl.name}` entry — the repeat would "
            f"silently replace the first; keep one",
            decl.span,
            code=Code.WRITTEN_TWICE,
        )
        return
    if decl.name in BUILTIN_CALL_FUNCS:
        bag.error(
            f"`{decl.name}` is a Builtin the language ships, so a "
            f"`primitives` entry may not declare it — a call would resolve "
            f"against two homes at once; rename the Primitive",
            decl.span,
            code=Code.NAME_TAKEN,
        )
        return
    if decl.name in K.KERNEL_CONTRACT_NAMES:
        row = K.CONTRACTS[decl.name]
        bag.error(
            f"`{decl.name}` answers the kernel's `{row.spelled}`, which the game "
            f"answers in the language (`function {decl.name}(card : Card) = …`), "
            f"so a `primitives` entry may not declare it; rename the Primitive",
            decl.span,
            code=Code.NAME_TAKEN,
        )
        return
    if decl.name in own_definitions:
        bag.error(
            f"`{decl.name}` is already defined in this game, so a `primitives` "
            f"entry may not declare it too — a call would name both; rename one",
            decl.span,
            code=Code.NAME_TAKEN,
        )
        return
    walled = walled_namespace_of(decl.name)
    if walled is not None:
        bag.error(
            f"`{decl.name}` is {walled}, not a call-position Primitive, so "
            f"the `primitives` block cannot declare it — its signature is the "
            f"mechanic's, not a parameter list; the round slots take their own "
            f"declaration form (issue #142)",
            decl.span,
            code=Code.WRONG_SORT_OF_NAME,
        )
        return
    if unimplemented(frozenset({decl.name})):
        bag.unknown(
            f"nothing implements the Primitive `{decl.name}` — a "
            f"`primitives` entry names Python the engine can find "
            f"(cardlang/primitives_block.py, PRIMITIVE_IMPLEMENTATIONS); check "
            f"the spelling, or register the implementation",
            decl.name,
            PRIMITIVE_IMPLEMENTATIONS,
            decl.span,
            code=Code.UNKNOWN_PRIMITIVE,
        )


def _phase_list(phases: frozenset[str]) -> str:
    """The declaring phases, as a diagnostic reads them."""
    names = "`, `".join(sorted(phases))
    return f"phase `{names}`" if len(phases) == 1 else f"phases `{names}`"


@dataclass(frozen=True, slots=True)
class _ReadCollisions:
    """The name-membership sets a `reads` clause is checked against.

    Held as one value because they answer about the GAME, not about any one
    entry or read: each is a walk of the game's declarations, so computing them
    per read would re-walk the whole game per name."""

    ambiguous: frozenset[str]
    shadowed: frozenset[str]
    phase_zone: frozenset[str]
    phase_local: frozenset[str]


def _check_primitive_reads(
    game: n.Game,
    decl: n.PrimitiveDecl,
    collisions: _ReadCollisions,
    bag: DiagnosticBag,
) -> None:
    """One entry's `reads` clause: every name classified, every binder bound.

    The engine-structural half of what a Primitive sees (`EngineFacts`) is not
    spellable here, and its field names are refused at THIS site rather than
    left to read as ordinary unknowns, so the deferral is loud and cites its
    issue."""
    params = {p.name for p in decl.params}
    # A clause is a SET of declarations: the row it becomes is keyed by name,
    # and so is the per-call key map, so a repeat is not additive — one entry
    # silently wins. `hand, hand[p]` would play to completion returning a
    # value computed from ONE hand while the declaration says every hand, which
    # is a wrong answer with no failure anywhere. Refused as a multiset before any
    # per-entry check, so the diagnostic names the repeat rather than whichever
    # of the two copies happens to be malformed.
    # The parameter list is a SET for the same reason, one slot over: the type
    # pass reads it as a map (last wins) while the driver resolves a binder by
    # its INDEX (first wins), so a repeat makes the two halves of one
    # declaration disagree about which parameter a binder names.
    seen_params: set[str] = set()
    for param in decl.params:
        if param.name in seen_params:
            bag.error(
                f"`{decl.name}` declares the parameter `{param.name}` more than "
                f"once — each parameter is named once, and the repeat would "
                f"silently replace the first; rename one",
                param.span or decl.span,
                code=Code.NAME_TAKEN,
            )
            return
        seen_params.add(param.name)
    seen: set[str] = set()
    for read in decl.reads:
        if read.name in seen:
            bag.error(
                f"`{decl.name}` reads `{read.name}` more than once — a `reads` "
                f"clause names each spelling at most once: the entry receives "
                f"one value per name, so two declarations of one name cannot "
                f"both reach it; keep one",
                read.span or decl.span,
                code=Code.WRITTEN_TWICE,
            )
            return
        seen.add(read.name)
    # A PURE implementation never receives the bundle (`primitives.call_declared`
    # hands it the coerced arguments and nothing else), so a `reads` clause on
    # one declares a dependency the dispatch cannot honour — accepted-and-
    # ignored, which is the defect class this block exists to end.
    impl = PRIMITIVE_IMPLEMENTATIONS.get(decl.name)
    if decl.reads and impl is not None:
        match impl.contract:
            case InvocationContract.PURE:
                bag.error(
                    f"`{decl.name}` is implemented pure over its arguments, so "
                    f"it never receives the declared reads — a `reads` clause "
                    f"on it would be accepted and ignored; drop the clause",
                    decl.span,
                    code=Code.HAS_NO_EFFECT,
                )
                return
            case InvocationContract.BUNDLED:
                pass
            case _ as unreachable:
                assert_never(unreachable)
    # The collision sets are consulted BEFORE `classify_read`, which is
    # collision-unaware by design: it is also the loader's materialization call
    # (`runtime/driver.declared_primitives`), where a refusal could never fire.
    for read in decl.reads:
        if read.name in collisions.ambiguous:
            bag.error(
                f"`{decl.name}` reads `{read.name}`, which this game declares "
                f"as BOTH a state variable and a zone — the declaration cannot "
                f"say which, and the two are materialized into different halves "
                f"of what the implementation receives; rename one of the two",
                read.span or decl.span,
                code=Code.NAME_TAKEN,
            )
            continue
        if read.name in collisions.shadowed:
            # The tail says WHICH declaration is meant, so the untailed reason
            # is false about the text in front of the designer. The pair stays
            # refused for the other half of the collision: the game-level
            # variable of that spelling would be unreadable by any declaration
            # at all, with nothing on the page saying so. Lifting it means the
            # bundle stops being keyed by bare name; issue #516.
            bag.error(
                (
                    f"`{decl.name}` reads `{read.name} in {read.phase}`, and "
                    f"the game's own `state {{ }}` declares `{read.name}` too "
                    f"— the tail says which of the two is meant, but the "
                    f"game-level variable is then unreadable by any "
                    f"declaration and nothing says so; rename one of the two"
                )
                if read.phase is not None
                else (
                    f"`{decl.name}` reads `{read.name}`, which the game AND a "
                    f"phase both declare — the declaration cannot say which, "
                    f"and at run time the phase's value wins while that phase "
                    f"is active; rename one of the two"
                ),
                read.span or decl.span,
                code=Code.NAME_TAKEN,
            )
            continue
        if read.name in collisions.phase_zone:
            bag.error(
                f"`{decl.name}` reads `{read.name}`, which "
                f"{_phase_list(declaring_phases(game, read.name))} declares as "
                f"state while this game declares it as a zone — the declaration "
                f"cannot say which, and an untailed `reads` name classifies "
                f"against the zones and the GAME's state, so the phase's "
                f"variable is not what it denotes; rename one of the two (a "
                f"scope tail does not settle it either — a zone is game-level "
                f"whichever phase a read names, so one of the two spellings "
                f"would still be unreachable)",
                read.span or decl.span,
                code=Code.NAME_TAKEN,
            )
            continue
        if read.phase is not None and _check_read_tail(game, decl, read, bag):
            continue
        kind = classify_read(game, read.name, read.phase)
        if kind is None:
            if read.name in collisions.phase_local:
                where = declaring_phases(game, read.name)
                tail = (
                    f"`{read.name} in {sorted(where)[0]}`"
                    if len(where) == 1
                    else f"`{read.name} in <phase>`"
                )
                bag.error(
                    f"`{decl.name}` reads `{read.name}`, which a PHASE declares "
                    f"({_phase_list(where)}) — a Primitive's row is "
                    f"materialized on every call, so a phase-local variable is "
                    f"readable only while that phase runs; write {tail} to "
                    f"declare the scope, declare it in the game's "
                    f"`state {{ }}` block, or pass the value as an argument",
                    read.span or decl.span,
                    code=Code.OUT_OF_SCOPE,
                )
                continue
            hint = (
                f" — `{read.name}` is an engine fact a Primitive receives "
                f"whole today; the `reads` clause names this game's own zones "
                f"and state variables only (issue #474)"
                if read.name in engine_fact_names()
                else ""
            )
            bag.unknown(
                f"`{decl.name}` reads `{read.name}`, which this game declares "
                f"in neither `zones {{ }}` nor `state {{ }}`{hint}",
                read.name,
                {z.name for z in game.zones}
                | {nd.name for nd in _walk(game) if isinstance(nd, n.StateDecl)}
                - phase_local_state_names(game),
                read.span or decl.span,
                code=Code.UNKNOWN_NAME,
            )
            continue
        if read.binder is None:
            continue
        if kind not in BINDABLE_READ_KINDS:
            bag.error(
                f"`{decl.name}` reads `{read.name}[{read.binder}]`, but "
                f"`{read.name}` is a {kind.value} — it has no instances to key, "
                f"so write `{read.name}`",
                read.span or decl.span,
                code=Code.WRONG_SUBSCRIPT,
            )
        elif read.binder not in params:
            bag.error(
                f"`{decl.name}` reads `{read.name}[{read.binder}]`, but "
                f"`{read.binder}` is not one of its parameters "
                f"({', '.join(p.name for p in decl.params) or 'it declares none'}) "
                f"— an index binder keys the instance the CALL names",
                read.span or decl.span,
                code=Code.UNKNOWN_NAME,
            )
    _check_read_tails_nest(game, decl, bag)


def _and_list(items: list[str]) -> str:
    """`a` and `b`; `a`, `b` and `c` — a list as a sentence reads it."""
    return items[0] if len(items) == 1 else ", ".join(items[:-1]) + " and " + items[-1]


def _check_read_tails_nest(
    game: n.Game, decl: n.PrimitiveDecl, bag: DiagnosticBag
) -> None:
    """The phases one entry's tails name lie on ONE ancestor path.

    Their subtrees then nest, and the innermost's subtree is the intersection —
    the region the entry is callable in. Phases neither of which is inside the
    other intersect in NOTHING: `runtime/driver.run_phase` pops a phase's frame
    when the phase ends, so no position in the game runs both, and an entry
    reading from both could never be called anywhere. A designed constraint,
    not a deferral — nothing anyone would build makes such an entry callable,
    which is why the refusal teaches the two fixes that do exist rather than
    citing an issue.

    Settled per ENTRY, because a per-read arm cannot see the set, and AFTER
    every tail has validated, because a tail that names no phase of the game,
    or a phase that does not declare the name, has no path — asking the
    composition question of it would report the typo twice. That is the same
    predicate `_scoped_entry_phases` asks before it hands an entry to
    containment."""
    tailed_reads = [read for read in decl.reads if read.phase is not None]
    if len(tailed_reads) < 2:
        return
    if any(
        read.phase not in phase_names(game)
        or classify_read(game, read.name, read.phase) is None
        for read in tailed_reads
    ):
        return
    named: list[str] = []
    for read in tailed_reads:
        if read.phase is not None and read.phase not in named:
            named.append(read.phase)
    if len(named) < 2 or phase_chain(game, frozenset(named)) is not None:
        return
    bag.error(
        f"`{decl.name}` reads "
        f"{_and_list([f'`{r.name} in {r.phase}`' for r in tailed_reads])}, and "
        f"{_and_list([f'`{p}`' for p in named])} do not nest — no place in "
        f"this game runs {'both' if len(named) == 2 else 'them all'}, so the "
        f"entry could never be called; keep one, and pass the other value as "
        f"an argument or declare it in the game's `state {{ }}`",
        decl.span,
        code=Code.OUT_OF_SCOPE,
    )


def _tail_names_instead(game: n.Game, spelling: str) -> str:
    """What a scope tail's name IS, when it is not a phase — so the refusal
    does not mislead a designer who wrote a real name in the wrong slot."""
    if any(z.name == spelling for z in game.zones):
        return " — it is a zone of this game"
    if game.state is not None and any(d.name == spelling for d in game.state.decls):
        return " — it is a state variable of this game"
    if any(m.name == spelling for m in game.move_types):
        return " — it is a move type of this game"
    return ""


def _check_read_tail(
    game: n.Game, decl: n.PrimitiveDecl, read: n.PrimitiveRead, bag: DiagnosticBag
) -> bool:
    """One scoped read's tail, validated against the phase tree. True when the
    tail is wrong and a diagnostic was issued.

    Runs before classification, beside the collision arms and for their reason:
    `classify_read` is also the loader's materialization call
    (`runtime/driver.declared_primitives`), where a refusal could never fire."""
    assert read.phase is not None
    phase = read.phase
    if phase not in phase_names(game):
        known = phase_names(game)
        bag.unknown(
            f"`{decl.name}` reads `{read.name} in {phase}`, but this game "
            f"declares no phase `{phase}`"
            f"{_tail_names_instead(game, phase)} — a scope tail names the "
            f"phase whose `state {{ }}` declares the name "
            f"({_phase_list(known) if known else 'this game declares no phase'})",
            phase,
            known,
            read.span or decl.span,
            code=Code.UNKNOWN_PHASE,
        )
        return True
    if classify_read(game, read.name, phase) is None:
        elsewhere = declaring_phases(game, read.name) - {phase}
        if elsewhere:
            remedy = f" — {_phase_list(elsewhere)} declares it"
        elif (here := classify_read(game, read.name)) is not None:
            # Name what it IS. A zone earns its own half-sentence, because the
            # language has no phase-local `zones { }` form at all and a
            # designer who wrote one needs to know the tail can never apply to
            # it, not merely that it does not apply here.
            remedy = (
                f" — this game declares `{read.name}` as a {here.value}, and a "
                f"zone is game-level whichever phase runs; drop the tail"
                if here in (ReadKind.ZONE_FAMILY, ReadKind.SINGLE_ZONE)
                else f" — this game's own `state {{ }}` declares `{read.name}`, "
                f"and a game-level declaration stands wherever the game runs; "
                f"drop the tail"
            )
        else:
            remedy = " — check the spelling, or declare it in that phase"
        bag.unknown(
            f"`{decl.name}` reads `{read.name} in {phase}`, but phase "
            f"`{phase}` declares no state `{read.name}`{remedy}",
            read.name,
            states_declared_in(game, phase),
            read.span or decl.span,
            code=Code.UNKNOWN_STATE_VARIABLE,
        )
        return True
    inner = descendant_redeclarations(game, phase, read.name)
    if inner:
        bag.error(
            f"`{decl.name}` reads `{read.name} in {phase}`, and "
            f"{_phase_list(inner)} inside `{phase}` declares `{read.name}` too "
            f"— at run time the innermost frame wins, so a call from in there "
            f"would receive that phase's value while the declaration names "
            f"`{phase}`'s; rename one of the two",
            read.span or decl.span,
            code=Code.NAME_TAKEN,
        )
        return True
    return False


# --- the phase-scoped read's containment analysis ----------------------------
#
# An entry with a [[phase-scoped-read]] is callable only where its REGION runs
# — the innermost of the phases its tails name, whose subtree is the
# intersection of theirs. Settled HERE — a scope fact, the actor-alias
# precedent — and necessarily before `expand`, which erases the `run` sites a
# procedure body is judged at.

# Where a `Call` may sit, by the `n.Game` field its container hangs off.
# AUTHORED, and pinned total against the field set
# (tests/test_phase_scoped_reads.py), so a new field lands unclassified and
# reddens rather than defaulting to "allowed" — which is the direction a
# missing arm would fail in.
_CONTAINMENT_BY_GAME_FIELD: dict[str, str] = {
    # The three containers whose contents are JUDGED rather than refused.
    "phases": "subtree",
    "move_types": "offering",
    "procedures": "run_site",
    # Everything else runs outside any phase, or holds no call at all. Refusing
    # both together is exact in the safe direction: a field that cannot hold a
    # `Call` contributes no diagnostic, and one that can is refused for the
    # reason the wall states — a `winner:`/`loser:` expression runs with no
    # phase frame standing at all, and a function or rule body has no
    # lexical phase, so its liveness is reachability rather than position
    # (issue #518, the near neighbour of issue #242's standing question). A
    # procedure is the one callable container that IS judged, because a `run`
    # site is a position.
    "name": "refused",
    "players": "refused",
    "deck": "refused",
    "zones": "refused",
    "content_flavor": "refused",
    "direction": "refused",
    "ranking": "refused",
    "ranking_convention": "refused",
    "suit_ranking": "refused",
    "rank_sequence": "refused",
    "catalogues": "refused",
    "teams": "refused",
    "positions": "refused",
    "board": "refused",
    "max_length": "refused",
    "state": "refused",
    "winner": "refused",
    "loser": "refused",
    "stop_result": "refused",
    "rules": "refused",
    "functions": "refused",
    "primitives": "refused",
    "uses": "refused",
}

# Inside a phase, every item of the `PhaseItem` union is in the subtree — the
# whole extent of the `Phase` node. `run_phase` pushes the frame and declares
# the state before the qualifier, the hooks and the body, and pops it in a
# `finally`, so all of them run with the frame standing. The one item that
# sits inside the extent syntactically and cannot hold a call is named, with
# the guard that owns it, rather than re-covered here.
_SUBTREE_PHASE_ITEMS: dict[str, str] = {
    "StateBlock": "owned by _check_state_default_scope",
    "ActiveRules": "in the subtree",
    "LegalMoves": "in the subtree",
    "Mode": "in the subtree",
    "BeforeEach": "in the subtree",
    "AfterEach": "in the subtree",
    "Phase": "in the subtree",
    "Stmt": "in the subtree",
}


def _find_phase(game: n.Game, name: str) -> n.Phase | None:
    return next(
        (p for p in _child_nodes(game.phases) if isinstance(p, n.Phase) and p.name == name),
        None,
    )


@dataclass(frozen=True, slots=True)
class _ScopedEntry:
    """One entry's scope, in the shape the containment analysis needs it.

    `chain` is the phases its tails name, ordered outer to inner; `region` the
    innermost of them, whose subtree IS the intersection of the named subtrees
    and therefore the extent the entry is callable in; `binding` the read
    spelling that ties the entry to that region, which the refusal quotes so
    the designer can see WHICH declaration made a call illegal, and `read` the
    state variable it names. When two reads
    name the region, clause order picks the binding — a determinism rule
    carrying no meaning, since the tails are a set."""

    chain: tuple[str, ...]
    region: str
    binding: str
    read: str


def _scoped_entry_phases(game: n.Game) -> dict[str, _ScopedEntry]:
    """Entry name -> its scope, for every entry whose tails are USABLE — they
    name phases of the game that lie on ONE ancestor path, and each names a
    phase that declares the read it rides on.

    An entry whose tail is wrong, or whose phases do not nest, is left out and
    the arms above speak for it: containment has nothing to say about a scope
    that does not resolve, and saying it anyway would report a call site as a
    second defect when the designer has one to fix. This asks `classify_read`
    and `phase_chain` the SAME questions those arms ask rather than restating
    their conditions — a scope either denotes a region or it does not.

    The classifier is asked per READ against that read's own tail, never
    against the region: `dealer in hand_sequence` denotes nothing under the
    region `play`, and an entry dropped on that question would leave every one
    of its call sites unjudged."""
    if game.primitives is None:
        return {}
    scoped: dict[str, _ScopedEntry] = {}
    for decl in game.primitives.decls:
        tailed = frozenset(
            r.phase for r in decl.reads if r.phase is not None
        )
        if not tailed:
            continue
        chain = phase_chain(game, tailed)
        if chain is None:
            continue
        if any(
            classify_read(game, r.name, r.phase) is None
            for r in decl.reads
            if r.phase is not None
        ):
            continue
        region = chain[-1]
        bound = next(r.name for r in decl.reads if r.phase == region)
        scoped[decl.name] = _ScopedEntry(
            chain=chain,
            region=region,
            binding=f"{bound} in {region}",
            read=bound,
        )
    return scoped


def _offers_move_type(move_type: str) -> Callable[[object], bool]:
    """Whether a node OFFERS `move_type` — puts it in play at the position it
    sits at — by name across BOTH move-type namespaces.

    Derived from the classified slot table rather than from `n.Offer` alone, so
    a round form is seen by the same arm wherever it is written. The namespaces
    overlap in the corpus — pinochle's `declare_trump_suit` is kernel-listed and
    game-defined at once — so an edge collected by slot namespace would miss a
    game move type's `legal_moves:` mention."""

    def offers(node: object) -> bool:
        return any(
            puts_in_play
            and isinstance(node, cls)
            and move_type in slot_strings(node, field_name)
            for (cls, field_name), puts_in_play in _MOVE_TYPE_SLOT_OFFERS.items()
        )

    return offers


# The DEFINITION bodies whose statements run somewhere this analysis does not
# derive, and how each is named in the refusal. A move type's body runs at its
# own offers' positions, which is decided by something other than where the
# text sits, and deriving it means judging that container's own containment
# first, up a chain that can cycle — so it is a wall (issue #521). Pinned
# against the statement-holding definition productions of the grammar
# (tests/test_phase_scoped_reads.py), the others of which are the containers
# that DO yield positions: a phase, and a procedure through its `run` sites.
_UNPOSITIONED_CONTAINERS: dict[str, str] = {
    "move_types": "another move type",
}


def _definition_bodies(game: n.Game) -> dict[int, tuple[str, Said]]:
    """id(node) -> (the `n.Game` field of the definition whose body holds it, a
    phrase naming that definition).

    Finer than `_statement_owners`' attribution, because a wall on an offer
    made inside a definition body must NAME the definition: an addressee told
    only "inside a move type" is left to find which."""
    bodies: dict[int, tuple[str, Said]] = {}
    for move_type in game.move_types:
        for node in _walk(move_type):
            bodies[id(node)] = ("move_types", "move type " + cite_named(move_type, f"`{move_type.name}`"))
    return bodies


def _offering_positions(
    game: n.Game,
    move_type: str,
    owners: dict[int, str],
    bodies: dict[int, tuple[str, Said]],
) -> tuple[list[object], list[tuple[object, Said, str]], frozenset[str]]:
    """Where `move_type` is put IN PLAY, which is not always where the offer's
    text sits — with the offers this analysis declines to position, and the
    procedures that offer.

    Exactly one container yields a position outright: a phase, whose statements
    run where they are written. A procedure's run wherever it is RUN, because
    expansion is by value, so its `run` sites are the positions — the same
    reasoning the call arm uses. Every other container is walled, which is the
    safe direction as well as today's exact answer: a statement form the grammar
    grows into a new container lands in the refusal rather than being judged at
    a position nobody derived."""
    offers = _offers_move_type(move_type)
    from_procedures = _procedures_reaching(game, offers)
    positions: list[object] = []
    walled: list[tuple[object, Said, str]] = []
    for node in _walk(game):
        if not (
            offers(node)
            or (isinstance(node, n.RunStmt) and node.name in from_procedures)
        ):
            continue
        owner = owners.get(id(node), "phases")
        if owner == "procedure":
            continue  # its `run` sites are this offer's positions, collected here
        if owner == "phases":
            positions.append(node)
            continue
        # The container's own `n.Game` field decides how the wall names it, so
        # a definition body and the field it hangs off cannot drift apart.
        field_name, named = bodies.get(id(node), (owner, f"this game's `{owner}`"))
        walled.append(
            (
                node,
                named,
                _UNPOSITIONED_CONTAINERS.get(field_name, f"a `{field_name}` item"),
            )
        )
    return positions, walled, from_procedures


def _check_scoped_read_containment(game: n.Game, bag: DiagnosticBag) -> None:
    """Every call of an entry carrying a scope tail sits where its region runs.

    Its own check rather than part of `_check_primitives_block`, because it is
    a fact about the game's CALL SITES rather than about the block, and it must
    run while the `run` sites still exist — `expand` splices them away, by
    value, which is exactly why a procedure body is judged at each `RunStmt`
    rather than once at its definition."""
    scoped = _scoped_entry_phases(game)
    if not scoped:
        return
    bodies = _definition_bodies(game)
    owners = _statement_owners(game, bodies)
    holders = _phase_of_node(game)
    origins = n.library_origins(game)
    for entry, scope in sorted(scoped.items(), key=lambda item: item[0]):
        phase_name = scope.region
        phase = _find_phase(game, phase_name)
        # NOT a `continue`: skipping here would run zero cells for this entry
        # and report the pass clean, which is a scoped entry callable from
        # anywhere with nothing saying so — the exact unsoundness this check
        # exists to refuse. Two walks answer "is this a phase of the game"
        # (`phase_names`, which `_scoped_entry_phases` filtered on, and this
        # one); that they agree is the argument FOR asserting it, not for
        # assuming it.
        assert phase is not None, (
            f"`_scoped_entry_phases` admitted the phase {phase_name!r}, which "
            f"`_find_phase` cannot find — the two phase walks disagree"
        )
        inside = {id(node) for node in _walk(phase)}
        reaching = _procedures_reaching(game, _calls_entry(entry))
        _check_direct_call_positions(game, entry, scope, inside, holders, bag)
        _check_offered_containers(
            game, entry, scope, inside, reaching, owners, bodies, origins, bag
        )
        _check_run_sites(game, entry, phase_name, inside, reaching, owners, bag)


def _calls_entry(entry: str) -> Callable[[object], bool]:
    """Whether a node CALLS `entry` — the seed the procedure closure follows for
    the call arm, as `_offers_move_type` is for the offering one."""
    return lambda node: isinstance(node, n.Call) and node.func == entry


def _procedures_reaching(
    game: n.Game, seed: Callable[[object], bool]
) -> frozenset[str]:
    """Procedures whose body reaches a node `seed` accepts, through `run` as
    well as directly — a fixpoint, since one procedure's `run` of another
    composes.

    Depth one today: `_check_procedures` refuses a procedure that runs another
    ("expansion is a single splice, not a call graph"), so the loop settles on
    its first pass. Written as a fixpoint anyway, because composing is this
    derivation's own fact rather than the wall's — the day a procedure may run
    another, the closure is already right."""
    direct = {p.name for p in game.procedures if any(seed(nd) for nd in _walk(p))}
    reaching = set(direct)
    changed = True
    while changed:
        changed = False
        for proc in game.procedures:
            if proc.name in reaching:
                continue
            if any(
                isinstance(nd, n.RunStmt) and nd.name in reaching
                for nd in _walk(proc)
            ):
                reaching.add(proc.name)
                changed = True
    return frozenset(reaching)


def _reaches_scoped_entry(
    node: object, entry: str, reaching: frozenset[str]
) -> bool:
    """Whether a container's own text reaches a call of `entry` — directly, or
    through a `run` of a procedure that does."""
    return any(
        (isinstance(nd, n.Call) and nd.func == entry)
        or (isinstance(nd, n.RunStmt) and nd.name in reaching)
        for nd in _walk(node)
    )


def _phase_of_node(game: n.Game) -> dict[int, str]:
    """id(node) -> the name of the INNERMOST phase whose extent holds it.

    A POSITION question, so it is this pass's: the same `_walk(phase)` extent
    the containment relation is built from, taken outer phase first so a deeper
    one overrides. Which of two phases encloses the other is an ANCESTRY
    question and is asked of `phase_paths` instead."""
    paths = phase_paths(game)
    depth: list[tuple[int, n.Phase]] = sorted(
        (
            (len(paths[node.name]), node)
            for node in _walk(game)
            if isinstance(node, n.Phase) and node.name in paths
        ),
        key=lambda item: item[0],
    )
    holders: dict[int, str] = {}
    for _, phase in depth:
        for node in _walk(phase):
            holders[id(node)] = phase.name
    return holders


def _outside(entry: str, scope: _ScopedEntry, where: str) -> str:
    """The refusal a call outside a scoped entry's region meets.

    It names the READ that binds the region, not merely the region: with more
    than one phase in the clause, a designer told only "callable only where
    `inner` runs" is left to work out which of the tails said so."""
    return (
        f"`{entry}` reads `{scope.binding}`, so it is callable only where "
        f"`{scope.region}` runs — this call is {where}; move the call inside "
        f"`{scope.region}`, or pass the value as an argument"
    )


def _outside_phase(game: n.Game, holder: str, region: str) -> str:
    """How a refusal names the phase a call sits in.

    A phase that ENCLOSES the region runs outside it for a different reason
    than one that merely runs elsewhere — its own frame is standing, the
    region's is not — and the two want different fixes, so the sentence says
    which. This is where an entry naming two nested phases is most often
    misread: the outer tail says which declaration is meant, never where the
    entry may be called."""
    here, there = phase_paths(game).get(holder), phase_paths(game).get(region)
    if here is not None and there is not None and here != there and there[: len(here)] == here:
        return (
            f"in `{holder}`, which encloses `{region}` but runs outside it "
            f"(`{region}`'s state does not stand here)"
        )
    return f"in `{holder}`, which runs outside it"


def _check_direct_call_positions(
    game: n.Game,
    entry: str,
    scope: _ScopedEntry,
    inside: set[int],
    holders: dict[int, str],
    bag: DiagnosticBag,
) -> None:
    """Calls written in the game's own text, outside a move type or procedure
    body: legal inside the region's subtree, refused everywhere else."""
    for field_name, arm in sorted(_CONTAINMENT_BY_GAME_FIELD.items()):
        if arm in ("offering", "run_site"):
            continue  # judged by their own containers below
        for node in _child_nodes(getattr(game, field_name)):
            if not (isinstance(node, n.Call) and node.func == entry):
                continue
            if arm == "subtree" and id(node) in inside:
                continue
            if arm != "subtree":
                where = f"in this game's `{field_name}`, which runs outside it"
            else:
                holder = holders.get(id(node))
                # NOT a fallback: `_CONTAINMENT_BY_GAME_FIELD` puts this node
                # under `game.phases`, and the attribution covers the extent of
                # every phase, so a miss means the two walks disagree.
                assert holder is not None, (
                    f"a call of `{entry}` sits under `{field_name}` and inside "
                    f"no phase's extent — the position attribution and the "
                    f"containment taxonomy disagree"
                )
                where = _outside_phase(game, holder, scope.region)
            bag.error(_outside(entry, scope, where), node.span or game.span, code=Code.OUT_OF_SCOPE)


def _check_offered_containers(
    game: n.Game,
    entry: str,
    scope: _ScopedEntry,
    inside: set[int],
    reaching: frozenset[str],
    owners: dict[int, str],
    bodies: dict[int, tuple[str, Said]],
    origins: dict[int, n.LibraryOrigin],
    bag: DiagnosticBag,
) -> None:
    """A game move type has no lexical phase, so its body's containment is its
    OFFERING sites': every POSITION that puts it in play must sit inside the
    subtree, and a move type nothing offers is refused rather than passing
    vacuously.

    Library text reaches a scoped entry only through the game's text, since
    a library names no Primitive: a library move type runs the game's answer
    to a `Procedure` row, or a library offers the game's move type. So a
    refusal standing in library text -- a library move type nothing offers,
    an offer a library move type makes -- carries the sentence the game's
    author reads, with the fix the game's text can take, for `attribution`
    to tell."""
    phase_name = scope.region
    read = scope.read
    for move_type in game.move_types:
        if not _reaches_scoped_entry(move_type, entry, reaching):
            continue
        positions, walled, from_procedures = _offering_positions(
            game, move_type.name, owners, bodies
        )
        # The game's text that reaches the entry from this move type: the
        # move type itself, or the procedure a library move type runs.
        runs = sorted(
            nd.name for nd in _walk(move_type)
            if isinstance(nd, n.RunStmt) and nd.name in reaching
        )
        through: Said = (
            "move type " + cite_named(move_type, f"`{move_type.name}`")
            if move_type.origin is None or not runs
            else "this game's procedure " + _cite_in(game, "procedure", runs[0], f"`{runs[0]}`")
        )
        entry_named = _cite_in(game, "function", entry, f"`{entry}`")
        for site, named, kind in walled:
            site_origin = origins.get(id(site))
            # A wall with a witness, not a decision: coup's move-type effects
            # offer three move types this way, and it migrates when its eviction
            # wall falls (issue #521). Following the offer would mean judging
            # the offering CONTAINER's own containment, and so on up a chain the
            # flow analysis does not walk — so the refusal says exactly that,
            # rather than a false thing about where state stands.
            made: Said = (
                "the `run` of procedure "
                + _cite_in(game, "procedure", site.name, f"`{site.name}`")
                + ", which offers " + cite_named(move_type, f"`{move_type.name}`") + ","
                if isinstance(site, n.RunStmt)
                else "this offer of " + cite_named(move_type, f"`{move_type.name}`")
            )
            bag.error(
                f"move type " + cite_named(move_type, f"`{move_type.name}`") + f" calls " + entry_named + f", which reads "
                f"state declared in phase `{phase_name}`, and " + made + f" sits "
                f"inside " + named + f" — the analysis does not follow offers made "
                f"from inside {kind}, so there is no "
                f"position to judge and the scope cannot be established; offer "
                f"" + cite_named(move_type, f"`{move_type.name}`") + f" from a statement inside `{phase_name}`",
                getattr(site, "span", None) or game.span,
                for_game=None if site_origin is None else (
                    cite_origin(site_origin, getattr(site, "span", None) or game.span) + f" "
                    f"offers " + cite_named(move_type, f"`{move_type.name}`") + f", which calls " + entry_named + f" through "
                    f"" + through + f", and " + entry_named + f" reads state declared in phase "
                    f"`{phase_name}` — the analysis does not follow offers made "
                    f"from inside {kind}, so there is no position to judge and "
                    f"the scope cannot be established; keep " + entry_named + f" out of "
                    f"" + through + f", or declare `{read}` at game level and drop "
                    f"`in {phase_name}` from " + entry_named + f"'s read of it"
                ),
                stands_on=move_type.span,
                code=Code.OUT_OF_SCOPE,
            )
        if not positions:
            if walled or from_procedures:
                # Walled offers are refused above, once per unpositionable site.
                # An offer inside a procedure with no position means that
                # procedure is never run, which `_check_procedures` refuses
                # game-wide with the message naming what to run — reporting it
                # again here would make one defect look like two.
                continue
            # Designed constraint, not a deferral: a move type nothing offers
            # never runs, so "every offering site is inside the phase" would be
            # true of it vacuously — a guard that cannot fire. Refusing is what
            # keeps the containment claim about a real containment.
            origin = move_type.origin
            bag.error(
                f"move type " + cite_named(move_type, f"`{move_type.name}`") + f" calls " + entry_named + f", which reads "
                f"state declared in phase `{phase_name}`, and no statement "
                f"offers " + cite_named(move_type, f"`{move_type.name}`") + f" — an unoffered move type has no "
                f"phase to be inside, so the scope cannot be established; "
                f"offer it inside `{phase_name}`",
                move_type.span or game.span,
                for_game=None if origin is None else (
                    cite_origin(origin, move_type.span or game.span) + f" calls " + entry_named + f" "
                    f"through " + through + f", and " + entry_named + f" reads state declared in "
                    f"phase `{phase_name}`, but no statement offers "
                    f"" + cite_named(move_type, f"`{move_type.name}`") + f" — an unoffered move type has no phase "
                    f"to be inside, so the scope cannot be established; offer "
                    f"" + cite_named(move_type, f"`{move_type.name}`") + f" inside `{phase_name}`"
                ),
                code=Code.OUT_OF_SCOPE,
            )
            continue
        for site in positions:
            if id(site) in inside:
                continue
            # One diagnostic per offending position, spanned at it: the
            # addressee is whoever put the move type in play there, not whoever
            # wrote the entry.
            if isinstance(site, n.RunStmt):
                run_named = _cite_in(game, "procedure", site.name, f"`{site.name}`")
                bag.error(
                    f"move type " + cite_named(move_type, f"`{move_type.name}`") + f" calls " + entry_named + f", which reads "
                    f"state declared in phase `{phase_name}`, and procedure "
                    + run_named + " offers " + cite_named(move_type, f"`{move_type.name}`")
                    + " wherever it is run — this `run` puts "
                    + cite_named(move_type, f"`{move_type.name}`") + f" in play outside "
                    f"`{phase_name}`, where that state does not stand; run "
                    + run_named + f" inside `{phase_name}` only",
                    site.span or game.span,
                    code=Code.OUT_OF_SCOPE,
                )
                continue
            bag.error(
                f"move type " + cite_named(move_type, f"`{move_type.name}`") + f" calls " + entry_named + f", which reads "
                f"state declared in phase `{phase_name}` — this offer puts "
                f"" + cite_named(move_type, f"`{move_type.name}`") + f" in play outside `{phase_name}`, where "
                f"that state does not stand; offer " + cite_named(move_type, f"`{move_type.name}`") + f" inside "
                f"`{phase_name}` only",
                getattr(site, "span", None) or game.span,
                code=Code.OUT_OF_SCOPE,
            )


def _check_run_sites(
    game: n.Game,
    entry: str,
    phase_name: str,
    inside: set[int],
    reaching: frozenset[str],
    owners: dict[int, str],
    bag: DiagnosticBag,
) -> None:
    """A procedure body is judged at every `RunStmt` naming it, because
    expansion is by VALUE: the run site's position IS the body's future
    position. A procedure run both inside and outside the subtree is refused at
    the offending site.

    Two positions a `run` can occupy are decided elsewhere and not re-decided
    here: inside a move type, where the move type's own offering arm judges the
    spliced body along with the rest of it; and inside another procedure, which
    `_check_procedures` refuses outright. A procedure NO statement runs is
    likewise `_check_procedures`' — it refuses every uninvoked procedure
    game-wide, so a scope-flavoured copy of that refusal would report one defect
    as two."""
    if not reaching:
        return
    for run in _walk(game):
        if not (isinstance(run, n.RunStmt) and run.name in reaching):
            continue
        owner = owners.get(id(run), "phases")
        if owner in ("move_type", "procedure"):
            continue  # decided by the containers named in this docstring
        if owner == "phases" and id(run) in inside:
            continue
        where = "in another phase" if owner == "phases" else f"in this game's `{owner}`"
        procedure = _cite_in(game, "procedure", run.name, f"`{run.name}`")
        bag.error(
            "procedure " + procedure + " calls "
            + _cite_in(game, "function", entry, f"`{entry}`") + ", which reads state "
            f"declared in phase `{phase_name}`, and a procedure body runs where "
            f"its `run` site sits — this one is {where}, which runs outside "
            f"`{phase_name}`; run " + procedure + f" inside `{phase_name}` only",
            run.span or game.span,
            code=Code.OUT_OF_SCOPE,
        )


def _statement_owners(
    game: n.Game, bodies: dict[int, tuple[str, Said]]
) -> dict[int, str]:
    """id(node) -> the `n.Game` field whose subtree holds it. Built once per
    containment check so a `run` or an offer can be attributed to the container
    that decides it, rather than by re-walking per site."""
    owners: dict[int, str] = {
        node_id: "move_type"
        for node_id, (field_name, _) in bodies.items()
        if field_name == "move_types"
    }
    for proc in game.procedures:
        for node in _walk(proc):
            owners[id(node)] = "procedure"
    for field_name, arm in _CONTAINMENT_BY_GAME_FIELD.items():
        if arm in ("offering", "run_site"):
            continue
        for node in _child_nodes(getattr(game, field_name)):
            owners.setdefault(id(node), field_name if arm == "refused" else "phases")
    return owners
