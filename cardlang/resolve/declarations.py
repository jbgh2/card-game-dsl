"""Resolve step: the game's declarations, before positions and rules.

Contract (decisions.md "Closed-domain completeness", write-time triage)
-----------------------------------------------------------------------
Assumes:      one flat game: the splice has run and raised.
Establishes:  ``game.ranking`` is the
              operative strength order: a ``ranking:`` convention keyword
              is expanded against the deck here (``_expand_ranking``), so
              no later pass may branch on ``ranking_convention`` for
              semantics — it survives only as the source-form record
              ``ir.emit`` prints.
              The step returns the reader clauses whose declarations its
              Owner Guards refused, for ``_check_unread_clauses``.
Now illegal:  a ``teams:`` list that does not PARTITION the seats
              (``_check_teams``); every consumer building ``{p: ti for ti,
              members in enumerate(game.teams) for p in members}`` — the
              driver, the returns path, and the readiness proofs — may
              therefore read it as one.
              In a game with a climbing round, a
              move type spelled like one of the engine's own actions
              (``_check_climb_action_names``, over
              ``primitives.engine_actions``): the action space's name block
              and every rendering may therefore assume no move type and no
              climb action share a word.
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import replace
from cardlang.diagnostic_codes import Code
from cardlang.ast import nodes as n
from cardlang.builtins.functions import (
    PRIMITIVE_CLIMB_ENGINES,
    PRIMITIVE_CLIMB_FOLLOWS,
    TRICK_ORDER_EXCLUDED_FUNCS,
    TRICK_ORDER_GATED_WINNERS,
    TRICK_WINNER_NAMES,
)
from cardlang import kernel_contracts as K
from cardlang.attribution import cite_library, cite_named, cite_origin
from cardlang.diagnostics import DiagnosticBag, Said, Span, near_misses
from cardlang.runtime.values import content_kind_clause
from cardlang.stdlib.enums import SEAT_DIRECTION_VALUES, rank_names, suit_names
from cardlang.stdlib.moves import LIBRARY_MOVE_TYPES
from cardlang.typecheck import card_content_forms
from cardlang.catalogue_pass import check_catalogues
from cardlang.resolve.walk import _walk
from cardlang.resolve.binders import _introduced_binders
from cardlang.resolve.reserved import RESERVED_VALUE_NAMES, _PARAM_BEARING, _RESERVED_WHY
from cardlang.resolve.slots import _ROUND_QUERY_NAMES
from cardlang.resolve.declared import (
    _component_known,
    _deck_known,
    _declared_suits_phrase,
    _map_climb_rounds,
)
from cardlang.resolve.crossings import _cite_in
from cardlang.resolve.clause_gates import (
    _ANSWER_IS_TRUMP,
    _CARD_CONTENT_GATE,
    _TRICK_ORDER_READERS,
    _climb_queries,
    _drop_trick_order,
    _round_trump_clauses,
)
from cardlang.resolve.round_winners import _refuses, _winner_refusals


def step(game: n.Game, bag: DiagnosticBag) -> tuple[n.Game, set[str]]:
    """The declarations step, in report order. Returns the game with its
    ranking expanded, its card points lowered and its climb engines
    resolved, and the reader clauses whose answers its Owner Guards
    refused."""
    _resolve_component_set(game, bag)
    _reject_card_content_clauses(game, bag)
    _resolve_direction(game, bag)
    game = _expand_ranking(game, bag)
    _resolve_ranking(game, bag)
    refused_clauses: set[str] = set()
    game = _resolve_card_points(game, bag, refused_clauses)
    _resolve_suit_ranking(game, bag, refused_clauses)
    game = _resolve_climb_engines(game, bag)
    _check_trick_order_partition(game, bag, refused_clauses)
    _check_piece_rounds(game, bag)
    _check_duplicate_names(game, bag)
    _check_climb_action_names(game, bag)
    if game.catalogues or game.rank_sequence is not None:
        check_catalogues(game, _label_namesakes(game).get, bag)
    _check_reserved_params(game, bag)
    _check_reserved_binders(game, bag)
    _resolve_max_length(game, bag)
    _check_teams(game, bag)
    return game, refused_clauses


def _check_reserved(
    name: str,
    kind: str,
    span: Span | None,
    bag: DiagnosticBag,
    reserved: frozenset[str] = RESERVED_VALUE_NAMES,
) -> None:
    if name in reserved:
        bag.error(
            f"{kind} '{name}' is a reserved word — {_RESERVED_WHY[name]} — "
            f"pick another name",
            span,
            code=Code.RESERVED_WORD,
        )


def _trick_order_named(game: n.Game) -> Said:
    """The game's Trick Order, named by the function that declares it."""
    return "function " + _cite_in(game, "function", "is_trump", "`is_trump`")


