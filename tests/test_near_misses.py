"""A refused name is told the declared names it nearly spells.

Every compile-time refusal of a name the checker looked up in a set it holds
-- a zone, a state variable, a move type, a deck, a rank, a phase, a library,
a type, any declared or registered spelling -- carries that set's Near Misses
(docs/glossary/near-miss.md), and the rendered refusal offers them as one
`did you mean` clause. The words and the measure have one owner,
`cardlang.diagnostics`; every refusal site hands the owner the spelling and the
set, and none spells its own suggestion.

Completeness ledger (decisions.md "Closed-domain completeness")
---------------------------------------------------------------
property:        a refusal of a name absent from the set the checker looked
                 it up in renders the declared names that resemble it -- at
                 most three, most alike first, alphabetical among equals, the
                 refused spelling itself never -- in one `did you mean`
                 clause, and renders none where nothing resembles it; the
                 resemblance measure is one function, shared with the parse
                 layer's ranking of what the grammar expected; a refusal the
                 attribution step retells keeps its Near Misses.
domain:          every refusal site in the resolve, typecheck and catalogue
                 passes that refuses a designer-written spelling because the
                 set it was looked up in lacks it, each witnessed by one slip
                 planted in a real corpus or family game (or, for a library's
                 own text, a library body) that reaches the site; crossed with
                 the bare-name ref kinds the resolver classifies, one slip per
                 kind; and the misuse probes below. Refusals of a name that
                 IS in the set it may not be in (a collision, a reserved
                 word) or that resolves to the wrong kind or the wrong scope
                 refuse what the name denotes, not its spelling, and are
                 told their own sentence. The parse layer's syntax errors
                 rank the grammar's expected words by the same measure and
                 are the grammar's to word (issue #1045 for statement
                 keywords). Command-line and play-session arguments list
                 their whole set already, and runtime refusals speak the
                 runtime channel.
registry:        sites: `_owner_sites` (an AST scrape of every
                 `DiagnosticBag.unknown` call in `_SCRAPED`) against
                 `WITNESSES`; re-spelled refusals: `_respelled_sites` over
                 the same modules; ref kinds: `cardlang.ast.nodes.REF_KINDS`
                 against `REF_KIND_WITNESSES`.
held by:         Derived and Pinned. The owner is a single constructor
                 (`DiagnosticBag.unknown`) and a single renderer
                 (`Diagnostic.format`); the pins catch a site that re-spells
                 an unknown-name refusal itself and a routed site with no
                 witness. A refusal's sentence is a `str` and no union tells
                 an unknown-name sentence from any other, so the fact cannot
                 be held by a type; a typed lookup returning `Found | Miss`
                 was priced and gives no higher rung, since a site may still
                 ignore the `Miss` and write its own sentence (#1044, the
                 Architect's counsel).
does not prove:  that every site of the class is routed. The re-spelling pin
                 reads refusals worded `unknown` or `unresolved`; a name
                 refusal worded otherwise and left unrouted is invisible to
                 it, and the instrument for that is a fresh read of the
                 package's refusals against `WITNESSES`. Nor that the Near
                 Misses offered are the name the author meant: the measure
                 ranks spelling, and a slip that lands nearer another
                 declared name is offered that name first.
"""

from __future__ import annotations

import ast
import inspect
from dataclasses import dataclass
from pathlib import Path
from typing import get_args

import pytest

from cardlang import diagnostics
from cardlang.ast import nodes as n
from cardlang.diagnostics import DiagnosticBag, DiagnosticError
from cardlang.parse import parse_library
from cardlang.pipeline import check_dsl

_ROOT = Path(__file__).resolve().parent.parent

# The passes whose refusals of a spelling this module pins.
_SCRAPED: tuple[str, ...] = (
    "cardlang/resolve.py",
    "cardlang/typecheck.py",
    "cardlang/catalogue_pass.py",
)

_DESIGNED_RED = pytest.mark.xfail(
    strict=True, raises=AssertionError, reason="issue #1044: no refusal offers Near Misses yet"
)


# --------------------------------------------------------------------------
# The census: which refusal sites the owner serves.
# --------------------------------------------------------------------------


