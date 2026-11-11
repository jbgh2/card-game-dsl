"""Resolve step: the library splice (`uses`).

The first step: each library a game `uses` is checked against the game and
spliced in, its definitions with it, and its rules held aside for the rule
instantiation step. The splice's own errors (an unknown library, a
collision, an unmet `requires`) make the spliced game unrepresentative, so
the root raises them, as a complete set, before any later step runs.

Contract (decisions.md "Closed-domain completeness", write-time triage)
-----------------------------------------------------------------------
Assumes:      the parsed game, and the library source the loader hands it
              (``library_names``, ``load_library``, read here and nowhere
              else in the pass); ``check_library_alone`` has judged each
              library before the game is judged against it, and wrote its
              refusals into the same bag, which ``_apply_uses`` and
              ``_check_requires`` read to skip what it refused.
Establishes:  one flat game, its library definitions spliced and its
              library rules returned beside it, not spliced.
              Every piece of library text spliced into the game -- a family
              library's move types, functions, procedures and provided state
              declarations, and every library rule a game activates, the
              standard library's included -- carries its ``n.LibraryOrigin``,
              and no game text carries one: it is the only record of where
              spliced text came from that any check, this pass's included,
              may read.
Now illegal:  for a game that ``uses`` a
              library, a game-introduced binder or declaration parameter
              spelled like a variable the library PROVIDES, where the game
              does not already bind that spelling at declaration level
              (``_check_provided_shadowed_by_binder``, decisions.md "Family
              libraries"). Like every other rule about provided state it is
              settled inside ``_apply_uses``, before the splice — afterwards
              the two are one flat declaration block and the distinction no
              longer exists to check.
              For a game that ``uses`` a
              library, anything the library brings in that a game clause the
              game lacks (or holds) gates — a Builtin call or a construct, by
              every row of ``_CLAUSE_GATES``, plus a literal ``lines(k)`` past
              the board — refused on the game's ``uses`` line
              (``_check_library_clause_gates``) before the splice, so the
              gates downstream meet it only as its Shadow Guards. Each row's
              test is the one its gate asks, and each row states the clause it
              gates and its role (``_ClauseGate.clause``, ``.role``). A
              library rule the game does not
              activate is not brought in, and is not judged against the game;
              nor is a library ``check_library_alone`` refuses, whose own
              author speaks first and alone.
              A ``uses``
              line naming the standard library, whose rules need none.
              For a library's ``requires { }``: a row is a keyed
              declaration (state, zone) or a Definition Contract of a kind
              in ``CONTRACT_KINDS`` — derived, so a rule, which no library
              text can name, is never one — and every Definition Contract is
              answered by exactly one of the game's own definitions of its
              kind, at its parameters' positions and exact type spellings
              (``_check_definition_requirement``). Illegal after this pass: a
              row whose shape no game could answer, a library both defining
              and requiring a definition, a row answered by another library's
              definition, a function row spelled like a native name or a
              round callback, a procedure row a library procedure runs, and a
              move or procedure row the library never reaches
              (``_check_contract_shapes``, ``_check_definition_claims``). The
              splice records each answer: the game's answering function or
              procedure carries every row it answers (``contracts``), and
              every library call of a contracted function carries its own
              row (``Call.contract``), each stamp with the row's own span
              (``ContractStamp.row_span``), which a refusal naming the row
              cites —
              ``typecheck`` reads both, and nothing else about imports;
              ``_check_hidden_reads``, ``_check_play_source`` and the
              no-acting-seat walk read them to tell the game's author. A
              library ``run`` of a contracted procedure carries no stamp: its
              arity and parameter types are the row's by the check above, and
              a refusal there raises before ``typecheck`` runs. ``expand``
              needs no delta: a contracted procedure is a game procedure, run
              from a library move type's effect.
Verified by:  for the Definition Contracts, the grid
              in ``tests/test_definition_contracts.py``.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import assert_never, cast
from cardlang.diagnostic_codes import Code
from cardlang.ast import nodes as n
from cardlang.builtins.functions import CALL_FUNCS, VALUE_NAMES
from cardlang import kernel_contracts as K
from cardlang.attribution import (
    cite_definition,
    cite_library,
    cite_named,
    naming_library,
    cite_where,
)
from cardlang.diagnostics import (
    DiagnosticBag,
    LibraryCitation,
    Said,
    Sentence,
    Severity,
    Span,
    listed,
)
from cardlang.domains import index_phrase, role_of
from cardlang.libraries import library_names, load_library
from cardlang.runtime.errors import OwnerGuardError
from cardlang.stdlib.boards import board_entry
from cardlang.stdlib.enums import SEAT_DIRECTION_VALUES, rank_names, suit_names
from cardlang.stdlib.rules import STDLIB_NAME, stdlib_rules
from cardlang.resolve.walk import _traverse, _walk
from cardlang.resolve.binders import _introduced_binders
from cardlang.resolve.reserved import _PARAM_BEARING
from cardlang.resolve.slots import _round_query_slot
from cardlang.resolve.declared import _deck_known, _stamped_stdlib_rules, _written_state_name
from cardlang.resolve.clause_gates import (
    _ANSWER_IS_TRUMP,
    _CLAUSE_GATES,
    _activated_rule_names,
    _board_spelling,
)
from cardlang.resolve.library_alone import (
    CONTRACT_KINDS,
    _CONTRACT_KIND_OF,
    _CONTRACT_ROWS,
    _DEFINITION_KEYWORDS,
    _LIBRARY_DEF_KINDS,
    _contract_rows,
    _contracted,
    _keyed_rows,
    _spelled_contract,
    check_library_alone,
    is_zone_contract,
)
# The kinds `_apply_uses` splices at the `uses` line. A library's rules splice
# where a game's `active_rules:` names them instead (`_instantiate_rules`), the
# one activation-driven splice every tier's rules share (decisions.md "Family
# libraries"); the collision Owner Guards still sweep every kind above.
_USES_SPLICED_KINDS: tuple[tuple[str, str], ...] = tuple(
    kind for kind in _LIBRARY_DEF_KINDS if kind[0] != "rules"
)



@dataclass(frozen=True)
class _StateClaims:
    """The outcome of resolving who claims which state name across a game and
    the libraries it uses.

    `provided` maps a surviving provided name to the library that owns it — the
    input to both the read-only Owner Guard and the splice. `contested` is the names a
    claim collision has already been reported for, which `_check_requires` skips
    so one bad name yields one diagnostic instead of two."""

    provided: dict[str, LibraryCitation]
    contested: frozenset[str]


def _apply_uses(
    game: n.Game, bag: DiagnosticBag
) -> tuple[n.Game, dict[str, n.RuleDef]]:
    """Resolve every `uses <library>` line: load the named libraries, refuse the
    three-way collisions, check each library's `requires` contract against the
    game's declared state, and splice the definitions into the game.

    Runs FIRST in `resolve`, before every other name check, so that what flows on
    is one flat `Game` and no later pass needs to know imports exist — which is
    what makes an import pure name resolution, with no runtime or
    information-set implication.

    Collisions are errors, never overrides: `uses` is composition, and a game
    redefining what it imports would make the tier inheritance (decisions.md
    "Family libraries"). That is also why the game's own definitions are spliced
    alongside, not merged over, the library's."""
    if not game.uses:
        return game, {}

    available = library_names()
    libraries: list[tuple[n.UsesDecl, n.Library]] = []
    seen_uses: dict[str, n.UsesDecl] = {}
    for use in game.uses:
        if use.name in seen_uses:
            bag.error(
                f"game '{game.name}' already uses " + cite_library(use.name, None)
                + " — the repeat imports nothing further; delete it",
                use.span,
                code=Code.WRITTEN_TWICE,
            )
            continue
        seen_uses[use.name] = use
        if use.name == STDLIB_NAME:
            bag.error(
                cite_library(STDLIB_NAME, None)
                + " needs no `uses` line; its rules are switched on by name in "
                "`active_rules:` — delete this line",
                use.span,
                code=Code.HAS_NO_EFFECT,
            )
            continue
        if use.name not in available:
            known = ", ".join(sorted(available)) or "none"
            bag.unknown(
                "unknown " + cite_library(use.name, None)
                + f" — `uses` names a family library in docs/libraries/ "
                f"(available: {known})",
                use.name,
                available,
                use.span,
                code=Code.UNKNOWN_LIBRARY,
            )
            continue
        libraries.append((use, load_library(use.name)))

    _check_library_collisions(game, libraries, bag)
    claims = _check_state_claims(game, libraries, bag)
    definition_claims = _check_definition_claims(game, libraries, bag)
    _check_library_shadows_game(game, libraries, bag)
    _check_provided_readonly(game, claims.provided, bag)
    _check_provided_shadowed_by_binder(game, claims.provided, bag)
    skip = claims.contested | frozenset(claims.provided)
    answers: dict[tuple[str, str], tuple[n.ContractStamp, ...]] = {}
    for use, library in libraries:
        before = len(bag.items)
        check_library_alone(library, bag)
        # A library its own author must fix is not judged against the game's
        # clauses: one the game lacks may not be needed once the library is sound.
        sound = not any(d.severity is Severity.ERROR for d in bag.items[before:])
        for key, stamp in _check_requires(
            game, use, library, bag, skip, definition_claims
        ).items():
            answers[key] = answers.get(key, ()) + (stamp,)
        if sound:
            _check_library_clause_gates(game, use, library, bag)
    # The Definition Contracts cross the splice here, the one moment both
    # sides are in hand: the game's answering definitions carry every row they
    # answer, one per library, and each library's calls of a contracted
    # function carry its own row, so typecheck types those calls against the
    # row and checks the answer's inferred result against each, reporting on
    # each library's `uses` line.
    game = replace(
        game,
        functions=tuple(
            replace(f, contracts=answers.get(("functions", f.name), ()))
            for f in game.functions
        ),
        procedures=tuple(
            replace(p, contracts=answers.get(("procedures", p.name), ()))
            for p in game.procedures
        ),
    )
    libraries = [
        (use, _stamp_origin(use, _stamp_contracted_calls(use, library)))
        for use, library in libraries
    ]

    # Imported definitions come FIRST, in `uses` order, then the game's own: the
    # import is the base a game extends, which is the order the game file itself
    # reads in (`uses` sits at the top). Names are unique across the two by the
    # collision Owner Guards above, so order carries no meaning beyond IR stability —
    # but it must be STABLE, since `ir.emit` prints these tuples in order and the
    # goldens pin the printout.
    spliced: dict[str, tuple[object, ...]] = {}
    for field, _ in _USES_SPLICED_KINDS:
        from_libraries = tuple(
            d for _, library in libraries for d in getattr(library, field)
        )
        spliced[field] = from_libraries + tuple(getattr(game, field))
    # Provided state splices the same way and for the same reason: a library's
    # `state { }` becomes part of the game's own, so no later pass can tell a
    # provided variable from one the game declared, and the tier keeps carrying
    # no runtime and no information-set implication. The read-only rule is
    # therefore enforced ENTIRELY above this line — once the two are one block
    # the distinction no longer exists to check.
    provided_decls = tuple(
        decl
        for _, library in libraries
        if library.state is not None
        for decl in library.state.decls
    )
    state = game.state
    if provided_decls:
        state = (
            replace(state, decls=provided_decls + state.decls)
            if state is not None
            else n.StateBlock(decls=provided_decls)
        )
    # `uses` is emptied here for the same reason `procedures` is emptied by
    # `expand`: a surviving entry downstream would mean the import was parsed and
    # ignored, and `openspiel.encoding` walks every dataclass field of the Game.
    # The libraries' rules return beside the game, stamped like the rest, for
    # `_instantiate_rules` to splice where `active_rules:` names them.
    library_rules = {r.name: r for _, library in libraries for r in library.rules}
    return replace(game, uses=(), state=state, **spliced), library_rules  # type: ignore[arg-type]


