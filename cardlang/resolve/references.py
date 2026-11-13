"""Resolve step: references on the classified tree.

Contract (decisions.md "Closed-domain completeness", write-time triage)
-----------------------------------------------------------------------
Assumes:      the classified tree, read-only, and the categories it was
              classified against.
Establishes:  every call, card literal and rotate/winner target names what
              its namespace or registry holds (``_validate_refs``).
              A move parameter's
              domain, a function parameter's type and an outcome payload's
              type name the direction domain only where the board minted it
              (``_minted_directions``, the one gate each of them reads), so a
              later pass may look any such name up in the position or the
              direction source and find it. A ``state`` variable's declared
              type names a value type or one of the game's named-member
              position domains (``_declared_type_universe``, the one set the
              ``StateDecl`` arm reads and a function parameter's set
              extends); an integer position domain, ``dir`` and ``cell`` in
              a game with no ``board:`` are refused there
              (``_state_type_refusal``), each naming a declaration that checks
              in that game. A board verb stands only on a
              board whose family declares what the verb reads
              (``BOARD_VERB_NEEDS``; ``_check_board_call`` for the game's
              call, the ``_BOARD_NEED_GATES`` rows on the ``uses`` line for a
              library's), so the runtime may read the board entry's edges,
              lines or frame behind any board verb it meets; held by Derived
              and Pinned, one table pinned total against
              ``BOARD_ONLY_CALL_FUNCS``.
Now illegal:  a round
              ``trump`` clause on a winner whose body reads no
              trump (the winner-slot arm of ``_validate_refs``; the
              partition is ``TRUMP_READING_WINNERS``). The round clause's TYPE (``Suit?``)
              is typecheck's (``_check_round_trump``); its presence against
              its winner is settled here, with the winner namespace.
              A call, in a game that writes no ``primitives { }`` block,
              to any Primitive (``PRIMITIVE_CALL_FUNCS``, the declared-only
              arm of ``_validate_refs``): the name is in the corpus-wide
              namespace, so the unknown-name arm cannot speak for it, and a
              declaration is its only route to Python.
              ``typecheck``'s ``Call`` arm is the Shadow Guard behind this —
              no table states such a call's signature — with
              ``runtime/evaluate.py``'s ``native_call`` refusal behind that.
              A Stake row no seat
              can read on a ``Card``-parameterized move type,
              whose action id is its card's (``_check_move_params``). Every
              row reaching a Seat Policy is therefore on a move type whose
              action ids name it.
"""

from __future__ import annotations

from dataclasses import replace
from cardlang.diagnostic_codes import Code
from cardlang.ast import nodes as n
from cardlang.board_domains import BOARD_DOMAIN, DIRECTION_DOMAIN
from cardlang.builtins.functions import (
    BOARD_ONLY_CALL_FUNCS,
    DECK_ONLY_CALL_FUNCS,
    PRIMITIVE_CALL_FUNCS,
    TRICK_ORDER_GATED_WINNERS,
    TRUMP_READING_WINNERS,
)
from cardlang import kernel_contracts as K
from cardlang.primitives_block import Regime, call_namespace, regime
from cardlang.attribution import cite_library, cite_named, cite_origin
from cardlang.diagnostics import DiagnosticBag, LibraryCitation, Said, Sentence, Span, listed
from cardlang.domains import (
    CARD_AXIS_ROLES,
    CARD_PARAM_DOMAINS,
    PARAM_DOMAIN_ORDER,
    ZONE_INDEX_ROLES,
    Role,
    role_names,
    role_of,
)
from cardlang.domains import ITERABLE_ROLES as _ITERATION_ROLES
from cardlang.domains import PARAM_DOMAINS as _FIXED_DOMAINS
from cardlang.runtime.errors import OwnerGuardError
from cardlang.runtime.values import content_kind_clause
from cardlang.stdlib.boards import board_entry
from cardlang.stdlib.moves import CLIMB_DECISION_MOVE_TYPE, LIBRARY_MOVE_TYPES
from cardlang.stdlib.zones import LIBRARY_ZONE_TYPES, identity_to_all
from cardlang.resolve.walk import _walk
from cardlang.resolve.slots import _NAME_SLOTS, _ROUND_QUERY_REGISTRIES, _slot_root
from cardlang.resolve.declared import (
    CARD_PARAMETER_FAMILY,
    _combination_outside_a_parameter,
    _declared_suits_phrase,
    _declared_type_universe,
    _direction_refusal,
    _family_shape,
    _minted_directions,
    _simultaneous_role_refused,
    _tell_board_refusal,
)
from cardlang.resolve.clause_gates import (
    _BOARD_NEED_GATES,
    _CARD_CONTENT_GATE,
    _CARD_POINTS_CALLS,
    _CELL_RANGE_GATE,
    _RANK_PARAMETER_GATE,
    _SEAT_GATES,
    _SUIT_RANKING_CALLS,
    _TEAM_CALL_FUNCS,
    _TEAM_RANGE_GATE,
    _TEAM_STATE_GATE,
    _board_remedy,
    _card_points_fix,
    _cell_ranges,
)
from cardlang.resolve.round_winners import _refuses, _winner_refusals
from cardlang.resolve.ranking_slots import ranking_slot
from cardlang.resolve.classifier import (
    _Categories,
    _each_destination_refuses,
    _slot_name_outside_slot,
    _slot_refuses,
)

# Domain nouns that mislead as an indexed-`let` binder. `let x[i] = …` builds a
# per-PLAYER map — the index is a binder bound to each player in turn, whatever
# it is named — so a binder named after a NON-player domain reads as a
# per-suit/per-team store the form does not build (`let x[suit] = 1` keyed by
# players, then `x[hearts]` key-errors; a team read silently lands on a seat).
# Derived from the iteration-role column, minus the domain the form actually
# ranges over.
_MISLEADING_LET_INDEXES = role_names(_ITERATION_ROLES - {Role.PLAYER})


def _undeclared_primitive_hint(game: n.Game, func: str) -> str:
    """The half-sentence an unknown call earns when the name IS a Primitive
    some other game declares. Without it a declared game's author reads
    "unknown function" about a name they can see in the registry, and the
    regime — the thing that actually refused it — stays invisible."""
    if regime(game) is not Regime.DECLARED or func not in PRIMITIVE_CALL_FUNCS:
        return ""
    return (
        f" — `{func}` is a Primitive another game declares, and this game's "
        f"`primitives {{ }}` block does not; declare it here to call it"
    )


def _state_type_refusal(game: n.Game, type_name: str) -> str | None:
    """How a `state` variable's refusal of a type outside
    `_declared_type_universe` ends, for the type names a parameter takes, the
    direction domain wherever it is spelled, and the board's `cell` in a game
    with no `board:`; None for every other name, which is unknown. Each ending
    names a declaration that checks in the game it is told in: whether `dir`
    is minted is `_minted_directions`' to say, and what a game without it
    lacks `_direction_refusal`'s."""
    if any(p.name == type_name and p.members_named is None for p in game.positions):
        return (
            "a position domain of numbers: a move or function parameter takes "
            "one, and a state variable remembers it as an `Integer`"
        )
    if type_name in _minted_directions(game):
        return (
            "the board's direction domain: a move or function parameter takes "
            "a direction (`along : dir`), and a state variable cannot hold one"
        )
    if (unminted := _direction_refusal(game, type_name)) is not None:
        instead = (
            "if it is the turn order's direction, a state variable holds it as "
            "a `SeatDirection`"
            if game.board is None
            else "a state variable remembers a square as a `cell?`"
        )
        return f"{unminted} -- {instead}"
    if type_name == BOARD_DOMAIN and game.board is None:
        fix = (
            "a board game declares `pieces:` in place of `cards:`, and a `board:`"
            if game.content_flavor == "card"
            else "declare the `board:` its pieces stand on"
        )
        return f"the squares a `board:` mints, but the game declares no `board:` -- {fix}"
    return None


