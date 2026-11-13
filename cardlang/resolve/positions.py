"""Resolve step: position domains and the board's minted domains.

Contract (decisions.md "Closed-domain completeness", write-time triage)
-----------------------------------------------------------------------
Assumes:      one flat game, its declarations checked.
Establishes:  the declared position domains are valid, and the board's
              `cell` and direction domains are minted into
              ``game.positions``; this is the one minting site, so from here
              ``game.positions`` is the union. No name declared or minted at
              any of the sites in ``RESERVATION_SITES`` takes a spelling one of
              ``POSITION_NAME_SOURCES`` already holds.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, replace
from cardlang.diagnostic_codes import Code
from cardlang.ast import nodes as n
from cardlang.board_domains import LINE_NOUN, BOARD_DOMAIN, DIRECTION_DOMAIN, board_directions
from cardlang.primitives_block import COLLECTION_TYPE_CONSTRUCTOR
from cardlang.diagnostics import DiagnosticBag, SlotKind, Unless
from cardlang.domains import SIMULTANEOUS_ROLES, ZONE_INDEX_ROLES, role_names
from cardlang.domains import ITERABLE_ROLES as _ITERATION_ROLES
from cardlang.stdlib.boards import BoardEntry, BoardRefusal, board_entry
from cardlang.stdlib.zones import LIBRARY_ZONE_TYPES
from cardlang.typecheck import KNOWN_TYPE_NAMES, POSITIVE_PARAM_DOMAIN
from cardlang.resolve.declared import _tell_board_refusal


def step(game: n.Game, bag: DiagnosticBag) -> tuple[n.Game, frozenset[str]]:
    """The positions step. Returns the game with the board's domains minted
    into `game.positions`, and the name of every position domain, declared
    and minted."""
    position_names = _resolve_positions(game, bag)
    # The board mints its `cell` domain into `game.positions` (after the
    # declared positions are validated, so the collision Owner Guard reads the
    # pre-injection names); from here `game.positions` is the union and
    # `position_names` names both kinds for the zone-index and move-parameter
    # checks below.
    game = _resolve_board(game, bag, position_names)
    return game, frozenset(p.name for p in game.positions)


# The bound on a declared position domain's member count: a Suit-sized or
# column-sized layout is orders of magnitude below it, and a cross-product of
# two runaway domains would otherwise silently explode the OpenSpiel
# offering block (every member pair mints an action id). No physical
# tabletop layout approaches it.
_POSITION_MEMBER_CEILING = 256


# The sites that reserve a name against the sources below: every place a
# spelling enters a namespace the sources also name — the author's
# `positions { }` block and the two domains a `board:` clause mints. Named here so the set can
# be enumerated — the sources' accumulation is one axis of this guard, and its
# consumers are the other; tests/test_positions.py crosses them and scrapes the
# call sites, so a consumer cannot join in silence any more than a source can.
DECLARED_POSITION_SITE = "declared"
MINTED_CELL_SITE = "board-minted cell"
MINTED_DIRECTION_SITE = "board-minted dir"
RESERVATION_SITES: tuple[str, ...] = (
    DECLARED_POSITION_SITE,
    MINTED_CELL_SITE,
    MINTED_DIRECTION_SITE,
)


@dataclass(frozen=True)
class ReservedNameSource:
    """One namespace a name minted into the type namespace is reserved against.

    The registry below is the AXIS of the reservation. Its domain is "every
    namespace whose names a position domain must not collide with", and that
    domain accumulates: each construct that mints names into a namespace of
    its own (zone types, collection nouns, the constructor word) is one more
    source. An inline union of sources has nothing to enumerate, so a sweep
    built on one can derive from every source it already knows and stay blind
    to the next. A table can be iterated: by the guard below, by the diagnostic
    that names which source matched, and by the grid in tests/test_positions.py
    that crosses the sources against `RESERVATION_SITES` — so a source added
    here reaches every site and every cell without a second edit.

    `names` takes the game because the sources are not homogeneous: some are
    static registries, fixed for every game, and one depends on whether the
    game declares a board. A source that ignores the argument is answering "the same
    names for every game", which is a fact about that source, not a reason to
    split the table.

    A source that reserves a name only under some condition expresses that in
    `names` — an empty answer for a game where the ambiguity cannot arise —
    rather than by being consulted at some sites and not others. Every
    reservation site asks every source, so a new site inherits the whole
    registry and a new source reaches every site.
    """

    label: str
    names: Callable[[n.Game], frozenset[str]]


#: Every namespace a position domain's name is reserved against.
#: ORDERED: `_reserved_domain_source` reports the first match, so a spelling
#: reachable from two sources names one of them deterministically.
POSITION_NAME_SOURCES: tuple[ReservedNameSource, ...] = (
    ReservedNameSource(
        "a built-in domain id",
        lambda game: frozenset(
            role_names(_ITERATION_ROLES | SIMULTANEOUS_ROLES | ZONE_INDEX_ROLES)
        ),
    ),
    ReservedNameSource("a built-in type name", lambda game: KNOWN_TYPE_NAMES),
    ReservedNameSource("a zone type", lambda game: frozenset(LIBRARY_ZONE_TYPES)),
    # The word an entry's collection spelling is written with. It is a NAME,
    # not a keyword — the grammar cannot tell it from any other head — so the
    # reservation is what keeps `x : Collection<Card>` from reading two ways in
    # a game that declares its own `Collection`. Held disjoint from the two
    # registries beside it, so the constructor cannot become a third spelling
    # of a type either registry already names.
    ReservedNameSource(
        "a collection type constructor",
        lambda game: frozenset({COLLECTION_TYPE_CONSTRUCTOR}),
    ),
    # A procedure parameter written `Positive` takes a written number of 1 or
    # more; a position domain of that name would make the same parameter
    # spelling read as the declared range at every other host.
    ReservedNameSource(
        "a procedure parameter domain",
        lambda game: frozenset({POSITIVE_PARAM_DOMAIN}),
    ),
    # The collection noun, found by crossing the sources against the slots that
    # read them. `DomainQuery.binder` carries ONE name resolved against two
    # namespaces, and the optional `in <collection>` clause is what picks: bare
    # reads `game.positions`, the collection form also the board's `line`. So
    # in a board game `positions { line : 1..3 }` turns `any line where ...` —
    # rejected in every other board game, with a diagnostic pointing at the
    # collection form — into an accepted quantifier over the declared integer
    # domain, while `any line in lines(3)` in the SAME game still means board
    # lines. One spelling, two meanings, no diagnostic.
    #
    # Two derived narrowings, each closing what would otherwise be an
    # over-reservation the corpus refutes:
    #  * BOARD GAMES ONLY. The collection form needs a `TLine`, which only
    #    `lines(k)` produces and which is board-only, so in a boardless game
    #    the noun has exactly one meaning and reserving it would take a name
    #    nothing else can claim.
    #  * The line noun alone. A position domain is a collection noun by being
    #    one (`all cells in <line>` iterates the minted `cell`'s members), so
    #    only the board's `line`, no position domain, is reserved. FreeCell's
    #    `positions { cell : 1..4 }` — boardless — stays legal.
    ReservedNameSource(
        "a collection noun",
        lambda game: frozenset({LINE_NOUN}) if game.board is not None else frozenset(),
    ),
)


def _reserved_domain_source(game: n.Game, name: str, site: str) -> str | None:
    """The label of the first source reserving `name`, or None if it is free.

    The diagnostic says WHICH namespace a name was already taken from rather
    than listing the namespaces it might have come from: a message that
    enumerates the sources in prose goes stale the moment the registry above
    grows, and a stale enumeration reads exactly like a fresh one.

    `site` does not select sources — every site asks the whole registry, and a
    source that reserves conditionally says so in its own `names`. It is taken
    so each call NAMES which reservation it is, which is what lets
    tests/test_positions.py derive the consumer axis from the calls instead of
    from a list someone has to remember to extend.
    """
    assert site in RESERVATION_SITES, f"unknown reservation site {site!r}"
    for source in POSITION_NAME_SOURCES:
        if name in source.names(game):
            return source.label
    return None


def _resolve_positions(game: n.Game, bag: DiagnosticBag) -> frozenset[str]:
    """Validate the `positions { }` block (decisions.md "Position domains and
    positional zones"): static, non-empty, bounded ranges, and names reserved
    against every namespace in `POSITION_NAME_SOURCES` — the reconciliation
    between a definition site the author owns and the ones the kernel owns is
    rejection, so a lookup that consults positions first can never shadow a
    kernel row. Duplicates are rejected by `_check_duplicate_names`, with every
    other declaration namespace. Returns the declared names for the consumers
    (zone indexes, move parameters, the bare-reference Owner Guard).

    AUTHOR-DECLARED entries only. A re-resolve of an already-resolved game
    sees the board's minted `cell` beside them (`_resolve_board` appends it to
    `game.positions`), and the mint is not a declaration: its bounds are
    unread, and the kernel is entitled to its own spellings — the two guards in
    `_resolve_board` are what reconcile a minted name, at their own sites.

    The member ceiling is not lost by that skip. A minted domain's member count
    is bounded where the mint is: `board_entry` refuses a family argument
    outside its declared range, so the widest board a designer can write mints
    no more cells than `_POSITION_MEMBER_CEILING` admits. That is an agreement
    between two registries rather than one rule, so it is crossed rather than
    assumed — tests/test_positions.py."""
    for p in (p for p in game.positions if p.members_named is None):
        if p.lo > p.hi:
            bag.error(
                f"position domain '{p.name}' declares an empty range "
                f"{p.lo}..{p.hi} — the bounds are inclusive and must satisfy "
                f"lo <= hi",
                p.span,
                code=Code.OUT_OF_RANGE,
            )
        elif p.hi - p.lo + 1 > _POSITION_MEMBER_CEILING:
            bag.error(
                f"position domain '{p.name}' declares {p.hi - p.lo + 1} "
                f"members — more than the ceiling "
                f"({_POSITION_MEMBER_CEILING}); every member mints action-"
                f"space ids, so a runaway range is a declaration error",
                p.span,
                code=Code.OUT_OF_RANGE,
            )
        source = _reserved_domain_source(game, p.name, DECLARED_POSITION_SITE)
        if source is not None:
            bag.error(
                f"position domain '{p.name}' collides with {source} — "
                f"pick another name",
                p.span,
                code=Code.NAME_TAKEN,
            )
    return frozenset(p.name for p in game.positions)


def _resolve_board(
    game: n.Game, bag: DiagnosticBag, declared_positions: frozenset[str]
) -> n.Game:
    """Validate the `board:` clause and mint its `cell` position domain
    (decisions.md "Boards and cells"). A board mints one named-member domain
    (`cell`) whose members are the board's cells; it rides the `positions { }`
    substrate, so the minted domain is injected into `game.positions` as a
    named-member `PositionDecl` and thereafter flows through every surface the
    integer position domains flow through (zone index, move parameter, unowned
    projection, action space, IR).

    Returns the game unchanged when there is no board, or with the minted
    domain appended; every rejection path returns without minting (the game is
    left boardless downstream, so a single mistake yields a single
    diagnostic)."""
    if game.board is None:
        return game
    # Idempotency: a re-resolve of an already-resolved game sees the MINTED
    # `cell` domain (a named-member PositionDecl, `members_named` set) and must
    # neither re-mint it nor misread it as a user collision. A user-DECLARED
    # `cell` (integer range, `members_named is None`) is not this case — it is
    # the collision the Owner Guard below reports.
    if any(
        p.name == BOARD_DOMAIN and p.members_named is not None for p in game.positions
    ):
        return game
    # `board:` requires `pieces:`. Parse enforces cards XOR pieces, so a
    # non-piece flavor here is exactly a card game — the `board: + cards:`
    # rejection and the `board: without pieces:` one are the same Owner Guard (no game
    # has witnessed needing a board on a card deck).
    if game.content_flavor != "piece":
        bag.error(
            f"game '{game.name}' declares `board:` but not `pieces:` — a board "
            f"lays out piece positions and is only valid alongside `pieces:` "
            f"(a card game with a board is rejected until a game witnesses "
            f"needing both)",
            game.board.span,
            code=Code.MISSING_DECLARATION,
            unless=Unless(SlotKind.CONTENT_KIND, frozenset({"piece"})),
        )
        return game
    # Collision: the minted `cell` may shadow neither a declared `positions { }`
    # name (name both sites) nor a built-in spelling (the standing Owner Guard, reused
    # so a future built-in named `cell` cannot land silently). `declared_positions`
    # names only the user's declared domains (this runs right after
    # `_resolve_positions`, before the mint below appends to `game.positions`).
    if BOARD_DOMAIN in declared_positions:
        bag.error(
            f"the board mints a position domain named '{BOARD_DOMAIN}', which "
            f"collides with the declared `positions {{ {BOARD_DOMAIN} : ... }}` "
            f"— rename the declared domain (a board already provides '{BOARD_DOMAIN}')",
            game.board.span,
            code=Code.NAME_TAKEN,
        )
        return game
    minted_clash = _reserved_domain_source(game, BOARD_DOMAIN, MINTED_CELL_SITE)
    if minted_clash is not None:
        bag.error(
            f"the board mints a position domain named '{BOARD_DOMAIN}', which "
            f"collides with {minted_clash}",
            game.board.span,
            code=Code.NAME_TAKEN,
        )
        return game
    # Family/args validity is the registry's to judge: `board_entry` raises a
    # BoardRefusal naming the violated bound (unknown family, wrong arity,
    # out-of-bounds arg), which becomes a diagnostic at the clause span, told
    # after the `dir` checks below. Narrow BY TYPE, not by `ValueError`: the
    # same call builds a `BoardEntry`, whose `__post_init__` pins the
    # registry's own output. Those address the engine maintainer, and a
    # `ValueError` catch would turn each into a diagnostic on the designer's
    # `board:` line — an engine bug presenting as a compile error on a correct
    # game.
    entry: BoardEntry | None
    refused: BoardRefusal | None = None
    try:
        entry = board_entry(game.board.family, game.board.args)
    except BoardRefusal as exc:
        entry, refused = None, exc
    # A board whose family has a movement frame mints a SECOND domain, `dir`
    # (the movement directions), as a separate source (`directions_of`) rather
    # than a `game.positions` entry; a frameless board (`morris9`) mints none,
    # and a declared `positions { dir : ... }` beside it is an ordinary
    # domain. A board the registry refuses is judged as though it mints `dir`.
    # A declared `dir` clashes with a minted one -- the `cell` collision's
    # twin. No early return: unlike a `cell` clash, a declared `dir` does not
    # block minting `cell` (they are different names), so the error is
    # emitted and cell minting proceeds; the bag halts the pipeline either way.
    mints_directions = entry is None or bool(board_directions(entry))
    if mints_directions and DIRECTION_DOMAIN in declared_positions:
        bag.error(
            f"the board mints a movement-direction domain named "
            f"'{DIRECTION_DOMAIN}', which collides with the declared "
            f"`positions {{ {DIRECTION_DOMAIN} : ... }}` — rename the declared "
            f"domain (a board already provides '{DIRECTION_DOMAIN}')",
            game.board.span,
            code=Code.NAME_TAKEN,
        )
    # The `cell` clash above is checked against BOTH declared positions and the
    # reserved set; `dir` gets the same second check, so every name the board
    # mints is refused against the same sources.
    direction_clash = (
        _reserved_domain_source(game, DIRECTION_DOMAIN, MINTED_DIRECTION_SITE)
        if mints_directions
        else None
    )
    if direction_clash is not None:
        bag.error(
            f"the board mints a movement-direction domain named "
            f"'{DIRECTION_DOMAIN}', which collides with {direction_clash} — "
            f"rename the declared type (a board already provides "
            f"'{DIRECTION_DOMAIN}')",
            game.board.span,
            code=Code.NAME_TAKEN,
        )
    if entry is None:
        assert refused is not None
        _tell_board_refusal(refused, game.board.family, game.board.span, bag)
        return game
    # `lo`/`hi` are unread for a named-member domain (`.members` returns
    # `members_named`); they carry the member count so the struct stays
    # internally consistent if ever inspected.
    minted = n.PositionDecl(
        name=BOARD_DOMAIN,
        lo=0,
        hi=len(entry.cells) - 1,
        members_named=entry.cells,
        span=game.board.span,
    )
    return replace(game, positions=game.positions + (minted,))