def _stamp_origin(use: n.UsesDecl, library: n.Library) -> n.Library:
    """`library` with each definition and provided declaration carrying its
    `n.LibraryOrigin`: the library, the definition in the designer's words (as
    `_library_nodes` names it), the `uses` line, and the zones its contract
    names."""
    zones = tuple(r.name for r in _keyed_rows(library) if is_zone_contract(r))
    stamped: dict[str, object] = {}
    for field, noun in _LIBRARY_DEF_KINDS:
        stamped[field] = tuple(
            replace(
                d,
                origin=n.LibraryOrigin(
                    library.name, f"{noun} `{d.name}`", use.span, contracted_zones=zones
                ),
            )
            for d in getattr(library, field)
        )
    state = library.state
    if state is not None:
        state = replace(
            state,
            decls=tuple(
                replace(
                    decl,
                    origin=n.LibraryOrigin(
                        library.name, "its provided state", use.span, decl.name, zones
                    ),
                )
                for decl in state.decls
            ),
        )
    return replace(library, state=state, **stamped)  # type: ignore[arg-type]


def _stamp_contracted_calls(use: n.UsesDecl, library: n.Library) -> n.Library:
    """`library` with every call of a function its Definition Contract names
    carrying that row (`n.Call.contract`), so typecheck types the call against
    the row whatever the game answered."""
    rows = {r.name: r for r in _contract_rows(library, "functions")}
    if not rows:
        return library
    stamps = {
        name: n.ContractStamp(
            library=library.name,
            row=_spelled_contract(row),
            param_types=tuple(p.type_name for p in row.params),
            result_type=row.result_type,
            uses_span=use.span,
            row_span=row.span,
        )
        for name, row in rows.items()
        if isinstance(row, n.FunctionContract)
    }

    def stamp(value: object) -> object:
        if isinstance(value, tuple):
            return tuple(stamp(item) for item in value)
        if isinstance(value, n.Call) and value.func in stamps:
            return replace(
                value, args=cast(tuple[n.Expr, ...], stamp(value.args)), contract=stamps[value.func]
            )
        return _traverse(value, lambda _field, v: stamp(v))

    return replace(
        library,
        rules=cast(tuple[n.RuleDef, ...], stamp(library.rules)),
        move_types=cast(tuple[n.MoveTypeDef, ...], stamp(library.move_types)),
        functions=cast(tuple[n.FunctionDef, ...], stamp(library.functions)),
        procedures=cast(tuple[n.ProcedureDef, ...], stamp(library.procedures)),
    )


def _library_nodes(library: n.Library, game: n.Game) -> list[tuple[object, str]]:
    """Every node of what `library` brings into `game`, with the definition
    that holds it, in the designer's words: its move types, functions and
    procedures, its provided state, and the rules the game activates. A rule
    no game activates is checked against its library alone (decisions.md
    "Family libraries")."""
    activated = _activated_rule_names(game)
    found: list[tuple[object, str]] = []
    for field, noun in _LIBRARY_DEF_KINDS:
        for definition in getattr(library, field):
            if field == "rules" and definition.name not in activated:
                continue
            where = f"{noun} `{definition.name}`"
            found.extend((nd, where) for nd in _walk(definition))
    if library.state is not None:
        found.extend((nd, "its provided state") for nd in _walk(library.state))
    return found


def _library_calls(library: n.Library, game: n.Game) -> list[tuple[n.Call, str]]:
    """Every call `library` brings into `game` (`_library_nodes`)."""
    return [(nd, where) for nd, where in _library_nodes(library, game) if isinstance(nd, n.Call)]