def _resolve_climb_engines(game: n.Game, bag: DiagnosticBag) -> n.Game:
    """Stamp each climbing round's engine (`n.ClimbEngine`) from its two slot
    names, the Owner Guard of the pairing: a `combinations` name is one of
    the game's Combination Catalogues, paired with a function of the game,
    or a registered lead query (`PRIMITIVE_CLIMB_ENGINES`), paired with its
    own follows query. Every later reader of a round's engine reads the
    stamp, never the names. A game runs one climb engine: the action space
    numbers one universe of plays."""
    catalogues = {c.name for c in game.catalogues}
    functions = {f.name for f in game.functions}
    origins = n.library_origins(game)

    def stamp(nd: n.ClimbRound) -> n.ClimbRound:
        lead, follows = nd.combos_fn, nd.follows_fn
        if lead in catalogues:
            origin = origins.get(id(nd))
            if origin is not None:
                # A library declares no catalogue (`library_catalogue_reject`),
                # so the name is the importing game's: a slot the game feeds.
                bag.error(
                    cite_origin(origin, nd.span) + f" holds a climbing round over "
                    f"`{lead}`, this game's combination catalogue — a catalogue "
                    f"belongs to the one game that declares it, so a library "
                    f"that several games import may not name one: write the "
                    f"round in the game",
                    nd.span,
                    code=Code.LIBRARY_REACHES_ONE_GAME,
                )
                return nd
            if follows in functions:
                return replace(nd, engine=n.DeclaredEngine(lead, follows))
            if follows in PRIMITIVE_CLIMB_FOLLOWS:
                bag.error(
                    f"climb round over the catalogue '{lead}' names `follows` query "
                    f"'{follows}', a registered engine's; a catalogue's plays "
                    f"follow by a function of the game — write "
                    f"`function {follows}_play(play : Combination, standing : "
                    f"Combination?) = …` and name it",
                    nd.span,
                    code=Code.CLIMB_ROUND_QUERIES,
                )
            else:
                bag.unknown(
                    f"climb round over the catalogue '{lead}': `follows` names "
                    f"'{follows}', which is no function of this game",
                    follows,
                    functions,
                    nd.span,
                    code=Code.UNKNOWN_FUNCTION,
                )
            return nd
        if lead in PRIMITIVE_CLIMB_ENGINES:
            own = PRIMITIVE_CLIMB_ENGINES[lead]
            if follows == own:
                return replace(nd, engine=n.RegisteredEngine(lead, follows))
            if follows in PRIMITIVE_CLIMB_FOLLOWS:
                # The runtime keys the engine by the lead query alone, so a
                # follows query from another engine would run over the wrong
                # engine's plays.
                bag.error(
                    f"climb round pairs `combinations` query '{lead}' "
                    f"with `follows` query '{follows}', which is another "
                    f"engine's; '{lead}' follows with '{own}'",
                    nd.span,
                    code=Code.CLIMB_ROUND_QUERIES,
                )
            elif follows in functions:
                named = next(f for f in game.functions if f.name == follows)
                bag.error(
                    "climb round `follows` names " + cite_named(named, f"'{follows}'")
                    + f", a function of this game; the registered engine '{lead}' "
                    f"follows with its own query '{own}'",
                    nd.span,
                    code=Code.CLIMB_ROUND_QUERIES,
                )
            else:
                bag.unknown(
                    f"climb round `follows` query '{follows}' is not a "
                    f"combination follows query; '{lead}' follows with '{own}'",
                    follows,
                    (own,),
                    nd.span,
                    code=Code.CLIMB_ROUND_QUERIES,
                )
            return nd
        bag.unknown(
            f"climb round `combinations` query '{lead}' is not a combination "
            f"lead query, nor a combination catalogue of this game",
            lead,
            (*PRIMITIVE_CLIMB_ENGINES, *catalogues),
            nd.span,
            code=Code.CLIMB_ROUND_QUERIES,
        )
        return nd

    stamped = _map_climb_rounds(game, stamp)
    assert isinstance(stamped, n.Game)
    engines = {nd.engine for nd in _walk(stamped) if isinstance(nd, n.ClimbRound) and nd.engine}
    if len(engines) > 1:
        from cardlang.runtime.primitives import engine_label

        names = sorted(engine_label(e) for e in engines)
        bag.error(
            f"a game runs one climb engine, and this one names {len(engines)}: "
            + ", ".join(f"'{x}'" for x in names)
            + " — the action space numbers one universe of plays",
            game.span,
            code=Code.CLIMB_ROUND_QUERIES,
        )
    return stamped


def _label_namesakes(game: n.Game) -> dict[str, str]:
    """Every name a Combination Shape's label may not take, with what it
    already names: a label is a value of the game's `Shape` enum, read bare
    (`play.shape is flush`), so it shares the namespace a deck's ranks and
    suits, the game's declarations and the language's round queries live
    in."""
    out: dict[str, str] = {}
    if _component_known(game.deck):
        out.update(dict.fromkeys(rank_names(game.deck), "a rank of the deck"))
        out.update(dict.fromkeys(suit_names(game.deck), "a suit of the deck"))
    out.update(dict.fromkeys(SEAT_DIRECTION_VALUES, "a seat direction"))
    out.update(dict.fromkeys(_ROUND_QUERY_NAMES, "a registered round query"))
    out.update(dict.fromkeys(LIBRARY_MOVE_TYPES, "a move type"))
    for nd in _walk(game):
        if isinstance(nd, n.StateDecl):
            out[nd.name] = "a state variable"
        elif isinstance(nd, n.Phase):
            out[nd.name] = "a phase"
    out.update({z.name: "a zone" for z in game.zones})
    out.update({f.name: "a function" for f in game.functions})
    out.update({p.name: "a procedure" for p in game.procedures})
    out.update({m.name: "a move type" for m in game.move_types})
    out.update({r.name: "a rule" for r in game.rules})
    out.update({c.name: "a combination catalogue" for c in game.catalogues})
    return out


def _check_climb_action_names(game: n.Game, bag: DiagnosticBag) -> None:
    """In a game with a climbing round, no move type is spelled like one of
    the engine's own actions (`primitives.engine_actions`: its pass, and a
    registered engine's announcements and interrupt decline). The two would render and announce
    alike to every seat, report one verb, and — for a nullary move an `offer`
    presents — share one action id, so the refusal is by name, whatever
    presents the move type and whether or not anything does. A library move
    type is judged in the game that imports it, where the climb is: a library
    holds no climbing round, so the clash is the game's, and its refusal
    carries the sentence the game's author reads (`attribution`)."""
    from cardlang.runtime import primitives

    owner: dict[str, str] = {}
    for nd in _walk(game):
        if not isinstance(nd, n.ClimbRound):
            continue
        if nd.engine is None:
            continue  # an unpaired round, refused by `_resolve_climb_engines`
        label = primitives.engine_label(nd.engine)
        owner.update(dict.fromkeys(primitives.engine_actions(nd.engine), label))
    for mt in game.move_types:
        engine = owner.get(mt.name)
        if engine is None:
            continue
        bag.error(
            f"move type " + cite_named(mt, f"`{mt.name}`") + f" is spelled like the climb engine "
            f"`{engine}`'s own action " + cite_named(mt, f"`{mt.name}`") + f" — a seat would see the "
            f"two alike; rename the move type",
            mt.span,
            for_game=None if mt.origin is None else (
                cite_origin(mt.origin, mt.span) + f" is spelled "
                f"like the climb engine `{engine}`'s own action " + cite_named(mt, f"`{mt.name}`") + f", "
                f"which this game's climbing round plays — a seat would see the "
                f"two alike, so a game whose climbing round uses `{engine}` "
                "cannot use " + cite_library(mt.origin.library, mt.span)
            ),
            code=Code.NAME_TAKEN,
        )