def _template(expr: ast.expr) -> str:
    """The literal words of a refusal's sentence, each interpolation `{}`."""
    if isinstance(expr, ast.Constant) and isinstance(expr.value, str):
        return expr.value
    if isinstance(expr, ast.JoinedStr):
        return "".join(
            v.value if isinstance(v, ast.Constant) and isinstance(v.value, str) else "{}"
            for v in expr.values
        )
    if isinstance(expr, ast.BinOp) and isinstance(expr.op, ast.Add):
        return _template(expr.left) + _template(expr.right)
    return "{}"


def _calls(method: str) -> list[tuple[str, str, int]]:
    """Every `<x>.<method>(sentence, ...)` call in `_SCRAPED`, as (module,
    innermost enclosing function, line), with the sentence's template."""
    found: list[tuple[str, str, int]] = []
    for rel in _SCRAPED:
        tree = ast.parse((_ROOT / rel).read_text())
        owner: dict[int, str] = {}
        for fn in ast.walk(tree):
            if isinstance(fn, ast.FunctionDef | ast.AsyncFunctionDef):
                for node in ast.walk(fn):
                    owner[id(node)] = fn.name  # innermost wins: walked last
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr == method
                and node.args
            ):
                key = f"{Path(rel).stem}::{owner.get(id(node), '<module>')}::{_template(node.args[0])[:60]}"
                found.append((key, rel, node.lineno))
    return found


def _owner_sites() -> list[str]:
    return [key for key, _rel, _line in _calls("unknown")]


def _respelled_sites() -> list[str]:
    """Refusals still composed by `bag.error` with an unknown-name sentence."""
    out: list[str] = []
    for key, rel, line in _calls("error"):
        words = key.split("::", 2)[2].lower()
        if " unknown" in f" {words}" or "unresolved name" in words or "is unknown" in words:
            out.append(f"{rel}:{line}  {key}")
    return out


# --------------------------------------------------------------------------
# The witnesses: one slip per site, planted in a real game.
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class Slip:
    """A one-place edit of a real game (or a library body) that reaches one
    refusal site. `marker` picks the refusal's rendered line; `meant` is the
    declared name a Near Miss must offer."""

    source: str  # a repo-relative game path, or `library:` + a library body
    old: str
    new: str
    marker: str
    meant: str


_LIB_HEAD = "library nm_probe {\n  requires { score : Integer }\n  function helper() = 1\n"