def _check_library_clause_gates(
    game: n.Game, use: n.UsesDecl, library: n.Library, bag: DiagnosticBag
) -> None:
    """What a library brings in that a game clause gates, checked against the
    game's clauses and reported on its `uses` line.

    The Owner Guard for every such construct a library brings in: the game's
    author wrote the `uses` line and lacks the clause, and the construct sits
    in a file they did not write. Each gate's own check stays the Owner Guard
    for what the game writes, and is the Shadow Guard for what is spliced,
    which never reaches it while `resolve` raises on this pass's refusals
    before splicing on.

    One refusal per gate, naming everything the library writes that the gate
    refuses, and where; a construct two gates refuse is reported by the first,
    as the gates themselves do. The fix offered is the game's to make, never an
    edit to the library, whose author is someone else.

    Asked only of a library `check_library_alone` passes (`_apply_uses`): a
    library at fault in itself -- a Primitive it calls or names in a round's
    query slot, a malformed contract row -- is its author's to fix whatever
    imports it, so that refusal stands alone and the game is asked no clause
    for text the library may not hold."""
    nodes = _library_nodes(library, game)
    # A call of a Kernel Definition Contract the library writes a row for is
    # that row's to judge: the game answers it or is told to on this same
    # line (`_check_definition_requirement`), once.
    claimed: set[object] = set(_contracted(library, "functions") & K.KERNEL_CONTRACT_NAMES)
    for gate in _CLAUSE_GATES:
        if not gate.unmet(game):
            continue
        reached: dict[Said, dict[str, Span | None]] = {}
        refused: list[Span] = []
        # Claimed once the gate has every occurrence, so a member recurring in
        # a second definition is named there too; a later gate skips it.
        keys: set[object] = set()
        for nd, where in nodes:
            phrases = gate.needs(nd, game)
            if not phrases:
                continue
            key = nd.func if isinstance(nd, n.Call) else nd
            if key in claimed:
                continue
            keys.add(key)
            at = getattr(nd, "span", None)
            if at is not None:
                refused.append(at)
            for phrase in phrases:
                reached.setdefault(phrase, {}).setdefault(where, at)
        claimed |= keys
        if not reached:
            continue
        listing = Sentence.join(" and ", (
            phrase + " (in "
            + Sentence.join(", ", (cite_where(where, at) for where, at in places.items()))
            + ")"
            for phrase, places in reached.items()
        ))
        verb, _, rest = gate.reads.partition(" ")
        reads = f"{verb}s {rest}" if len(reached) == 1 else gate.reads
        # The sentence names each definition once; a definition the gate
        # refuses at several places stands on each.
        bag.error(
            cite_library(library.name, None) + f" {gate.verb} " + listing
            + f", which {reads}, but {gate.lacks(game)} — "
            + naming_library(gate.fix(game), library.name, None),
            use.span,
            stands_on=tuple(refused),
            code=Code.LIBRARY_REQUIREMENT_UNMET,
        )
    _check_library_lines_span(game, use, library, _library_calls(library, game), bag)


def _check_library_lines_span(
    game: n.Game,
    use: n.UsesDecl,
    library: n.Library,
    calls: list[tuple[n.Call, str]],
    bag: DiagnosticBag,
) -> None:
    """The board's size against a literal `lines(k)` a library writes: the one
    board gate judged on an argument, read off the same `BoardEntry.lines`
    bound `_check_board_call` holds a game's own call to. A board the registry
    refuses outright is the `board:` clause's refusal, by `_resolve_board`."""
    if game.board is None:
        return
    try:
        entry = board_entry(game.board.family, game.board.args)
    except OwnerGuardError:
        return
    # Shadow Guard: a board that declares no lines at all is the lines row of
    # `_BOARD_NEED_GATES`'s refusal (its Owner Guard), told on this same line;
    # the span is judged only where some length is declared.
    if not entry.answers("lines"):
        return
    for call, where in calls:
        if call.func != "lines" or len(call.args) != 1:
            continue
        arg = call.args[0]
        if not isinstance(arg, n.IntLit):
            continue
        try:
            entry.lines(arg.value)
        except OwnerGuardError:
            board = _board_spelling(game)
            bag.error(
                cite_library(library.name, None) + f" calls `lines({arg.value})` (in "
                + cite_where(where, call.span)
                + f"), which reads lines of {arg.value} cells off the board, "
                f"but this game's `board: {board}` has none — declare a board "
                f"that does",
                use.span,
                code=Code.LIBRARY_REQUIREMENT_UNMET,
            )


def _check_library_collisions(
    game: n.Game,
    libraries: list[tuple[n.UsesDecl, n.Library]],
    bag: DiagnosticBag,
) -> None:
    """The three-way collision matrix — game / library / engine — swept across
    every definition kind in `_LIBRARY_DEF_KINDS` rather than the kinds that
    happen to collide in today's corpus (decisions.md "Closed-domain
    completeness": sweep the class, don't patch the instance).

    The engine leg covers the two registries whose names share ONE namespace with
    a game's definitions: rules (the stdlib rule index, which library rules splice
    into `game.rules`) and native call functions — two different namespaces, which
    is why the leg is named for the engine rather than for either of them. Kernel MOVE types are deliberately not a cell: they and a game's
    `move_type` definitions are two disjoint consult paths that never merge
    (`stdlib/moves.py`, and Stud/Skat/Schnapsen/Coup all rely on it), so a guard
    here would reject four games that are correct today."""
    for field, noun in _LIBRARY_DEF_KINDS:
        local = {d.name: d for d in getattr(game, field)}
        from_libraries: dict[str, LibraryCitation] = {}
        for use, library in libraries:
            # A definition the library also contracts for is the library's own
            # contradiction (`_check_definition_claims`); the game answering
            # the row did what the row asked.
            contracted = _contracted(library, field) if field in _CONTRACT_ROWS else frozenset()
            for definition in getattr(library, field):
                if definition.name in local and definition.name in contracted:
                    continue
                defined = cite_library(library.name, definition.span)
                if definition.name in local:
                    bag.error(
                        f"{noun} " + cite_named(local[definition.name], f"'{definition.name}'")
                        + " is defined by this game and also by " + defined
                        + " — `uses` imports, it does not inherit, so there is no "
                        f"override: rename the game's {noun}, or drop it and use "
                        + defined + "'s",
                        local[definition.name].span,
                        code=Code.NAME_TAKEN,
                    )
                elif definition.name in from_libraries:
                    bag.error(
                        f"{noun} " + cite_named(definition, f"'{definition.name}'")
                        + " is defined by both "
                        + from_libraries[definition.name] + " and " + defined
                        + " — resolution is flat, so neither wins; "
                        "use only one of them, or rename in one library",
                        use.span,
                        code=Code.NAME_TAKEN,
                    )
                else:
                    from_libraries[definition.name] = defined

    stdlib_rule_index = stdlib_rules()
    for _, library in libraries:
        for rule in library.rules:
            if rule.name in stdlib_rule_index:
                shadowed = stdlib_rule_index[rule.name]
                bag.error(
                    cite_library(library.name, rule.span)
                    + f" defines rule " + cite_named(rule, f"'{rule.name}'") + f", which shadows "
                    + cite_definition(STDLIB_NAME, f"rule `{rule.name}`", shadowed.span)
                    + " — delete it (`active_rules` resolves it from the stdlib), or "
                    "rename it if the body genuinely differs",
                    rule.span,
                    code=Code.NAME_TAKEN,
                )
        for fn in library.functions:
            # The WHOLE registry, unlike the namespace `_library_slot_names`
            # gives a library's CALLS: naming and calling are different
            # questions. A library body may not CALL a game-local Primitive,
            # but a library function that TAKES one's name shadows it in every
            # legacy game that imports the library — and a library cannot know
            # which games those are, so the widest namespace is the only sound
            # one here, and it reports to the library's own author.
            if fn.name in CALL_FUNCS:
                bag.error(
                    cite_library(library.name, fn.span) + f" defines function " + cite_named(fn, f"'{fn.name}'") + f", "
                    f"which shadows the native function of the same name; rename "
                    f"it (a call would type-check against the native signature "
                    f"but run this one instead)",
                    fn.span,
                    code=Code.NAME_TAKEN,
                )
            elif fn.name in K.KERNEL_CONTRACT_NAMES:
                row = K.CONTRACTS[fn.name]
                bag.error(
                    cite_library(library.name, fn.span) + f" defines function "
                    + cite_named(fn, f"'{fn.name}'") + f", which answers the "
                    f"kernel's `{row.spelled}` — only a game answers it; a "
                    f"library that needs the fact writes the row in `requires` "
                    f"(`{row.spelled}`)",
                    fn.span,
                    code=Code.LIBRARY_REACHES_ONE_GAME,
                )
            elif (slot := _round_query_slot(fn.name)) is not None:
                bag.error(
                    cite_library(library.name, fn.span) + f" defines function " + cite_named(fn, f"'{fn.name}'") + f", "
                    f"which has the name of the language's own `{fn.name}` that {slot} "
                    f"names; in a game whose round names it, that slot runs the "
                    f"language's `{fn.name}` and never calls this function — rename it",
                    fn.span,
                    code=Code.NAME_TAKEN,
                )