def _check_teams(game: n.Game, bag: DiagnosticBag) -> None:
    """`teams:` must PARTITION the seats — every seat in exactly one team.

    Every consumer already reads it as one: the driver and the OpenSpiel
    returns path both build `{p: ti for ti, members in enumerate(game.teams)
    for p in members}`, which is a partition or it is a lie. The three ways
    to break it were all accepted silently (issue #155), and the dict
    comprehension makes the worst one quiet rather than loud — a seat listed
    in two teams is assigned the LATER one, because a later key overwrites an
    earlier one, so the game plays on with that seat scoring for a team its
    author did not put it on.

    The Owner Guard belongs HERE, at the declaration, and not at any of the readers,
    because one of the readers is the information sets. A team zone family
    asks `domains.zone_observer_key` who owns an instance, which for a team
    is `rs.team_of.get(observer)` -- so a seat in no team is silently a
    non-owner of every team family, and a zone type whose owner projection
    differs from its others projection shows that seat the count-only view of
    its own team's zone. `tests/openspiel_ready/partition.py` asks the SAME
    function, so the readiness proofs and the runtime agree on the same wrong
    owner and the soundness matrix stays green: no downstream oracle can see
    this, which is what makes the declaration the only place it can be
    caught.

    The grid is tests/test_teams_partition.py.
    """
    if not game.teams:
        return
    if not game.players.is_well_formed:
        # Shadow Guard. `typecheck` owns the players-count diagnostic ("a game
        # needs at least one player") and
        # is the only place it should be reported. Resolve raises before
        # typecheck ever runs, so building a partition complaint on top of a
        # malformed `players:` would REPLACE the real diagnostic with a
        # derivative one and send the author to fix the wrong clause.
        return
    count = game.players.count
    holding: dict[int, list[int]] = {}
    for team_index, members in enumerate(game.teams):
        for seat in members:
            holding.setdefault(seat, []).append(team_index)

    for seat in sorted(s for s in holding if not 0 <= s < count):
        bag.error(
            f"`teams:` names seat {seat}, which the game does not have: it "
            f"declares {count} player(s) (0..{count - 1}). The seat never "
            f"matches, so its team silently plays a member short",
            game.span,
            code=Code.TEAMS_MUST_PARTITION_SEATS,
        )
    for seat in sorted(s for s, ts in holding.items() if len(ts) > len(set(ts))):
        bag.error(
            f"`teams:` lists seat {seat} twice in the same team — a seat "
            f"belongs to its team once",
            game.span,
            code=Code.TEAMS_MUST_PARTITION_SEATS,
        )
    for seat in sorted(s for s, ts in holding.items() if len(set(ts)) > 1):
        named = ", ".join(str(t) for t in sorted(set(holding[seat])))
        bag.error(
            f"`teams:` puts seat {seat} on more than one team (teams "
            f"{named}) — the engine keeps only the last, so this seat would "
            f"score for a team you did not put it on",
            game.span,
            code=Code.TEAMS_MUST_PARTITION_SEATS,
        )
    for seat in (s for s in range(count) if s not in holding):
        bag.error(
            f"`teams:` leaves seat {seat} on no team, but the game declares "
            f"{count} player(s) — every seat must belong to exactly one team",
            game.span,
            code=Code.TEAMS_MUST_PARTITION_SEATS,
        )


def _resolve_max_length(game: n.Game, bag: DiagnosticBag) -> None:
    if game.max_length is None:
        bag.error(
            f"game '{game.name}' must declare `max_length: <n>` — the most "
            "decisions a run makes: a game that reaches it ends there, scored "
            "by its Stop Result (`at max_length: …`) and a tie when it declares "
            "none, and the OpenSpiel adapter reports it as the game's length "
            "(docs/decisions.md, \"Game length as a declared contract\")",
            game.span,
            code=Code.MISSING_DECLARATION,
        )
    elif game.max_length <= 0:
        bag.error(
            f"game '{game.name}' declares `max_length: {game.max_length}` — "
            "it must be a positive integer",
            game.span,
            code=Code.OUT_OF_RANGE,
        )


def _answered_in_two_spellings(first: object, second: object) -> bool:
    """Two answers to one Kernel Definition Contract, one of them lowered from
    a block spelling."""
    return (
        isinstance(first, n.FunctionDef)
        and isinstance(second, n.FunctionDef)
        and first.name in K.KERNEL_CONTRACT_NAMES
        and (first.spelled_as is not None or second.spelled_as is not None)
    )


def _answer_spelling(answer: n.FunctionDef) -> Said:
    """An answer named as the designer wrote it, in a sentence about two."""
    if answer.spelled_as is None:
        return "function " + cite_named(answer, f"`{answer.name}`")
    return "the `card_points { }` table"


