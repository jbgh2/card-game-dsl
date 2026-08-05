"""Card is the deck flavor of Piece: the content-kind agreement matrix.

The flagship flavor grid. A game declares its content with `cards:` (a card
deck) or `pieces:` (a piece set); every surface that spells card-content
vocabulary -- the movement/reveal item noun, the filter binder, `.suit`/`.rank`
field access, the card-query and aggregation forms, the `ranking:`/`trump:`
clauses, the `suit`/`rank` quantifier and iteration roles, the Card/Suit/Rank
move-parameter domains, the deck-reading stdlib calls, and card literals --
must AGREE with the declared flavor: legal (in its flavor spelling) in a card
game, rejected NAMING THE KIND in a piece game, and vice versa. A piece game's
own axis vocabulary (the `side`/`kind` fields, the `x`/`o`/`mark` values) works
exactly as the deck's does; and a minimal piece game runs one playout end to
end through the driver.

Completeness ledger (decisions.md "Closed-domain completeness")
---------------------------------------------------------------
property:   for every surface position where the grammar commits to card-
            content vocabulary, the construct is (a) legal in a card game and
            in a piece game in that game's own flavor spelling, or (b) rejected
            with a diagnostic that names the game's declared content kind and
            set ("this game declares pieces ('xo_marks')") -- never parsed and
            silently given card meaning in a piece game (accepted-but-ignored)
            nor accepted with a card type nothing can inhabit; and a minimal
            piece game parses, resolves, typechecks, AND runs a playout.
domain:     {the card-content surface positions -- enumerated below} x
            {card game, piece game}. The surface positions, and where each
            axis derives:
              - movement/reveal item noun, filter binder, field access,
                card-query forms (cq_set/count/any/all), aggregation forms
                (sum / RANK_DIR over cards in), `ranking:` (enumeration and
                convention), `trump:`, card literal -- grammar-anchored, no
                registry; the members are hand-listed once, each below;
              - quantifier / for-each roles -- `cardlang.domains.DOMAINS`, the
                card-axis rows (`CARD_AXIS_ROLES` = suit, rank) vs the seat
                rows (player, team);
              - move-parameter domains -- `cardlang.domains.PARAM_DOMAIN_ORDER`
                plus `Card`, the card-content domains (Suit/Suit?/Rank/Card) vs
                Player;
              - deck-reading stdlib calls -- `DECK_ONLY_CALL_FUNCS` (itself the
                audited subset of `CALL_FUNCS`), vs a generic member
                (top_of);
              - axis values -- the piece set's `deck_suits`/`deck_ranks`.
registry:   cardlang.domains.DOMAINS / CARD_AXIS_ROLES / PARAM_DOMAIN_ORDER;
            cardlang.builtins.functions.CALL_FUNCS / DECK_ONLY_CALL_FUNCS;
            cardlang.runtime.values.COMPONENT_SETS (the piece set xo_marks) and
            content_kind_clause (the one diagnostic prefix every wall opens
            with, asserted here so the walls cannot drift from the grid).
covered:    the parametrizations below, each over its registry --
            test_move_param_domain_flavor (PARAM_DOMAIN_ORDER + Card x flavor),
            test_quantifier_role_flavor / test_for_each_role_flavor (DOMAINS
            roles x flavor), test_deck_only_call_rejected_in_piece_game
            (DECK_ONLY_CALL_FUNCS), plus the hand-listed grammar-anchored
            surfaces (test_item_noun_*, test_field_*, test_card_query_*,
            test_aggregation_*, test_ranking_*, test_trump_*, test_card_literal_*,
            test_reveal_*), the axis-value positives (test_axis_value_*), the
            deck-only totality pins (subset + total partition), and the
            end-to-end positive (test_minimal_piece_game_runs_one_playout):
            a driver playout whose GameResult pins the EXACT scores {0: 5,
            1: 0} -- 5 is the count of pieces the `piece.side is x` filter
            selected through the axis map, so the flavor binder, the
            side->suit translation, and piece-set resolution/construction
            (build_deck seeding the box) are observed, not assumed (red
            under the side->rank map swap, which scores {0: 0, 1: 0}).
sampled:    the field wall is a type-layer wall (`_check_expr`'s `Member` arm),
            so it fires in every predicate context where an item is bound, not
            only the movement filter that seeds most cells here -- sampled by
            the pronoun-rooted chain `action.card.<axis>` in a move guard
            (test_pronoun_rooted_field_access, a `Member` on a `TCard` receiver
            that types differently from a binder root) and by a field access in
            a quantifier body (probed while authoring); the axis VALUES feed the
            existing membership operation as a deck suit does
            (test_axis_value_membership_in_piece_game), the one pairwise cell
            (new value shape x existing operation) pinned as a positive; the
            card-query positive in a card game is the corpus (GOPS et al.), one
            representative pinned here.
residual:   card-content vocabulary reachable ONLY through the trick-taking and
            rule-obligation machinery -- a per-round `round ... trump`, the
            `climb`/`combinations`/`follows` forms, `demands:`/`exempts:`/
            `actions where` card predicates, an outcome-function name, and a
            suit argument to a rule template -- is NOT flavor-walled here: that
            machinery is card-oriented and out of rung-1 scope (the topology
            ladder defers the rule system to a later rung), and a piece game
            reaching it degrades loudly through the existing card-zone /
            name-resolution / deck-only-call walls rather than silently taking
            card meaning. Likewise a card-content TYPE annotation (`Suit`/
            `Rank`/`Card`) at a declaration site is accepted AT the annotation
            in BOTH flavors (the name is a known type); loudness then comes
            from two places, not a silent gap. A state var carries an
            initializer, and the merged default-type pass
            (typecheck.py `_check_state_default_type`) rejects a piece value
            under a card-typed var -- `foo : Suit = x` in a piece game fails
            "declared Suit ... default has type side". The initializer-less
            slots (struct field, function parameter, variant case) accept the
            annotation and fail at every USE in a piece game (no card value
            resolves in a piece namespace). Position-domain names at the
            function-parameter and variant-payload slots ADMIT and resolve to
            their member type (the merge's payload-admit policy,
            tests/test_type_name_positions.py; the board `cell` -> TCell
            extension is pinned in tests/test_board_clause.py). A struct
            DERIVED field reading an item field (`some_card.side`) is a sub-case
            -- `struct_registry` types it against the default `CARD_FIELDS`
            (its inference env carries no game flavor), reached in a piece game
            only through a card-content struct field, itself a loud residual. A
            declaration-site / rule-system wall naming the kind is deferred and
            recorded in issue #114. Piece TWINS of the
            card-query and aggregation forms are grammatically inexpressible (no
            `pieces in ...` / `over pieces in ...` productions -- deliberately
            not added), so those forms have no piece-flavor accept cell; the
            piece game counts/aggregates through the same generic collection
            surfaces a card game shares, unaffected here.
"""