# Where a name a library injects can land in the game, as (game field, the noun
# a diagnostic calls it). Read off `_classify`'s precedence chain plus the
# namespaces that own a name outside it (positions; the definition kinds). This
# is the axis `_game_bindings` sweeps, so a namespace added to `_classify` or a
# def kind added to `_LIBRARY_DEF_KINDS` without an entry here fails a static
# test rather than silently leaving a hole a library could inject through.
_INJECTABLE_TARGETS: tuple[tuple[str, str], ...] = (
    ("zones", "zone"),
    ("positions", "position domain"),
    # The definition kinds, with the SAME nouns as `_LIBRARY_DEF_KINDS` so
    # the same-kind skip below matches by noun. Pinned equal to it by
    # `tests/test_family_libraries.py::test_injectable_targets_cover_every_def_kind`.
    ("functions", "function"),
    ("move_types", "move type"),
    ("rules", "rule"),
    ("procedures", "procedure"),
)


def _game_bindings(game: n.Game) -> dict[str, tuple[str, Span | None]]:
    """Every name the game binds that a bare reference could resolve to, mapped
    to (the noun for a diagnostic, the span to point at). Built in `_classify`
    precedence order with `setdefault`, so when a game reuses one name across its
    own namespaces (which the base language allows — the author wrote both and
    can see both) the reported noun is the one a reference actually resolves to.

    Deck values have no declaration site, so their span is None; the caller
    points at the library's injected declaration instead, which is the only text
    an author can edit to fix the clash."""
    bindings: dict[str, tuple[str, Span | None]] = {}
    for nd in _walk(game):
        if isinstance(nd, n.StateDecl):
            bindings.setdefault(nd.name, ("state variable", nd.span))
    for zone in game.zones:
        bindings.setdefault(zone.name, ("zone", zone.span))
    deck = game.deck
    if _deck_known(deck):
        for suit in suit_names(deck):
            bindings.setdefault(suit, ("suit value", None))
        for rank in rank_names(deck):
            bindings.setdefault(rank, ("rank value", None))
    for direction in SEAT_DIRECTION_VALUES:
        bindings.setdefault(direction, ("direction value", None))
    for pos in game.positions:
        bindings.setdefault(pos.name, ("position domain", pos.span))
    for field, noun in _INJECTABLE_TARGETS:
        if field in ("zones", "positions"):
            continue  # already added above, with their own spans
        for definition in getattr(game, field):
            bindings.setdefault(definition.name, (noun, definition.span))
    # The round slots' callback names: the game names them in its rounds, so a
    # library may not bring one in as a definition of its own. Lowest
    # precedence, added last, so a real game binding keeps the reported noun.
    for value_fn in VALUE_NAMES:
        bindings.setdefault(value_fn, ("round callback", None))
    return bindings


def _check_library_shadows_game(
    game: n.Game,
    libraries: list[tuple[n.UsesDecl, n.Library]],
    bag: DiagnosticBag,
) -> None:
    """A name a library injects into the game must not already name something in
    the game — in ANY namespace, not merely the same kind.

    `_check_library_collisions` owns the same-kind diagonal (a library function
    over a game function is an attempted override) and `_check_state_claims` owns
    provided-over-game-state; this owns everything off both — a provided name or
    a library definition landing on the game's zones, deck values, positions, or
    definitions of a DIFFERENT kind. Those are the silent traps: a `uses` import
    adds names and cannot override, and the game's author never opens the library
    file, so a bare reference they write meaning their own zone or the suit
    `hearts` would resolve to the library's variable instead, or the reverse. The
    base language lets a game reuse one name across its own namespaces because the
    author wrote and can see both; here one side is invisible, which is the whole
    difference.

    The refusal is deliberately CONSERVATIVE: a coincidence is refused even where
    `_classify` precedence would keep it harmless (a library `function` named
    after a game `state` variable, which a reference never confuses), because the
    rule a designer holds is "a library may not bring in a name you already use",
    not a table of safe precedence pairs. No corpus game pays for it.

    Matched by NAME, not `ref_kind`: this runs before classification (like
    `_check_provided_readonly`), which is what lets it see a zone reached only
    through the bare-string `round … into <zone>` slot that classification never
    stamps — the silent half of the collision matrix that a classify-based check
    would leave open.

    Reported naming the library, because the game author cannot see what they
    collided with. The span points at the game's own declaration when it has one
    (a zone, a definition), and at the library's injected declaration for a deck
    value, which has none."""
    game_names = _game_bindings(game)
    def_nouns = {noun for _, noun in _LIBRARY_DEF_KINDS}
    # The name each library's Definition Contract rows make the game define.
    contracted_by: dict[str, LibraryCitation] = {
        r.name: cite_library(library.name, r.span)
        for _, library in libraries
        for field, _noun, _cls in CONTRACT_KINDS
        for r in _contract_rows(library, field)
    }
    for use, library in libraries:
        own_rows = frozenset(
            r.name for r in library.requires if not isinstance(r, n.RequireDecl)
        )
        injected: list[tuple[str, str, Span | None]] = [
            (decl.name, "provided state", decl.span)
            for decl in (library.state.decls if library.state is not None else ())
        ]
        for field, noun in _LIBRARY_DEF_KINDS:
            for definition in getattr(library, field):
                injected.append((definition.name, noun, definition.span))

        for name, inject_noun, inject_span in injected:
            hit = game_names.get(name)
            if hit is None:
                continue
            game_noun, game_span = hit
            # The two pairs other Owner Guards already report — skip them so one clash
            # yields one diagnostic. Same-kind definition collisions are
            # `_check_library_collisions` ("does not inherit"); a provided name
            # over the game's own state is `_check_state_claims`.
            if inject_noun == game_noun and inject_noun in def_nouns:
                continue
            if inject_noun == "provided state" and game_noun == "state variable":
                continue
            # A library function taking a round callback's name is
            # `_check_library_collisions`'s, which names the slot.
            if inject_noun == "function" and game_noun == "round callback":
                continue
            # A name the library both holds and contracts for is its own
            # contradiction, told to its author by `_check_contract_names`.
            if name in own_rows:
                continue
            asked_by = contracted_by.get(name)
            if asked_by is not None and game_noun in def_nouns:
                # The game's definition answers another library's contract, so
                # renaming it is not a fix the game's author can take.
                bag.error(
                    cite_library(library.name, inject_span)
                    + f" brings in {inject_noun} " + cite_where(f"'{name}'", inject_span)
                    + ", but " + asked_by + " has this game define "
                    + cite_where(f"'{name}'", game_span) + f" as a "
                    f"{game_noun} — the two libraries cannot both be used: drop "
                    f"one `uses` line",
                    use.span,
                    code=Code.NAME_TAKEN,
                )
                continue
            bag.error(
                cite_library(library.name, inject_span)
                + f" brings in {inject_noun} " + cite_where(f"'{name}'", inject_span)
                + ", but this game already uses " + cite_where(f"'{name}'", game_span)
                + f" as a {game_noun} — a `uses` "
                f"import adds names without overriding, and the game's author "
                f"cannot see " + cite_library(library.name, inject_span)
                + "'s, so the two would silently mean different things: rename one",
                game_span if game_span is not None else inject_span,
                code=Code.NAME_TAKEN,
            )