def _check_duplicate_names(game: n.Game, bag: DiagnosticBag) -> None:
    """Every declaration namespace enforces uniqueness (closed-domain
    completeness): a duplicated name would otherwise shadow silently,
    last-wins — accepted-but-ignored at the declaration level. Scopes that
    legitimately shadow ACROSS levels (a phase-local state var over a game
    var) are separate namespaces and stay legal; duplication is rejected
    only WITHIN one declaration list.

    The same sweep also rejects `RESERVED_VALUE_NAMES` (`reserved=True`
    namespaces only): zones, functions, user type names, and state variables
    are all reachable as a bare `NameRef` in general expression position,
    where a reserved word never means "the declaration" (see
    `RESERVED_VALUE_NAMES`'s docstring). Move-type/rule NAMES and phase
    names are exempt — none is ever referenced as a bare NameRef (each lives
    in its own fixed syntactic slot: `constrains:`, `active_rules:`/
    `legal_moves:`, `produces:`, `transition_to:`), so no reserved word can
    hijack one."""

    def check(
        kind: str,
        named: Iterator[object] | tuple[object, ...] | list[object],
        reserved: bool = False,
    ) -> None:
        seen: dict[str, object] = {}
        for decl in named:
            name = getattr(decl, "name")
            if name in seen and kind == "function" and _answered_in_two_spellings(seen[name], decl):
                assert isinstance(decl, n.FunctionDef)
                first = seen[name]
                assert isinstance(first, n.FunctionDef)
                bag.error(
                    f"`{name}` is answered twice — " + _answer_spelling(first)
                    + " and " + _answer_spelling(decl) + f" both answer the "
                    f"kernel's `{K.CONTRACTS[name].spelled}`; keep one",
                    decl.span,
                    code=Code.WRITTEN_TWICE,
                )
            elif name in seen:
                bag.error(
                    f"duplicate {kind} " + cite_named(decl, f"'{name}'")
                    + " — the later declaration would silently shadow the earlier one",
                    getattr(decl, "span", None),
                    code=Code.NAME_TAKEN,
                )
            seen[name] = decl
            if reserved:
                _check_reserved(name, kind, getattr(decl, "span", None), bag)

    check("zone", game.zones, reserved=True)
    # Position names live in dedicated slots (zone index, type arg, parameter
    # type) — never bare expression position — so, like move_type names, they
    # need uniqueness but not the reserved-word sweep.
    check("position", game.positions)
    check("move_type", game.move_types)
    check("function", game.functions, reserved=True)
    check("procedure", game.procedures)
    check("rule", game.rules)
    if game.state is not None:
        check("state variable", game.state.decls, reserved=True)
    phases: list[object] = []
    modes: list[object] = []
    for nd in _walk(game):
        if isinstance(nd, n.Phase):
            phases.append(nd)
        elif isinstance(nd, n.Mode):
            modes.append(nd)
        elif isinstance(nd, n.StateBlock) and nd is not game.state:
            check("state variable", nd.decls, reserved=True)
    check("phase", phases)
    # Modes are collected GAME-WIDE, not per phase, for the same reason phases
    # are: the runtime keys reached transitions by bare mode name in one
    # `RuntimeState.fired_transitions` set, and a phase's entry discards only
    # its own modes' names. A name reached under one phase is therefore still
    # present while another runs, and a nested trick reads every enclosing
    # phase's modes at once. Two phases each declaring a `done` would share
    # that key — one phase's transition would put the other phase straight into
    # its "after" mode, whose rules then apply from the start and whose
    # "before" mode never holds at all. Uniqueness here is what lets the
    # runtime keep using a bare name, so the checker's scope and the runtime's
    # agree.
    check("mode", modes)


def _check_reserved_params(game: n.Game, bag: DiagnosticBag) -> None:
    """Function/move-type/rule parameters are declarations `_check_duplicate_names`
    never reaches (they live on `.params`, not one of its top-level lists) but
    are reachable as a bare `NameRef` inside the body exactly like a state
    variable — a parameter named `empty` is just as unreferenceable via
    `x is empty` as a state variable of the same name would be.

    Function parameters are the ONE exception to `RESERVED_VALUE_NAMES` in
    full: `_CALL_SITE_PRONOUNS` (`actor`/`action`/`winner`) is exactly the
    set a function body is already forbidden from READING (the runtime
    clears them before a hermetic call — `_check_functions`'s "pass the
    value in as a parameter instead"), so naming a parameter after one is
    not a hijack, it is that error message's own prescribed fix — pinned by
    `tests/test_functions.py::test_function_param_does_not_leak_into_pronoun_sites`
    (`function lead(actor : Player) = score[actor]`). `state`/`active_rules`
    stay reserved for function parameters too: those two remain READABLE
    inside a function body, so a same-named parameter would still shadow
    them. `outcome` is reserved for them as well, for the separate reason
    `_KEYWORD_RESERVED` records — it is a clause keyword, not a pronoun a
    hermetic call clears. Move-type/rule bodies are not hermetic — they read
    `actor`/`action`/`winner` directly as live pronouns — so every reserved
    word stays reserved for their parameters."""
    for row in _PARAM_BEARING.values():
        for decl in row.reach(game):
            for p in decl.params:
                _check_reserved(p.name, row.noun, p.span, bag, row.reserved)


def _check_reserved_binders(game: n.Game, bag: DiagnosticBag) -> None:
    """Sweep every binder-introducing node via `_introduced_binders` — the one
    registry of which node kinds bind names — rather than re-enumerating the
    user-choosing ones by hand. This reserved-word check is safe to apply
    uniformly to EVERY name `_introduced_binders` returns, including the FIXED
    ones (`card`/`player`/the quantifier role noun): none of those spellings is
    ever in `RESERVED_VALUE_NAMES` (deliberately — see its docstring), so the
    check is a no-op for them and only ever fires for the genuinely
    user-chosen binders: `for each <role> <binder>:`, `each <role>
    simultaneously:`, and `let <name>[<index>]`."""
    for nd in _walk(game):
        if isinstance(nd, n.DomainQuery):
            # A position query's binder is its noun, a domain name the designer
            # did not choose as a binder; `_check_domain_query` and
            # `_membership_capture` own it and name a reserved word as what it
            # is.
            continue
        for name in _introduced_binders(nd):
            _check_reserved(name, "binder", getattr(nd, "span", None), bag)


