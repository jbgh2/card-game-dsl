"""Inside a rule, `hand` is the cards the player on turn plays from.

A rule is asked at one decision only: the card a trick round offers
(decisions.md "Rule demand forms"). So a rule's bare `hand` names that
round's Play Source -- the acting seat's instance of the round's `source`
family, or the zone `play_source_for` routes it to under Delegated Play --
whatever the game calls its zones. Resolve stamps the reading once
(`ref_kind == "play_source"`), and every later pass reads the stamp. The
standard library's rules read it, so they need nothing from a game: they are
`library stdlib`, with an empty contract, spliced into a game when its
`active_rules:` names them, exactly as a family library's rules are.

Completeness ledger (decisions.md "Closed-domain completeness")
---------------------------------------------------------------
property:   a bare `hand` in a rule clause is the Play Source, from every rule
            origin, whatever else the game calls `hand`, and nowhere else; a
            sentence that would make one `hand` carry two readings is refused
            at check time in the designer's own text, with its fix named.
domain:     the rule clauses (every expression-holding field of `RuleDef`)
            x what the game declares under the spelling `hand` (nothing; a
            zone of every index shape; a state variable at game and phase
            level; a position domain; each definition kind) x the trick
            round's source family (`hand` itself or another family), for a
            game-local rule and a family-library rule. Beside it: the
            positions a `hand` can stand at around a clause (subscripted, a
            clause binder's scope, a function the clause calls, transitively,
            a rule parameter); the round forms a game can run; the library
            tiers a rule can be activated from, activated or not; the round
            fields `state.` publishes, read from a family library; the parse
            entry points.
registry:   clauses: `dataclasses.fields(n.RuleDef)` by annotation;
            zone index shapes: `cardlang.domains.ZONE_INDEX_ROLES`;
            definition kinds: `cardlang.resolve._INJECTABLE_TARGETS`;
            round forms: the `Round` node kinds of `n.Stmt`;
            round fields: `cardlang.stdlib.round_state.ROUND_STATE_FIELDS`;
            parse entry points: `cardlang.parse._parser().options.start` and
            `tests/test_parse.py::_parse_entry_points`.
does not prove:  that the runtime reads the same cards the checker typed: the
            witness game below plays the reading end to end for one source
            family and one seed, and Bridge's Delegated Play is the corpus
            witness for the routed pool.
"""

from __future__ import annotations

import dataclasses
import random
from pathlib import Path
from typing import Any, get_args

import pytest

from cardlang.ast import nodes as n
from cardlang.diagnostics import DiagnosticError
from cardlang.domains import ZONE_INDEX_ROLES, role_names
from cardlang.parse import _parser, parse_library, parse_text
from cardlang.pipeline import check_dsl
from cardlang.resolve import _INJECTABLE_TARGETS, _walk, resolve, slot_namespace
from cardlang.runtime.driver import play_game
from cardlang.runtime.state import RuntimeState
from cardlang.runtime.values import Card
from cardlang.stdlib.round_state import ROUND_STATE_FIELDS
from tests.test_family_libraries import _patch_libraries
from tests.test_parse import _parse_entry_points

REPO = Path(__file__).resolve().parent.parent
GAMES = REPO / "docs" / "games"
WITNESS = REPO / "tests" / "fixtures" / "play_source_hands.cardlang"

PLAY_SOURCE = "play_source"
CAPTURE = "inside a rule, `hand` is the cards the player on turn plays from"
FUNCTION_FIX = "keep the filter in the rule and have the function take a card"
NO_TRICK = "this game plays no trick round"


# --- the axes, derived ------------------------------------------------------

#: Every clause of a rule: the fields of `RuleDef` holding an expression.
CLAUSES: tuple[str, ...] = tuple(
    f.name
    for f in dataclasses.fields(n.RuleDef)
    if not str(f.type).startswith(("str", "tuple", "Span"))
)

#: How each clause is written when it reads bare `hand`, and how a game-local
#: rule's other clauses read a neighbouring zone instead, so that one clause
#: alone names `hand`. A family library's rule reads `hand` in every clause: a
#: library reaches no zone of the game's.
_CLAUSE_TEXT: dict[str, tuple[str, str]] = {
    "applies_when": ("applies_when: hand is not empty", "applies_when: trick_pile is empty"),
    "demands": (
        "demands: cards in hand where card.suit is state.led_suit",
        "demands: cards in trick_pile where card.suit is state.led_suit",
    ),
    "if_impossible": ("if_impossible: hand", "if_impossible: trick_pile"),
    "exempts": (
        "exempts: cards in hand where card.suit is state.led_suit",
        "exempts: cards in trick_pile where card.suit is state.led_suit",
    ),
}