def _check_state_claims(
    game: n.Game,
    libraries: list[tuple[n.UsesDecl, n.Library]],
    bag: DiagnosticBag,
) -> _StateClaims:
    """Refuse every way two claims on one state name can collide, and report which
    names survive as PROVIDED.

    A state name can be claimed from three places — the game's own `state { }`, a
    library's `state { }`, and a library's `requires { }` — and only two
    coexistences are legal: a requirement the game answers, and two libraries
    requiring one name, which one game declaration answers. The rest are refused:

    - A library that both provides and requires a name is incoherent, not merely
      redundant. The two clauses point opposite ways — `state` says the library
      owns the initial value, `requires` says the game picks it — so there is no
      reading under which both hold.
    - A game declaring what a library provides is the state face of "`uses`
      imports, it does not inherit". Keeping the game's would be an override;
      keeping the library's would discard a declaration the author wrote.
    - Two libraries providing one name have no winner, because resolution is
      flat. Picking one by `uses` order would make the game's meaning depend on
      the order of its import lines.
    - A requirement answered by ANOTHER library's provision is refused because
      `requires` says the including GAME declares the name. Letting a second
      library's variable answer it would couple two libraries through a name
      neither mentions the other in, and would do it silently.

    Each is reported where its author can fix it: the provision's own span when
    the library contradicts itself, the game's declaration when the game
    shadows, and the `uses` line when two imports disagree."""
    declared: dict[str, n.StateDecl] = {}
    for node in _walk(game):
        if isinstance(node, n.StateBlock):
            for decl in node.decls:
                declared.setdefault(decl.name, decl)

    provided: dict[str, LibraryCitation] = {}
    provider: dict[str, str] = {}
    contested: set[str] = set()
    # A Definition Contract row claims no state name: `_check_definition_claims`
    # owns its collisions, so the state sweep reads the keyed rows alone.
    for use, library in libraries:
        required = {r.name for r in _keyed_rows(library)}
        for decl in library.state.decls if library.state is not None else ():
            if decl.name in required:
                contested.add(decl.name)
                bag.error(
                    cite_library(library.name, decl.span)
                    + " both provides and requires state "
                    + cite_named(decl, f"'{decl.name}'") + " — `state` owns the variable and its initial "
                    f"value, `requires` leaves both to the including game, so a "
                    f"name can be one or the other: drop it from whichever "
                    f"clause is wrong",
                    decl.span,
                    code=Code.REQUIRES_WHAT_IS_PROVIDED,
                )
            elif decl.name in provided:
                contested.add(decl.name)
                bag.error(
                    "state " + cite_named(decl, f"'{decl.name}'") + " is provided by both "
                    + provided[decl.name] + " and " + cite_library(library.name, decl.span)
                    + " — resolution is flat, so neither wins; use only one of them, "
                    "or rename in one library",
                    use.span,
                    code=Code.NAME_TAKEN,
                )
            elif decl.name in declared:
                contested.add(decl.name)
                bag.error(
                    "state " + cite_named(declared[decl.name], f"'{decl.name}'")
                    + " is declared by this game and also "
                    "provided by " + cite_library(library.name, decl.span)
                    + " — `uses` imports, it does not inherit, so there is no override: delete the "
                    "game's declaration and read " + cite_library(library.name, decl.span)
                    + "'s, or rename the game's",
                    declared[decl.name].span,
                    code=Code.NAME_TAKEN,
                )
            else:
                provided[decl.name] = cite_library(library.name, decl.span)
                provider[decl.name] = library.name

    for use, library in libraries:
        for want in _keyed_rows(library):
            owner = provider.get(want.name)
            if owner is not None and owner != library.name:
                contested.add(want.name)
                bag.error(
                    cite_library(library.name, want.span)
                    + " requires state " + cite_where(f"'{want.name}'", want.span) + ", which "
                    + provided[want.name]
                    + " provides — a requirement names "
                    "state the including GAME declares, and is not answered by "
                    "another library's provision; declare it in the game and "
                    "rename one of the two",
                    use.span,
                    code=Code.REQUIRES_WHAT_IS_PROVIDED,
                )
    return _StateClaims(provided=provided, contested=frozenset(contested))


def _check_provided_readonly(
    game: n.Game, provided: dict[str, LibraryCitation], bag: DiagnosticBag
) -> None:
    """A game may READ library-provided state and may not WRITE it.

    Runs BEFORE the splice, over the game's own text alone, which is the only
    moment the distinction exists: afterwards a provided variable is one of the
    game's own state declarations and the library's definitions — which write
    their own state freely — are indistinguishable from the game's.

    Every write form is swept, not just `:=`: `_STATE_WRITE_SITES` is the
    executor's own set of state-writing statements, so `rotate` and a `turns …
    again <flag>` are covered by construction rather than by remembering them.

    Matched by NAME rather than by `ref_kind`, because `_apply_uses` runs before
    classification — deliberately, since the splice is what later passes must see
    a flat game after. That is sound for the class this Owner Guard owns: a write
    target must classify as a state variable (`_bad_write_target`), and a provided
    name IS one. The one case where the two readings differ is a game-local binder
    named after a provided variable; the shadow itself belongs to
    `_check_provided_shadowed_by_binder` below, and a write THROUGH such a binder
    draws both diagnostics — two true sentences about one name, with the same fix
    — rather than the write going unreported because some other construct in the
    game happens to bind the same word.

    Reported to the GAME's author, unlike `_check_library_encapsulation` next
    door: the game's author wrote the assignment and is the only one who can
    withdraw it."""
    for node in _walk(game):
        name = _written_state_name(node)
        if name is None or name not in provided:
            continue
        owner = provided[name]
        bag.error(
            "cannot write " + cite_where(f"'{name}'", owner.span) + ": " + owner
            + " provides it. Provided state belongs to " + owner
            + " — the game may read it, but only " + owner + "'s own definitions "
            "may write it. Keep a state variable of the game's own for what the "
            "game must change, or have " + owner + " expose a procedure that makes "
            "the change",
            getattr(node, "span", None),
            code=Code.NOT_WRITABLE,
        )


# Binder-introducing node kinds whose introduced SPELLING is the game AUTHOR'S TO
# CHOOSE, as against the kinds nobody writing a game gets to name (`any player
# where` always binds `player`, an aggregation always binds `card`, a transfer
# filter binds the content noun, a position query binds the domain's noun). Both
# halves shadow identically, so this is not a scoping table: it decides only
# whether a collision with a provided name has anything at the refusal site to
# rename, and therefore which fix the diagnostic prescribes.
#
# Membership is one claim: the spelling is the AUTHOR'S TO CHOOSE — respelling it
# is an edit that leaves the game otherwise unchanged. Neither "the grammar has a
# free `NAME` there" nor "some text of the game's fixes it" is that test, and each
# mis-sorts a member. `each <role> simultaneously` takes a free `NAME`, but
# `SIMULTANEOUS_ROLES` admits one spelling, so there is no other name to write. A
# transfer filter's noun follows `cards:`/`pieces:`, which is the game's own text,
# but changing it means writing a game of the other content kind rather than
# renaming a binder. And `n.DomainQuery`'s bare form takes its noun from the
# game's own `positions { }` row, which IS the author's to choose — that kind is
# filed under the language because the only sub-position that is theirs is one
# `_game_bindings` holds, and `_check_provided_shadowed_by_binder` skips those, so
# no cell reaching the guard through this kind is respellable. Pinned against
# `_node_binders`'s own domain by
# `tests/test_family_libraries.py::test_the_author_chosen_split_classifies_every_
# binding_kind`, so a new binding node kind must be filed under one side or the
# other rather than defaulting to either.
_AUTHOR_CHOSEN_BINDERS: frozenset[type] = frozenset(
    {n.ForEach, n.Turns, n.HostedPoll, n.LetStmt, n.ProduceArm}
)


