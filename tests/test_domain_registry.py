"""The quantifiable-domain registry: the domain x form MATRIX.

Every row of `cardlang.domains.DOMAINS` crossed with every form that ranges over
a domain — the quantifiers, `for each`, `each … simultaneously`, and the
move-parameter/action-space surface. Each cell is either GREEN (accepted, and
for `for each` its actorhood matches the row's `binds_actor` column) or a
declared WALL with its diagnostic. The matrix is DERIVED from the registry, not
hand-listed: a new row (or a new column value on an existing row) is a new set
of cells that this module forces someone to classify.

The defect class this exists to close (docs/decisions.md, "Closed-domain
completeness"): four domains defined in two half-tables under two key
namespaces — `roles.ROLES` (lowercase, gating `for each` and binder typing) and
`mechanics.enumerate_domain` (capitalised, gating move parameters) — with
nothing relating `player` to `Player`. Neither table knows the other's columns, so
"what is `team` legal in?" has no single answer, and the seat/value asymmetry
(`for each player` rebinds the actor; `for each suit` does not) lives as an if-chain
in `execute._for_each` rather than as a fact of the table.

Completeness ledger
--------------------
    property:   Each registry row's column values are TRUE OF THE ENGINE, at
                every layer that consumes them — a row that says `iterable` is
                iterable, a row that says `binds_actor` really rebinds
                `ctx.acting_as` when iterated, a row that says NOT `simultaneous`
                is walled loudly out of `each … simultaneously`, and a row's
                `param_domains` are exactly the move-parameter spellings the
                checker admits and the action space enumerates. No column may be
                a claim the code does not honour, and no form may be reachable
                for a row whose column denies it.

    domain:     Two axes, each derived from its own registry in code, never from
                the implementation's coverage:
                  A. domain rows — `cardlang.domains.DOMAINS` (4 rows today).
                  B. forms that range over a domain — enumerated from the GRAMMAR
                     (cardlang/grammar/cardlang.lark), not from the registry:
                     the 8 `quantifier` productions (`any`/`all` x 4 nouns), the
                     `for_each` production, the `each_simultaneous` production,
                     and the `move_param` type slot.
                Axis B is crossed with the declared-type spelling x {plain,
                optional} for the move-parameter cells (8 spellings), so the
                optional forms no row admits (`Player?`, `Rank?`, `Team?`) are
                cells that must be REJECTED, not cells that go unmentioned.

    registry:   A. `cardlang.domains.DOMAINS` (rows + columns)
                B. `cardlang/grammar/cardlang.lark` — `quantifier`, `for_each`,
                   `each_simultaneous`, `move_param`

    covered:    Exhaustive over A x B — 4 rows x (2 quantifier forms + `for each`
                + `each … simultaneously` + 2 move-param spellings) = 24 cells,
                every one executed as a probe below, plus:
                  - quantifier: all 8 productions accepted (`test_every_row_is_
                    quantifiable`), and each row's BINDER TYPE witnessed by a
                    cross-typed predicate that must be walled by the type layer
                    (`test_a_quantifier_binder_types_as_its_rows_binder_type`) —
                    a binder typed `TAny` would let those through.
                  - `for each`: accepted for every `iterable` row, and ACTORHOOD
                    checked at runtime against `binds_actor` for every row
                    (`test_for_each_binds_the_actor_iff_the_row_is_a_seat_domain`)
                    — the seat/value asymmetry is checked as data, not asserted.
                  - `each … simultaneously`: accepted for the `simultaneous` row,
                    walled with "simultaneous moves are per player" for the other
                    three. The wall message itself is derived from the column.
                  - move params: the 8 declared-type spellings — `Player`, `Suit`,
                    `Suit?`, `Rank` accepted; `Player?`, `Team`, `Team?`, `Rank?`
                    walled with "unsupported parameter domain". Plus `Card` (the
                    documented non-row outlier, accepted), an unknown type name,
                    and `Integer` (deferred), each walled.
                  - the rank divergence: `for each rank` is legal with no
                    `ranking:` (it iterates deck order) while a `Rank` PARAM in
                    the same game is walled — the two member columns really are
                    two columns (`test_the_rank_rows_two_member_columns_diverge`).
                Non-row nouns (`for each color`, `each color simultaneously`) are
                walled — the registry is closed, not open.

    sampled:    Member ORDER is pinned by example, not exhaustively: the corpus
                goldens (tests/test_migration_characterization.py) hold every
                iteration order fixed byte-for-byte across the corpus, which is a
                stronger witness than a synthetic matrix but is not a per-row
                enumeration. `role_members` non-emptiness per row is pinned in
                tests/test_role_registry.py.

    residual:   1. THE GRAMMAR SURFACE DOES NOT LIGHT UP FROM A NEW ROW. The
                   claim "a new domain registers itself and arrives with its full
                   column green" is TRUE for the semantic layers — binder typing,
                   iteration, actorhood, member enumeration, and the
                   move-param/action-space domains all read the table — and NOT
                   YET TRUE for the grammar surface. `cardlang.lark` still
                   hardcodes 8 quantifier productions (`any player where` / `all
                   suits where` / …) and the player/card query families as literal
                   nouns, so a 5th row would type, iterate, bind and enumerate
                   correctly but would have NO `any <noun> where` production and
                   would be a syntax error at the quantifier surface. That is a
                   loud wall (a parse error naming the unknown noun), not a silent
                   acceptance, so it is a residual and not a defect — but it is
                   the honest limit of the registry today. Recorded in
                   docs/roadmap.md ("Quantifier productions are not registry-
                   derived").
                2. `each player simultaneously` accepts a body that is not a
                   `chosen` movement (`marker[0] += 1`, or a plain `move one card
                   …`), then dies on a BARE ASSERT in `execute._pass_selection`.
                   Pre-existing, and on the form's BODY axis rather than this
                   module's domain axis — the domain gate is total; the body gate
                   is missing. Wrong failure currency (a bare assert, not a
                   diagnostic). Recorded in docs/roadmap.md ("`each …
                   simultaneously` body shape is unchecked").
"""