from __future__ import annotations

import random
from collections.abc import Callable

import pytest

from cardlang.builtins.functions import (
    BOARD_ONLY_CALL_FUNCS,
    CALL_FUNCS,
    DECK_ONLY_CALL_FUNCS,
    ANY_FLAVOR_CALL_FUNCS,
)
from cardlang.diagnostics import DiagnosticError
from cardlang.domains import CARD_AXIS_ROLES, PARAM_DOMAIN_ORDER, role_of
from cardlang.pipeline import check_dsl
from cardlang.runtime.driver import play_game
from cardlang.runtime.values import content_kind_clause

# The two flavor prefixes every piece/card mismatch diagnostic opens with, from
# the one runtime helper the walls themselves call -- so a wall whose wording
# drifts from the grid fails here.
PIECE_KIND = content_kind_clause("piece", "xo_marks")
CARD_KIND = content_kind_clause("card", "standard52")


# --- source builders -------------------------------------------------------
#
# Two parallel minimal games, one per flavor, with the same slots so a cell is
# one fragment injected into both. The default movement exercises the filter
# binder + a valid axis field, so the base itself is a positive cell for the
# noun + binder + field + axis-value surfaces. `clause` (a game-level line),
# `body` (statements in the phase), and `top` (top-level declarations after the
# game) default empty; `filt` defaults to a valid same-axis compare.


def card_game(*, clause: str = "", filt: str = "card.suit is hearts", body: str = "", top: str = "") -> str:
    return (
        "game G {\n"
        "  players: 2\n"
        "  cards: standard52\n"
        "  max_length: 60\n"
        f"{clause}"
        "  zones { deck : Deck  hand[player] : Hand<player> }\n"
        "  state { score[player] : Integer = 0  n : Integer = 0 }\n"
        "  phase play {\n"
        f"    move all cards from deck where {filt} to hand[0]\n"
        f"{body}"
        "  }\n"
        "  winner: highest score\n"
        "}\n"
        f"{top}"
    )