def _check_provided_shadowed_by_binder(
    game: n.Game, provided: dict[str, LibraryCitation], bag: DiagnosticBag
) -> None:
    """A name the GAME introduces into a scope narrower than the game may not be
    spelled like a library-provided state variable.

    The binder face of `_check_library_shadows_game`, turning on the same
    visibility asymmetry. `_classify` tries `locals` before `state_vars`, so
    inside the binder's scope the bare name IS the binder and the provided
    variable cannot be read there — and the game's author never opens the
    library file to learn that the spelling was taken. That invisibility is what
    puts this outside the base language's shadowing carve-out, whose whole
    justification is that a binder is scoped strictly narrower than a same-named
    outer declaration the author WROTE (`RESERVED_VALUE_NAMES`'s docstring).

    The class is closed at the two registries that own it: `_introduced_binders`
    for the binders a body walk meets, and `_PARAM_BEARING` for the declaration
    parameters, which scope to their own guard/effect/body and so are
    deliberately not in the first. A `_PARAM_BEARING` row whose parameters scope
    no DSL body is skipped by that declared property: a Primitive's parameters
    label a Python signature and key its `reads` binders, so no DSL text sits
    inside their scope and there is nothing to shadow.

    A spelling the game already binds at DECLARATION level is left to the two
    Owner Guards that own that level — its own `state { }`, phase-local blocks
    included, is `_check_state_claims`, and its zones, positions, deck values and
    definitions are `_check_library_shadows_game`. For a provided name in
    `_game_bindings` one of those refuses the clash in full and with the fix on
    the side that can take it, so a second sentence here would add nothing; over
    a declared position domain, whose noun a position query binds, it would add a
    false one, since that spelling is the author's own `positions { }` row to
    respell. One clash, one diagnostic — the skip
    `_check_library_shadows_game` already keeps for its own two siblings.

    The game's flavor is passed rather than defaulted, unlike
    `_check_reserved_binders` next door: the transfer/reveal filter binder is the
    one binder whose spelling varies with content kind, and a piece game's
    `piece` is exactly as shadowing as a card game's `card`.

    Runs BEFORE the splice, for the reason every rule in `_apply_uses` does:
    after it a provided variable is one of the game's own declarations, and a
    binder shadowing one of those is the ordinary idiom the base language allows.
    That also scopes the rule correctly — a LIBRARY's own binder over its own
    provided state is ordinary shadowing, since its author wrote and can see
    both.

    Reported to the GAME's author either way — that is where the shadow is
    written, and the file they have open — but the prescribed fix follows the
    binder, because only one of the two sides can take it. A spelling the author
    chose is theirs to respell. One they did not choose is not respellable at
    all, so the only text that can change is the library's declaration, and
    "rename the binder" there would be advice nobody can follow."""
    if not provided:
        return
    declared = _game_bindings(game)

    def check(name: str, noun: str, chosen: bool, span: Span | None) -> None:
        library = provided.get(name)
        if library is None or name in declared:
            return
        if chosen:
            bag.error(
                f"{noun} " + cite_where(f"'{name}'", span) + " is spelled like state "
                + cite_where(f"'{name}'", library.span) + ", which "
                + library + " provides — wherever this name is in scope the bare "
                f"word is the {noun}, so the provided variable cannot be read "
                f"there, and nothing in this file says the spelling was taken: "
                f"rename the {noun}",
                span,
                code=Code.NAME_TAKEN,
            )
        else:
            bag.error(
                library + " provides state " + cite_where(f"'{name}'", library.span)
                + f", and this form "
                "binds " + cite_where(f"'{name}'", span) + " — inside its scope the bare name is the binder, "
                f"so the provided variable cannot be read here. The spelling is "
                f"not this game's to choose, so there is nothing here to rename: "
                f"rename " + library + "'s variable",
                span,
                code=Code.NAME_TAKEN,
            )

    for node in _walk(game):
        chosen = type(node) in _AUTHOR_CHOSEN_BINDERS
        # One node, one sentence per spelling: a `let` binds `name` and `index`
        # from one span, and `let limit[limit] = 1` spells them the same.
        for name in dict.fromkeys(_introduced_binders(node, game.content_flavor)):
            check(name, "binder", chosen, getattr(node, "span", None))
    for row in _PARAM_BEARING.values():
        if not row.scopes_body:
            continue
        for decl in row.reach(game):
            for param in decl.params:
                check(param.name, row.noun, True, param.span)


def _game_declarations_of(game: n.Game, name: str) -> list[str]:
    """Every kind of thing `name` is declared as in the game, as the noun a
    near-miss names: state, a zone, each definition kind, and a Primitive."""
    found: list[str] = []
    if any(
        decl.name == name
        for node in _walk(game)
        if isinstance(node, n.StateBlock)
        for decl in node.decls
    ):
        found.append("state")
    if any(zone.name == name for zone in game.zones):
        found.append("a zone")
    for field, noun in _LIBRARY_DEF_KINDS:
        if any(d.name == name for d in getattr(game, field)):
            found.append(f"a {noun}")
    if game.primitives is not None and any(d.name == name for d in game.primitives.decls):
        found.append("a Primitive")
    return found


def _definition_template(want: n.DefinitionContract) -> Said:
    """The definition that answers a row, as the game would write it, cited
    at the row."""
    if isinstance(want, n.MoveContract):
        return "a " + cite_named(want, f"`move_type {want.name} {{ effect {{ ... }} }}`") + " block"
    listed = ", ".join(f"{p.name} : {p.type_name}" for p in want.params)
    if isinstance(want, n.FunctionContract):
        return cite_named(want, f"`function {want.name}({listed}) = …`")
    return cite_named(want, f"`procedure {want.name}({listed}) {{ … }}`")


def _check_definition_requirement(
    game: n.Game,
    use: n.UsesDecl,
    library: n.Library,
    want: n.DefinitionContract,
    bag: DiagnosticBag,
) -> n.ContractStamp | None:
    """The definition leg of the contract: the game defines this move type,
    function or procedure itself, at the row's parameters. Reported on the
    game's `uses` line, to the game's author; the shapes the LIBRARY could get
    wrong are `_check_contract_shapes`', and ran before any game was consulted.

    Parameters are matched by position and by their type spelling, exactly: the
    row's parameter names are its own reading, since the library never names
    the game's binders. A function's RESULT is typecheck's: its type is inferred
    from the body, never declared, so the stamp returned for an answer that
    matches here carries the row's result to `typecheck`, which reports a
    mismatch on this same `uses` line.

    The near-misses worth naming: a game that declared the name as anything
    else has not forgotten it, and telling it to add a definition without
    saying why would read as the checker missing the declaration in front of
    it."""
    field, noun = _CONTRACT_KIND_OF[type(want)]
    spelled = want.name if isinstance(want, n.MoveContract) else _spelled_contract(want)
    head = cite_library(library.name, want.span) + f" requires {noun} " + cite_where(f"`{spelled}`", want.span)
    found = [d for d in getattr(game, field) if d.name == want.name]
    if len(found) > 1:
        # Shadow Guard of `_check_duplicate_names`, which refuses the duplicate
        # after the splice; counted here so the contract's guarantee does not
        # depend on that guard's coverage.
        bag.error(
            head + f", which game '{game.name}' defines {len(found)} times — a "
            f"requirement must name ONE definition",
            use.span,
            code=Code.REQUIREMENT_MATCHES_SEVERAL,
        )
        return None
    if not found:
        row = K.CONTRACTS.get(want.name) if isinstance(want, n.FunctionContract) else None
        if row is not None and row.defaulted and K.has_trick_order(game):
            return None  # answered by the driver's default
        if row is not None and want.name in K.TRICK_ORDER_CONTRACTS:
            # A Trick Order row answers only in a game with a Trick Order,
            # which answering `is_trump` declares.
            fix: Said = (
                _ANSWER_IS_TRUMP + " — the Trick Order's default answers this row"
                if row.defaulted
                else _ANSWER_IS_TRUMP
            )
            bag.error(
                head + f", which game '{game.name}' does not answer, since it "
                f"declares no Trick Order — " + fix,
                use.span,
                code=Code.LIBRARY_REQUIREMENT_UNMET,
            )
            return None
        others = _game_declarations_of(game, want.name)
        if others:
            bag.error(
                head + f", which game '{game.name}' declares as {others[0]} — the "
                f"row names a {noun}, so the definition belongs in "
                + _definition_template(want),
                use.span,
                code=Code.REQUIREMENT_MISMATCH,
            )
        else:
            table = (
                " or a `card_points { }` table"
                if isinstance(want, n.FunctionContract) and want.name == "card_points"
                else ""
            )
            bag.unknown(
                head + f", which game '{game.name}' does not define — add "
                + _definition_template(want) + table,
                want.name,
                _definitions_of_kind(game, want),
                use.span,
                code=Code.LIBRARY_REQUIREMENT_UNMET,
            )
        return None
    if isinstance(want, n.MoveContract):
        return None
    have = found[0]
    if len(have.params) != len(want.params):
        count = len(have.params)
        bag.error(
            head + f", but game '{game.name}' defines " + cite_named(have, f"`{want.name}`") + f" with {count} "
            f"parameter{'' if count == 1 else 's'}",
            use.span,
            code=Code.REQUIREMENT_MISMATCH,
        )
        return None
    for i, (got, wanted) in enumerate(zip(have.params, want.params), start=1):
        if got.type_name != wanted.type_name:
            bag.error(
                head + f", but game '{game.name}' defines " + cite_named(have, f"`{want.name}`") + f" whose "
                f"parameter {i} is `{got.type_name}`",
                use.span,
                code=Code.REQUIREMENT_MISMATCH,
            )
            return None
    return n.ContractStamp(
        library=library.name,
        row=_spelled_contract(want),
        param_types=tuple(p.type_name for p in want.params),
        result_type=want.result_type if isinstance(want, n.FunctionContract) else None,
        uses_span=use.span,
        row_span=want.span,
    )