from __future__ import annotations

import random
from typing import Any

import pytest

from cardlang.ast import nodes as n
from cardlang.diagnostics import DiagnosticError
from cardlang.domains import DOMAINS, Domain, role_members
from cardlang.pipeline import check_dsl
from cardlang.runtime.driver import play_game
from cardlang.runtime.execute import execute
from cardlang.runtime.state import Ctx

# A 4-player partnership game with a declared ranking and one decision point:
# the minimal shape in which all four rows are populated and non-empty
# (`rs.teams` needs `partnerships:`, the `Rank` param domain needs `ranking:`).
GAME = """
game G {{
  players: 4
  max_length: 1000
  cards: standard52
  partnerships: [[0, 2], [1, 3]]
{ranking}  zones {{ deck : Deck  hand[player] : Hand<player>  pile : TrickPile }}
  state {{ done : Boolean = false  marker[player] : Integer = 0 }}
  phase root {{
    deal 5 cards from deck to each hand
{stmt}
    round offering [{vocab}] from 0 over players where player is 0 until done
  }}
  winner: highest marker
}}
move_type stop {{ effect {{ done := true }} }}
{extra}
"""

RANKING = "  ranking: A K Q J 10 9 8 7 6 5 4 3 2\n"


def _src(stmt: str = "", vocab: str = "stop", extra: str = "", ranking: bool = True) -> str:
    return GAME.format(
        ranking=RANKING if ranking else "",
        stmt=f"    {stmt}" if stmt else "",
        vocab=vocab,
        extra=extra,
    )


def _accepts(src: str) -> n.Game:
    return check_dsl(src, "g.cardlang")


def _rejects(src: str, fragment: str) -> None:
    with pytest.raises(DiagnosticError) as exc:
        check_dsl(src, "g.cardlang")
    assert fragment in str(exc.value), f"expected {fragment!r} in:\n{exc.value}"


def _param_move(spelling: str) -> str:
    return f"move_type m(x : {spelling}) {{ effect {{ done := true }} }}"


# --- the form axis, derived from the grammar's nouns -------------------------
#
# The quantifier productions spell the plural for `all` (`all players where`),
# the singular for `any` (`any player where`). Both are literal nouns in
# cardlang.lark — see the grammar-surface residual in the module ledger.
def _any(row: Domain) -> str:
    return f"any {row.id} where"


def _all(row: Domain) -> str:
    return f"all {row.id}s where"