def _rule(
    name: str,
    reads_hand_in: frozenset[str] | str | None,
    *,
    params: str = "",
    clauses: tuple[str, ...] = CLAUSES,
) -> str:
    reading_in = (
        frozenset({reads_hand_in}) if isinstance(reads_hand_in, str)
        else reads_hand_in or frozenset()
    )
    lines = [f"rule {name}{params} {{", "  constrains: play_to_trick"]
    for clause in clauses:
        reading, other = _CLAUSE_TEXT[clause]
        lines.append("  " + (reading if clause in reading_in else other))
    lines.append("}")
    return "\n".join(lines)


#: The clauses of a rule a game can play: an obligation and its fallback.
PLAYED = ("applies_when", "demands", "if_impossible")


#: What a game may declare under the spelling `hand`, beside its trick source.
#: Zone index shapes come from the domain registry plus a position domain and
#: a single zone; state variables at both levels; every definition kind.
def _hand_declarations() -> dict[str, dict[str, str]]:
    decls: dict[str, dict[str, str]] = {"nothing": {}}
    for role in role_names(ZONE_INDEX_ROLES):
        if role == "player":
            # The family the trick round sources, and a family beside it.
            decls["zone[player]"] = {}
            decls["zone[player] beside"] = {"zone": "hand[player] : Hand<player>"}
        elif role == "team":
            decls["zone[team]"] = {"zone": "hand[team] : TeamPile<team>"}
        else:
            decls[f"zone[{role}]"] = {"zone": f"hand[{role}] : Discard"}
    decls["zone[position]"] = {"zone": "hand[column] : Discard"}
    decls["zone"] = {"zone": "hand : Discard"}
    decls["zone face-down"] = {"zone": "hand : FaceDownPile"}
    decls["game state"] = {"state": "hand : Integer = 0"}
    decls["phase state"] = {"phase_state": "state { hand : Integer = 0 }"}
    spelled = {
        "positions": {"positions": "hand : 1..2"},
        "functions": {"extra": "function hand() = 1"},
        "move_types": {
            "extra": "move_type hand { effect { score[0] := 1 } }",
            "deal": "for each player p: offer to p one of [hand]",
        },
        "rules": {
            "extra": "rule hand { constrains: play_to_trick "
            "demands: cards in held where card.suit is hearts if_impossible: held }"
        },
        "procedures": {
            "extra": "procedure hand() { score[0] := 1 }", "deal": "run hand()"
        },
    }
    for field, noun in _INJECTABLE_TARGETS:
        if field != "zones":
            decls[noun] = spelled[field]
    return decls


HAND_DECLS = _hand_declarations()
#: The declarations a rule clause's bare `hand` would have read under the
#: game's own namespaces, and which it now must not: every zone that is not a
#: family kept per player, and every state variable. A per-player family is
#: what the Play Source is an instance of; a definition or a position domain
#: is never a value a bare name reads.
CAPTURED = tuple(
    d for d in HAND_DECLS
    if (d.startswith("zone") and not d.startswith("zone[player]")) or d.endswith("state")
)


TEMPLATE = """game G_{tag} {{
  players: 4
  teams: [[0, 2], [1, 3]]
  max_length: 1000
  cards: standard52
  ranking: aces high
  {uses}
  positions {{ column : 1..4 {positions} }}
  zones {{ deck : Deck  {source}[player] : Hand<player>  trick_pile : TrickPile  {zone} }}
  state {{ score[player] : Integer = 0  leader : Player? = none  {state} }}
  phase deal_out {{ shuffle deck  deal 13 cards from deck to each {source}  {deal} }}
  phase play {{
    {phase_state}
    active_rules: [{active}]
    legal_moves: [play_to_trick]
    leader := 0
    repeat until (all players where {source}[player] is empty) {{
      {round}
      move all cards from trick_pile to deck
      leader := winner
    }}
  }}
  winner: highest score
}}
{extra}
"""

TRICK_ROUND = (
    "round play_to_trick from leader over all players source {source} "
    "into trick_pile winner highest_of_led_suit"
)