WITNESSES: dict[str, Slip] = {
    # Game clauses.
    "resolve::_apply_uses::unknown {} — `uses` names a family library in docs/libra": Slip(
        "docs/games/five-card-draw.cardlang", "uses poker_betting", "uses poker_beting",
        "unknown library 'poker_beting'", "poker_betting"),
    "resolve::_resolve_component_set::unknown deck '{}' — known decks: {}": Slip(
        "docs/games/hearts.cardlang", "cards: standard52", "cards: standard53",
        "unknown deck 'standard53'", "standard52"),
    "resolve::_resolve_component_set::unknown piece set '{}' — known piece sets: {}": Slip(
        "docs/games/breakthrough.cardlang", "pieces: breakthrough_men", "pieces: breakthru_men",
        "unknown piece set 'breakthru_men'", "breakthrough_men"),
    "resolve::_resolve_direction::unknown direction '{}' — declare {} (omitting the clause ": Slip(
        "docs/games/hearts.cardlang", "direction: clockwise", "direction: clockwize",
        "unknown direction 'clockwize'", "clockwise"),
    "resolve::_resolve_ranking::ranking: names unknown rank '{}' — not a rank of deck '{}' (k": Slip(
        "docs/games/hearts.cardlang", "ranking: aces high", "ranking: aces hgih",
        "unknown rank 'hgih'", "aces high"),
    "resolve::_resolve_card_points::card_points names unknown rank '{}' — not a rank of deck '": Slip(
        "docs/games/cribbage.cardlang", "J: 10  Q: 10  K: 10", "J: 10  Q: 10  KK: 10",
        "card_points names unknown rank 'KK'", "K"),
    "resolve::_resolve_suit_ranking::suit ranking: '{}' is not a suit of deck '{}' — list {} strong": Slip(
        "docs/games/bridge.cardlang", "suit ranking: spades hearts diamonds clubs",
        "suit ranking: spades hearts diamonds clbs", "suit ranking: 'clbs'", "clubs"),
    "resolve::_resolve_board::unknown board family '{}' (registered families: {})": Slip(
        "docs/games/breakthrough.cardlang", "board: grid(8, 8)", "board: gird(8, 8)",
        "unknown board family 'gird'", "grid"),
    "catalogue_pass::_check_sequence::`sequence:` names `{}`, which is no rank of `{}`": Slip(
        "docs/games/big-two.cardlang", "sequence: A 2 3 4 5 6 7 8 9 10 J Q K A",
        "sequence: A 2 3 4 5 6 7 8 9 10 J Q KK A", "`sequence:` names `KK`", "K"),
    # Zones and declared types.
    "resolve::_resolve_zone::unknown index role '{}'": Slip(
        "docs/games/hearts.cardlang", "hand[player]     : Hand<player>",
        "hand[playr]     : Hand<player>", "unknown index role 'playr'", "player"),
    "resolve::_resolve_zone::unknown zone type '{}'": Slip(
        "docs/games/hearts.cardlang", "hand[player]     : Hand<player>",
        "hand[player]     : Hnad<player>", "unknown zone type 'Hnad'", "Hand"),
    "resolve::_resolve_zone::unknown owner '{}'": Slip(
        "docs/games/hearts.cardlang", "hand[player]     : Hand<player>",
        "hand[player]     : Hand<playr>", "unknown owner 'playr'", "player"),
    "resolve::_validate_refs::unknown type '{}' in declaration of {}": Slip(
        "docs/games/hearts.cardlang", "cumulative_score[player] : Integer = 0",
        "cumulative_score[player] : Integr = 0", "unknown type 'Integr'", "Integer"),
    "resolve::_check_declared_type_names::unknown type '{}' in parameter '{}' of function {}": Slip(
        "docs/games/belote.cardlang", "function is_trump(card : Card) =",
        "function is_trump(card : Crad) =", "unknown type 'Crad'", "Card"),
    "resolve::_check_declared_type_names::unknown type '{}' in payload of case '{}'": Slip(
        "docs/games/bridge.cardlang", "contract_finalized(Player, Integer, Suit?, Integer)",
        "contract_finalized(Player, Integr, Suit?, Integer)", "unknown type 'Integr'", "Integer"),
    "resolve::_check_move_params::move {} has unsupported parameter domain '{}' (expected {}){}": Slip(
        "docs/games/belote.cardlang", "move_type take_suit(s : Suit) {",
        "move_type take_suit(s : Siut) {", "unsupported parameter domain 'Siut'", "Suit"),
    "resolve::_check_procedures::procedure parameter '{}: {}' has an unsupported domain — proce": Slip(
        "docs/games/cheat.cardlang", "procedure resolve_play(who : Player) {",
        "procedure resolve_play(who : Playr) {", "'who: Playr' has an unsupported domain", "Player"),
    "resolve::_instantiate_rules::argument for rule parameter '{}: Suit'{} must be a suit literal": Slip(
        "docs/games/hearts.cardlang", "active_rules: [+ NoLeadingSuitUntilBroken(hearts)]",
        "active_rules: [+ NoLeadingSuitUntilBroken(heart)]", "must be a suit literal", "hearts"),
    # The primitives block.
    "resolve::_check_primitive_name::nothing implements the Primitive `{}` — a `primitives` entr": Slip(
        "docs/games/cribbage.cardlang", "peg_pair_points() : Integer                 reads play_pile",
        "peg_pair_point() : Integer                 reads play_pile",
        "nothing implements the Primitive `peg_pair_point`", "peg_pair_points"),
    "resolve::_check_primitive_reads::`{}` reads `{}`, which this game declares in neither `zones ": Slip(
        "docs/games/cribbage.cardlang", "peg_pair_points() : Integer                 reads play_pile",
        "peg_pair_points() : Integer                 reads play_pil", "reads `play_pil`", "play_pile"),
    "resolve::_check_read_tail::`{}` reads `{} in {}`, but this game declares no phase `{}`{} — ": Slip(
        "docs/games/cribbage.cardlang", "dealer in hand_sequence", "dealer in hand_sequenc",
        "declares no phase `hand_sequenc`", "hand_sequence"),
    "resolve::_check_read_tail::`{}` reads `{} in {}`, but phase `{}` declares no state `{}`{}": Slip(
        "docs/games/cribbage.cardlang", "seq_bits in play,", "seq_bit in play,",
        "declares no state `seq_bit`", "seq_bits"),
    # Rules, phases, modes.
    "resolve::_resolve_phase_item::active_rules names undefined rule '{}'": Slip(
        "docs/games/hearts.cardlang", "active_rules: [MustFollowSuit, MustLeadTwoOfClubs]",
        "active_rules: [MustFolowSuit, MustLeadTwoOfClubs]", "undefined rule 'MustFolowSuit'",
        "MustFollowSuit"),
    "resolve::_check_rule_reaches_a_reader::rule {} constrains unknown move type '{}'": Slip(
        "docs/games/hearts.cardlang", "constrains: play_to_trick", "constrains: play_to_trik",
        "constrains unknown move type 'play_to_trik'", "play_to_trick"),
    "resolve::_resolve_phase_item::legal_moves names unknown move type '{}'": Slip(
        "docs/games/hearts.cardlang", "[transfer_between_hands]", "[transfer_between_hand]",
        "legal_moves names unknown move type", "transfer_between_hands"),
    "resolve::_resolve_transition::transition_to target '{}' is not a sibling mode of this phase ": Slip(
        "docs/games/hearts.cardlang", "transition_to: hearts_broken when",
        "transition_to: hearts_brokn when", "transition_to target 'hearts_brokn'", "hearts_broken"),
    "resolve::_resolve_transition::transition event names unknown move type '{}'": Slip(
        "docs/games/hearts.cardlang", "when play_to_trick where", "when play_to_trik where",
        "transition event names unknown move type", "play_to_trick"),
    # Statements and expressions.
    "resolve::_rewrite::unresolved name '{}'{}": Slip(
        "docs/games/hearts.cardlang", "move all cards to deck", "move all cards to dekc",
        "unresolved name 'dekc'", "deck"),
    "resolve::_validate_refs::call to unknown function '{}'": Slip(
        "docs/games/hearts.cardlang", "leader := player_holding(2 of clubs)",
        "leader := player_holdin(2 of clubs)", "unknown function 'player_holdin'", "player_holding"),
    "resolve::_validate_refs::unknown rank '{}' in card literal": Slip(
        "docs/games/hearts.cardlang", "elif card is Q of spades", "elif card is QQ of spades",
        "unknown rank 'QQ'", "Q"),
    "resolve::_validate_refs::unknown suit '{}' in card literal": Slip(
        "docs/games/hearts.cardlang", "elif card is Q of spades", "elif card is Q of spdes",
        "unknown suit 'spdes'", "spades"),
    "resolve::_validate_refs::rotate through unknown value '{}'": Slip(
        "docs/games/hearts.cardlang", "rotate pass_direction through [left, right, across, hold]",
        "rotate pass_direction through [left, rihgt, across, hold]", "unknown value 'rihgt'", "right"),
    "resolve::_validate_refs::{} references unknown variable '{}'": Slip(
        "docs/games/hearts.cardlang", "winner: lowest cumulative_score",
        "winner: lowest cumulative_scor", "unknown variable 'cumulative_scor'", "cumulative_score"),
    "resolve::_validate_refs::`again {}`: names no declared state variable — the go-again flag": Slip(
        "docs/games/five-card-draw.cardlang", "again more {", "again mroe {", "`again mroe`", "more"),
    "resolve::_rewrite::round `trump` names '{}', which is neither a suit of this deck ({})": Slip(
        "docs/games/bridge.cardlang", "winner highest_trump_or_led_suit trump trump_suit",
        "winner highest_trump_or_led_suit trump trump_sut", "`trump` names 'trump_sut'", "trump_suit"),
    "resolve::_rewrite::`{}` is no row label of this game's catalogue — a play's `.shape` ": Slip(
        "docs/games/big-two.cardlang", "elif play.shape is quads then", "elif play.shape is quad then",
        "`quad` is no row label", "quads"),
    "resolve::_check_domain_query::`{}` ranges over a position domain's members, and `{}` is no": Slip(
        "docs/games/hearts.cardlang", "demands: cards in hand where card is 2 of clubs",
        "demands: crads in hand where card is 2 of clubs", "`crad` is no position domain", "cards"),
    "resolve::_check_domain_query::unknown {} '{}' -- {}": Slip(
        "docs/games/hearts.cardlang", "if any player where base[player] is 26 {",
        "if any playr where base[player] is 26 {", "'playr'", "player"),
    "resolve::_validate_refs::unknown `for each` role '{}' (expected one of {})": Slip(
        "docs/games/hearts.cardlang", "for each player p:", "for each playr p:",
        "`for each` role 'playr'", "player"),
    "resolve::_check_offering_moves::offer names unknown move type '{}'": Slip(
        "docs/games/hearts.cardlang", "[charge_the_others, credit_the_shooter]",
        "[charge_the_other, credit_the_shooter]", "offer names unknown move type", "charge_the_others"),
    "resolve::_check_procedures::run of unknown procedure '{}'": Slip(
        "docs/games/five-card-draw.cardlang", "run betting_street(first_actor, 2, 0)",
        "run betting_stret(first_actor, 2, 0)", "unknown procedure 'betting_stret'", "betting_street"),
    "resolve::_validate_refs::produces names unknown outcome phase '{}'": Slip(
        "docs/games/bridge.cardlang", "auction produces:", "auctoin produces:",
        "unknown outcome phase 'auctoin'", "auction"),
    # Rounds.
    "resolve::_validate_refs::round source zone '{}' is unknown": Slip(
        "docs/games/hearts.cardlang", "from leader over all players source hand",
        "from leader over all players source hnad", "round source zone 'hnad'", "hand"),
    "resolve::_validate_refs::round play zone '{}' is unknown": Slip(
        "docs/games/hearts.cardlang", "source hand into trick_pile", "source hand into trick_pil",
        "round play zone 'trick_pil'", "trick_pile"),
    "resolve::_validate_refs::round move type '{}' is unknown": Slip(
        "docs/games/hearts.cardlang", "round play_to_trick from", "round play_to_trik from",
        "round move type 'play_to_trik'", "play_to_trick"),
    "resolve::_validate_refs::trick round winner '{}' is not a trick winner function": Slip(
        "docs/games/hearts.cardlang", "winner highest_of_led_suit", "winner highest_of_lead_suit",
        "trick round winner 'highest_of_lead_suit'", "highest_of_led_suit"),
    "resolve::_validate_refs::round early-termination predicate '{}' is unknown": Slip(
        "docs/games/getaway.cardlang", "winner highest_of_led_suit early on_play_off_led_suit",
        "winner highest_of_led_suit early on_play_of_led_suit", "'on_play_of_led_suit' is unknown",
        "on_play_off_led_suit"),
    "resolve::_validate_refs::climb round source zone '{}' is unknown": Slip(
        "docs/games/big-two.cardlang", "              source hand into trick_pile",
        "              source hnad into trick_pile", "climb round source zone 'hnad'", "hand"),
    "resolve::_validate_refs::climb round play zone '{}' is unknown": Slip(
        "docs/games/big-two.cardlang", "source hand into trick_pile", "source hand into trick_pil",
        "climb round play zone 'trick_pil'", "trick_pile"),
    "resolve::_validate_refs::climb round move type '{}' is unknown": Slip(
        "docs/games/big-two.cardlang", "round climb play_combination from",
        "round climb play_combinaton from", "climb round move type 'play_combinaton'",
        "play_combination"),
    "resolve::stamp::climb round `combinations` query '{}' is not a combination lead q": Slip(
        "docs/games/big-two.cardlang", "combinations big_two follows", "combinations big_tw follows",
        "`combinations` query 'big_tw'", "big_two"),
    "resolve::stamp::climb round over the catalogue '{}': `follows` names '{}', which is ": Slip(
        "docs/games/big-two.cardlang", "combinations big_two follows big_two_follows",
        "combinations big_two follows big_two_folows", "`follows` names 'big_two_folows'",
        "big_two_follows"),
    "resolve::stamp::climb round `follows` query '{}' is not a combination follows query; ": Slip(
        "docs/games/tichu.cardlang", "combinations tichu_lead_options follows tichu_follows",
        "combinations tichu_lead_options follows tichu_folows", "`follows` query 'tichu_folows'",
        "tichu_follows"),
    # A family library's contract, answered by the importing game.
    "resolve::_check_definition_requirement::{}, which game '{}' does not define — add {}{}": Slip(
        "docs/games/five-card-draw.cardlang", "move_type fold {", "move_type fol {",
        "requires move type `fold`", "fold"),
    "resolve::_check_requires::{} requires state {}, which game '{}' does not declare — add ": Slip(
        "docs/games/five-card-draw.cardlang", "stack[player]     : Integer = 100",
        "stak[player]     : Integer = 100", "requires state `stack", "stack"),
    "resolve::_check_zone_requirement::{} requires zone {}, which game '{}' does not declare — ad": Slip(
        "experiments/green-lane/variants/v2-bounty-mini.cardlang", "shipment[player]",
        "shipmnt[player]", "requires zone `shipment", "shipment"),
    # A family library's own text.
    "resolve::_check_library_encapsulation::{} reads '{}', which is neither in its `requires` contract n": Slip(
        "library:" + _LIB_HEAD + "  function probe(p : Player) = score\n}\n", "= score", "= scor",
        "reads 'scor'", "score"),
    "resolve::_check_library_encapsulation::{} calls '{}', which is neither defined in the library nor ": Slip(
        "library:" + _LIB_HEAD + "  function probe(p : Player) = helper()\n}\n", "= helper()",
        "= helpr()", "calls 'helpr'", "helper"),
    "resolve::_check_library_encapsulation::{} names the {} '{}', which the library does not have — i": Slip(
        "library:" + _LIB_HEAD + "  function probe(c : Card) = 1\n}\n", "c : Card", "c : Crad",
        "'Crad', which the library does not have", "Card"),
    # The type layer.
    "typecheck::_check_enum_literal::{} is not a {} value of this deck": Slip(
        "docs/games/hearts.cardlang", "where action.card.suit is hearts",
        'where action.card.suit is "heart"', '"heart" is not a Suit value', "hearts"),
    "typecheck::_check_expr::a round publishes no `{}` — `state.` names a round's published": Slip(
        "docs/games/hearts.cardlang", "applies_when: state.led_suit is none",
        "applies_when: state.led_sut is none", "publishes no `led_sut`", "led_suit"),
    "typecheck::_check_expr::{} has no field '{}' (its fields are {})": Slip(
        "docs/games/hearts.cardlang", "where action.card.suit is hearts",
        "where action.card.siut is hearts", "has no field 'siut'", "suit"),
    "typecheck::_check_expr::a Combination has no field `{}` — its one field is `shape`, and ": Slip(
        "docs/games/big-two.cardlang", "if play.shape is straight_flush then",
        "if play.shap is straight_flush then", "no field `shap`", "shape"),
    "typecheck::_check_transfer::movements move cards; '{}' is not a supported item noun (re": Slip(
        "docs/games/hearts.cardlang", "move all cards from trick_pile to captured[winner]",
        "move all crads from trick_pile to captured[winner]", "'crads' is not a supported item noun",
        "cards"),
    "typecheck::_check_produce_stmt::{} produces unknown outcome case '{}'": Slip(
        "docs/games/bridge.cardlang", "produce all_pass", "produce all_pas",
        "unknown outcome case 'all_pas'", "all_pass"),
    "typecheck::_check_produces::produces names unknown outcome case '{}' of '{}'": Slip(
        "docs/games/bridge.cardlang", "contract_finalized(d, level, strain, dbl) {",
        "contract_finalised(d, level, strain, dbl) {", "outcome case 'contract_finalised'",
        "contract_finalized"),
    "typecheck::walk::continue to '{}' is not a later sibling phase": Slip(
        "docs/games/bridge.cardlang", "continue to play", "continue to paly",
        "continue to 'paly'", "play"),
}