def piece_game(*, clause: str = "", filt: str = "piece.side is x", body: str = "", top: str = "") -> str:
    return (
        "game G {\n"
        "  players: 2\n"
        "  pieces: xo_marks\n"
        "  max_length: 60\n"
        f"{clause}"
        "  zones { box : Deck  reserve[player] : PlayerPile<player> }\n"
        "  state { score[player] : Integer = 0  n : Integer = 0 }\n"
        "  phase play {\n"
        f"    move all pieces from box where {filt} to reserve[0]\n"
        f"{body}"
        "  }\n"
        "  winner: highest score\n"
        "}\n"
        f"{top}"
    )


def _reject(source: str) -> str:
    """`check_dsl` the source, require a `DiagnosticError`, and return the full
    diagnostic text -- the primary message plus every co-reported note -- so an
    assertion need not depend on which wall happens to sort first in the bag."""
    with pytest.raises(DiagnosticError) as exc:
        check_dsl(source, "grid.cardlang")
    parts = [exc.value.diagnostic.message]
    parts.extend(getattr(exc.value, "__notes__", []) or [])
    return "\n".join(parts)


def _accept(source: str) -> None:
    check_dsl(source, "grid.cardlang")


# --- item noun (movement) --------------------------------------------------
# `Movement.item` is a free NAME (grammar `selection: [select_mode] amount
# NAME`), conventionally the content noun; the wall makes it agree with flavor.


def test_item_noun_cards_accepted_in_card_game() -> None:
    _accept(card_game())


def test_item_noun_pieces_accepted_in_piece_game() -> None:
    _accept(piece_game())


def test_item_noun_pieces_rejected_in_card_game() -> None:
    src = card_game().replace("move all cards from deck", "move all pieces from deck")
    assert CARD_KIND in _reject(src)


def test_item_noun_cards_rejected_in_piece_game() -> None:
    src = piece_game().replace("move all pieces from box", "move all cards from box")
    assert PIECE_KIND in _reject(src)


# --- field access (the axis fields) ----------------------------------------
# `Member.field` is a free NAME; the per-game axis table types `side`/`kind`
# for pieces, `suit`/`rank` for cards, and rejects the other flavor's spelling.


def test_field_suit_accepted_in_card_game() -> None:
    _accept(card_game(filt="card.suit is hearts"))


def test_field_rank_accepted_in_card_game() -> None:
    _accept(card_game(filt="card.rank is A"))


def test_field_side_accepted_in_piece_game() -> None:
    _accept(piece_game(filt="piece.side is x"))


def test_field_kind_accepted_in_piece_game() -> None:
    _accept(piece_game(filt="piece.kind is mark"))


def test_field_suit_rejected_in_piece_game() -> None:
    # The card-axis spelling on a piece: the item has fields side/kind, not suit.
    text = _reject(piece_game(filt="piece.suit is x"))
    assert "field 'suit'" in text and ("kind" in text and "side" in text)


def test_field_side_rejected_in_card_game() -> None:
    # RHS `hearts` resolves in a card deck (so the only error is the field
    # wall, not an unresolved name); `side` is not a card field.
    text = _reject(card_game(filt="card.side is hearts"))
    assert "field 'side'" in text and ("rank" in text and "suit" in text)


def test_cross_axis_compare_rejected_in_piece_game() -> None:
    # `piece.side is mark` compares the side axis (x/o) with a kind value (mark):
    # the existing cross-enum wall catches it once each axis has its own enum.
    assert "can never be equal" in _reject(piece_game(filt="piece.side is mark"))


# --- adversarial misuse probes (the wrong sentences) -----------------------


def test_bare_binder_outside_filter_is_unresolved() -> None:
    # `piece` is a filter binder, not a global name -- referenced outside any
    # filter it is unresolved, with the flavor-aware hint.
    text = _reject(piece_game(body="    let z = piece\n"))
    assert "unresolved name 'piece'" in text and "`where` filter" in text


def test_mixed_vocabulary_rejected_in_piece_game() -> None:
    # `sum of rank_value(piece) over cards in box`: a card aggregation, a deck-
    # only call, and the wrong binder at once -- loudly rejected, the deck-only
    # wall naming the kind.
    src = piece_game().replace(
        "n : Integer = 0", "n : Integer = sum of rank_value(piece) over cards in box"
    )
    assert PIECE_KIND in _reject(src)