def game_text(
    tag: str,
    *,
    source: str = "hand",
    active: str = "R",
    rules: str = "",
    decl: dict[str, str] | None = None,
    uses: str = "",
    round_stmt: str | None = None,
) -> str:
    d = decl or {}
    extra = "\n".join(x for x in (rules, d.get("extra", "")) if x)
    return TEMPLATE.format(
        tag=tag.replace(" ", "_").replace("[", "_").replace("]", "_").replace("-", "_"),
        source=source,
        active=active,
        uses=uses,
        positions=d.get("positions", ""),
        zone=d.get("zone", ""),
        state=d.get("state", ""),
        phase_state=d.get("phase_state", ""),
        deal=d.get("deal", ""),
        round=(round_stmt if round_stmt is not None else TRICK_ROUND).format(source=source),
        extra=extra,
    )


def _source_for(decl: str) -> str:
    # The trick source is `hand` only when the game's `hand` is a per-player
    # family; otherwise it is another family and `hand` is the declaration.
    return "hand" if decl == "zone[player]" else "held"


def _hand_refs_in(rule: n.RuleDef, clause: str) -> list[n.NameRef]:
    return [
        nd
        for nd in _walk(getattr(rule, clause))
        if isinstance(nd, n.NameRef) and nd.name == "hand"
    ]


def _resolve_text(text: str) -> n.Game:
    return resolve(parse_text(text, "probe.cardlang"))


def _follow_suit_checker(source: str) -> tuple[Any, Any, list[int]]:
    """A chooser asserting, at every card decision, that a seat holding the
    led suit is offered only cards of it; and the hook that hands it the
    live world. `seen` counts the decisions the rule constrained, so a
    playout in which the rule was never consulted cannot pass."""
    world: list[RuntimeState] = []
    seen: list[int] = []

    def attach(rs: RuntimeState) -> None:
        world.append(rs)

    def chooser(player: int, candidates: list[Any], k: int) -> list[Any]:
        if world and candidates and all(isinstance(c, Card) for c in candidates):
            rs = world[0]
            led = rs.mech_state[-1].get("led_suit") if rs.mech_state else None
            held = rs.zones.instance(source, player).cards
            if led is not None and any(c.suit == led for c in held):
                assert all(c.suit == led for c in candidates), (player, led, candidates)
                if any(c.suit != led for c in held):
                    seen.append(player)
        return list(candidates[:k])

    return attach, chooser, seen


def _plays_following_suit(game: n.Game, source: str, seed: int) -> None:
    attach, chooser, seen = _follow_suit_checker(source)
    play_game(game, random.Random(seed), chooser=chooser, on_first_decision=attach)
    assert seen, "no decision was constrained: the rule was never consulted"


def _refused(text: str, *needles: str) -> str:
    with pytest.raises(DiagnosticError) as exc:
        _resolve_text(text)
    message = str(exc.value)
    for needle in needles:
        assert needle in message, f"expected {needle!r} in:\n{message}"
    return message


# --- A: the classification grid --------------------------------------------

_CLASSIFY_CELLS = [
    pytest.param(clause, decl, origin, id=f"{clause}-{decl}-{origin}")
    for clause in CLAUSES
    for decl in HAND_DECLS
    for origin in ("game", "family library")
]


def test_the_clause_axis_is_every_expression_field_of_a_rule() -> None:
    """Anti-vacuity on the derivation.

    red under: annotate a new `RuleDef` clause as `str` -- it leaves the axis."""
    assert set(CLAUSES) == {"applies_when", "demands", "if_impossible", "exempts"}
    assert set(CLAUSES) == set(_CLAUSE_TEXT)


@pytest.mark.parametrize("decl", list(HAND_DECLS))
def test_every_declaration_row_checks_beside_a_rule_that_reads_no_hand(decl: str) -> None:
    """The control for every row below: what the game calls `hand` is
    refused only beside a rule clause reading bare `hand`, never alone."""
    source = _source_for(decl)
    rule = _rule("R", None, clauses=PLAYED).replace("trick_pile", source).replace(
        f"applies_when: {source} is empty", "applies_when: state.led_suit is not none"
    )
    check_dsl(game_text(f"ctl_{decl}", source=source, rules=rule, decl=HAND_DECLS[decl]),
              "ctl.cardlang")