# The bare-name axis: one slip per kind of name a bare identifier resolves as.
REF_KIND_WITNESSES: dict[n.RefKind, Slip] = {
    "local": Slip("docs/games/hearts.cardlang", "if p is not shooter {", "if p is not shoter {",
                  "unresolved name 'shoter'", "shooter"),
    "state_var": Slip("docs/games/hearts.cardlang", "cumulative_score[player] >= 100",
                      "cumulative_scor[player] >= 100", "unresolved name 'cumulative_scor'",
                      "cumulative_score"),
    "zone": Slip("docs/games/hearts.cardlang", "move all cards to deck", "move all cards to dekc",
                 "unresolved name 'dekc'", "deck"),
    "enum_value": Slip("docs/games/hearts.cardlang", "where action.card.suit is hearts",
                       "where action.card.suit is heart", "unresolved name 'heart'", "hearts"),
    "bool": Slip("docs/games/hearts.cardlang", "applies_when: state.led_suit is none",
                 "applies_when: ture", "unresolved name 'ture'", "true"),
    "null": Slip("docs/games/hearts.cardlang", "applies_when: state.led_suit is none",
                 "applies_when: state.led_suit is nnoe", "unresolved name 'nnoe'", "none"),
    "pronoun": Slip("docs/games/hearts.cardlang", "let shooter = actor", "let shooter = actr",
                    "unresolved name 'actr'", "actor"),
    "play_source": Slip("docs/games/hearts.cardlang", "demands: cards in hand where card is 2 of clubs",
                        "demands: cards in hnad where card is 2 of clubs", "unresolved name 'hnad'",
                        "hand"),
}


