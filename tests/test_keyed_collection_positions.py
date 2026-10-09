"""A keyed collection stands only where its own key is wanted.

property:   a keyed collection -- an indexed `let`, a per-seat or per-team
            state variable -- is compatible with another collection only when
            the two keys agree: never with an unkeyed collection (a zone, a
            `[...]` list, a query result) in either direction, never across
            key domains, at every depth; every refusal names the key, and
            offers the one-entry spelling exactly when the key is the only
            mismatch. The runtime holds a keyed collection as a
            map, so a crossing reads the keys instead of the entries, compares
            a map with a list (never equal), or replaces a store with a
            differently-keyed one.
domain:     the relation grid: key x key x nesting depth under `coercible`,
            both operand orders, with the key axis every value the `key` facet
            can take (no key, each zone-index role's binder type, and the
            unknown key a conditional mints when its branches disagree). The
            sentence grid: every checker position where one collection stands
            for another -- a Builtin's and a declared Primitive's collection
            parameter, a card source (aggregation, card query, comprehension,
            subset), `is empty`/`is not empty`, a turn ring's and a round's
            participants, a lines quantifier's source, a rule's
            `if_impossible:`, equality (both operand orders), whole-variable
            assignment, and membership's element comparison -- crossed with
            every argument shape of that position's element kind (unkeyed,
            Player-keyed, Team-keyed, and maybe-keyed through a conditional).
            Membership's right-hand side refuses any keyed collection for its
            own reason (keys or values?), beside `_check_membership_operands`.
registry:   key axis: `domains.ZONE_INDEX_ROLES` binder types plus the two
            facet values outside it; depth axis: `TCollection.element`;
            positions: `_check_operand`'s callers whose expected type is a
            collection, `_check_card_source`, `_check_is_check`,
            `_check_if_impossible`, `_check_equality_operands`,
            `_check_membership_operands`. Sticky-key merge: tests/
            test_nominal_type_identity.py::
            test_the_keying_domain_is_governed_by_the_sticky_key_rule.
does not prove:  a keyed map reached through the permissive top -- a Builtin
            parameter typed `Any` (`suit_of`), an `if` whose branches do not
            join (issue #116) -- whose shape the checker cannot see, so no
            relation is consulted there.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

import pytest

from cardlang import typecheck
from cardlang.diagnostics import DiagnosticError
from cardlang.domains import DOMAINS, ZONE_INDEX_ROLES
from cardlang.pipeline import check_dsl
from cardlang.types import TAny, TCard, TCollection, TInteger, TPlayer, TTeam, Type, coercible

# --- the relation grid --------------------------------------------------------

#: Every value the `key` facet can take, derived: no key, the binder type of
#: each role a state variable may be indexed by, and the unknown key `join`
#: mints for a conditional whose branches are keyed differently or not at all.
KEYS: dict[str, Type | None] = {
    "unkeyed": None,
    **{d.id.value: d.binder_type for d in DOMAINS if d.id in ZONE_INDEX_ROLES},
    "maybe-keyed": TAny(),
}

#: The authored decision: which (source key, wanted key) pairs fit. Present
#: never fits absent, a present key fits only its own domain, and the unknown
#: key fits only itself: a conditional mints it when its branches' keys
#: disagree, so `score := if flag then score else [0, 0]` may install a list.
FITS: frozenset[tuple[str, str]] = frozenset(
    {
        ("unkeyed", "unkeyed"),
        ("player", "player"),
        ("team", "team"),
        ("maybe-keyed", "maybe-keyed"),
    }
)

def _top(key: Type | None) -> Type:
    return TCollection(TInteger(), key=key)


def _one_level_down(key: Type | None) -> Type:
    return TCollection(TCollection(TInteger(), key=key))


DEPTHS: dict[str, Callable[[Type | None], Type]] = {
    "top": _top,
    "one level down": _one_level_down,
}


def test_the_key_axis_covers_the_authored_table() -> None:
    """The authored table decides every pair of the derived axis.

    red under: in `cardlang/domains.py`, add `Role.SUIT` to
    `ZONE_INDEX_ROLES` -- the axis gains a key no row of `FITS` names.
    """
    labels = set(KEYS)
    assert {"player", "team"} <= labels
    mentioned = {label for pair in FITS for label in pair}
    assert mentioned == labels, sorted(labels ^ mentioned)


@pytest.mark.parametrize("depth", DEPTHS)
@pytest.mark.parametrize("want", KEYS)
@pytest.mark.parametrize("got", KEYS)
def test_a_collection_coerces_only_to_a_fitting_key(got: str, want: str, depth: str) -> None:
    build = DEPTHS[depth]
    expected = (got, want) in FITS
    assert coercible(build(KEYS[got]), build(KEYS[want])) is expected


def test_the_zone_facet_still_never_decides() -> None:
    zone, plain = TCollection(TCard(), zone=True), TCollection(TCard())
    assert coercible(zone, plain) and coercible(plain, zone)


@pytest.mark.parametrize(
    ("t", "printed"),
    [
        (TCollection(TCard()), "Collection<Card>"),
        (TCollection(TInteger(), key=TPlayer()), "Collection<Integer> keyed by Player"),
        (TCollection(TInteger(), key=TTeam()), "Collection<Integer> keyed by Team"),
        (
            TCollection(TInteger(), key=TAny()),
            "Collection<Integer> keyed in one branch of a conditional",
        ),
    ],
)
def test_a_printed_collection_type_shows_its_key(t: Type, printed: str) -> None:
    assert typecheck._type_name(t) == printed


# --- the sentence grid --------------------------------------------------------


def _game(stmt: str, *, block: str = "", rules: str = "") -> str:
    return f"""game G {{
  players: 2
  max_length: 50
  cards: standard52
  teams: [[0], [1]]
{block}  zones {{ deck : Deck  hand[player] : Hand<player>  pile : Discard }}
  state {{
    score[player] : Integer = 0
    bids[player] : Integer = 0
    tscore[team] : Integer = 0
    flag : Boolean = false
  }}
  phase play {{
    shuffle deck
    deal 2 cards from deck to each hand
    let probe[p] = A of spades
    let pair = [A of spades, K of hearts]
    let nums = [0, 0]
    let seats = [0, 1]
    let mates[p] = p
    let maybe_cards = if flag then probe else pair
    let maybe_nums = if flag then score else nums
    {stmt}
  }}
  winner: highest score
}}
{rules}"""


@dataclass(frozen=True)
class Position:
    template: str
    kind: str
    block: str = ""
    rules: str = ""


#: Every position where one collection stands for another, by the element kind
#: it reads. `{x}` is the argument.
POSITIONS: dict[str, Position] = {
    "builtin parameter": Position("if top_of({x}) is A of spades {{ flag := true }}", "card"),
    "primitive parameter": Position(
        "flag := gin_valid_meld({x})",
        "card",
        block="  primitives { gin_valid_meld(cards : Collection<Card>) : Boolean }\n",
    ),
    "aggregation source": Position("score[0] := sum of 1 over cards in {x}", "card"),
    "card query source": Position(
        "if any card in {x} where card.suit is hearts {{ flag := true }}", "card"
    ),
    "subset source": Position(
        "if any subset of 1 cards in [{x}, pile] where flag {{ flag := true }}", "card"
    ),
    "is empty": Position("if {x} is empty {{ flag := true }}", "card"),
    "is not empty": Position("if {x} is not empty {{ flag := true }}", "card"),
    "turn ring participants": Position(
        "turns t from 0 over {x} until flag {{ flag := true }}", "player"
    ),
    "round participants": Position(
        "turns t from 0 over {x} until flag {{ offer to t one of [raise, pass] }}",
        "player",
        rules="move_type raise { effect { flag := true } }\n"
        "move_type pass { effect { flag := true } }\n",
    ),
    "equality, left": Position("if {x} is score {{ flag := true }}", "integer"),
    "equality, right": Position("if score is {x} {{ flag := true }}", "integer"),
    "whole-variable assignment": Position("score := {x}", "integer"),
    "membership element": Position("if {x} in [score, bids] {{ flag := true }}", "integer"),
}

#: The argument shapes of each element kind, with whether each is accepted.
ARGUMENTS: dict[str, dict[str, tuple[str, bool]]] = {
    "card": {
        "zone": ("hand[0]", True),
        "unkeyed list": ("pair", True),
        "player-keyed": ("probe", False),
        "maybe-keyed": ("maybe_cards", False),
    },
    "player": {
        "all players": ("all players", True),
        "unkeyed list": ("seats", True),
        "player-keyed": ("mates", False),
    },
    "integer": {
        "same key": ("bids", True),
        "unkeyed list": ("nums", False),
        "list literal": ("[3, 4]", False),
        "team-keyed": ("tscore", False),
        "maybe-keyed": ("maybe_nums", False),
    },
}

#: What a refusal must name for each refused argument: the key, and the
#: one-entry spelling of whichever side is keyed.
NAMES: dict[str, tuple[str, ...]] = {
    "probe": ("keyed by Player", "probe[p]"),
    "maybe_cards": ("one branch of a conditional", "give every branch the same shape"),
    "mates": ("keyed by Player", "mates[p]"),
    "nums": ("keyed by Player", "score[p]"),
    "[3, 4]": ("keyed by Player", "score[p]"),
    "tscore": ("keyed by Team", "keyed by Player"),
    "maybe_nums": ("one branch of a conditional", "give every branch the same shape"),
}

#: Membership's keyed side is each member of the right-hand collection, which
#: has no one name to subscript.
MEMBERSHIP_NAMES: dict[str, tuple[str, ...]] = {
    "nums": ("keyed by Player", "each member of the collection holds one entry per player"),
    "[3, 4]": ("keyed by Player", "each member of the collection holds one entry per player"),
    "tscore": ("keyed by Team", "keyed by Player"),
    "maybe_nums": ("one branch of a conditional", "give every branch the same shape"),
}

CELLS = [
    pytest.param(pos, arg, id=f"{pos}-{arg}")
    for pos, p in POSITIONS.items()
    for arg in ARGUMENTS[p.kind]
]


@pytest.mark.parametrize(("position", "argument"), CELLS)
def test_a_keyed_collection_stands_only_where_its_key_is_wanted(
    position: str, argument: str
) -> None:
    p = POSITIONS[position]
    spelling, accepted = ARGUMENTS[p.kind][argument]
    src = _game(p.template.format(x=spelling), block=p.block, rules=p.rules)
    if accepted:
        check_dsl(src, "g.cardlang")
        return
    with pytest.raises(DiagnosticError) as ei:
        check_dsl(src, "g.cardlang")
    msg = str(ei.value)
    names = MEMBERSHIP_NAMES if position == "membership element" else NAMES
    for name in names[spelling]:
        assert name in msg, msg
    assert msg.count("error:") == 1, msg


def _board_game(stmt: str) -> str:
    return f"""game B {{
  players: 2
  max_length: 30
  board: grid(3, 3)
  pieces: xo_marks
  zones {{ box : Deck  square[cell] : Cell<cell>  reserve[player] : PlayerPile<player> }}
  state {{ result[player] : Integer = 0 }}
  phase play {{
    let ls[p] = lines(3)[0]
    let flat = lines(3)
    {stmt}
  }}
  winner: highest result
}}"""


@pytest.mark.parametrize(("source", "accepted"), [("flat", True), ("ls", False)])
def test_a_lines_quantifier_takes_an_unkeyed_collection_of_lines(
    source: str, accepted: bool
) -> None:
    src = _board_game(
        f"if any line in {source} where all cells in line where square[cell] is empty "
        f"{{ result[0] := 1 }}"
    )
    if accepted:
        check_dsl(src, "b.cardlang")
        return
    with pytest.raises(DiagnosticError, match=r"keyed by Player[\s\S]*ls\[p\]"):
        check_dsl(src, "b.cardlang")


_RULE_GAME = """game R {{
  players: 2
  max_length: 50
  cards: standard52
  ranking: A K Q J 10 9 8 7 6 5 4 3 2
  zones {{ deck : Deck  hand[player] : Hand<player>  pile : TrickPile }}
  state {{ held[player] : Card = A of spades  score[player] : Integer = 0 }}
  phase play {{
    shuffle deck
    deal 2 cards from deck to each hand
    round play_to_trick from 0 over all players source hand into pile winner highest_of_led_suit
  }}
  winner: highest score
}}
rule follow {{
  constrains: play_to_trick
  demands: cards in hand where card.suit is hearts
  if_impossible: {fallback}
}}"""


@pytest.mark.parametrize(("fallback", "accepted"), [("hand", True), ("held", False)])
def test_an_if_impossible_fallback_is_an_unkeyed_card_set(fallback: str, accepted: bool) -> None:
    src = _RULE_GAME.format(fallback=fallback)
    if accepted:
        check_dsl(src, "r.cardlang")
        return
    with pytest.raises(DiagnosticError, match=r"keyed by Player[\s\S]*held\[p\]"):
        check_dsl(src, "r.cardlang")


def test_a_key_one_level_down_is_refused_in_a_comparison() -> None:
    """The depth row: two lists of per-seat values against two lists of lists."""
    with pytest.raises(DiagnosticError, match="keyed by Player"):
        check_dsl(_game("if [score, bids] is [nums, nums] { flag := true }"), "g.cardlang")


def test_two_same_keyed_values_still_compare_and_assign() -> None:
    check_dsl(
        _game("if score is bids { flag := true }\n    score := bids\n    tscore := tscore"),
        "g.cardlang",
    )


#: The fix phrases a key refusal may append. Each is a remedy only when the
#: key is the sole mismatch, since an entry of the wrong element type fits no
#: better than the whole value.
KEY_FIXES = ("one entry at a time", "give every branch the same shape")

#: Positions where the key AND the element mismatch, one per caller of the
#: hint: an operand position, a member-reading position, an assignment,
#: equality, and membership's element.
BOTH_MISMATCH: dict[str, str] = {
    "builtin parameter": "if top_of(score) is A of spades { flag := true }",
    "card source": "score[0] := sum of 1 over cards in score",
    "assignment": "score := pair",
    "assignment across domains": "score := [tscore, tscore]",
    "equality": "if score is pair { flag := true }",
    "membership element": "if pair in [score, bids] { flag := true }",
}


@pytest.mark.parametrize("case", BOTH_MISMATCH)
def test_a_key_fix_is_offered_only_when_the_key_is_the_sole_mismatch(case: str) -> None:
    with pytest.raises(DiagnosticError) as ei:
        check_dsl(_game(BOTH_MISMATCH[case]), "g.cardlang")
    msg = str(ei.value)
    assert "keyed" in msg, msg
    assert not any(fix in msg for fix in KEY_FIXES), msg