# A predicate of the WRONG type for each row's binder: if the binder were typed
# `TAny` (or typed from some table other than the row's `binder_type`), these
# would sail through the type layer. Each must be walled.
CROSS_TYPED: dict[str, str] = {
    "player": "player is hearts",
    "team": "team is hearts",
    "suit": "suit is A",
    "rank": "rank is hearts",
}


# --- quantifier cells --------------------------------------------------------


def test_every_row_is_quantifiable_in_both_forms() -> None:
    # All 8 grammar productions, derived from the rows.
    for row in DOMAINS:
        _accepts(_src(f"let a = {_any(row)} marker[0] is 0"))
        _accepts(_src(f"let b = {_all(row)} marker[0] is 0"))


def test_a_quantifier_binder_types_as_its_rows_binder_type() -> None:
    # The witness that the binder really carries the row's `binder_type`: a
    # cross-typed comparison must be rejected by the type layer. A `TAny` binder
    # would accept every one of these.
    for row in DOMAINS:
        _rejects(
            _src(f"let q = {_any(row)} {CROSS_TYPED[row.id]}"),
            "can never be equal",
        )


def test_a_non_row_noun_has_no_quantifier_production() -> None:
    # The grammar-surface residual, stated as a test: the quantifier nouns are
    # grammar literals, so an unknown noun is a SYNTAX error (a loud wall), not a
    # registry diagnostic. This is what a 5th registry row would hit today.
    _rejects(_src("let q = any color where marker[0] is 0"), "syntax error")


# --- `for each` cells --------------------------------------------------------


def test_for_each_accepts_exactly_the_iterable_rows() -> None:
    for row in DOMAINS:
        src = _src(f"for each {row.id} x: marker[actor] += 1")
        if row.iterable:
            _accepts(src)
        else:  # pragma: no cover - no such row today; the cell is declared, not dead
            _rejects(src, "unknown `for each` role")


def test_for_each_rejects_a_non_row_role() -> None:
    _rejects(
        _src("for each color x: marker[actor] += 1"),
        "unknown `for each` role 'color' (expected one of player, rank, suit, team)",
    )


def test_for_each_binds_the_actor_iff_the_row_is_a_seat_domain() -> None:
    """The `binds_actor` column, checked as behaviour rather than asserted.

    The body is `marker[actor] += 1`, so it records WHO the acting player was on
    each pass. A SEAT row rebinds `acting_as(member)` per member, so every seat's
    marker goes up by exactly one; a VALUE row leaves the ambient actor alone, so
    seat 0 (the ambient actor) absorbs one increment per member and no other seat
    moves. The expectation is computed FROM THE ROW, so a row whose column lies —
    or an `execute._for_each` that reintroduces a hand-written per-role arm —
    fails here.
    """
    rs = _first_decision_state(_accepts(_src("for each player x: marker[actor] += 1")))

    for row in DOMAINS:
        if not row.iterable:  # pragma: no cover - no such row today
            continue
        game = _accepts(_src(f"for each {row.id} x: marker[actor] += 1"))
        stmt = next(s for s in game.phases[0].items if isinstance(s, n.ForEach))

        ctx = Ctx(rs=rs, chooser=lambda p, c, k: list(c[:k])).acting_as(0)
        ctx.rs.push_frame()
        ctx.rs.declare("marker", indexed=True, value={p: 0 for p in rs.seating.players})
        execute(stmt, ctx)
        marker = dict(ctx.rs.get("marker"))
        ctx.rs.pop_frame()

        members = role_members(row.id, ctx)
        assert members, f"row {row.id!r} has an empty runtime domain"
        if row.binds_actor:
            expected = {p: 1 for p in rs.seating.players}
        else:
            expected = {p: (len(members) if p == 0 else 0) for p in rs.seating.players}
        assert marker == expected, (
            f"row {row.id!r} declares binds_actor={row.binds_actor}, but iterating it "
            f"produced {marker} (expected {expected})"
        )


def _first_decision_state(game: n.Game) -> Any:
    captured: dict[str, Any] = {}
    play_game(game, random.Random(0), on_first_decision=lambda rs: captured.setdefault("rs", rs))
    return captured["rs"]


# --- `each … simultaneously` cells -------------------------------------------