def _rendered_errors(slip: Slip) -> list[str]:
    """Every error line the slipped source renders, primary and collected."""
    if slip.source.startswith("library:"):
        from cardlang.resolve import _check_library_encapsulation

        text = slip.source.removeprefix("library:")
        if slip.old not in text:
            pytest.fail(f"the library body no longer holds {slip.old!r}: re-plant this slip")
        bag = DiagnosticBag()
        _check_library_encapsulation(parse_library(text.replace(slip.old, slip.new, 1), "nm_probe.cardlang"), bag)
        return [line for d in bag.items for line in d.format().splitlines()]
    path = _ROOT / slip.source
    text = path.read_text()
    if slip.old not in text:
        pytest.fail(f"{slip.source} no longer holds {slip.old!r}: re-plant this slip")
    try:
        check_dsl(text.replace(slip.old, slip.new, 1), slip.source)
    except DiagnosticError as exc:
        lines = str(exc).splitlines()
        for note in getattr(exc, "__notes__", []):
            lines.extend(note.splitlines())
        return [line for line in lines if ": error: " in line]
    pytest.fail(f"the slip {slip.new!r} in {slip.source} checks clean")


def _offered(slip: Slip) -> str:
    """The refusal line the slip's site renders; the precondition that the
    slip still reaches its site fails the row outside the designed red."""
    hits = [line for line in _rendered_errors(slip) if slip.marker in line]
    if not hits:
        pytest.fail(f"no refusal names {slip.marker!r}: the slip no longer reaches its site")
    return hits[0]