def _check_definition_claims(
    game: n.Game,
    libraries: list[tuple[n.UsesDecl, n.Library]],
    bag: DiagnosticBag,
) -> frozenset[tuple[str, str]]:
    """Refuse the two ways a Definition Contract can be claimed from the wrong
    side, for every contractable kind, and report which (kind, name) pairs
    were ruled on.

    The state-claim rules one kind over (`_check_state_claims`), for the same
    reasons: a library that both defines and requires a definition points two
    ways at once, and a requirement answered by ANOTHER library's definition
    couples two libraries through a name neither mentions the other in. The
    game's own definition is the one answer, and
    `_check_definition_requirement` checks for it."""
    contested: set[tuple[str, str]] = set()
    for field, noun, _cls in CONTRACT_KINDS:
        keyword = _DEFINITION_KEYWORDS[field]
        defined_by: dict[str, LibraryCitation] = {}
        for _, library in libraries:
            for d in getattr(library, field):
                defined_by.setdefault(d.name, cite_library(library.name, d.span))
        for use, library in libraries:
            own = {d.name: d for d in getattr(library, field)}
            for want in _contract_rows(library, field):
                if want.name in own:
                    contested.add((field, want.name))
                    bag.error(
                        cite_library(library.name, own[want.name].span) + f" both defines and requires "
                        f"{noun} " + cite_where(f"'{want.name}'", want.span) + f" — `{keyword}` makes it the "
                        f"library's and `requires` leaves it to the including "
                        f"game, so a name can be one or the other: drop it from "
                        f"whichever clause is wrong",
                        own[want.name].span,
                        code=Code.REQUIRES_WHAT_IS_PROVIDED,
                    )
                elif want.name in defined_by:
                    contested.add((field, want.name))
                    bag.error(
                        cite_library(library.name, want.span) + f" requires {noun} " + cite_where(f"`{want.name}`", want.span) + f", "
                        "which " + defined_by[want.name] + " defines — a "
                        f"requirement names a {noun} the including GAME defines, "
                        f"and is not answered by another library's definition; "
                        f"define it in the game and rename one of the two",
                        use.span,
                        code=Code.REQUIRES_WHAT_IS_PROVIDED,
                    )
    return frozenset(contested)


def _check_zone_requirement(
    game: n.Game,
    use: n.UsesDecl,
    library: n.Library,
    want: n.RequireDecl,
    zoned: dict[str, list[n.ZoneDecl]],
    bag: DiagnosticBag,
) -> None:
    """The zone leg of the contract: the game declares this zone, in its
    `zones { }` block, at the library's index and type.

    The same "exactly one declaration" rule as the state leg, and for a weaker
    reason: `zones { }` is a game-level block with no phase-local form, so a
    second declaration is already a duplicate (`_check_duplicate_names`). The
    count is still checked here so the contract's guarantee does not depend on
    another Owner Guard's coverage.

    Reported on the game's `uses` line, to the game's author — the shape
    questions the LIBRARY could get wrong are `_check_contract_shapes`', and
    ran before any game was consulted."""
    spelled = _spelled_contract(want)
    found = zoned.get(want.name, [])
    if not found:
        # The near-miss worth naming: a game that declared the name as STATE has
        # not simply forgotten it, and telling it to add a zone without saying
        # why would read as the checker missing the declaration in front of it.
        as_state = any(
            decl.name == want.name
            for node in _walk(game)
            if isinstance(node, n.StateBlock)
            for decl in node.decls
        )
        if as_state:
            bag.error(
                cite_library(library.name, want.span) + f" requires zone " + cite_where(f"`{spelled}`", want.span) + f", which "
                f"game '{game.name}' declares as state — '{want.type_name}' is "
                f"a zone type, so the declaration belongs in `zones {{ }}`",
                use.span,
                code=Code.REQUIREMENT_MISMATCH,
            )
        else:
            bag.unknown(
                cite_library(library.name, want.span) + f" requires zone " + cite_where(f"`{spelled}`", want.span) + f", which "
                f"game '{game.name}' does not declare — add it to the game's "
                f"`zones {{ }}` block",
                want.name,
                {z.name for z in game.zones},
                use.span,
                code=Code.LIBRARY_REQUIREMENT_UNMET,
            )
        return
    if len(found) > 1:
        bag.error(
            cite_library(library.name, want.span) + f" requires zone " + cite_where(f"`{spelled}`", want.span) + f", which game "
            f"'{game.name}' declares {len(found)} times — a requirement must "
            f"name ONE declaration",
            use.span,
            code=Code.REQUIREMENT_MATCHES_SEVERAL,
        )
        return
    have = found[0]
    if have.index != want.index:
        shown_index = f"'{have.index}'" if have.index else "nothing"
        bag.error(
            cite_library(library.name, want.span) + f" requires zone " + cite_where(f"`{spelled}`", want.span) + f", but game "
            f"'{game.name}' declares it indexed by {shown_index}",
            use.span,
            code=Code.REQUIREMENT_MISMATCH,
        )
    wanted_args = tuple(a.name for a in want.type_args)
    have_args = tuple(a.name for a in have.type_ref.args)
    if (have.type_ref.name, have_args) != (want.type_name, wanted_args):
        shown = have.type_ref.name + (
            f"<{', '.join(have_args)}>" if have_args else ""
        )
        bag.error(
            cite_library(library.name, want.span) + f" requires zone " + cite_where(f"`{spelled}`", want.span) + f", but game "
            f"'{game.name}' declares it as `{shown}` — a zone type fixes the "
            f"per-observer projection, so the contract names the type the "
            f"library's definitions were written against",
            use.span,
            code=Code.REQUIREMENT_MISMATCH,
        )