def test_each_simultaneously_accepts_exactly_the_seat_rows() -> None:
    # The body is role-NEUTRAL (`hand[0]`, not `hand[player]`), so the only thing
    # varying across the cells is the role: a body reading `player` would make the
    # value rows fail on an unresolved-name wall instead of the domain wall, and
    # the cell would be green for the wrong reason.
    for row in DOMAINS:
        src = _src(f"each {row.id} simultaneously:\n      move chosen 3 cards from hand[0] to pile")
        if row.simultaneous:
            _accepts(src)
        else:
            _rejects(
                src,
                f"`each {row.id} simultaneously` is not runnable — "
                f"simultaneous moves are per player",
            )


def test_each_simultaneously_rejects_a_non_row_role() -> None:
    _rejects(
        _src("each color simultaneously:\n      move chosen 3 cards from hand[0] to pile"),
        "is not runnable — simultaneous moves are per player",
    )


# --- move-parameter cells ----------------------------------------------------


def test_every_declared_type_spelling_plain_and_optional() -> None:
    """The move-param column, over the full spelling axis — every row's
    `type_name` in both its plain and its optional form (8 cells), classified by
    whether the row admits that exact spelling. The optional spellings no row
    lists (`Player?`, `Rank?`, `Team?`) must be REJECTED, never silently read as
    their plain form; `Team` must be rejected because the `team` row declares no
    parameter spelling at all."""
    seen: list[tuple[str, bool]] = []
    for row in DOMAINS:
        for spelling in (row.type_name, f"{row.type_name}?"):
            src = _src(vocab="stop, m", extra=_param_move(spelling))
            admitted = spelling in row.param_domains
            seen.append((spelling, admitted))
            if admitted:
                _accepts(src)
            else:
                _rejects(src, f"move 'm' has unsupported parameter domain '{spelling}'")

    # The classification itself, pinned: exactly which of the 8 spellings are
    # admitted. A row that gains or loses a `param_domains` entry changes this.
    assert seen == [
        ("Player", True),
        ("Player?", False),
        ("Team", False),
        ("Team?", False),
        ("Suit", True),
        ("Suit?", True),
        ("Rank", True),
        ("Rank?", False),
    ]


def test_the_optional_suit_domain_is_the_only_nullable_one() -> None:
    # `Suit?` is admitted because the `suit` row lists it (the no-trump strain is
    # a real member). It is the only `?` spelling any row lists — the asymmetry is
    # a registry fact, not an accident of a dispatch that strips `?`.
    optional = [s for row in DOMAINS for s in row.param_domains if s.endswith("?")]
    assert optional == ["Suit?"]


def test_the_card_outlier_is_admitted_but_is_not_a_row() -> None:
    # `Card` is a legal move-parameter domain but deliberately NOT a registry row
    # (state-dependent: the live hand). Both halves are pinned: it is accepted at
    # the surface, and it is absent from the table.
    _accepts(
        _src(
            vocab="stop, m",
            extra=(
                "move_type m(x : Card) { effect { "
                "move one card from hand[actor] where card is x to pile\n done := true } }"
            ),
        )
    )
    assert "Card" not in {row.type_name for row in DOMAINS}
    assert "Card" not in {s for row in DOMAINS for s in row.param_domains}


def test_an_unknown_and_a_deferred_param_domain_are_walled() -> None:
    _rejects(
        _src(vocab="stop, m", extra=_param_move("Color")),
        "move 'm' has unsupported parameter domain 'Color'",
    )
    _rejects(
        _src(vocab="stop, m", extra=_param_move("Integer")),
        "bounded-Integer parameter domains are deferred",
    )


# --- the rank row's two member columns are two columns ------------------------


def test_the_rank_rows_two_member_columns_diverge() -> None:
    """`rank` is the row that proves `members` and `static_members` must stay
    separate columns. Iterating the rank ROLE reads `rs.ranks` (the declared
    `ranking:` if there is one, else DECK ORDER — always non-empty), while a
    `Rank` move PARAM enumerates the declared ranking only (empty without one).
    So in a game with no `ranking:`, `for each rank` is legal and a `Rank`
    parameter is a compile error. Folding the two accessors into one member
    enumerator would break exactly one of these two cells."""
    _accepts(_src("for each rank r: marker[actor] += 1", ranking=False))
    _rejects(
        _src(vocab="stop, m", extra=_param_move("Rank"), ranking=False),
        "has a Rank parameter, but the game declares no ranking:",
    )