def _assert_offers(slip: Slip) -> None:
    line = _offered(slip)
    assert "did you mean " in line, f"no Near Miss offered: {line}"
    clause = line.split("did you mean ", 1)[1]
    assert f"`{slip.meant}`" in clause, f"{slip.meant!r} not offered: {line}"


@_DESIGNED_RED
@pytest.mark.parametrize("site", sorted(WITNESSES))
def test_a_refused_name_is_offered_the_declared_name_it_nearly_spells(site: str) -> None:
    _assert_offers(WITNESSES[site])


@_DESIGNED_RED
@pytest.mark.parametrize("kind", sorted(REF_KIND_WITNESSES))
def test_a_bare_name_of_every_ref_kind_is_offered_its_near_miss(kind: n.RefKind) -> None:
    _assert_offers(REF_KIND_WITNESSES[kind])


def test_every_ref_kind_has_a_witness() -> None:
    """red under: deleting any entry of `REF_KIND_WITNESSES`, or adding a
    member to `cardlang.ast.nodes.RefKind`."""
    assert set(REF_KIND_WITNESSES) == set(n.REF_KINDS)


@_DESIGNED_RED
def test_every_owner_site_has_a_witness_and_every_witness_a_site() -> None:
    sites = _owner_sites()
    assert len(sites) == len(set(sites)), f"two owner sites share a key: {sorted(sites)}"
    assert set(sites) == set(WITNESSES), (
        f"routed with no witness: {sorted(set(sites) - set(WITNESSES))}; "
        f"witnessed but not routed: {sorted(set(WITNESSES) - set(sites))}"
    )