# --- axis values (bare enum values) ----------------------------------------
# The piece set's suit-slot / rank-slot values enter the enum namespace exactly
# as a deck's do.


@pytest.mark.parametrize("value", ["x", "o"])
def test_axis_value_side_resolves_in_piece_game(value: str) -> None:
    _accept(piece_game(filt=f"piece.side is {value}"))


def test_axis_value_kind_resolves_in_piece_game() -> None:
    _accept(piece_game(filt="piece.kind is mark"))


def test_axis_value_membership_in_piece_game() -> None:
    # Pairwise: the new axis-value shape feeds the existing membership operation
    # exactly as a deck suit does (`card.suit in [hearts, spades]`).
    _accept(piece_game(filt="piece.side in [x, o]"))


# --- card-query forms ------------------------------------------------------
# cq_set / cq_count / cq_any / cq_all all hardcode "card"/"cards"; each is
# rejected in a piece game (piece twins are grammatically inexpressible).

_CARD_QUERY_FILTERS: dict[str, str] = {
    "cq_any": "any card in box where true",
    "cq_all": "all cards in box where true",
}


@pytest.mark.parametrize("form", sorted(_CARD_QUERY_FILTERS))
def test_card_query_rejected_in_piece_game(form: str) -> None:
    assert PIECE_KIND in _reject(piece_game(filt=_CARD_QUERY_FILTERS[form]))


def test_card_query_count_rejected_in_piece_game() -> None:
    # cq_count is Integer-valued; exercise it in a state initializer.
    src = piece_game().replace(
        "n : Integer = 0", "n : Integer = number of cards in box"
    )
    assert PIECE_KIND in _reject(src)


def test_card_query_accepted_in_card_game() -> None:
    _accept(card_game(filt="any card in deck where card.suit is hearts"))


# --- aggregation forms -----------------------------------------------------
# `sum of ... over cards in ...` and the RANK_DIR order aggregators hardcode
# "cards"; rejected in a piece game.


def test_aggregation_sum_rejected_in_piece_game() -> None:
    src = piece_game().replace(
        "n : Integer = 0", "n : Integer = sum of 1 over cards in box"
    )
    assert PIECE_KIND in _reject(src)


def test_aggregation_order_rejected_in_piece_game() -> None:
    src = piece_game(filt="piece is (highest score over cards in box or piece)")
    assert PIECE_KIND in _reject(src)


def test_aggregation_accepted_in_card_game() -> None:
    src = card_game().replace(
        "n : Integer = 0", "n : Integer = sum of 1 over cards in deck"
    )
    _accept(src)


# --- ranking: / trump: clauses ---------------------------------------------
# Both the enumeration and the convention form of `ranking:`, and `trump:`,
# read the deck's suits/ranks; rejected in a piece game (this closes the T2
# accepted-unvalidated residual, which swallowed BOTH forms silently).


def test_ranking_enumeration_rejected_in_piece_game() -> None:
    assert PIECE_KIND in _reject(piece_game(clause="  ranking: x o mark\n"))


def test_ranking_convention_rejected_in_piece_game() -> None:
    assert PIECE_KIND in _reject(piece_game(clause="  ranking: aces high\n"))


def test_ranking_accepted_in_card_game() -> None:
    _accept(card_game(clause="  ranking: aces high\n"))


def test_trump_rejected_in_piece_game() -> None:
    assert PIECE_KIND in _reject(piece_game(clause="  trump: x\n"))


def test_trump_accepted_in_card_game() -> None:
    _accept(card_game(clause="  trump: hearts\n"))


# --- quantifier / for-each roles -------------------------------------------
# `any suit where`, `for each rank` etc. range over deck axes; the card-axis
# roles (CARD_AXIS_ROLES = suit, rank) are rejected in a piece game, the seat
# roles (player, team) stay legal in both. `_ROLE_QUANTIFIER` spells each role's
# `any <role> where` surface; team needs a team to be non-degenerate.

_ROLE_QUANTIFIER: dict[str, str] = {
    "suit": "any suit where true",
    "rank": "any rank where true",
    "player": "any player where true",
    "team": "any team where true",
}
_ROLE_FOREACH: dict[str, str] = {
    "suit": "for each suit s: n += 0\n",
    "rank": "for each rank r: n += 0\n",
    "player": "for each player p: n += 0\n",
    "team": "for each team t: n += 0\n",
}