# What a write target may be. `:=`, `+=`, `-=` and `rotate` all write persistent
# state (`runtime/execute.py`'s `_assign` -> `rs.set`, `_rotate`), and persistent state
# is the only thing they can write — so a write target must classify as a state
# variable, full stop.
#
# This is one rule and not three Owner Guards because the target is a `NameRef`: it goes
# through `_classify` like every read, so "what is this name?" is already answered by
# the time we get here. Were it a bare `str` that no name check ever saw, the three
# ways it can go wrong would need three separate hand-written checks — and the easiest
# to omit is the plain typo, so `totaly_score := 1` would reach the runtime, which
# requires every name it writes to have been declared.
#
# The subtle one is a binder shadowing a state variable. A READ resolves binders BEFORE
# state variables; a write goes to state regardless. So `let turn = …` followed by
# `turn := 1` would write the state variable while every `turn` around it meant the
# binder — one name, two things, silently. Classifying the target makes that impossible
# rather than merely detected: the target resolves to the binder, and a binder is not
# a write target.
_WRITE_TARGET_KINDS: dict[str, str] = {
    "local": "a binder (a `let`, a loop binder, or a parameter)",
    "zone": "a zone",
    "enum_value": "a value of the deck",
    "null": "the literal `none`",
    "bool": "a boolean literal",
    "pronoun": "a pronoun",
    "function": "a function",
}


def _named_ref(game: n.Game, ref: n.NameRef) -> Said:
    """`ref` quoted, cited at the provided state it reads where it reads
    some."""
    words = f"'{ref.name}'"
    if ref.ref_kind != "state_var" or game.state is None:
        return words
    provided = next(
        (d for d in game.state.decls if d.name == ref.name and d.origin is not None), None
    )
    return words if provided is None else cite_named(provided, words)


def _bad_write_target(game: n.Game, node: n.AssignStmt | n.RotateStmt) -> Said | None:
    """Why this write target is illegal, or None if it is a state variable."""
    verb = "assign to" if isinstance(node, n.AssignStmt) else "rotate"
    kind = node.target.ref_kind
    if kind is None:
        return None  # unresolved: `_classify` has already reported it, by name
    if not _slot_refuses(_NAME_SLOTS[(type(node), "target")], kind):
        return None
    what = _WRITE_TARGET_KINDS.get(kind, f"a {kind}")
    return (
        f"cannot {verb} " + _named_ref(game, node.target) + f": it is {what}, and only a declared state "
        f"variable can be written. A binder is a bound value, not a variable — and if "
        f"a state variable of the same name exists, the two would not agree anyway "
        f"(a read here means the binder; a write always goes to state)"
    )


def _bad_zone_endpoint(
    game: n.Game, node: n.Transfer | n.EpistemicOp, slot: str, what: str
) -> tuple[Said, n.NameRef] | None:
    """Why this zone-position expression (a movement's `from <here>` /
    `to <here>`, an epistemic op's target) is illegal, and the root name it
    refuses, or None. The same move
    as `_bad_write_target`, one grammar position over: the position is
    name-shaped (the grammar rejects literals there), so its ROOT name has a
    classification, and most classifications cannot possibly be a zone.
    `deal 1 cards from turn to each hand` and `shuffle turn` (with
    `turn : Integer`) would otherwise both check clean and reach the executor,
    which requires an actual Zone in this position and refuses anything else at
    play time — a statically nameable error deferred to the wrong time.

    A `local` root stays accepted HERE: a binder may legitimately hold a zone
    value (`let h = hand[0]`), and which one it holds is a TYPE question —
    typecheck's `_check_transfer`/EpistemicOp arms decide it from the binder's
    inferred type (decisions.md, "`let` bindings scope forward and carry
    their type"). The executor's typed error remains the Owner Guard for the
    deliberately-loose initializers (`outcome`, unregistered action fields)."""
    root = _slot_root(getattr(node, slot))
    if root is None:
        return None  # not name-rooted: nothing to classify here
    kind = root.ref_kind
    if kind is None:
        return None  # unresolved, already reported by the classifier
    if not _slot_refuses(_NAME_SLOTS[(type(node), slot)], kind):
        return None
    what_it_is = _WRITE_TARGET_KINDS.get(kind, f"a {kind}")
    if kind == "state_var":
        what_it_is = "a state variable"
    return f"cannot {what} " + _named_ref(game, root) + f": it is {what_it_is}, not a zone", root


# The closed set of statically enumerable move-parameter domains (decisions.md
# "Surface totality") is `cardlang.domains.PARAM_DOMAINS` — the union of the
# registry rows' `param_domains`, imported above as `_FIXED_DOMAINS`. It is
# matched by exact string, not by stripping a trailing `?`: only `Suit?` is
# listed by a row, so only it has a real nullable enumeration. `Rank?`/`Player?`
# parse (payload types are generically optional-able) but no row admits them, so
# they fall through to the "unsupported domain" branch below rather than being
# silently accepted and then ignored at runtime. `Card` is deliberately not a
# registry row at all (state-dependent — the live hand), so it is absent from
# this set and checked separately below.
#
# The one list of legal spellings the diagnostic names, derived from the same
# rows in enumeration order so a new domain row cannot leave the message stale.
_LEGAL_PARAM_DOMAINS = f"{', '.join(PARAM_DOMAIN_ORDER)}, or Card"