@_DESIGNED_RED
def test_no_refusal_spells_its_own_unknown_name_sentence() -> None:
    assert _respelled_sites() == []


# --------------------------------------------------------------------------
# Misuse probes: the slips an author plausibly makes that the owner must not
# answer wrongly.
# --------------------------------------------------------------------------

_PROBES: dict[str, tuple[Slip, bool]] = {
    # (slip, whether a Near Miss is offered at all); `meant` is what must be
    # offered when one is, and what must NOT be offered when none is.
    "nothing resembles the spelling": (
        Slip("docs/games/hearts.cardlang", "move all cards to deck", "move all cards to xq",
             "unresolved name 'xq'", "deck"), False),
    "a case slip": (
        Slip("docs/games/hearts.cardlang", "move all cards to deck", "move all cards to Deck",
             "unresolved name 'Deck'", "deck"), True),
    "a name of another namespace is never offered": (
        Slip("docs/games/hearts.cardlang", "[charge_the_others, credit_the_shooter]",
             "[capturd, credit_the_shooter]", "offer names unknown move type 'capturd'", "captured"),
        False),
    "a quantifier noun misspelled": (
        Slip("docs/games/hearts.cardlang", "if any player where base[player] is 26 {",
             "if any playr where base[player] is 26 {", "'playr'", "player"), True),
    "a ranking convention misspelled": (
        Slip("docs/games/hearts.cardlang", "ranking: aces high", "ranking: Aces Hihg",
             "unknown rank", "aces high"), True),
}