@pytest.mark.parametrize("role", sorted(_ROLE_QUANTIFIER))
def test_quantifier_role_flavor(role: str) -> None:
    q = _ROLE_QUANTIFIER[role]
    if role_of(role) in CARD_AXIS_ROLES:
        assert PIECE_KIND in _reject(piece_game(filt=q))
        _accept(card_game(filt=q))
    else:
        _accept(piece_game(filt=q))
        _accept(card_game(filt=q))


@pytest.mark.parametrize("role", sorted(_ROLE_FOREACH))
def test_for_each_role_flavor(role: str) -> None:
    stmt = _ROLE_FOREACH[role]
    if role_of(role) in CARD_AXIS_ROLES:
        assert PIECE_KIND in _reject(piece_game(body=f"    {stmt}"))
        _accept(card_game(body=f"    {stmt}"))
    else:
        _accept(piece_game(body=f"    {stmt}"))
        _accept(card_game(body=f"    {stmt}"))


# --- move-parameter domains ------------------------------------------------
# A parameterized move OFFERED in a decision passes `_check_move_params`; the
# card-content domains (Suit/Suit?/Rank/Card) are rejected in a piece game, and
# Player stays legal in both. Axis derives from PARAM_DOMAIN_ORDER + Card.

_PARAM_DOMAINS: tuple[str, ...] = PARAM_DOMAIN_ORDER + ("Card",)
_CARD_CONTENT_DOMAINS: frozenset[str] = frozenset({"Suit", "Suit?", "Rank", "Card"})


def _param_game(build: Callable[..., str], domain: str) -> str:
    # A move typed by `domain`. The move type is a top-level declaration;
    # `offer` is incidental -- the merged relocation gates every DECLARED move
    # type (resolve `_validate_refs`), offered or not (probed directly by
    # test_move_param_domain_flavor_gates_declared_but_unoffered below).
    top = f"move_type act(v : {domain}) {{ effect {{ n += 1 }} }}\n"
    body = "    for each player p: offer to p one of [act]\n"
    return build(body=body, top=top)


@pytest.mark.parametrize("domain", sorted(_PARAM_DOMAINS))
def test_move_param_domain_flavor(domain: str) -> None:
    # The piece-reject limb of the property. The card-game-legal limb (a) is
    # corpus-sampled, not re-probed here: each card-content domain needs its
    # own card-game setup (Rank a `ranking:`, Card a `hand[player]` zone), and
    # the corpus exercises them all -- Go Fish's `ask(rank : Rank)`, Schnapsen's
    # `play_card(c : Card)`, Bridge's `submit_bid(strain : Suit?)`.
    if domain in _CARD_CONTENT_DOMAINS:
        assert PIECE_KIND in _reject(_param_game(piece_game, domain))
    else:  # Player: a seat domain, legal in both flavors
        _accept(_param_game(piece_game, domain))
        _accept(_param_game(card_game, domain))


def test_move_param_domain_flavor_gates_declared_but_unoffered() -> None:
    # The merged relocation gates a move type by its DECLARATION, so a
    # card-content param in a piece game is rejected even when no vocabulary
    # offers it -- the reach main's move-param relocation added.
    top = "move_type act(v : Suit) { effect { n += 1 } }\n"
    assert PIECE_KIND in _reject(piece_game(top=top))


# --- deck-reading stdlib calls ---------------------------------------------
# Every DECK_ONLY_CALL_FUNCS member reads suit/rank/points; a call to one in a
# piece game is a resolve wall. A generic member (top_of) accepts in both.