def _check_requires(
    game: n.Game,
    use: n.UsesDecl,
    library: n.Library,
    bag: DiagnosticBag,
    skip: frozenset[str] = frozenset(),
    skip_definitions: frozenset[tuple[str, str]] = frozenset(),
) -> dict[tuple[str, str], n.ContractStamp]:
    """Check a library's `requires` contract against the game's declarations,
    and return the stamp each answering function or procedure carries on,
    keyed by (definition kind, name).

    An entry names state, a zone, or a definition the game defines, and the
    row's shape says which: a Definition Contract row is its own node, and a
    keyed row's type says state or zone (`is_zone_contract`). The zone leg is
    `_check_zone_requirement`, the definition leg
    `_check_definition_requirement`; what follows is the state one.
    `skip_definitions` is the definition twin of `skip`: the (kind, name)
    pairs `_check_definition_claims` has already ruled on.

    `skip` names the state `_check_state_claims` has already ruled on — provided
    names and contested ones. Without it a name claimed both ways would fail
    twice, and the second failure ("the game does not declare it") would be
    advice pointing away from the real defect.

    Reported on the game's `uses` line, to the game's author: the author wrote
    that line, and an undeclared-name error surfacing from inside spliced library
    text would name symbols they never typed.

    What is checked is that EXACTLY ONE declaration of the name exists somewhere
    in the game, at the library's arity and type. Which `state { }` block holds
    it is not checked, and deliberately so: a phase's state block is the natural
    home for state that resets on phase re-entry, which is exactly what per-hand
    betting state is, and Stud declares all seven of `poker_betting`'s
    requirements inside `phase play`. A ZONE requirement has no such freedom to
    misuse: `zones { }` is game-level only, so `_check_zone_requirement` looks in
    exactly one place.

    That is weaker than "the library's definitions can read it where they run",
    and the gap is real rather than theoretical: move Kuhn's `limit` into `phase
    deal` while the imported `bet` runs in `phase betting`, and this check passes,
    typecheck passes, and the playout dies on a bare KeyError from
    `runtime/state.py`. The gap is NOT the import tier's — a plain game with no
    library reproduces it, one phase declaring what another reads — so closing it
    means use-site scope reachability for state generally, which this contract
    cannot stand in for. Recorded as a residual in issue #138, and in the ledger of
    tests/test_family_libraries.py. Narrowing the contract to game-level
    declarations would not close it either, and would reject Stud.

    Exactly one, and the count is the Owner Guard — not a tie broken by declaration
    order. Cross-block shadowing is legal in general (`_check_duplicate_names`),
    but the two shadowed declarations are answers to different questions and no
    fixed bias picks correctly: a shadow in the phase where the library's
    definitions run makes last-wins right, a shadow in some other phase makes
    first-wins right. This function used to take the first while `typecheck` and
    `runtime/driver.py` took the last, so a game could satisfy the contract on
    one declaration and bind the other. Refusing the shadow outright is the only
    answer that does not depend on a scope question the contract cannot see; it
    costs a `requires`d name nothing, because that name is the library's
    interface rather than game-private state (decisions.md "Family libraries" —
    the same reason the metamorphic rename transform excludes it)."""
    declared: dict[str, list[n.StateDecl]] = {}
    for node in _walk(game):
        if isinstance(node, n.StateBlock):
            for decl in node.decls:
                declared.setdefault(decl.name, []).append(decl)
    zoned: dict[str, list[n.ZoneDecl]] = {}
    for zone in game.zones:
        zoned.setdefault(zone.name, []).append(zone)
    # Requirements already reported as malformed in the LIBRARY's own text.
    # Comparing one against the game's declaration derives a second error that
    # is worse than useless: it renders the malformation as a MISMATCH, so a
    # non-role index prints as "a scalar" and an unresolvable type prints as
    # the game's type being wrong — blaming the game author for a defect in a
    # file they did not write, and, when the name is undeclared, advising them
    # to add a declaration the language would refuse.
    #
    # Matched by SPAN rather than by re-deriving which requirements are
    # well-formed. That is what makes this complete over the class rather than
    # over the two members known today: a requirement is malformed exactly when
    # some Owner Guard has already reported against its own span, so a future
    # Owner Guard on a new `RequireDecl` field is covered the day it lands,
    # with nothing to remember here. The malformation Owner Guards run before
    # this pass, in `check_library_alone`, and report at the requirement's span
    # (`_check_require_indexes` for the index, `_check_library_encapsulation`
    # for the type name, `_check_contract_shapes` for the row's shape).
    #
    # This is the opposite direction from `skip`, which suppresses a downstream
    # report about a name the GAME's own claims already ruled on.
    malformed = {d.span for d in bag.items if d.span is not None}
    stamps: dict[tuple[str, str], n.ContractStamp] = {}
    for want in library.requires:
        # Span-keyed, so it speaks about EVERY leg and is hoisted above the
        # split: a malformed zone contract would otherwise get its shape error
        # in the library AND a mismatch pinned on the game, which is the second
        # report this suppression exists to prevent.
        if want.span is not None and want.span in malformed:
            continue
        if not isinstance(want, n.RequireDecl):
            field = _CONTRACT_KIND_OF[type(want)][0]
            if (field, want.name) in skip_definitions:
                continue
            stamp = _check_definition_requirement(game, use, library, want, bag)
            if stamp is not None:
                stamps[(field, want.name)] = stamp
            continue
        if is_zone_contract(want):
            # `skip` is the STATE-claim set (`_check_state_claims`), so it never
            # speaks about a zone name — reading it here would silently drop a
            # zone contract whenever the game happened to declare a state
            # variable of the same name.
            _check_zone_requirement(game, use, library, want, zoned, bag)
            continue
        if want.name in skip:
            continue
        found = declared.get(want.name, [])
        wanted = f"{want.name}{f'[{want.index}]' if want.index else ''}"
        spelled = f"{wanted} : {want.type_name}"
        if not found:
            # The near-miss worth naming: a game that defined the name as a
            # function (or any definition) has not forgotten it.
            others = _game_declarations_of(game, want.name)
            if others:
                bag.error(
                    cite_library(library.name, want.span) + f" requires state " + cite_where(f"`{spelled}`", want.span) + f", which "
                    f"game '{game.name}' declares as {others[0]} — the row names "
                    f"a `state {{ }}` variable, so the declaration belongs there",
                    use.span,
                    code=Code.REQUIREMENT_MISMATCH,
                )
                continue
            bag.unknown(
                cite_library(library.name, want.span) + f" requires state " + cite_where(f"`{spelled}`", want.span) + f", which "
                f"game '{game.name}' does not declare — add it to the game's "
                f"`state {{ }}` block with the initial value the game wants",
                want.name,
                {nd.name for nd in _walk(game) if isinstance(nd, n.StateDecl)},
                use.span,
                code=Code.LIBRARY_REQUIREMENT_UNMET,
            )
            continue
        if len(found) > 1:
            bag.error(
                cite_library(library.name, want.span) + f" requires state " + cite_where(f"`{spelled}`", want.span) + f", which "
                f"game '{game.name}' declares {len(found)} times — a requirement "
                f"must name ONE declaration, or which one the library's "
                f"definitions read depends on where they run; keep a single "
                f"declaration of " + cite_where(f"'{want.name}'", want.span),
                use.span,
                code=Code.REQUIREMENT_MATCHES_SEVERAL,
            )
            continue
        have = found[0]
        if have.index != want.index:
            # Rendered from the ROLE, not from the truthiness of the field: the
            # index is a member of a closed domain, and collapsing it to a
            # boolean printed "to be per-player, but … declares it as
            # per-player" for a `[team]`-against-`[player]` mismatch — the two
            # roles Bridge and Belote both use (issue #144). Both sides are
            # classified rather than assumed: `_check_require_indexes` has
            # already refused a requirement whose index names no role, and
            # resolve's state-index Owner Guard the declaration's.
            got = index_phrase(role_of(have.index) if have.index else None)
            need = index_phrase(role_of(want.index) if want.index else None)
            bag.error(
                cite_library(library.name, want.span) + f" requires state " + cite_where(f"`{spelled}`", want.span) + f" to be "
                f"{need}, but game '{game.name}' declares it as {got}",
                use.span,
                code=Code.REQUIREMENT_MISMATCH,
            )
        if (have.type_name, have.optional) != (want.type_name, False):
            bag.error(
                cite_library(library.name, want.span) + f" requires state " + cite_where(f"`{spelled}`", want.span) + f", but game "
                f"'{game.name}' declares it as "
                f"`{have.type_name}{'?' if have.optional else ''}`",
                use.span,
                code=Code.REQUIREMENT_MISMATCH,
            )
    return stamps


def _with_held_rules(game: n.Game, library_rules: dict[str, n.RuleDef]) -> n.Game:
    """`game` beside every library rule the splice holds aside and every
    standard library rule, activated or not, for the step to tell refusals
    standing on them."""
    held = (*library_rules.values(), *_stamped_stdlib_rules().values())
    return replace(game, rules=(*game.rules, *held))


def _definitions_of_kind(game: n.Game, want: n.DefinitionContract) -> frozenset[str]:
    """The game's own definitions of the kind a Definition Contract row asks for."""
    match want:
        case n.FunctionContract():
            return frozenset(f.name for f in game.functions)
        case n.MoveContract():
            return frozenset(m.name for m in game.move_types)
        case n.ProcedureContract():
            return frozenset(p.name for p in game.procedures)
        case _:
            assert_never(want)