@pytest.mark.parametrize(
    "probe",
    [
        pytest.param(name, marks=_DESIGNED_RED) if offered else name
        for name, (_slip, offered) in sorted(_PROBES.items())
    ],
)
def test_a_misuse_probe_is_answered_rightly(probe: str) -> None:
    slip, offered = _PROBES[probe]
    if offered:
        _assert_offers(slip)
    else:
        line = _offered(slip)
        clause = line.split("did you mean ", 1)[1] if "did you mean " in line else ""
        assert f"`{slip.meant}`" not in clause, line


# --------------------------------------------------------------------------
# The owner itself.
# --------------------------------------------------------------------------


def _owner(name: str) -> object:
    found = getattr(diagnostics, name, None)
    assert found is not None, f"cardlang.diagnostics has no `{name}`"
    return found


@_DESIGNED_RED
def test_near_misses_are_ranked_most_alike_first_then_alphabetically_at_most_three() -> None:
    near_misses = _owner("near_misses")
    assert callable(near_misses)
    among = ["hands", "hand", "band", "land", "trick_pile", "xyz"]
    assert near_misses("hnad", among) == ("hand", "band", "hands")
    assert near_misses("hand", ["hand", "hands"]) == ("hands",)  # never the spelling itself
    assert near_misses("q", ["deck", "hand"]) == ()
    assert near_misses("DECK", ["deck"]) == ("deck",)


@_DESIGNED_RED
def test_a_diagnostic_renders_its_near_misses_as_one_clause() -> None:
    diagnostic_cls = _owner("Diagnostic")
    params = inspect.signature(diagnostic_cls).parameters  # type: ignore[arg-type]
    assert "near_misses" in params
    span = diagnostics.Span("g.cardlang", 0, 1, 3, 5)
    one = diagnostics.Diagnostic(diagnostics.Severity.ERROR, "unknown thing 'x'", span, near_misses=("a",))  # type: ignore[call-arg]
    three = diagnostics.Diagnostic(
        diagnostics.Severity.ERROR, "unknown thing 'x'", span, near_misses=("a", "b", "c")  # type: ignore[call-arg]
    )
    assert one.format() == "g.cardlang:3:5: error: unknown thing 'x'; did you mean `a`?"
    assert three.format() == "g.cardlang:3:5: error: unknown thing 'x'; did you mean `a`, `b` or `c`?"


@_DESIGNED_RED
def test_the_parse_layer_ranks_by_the_one_measure() -> None:
    import cardlang.parse as parse

    resemblance = _owner("resemblance")
    assert getattr(parse, "resemblance", None) is resemblance


def test_ref_kinds_are_a_closed_literal() -> None:
    """The bare-name axis is the resolver's dispatch domain, not a sample of
    it. red under: widening `RefKind` to `str`."""
    assert n.REF_KINDS == get_args(n.RefKind) and n.REF_KINDS
