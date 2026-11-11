"""The clause gates: what a game clause admits, and the test each gate asks."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field, fields, is_dataclass
from typing import Literal
from cardlang.ast import nodes as n
from cardlang.board_domains import BOARD_DOMAIN
from cardlang.builtins.functions import (
    BOARD_NEEDS,
    BOARD_ONLY_CALL_FUNCS,
    BOARD_VERB_NEEDS,
    BoardNeed,
    DECK_ONLY_CALL_FUNCS,
    PRIMITIVE_CLIMB_FOLLOWS,
    PRIMITIVE_CLIMB_LEADS,
    TRICK_ORDER_EXCLUDED_FUNCS,
    TRICK_ORDER_EXCLUDED_WINNERS,
    TRICK_ORDER_GATED_FUNCS,
    TRICK_ORDER_GATED_WINNERS,
)
from cardlang.builtins.signatures import CALL_SIGS
from cardlang import kernel_contracts as K
from cardlang.attribution import cite_named
from cardlang.diagnostics import Said
from cardlang.domains import Role, role_of
from cardlang.runtime.errors import OwnerGuardError
from cardlang.stdlib.boards import BoardEntry, board_entry, board_spelling
from cardlang.typecheck import (
    POSITIVE_PARAM_DOMAIN,
    RANKING_GATED_FUNCS,
    card_content_forms,
    ranking_gated_slots,
)
from cardlang.types import TCell, TCollection, TInteger, TPlayer, TTeam
from cardlang.resolve.walk import _walk
from cardlang.resolve.declared import _declared_board

# The board-only calls that read the board from one of its two seats -- a
# movement frame's per-player view, where one seat's forward is the other's backward,
# or a seat's own borders (cardlang/stdlib/boards.py). Derived as exactly the
# board verbs taking a player argument, so a later player-taking board verb
# joins this set (and its two-seat Owner Guard) by construction rather than by
# a hand-list that would drift. The player-free board calls (`lines`,
# `is_diagonal`, `neighbors`) read no seat and stay unaffected.
_SEAT_CALL_FUNCS = frozenset(
    fn
    for fn in BOARD_ONLY_CALL_FUNCS
    if any(isinstance(p, TPlayer) for p in CALL_SIGS[fn].params)
)

def _mentions_team(value: object) -> bool:
    """Whether a type, or any type nested in it, is `Team`."""
    if isinstance(value, TTeam):
        return True
    if isinstance(value, tuple):
        return any(_mentions_team(v) for v in value)
    if is_dataclass(value) and not isinstance(value, type):
        return any(_mentions_team(getattr(value, f.name)) for f in fields(value))
    return False


# The Builtins that take or yield a team: each asks the game's `teams:`
# partition, so a game declaring none is refused at the call. Derived from the
# signatures, so a later team Builtin joins the refusal by construction.
_TEAM_CALL_FUNCS = frozenset(
    fn for fn, sig in CALL_SIGS.items() if _mentions_team(sig)
)

# The calls that read the game's card points, refused in a game that answers
# no `card_points` contract.
_CARD_POINTS_CALLS: frozenset[str] = frozenset({"card_points"})

# The calls that read the game's Trick Order, refused in a game without one:
# its three answers, and the two Builtins over them.
_TRICK_ORDER_READERS: frozenset[str] = TRICK_ORDER_GATED_FUNCS | frozenset(
    K.TRICK_ORDER_CONTRACTS
)

# The Builtins that read the game's `suit ranking:`, refused in a game that
# declares none.
_SUIT_RANKING_CALLS: frozenset[str] = frozenset({"suit_value"})


# What a `_CLAUSE_GATES` row's construct is to the clause it gates
# (`_ClauseGate.role`).
ClauseRole = Literal["reader", "engine_read", "beside"]


@dataclass(frozen=True)
class _ClauseGate:
    """A game clause some constructs need, or are refused beside.

    `needs` is the gate's one test: what in a node the clause decides, in the
    designer's words, or nothing. The gate asks it of the game's own text, and
    `_check_library_clause_gates` asks it of a library's definitions before the
    splice. A Builtin row's test is "a call whose name is in `members`", and
    `members` is the owning gate's own registry, never a copy of it. `unmet`
    reads the clause as the game WROTE it, because the `uses` check runs before
    `_expand_ranking`: a convention keyword is a `ranking:` here. A clause that
    is written but malformed counts as met, so its own Owner Guard speaks rather
    than a request for a clause the game already has. `verb` and `reads` say
    what the library does with what `needs` names ("calls `x`, which reads
    ..."), and `lacks` and `fix` say what the game has instead and what to
    write.

    `clause` names the `n.Game` field the row gates on, and `role` says what
    the row's construct is to that clause: a `reader` is a construct the
    clause exists for, so a clause no construct of any of its reader rows
    meets is read by nothing (`_check_unread_clauses`); an `engine_read`
    clause is read by the engine whatever the text writes; a `beside` row
    refuses a construct next to a clause it does not read. Both are
    required, so a row cannot join the table unclassified."""

    needs: Callable[[object, n.Game], tuple[Said, ...]]
    unmet: Callable[[n.Game], bool]
    verb: str
    reads: str
    lacks: Callable[[n.Game], str]
    fix: Callable[[n.Game], str]
    members: frozenset[str] = frozenset()
    clause: str = field(kw_only=True)
    role: ClauseRole = field(kw_only=True)


def _builtin_gate(
    members: frozenset[str],
    unmet: Callable[[n.Game], bool],
    reads: str,
    lacks: Callable[[n.Game], str],
    fix: Callable[[n.Game], str],
    *,
    clause: str,
    role: ClauseRole,
) -> _ClauseGate:
    """A row whose test is a call to one of the gate's Builtins."""
    return _ClauseGate(
        needs=lambda nd, g: (
            (f"`{nd.func}`",) if isinstance(nd, n.Call) and nd.func in members else ()
        ),
        unmet=unmet,
        verb="calls",
        reads=reads,
        lacks=lacks,
        fix=fix,
        members=members,
        clause=clause,
        role=role,
    )


def _teams_example(game: n.Game) -> str:
    """A `teams:` clause that partitions this game's seats, alternating them
    between two partnerships, for a refusal to offer as written."""
    count = max(game.players.count, 2)
    sides = (range(0, count, 2), range(1, count, 2))
    return "teams: [" + ", ".join(
        "[" + ", ".join(map(str, side)) + "]" for side in sides
    ) + "]"


def _declares_ranking(game: n.Game) -> bool:
    """`ranking:` as written or as expanded: before `_expand_ranking` a
    convention keyword is the clause, after it the expanded order is, and a
    convention that cannot expand is refused by resolve itself."""
    return bool(game.ranking) or game.ranking_convention is not None


def _rank_parameters(node: object, game: n.Game) -> tuple[str, ...]:
    """A move type's `Rank` parameter, which enumerates the declared ranking.
    `Rank?` is no parameter domain at all (`_FIXED_DOMAINS`)."""
    if isinstance(node, n.MoveTypeDef) and any(p.type_name == "Rank" for p in node.params):
        return ("a `Rank` parameter",)
    return ()


def _team_ranges(node: object, game: n.Game) -> tuple[str, ...]:
    """A range over the team domain: `for each team`, `any team where`, `all
    teams where`."""
    if isinstance(node, (n.ForEach, n.Quantifier)) and role_of(node.role) is Role.TEAM:
        if isinstance(node, n.ForEach):
            return ("`for each team`",)
        return ("`any team where`",) if node.kind == "any" else ("`all teams where`",)
    return ()


def _team_keyed_state(node: object, game: n.Game) -> tuple[Said, ...]:
    """A state declaration keyed by team."""
    if (
        isinstance(node, n.StateDecl)
        and node.index is not None
        and role_of(node.index) is Role.TEAM
    ):
        return (cite_named(node, f"`{node.name}[team]`"),)
    return ()


def _cell_ranges(node: object, game: n.Game) -> tuple[str, ...]:
    """A `for each` over the board's cells, the domain a `board:` mints."""
    if isinstance(node, n.ForEach) and node.role == BOARD_DOMAIN:
        return ("`for each cell`",)
    return ()


def _board_positions_past_end(node: object, game: n.Game) -> tuple[str, ...]:
    """A literal position past the end of a board region, read off the declared
    board (`_position_past_end`)."""
    if not (isinstance(node, n.Subscript) and isinstance(node.obj, n.Call)):
        return ()
    past = _position_past_end(node, game)
    if past is None:
        return ()
    index, length = past
    return (f"`{node.obj.func}(...)[{index}]` on a region of {length}",)


def _trick_order_reading_slots(node: object, game: n.Game) -> tuple[str, ...]:
    """A trick round naming a winner that reads the game's Trick Order."""
    if isinstance(node, n.TrickRound) and node.winner_fn in TRICK_ORDER_GATED_WINNERS:
        return (f"round winner `{node.winner_fn}`",)
    return ()


def _round_trump_clauses(node: object, game: n.Game) -> tuple[str, ...]:
    """A trick round's own `trump` clause."""
    if isinstance(node, n.TrickRound) and node.trump is not None:
        return ("a round `trump` clause",)
    return ()


def _trick_order_excluded_winners(node: object, game: n.Game) -> tuple[str, ...]:
    """A trick round naming a winner a Trick Order replaces."""
    if isinstance(node, n.TrickRound) and node.winner_fn in TRICK_ORDER_EXCLUDED_WINNERS:
        return (f"round winner `{node.winner_fn}`",)
    return ()


# EVERY registered climbing query: a climb query carries its own card order
# (the tichu_* engine hard-codes one), so a game naming one beside a Trick
# Order has two orders that the engine runs side by side.
_CLIMB_QUERIES = PRIMITIVE_CLIMB_LEADS | PRIMITIVE_CLIMB_FOLLOWS


def _climb_queries(node: object, game: n.Game) -> tuple[tuple[str, str], ...]:
    """A climbing round's queries, as (slot, name), each carrying its own card
    order."""
    if not isinstance(node, n.ClimbRound):
        return ()
    return tuple(
        (slot, name)
        for slot, name in (("combinations", node.combos_fn), ("follows", node.follows_fn))
        if name in _CLIMB_QUERIES
    )


def _trick_order_replaced_slots(node: object, game: n.Game) -> tuple[str, ...]:
    """Every round slot a Trick Order replaces, refused beside one
    by `_check_trick_order_partition`. An `early` clause on the Trick Order
    winner is not one: no clause the game writes clears it, so it is the
    library's own to drop and is refused in its file."""
    return (
        _round_trump_clauses(node, game)
        + _trick_order_excluded_winners(node, game)
        + tuple(f"climb query `{name}`" for _, name in _climb_queries(node, game))
    )


def _card_contents(node: object, game: n.Game) -> tuple[str, ...]:
    return card_content_forms(node)


def _ranking_slots(node: object, game: n.Game) -> tuple[str, ...]:
    return tuple(f"{slot} `{name}`" for slot, name in ranking_gated_slots(node))


_PIECES_LACK = "this game is played with pieces"
_PIECES_FIX = "a game played with pieces cannot use this library"
_NO_RANKING = "this game declares no `ranking:`"
_NO_TEAMS = "this game declares no `teams:`"
# What a game without a Trick Order writes to have one.
_ANSWER_IS_TRUMP = (
    "answer `is_trump`: write `function is_trump(card : Card) = …`, or "
    "`function is_trump(card : Card) = false` for a game with no trumps"
)


def _drop_trick_order(game: n.Game) -> str:
    """How the designer removes the game's Trick Order."""
    return "drop the Trick Order's functions"


def _trick_order_fix(game: n.Game) -> str:
    return (
        f"a game with a Trick Order cannot use this library; "
        f"{_drop_trick_order(game)} or the `uses` line"
    )


def _card_points_fix(game: n.Game) -> str:
    return (
        "declare a `card_points { }` table, or write "
        "`function card_points(card : Card) = …`"
    )


def _teams_fix(game: n.Game) -> str:
    return f"declare the partnerships (`{_teams_example(game)}`)"


_CARD_CONTENT_GATE = _ClauseGate(
    _card_contents,
    lambda g: g.content_flavor == "piece",
    "writes",
    "read a deck card's content",
    lambda g: _PIECES_LACK,
    lambda g: _PIECES_FIX,
    clause="deck",
    role="engine_read",
)
_TRICK_ORDER_READING_GATE = _ClauseGate(
    _trick_order_reading_slots,
    lambda g: g.content_flavor == "card" and not K.has_trick_order(g),
    "writes",
    "read the game's Trick Order",
    lambda g: "this game declares none",
    lambda g: _ANSWER_IS_TRUMP,
    clause="trick_order",
    role="reader",
)
_TRICK_ORDER_REPLACED_GATE = _ClauseGate(
    _trick_order_replaced_slots,
    lambda g: g.content_flavor == "card" and K.has_trick_order(g),
    "writes",
    "carry the trump and card order a Trick Order replaces",
    lambda g: "this game declares a Trick Order",
    _trick_order_fix,
    clause="trick_order",
    role="beside",
)
_TEAM_RANGE_GATE = _ClauseGate(
    _team_ranges,
    lambda g: not g.teams,
    "writes",
    "range over the game's teams",
    lambda g: _NO_TEAMS,
    _teams_fix,
    clause="teams",
    role="engine_read",
)
_TEAM_STATE_GATE = _ClauseGate(
    _team_keyed_state,
    lambda g: not g.teams,
    "provides",
    "key state by the game's teams",
    lambda g: _NO_TEAMS,
    _teams_fix,
    clause="teams",
    role="engine_read",
)


def _board_remedy(game: n.Game) -> str:
    """What a game lacking a `board:` can do: a board lays out a piece game,
    and is refused beside `cards:`."""
    if game.content_flavor == "piece":
        return "declare one"
    return "a board is declared only in a game played with pieces"


def _board_fix(game: n.Game) -> str:
    remedy = _board_remedy(game)
    if game.content_flavor == "piece":
        return remedy
    return f"{remedy}, so a card game cannot use this library"


_CELL_RANGE_GATE = _ClauseGate(
    _cell_ranges,
    lambda g: g.board is None,
    "writes",
    "range over the board's cells",
    lambda g: "this game declares no `board:`",
    _board_fix,
    clause="board",
    role="engine_read",
)
_BOARD_POSITION_GATE = _ClauseGate(
    _board_positions_past_end,
    lambda g: g.board is not None,
    "writes",
    "read a position past the end of a board region",
    lambda g: f"this game declares `board: {_board_spelling(g)}`",
    lambda g: "declare a board that holds it",
    clause="board",
    role="beside",
)
_RANK_PARAMETER_GATE = _ClauseGate(
    _rank_parameters,
    lambda g: not _declares_ranking(g),
    "declares",
    "enumerate the game's ranking",
    lambda g: _NO_RANKING,
    lambda g: "declare one",
    clause="ranking",
    role="engine_read",
)
_RANKING_SLOT_GATE = _ClauseGate(
    _ranking_slots,
    lambda g: not _declares_ranking(g),
    "writes",
    "read a card's rank strength from `ranking:`",
    lambda g: _NO_RANKING,
    lambda g: "declare one",
    clause="ranking",
    role="engine_read",
)


def _board_spelling(game: n.Game) -> str:
    board = game.board
    if board is None:
        return "none"
    return board_spelling(board.family, board.args)


# What each need is to a designer: the part of a board a verb reads.
_BOARD_NEED_PHRASES: dict[BoardNeed, str] = {
    "lines": "the board's lines",
    "edges": "the board's declared adjacency (which points it joins)",
    "frame": "the board's movement frame (the directions each seat moves along)",
    "borders": "each seat's two borders (the board edges it joins)",
}


def _answered_verbs(entry: BoardEntry) -> str:
    """The board verbs `entry` answers, as a refusal lists them."""
    verbs = sorted(v for v, need in BOARD_VERB_NEEDS.items() if entry.answers(need))
    if not verbs:
        return "no board verb"
    if len(verbs) == 1:
        return f"`{verbs[0]}`"
    return ", ".join(f"`{v}`" for v in verbs[:-1]) + f" or `{verbs[-1]}`"


def _board_need_gate(need: BoardNeed) -> _ClauseGate:
    """The row refusing every board verb that reads `need` on a board whose
    family does not declare it -- asked of the game's own call by
    `_check_board_call` and of a library's on its `uses` line."""

    def unmet(g: n.Game) -> bool:
        entry = _declared_board(g)
        return entry is not None and not entry.answers(need)

    def lacks(g: n.Game) -> str:
        # Asked only where `unmet` held, so the entry stands.
        entry = _declared_board(g)
        answered = _answered_verbs(entry) if entry is not None else "no board verb"
        return (
            f"`board: {_board_spelling(g)}` has none — on this board a game may "
            f"call {answered}"
        )

    return _builtin_gate(
        frozenset(v for v, n_ in BOARD_VERB_NEEDS.items() if n_ == need),
        unmet,
        "read " + _BOARD_NEED_PHRASES[need],
        lacks,
        lambda g: "declare a board that has one, or use a library written for this board",
        clause="board",
        role="beside",
    )


# One row per need, in `BOARD_NEEDS` order: a verb's refusal on a board that
# does not declare what it reads.
_BOARD_NEED_GATES: tuple[_ClauseGate, ...] = tuple(_board_need_gate(need) for need in BOARD_NEEDS)


# Why a seat verb needs exactly two seats, by the part it reads, in the
# designer's words. Keyed by every need a seat verb reads: a seat verb reading
# a need with no reason here fails at import, building `_SEAT_GATES`.
_SEAT_NEED_REASONS: dict[BoardNeed, str] = {
    "frame": (
        "the board's movement frame, which faces two seats against each other "
        "(one seat's forward is the other's backward)"
    ),
    "borders": "a seat's own two edges of the board, which the board gives to two seats",
}


def _seat_gate(need: BoardNeed) -> _ClauseGate:
    """The row refusing every seat verb that reads `need` in a game without
    exactly two seats -- asked of the game's own call by `_check_board_call`
    and of a library's on its `uses` line."""
    return _builtin_gate(
        frozenset(v for v in _SEAT_CALL_FUNCS if BOARD_VERB_NEEDS[v] == need),
        lambda g: g.board is not None and g.players.count != 2,
        "read " + _SEAT_NEED_REASONS[need],
        lambda g: f"this game declares `players: {g.players.count}`",
        lambda g: "declare `players: 2`",
        clause="players",
        role="beside",
    )


# One row per need a seat verb reads, in `BOARD_NEEDS` order.
_SEAT_GATES: tuple[_ClauseGate, ...] = tuple(
    _seat_gate(need)
    for need in BOARD_NEEDS
    if any(BOARD_VERB_NEEDS[v] == need for v in _SEAT_CALL_FUNCS)
)


# Every gate on a construct's legality that a game clause decides, in the order
# the gates themselves run, so a construct two gates refuse is reported by the
# one that refuses it when the game writes it (the content flavor first: in a
# piece game a `Rank` parameter's fix is not a `ranking:`, which a piece game
# cannot declare). Each row's test is the one its gate asks, so a construct
# joining a gate joins its row, and a new clause gate is a new row;
# `_check_library_clause_gates` reads the table and names no gate. That each
# row agrees with its gate, member by member, is executed in
# tests/test_library_clause_gates.py.
_CLAUSE_GATES: tuple[_ClauseGate, ...] = (
    _builtin_gate(
        DECK_ONLY_CALL_FUNCS,
        lambda g: g.content_flavor == "piece",
        "read a card's suit, rank or points",
        lambda g: _PIECES_LACK,
        lambda g: _PIECES_FIX,
        clause="deck",
        role="engine_read",
    ),
    _CARD_CONTENT_GATE,
    _builtin_gate(
        _TRICK_ORDER_READERS,
        lambda g: not K.has_trick_order(g),
        "read the game's Trick Order",
        lambda g: "this game declares none",
        lambda g: _ANSWER_IS_TRUMP,
        clause="trick_order",
        role="reader",
    ),
    _TRICK_ORDER_READING_GATE,
    _builtin_gate(
        TRICK_ORDER_EXCLUDED_FUNCS,
        lambda g: K.has_trick_order(g),
        "read the trump and led suit a trick round names",
        lambda g: "this game declares a Trick Order, which replaces them",
        _trick_order_fix,
        clause="trick_order",
        role="beside",
    ),
    _TRICK_ORDER_REPLACED_GATE,
    _builtin_gate(
        _CARD_POINTS_CALLS,
        lambda g: K.answer(g, "card_points") is None,
        "read the game's card points",
        lambda g: "this game declares none",
        _card_points_fix,
        clause="card_points",
        role="reader",
    ),
    _builtin_gate(
        _SUIT_RANKING_CALLS,
        lambda g: g.suit_ranking is None,
        "read a suit's strength from `suit ranking:`",
        lambda g: "this game declares no `suit ranking:`",
        lambda g: "declare one, naming the deck's suits strongest first",
        clause="suit_ranking",
        role="reader",
    ),
    _builtin_gate(
        _TEAM_CALL_FUNCS,
        lambda g: not g.teams,
        "ask which team a seat is on",
        lambda g: _NO_TEAMS,
        _teams_fix,
        clause="teams",
        role="engine_read",
    ),
    _TEAM_RANGE_GATE,
    _TEAM_STATE_GATE,
    _builtin_gate(
        BOARD_ONLY_CALL_FUNCS,
        lambda g: g.board is None,
        "read the board",
        lambda g: "this game declares no `board:`",
        _board_fix,
        clause="board",
        role="engine_read",
    ),
    _CELL_RANGE_GATE,
    _BOARD_POSITION_GATE,
    *_BOARD_NEED_GATES,
    *_SEAT_GATES,
    _builtin_gate(
        RANKING_GATED_FUNCS,
        lambda g: not _declares_ranking(g),
        "read a card's rank strength from `ranking:`",
        lambda g: _NO_RANKING,
        lambda g: "declare one",
        clause="ranking",
        role="engine_read",
    ),
    _RANK_PARAMETER_GATE,
    _RANKING_SLOT_GATE,
)

# The Builtins no game clause gates. Listed, not derived by subtraction, so a
# newly registered Builtin lands in neither this set nor a `_CLAUSE_GATES` row
# and the partition pin names it, rather than passing silently as clause-free.
_CLAUSE_FREE_BUILTINS: frozenset[str] = frozenset(
    {"bottom_of", "error", "player_holding", "top_of"}
)


def _activated_rule_names(game: n.Game) -> frozenset[str]:
    """The rules the game's `active_rules:` switches on, the only library rules
    the splice brings in (`_instantiate_rules`)."""
    return frozenset(
        ref.name
        for nd in _walk(game)
        if isinstance(nd, n.ActiveRules)
        for ref in nd.refs
        if ref.delta in ("plain", "add")
    )


# Why each REACHABLE reference namespace is not swept here. Rows exist only for
# namespaces a library's own text can actually name: an excuse for something
# unreachable excuses nothing, and a table holding those cannot be pinned in the
# deleting direction — `test_every_reachable_reference_namespace_is_swept_or_
# excused` would stay green with the row gone, which makes the row read as a
# guarantee it never was. (The unreachable namespaces are `rule`, `game`,
# `library`, `component_set`, `board_family`, `zone_type`, `zone_type_arg` and
# `param`, each because its clause — `active_rules:`, `zones { }`, `cards:`,
# `board:`, `uses`, `primitives { }` — is a GAME clause the library grammar has
# no production for.)
#
# Three shapes of reason, and they are not interchangeable. CLOSED: the
# namespace is the same for a library as for a game, so no importing game can
# feed it. GUARDED ELSEWHERE: the name IS game-fed, and another pass refuses it —
# the row must then say WHICH pass, because "something catches it" is how a
# reason becomes untrue without anyone noticing. DESIGNED: nothing checks the
# name anywhere, by a recorded decision.
#
# Every reason below was PROBED through the full pipeline, not reasoned: a case
# `resolve` alone accepts is often refused a stage later, and the pass a
# guarded-elsewhere row names is the one the probe found refusing it.
_LIBRARY_UNSWEPT: dict[str, str] = {
    "kernel_move_type": "closed: `LIBRARY_MOVE_TYPES`, identical for a library and a game",
    "primitive_query": (
        "guarded elsewhere: a Primitive the slot's registry "
        "(`_ROUND_QUERY_REGISTRIES`) holds is refused to the library's author by "
        "`_round_slot_primitives`, since a Primitive is one game's own; any other "
        "name outside that registry is refused by `_validate_refs`'s round arms "
        "after the splice, at the library's span — the registries are the same for "
        "every importing game, so no game can feed the slot a name"
    ),
    "climb_lead": (
        "guarded elsewhere: a registered lead query is refused to the library's "
        "author by `_round_slot_primitives`; a name nothing declares by "
        "`_resolve_climb_engines` after the splice, at the library's span; and "
        "the importing game's own catalogue, the one name a game feeds the slot, "
        "by `_resolve_climb_engines`'s library-origin arm"
    ),
    "climb_follows": (
        "guarded elsewhere: a registered follows query is refused by "
        "`_round_slot_primitives`; a game function is followed by only beside a "
        "catalogue, which a library's round may not name "
        "(`_resolve_climb_engines`'s library-origin arm)"
    ),
    "round_state": (
        "closed: `ROUND_STATE_FIELDS`, the fields a round publishes, identical for a "
        "library and a game; typecheck refuses any other `state.` field"
    ),
    "index_domain": (
        "guarded elsewhere, and NOT closed — the row's earlier reading claimed the "
        "namespace was closed because a game may not declare a non-role index "
        "either. Zone contracts falsified that: a game DOES declare "
        "position-indexed zone families (Klondike's `tableau_down[column]`), so a "
        "contract could name a position domain the importing game alone declares. "
        "`_check_require_indexes` refuses it, to the library's author, for a "
        "requirement and for a provided variable alike"
    ),
    "role": (
        "guarded elsewhere, and NOT closed. The role NAMES are the domain registry's, "
        "but `suit`/`rank` admissibility follows the importing game's component set: "
        "`for each suit` is accepted by a card game and refused by a piece game. So "
        "this is deck-agnosticism escaping through a role, the same property "
        "`deck_rank`/`deck_suit` are swept for. It is not silent — `_validate_refs` "
        "refuses it at the library's span — but the library-alone property is weaker "
        "here than the sweep provides (issue #183)"
    ),
    "content_kind": (
        "guarded elsewhere: typecheck compares the item noun against the game's content "
        "flavor and reports to the library's author. NOT, as this row first claimed, "
        "because a movement always names a zone the classified pass refuses — that "
        "premise is now doubly false, since a movement may also name a CONTRACTED "
        "zone; re-probed with an unknown noun and with a flavor-wrong one, both "
        "refused to the library's author (issue #170)"
    ),
    "outcome_tag": (
        "guarded elsewhere: a `produce` outside an outcome-phase body is refused "
        "outright, and a library holds no phase — so every library `produce` is "
        "refused to the library's author (probed via the full "
        "pipeline; `resolve` alone accepts them, which is what made the first reading "
        "of this row say the tags were merely `owned` by a swept name)"
    ),
    "field": (
        "designed: `x.field` on anything but the `state` pronoun is a field of that "
        "object's type, and the pronoun namespaces' fields are `TAny` by decision "
        "(decisions.md, the `action` trap) — so there is nothing to check rather than "
        "something owned elsewhere"
    ),
}


# The board verbs that return a positional collection, each the `BoardEntry`
# method of the same name (pinned by tests/test_positional_index.py): the
# lengths `_static_length` reads off the declared board.
_REGION_CALL_FUNCS = frozenset(
    fn
    for fn, ret in ((fn, CALL_SIGS[fn].ret) for fn in BOARD_ONLY_CALL_FUNCS)
    if isinstance(ret, TCollection) and ret.key is None
)


def _static_length(obj: n.Expr, game: n.Game) -> int | None:
    """How many members a positional collection holds, where the sentence
    states it: a `[...]` list's own count, or a board region on the declared
    board. A region whose argument the sentence does not fix answers the
    largest count over every argument the board admits -- each seat for a
    per-seat region, each cell for a cell's region (`neighbors(c)`, the
    board's largest degree), each declared length for `lines(k)` with a
    computed `k` -- so a position some argument holds is never refused. None
    where the count is runtime data."""
    if isinstance(obj, n.ListLit):
        return len(obj.elements)
    if not (isinstance(obj, n.Call) and obj.func in _REGION_CALL_FUNCS):
        return None
    if game.board is None or len(obj.args) != 1:
        return None
    try:
        entry = board_entry(game.board.family, game.board.args)
        method = getattr(entry, obj.func)
        param = CALL_SIGS[obj.func].params[0]
        arg = obj.args[0]
        admitted: tuple[object, ...]
        if isinstance(param, TPlayer):
            admitted = tuple(range(game.players.count))
        elif isinstance(param, TCell):
            admitted = entry.cells
        elif isinstance(param, TInteger):
            admitted = (arg.value,) if isinstance(arg, n.IntLit) else entry.line_lengths
        else:
            return None
        return max((len(method(a)) for a in admitted), default=None)
    except (OwnerGuardError, ValueError):
        # Refused where it is written: an invalid `board:` clause
        # (`_resolve_board`), or the call itself (`_check_board_call`, the
        # frame's two-seat guard). There is no region to count.
        return None


def _position_past_end(node: object, game: n.Game) -> tuple[int, int] | None:
    """(position, length) for a literal position past the end of a collection
    whose length the sentence states (`_static_length`), else None. The one
    test `_check_positional_index_range` asks, and, for a board region,
    `_BOARD_POSITION_GATE`'s."""
    if not (isinstance(node, n.Subscript) and isinstance(node.index, n.IntLit)):
        return None
    length = _static_length(node.obj, game)
    if length is None or node.index.value < length:
        return None
    return node.index.value, length
    # Move parameters are deliberately NOT checked here: `_check_move_params`
    # already owns them with a stricter, better-worded gate (it names the legal
    # domains, including the game's declared position domains). Its gap was
    # REACH, not strength — it ran only for a move an offering enumerates —
    # and the fix is to run it for every declared move type, at its own call
    # site, rather than to shadow it with a second diagnostic in a different
    # channel (two messages for one defect is noise).


# The closed set of procedure-parameter domains (decisions.md "Named
# procedures"), corpus-first. Unlike a move parameter, a procedure argument is
# an arbitrary expression rather than a value the action space must enumerate,
# so this set gates what an argument may *denote*, not what can be enumerated —
# which is why it is a separate registry from `_FIXED_DOMAINS` below and not a
# slice of it. `Zone` is deliberately absent: the design note guessed the corpus
# would need it, and the corpus disagreed (Coup's blocks reach their zones by
# indexing a zone family with the player parameter — `influence[victim]` — so a
# Player parameter already carries the zone). Recorded in issue #134; extend
# when a game forces it.
#
# `Rank?` and not `Rank`: Coup's proven-claim swap is called both with a literal
# character (`run prove_claim(actor, Duke)`) and with the block claim, which is a
# `Rank?` because "no block" is a real state. The call sites all sit inside `if
# block_claim is not none`, but the language has no flow narrowing, so a bare
# `Rank` parameter would reject the very argument the block sites must pass. A
# `Rank?` parameter accepts both (`coercible(Rank, Rank?)`), which is why the
# optional form is the one the corpus forces. Bare `Rank` rides along: it is the
# same domain minus the null, meaningful on its own, and free to support.
#
# `Integer` is forced by poker_betting's `betting_street(big_size)`: Stud's
# fourth street computes its big size from the cards showing. It strains
# nothing — an argument is an expression the caller evaluates once, not a value
# the action space enumerates, and `function` parameters take Integer too.
#
# `Positive` is forced by the same procedure's `bet_size`: a street played at a
# size of 0 offers a free bet, and one at a negative size pays the bettor, so
# no rulebook reads either. A procedure argument is evaluated once the body is
# spliced, past every check, so the domain is held where it can be decided:
# the `run` site admits a written number of 1 or more and nothing else
# (`_check_positive_arguments`).
_PROCEDURE_PARAM_DOMAINS = frozenset({"Player", "Rank", "Rank?", "Integer", POSITIVE_PARAM_DOMAIN})