def _resolve_component_set(game: n.Game, bag: DiagnosticBag) -> None:
    """An unknown or wrong-flavor component-set name is a diagnostic, never a
    raw registry raise from inside category building (the suit registry
    derives from the runtime deck table, which fails loudly for unknown
    names — correct at playout time, wrong as a designer-facing check); the
    categories fall back to an empty suit namespace so the rest of the
    file's diagnostics still collect. The unknown-name message lists only
    the sets of the CLAUSE'S flavor; a known name of the other flavor gets
    the cross-flavor message instead."""
    from cardlang.runtime.values import COMPONENT_SETS, DECKS, component_set

    cs = component_set(game.deck)
    if cs is None:
        if game.content_flavor == "card":
            bag.unknown(
                f"unknown deck '{game.deck}' — known decks: "
                f"{', '.join(sorted(DECKS))}",
                game.deck,
                DECKS,
                game.span,
                code=Code.UNKNOWN_DECK,
            )
        else:
            piece_sets = sorted(
                name for name, c in COMPONENT_SETS.items() if c.flavor == "piece"
            )
            bag.unknown(
                f"unknown piece set '{game.deck}' — known piece sets: "
                f"{', '.join(piece_sets)}",
                game.deck,
                piece_sets,
                game.span,
                code=Code.UNKNOWN_DECK,
            )
    elif cs.flavor != game.content_flavor:
        if cs.flavor == "piece":
            bag.error(
                f"'{game.deck}' is a piece set — declare it with "
                f"`pieces: {game.deck}`, not `cards:`",
                game.span,
                code=Code.WRONG_SPELLING,
            )
        else:
            bag.error(
                f"'{game.deck}' is a card deck — declare it with "
                f"`cards: {game.deck}`, not `pieces:`",
                game.span,
                code=Code.WRONG_SPELLING,
            )


def _reject_card_content_clauses(game: n.Game, bag: DiagnosticBag) -> None:
    """`ranking:` and `suit ranking:` read a deck's rank order and suits, and
    a card fact's answer a deck's cards; a piece set has none of them, so each
    is rejected NAMING THE KIND in a piece game (rather
    than the silent no-op the `_deck_known` gate on `_expand_ranking`/
    `_resolve_ranking` would otherwise give -- accepted-but-ignored, either the
    enumeration or the convention form). A card game is unaffected."""
    if game.content_flavor != "piece":
        return
    kind = content_kind_clause(game.content_flavor, game.deck)
    if game.ranking or game.ranking_convention is not None:
        bag.error(
            f"{kind} -- `ranking:` orders a deck's cards by rank, which a "
            f"piece set has no notion of; drop the clause",
            game.span,
            code=Code.PIECES_ARE_NOT_CARDS,
        )
    if game.suit_ranking is not None:
        bag.error(
            f"{kind} -- `suit ranking:` orders a deck's suits, which a piece "
            f"set has none of; drop the clause",
            game.suit_ranking.span or game.span,
            code=Code.PIECES_ARE_NOT_CARDS,
        )
    for answer in K.answers(game):
        spelled = answer.spelled_as
        if spelled is not None:
            bag.error(
                f"{kind} -- `card_points` prices a deck's cards by rank, which a "
                f"piece set has no notion of; drop the clause",
                answer.span or game.span,
                code=Code.PIECES_ARE_NOT_CARDS,
            )
        else:
            bag.error(
                f"{kind} — function " + cite_named(answer, f"`{answer.name}`")
                + f" answers the kernel's `{K.CONTRACTS[answer.name].spelled}`, a "
                f"fact of a deck card, which a piece set has no notion of; drop "
                f"the function",
                answer.span or game.span,
                code=Code.PIECES_ARE_NOT_CARDS,
            )


def _resolve_direction(game: n.Game, bag: DiagnosticBag) -> None:
    """`direction:` is grammatically a bare NAME; an unguarded unknown value
    (`direction: anticlockwise`) would silently seat the turn ring clockwise —
    driver.py reads the clause as `clockwise = direction != "counterclockwise"`
    (Surface totality: accepted-with-different-semantics)."""
    from cardlang.runtime.values import GAME_DIRECTIONS

    if game.direction is not None and game.direction not in GAME_DIRECTIONS:
        options = " or ".join(f"`direction: {d}`" for d in GAME_DIRECTIONS)
        bag.unknown(
            f"unknown direction '{game.direction}' — declare {options} "
            f"(omitting the clause means clockwise)",
            game.direction,
            GAME_DIRECTIONS,
            game.span,
            code=Code.UNKNOWN_TURN_DIRECTION,
        )


def _expand_ranking(game: n.Game, bag: DiagnosticBag) -> n.Game:
    """Expand a `ranking:` convention keyword (`aces high`, …) into the
    operative strongest-first tuple: the `RANKING_CONVENTIONS` template
    filtered to the declared deck's ranks. Establishes: post-resolve,
    `game.ranking` IS the strength order for every game;
    `game.ranking_convention` survives only as the record of the source
    form (`ir.emit` prints it). Every consumer downstream of resolve
    (typecheck's Rank enum, `domains.py`'s move-param domain, the driver's
    `rank_index`, the OpenSpiel action space) reads the expanded tuple and
    never learns conventions exist.

    The Owner Guard: a convention is only meaningful for a deck whose ranks all
    have a place in the French template — for any other deck (tarot78's
    atouts, tichu56's specials, coup15's characters) filtering would
    silently produce a partial or empty ranking, an accepted-but-ignored
    declaration. Rejected here, in deck-membership terms, with the
    offending ranks named. An unknown deck already got its diagnostic in
    `_resolve_component_set`; the convention is left unexpanded then (empty
    `ranking`), matching how the rest of resolve degrades without a deck."""
    if game.ranking_convention is None:
        return game
    if not _deck_known(game.deck):
        return game
    from cardlang.runtime.values import RANKS, expand_ranking_convention
    from cardlang.runtime.values import deck_ranks as ordered_deck_ranks

    french = frozenset(RANKS)
    # The ORDERED runtime deck_ranks (first-appearance tuple), not this
    # kernel enums' frozenset wrapper: the offenders appear in the
    # diagnostic, and frozenset iteration is hash-seed-dependent — a
    # rejection golden built on it flakes across CI runs.
    offenders = [r for r in ordered_deck_ranks(game.deck) if r not in french]
    if offenders:
        bag.error(
            f"ranking: {game.ranking_convention} — deck '{game.deck}' has "
            f"ranks outside the standard A..2 set "
            f"({', '.join(offenders)}), so no named convention orders it; "
            f"enumerate the ranking explicitly instead",
            game.span,
            code=Code.RANKING_INCOMPLETE,
        )
        return game
    return replace(
        game,
        ranking=expand_ranking_convention(game.ranking_convention, game.deck),
    )