def _check_move_params(
    mt: n.MoveTypeDef,
    bag: DiagnosticBag,
    span: Span | None,
    game: n.Game,
    positions: frozenset[str],
    directions: frozenset[str],
) -> None:
    """Totality gate for a parameterized move offered/enumerated in a decision
    (an `offer` statement). Fixed-from-type
    domains (`Suit`/`Suit?`/`Rank`/`Player`) and a single `Card` parameter are
    allowed; a `Card` parameter combined with any other parameter, a
    bounded-`Integer` parameter (deferred), two parameters sharing a name, and
    a `Rank` parameter in a game with no declared `ranking:`
    (`_RANK_PARAMETER_GATE`) are rejected with a message.

    The ranking gate covers only `Rank`: `Player`'s domain is the seats, always
    non-empty for a real game, and `Suit`'s is `deck_suits`, always non-empty
    for a real deck — neither can be empty the way `game.ranking` (optional,
    `()` by default) can. Without this gate, a Rank-parameterized move in a
    no-`ranking:` game would pass resolve clean and only fail at runtime,
    mid-decision, once `param_domain` enumerates the empty `rank_index` and
    the move contributes zero candidates — a crash where a compile-time
    diagnostic belongs (CLAUDE.md "Surface totality")."""
    types = [p.type_name for p in mt.params]
    for p in mt.params:
        refused = _combination_outside_a_parameter(p.type_name, "a move type's parameter")
        if refused is not None:
            bag.error(refused, span, code=Code.TYPE_NOT_ALLOWED_HERE)
            return
    # A piece game has no suit/rank/card domain to enumerate, so a move
    # parameterized by one has no candidate space. Checked before the
    # ranking / unsupported-domain arms so the diagnostic names the KIND
    # (a Rank param in a piece game is a flavor error, not a missing-ranking
    # one); Player and position domains stay legal. Spliced from a library,
    # `_check_library_clause_gates` has refused both first, by the same gates.
    if _refuses(_CARD_CONTENT_GATE, mt, game):
        offending = [t for t in types if t in CARD_PARAM_DOMAINS]
        if offending:
            bag.error(
                f"{content_kind_clause(game.content_flavor, game.deck)} -- "
                f"move " + cite_named(mt, f"'{mt.name}'") + f" has a "
                f"{offending[0]} parameter, whose domain is the deck's "
                f"suits/ranks; a piece set enumerates neither",
                span,
                code=Code.PIECES_ARE_NOT_CARDS,
            )
            return
    if "Card" in types and mt.stake is not None:
        bag.error(
            f"`{mt.stake}` on move type " + cite_named(mt, f"`{mt.name}`") + f": a card play is offered as "
            f"its card, and its action id is the card's, naming no move type, "
            f"so no seat can read the row — delete it (issue #770)",
            span,
            code=Code.HAS_NO_EFFECT,
        )
    if "Card" in types and len(types) > 1:
        bag.error(
            f"move " + cite_named(mt, f"'{mt.name}'") + f" combines a Card parameter with another parameter; "
            f"Card's domain is the live hand and its actions are the card block, "
            f"so a Card parameter cannot be combined with another parameter "
            f"(fold into one parameter)",
            span,
            code=Code.CARD_PLAY_PARAMETERS,
        )
    names = [p.name for p in mt.params]
    dup_names = sorted({name for name in names if names.count(name) > 1})
    if dup_names:
        bag.error(
            f"move " + cite_named(mt, f"'{mt.name}'") + f" declares more than one parameter named "
            f"{', '.join(dup_names)}; `bind_params` binds parameters by name, "
            f"so a repeated name silently shadows the earlier parameter instead "
            f"of binding both (rename one)",
            span,
            code=Code.NAME_TAKEN,
        )
    for t in types:
        if t.rstrip("?") == "Integer":
            bag.error(
                f"move " + cite_named(mt, f"'{mt.name}'") + f" has parameter domain '{t}'; bounded-Integer "
                f"parameter domains are deferred (see "
                f"open-questions/move-parameter-domains.md)",
                span,
                code=Code.NOT_YET_SUPPORTED,
            )
        elif (
            t not in _FIXED_DOMAINS
            and t != "Card"
            and t not in positions
            and t not in directions
        ):
            expected = _LEGAL_PARAM_DOMAINS
            if positions:
                expected += ", or a declared position domain (" + ", ".join(sorted(positions)) + ")"
            if directions:
                expected += (
                    ", or a movement direction domain ("
                    + ", ".join(sorted(directions))
                    + ")"
                )
            bag.unknown(
                f"move " + cite_named(mt, f"'{mt.name}'") + f" has unsupported parameter domain '{t}' "
                f"(expected {expected})" + _no_board_for_directions(game, t),
                t,
                (*_FIXED_DOMAINS, "Card", *positions, *directions),
                span,
                code=Code.UNKNOWN_TYPE,
            )
        # Exact string, matching `_FIXED_DOMAINS`'s own convention (never by
        # stripping a trailing `?`): `Rank?` is not in `_FIXED_DOMAINS`, so it
        # is already rejected by the elif above and never reaches this branch
        # — only bare `Rank` needs the non-empty-`ranking:` gate.
        elif t == "Rank" and _refuses(_RANK_PARAMETER_GATE, mt, game):
            bag.error(
                f"move " + cite_named(mt, f"'{mt.name}'") + f" has a Rank parameter, but the game declares "
                f"no ranking: — Rank enumerates the declared ranking, so it "
                f"needs a non-empty one",
                span,
                code=Code.MISSING_DECLARATION,
            )


def _check_card_offering(
    names: tuple[str, ...],
    move_type_defs: dict[str, n.MoveTypeDef],
    game: n.Game,
    bag: DiagnosticBag,
    span: Span | None,
    origin: n.LibraryOrigin | None,
) -> None:
    """The Card domain's constraints on an offering of move types (an
    `offer`, which folds a Card-parameterized move through the
    `param_domain`/`card_to_action` machinery, decisions.md "Declared
    parameter domains"): at most one Card-parameterized move (its OpenSpiel
    action id is the card itself, so a second would be indistinguishable by
    id — the offer would otherwise collapse two card plays onto one action,
    cardlang/openspiel/encoding.py), and the actor's
    `hand[player]` zone must exist (`param_domain`'s Card branch enumerates
    it; without one the decision crashes mid-playout). Unknown move names are
    skipped — the caller's own loop already reports those.

    `origin` is the offer's when a library wrote it. Such an offer's refusal
    carries the sentence the game's author reads, for `attribution` to tell:
    a second card play that is the game's own move type (its answer to a
    `Move` row), or a `hand` the game declares. A game's offer of a library's
    move type whose contract fixes `hand` is refused at the move type: no
    game meeting the contract can offer it."""
    family = CARD_PARAMETER_FAMILY
    card_param_moves = [
        name
        for name in names
        if name in move_type_defs
        and len(move_type_defs[name].params) == 1
        and move_type_defs[name].params[0].type_name == "Card"
    ]
    if len(card_param_moves) > 1:
        answers = [m for m in card_param_moves if move_type_defs[m].origin is None]

        def quoted(m: str) -> LibraryCitation:
            return cite_named(move_type_defs[m], f"`{m}`")

        for_game: Said | None = None
        if origin is not None and answers:
            listed = Sentence.join(" and ", map(quoted, answers))
            offered = Sentence.join(", ", map(quoted, card_param_moves))
            takes = "takes" if len(answers) == 1 else "take"
            which = "it" if len(answers) == 1 else "one of them"
            for_game = (
                cite_origin(origin, span) + " offers " + offered
                + " in one offer, and this game's " + listed + f" {takes} a Card "
                f"parameter beside the other; a card play's action is the card "
                f"itself, so the two would be indistinguishable — answer "
                f"{which} with a move type that takes no Card parameter"
            )
        moves = Sentence.join(
            ", ", (cite_named(move_type_defs[m], m) for m in card_param_moves)
        )
        bag.error(
            "offering declares more than one Card-parameterized move ("
            + moves + "); a card play's action is the "
            "card itself, so a second Card-parameterized move would be "
            "indistinguishable — fold them into one move type",
            span,
            for_game=for_game,
            code=Code.CARD_PLAY_PARAMETERS,
        )
    hand = next((z for z in game.zones if z.name == family), None)
    if not card_param_moves or (
        # Intrinsic: a Card parameter enumerates the ACTOR's hand, which is
        # player-keyed by definition.
        hand is not None and hand.index is not None and role_of(hand.index) is Role.PLAYER
    ):
        return
    move = move_type_defs[card_param_moves[0]]
    param = move.params[0]
    offering_move = "offering move " + cite_named(move, f"'{move.name}'")
    if origin is not None:
        whose = "this game's " if move.origin is None else ""
        shape = "" if hand is None else f" (its `{family}` is {_family_shape(hand.index)})"
        fix: Said = (
            "answer " + cite_named(move, f"`{move.name}`") + " with a move type that "
            "takes no Card parameter, since "
            + cite_library(origin.library, None) + f"'s contract names `{family}` so"
            if family in origin.contracted_zones
            else f"declare `{family}` a zone kept per player, like "
            f"`{family}[player] : Hand<player>`"
        )
        bag.error(
            offering_move + " takes a Card parameter, "
            f"which enumerates the actor's `{family}[player]` zone — this game "
            f"declares none",
            span,
            for_game=(
                cite_origin(origin, span) + f" offers {whose}move type "
                + cite_named(move, f"`{move.name}`")
                + f", whose `{param.name} : Card` takes a card from "
                f"the acting seat's `{family}[player]`, but this game declares no "
                f"`{family}[player]`{shape} — " + fix
            ),
            code=Code.MISSING_DECLARATION,
        )
        return
    # The game's own offer of a library move type: a contract fixing `hand`
    # refuses it in every game meeting the contract, which is the library's
    # fact, about its move type.
    if move.origin is not None and family in move.origin.contracted_zones:
        shape = "none" if hand is None else _family_shape(hand.index)
        bag.error(
            "move type " + cite_named(move, f"`{move.name}`")
            + f"'s `{param.name} : Card` takes a card from "
            f"the acting seat's `{family}[player]`, but "
            + cite_library(move.origin.library, None)
            + f"'s contract names `{family}` as {shape}, so no game meeting it can offer "
            + cite_named(move, f"`{move.name}`") + f" — contract `{family}` per player, like "
            f"`{family}[player] : Hand<player>`",
            param.span or move.span,
            code=Code.WRONG_ZONE_SHAPE,
        )
        return
    bag.error(
        offering_move + " takes a Card parameter, "
        f"which enumerates the actor's `{family}[player]` zone — this game "
        f"declares none",
        span,
        code=Code.MISSING_DECLARATION,
    )


