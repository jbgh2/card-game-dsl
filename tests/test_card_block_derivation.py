"""The card block is reserved for the games that can decide a content item.

`ActionSpace` lays its ids out in blocks, and the card block is the home of
every id that names a content item — a bare `Card` drawn from a zone, and a
Card-parameterized move's `(name, card)` candidate, which `encode` folds onto
the same id (decisions.md "Declared parameter domains", OpenSpiel encoding).
A game none of whose decisions can produce such a candidate needs no card
block, and reserving one sizes `num_distinct_actions` — OpenSpiel's action
dimension — past anything the game can offer.

The two error directions are not symmetric, and the machinery here is shaped
by that. Reserving a block a game cannot use wastes ids; FAILING to reserve
one it can use hands a live decision no id, so `encode` would mint an id
inside the next block's range — a silent wrong answer. The derivation is
therefore built to fail toward PRESENT, and the absent case is guarded at run
time (`ActionSpace.encode`), so a miss stops the game instead of renumbering
it.

Completeness ledger (decisions.md "Closed-domain completeness"):

property:        the card block is present exactly when some decision the game
                 can reach offers a candidate `encode` routes to that block,
                 and a game whose block is absent REFUSES such a candidate
                 loudly rather than encoding it into a neighbouring block.
domain:          two crossed axes, each derived from its registry in code.
                 (1) `runtime.delegation.DECISION_POINTS` — the engine's own
                 enumeration of every `ctx.chooser` call site — crossed with
                 the configurations that make a site content-valued or not,
                 each isolated in a minimal game below. That registry is
                 what makes the axis total: a decision can only arise at a
                 chooser call site, the site list is reconciled against an AST
                 scrape by tests/test_delegated_play.py, and every site is
                 either isolated here or carries its reason. (2) Every game in
                 the adapter's registry, `cardlang.openspiel.game.GAMES`,
                 whose static answer is checked against what a played line
                 actually offers. Board games are in-domain on both axes: a
                 board's pieces are the deck's content items and share the
                 block.
registry:        axis 1: `cardlang.runtime.delegation.DECISION_POINTS`;
                 axis 2: `cardlang.openspiel.game.GAMES`;
                 site-list totality:
                 tests/test_delegated_play.py::test_every_decision_point_is_classified;
                 verb-image agreement:
                 tests/test_openspiel_encoding.py::test_declared_verbs_are_exactly_the_verbs_ids_produce.
does not prove:  a green execution row does NOT prove a game whose block is
                 absent can never offer a content item — a played line
                 samples the reachable decisions, it does not enumerate them.
                 The rows run one direction only: whatever a line DOES offer,
                 the static answer must already have said PRESENT. What backs
                 the other direction is not a row here but the runtime
                 refusal, which turns a wrong absent into a stopped game.
"""

from __future__ import annotations

import random
from typing import Any

import pytest

from cardlang.openspiel.encoding import CARD_VERB, ActionSpace
from cardlang.pipeline import check_dsl
from cardlang.runtime.delegation import DECISION_POINTS
from cardlang.runtime.driver import play_game
from cardlang.runtime.values import Card

# =============================================================================
# Axis 1 — one minimal game per decision-point configuration
#
# Each is a complete game the driver plays to a result, carrying exactly ONE
# decision-bearing construct, so the block it induces is that construct's
# alone. The deal is the deck order (nothing shuffles), so a line is fixed.
# =============================================================================

_BASE = """
game {name} {{
  players: 2
  max_length: 200
  cards: standard52
  ranking: A K Q J 10 9 8 7 6 5 4 3 2

  zones {{
    deck         : Deck
    hand[player] : Hand<player>
    pile[player] : PlayerPile<player>
    trick_pile   : TrickPile
  }}

  state {{
    score[player] : Integer = 0
    done          : Boolean = false
  }}

  phase deal {{
    deal 3 cards from deck to each hand
  }}

  phase play {{
{body}
  }}

  phase scoring {{
    for each player p: score[p] := number of cards in pile[p]
  }}

  winner: highest score
}}

{move_types}
"""


class Arm:
    """One decision-point configuration: the game that isolates it, the
    decision point it exercises, and whether that configuration needs the
    card block."""

    def __init__(
        self,
        name: str,
        site: str,
        present: bool,
        body: str,
        move_types: str = "",
        plays: bool = True,
        why_unplayed: str = "",
    ) -> None:
        self.name = name
        self.site = site
        self.present = present
        self.body = body
        self.move_types = move_types
        self.plays = plays
        self.why_unplayed = why_unplayed

    def game(self) -> Any:
        camel = "".join(part.title() for part in self.name.split("_"))
        return check_dsl(
            _BASE.format(name=f"Arm{camel}", body=self.body, move_types=self.move_types),
            f"{self.name}.cardlang",
        )