def _resolve_ranking(game: n.Game, bag: DiagnosticBag) -> None:
    """`ranking:` entries must name real ranks of the declared deck. Unchecked,
    a typo (`11` for `10`) silently widens typecheck's Rank enum domain
    (`value_enum_map` unions `game.ranking` into it) rather than erroring: the
    mistyped literal then type-checks fine and every comparison against it is
    simply False forever, at runtime, with no diagnostic anywhere (Surface
    totality). A repeated entry is rejected too — `driver.py` builds
    `rs.rank_index` from `enumerate(game.ranking)`, so a duplicate would
    silently give one rank two strengths and shift the intended strength of
    every rank after it, last-wins, with no error.

    Coverage is NOT required: `ranking:` may legitimately be a PARTIAL
    permutation of the deck's ranks. Every `docs/games/*.cardlang` ranking
    happens to be a full permutation of its deck, but
    `tests/test_action_space_multiparam.py`'s subset-ranking regression
    (`test_rank_domain_sourced_from_game_ranking_not_deck`) pins a partial
    `ranking:` as a deliberate, supported feature — it narrows the `Rank`
    move-parameter domain to fewer than the deck's ranks. Which cards reach
    a rank-strength read is a fact of zone contents, decidable only at play
    time, so a card whose rank falls outside a partial ranking is the
    RUNTIME's Owner Guard (`runtime/values.py`, `rank_strength`, the one
    lookup every `rank_index` consumer routes through), never this
    check's; the ledgers are tests/test_ranking_guard.py and
    tests/test_trump_slot_class.py."""
    if game.ranking_convention is not None:
        # Convention arm: `_expand_ranking` built the tuple from the deck's
        # own ranks filtered through a registry template — unique and
        # deck-member by construction, so re-validating it here would be
        # re-deriving an established fact. The convention's Owner Guards (French
        # deck, known spelling) live in `_expand_ranking` and the grammar.
        return
    if not game.ranking or not _deck_known(game.deck):
        return
    from cardlang.runtime.values import RANKING_CONVENTIONS

    known = rank_names(game.deck)
    # A clause whose words together nearly spell a convention ("aces hgih",
    # "Aces High", "ace ten") is offered the convention, not a rank.
    phrase = " ".join(game.ranking)
    meant_a_convention = bool(near_misses(phrase, RANKING_CONVENTIONS))
    seen: dict[str, None] = {}
    for rank in game.ranking:
        if rank in seen:
            bag.error(
                f"ranking: repeats rank '{rank}' — each rank may appear at "
                f"most once (a duplicate would silently give it two "
                f"strengths and shift every rank after it down by one)",
                game.span,
                code=Code.WRITTEN_TWICE,
            )
        seen[rank] = None
        if rank not in known:
            # A misspelled convention ("aces sideways", "high aces", a
            # newline inside "aces high") arrives HERE, as enumeration
            # words the deck doesn't know — the grammar falls through
            # rather than erroring, since the words are legal NAMEs. When
            # the bad entry is a word from some convention's spelling,
            # point at the closed set instead of leaving the author to
            # guess rank spellings.
            conv_words = {
                w.lower()
                for key in RANKING_CONVENTIONS
                for w in (key, *key.replace("-", " ").split())
            }
            if rank.lower() in conv_words:
                hint = (
                    f"  (`{rank}` is a word of a ranking convention, which "
                    f"`ranking:` names whole: one of "
                    + ", ".join(sorted(RANKING_CONVENTIONS)) + ")"
                )
            elif rank in suit_names(game.deck):
                hint = (
                    f"  ('{rank}' is a suit: a game ranks its suits with "
                    f"`suit ranking:`, strongest first)"
                )
            else:
                hint = ""
            bag.unknown(
                f"ranking: names unknown rank '{rank}' — not a rank of deck "
                f"'{game.deck}' (known ranks: {', '.join(sorted(known))})"
                + hint,
                phrase if meant_a_convention else rank,
                RANKING_CONVENTIONS if meant_a_convention else known,
                game.span,
                code=Code.UNKNOWN_RANK,
            )


def _resolve_card_points(game: n.Game, bag: DiagnosticBag, refused: set[str]) -> n.Game:
    """`card_points { }` keys must name real ranks of the declared deck, each
    at most once — `_resolve_ranking`'s two Owner Guards, applied to the
    table's key position, read off the lowered answer's `LoweredSpelling`.
    Unchecked, a typo (`ace` for `A`) would price the intended rank 0 (or the
    else value) forever, at runtime, with no diagnostic anywhere — the
    accepted-but-ignored class; and a duplicate key would be a dead arm of the
    lowered chain. Coverage is NOT required: the table may legitimately be
    sparse (Tichu prices five ranks; the rest read 0), exactly as `ranking:`
    may be partial. The else row needs no key check — `else` is the grammar's
    own keyword, excluded from the key terminal.

    A refused table's answer gets a constant body, the table's everything-else
    value, so the fault reports here once and never again as the chain's
    unresolved rank; resolve raises before any later pass reads it. So does a
    table in a game with no deck to rank it against. An accepted table's keys
    are classified as the ranks they are."""
    answer = K.answer(game, "card_points")
    spelled = answer.spelled_as if answer is not None else None
    if answer is None or spelled is None or spelled.form != "card_points_table":
        return game
    assert isinstance(answer.body, n.IfExpr), "a lowered table is a chain"
    if not _deck_known(game.deck) or game.content_flavor != "card":
        # `_reject_card_content_clauses` or `_resolve_component_set` named
        # the fault; the keys have no deck to be ranks of.
        return _with_answer_body(game, answer, answer.body.otherwise)
    known = rank_names(game.deck)
    seen: set[str] = set()
    before = len(bag.items)
    for entry in spelled.entries:
        if entry.rank in seen:
            bag.error(
                f"card_points repeats rank '{entry.rank}' — each rank may "
                f"appear at most once (a duplicate would silently keep only "
                f"the last value)",
                entry.span or game.span,
                code=Code.WRITTEN_TWICE,
            )
        seen.add(entry.rank)
        if entry.rank not in known:
            bag.unknown(
                f"card_points names unknown rank '{entry.rank}' — not a rank "
                f"of deck '{game.deck}' (known ranks: {', '.join(sorted(known))})",
                entry.rank,
                known,
                entry.span or game.span,
                code=Code.UNKNOWN_RANK,
            )
    if len(bag.items) > before:
        refused.add("card_points")
        return _with_answer_body(game, answer, answer.body.otherwise)
    # Every key is a rank of the deck, decided here: each arm's key is
    # classified so, whatever state, zone or local the game spells the same,
    # since the table's key position names ranks only.
    def ranked(cond: n.Expr) -> n.Expr:
        assert isinstance(cond, n.BinOp), "a lowered arm compares the card's rank"
        key = cond.right
        if isinstance(key, n.NameRef):
            return replace(cond, right=replace(key, ref_kind="enum_value"))
        return cond

    chain = answer.body
    return _with_answer_body(
        game,
        answer,
        replace(
            chain,
            cond=ranked(chain.cond),
            elifs=tuple((ranked(c), v) for c, v in chain.elifs),
        ),
    )