@pytest.mark.parametrize("clause,decl,origin", _CLASSIFY_CELLS)
def test_a_rule_s_bare_hand_is_the_play_source(
    clause: str, decl: str, origin: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = _source_for(decl)
    rule = _rule("R", clause if origin == "game" else frozenset(CLAUSES))
    tag = f"{clause}_{decl}_{origin}"
    if origin == "game":
        text = game_text(tag, source=source, rules=rule, decl=HAND_DECLS[decl])
    else:
        _patch_libraries(
            monkeypatch, {"tricks": parse_library(f"library tricks {{ {rule} }}", "t.cardlang")}
        )
        text = game_text(
            tag, source=source, decl=HAND_DECLS[decl], uses="uses tricks"
        )
    if decl in CAPTURED:
        _refused(text, CAPTURE, "rename")
        return
    game = _resolve_text(text)
    resolved = next(r for r in game.rules if r.name == "R")
    refs = _hand_refs_in(resolved, clause)
    assert refs, "the clause under test reads no `hand`"
    assert {r.ref_kind for r in refs} == {PLAY_SOURCE}
    check_dsl(text, f"{tag}.cardlang")


@pytest.mark.parametrize("decl", [d for d in HAND_DECLS if d not in CAPTURED])
def test_an_admitted_game_plays_its_rule_against_the_play_source(decl: str) -> None:
    source = _source_for(decl)
    rule = _rule("R", frozenset(PLAYED), clauses=PLAYED).replace(
        "applies_when: hand is not empty", "applies_when: state.led_suit is not none"
    )
    game = check_dsl(
        game_text(f"play_{decl}", source=source, rules=rule, decl=HAND_DECLS[decl]),
        "play.cardlang",
    )
    _plays_following_suit(game, source, seed=5)


def test_a_rule_naming_the_source_family_bare_reads_the_same_cards() -> None:
    """A rule may name the family the round sources by its own name; it is
    a zone read of the acting seat's instance, the cards the round offers."""
    rule = _rule("R", None, clauses=PLAYED).replace("trick_pile", "held").replace(
        "applies_when: held is empty", "applies_when: state.led_suit is not none"
    )
    text = game_text("bare_source", source="held", rules=rule)
    game = check_dsl(text, "bare_source.cardlang")
    resolved = next(r for r in game.rules if r.name == "R")
    assert {
        nd.ref_kind for nd in _walk(resolved.demands)
        if isinstance(nd, n.NameRef) and nd.name == "held"
    } == {"zone"}
    _plays_following_suit(game, "held", seed=5)


@pytest.mark.xfail(
    strict=True,
    raises=TypeError,
    reason="a bare zone as a whole `demands:` is not coerced to its cards at "
    "play (issue #626)",
)
def test_a_bare_play_source_demand_plays() -> None:
    rule = (
        "rule R { constrains: play_to_trick applies_when: state.led_suit is not none "
        "demands: hand if_impossible: hand }"
    )
    game = check_dsl(game_text("bare_demand", rules=rule), "bare_demand.cardlang")
    play_game(game, random.Random(3))


# --- B: the positions around a clause --------------------------------------


def test_a_subscripted_hand_in_a_rule_is_the_zone_family() -> None:
    """red under: stamp the Play Source on a `Subscript`'s object too."""
    rule = _rule("R", None).replace(
        "if_impossible: trick_pile", "if_impossible: hand[actor]"
    )
    game = _resolve_text(game_text("sub", source="held", rules=rule, decl=HAND_DECLS["zone[player] beside"]))
    resolved = next(r for r in game.rules if r.name == "R")
    refs = _hand_refs_in(resolved, "if_impossible")
    assert {r.ref_kind for r in refs} == {"zone"}


def test_a_subscripted_hand_with_no_hand_family_names_the_fix() -> None:
    rule = _rule("R", None).replace(
        "if_impossible: trick_pile", "if_impossible: hand[actor]"
    )
    _refused(
        game_text("subnone", source="held", rules=rule),
        "inside a rule, `hand` is already the cards the player on turn plays "
        "from; write `hand` alone",
    )


@pytest.mark.parametrize("depth", [1, 2], ids=["called", "called-through-another"])
@pytest.mark.parametrize("name", ["hand", "held"], ids=["hand", "source-family"])
def test_a_function_reached_from_a_rule_may_not_read_the_play_source(
    depth: int, name: str
) -> None:
    rule = _rule("R", "if_impossible", clauses=PLAYED).replace(
        "applies_when: trick_pile is empty", "applies_when: state.led_suit is not none"
    ).replace(
        "demands: cards in trick_pile where card.suit is state.led_suit",
        "demands: follow_set(state.led_suit)",
    )
    fns = (
        f"function follow_set(s : Suit) = cards in {name} where card.suit is s"
        if depth == 1
        else "function follow_set(s : Suit) = inner(s)\n"
        f"function inner(s : Suit) = cards in {name} where card.suit is s"
    )
    _refused(
        game_text(f"fn{depth}{name}", source="held", rules=rule + "\n" + fns,
                  decl=HAND_DECLS["zone[player] beside"]),
        FUNCTION_FIX,
        "`cards in hand where follows(card, state.led_suit)`",
    )


def test_the_function_fix_the_refusal_names_checks_and_plays() -> None:
    """The refusal's suggested sentence is a claim: it must check and play."""
    rule = _rule("R", "if_impossible", clauses=PLAYED).replace(
        "applies_when: trick_pile is empty", "applies_when: state.led_suit is not none"
    ).replace(
        "demands: cards in trick_pile where card.suit is state.led_suit",
        "demands: cards in hand where follows(card, state.led_suit)",
    )
    text = game_text(
        "fnfix", source="held", rules=rule + "\nfunction follows(c : Card, s : Suit?) = c.suit is s",
        decl=HAND_DECLS["zone[player] beside"],
    )
    game = check_dsl(text, "fnfix.cardlang")
    _plays_following_suit(game, "held", seed=7)


def test_a_function_reached_from_no_rule_keeps_its_zone_reading() -> None:
    """red under: refuse a bare `hand` in every function body, not only in
    those a rule clause reaches."""
    fn = "function held_count() = number of cards in hand"
    game = _resolve_text(
        game_text("fnfree", source="hand", rules=_rule("R", "demands") + "\n" + fn).replace(
            "leader := winner", "leader := winner  score[0] += held_count()"
        )
    )
    fdef = next(f for f in game.functions if f.name == "held_count")
    assert {r.ref_kind for r in _walk(fdef) if isinstance(r, n.NameRef) and r.name == "hand"} == {"zone"}


def test_a_rule_parameter_named_hand_is_refused_at_the_parameter() -> None:
    rule = _rule("R", "demands", params="(hand: Suit)")
    _refused(
        game_text("param", rules=rule, active="R(spades)"),
        "a rule's parameter cannot be named `hand`",
    )


# --- C: the round forms a game runs ----------------------------------------

#: The decision-round node kinds of the statement union.
ROUND_FORMS: tuple[type, ...] = tuple(
    k for k in get_args(n.Stmt) if k.__name__.endswith("Round")
)


def test_the_round_form_axis_is_every_round_node() -> None:
    """red under: add a third `*Round` statement node without a row below."""
    assert {k.__name__ for k in ROUND_FORMS} == {"TrickRound", "ClimbRound"}


def test_a_rule_reading_hand_in_a_game_with_no_round_is_refused() -> None:
    text = game_text(
        "noround", rules=_rule("R", "demands"),
        round_stmt="move all cards from hand[leader] to trick_pile",
    ).replace("leader := winner", "")
    _refused(text, NO_TRICK)


def test_a_stdlib_rule_in_a_climb_only_game_is_refused() -> None:
    src = (GAMES / "big-two.cardlang").read_text()
    climb_only = src.replace(
        "legal_moves: [play_combination]",
        "active_rules: [MustFollowSuit]\n      legal_moves: [play_combination]",
        1,
    )
    assert climb_only != src
    with pytest.raises(DiagnosticError) as exc:
        check_dsl(climb_only, "big-two-rules.cardlang")
    assert NO_TRICK in str(exc.value)
    assert "big-two-rules.cardlang" in str(exc.value)


def test_the_no_trick_refusal_s_fix_checks() -> None:
    """The fix the refusal names -- take the rule out of `active_rules:` --
    is the corpus game itself."""
    check_dsl((GAMES / "big-two.cardlang").read_text(), "big-two.cardlang")


# --- D: the standard library and the one activation-driven splice ----------


def test_the_stdlib_is_a_library_named_stdlib_with_an_empty_contract() -> None:
    from cardlang.stdlib.rules import stdlib_library

    lib = stdlib_library()
    assert isinstance(lib, n.Library)
    assert lib.name == "stdlib"
    assert lib.requires == ()
    assert {r.name for r in lib.rules} >= {"MustFollowSuit", "NoLeadingSuitUntilBroken"}


def test_the_stdlib_loader_refuses_a_misnamed_library() -> None:
    from cardlang.stdlib.rules import load_stdlib

    with pytest.raises(ValueError, match="library stdlib"):
        load_stdlib("library standard { }", "cardlang/stdlib/rules.cardlang")


def test_the_stdlib_loader_refuses_a_contract_row() -> None:
    from cardlang.stdlib.rules import load_stdlib

    with pytest.raises(ValueError, match="requires"):
        load_stdlib(
            "library stdlib { requires { held[player] : Hand<player> } }",
            "cardlang/stdlib/rules.cardlang",
        )


def test_the_stdlib_body_meets_the_library_alone_law() -> None:
    """red under (the plant this test is): a stdlib body reading a name it does
    not have is refused, at the stdlib's own span."""
    from cardlang.stdlib.rules import load_stdlib

    with pytest.raises(DiagnosticError) as exc:
        load_stdlib(
            "library stdlib { rule Leak { constrains: play_to_trick "
            "demands: cards in hand where card.suit is trump_suit "
            "if_impossible: hand } }",
            "cardlang/stdlib/rules.cardlang",
        )
    assert "trump_suit" in str(exc.value)
    assert exc.value.diagnostic.span is not None
    assert exc.value.diagnostic.span.source_name == "cardlang/stdlib/rules.cardlang"


def test_uses_stdlib_is_refused_in_designer_words() -> None:
    _refused(
        game_text("usesstd", rules="", active="MustFollowSuit", uses="uses stdlib"),
        "the standard library needs no `uses` line; its rules are switched on by "
        "name in `active_rules:`",
    )


def test_no_family_library_is_named_like_the_stdlib() -> None:
    assert not (REPO / "docs" / "libraries" / "stdlib.cardlang").exists()


def test_the_stdlib_rules_check_and_play_from_a_family_not_named_hand() -> None:
    """The witness: Spades with its zone family named `hands`."""
    game = check_dsl(WITNESS.read_text(), "play_source_hands.cardlang")
    rules = {r.name: r for r in game.rules}
    assert {"MustFollowSuit", "NoLeadingSuitUntilBroken"} <= set(rules)
    _plays_following_suit(game, "hands", seed=11)


def _template_library() -> n.Library:
    every = frozenset(CLAUSES)
    return parse_library(
        "library tricks {\n"
        + _rule("Unused", every, params="(suit: Suit)").replace(
            "card.suit is state.led_suit", "card.suit is not suit"
        )
        + "\n"
        + _rule("Plain", every)
        + "\n"
        + _rule("Wanted", every)
        + "\n}",
        "tricks.cardlang",
    )


def test_an_unactivated_library_template_is_not_an_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_libraries(monkeypatch, {"tricks": _template_library()})
    _resolve_text(game_text("tmpl", active="Wanted", uses="uses tricks"))


def test_an_unactivated_library_rule_is_not_spliced(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_libraries(monkeypatch, {"tricks": _template_library()})
    game = _resolve_text(game_text("plain", active="Wanted", uses="uses tricks"))
    assert [r.name for r in game.rules] == ["Wanted"]


def test_an_activated_library_rule_follows_the_game_s_own(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_libraries(monkeypatch, {"tricks": _template_library()})
    game = _resolve_text(
        game_text(
            "order", active="Wanted, Own, Unused(hearts)", uses="uses tricks",
            rules=_rule("Own", "demands"),
        )
    )
    assert [r.name for r in game.rules] == ["Own", "Wanted", "Unused"]


def test_every_stdlib_rule_is_activated_by_some_corpus_game() -> None:
    """A rule no game activates is checked library-alone only, which checks
    names and not types, so the corpus must activate every one.

    red under: add a rule to `cardlang/stdlib/rules.cardlang` that no corpus
    game names in `active_rules:`."""
    from cardlang.stdlib.rules import stdlib_library

    activated = {
        ref.name
        for path in sorted(GAMES.glob("*.cardlang"))
        for nd in _walk(parse_text(path.read_text(), path.name))
        if isinstance(nd, n.ActiveRules)
        for ref in nd.refs
    }
    assert {r.name for r in stdlib_library().rules} <= activated


# --- E: `state.<field>` names a round's published field --------------------


def test_state_member_names_the_round_state_namespace() -> None:
    assert slot_namespace(n.Member(n.NameRef("state"), "led_suit"), "field") == "round_state"


@pytest.mark.parametrize("field", sorted(ROUND_STATE_FIELDS))
def test_a_family_library_reads_every_published_round_field(
    field: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    lib = parse_library(
        f"library tricks {{ function probe() = state.{field} }}", "tricks.cardlang"
    )
    from cardlang.resolve import _library_reach

    reach = _library_reach(lib)
    assert reach.slot_leaks == ()
    assert reach.unresolved == ()


# --- F: one grammar start for every library ---------------------------------


def test_one_library_start_and_one_game_start() -> None:
    """red under: restore `stdlib_rules` to the parser's start list."""
    assert set(_parser().options.start) == {"start", "library"}
    assert set(_parse_entry_points()) == {"start", "library"}


# --- G: cells the framing check added ----------------------------------------


@pytest.mark.xfail(
    strict=True,
    raises=pytest.fail.Exception,
    reason="a rule activated in a phase that runs no trick round, in a game "
    "that runs one elsewhere, is #359's per-activation walk (issue #359)",
)
def test_a_rule_activated_where_no_trick_round_runs_is_refused() -> None:
    src = (GAMES / "spades.cardlang").read_text()
    bidding = src.replace(
        "legal_moves: [submit_bid]",
        "active_rules: [MustFollowSuit]\n      legal_moves: [submit_bid]",
        1,
    )
    assert bidding != src
    with pytest.raises(DiagnosticError):
        check_dsl(bidding, "spades-bidding-rules.cardlang")


def test_a_library_rule_removed_in_a_mode_resolves_by_name(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_libraries(monkeypatch, {"tricks": _template_library()})
    text = game_text("remove", active="Wanted", uses="uses tricks").replace(
        "legal_moves: [play_to_trick]",
        "legal_moves: [play_to_trick]\n    mode m { active_rules: [-Wanted]  "
        "transition_to: m2 when play_to_trick where action.card.suit is spades }\n"
        "    mode m2 { }",
    )
    game = _resolve_text(text)
    assert [r.name for r in game.rules] == ["Wanted"]


def test_a_game_rule_named_like_an_unactivated_library_rule_is_refused(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Collision guards sweep every rule a library declares, activated or
    not. red under: sweep only the activated library rules for collisions."""
    _patch_libraries(monkeypatch, {"tricks": _template_library()})
    _refused(
        game_text("clash", active="Plain", uses="uses tricks", rules=_rule("Plain", "demands")),
        "rule 'Plain' is defined by this game and also by library 'tricks'",
    )


def test_bridge_s_rules_read_the_routed_play_source() -> None:
    """Bridge is the corpus's Delegated Play: dummy's card is chosen by
    declarer from dummy's exposed cards, which its follow-suit rule reads."""
    game = check_dsl((GAMES / "bridge.cardlang").read_text(), "bridge.cardlang")
    follow = next(r for r in game.rules if r.name == "MustFollowSuit")
    refs = [
        nd for clause in CLAUSES for nd in _walk(getattr(follow, clause))
        if isinstance(nd, n.NameRef) and nd.name == "hand"
    ]
    assert refs and {r.ref_kind for r in refs} == {PLAY_SOURCE}


def test_the_reserved_word_state_names_the_round_s_state() -> None:
    from cardlang.resolve import _RESERVED_WHY

    assert "round" in _RESERVED_WHY["state"]


def test_bridge_s_rule_reads_are_judged_as_the_routed_play_source() -> None:
    """The Hidden Read check judges a rule clause's `hand` as the Play Source:
    under Bridge's Delegated Play the pool declarer plays from, credited
    because a routed pool's visibility to its decider is the runtime
    `delegation.check_decider_sees`'s.

    red under: delete the `play_source` arm of `_HiddenReads.reads_of` -- the
    rule's clauses then make no read at all and nothing is judged."""
    from cardlang.resolve import hidden_read_verdicts

    game = check_dsl((GAMES / "bridge.cardlang").read_text(), "bridge.cardlang")
    verdicts = [
        v for v in hidden_read_verdicts(game)
        if v.position.startswith("rule `MustFollowSuit`")
    ]
    assert verdicts
    assert all(v.accepted for v in verdicts)
    assert {v.reason for v in verdicts} == {
        "bare-family sugar reads the routed pool its decider plays from"
    }