def test_stdlib_call_funcs_totally_classified() -> None:
    # Non-vacuous: all three sets are explicit literals (functions.py:223 keeps
    # them so, not derived by subtraction), so a call in NONE (a newly
    # registered function nobody classified) makes the union fall short and this
    # names it; a call in two breaks disjointness. The wall's domain is exactly
    # CALL_FUNCS, partitioned into deck-only / board-only / generic.
    #
    # red under: add a name to CALL_FUNCS (or drop one from a
    # classification set) without classifying it -- the union assertion below
    # then falls short of CALL_FUNCS. Demonstrated by the merge itself:
    # coup_note_reveal/tichu_hand_summary evicted from CALL_FUNCS left
    # DECK_ONLY as a strict superset until they were dropped from it here.
    assert ANY_FLAVOR_CALL_FUNCS <= CALL_FUNCS
    assert DECK_ONLY_CALL_FUNCS <= CALL_FUNCS
    assert BOARD_ONLY_CALL_FUNCS <= CALL_FUNCS
    assert (
        DECK_ONLY_CALL_FUNCS | BOARD_ONLY_CALL_FUNCS | ANY_FLAVOR_CALL_FUNCS
        == CALL_FUNCS
    )
    assert DECK_ONLY_CALL_FUNCS.isdisjoint(ANY_FLAVOR_CALL_FUNCS)
    assert BOARD_ONLY_CALL_FUNCS.isdisjoint(DECK_ONLY_CALL_FUNCS)
    assert BOARD_ONLY_CALL_FUNCS.isdisjoint(ANY_FLAVOR_CALL_FUNCS)


@pytest.mark.parametrize("fn", sorted(DECK_ONLY_CALL_FUNCS))
def test_deck_only_call_rejected_in_piece_game(fn: str) -> None:
    # The wall fires on the call NAME, before argument checking, so a uniform
    # placeholder argument suffices for every signature.
    src = piece_game().replace("n : Integer = 0", f"n : Integer = {fn}(0)")
    assert PIECE_KIND in _reject(src)


def test_generic_call_accepts_in_both_flavors() -> None:
    # top_of: ordered-collection position, content-agnostic -- legal in both.
    _accept(piece_game(filt="piece is top_of(box)"))
    _accept(card_game(filt="card is top_of(deck)"))


# --- card literals ---------------------------------------------------------
# `mark of x` is a well-formed card literal against xo_marks' ranks/suits; the
# wall rejects the card-literal form in a piece game (advisor gap: else
# accepted-but-ignored once the piece namespaces populate).


def test_card_literal_rejected_in_piece_game() -> None:
    assert PIECE_KIND in _reject(piece_game(filt="piece is (mark of x)"))


def test_card_literal_accepted_in_card_game() -> None:
    _accept(card_game(filt="card is (A of spades)"))


# --- reveal (epistemic op) -------------------------------------------------
# `reveal one card from ...` hardcodes "card"; rejected in a piece game (the
# piece twin is grammatically inexpressible).


def test_reveal_rejected_in_piece_game() -> None:
    src = piece_game(body="    reveal one card from box\n")
    assert PIECE_KIND in _reject(src)


def test_reveal_accepted_in_card_game() -> None:
    _accept(card_game(body="    reveal one card from deck\n"))


# --- pronoun-rooted field chain (sampled) ----------------------------------
# `action.card.<axis>` is a `Member` on a `TCard`, the same wall as a bare
# binder's field access -- sampled to prove the pronoun path is covered too.


def test_pronoun_rooted_field_access() -> None:
    # `action.card` is a `TCard`; `.suit` on it is the same `Member`-on-TCard
    # wall as a bare `piece.suit`. RHS `x` resolves in a piece game so the only
    # error is the field wall. (`action` binds in a move `when :` guard.)
    top = (
        "move_type act(v : Player) { when : action.card.suit is x  "
        "effect { n += 1 } }\n"
    )
    body = "    for each player p: offer to p one of [act]\n"
    src = piece_game(top=top, body=body)
    assert "field 'suit'" in _reject(src)


# --- the end-to-end positive: a minimal piece game runs --------------------


def test_minimal_piece_game_runs_one_playout() -> None:
    """The one runtime cell: the setup movement filters the box through the
    `piece` binder (`piece.side is x` -> Card.suit via the axis map), then the
    body drains reserve[0] counting one point per piece actually moved --
    score[0] IS the number of x-pieces the filter selected, observable in
    GameResult. xo_marks holds five ("mark","x") pieces, so anything but a
    correct axis map + binder yields a different number: red under
    axis_attributes swapped (side->rank) -- the filter then reads the kind
    axis, matches nothing, and scores {0: 0, 1: 0}."""
    body = (
        "    repeat until reserve[0] is empty {\n"
        "      move one piece from reserve[0] to box\n"
        "      score[0] += 1\n"
        "    }\n"
    )
    game = check_dsl(piece_game(body=body), "piece.cardlang")
    result = play_game(game, random.Random(0))
    assert result.scores == {0: 5, 1: 0}
    assert result.winner == 0