def _with_answer_body(game: n.Game, answer: n.FunctionDef, body: n.Expr) -> n.Game:
    """`game` with `answer`'s body replaced."""
    rebuilt = replace(answer, body=body)
    return replace(
        game, functions=tuple(rebuilt if f is answer else f for f in game.functions)
    )


def _resolve_suit_ranking(game: n.Game, bag: DiagnosticBag, refused: set[str]) -> None:
    """`suit ranking:` lists suits of the declared deck, each once, strongest
    first: every suit the deck declares (`Deck.suits`), and any of its special
    suits (`deck_suits` beyond the declared ones) it chooses to rank. A special
    suit it leaves out is refused when a card of that suit reaches
    `suit_value` (`runtime/values.py`, `suit_strength`), which is a fact of
    zone contents.

    A name the deck does not hold is refused naming what the designer most
    likely meant: a rank or a rank convention belongs to `ranking:`.

    A clause this guard refuses is handed to `_check_unread_clauses` in
    `refused`, which then says nothing of whether anything reads it.

    A piece game's clause is `_reject_card_content_clauses`'s; an unknown deck
    is `_resolve_component_set`'s."""
    ranking = game.suit_ranking
    if ranking is None or game.content_flavor != "card" or not _deck_known(game.deck):
        return
    from cardlang.runtime.values import DECKS, RANKING_CONVENTIONS, deck_ranks, deck_suits

    span = ranking.span or game.span
    suits = deck_suits(game.deck)
    before = len(bag.items)
    words = " ".join(ranking.suits)
    if words in RANKING_CONVENTIONS:
        bag.error(
            f"suit ranking: {words} is a rank convention — write it as "
            f"`ranking: {words}`; `suit ranking:` lists "
            f"{_declared_suits_phrase(game.deck)} strongest first",
            span,
            code=Code.WRONG_SPELLING,
        )
        refused.add("suit_ranking")
        return
    ranks = set(deck_ranks(game.deck))
    seen: set[str] = set()
    for name in ranking.suits:
        if name in seen:
            bag.error(
                f"suit ranking: repeats suit '{name}' — name each suit once, "
                f"strongest first",
                span,
                code=Code.WRITTEN_TWICE,
            )
        seen.add(name)
        if name in suits:
            continue
        if name in ranks:
            bag.error(
                f"suit ranking: '{name}' is a rank of deck '{game.deck}', not a "
                f"suit — a rank order is declared with `ranking:`; "
                f"`suit ranking:` lists {_declared_suits_phrase(game.deck)} "
                f"strongest first",
                span,
                code=Code.WRONG_SPELLING,
            )
        else:
            bag.unknown(
                f"suit ranking: '{name}' is not a suit of deck '{game.deck}' — "
                f"list {_declared_suits_phrase(game.deck)} strongest first",
                name,
                DECKS[game.deck].suits,
                span,
                code=Code.UNKNOWN_SUIT,
            )
    for declared in DECKS[game.deck].suits:
        if declared not in seen:
            bag.error(
                f"suit ranking: leaves out {declared} — list "
                f"{_declared_suits_phrase(game.deck)} strongest first",
                span,
                code=Code.RANKING_INCOMPLETE,
            )
    if len(bag.items) > before:
        refused.add("suit_ranking")



def _trick_order_rounds(game: n.Game) -> list[n.TrickRound]:
    """Every trick round the game's TEXT holds. The refusal half of the
    partition validates a round WHERE IT IS WRITTEN, so a round in a container
    nothing invokes is refused too: over-reporting in the safe direction,
    which can never miss."""
    return [nd for nd in _walk(game) if isinstance(nd, n.TrickRound)]