ARMS: list[Arm] = [
    # --- mechanics.run_decision_round: the three round forms ---------------
    Arm(
        "trick",
        "mechanics.run_decision_round",
        True,
        """    legal_moves: [play_to_trick]
    round play_to_trick from 0 over all players source hand into trick_pile
          winner highest_of_led_suit
    move all cards from trick_pile to pile[winner]""",
    ),
    Arm(
        "auction_nullary",
        "mechanics.run_decision_round",
        False,
        """    round offering [yield_bid] from 0 over all players until done""",
        move_types="""move_type yield_bid {
  effect { done := true }
}""",
    ),
    Arm(
        "auction_card_param",
        "mechanics.run_decision_round",
        True,
        """    round offering [toss] from 0 over all players until done""",
        move_types="""move_type toss(c : Card) {
  effect { done := true }
}""",
    ),
    # --- execute._select / _select_filtered / _select_joint -----------------
    Arm(
        "select_chosen",
        "execute._select",
        True,
        """    for each player p:
      move chosen 1 card from hand[p] to pile[p]""",
    ),
    Arm(
        "select_filtered",
        "execute._select_filtered",
        True,
        """    for each player p:
      move chosen 1 card from hand[p] where card.suit is clubs to pile[p]""",
    ),
    Arm(
        "select_joint",
        "execute._select_joint",
        False,
        """    for each player p:
      move chosen some cards from hand[p]
           where jointly gin_valid_meld(cards) to pile[p]""",
        plays=False,
        why_unplayed=(
            "a joint predicate must root in a registered subset codec, and "
            "every registered one belongs to a primitive module bound to ONE "
            "game file (`reads.PRIMITIVE_READS`), so no synthetic game may "
            "call it — issue #232. The static cell below still runs; only the "
            "execution cross-check is out of reach for this arm."
        ),
    ),
    # --- execute._offer -----------------------------------------------------
    Arm(
        "offer_nullary",
        "execute._offer",
        False,
        """    offer to 0 one of [take]""",
        move_types="""move_type take {
  effect { move 1 card from hand[0] to pile[0] }
}""",
    ),
    Arm(
        "offer_card_param",
        "execute._offer",
        True,
        """    offer to 0 one of [lay]""",
        move_types="""move_type lay(c : Card) {
  effect { move 1 card from hand[0] to pile[0] }
}""",
    ),
    # --- execute._pass_selection -------------------------------------------
    Arm(
        "pass_simultaneous",
        "execute._pass_selection",
        True,
        """    each player simultaneously:
      move chosen 1 card from hand[player] to pile[player]""",
    ),
    # --- evaluate._choose ---------------------------------------------------
    Arm(
        "choose_integer",
        "evaluate._choose",
        False,
        """    for each player p:
      score[p] := choose integer in 0 .. 3""",
    ),
]


def test_every_decision_point_has_an_isolating_arm() -> None:
    """Axis 1 is total against its registry: every chooser call site the engine
    has is exercised by at least one arm above, in both the configuration that
    needs the card block and the one that does not, where the site has both.

    Without this the arm list is a hand-written sample of the site list, and a
    new decision point would land with no cell — the hand-listed-axis defect
    (issue #380) one construct over.
    """
    covered = {arm.site for arm in ARMS}
    assert covered == set(DECISION_POINTS), (
        "decision points with no isolating arm: "
        f"{sorted(set(DECISION_POINTS) - covered)}; arms naming a site the "
        f"engine does not have: {sorted(covered - set(DECISION_POINTS))}"
    )


def _derivation_cells() -> list[Any]:
    """The arms, with the ones designed to FLIP marked. An arm expecting no
    block fails today — every game reserves one — so the mark is constrained to
    that assertion: an unconstrained `xfail` would count a harness crash or an
    import error as the designed red, which is the vacuously-green class
    wearing red."""
    return [
        pytest.param(
            arm,
            id=arm.name,
            marks=(
                []
                if arm.present
                else pytest.mark.xfail(strict=True, raises=AssertionError)
            ),
        )
        for arm in ARMS
    ]


@pytest.mark.parametrize("arm", _derivation_cells())
def test_the_arm_reserves_a_card_block_exactly_when_it_can_decide_a_card(
    arm: Arm,
) -> None:
    """The derivation cell. `verbs()` naming `CARD_VERB` is the block's public
    tell — it is the verb every card-block id reports."""
    space = ActionSpace.for_game(arm.game())
    assert (CARD_VERB in space.verbs()) is arm.present


@pytest.mark.parametrize(
    "arm", [a for a in ARMS if a.plays], ids=lambda a: a.name
)
def test_the_arms_played_line_agrees_with_its_declared_column(arm: Arm) -> None:
    """What makes the `present` column above MEASURED rather than asserted: an
    arm claims a block exactly when its own played line offers a candidate the
    block would number. Nothing here consults the derivation, so the column and
    the code under guard cannot agree by construction.

    red under: give `auction_nullary` a `move chosen 1 card` body without
    flipping its column — the line then offers a `Card` its column denies, and
    the cell fails (executed at authoring).
    """
    offered = _content_candidates_offered(arm.game())
    assert bool(offered) is arm.present, (
        f"{arm.name}: the played line offers {sorted(offered) or 'nothing'} "
        f"the card block would number, but the arm's column says "
        f"present={arm.present}"
    )


def _content_candidates_offered(game: Any) -> set[str]:
    """The kinds of card-block-numbered candidate a played line offers: a bare
    content item, or a Card-parameterized move's `(name, card)` pair, which
    `encode` folds onto the same id."""
    seen: set[str] = set()

    def chooser(player: int, candidates: list[Any], k: int) -> list[Any]:
        for c in candidates:
            if isinstance(c, Card):
                seen.add("Card")
            elif isinstance(c, tuple) and len(c) == 2 and isinstance(c[1], Card):
                seen.add("(move, Card)")
        return list(candidates)[:k]

    play_game(game, random.Random(0), chooser=chooser)
    return seen