def _check_offering_moves(
    names: tuple[str, ...],
    defined_move_types: set[str],
    bag: DiagnosticBag,
    span: Span | None,
) -> None:
    """The body of an offering's per-name loop: every named move type must
    be defined.

    Parameter DOMAINS are deliberately not checked here. They are a property
    of the move type's DECLARATION, so `_validate_refs` gates every declared
    move type once — which both closes the old gap (a move type no offering
    named was never gated at all) and stops a move type named by two
    offerings from reporting the same defect once per mention."""
    for name in names:
        if name not in defined_move_types:
            bag.unknown(f"offer names unknown move type '{name}'", name, defined_move_types, span, code=Code.UNKNOWN_MOVE_TYPE)


def _no_board_for_directions(game: n.Game, name: str) -> str:
    """The clause a move parameter's refusal of an unminted `dir` (or `dir?`)
    ends with, naming what the game lacks; empty for every other name."""
    refusal = _direction_refusal(game, name.removesuffix("?"))
    if refusal is None:
        return ""
    return f" -- `{DIRECTION_DOMAIN}` is " + refusal


def _check_board_call(nd: n.Call, game: n.Game, bag: DiagnosticBag) -> None:
    """The board-reading native calls (`lines`, BOARD_ONLY_CALL_FUNCS): a
    boardless game has no board to read; a board whose family does not declare
    what the verb reads (`BOARD_VERB_NEEDS`) does not answer it; and a literal
    `k` outside the lengths the board declares is a static error. The
    availability test is the `_BOARD_NEED_GATES` row the `uses` line asks of a
    library; the bound is reused from the board entry's own `lines()`
    (cardlang/stdlib/boards.py), so resolve and the runtime share one
    definition of it; a NON-literal `k` (no rung-1 witness) is left to that
    runtime bound, surfaced as a typed error (recorded residual, issue #111).

    Held by: Derived and Pinned. `BOARD_VERB_NEEDS` maps each board verb to
    the `BoardEntry` field it reads, pinned total against
    BOARD_ONLY_CALL_FUNCS; this check and the runtime `_board_of` both read
    it. Not higher: the Builtin namespace is a string registry throughout, and
    an enum for the board verbs alone would give one registry two shapes."""
    if game.board is None:
        bag.error(
            f"`{nd.func}` reads the board, but the game declares no `board:`",
            nd.span,
            code=Code.MISSING_DECLARATION,
        )
        return
    for gate in _BOARD_NEED_GATES:
        if _refuses(gate, nd, game):
            verb, _, rest = gate.reads.partition(" ")
            bag.error(f"`{nd.func}` {verb}s {rest}, but {gate.lacks(game)}", nd.span, code=Code.MISSING_DECLARATION)
            return
    # A seat verb reads the board from one of its two seats -- a grid's
    # per-player frame, or a seat's borders -- defined only for players 0 and
    # 1. Without this Owner Guard a game with three-plus (or one) seats
    # resolves clean and then dies at setup/play with the board's registry-bug
    # `ValueError` when a verb is called for seat 2 -- a typechecked game
    # failing at runtime, in the wrong channel. The row for the part the verb
    # reads (`_SEAT_GATES`) says why, as the `uses` line does.
    for gate in _SEAT_GATES:
        if _refuses(gate, nd, game):
            verb, _, rest = gate.reads.partition(" ")
            bag.error(
                f"`{nd.func}` {verb}s {rest}, but {gate.lacks(game)}; {gate.fix(game)}",
                nd.span,
                code=Code.MISSING_DECLARATION,
            )
    args = nd.args
    if nd.func == "lines" and len(args) == 1 and isinstance(args[0], n.IntLit):
        try:
            board_entry(game.board.family, game.board.args).lines(args[0].value)
        except OwnerGuardError as exc:
            _tell_board_refusal(exc, game.board.family, nd.span, bag)