def _check_trick_order_partition(game: n.Game, bag: DiagnosticBag, refused: set[str]) -> None:
    """The presence partition, both directions: a game either declares a
    [[trick-order]] — it answers `is_trump` — and names the winner and calls
    that read it, or declares none and names the round-configured ones. Never
    a mixture.

    The Owner Guard for a class that would otherwise be silent in both
    directions. WITH a Trick Order, the round-configured trump (a round's
    `trump` clause) and the winners that read it are not merely
    redundant — they describe a DIFFERENT order from the one the Trick Order
    declares, and the engine would quietly run one of the two. WITHOUT one,
    every gated name reads a table that was never materialized, which is a
    crash at play time rather than a diagnostic at check time; and an answer
    to `follow_class` or `card_strength` is a row of an order the game never
    declares, which nothing would read. A round whose winner reads a trump
    and that states none is refused, wherever it is written: a game clause
    that would state it does not exist, so a library's round is refused in
    the library's own text.

    Whether a Trick Order is read at all is `_check_unread_clauses`' question.
    """
    if game.content_flavor != "card":
        return  # `_reject_card_content_clauses` already named the kind
    if not K.has_trick_order(game):
        # --- without a Trick Order: no gated name may appear ----------------
        # A round spliced from a library whose winner reads the Trick Order is
        # `_check_library_clause_gates`'s, which this loop shadows.
        spliced = n.library_origins(game)
        for rnd in _trick_order_rounds(game):
            refusals = _winner_refusals(rnd, game)
            if "reads an absent Trick Order" in refusals:
                others = ", ".join(sorted(TRICK_WINNER_NAMES - TRICK_ORDER_GATED_WINNERS))
                bag.error(
                    f"round winner {rnd.winner_fn} reads the game's Trick "
                    f"Order, but this game declares none — {_ANSWER_IS_TRUMP}; "
                    f"or name {others}",
                    rnd.span,
                    code=Code.MISSING_DECLARATION,
                )
            elif "reads an unstated trump" in refusals:
                # The round-configured twin of a Trick Order's required
                # `is_trump`: a winner reading a trump the round never states
                # would play no-trump.
                # A library names no suit and answers no contract, so its fix
                # is a suit the game supplies, or the game's Trick Order.
                fix = (
                    f"require the suit from the game (`requires {{ trump_suit : "
                    f"Suit }}`) and write it on the round (`... winner "
                    f"{rnd.winner_fn} trump trump_suit`), or name "
                    f"highest_by_trick_order, whose trump is the game's `is_trump`"
                    if id(rnd) in spliced
                    else f"write it on the round (`... winner {rnd.winner_fn} "
                    f"trump <suit>`), or answer `is_trump` (`function "
                    f"is_trump(card : Card) = …`) and name highest_by_trick_order"
                )
                bag.error(
                    f"round winner {rnd.winner_fn} reads a trump, but none is "
                    f"stated — {fix}; a no-trump trick names highest_of_led_suit",
                    rnd.span,
                    code=Code.MISSING_DECLARATION,
                )
        # A call spliced from a library is `_check_library_clause_gates`'s,
        # which this loop and the excluded-call loop below shadow.
        for call in _gated_calls(game):
            bag.error(
                f"`{call.func}(...)` reads the game's Trick Order, but this game "
                f"declares none — {_ANSWER_IS_TRUMP}",
                call.span or game.span,
                code=Code.MISSING_DECLARATION,
            )
        for name in K.TRICK_ORDER_CONTRACTS[1:]:
            orphan = K.answer(game, name)
            if orphan is None:
                continue
            row = K.CONTRACTS[name]
            bag.error(
                f"function " + cite_named(orphan, f"`{name}`") + f" answers the "
                f"kernel's `{row.spelled}`, a row of the Trick Order, but the "
                f"game declares no Trick Order — {_ANSWER_IS_TRUMP}; or rename it",
                orphan.span or game.span,
                code=Code.MISSING_DECLARATION,
            )
        return

    # --- with a Trick Order: the round-configured names are refused ----------
    named = _trick_order_named(game)
    for rnd in _trick_order_rounds(game):
        if _round_trump_clauses(rnd, game):
            bag.error(
                "round `trump` clause beside " + named + " — "
                + _cite_in(game, "function", "is_trump", "`is_trump`")
                + " is the trump; drop the clause",
                rnd.span,
                code=Code.CONFLICTING_CLAUSES,
            )
        refusals = _winner_refusals(rnd, game)
        if "replaced by the Trick Order" in refusals:
            gated = ", ".join(sorted(TRICK_ORDER_GATED_WINNERS))
            bag.error(
                f"round winner {rnd.winner_fn} beside " + named + " — it declares "
                f"the game's Trick Order, and "
                f"{gated} is the winner that reads it; name that, or "
                f"{_drop_trick_order(game)}",
                rnd.span,
                code=Code.CONFLICTING_CLAUSES,
            )
        if "early beside the Trick Order" in refusals:
            bag.error(
                f"`early` clause on winner {rnd.winner_fn} — `early` "
                f"predicates read the literal led suit, and a Trick Order's "
                f"follow class may differ; no game has needed both — drop the "
                f"clause",
                rnd.span,
                code=Code.CONFLICTING_CLAUSES,
            )
    for nd in _walk(game):
        if not isinstance(nd, n.ClimbRound):
            continue
        for query_slot, fname in _climb_queries(nd, game):
            bag.error(
                f"climb round `{query_slot} {fname}` beside " + named + " — the "
                f"climbing round's queries carry their own order; a game with "
                f"a Trick Order cannot also name {fname} (the climb family "
                f"reading the Trick Order is issue #251)",
                nd.span,
                code=Code.CONFLICTING_CLAUSES,
            )
    for nd in _walk(game):
        if isinstance(nd, n.Call) and nd.func in TRICK_ORDER_EXCLUDED_FUNCS:
            arg = "pile"
            if nd.args and isinstance(nd.args[0], n.NameRef):
                arg = nd.args[0].name
            bag.error(
                f"`{nd.func}(...)` beside " + named + " — the Trick Order's "
                f"functions are the trick order; call "
                f"`{min(TRICK_ORDER_GATED_WINNERS)}({arg})`",
                nd.span or game.span,
                code=Code.CONFLICTING_CLAUSES,
            )


def _check_piece_rounds(game: n.Game, bag: DiagnosticBag) -> None:
    """A trick round's winner or a climbing query in a piece game: each reads
    a deck card's suit or rank, which a piece set has none of
    (`_CARD_CONTENT_GATE`). Refused here, before the type layer would ask the
    game for a `ranking:` a piece game cannot declare. Spliced from a library,
    `_check_library_clause_gates` has refused it first."""
    for nd in _walk(game):
        if isinstance(nd, n.TrickRound):
            if "reads a deck card" not in _winner_refusals(nd, game):
                continue
        elif not isinstance(nd, n.ClimbRound) or not _refuses(_CARD_CONTENT_GATE, nd, game):
            continue
        for phrase in card_content_forms(nd):
            bag.error(
                f"{content_kind_clause(game.content_flavor, game.deck)} -- "
                f"{phrase} reads a deck card's suit or rank, which a piece set "
                f"has none of",
                nd.span,
                code=Code.PIECES_ARE_NOT_CARDS,
            )


def _gated_calls(game: n.Game) -> list[n.Call]:
    """The calls reading a Trick Order in the game's own text. A library's
    call is `_check_library_clause_gates`', or, for a name its `requires`
    contracts for, that row's (`_check_definition_requirement`)."""
    spliced = {
        id(nd)
        for f in game.functions
        if f.origin is not None
        for nd in _walk(f.body)
    }
    return [
        nd
        for nd in _walk(game)
        if isinstance(nd, n.Call) and nd.func in _TRICK_ORDER_READERS and id(nd) not in spliced
    ]