def _validate_refs(game: n.Game, cats: _Categories, bag: DiagnosticBag) -> None:
    move_type_defs = {m.name: m for m in game.move_types}
    defined_move_types = set(move_type_defs)
    origins = n.library_origins(game)
    defined_functions = {f.name for f in game.functions}
    native_namespace = call_namespace(game)
    # Which role (if any) each declared zone family is keyed by — the fact the
    # `to each <family>` Owner Guard needs (the executor keys parcels per PLAYER).
    zone_index = {z.name: z.index for z in game.zones}
    # A `produces:` consumer may also name an outcome-declaring phase (its outcome
    # is produced as the phase runs, then dispatched by a sibling consumer).
    outcome_phases = {
        nd.name for nd in _walk(game) if isinstance(nd, n.Phase) and nd.outcome_cases
    }
    # Every DECLARED move type's parameter domains, gated exactly once. The
    # gate itself is unchanged; its REACH was the hole. It used to run from the
    # offering call sites, so a move type no `offer` names
    # had its parameter domains unchecked entirely — and an unchecked domain
    # name falls through `typecheck.type_from_name` to the permissive top,
    # which silently exempts the parameter from every downstream guard
    # (decisions.md, "`Any` means the top, never a failed lookup"). Declaring
    # a move type is what makes its parameters real; whether some phase happens
    # to offer it is not the checker's business — and gating at the declaration
    # also stops a move named by two offerings from reporting one defect
    # twice.
    declared_positions = frozenset(p.name for p in game.positions)
    # `for each <role>` iterates the closed seat/axis roles plus a board's
    # NAMED-MEMBER position domain (`cell`) -- breakthrough's fixed setup array
    # is the witness that lifts it. Integer `positions {}` domains stay refused:
    # no game addresses columns by loop (guards and parameters cover both
    # solitaires), so they stay rejected rather than accepted-and-unwitnessed
    # (issue #111). A boardless game
    # therefore reports the unchanged closed-role list.
    iterable_positions = frozenset(
        p.name for p in game.positions if p.members_named is not None
    )
    state_types = _declared_type_universe(game)
    move_directions = _minted_directions(game)
    for mt in game.move_types:
        if mt.params:
            _check_move_params(mt, bag, mt.span, game, declared_positions, move_directions)
    for nd in _walk(game):
        match nd:
            case n.Call() if (
                nd.func not in native_namespace
                and nd.func not in defined_functions
                and nd.func not in K.KERNEL_CONTRACT_NAMES
            ):
                # `native_namespace` is the game's own, not the corpus-wide
                # registry: a game with a `primitives { }` block names the
                # Primitives it declares and no other game's, so a neighbour's
                # trick winner is an unknown name here rather than a call that
                # resolves and then dispatches through a table this game never
                # claimed (issue #364).
                outside = _slot_name_outside_slot(nd.func)
                if outside is not None:
                    bag.error(outside, nd.span, code=Code.WRONG_SORT_OF_NAME)
                else:
                    bag.unknown(
                        f"call to unknown function '{nd.func}'"
                        + _undeclared_primitive_hint(game, nd.func),
                        nd.func,
                        (*native_namespace, *defined_functions, *K.KERNEL_CONTRACT_NAMES),
                        nd.span,
                        code=Code.UNKNOWN_FUNCTION,
                    )
            case n.Call() if nd.func in defined_functions:
                # A call the game's OWN `function` defines. Every arm below
                # keys a name against a corpus-wide native registry, and a
                # declared game may legally define a function named after a
                # Primitive absent from its namespace — so those registries
                # would answer about Python this call never reaches. The
                # runtime dispatches a defined function first
                # (`evaluate.Call`), and this arm is what keeps resolve's
                # reading of the name the same as the runtime's.
                pass
            case n.Call() if (
                game.content_flavor == "piece" and nd.func in DECK_ONLY_CALL_FUNCS
            ):
                # A deck-reading native call (suit_of, rank_value, a trick-
                # winner, ...) has nothing to read in a piece game. The generic
                # calls (top_of, team_of, ...) are absent from DECK_ONLY and
                # stay legal. This arm and every arm below it that asks a
                # `_CLAUSE_GATES` row are the Shadow Guards of
                # `_check_library_clause_gates` for what a library splices in.
                bag.error(
                    f"{content_kind_clause(game.content_flavor, game.deck)} -- "
                    f"`{nd.func}` reads a card's suit/rank/points, which a piece "
                    f"set has none of",
                    nd.span,
                    code=Code.PIECES_ARE_NOT_CARDS,
                )
            case n.Call() if nd.func in _CARD_POINTS_CALLS:
                # An unanswered `card_points` (an answered one met the
                # defined-function arm above). The points have ONE source, the
                # game's own answer (the deck registry carries no point
                # table), so the call has nothing to read.
                bag.error(
                    f"`card_points(...)` reads the game's card points, but this "
                    f"game declares none — {_card_points_fix(game)}",
                    nd.span,
                    code=Code.MISSING_DECLARATION,
                )
            case n.Call() if nd.func in K.KERNEL_CONTRACT_NAMES:
                # An unanswered Trick Order row: with a Trick Order the
                # driver's default answers it; without one,
                # `_check_trick_order_partition` has refused the call.
                pass
            case n.Call() if nd.func in _SUIT_RANKING_CALLS and game.suit_ranking is None:
                bag.error(
                    f"`{nd.func}` reads a suit's strength from `suit ranking:`, "
                    f"but this game declares no `suit ranking:` — declare one "
                    f"listing {_declared_suits_phrase(game.deck)} strongest first",
                    nd.span,
                    code=Code.MISSING_DECLARATION,
                )
            case n.Call() if nd.func in _TEAM_CALL_FUNCS and not game.teams:
                # The team-indexed `state`/`zone` arms below refuse the
                # declaration side of a missing `teams:`; this and the
                # role-ranging arm refuse the questions.
                bag.error(
                    f"`{nd.func}` asks which team a seat is on, but this game "
                    f"declares no `teams:` — declare the partnerships "
                    f"(`teams: [[0, 2], [1, 3]]`) or ask about the player",
                    nd.span,
                    code=Code.MISSING_DECLARATION,
                )
            case n.Call() if nd.func in BOARD_ONLY_CALL_FUNCS:
                # A board-reading call (lines) in a boardless game, or a literal
                # out-of-range k. The DECK_ONLY twin above (`game.board is None`
                # keyed instead of the flavor). DomainQuery noun validation runs
                # earlier (in `resolve`, before deep name resolution) so its
                # diagnostic is not masked by the pred's unresolved binder.
                _check_board_call(nd, game, bag)
            case n.Call() if (
                regime(game) is Regime.LEGACY
                and nd.func in PRIMITIVE_CALL_FUNCS
            ):
                # The regime partition's other direction, and the Owner Guard
                # for it. A declaration is the ONLY route to a Primitive's
                # Python — yet the name IS a Primitive, so the corpus-wide
                # namespace (`CALL_FUNCS`) admits it and the unknown-name arm
                # above says nothing. Without this the call reaches typecheck's
                # `Call` arm — the Shadow Guard behind this one, with
                # `native_call`'s refusal behind that: the wrong channel, about
                # a name the registry does hold.
                #
                # AFTER the flavor arms deliberately: a piece game cannot fix
                # this call by writing a block — the deck-only refusal stands
                # either way — so the reason that speaks there is the one whose
                # fix is real (`_check_primitive_name`'s ordering rule).
                bag.error(
                    f"`{nd.func}` is a Primitive a game reaches only by "
                    f"declaring it, and this game writes no `primitives {{ }}` "
                    f"block; declare it in one to call it",
                    nd.span,
                    code=Code.MISSING_DECLARATION,
                )
            case n.StateDecl():
                # One arm, both checks: a match runs its first matching arm
                # only, so two guarded StateDecl arms would report at most one
                # of two independent errors on the same declaration.
                refused = _combination_outside_a_parameter(nd.type_name, "a state variable")
                if refused is not None:
                    bag.error(refused, nd.span, code=Code.TYPE_NOT_ALLOWED_HERE)
                elif (typed := _state_type_refusal(game, nd.type_name)) is not None:
                    bag.error(
                        "state variable " + cite_named(nd, f"'{nd.name}'")
                        + f" is typed `{nd.type_name}`, " + typed,
                        nd.span,
                        code=Code.TYPE_NOT_ALLOWED_HERE,
                    )
                elif nd.type_name not in state_types:
                    bag.unknown(
                        f"unknown type '{nd.type_name}' in declaration of "
                        + cite_named(nd, f"'{nd.name}'"),
                        nd.type_name,
                        state_types,
                        nd.span,
                        code=Code.UNKNOWN_TYPE,
                    )
                if nd.index is not None and role_of(nd.index) not in ZONE_INDEX_ROLES:
                    # Same guard as a zone's index role, same registry. Before
                    # it existed, `state { x[suit] : Integer = 0 }` checked
                    # clean and the runtime silently keyed it BY PLAYERS (the
                    # driver's key-set dispatch defaulted every non-team role
                    # to seats) — the declared index was accepted and ignored.
                    roles = ", ".join(role_names(ZONE_INDEX_ROLES))
                    bag.unknown(
                        "state variable " + cite_named(nd, f"'{nd.name}'") + f" is indexed by "
                        f"'{nd.index}', which is not an indexable role "
                        f"({roles}) — a value domain has no per-member store "
                        f"(roadmap.md records the extension)",
                        nd.index,
                        role_names(ZONE_INDEX_ROLES),
                        nd.span,
                        code=Code.WRONG_SUBSCRIPT,
                    )
                elif _refuses(_TEAM_STATE_GATE, nd, game):
                    # A team-indexed store in a game with no teams has
                    # an EMPTY key set: it declares fine, holds nothing, and
                    # every later `x[…] := …` hits the runtime key guard far
                    # from the real mistake (the missing `teams:`).
                    bag.error(
                        "state variable " + cite_named(nd, f"'{nd.name}'") + " is indexed by 'team' but "
                        f"the game declares no `teams:` — there are no "
                        f"teams to key it by",
                        nd.span,
                        code=Code.MISSING_DECLARATION,
                    )
            case n.ZoneDecl() if (
                nd.index is not None
                and role_of(nd.index) is Role.TEAM
                and not game.teams
            ):
                bag.error(
                    f"zone '{nd.name}' is indexed by 'team' but the game "
                    f"declares no `teams:` — there are no teams to key "
                    f"it by",
                    nd.span,
                    code=Code.MISSING_DECLARATION,
                )
            case n.LetStmt() if (
                nd.index is not None and nd.index in _MISLEADING_LET_INDEXES
            ):
                bag.error(
                    f"`let {nd.name}[{nd.index}]` builds a per-PLAYER map — "
                    f"the index is a binder bound to each player in turn, "
                    f"whatever its name — so a binder named '{nd.index}' "
                    f"reads as a per-{nd.index} store this form does not "
                    f"build. Rename the binder; per-value stores are recorded "
                    f"in roadmap.md",
                    nd.span,
                    code=Code.WRONG_SUBSCRIPT,
                )
            case n.Produces() if nd.phase not in outcome_phases:
                bag.unknown(
                    f"produces names unknown outcome phase '{nd.phase}'",
                    nd.phase,
                    outcome_phases,
                    nd.span,
                    code=Code.UNKNOWN_OUTCOME,
                )
            case n.ForEach() if _refuses(_CELL_RANGE_GATE, nd, game):
                bag.error(
                    "`for each cell ...` ranges over the board's cells, but this "
                    f"game declares no `board:` — {_board_remedy(game)}",
                    nd.span,
                    code=Code.MISSING_DECLARATION,
                )
            case n.ForEach() if (
                role_of(nd.role) not in _ITERATION_ROLES
                and nd.role not in iterable_positions
                # A declared board that minted no cells is refused as a
                # `board:` clause (`_resolve_board`).
                and not (_cell_ranges(nd, game) and game.board is not None)
            ):
                bag.unknown(
                    f"unknown `for each` role '{nd.role}' (expected one of "
                    f"{', '.join(sorted(role_names(_ITERATION_ROLES) + sorted(iterable_positions)))})",
                    nd.role,
                    (*role_names(_ITERATION_ROLES), *iterable_positions),
                    nd.span,
                    code=Code.UNKNOWN_INDEX_DOMAIN,
                )
            case (n.ForEach() | n.Quantifier()) if (
                game.content_flavor == "piece" and role_of(nd.role) in CARD_AXIS_ROLES
            ):
                # `for each suit` / `any rank where` enumerate the deck's axes;
                # a piece set has no role surface for its own axes (side/kind),
                # so the card-axis roles are rejected naming the kind. The seat
                # roles (player/team) fall through, legal in both flavors.
                bag.error(
                    f"{content_kind_clause(game.content_flavor, game.deck)} -- "
                    f"the `{nd.role}` role ranges over a deck's {nd.role}s, which "
                    f"a piece set has none of",
                    nd.span,
                    code=Code.PIECES_ARE_NOT_CARDS,
                )
            case (n.ForEach() | n.Quantifier()) if _refuses(_TEAM_RANGE_GATE, nd, game):
                # The team domain of a game with no `teams:` is empty, so the
                # question would answer itself: `any` false, `all` true, `for
                # each` never running.
                spelled = (
                    "for each team"
                    if isinstance(nd, n.ForEach)
                    else ("any team where" if nd.kind == "any" else "all teams where")
                )
                bag.error(
                    f"`{spelled} ...` ranges over teams, but this game declares "
                    f"no `teams:` — there are no teams to range over; declare "
                    f"the partnerships (`teams: [[0, 2], [1, 3]]`) or range "
                    f"over players",
                    nd.span,
                    code=Code.MISSING_DECLARATION,
                )
            case n.EachSimultaneous() if _simultaneous_role_refused(nd):
                pass  # refused by `_refused_binder_sources`, before names are classified
            case n.EachSimultaneous() if n.simultaneous_body_error(nd.body) is not None:
                # The form gated its DOMAIN (above) and not its BODY. The executor
                # implements exactly one body shape, so everything else compiled and
                # then died on a bare assert — a runtime crash for a statically
                # checkable error, in the wrong channel. `run` made it reachable
                # from an entirely natural-looking program (`each player
                # simultaneously: run pass_card(player)`), since an expansion is a
                # block and never a bare movement.
                #
                # The reason comes FROM the executor's own requirement
                # (`n.simultaneous_body_error`), not from a hand-written copy of it:
                # the first version of this Owner Guard mirrored only the first of five
                # requirements, so `move chosen one card …` still reached the assert.
                bag.error(
                    f"`each {nd.role} simultaneously` runs one chosen movement per "
                    f"{nd.role} and nothing else — "
                    f"{n.simultaneous_body_error(nd.body)}. The form snapshots every "
                    f"{nd.role}'s selection against the state BEFORE the block and "
                    f"applies them together (that is what makes the pass atomic — "
                    f"nobody sees a passed card before choosing their own), and a "
                    f"snapshot is only defined for that one shape",
                    nd.span,
                    code=Code.OUT_OF_PLACE,
                )
            case n.CardLiteral() if game.content_flavor == "piece":
                # `mark of x` is a well-formed literal against a piece set's own
                # ranks/suits (the axis values populate the same namespaces), so
                # the membership check below would ACCEPT it -- a card-literal
                # form given piece meaning. Reject the form itself, naming the
                # kind, before that.
                bag.error(
                    f"{content_kind_clause(game.content_flavor, game.deck)} -- a "
                    f"card literal (`{nd.rank} of {nd.suit}`) names a deck card; "
                    f"a piece has no rank-of-suit identity",
                    nd.span,
                    code=Code.PIECES_ARE_NOT_CARDS,
                )
            case n.CardLiteral():
                if nd.rank not in cats.ranks:
                    bag.unknown(f"unknown rank '{nd.rank}' in card literal", nd.rank, cats.ranks, nd.span, code=Code.UNKNOWN_RANK)
                if nd.suit not in cats.suits:
                    bag.unknown(f"unknown suit '{nd.suit}' in card literal", nd.suit, cats.suits, nd.span, code=Code.UNKNOWN_SUIT)
            case n.RotateStmt():
                # Both checks in ONE arm: a bare `case n.RotateStmt():` above a guarded
                # one consumes the node, so the guarded arm never runs. (It did exactly
                # that, and `tests/test_binder_scoping.py` caught it.)
                bad = _bad_write_target(game, nd)
                if bad is not None:
                    bag.error(bad, nd.target.span, code=Code.NOT_WRITABLE)
                for value in nd.values:
                    if value not in cats.enums:
                        bag.unknown(
                            f"rotate through unknown value '{value}'", value, cats.enums, nd.span,
                            code=Code.UNKNOWN_NAME,
                        )
            case n.AssignStmt():
                bad = _bad_write_target(game, nd)
                if bad is not None:
                    bag.error(bad, nd.target.span, code=Code.NOT_WRITABLE)
            case n.Transfer():
                for endpoint, direction in (
                    ("source", "move cards from"),
                    ("dest", "move cards to"),
                ):
                    endpoint_refused = _bad_zone_endpoint(game, nd, endpoint, direction)
                    if endpoint_refused is not None:
                        bad, root = endpoint_refused
                        bag.error(bad, root.span, code=Code.WRONG_SORT_OF_NAME)
                # The joint-selection matrix (decisions.md "Joint-predicate
                # selection"): `jointly` is a DECISION over subsets, so it
                # requires `chosen` — a dealt jointly-selection has no
                # decider and a `random` one has no corpus user (both
                # recorded in roadmap.md, "Grammar surface deferred by
                # the checker"); `some` (any-size) is meaningless
                # without a joint predicate to own the size.
                if nd.joint and nd.selection_mode != "chosen":
                    bag.error(
                        "`where jointly` selects one subset as a player "
                        "decision — it requires `chosen` (a dealt or "
                        "`random` joint selection is not implemented; "
                        "recorded in roadmap.md)",
                        nd.span,
                        code=Code.NOT_YET_SUPPORTED,
                    )
                if nd.joint and nd.dest_each:
                    # `to each` would silently make EACH destination seat its
                    # own subset-decider over the shrinking pool — the decider
                    # identity is info-set-load-bearing, and no corpus game
                    # wants the shape (recorded in roadmap.md, "Grammar
                    # surface deferred by the checker").
                    bag.error(
                        "`where jointly` with `to each` is not implemented — "
                        "each destination seat would become its own subset "
                        "decider; write one joint selection per destination "
                        "instead (recorded in roadmap.md)",
                        nd.span,
                        code=Code.NOT_YET_SUPPORTED,
                    )
                if nd.amount == "some" and not nd.joint:
                    bag.error(
                        "amount `some` (any satisfying size) is only "
                        "meaningful under `where jointly`, whose predicate "
                        "owns the size constraint — use a count, `one`, or "
                        "`all` otherwise",
                        nd.span,
                        code=Code.OUT_OF_PLACE,
                    )
                if nd.dest_each and not isinstance(nd.dest, n.NameRef):
                    # The executor keys the family by BARE name per seat, so a
                    # subscripted or computed destination has no meaning under
                    # `each`. Before this Owner Guard, `to each hand[0]` checked
                    # clean and reached an executor that requires this
                    # destination to be a bare name it can key per seat.
                    bag.error(
                        "`to each` deals into a player-indexed family named "
                        "bare (like `to each hand`) — a subscripted or "
                        "computed destination targets one zone, so drop "
                        "`each` or name the family",
                        nd.span,
                        code=Code.WRONG_ZONE_SHAPE,
                    )
                if nd.dest_each and isinstance(nd.dest, n.NameRef):
                    # `to each X` deals one parcel per PLAYER (the executor
                    # iterates seats and keys `X[player]`), so X must be a
                    # player-indexed family. Before this Owner Guard, `to each deck`
                    # (a singleton) checked clean and then asked the zone store
                    # for a player-keyed family of that name, which it requires
                    # to be declared and refuses at play time;
                    # and `to each captured` (a TEAM family) silently dealt
                    # into team slots AS IF team ids were seats before crashing
                    # — player keying was assumed, not checked, the same class
                    # as the `== "team"` defaults the domain table replaced.
                    idx = zone_index.get(nd.dest.name)
                    # Intrinsic: `to each` deals one share per PLAYER, so the
                    # destination family must be player-keyed whatever else the
                    # table gains.
                    each_refused = _each_destination_refuses(zone_index, nd.dest.name, nd.dest.ref_kind)
                    if each_refused and nd.dest.ref_kind == "zone":
                        what_z = (
                            "a singleton zone"
                            if idx is None
                            else f"a family keyed by {idx}"
                        )
                        bag.error(
                            f"`to each {nd.dest.name}` deals one parcel per "
                            f"player, but '{nd.dest.name}' is {what_z} — name "
                            f"a player-indexed family (like hand[player]), or "
                            f"target one instance directly",
                            nd.span,
                            code=Code.WRONG_ZONE_SHAPE,
                        )
                    elif each_refused and nd.dest.ref_kind is not None:
                        # The executor consumes the NAME (`zones.instance(X,
                        # player)`), not a zone value — so unlike the generic
                        # endpoints, a binder can never stand here even when it
                        # HOLDS a zone: `let h = hand[0]` / `to each h` would
                        # type clean (h is a zone) and then ask the zone store
                        # for a family literally named 'h', which requires a
                        # declared family of that name and refuses at play time.
                        what_k = _WRITE_TARGET_KINDS.get(
                            nd.dest.ref_kind, f"a {nd.dest.ref_kind}"
                        )
                        bag.error(
                            f"`to each {nd.dest.name}` deals into "
                            f"{nd.dest.name}[player] BY NAME, so it must name "
                            f"a player-indexed zone family declared in "
                            f"`zones {{ }}` — '{nd.dest.name}' is {what_k}",
                            nd.span,
                            code=Code.WRONG_ZONE_SHAPE,
                        )
            case n.EpistemicOp() if _refuses(_CARD_CONTENT_GATE, nd, game):
                # `reveal one card from ...` hardcodes the noun "card"; a piece
                # game has no such statement (the piece twin is grammatically
                # inexpressible). `shuffle` falls through -- it moves a zone's
                # order, no card content, legal in both flavors.
                bag.error(
                    f"{content_kind_clause(game.content_flavor, game.deck)} -- "
                    f"`reveal one card` identifies a deck card; reveal a piece is "
                    f"not expressible",
                    nd.span,
                    code=Code.PIECES_ARE_NOT_CARDS,
                )
            case n.EpistemicOp():
                # The other member of the zone-position class: `shuffle turn` /
                # `reveal one card from turn` checked clean and then reached an
                # executor that requires an actual Zone as the op's target and
                # refuses anything else, exactly like the movement endpoints.
                zone_refused = _bad_zone_endpoint(game, nd, "zone", nd.op)
                if zone_refused is not None:
                    bad, root = zone_refused
                    bag.error(bad, root.span, code=Code.WRONG_SORT_OF_NAME)
            case n.Winner() | n.StopResult() if (
                nd.state_var is not None and nd.state_var not in cats.state_vars
            ):
                outside = _slot_name_outside_slot(nd.state_var)
                if outside is not None:
                    bag.error(outside, nd.span, code=Code.WRONG_SORT_OF_NAME)
                else:
                    bag.unknown(
                        f"{ranking_slot(nd).unknown} references unknown "
                        f"variable '{nd.state_var}'",
                        nd.state_var,
                        cats.state_vars,
                        nd.span,
                        code=Code.UNKNOWN_STATE_VARIABLE,
                    )
            case n.Turns() if nd.again is not None and nd.again not in cats.state_vars:
                # The go-again flag is ordinary game state the body's effects
                # write (decisions.md "The `turns` form") — a plain string
                # field like `Winner.target`, so the generic NameRef pass
                # never sees it; validate it here or it fails only at the
                # first turn boundary, where the executor reads it out of
                # round state — which requires the name to be in scope.
                bag.unknown(
                    f"`again {nd.again}`: names no declared state variable — "
                    f"the go-again flag is ordinary Boolean game state the "
                    f"body's move effects write",
                    nd.again,
                    cats.state_vars,
                    nd.span,
                    code=Code.UNKNOWN_STATE_VARIABLE,
                )
            case n.Offer():
                _check_offering_moves(nd.offering, defined_move_types, bag, nd.span)
                _check_card_offering(
                    nd.offering, move_type_defs, game, bag, nd.span, origins.get(id(nd))
                )
            case n.ClimbRound():
                # Trick zones plus the two combination-engine queries
                # (`combinations` lead, `follows` legal-follows). The termination
                # predicate's names are checked by the generic NameRef pass; its
                # Boolean type by the type checker.
                zone_names = {z.name for z in game.zones}
                if nd.source_zone not in zone_names:
                    bag.unknown(
                        f"climb round source zone '{nd.source_zone}' is unknown",
                        nd.source_zone, zone_names, nd.span,
                        code=Code.UNKNOWN_ZONE,
                    )
                if nd.play_zone not in zone_names:
                    bag.unknown(
                        f"climb round play zone '{nd.play_zone}' is unknown",
                        nd.play_zone, zone_names, nd.span,
                        code=Code.UNKNOWN_ZONE,
                    )
                if nd.move_type not in LIBRARY_MOVE_TYPES:
                    bag.unknown(
                        f"climb round move type '{nd.move_type}' is unknown",
                        nd.move_type, (CLIMB_DECISION_MOVE_TYPE,), nd.span,
                        code=Code.UNKNOWN_MOVE_TYPE,
                    )
                elif nd.move_type != CLIMB_DECISION_MOVE_TYPE:
                    # The climbing form's decision site is hardwired to
                    # `play_combination` — nothing in `ClimbForm` reads this
                    # field at all — so any other name ran as a climb regardless
                    # and meant nothing (decisions.md "Surface totality"). The
                    # trick form has carried the same Owner Guard since its surface was
                    # written; this form went without one.
                    bag.error(
                        f"the climb round form runs `{CLIMB_DECISION_MOVE_TYPE}`; "
                        f"'{nd.move_type}' is not runnable on it (roadmap.md)",
                        nd.span,
                        code=Code.NOT_YET_SUPPORTED,
                    )
                # The two slot names are the engine's, paired and stamped by
                # `_resolve_climb_engines`.
            case n.TrickRound():
                zone_names = {z.name for z in game.zones}
                if nd.source_zone not in zone_names:
                    bag.unknown(
                        f"round source zone '{nd.source_zone}' is unknown",
                        nd.source_zone, zone_names, nd.span,
                        code=Code.UNKNOWN_ZONE,
                    )
                if nd.play_zone not in zone_names:
                    bag.unknown(
                        f"round play zone '{nd.play_zone}' is unknown",
                        nd.play_zone, zone_names, nd.span,
                        code=Code.UNKNOWN_ZONE,
                    )
                else:
                    # A trick's plays ARE the provenance every winner reads, so
                    # the zone they land in must project identity to every
                    # observer — otherwise the winner is computed from facts no
                    # player's own stream could derive. Every trick round, not
                    # only a Trick Order one: the rule is the [[arrival-record]]
                    # rule (issue #256), and this is where the play zone is
                    # named (issue #250 PR 1, ruled point 4).
                    play_decl = next(
                        (z for z in game.zones if z.name == nd.play_zone), None
                    )
                    if (
                        play_decl is not None
                        and play_decl.type_ref.name in LIBRARY_ZONE_TYPES
                        and not identity_to_all(play_decl.type_ref.name)
                    ):
                        bag.error(
                            f"round `into {nd.play_zone}` "
                            f"({play_decl.type_ref.name}): a trick's play zone "
                            f"must project identity to every observer — the "
                            f"plays are the provenance every winner reads; use "
                            f"a TrickPile",
                            nd.span,
                            code=Code.WRONG_ZONE_VISIBILITY,
                        )
                if nd.winner_fn not in _ROUND_QUERY_REGISTRIES[(n.TrickRound, "winner_fn")]:
                    bag.unknown(
                        f"trick round winner '{nd.winner_fn}' is not a trick "
                        f"winner function",
                        nd.winner_fn,
                        {
                            name
                            for name in _ROUND_QUERY_REGISTRIES[(n.TrickRound, "winner_fn")]
                            if not _winner_refusals(replace(nd, winner_fn=name), game)
                        },
                        nd.span,
                        code=Code.UNKNOWN_ROUND_FUNCTION,
                    )
                elif nd.winner_fn in TRICK_ORDER_GATED_WINNERS:
                    # A Trick Order winner takes no `trump` argument at all --
                    # its trumps are the game's `is_trump` -- so this arm's
                    # question (a clause the winner would ignore) is not the one
                    # to ask. `_check_trick_order_partition` owns both cells,
                    # with a Trick Order and without one.
                    pass
                elif "ignores the trump clause" in _winner_refusals(nd, game):
                    # The winner contract carries a `trump` argument for every
                    # member, but only TRUMP_READING_WINNERS' bodies read it:
                    # on the others the round's `trump` clause was evaluated,
                    # traced, passed, and dropped — accepted-but-ignored
                    # (decisions.md "Surface totality"). Same arm as the
                    # `play_to_trick` guard below: a round-configuration
                    # clause its own slot cannot use.
                    readers = ", ".join(sorted(TRUMP_READING_WINNERS))
                    bag.error(
                        f"round `trump` clause on winner {nd.winner_fn}, which "
                        f"reads no trump — the clause would be silently ignored; "
                        f"drop it, or name a winner that reads a trump ({readers})",
                        nd.span,
                        code=Code.HAS_NO_EFFECT,
                    )
                if nd.move_type not in LIBRARY_MOVE_TYPES:
                    bag.unknown(
                        f"round move type '{nd.move_type}' is unknown",
                        nd.move_type, ("play_to_trick",), nd.span,
                        code=Code.UNKNOWN_MOVE_TYPE,
                    )
                elif nd.move_type != "play_to_trick":
                    # The trick form's decision site is hardwired to
                    # `play_to_trick`; any other name would silently run as a
                    # trick anyway (decisions.md "Surface totality").
                    bag.error(
                        f"the trick round form runs `play_to_trick`; "
                        f"'{nd.move_type}' is not runnable on it (roadmap.md)",
                        nd.span,
                        code=Code.NOT_YET_SUPPORTED,
                    )
                if (
                    nd.early_termination is not None
                    and nd.early_termination
                    not in _ROUND_QUERY_REGISTRIES[(n.TrickRound, "early_termination")]
                ):
                    bag.unknown(
                        f"round early-termination predicate "
                        f"'{nd.early_termination}' is unknown",
                        nd.early_termination,
                        _ROUND_QUERY_REGISTRIES[(n.TrickRound, "early_termination")],
                        nd.span,
                        code=Code.UNKNOWN_ROUND_FUNCTION,
                    )
