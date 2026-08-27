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
                 either isolated here or carries its reason. The games on this
                 axis are MINIMAL rather than borrowed from the corpus because
                 a corpus game carries several decision points at once and so
                 cannot isolate any of them — measured: removing the
                 `EachSimultaneous` arm from the derivation reddens one
                 synthetic arm here and no corpus game at all. (2) Every game
                 in the adapter's registry, `cardlang.openspiel.game.GAMES`,
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
from pathlib import Path
from typing import Any

import pytest

from cardlang.openspiel.encoding import (
    CARD_VERB,
    ActionSpace,
    _decides_a_content_item,
    card_to_action,
)
from cardlang.pipeline import check_dsl, check_source
import cardlang.openspiel.game as ogame  # registers the adapter's game table
from cardlang.runtime.chance import RefusingRandom, is_chance_free
from cardlang.runtime.delegation import DECISION_POINTS
from cardlang.runtime.driver import play_game
from cardlang.runtime.errors import ShadowGuardError
from cardlang.runtime.state import ChooserAbort
from cardlang.runtime.values import Card

GAMES_DIR = Path(__file__).resolve().parent.parent / "docs" / "games"

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
        builds_space: bool = True,
        why_no_space: str = "",
    ) -> None:
        self.name = name
        self.site = site
        self.present = present
        self.body = body
        self.move_types = move_types
        self.plays = plays
        self.why_unplayed = why_unplayed
        # Some configurations are refused by a guard unrelated to this
        # derivation, so no `ActionSpace` exists to read the block off. Their
        # cell asks the derivation directly — the property under test is its
        # answer, not the neighbouring guard's.
        self.builds_space = builds_space
        self.why_no_space = why_no_space

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
    Arm(
        # The configuration that makes `EachSimultaneous` unconditional rather
        # than a special case of the chosen-Transfer arm. `_pass_selection`
        # reads only `source` and `amount`, and `simultaneous_body_error`
        # checks neither `where` nor `joint` — so this body carries
        # `joint=True` and still draws BARE cards. A derivation keyed on
        # "chosen and not joint" reads it as deciding no content item and
        # leaves the block absent, while the game goes on offering cards.
        "pass_simultaneous_jointly",
        "execute._pass_selection",
        True,
        """    each player simultaneously:
      move chosen 2 cards from hand[player]
           where jointly (number of cards in cards) is 2 to pile[player]""",
        plays=False,
        why_unplayed="its cell asks the derivation directly; see why_no_space",
        builds_space=False,
        why_no_space=(
            "an inline joint predicate has no registered subset codec, so "
            "`for_game` refuses this game before any block is laid out — a "
            "guard about the COMBO block, unrelated to this derivation. The "
            "hole the arm pins is reachable in a game whose predicate does "
            "root in a registered codec."
        ),
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


@pytest.mark.parametrize("arm", ARMS, ids=lambda a: a.name)
def test_the_arm_reserves_a_card_block_exactly_when_it_can_decide_a_card(
    arm: Arm,
) -> None:
    """The derivation cell. `verbs()` naming `CARD_VERB` is the block's public
    tell — it is the verb every card-block id reports.

    red under: drop the `n.EachSimultaneous` arm from
    `encoding._decides_a_content_item` — `pass_simultaneous_jointly` fails and
    NOTHING ELSE DOES, the corpus row included (executed at authoring). That
    measurement is why these synthetic arms exist: every corpus game with a
    simultaneous pass also has a trick round, so the corpus cannot isolate the
    arm, and a derivation that lost it would ship green.
    """
    game = arm.game()
    if not arm.builds_space:
        mt_index = {m.name: m for m in game.move_types}
        assert _decides_a_content_item(game, mt_index) is arm.present
        return
    space = ActionSpace.for_game(game)
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


# =============================================================================
# The absent block's own behaviour — probed directly, because no corpus game
# reaches the refusal and code nothing executes is where the next defect sits
# =============================================================================


def _blockless() -> ActionSpace:
    """A space whose card block reserves no ids, built directly: the three
    states of the block parameter are `None` (standard 52), a list (derived),
    and the empty list (absent), and only the third is under probe here."""
    return ActionSpace([], ["check", "fold"], [], None, [])


def test_an_absent_block_reserves_no_ids_and_the_next_block_starts_at_zero() -> None:
    assert _blockless().num_distinct_actions == 2
    assert _blockless().decode(0) == "check"


def test_an_absent_block_declares_no_card_verb() -> None:
    """The claim `verbs()` makes must be one the ids can keep: with no block,
    no id reports `CARD_VERB`, so declaring it would advertise a verb the space
    cannot produce."""
    assert CARD_VERB not in _blockless().verbs()


@pytest.mark.expects_shadow_guard
def test_encoding_a_card_against_an_absent_block_is_refused_by_name() -> None:
    """The guarantee the execution rows cannot give. A line samples the
    decisions it reaches; this is what happens if the derivation is ever wrong
    about one it did not — the game stops, naming the derivation, instead of
    numbering the card into the bare-name block.

    `ShadowGuardError` is the type on purpose: the game is legal and the ENGINE
    is at fault, and the suite fails on that type wherever it is raised, so a
    derivation miss anywhere in the corpus surfaces as a test failure.
    """
    with pytest.raises(ShadowGuardError, match="card-block derivation"):
        _blockless().encode(Card("A", "clubs"))


def test_the_standard_and_absent_sentinels_do_not_collide() -> None:
    """`None` and `[]` must stay different states. Collapse them and an absent
    block is numbered as though it were the standard 52, so ids the space does
    not have become reachable.

    red under: widen `ActionSpace.__init__`'s `_name_base` from
    `card_block is None` to `not card_block` — the blockless space then claims
    52 card ids it does not hold and `decode(0)` dies instead of naming the
    first move (executed at authoring).
    """
    ace = Card("A", "clubs")
    standard = ActionSpace(None, ["check", "fold"], [], None, [])
    assert standard.encode(ace) == card_to_action(ace)
    assert standard.decode(standard.encode(ace)) == ace
    # The same id means different things in the two spaces, which is the whole
    # reason absence may not be spelled `None`.
    assert _blockless().decode(0) == "check"


def _content_candidates_offered(game: Any, seed: int = 0, bound: int = 0) -> set[str]:
    """The kinds of card-block-numbered candidate a played line offers: a bare
    content item, or a Card-parameterized move's `(name, card)` pair, which
    `encode` folds onto the same id.

    `bound` stops a long game early by refusing further draws; 0 plays it out.
    Stopping early can only SHRINK what a line offers, which is the safe
    direction for the one-way claim the callers make.
    """
    seen: set[str] = set()
    policy = random.Random(seed * 977 + 13)
    drawn = 0

    def chooser(player: int, candidates: list[Any], k: int) -> list[Any]:
        nonlocal drawn
        for c in candidates:
            if isinstance(c, Card):
                seen.add("Card")
            elif isinstance(c, tuple) and len(c) == 2 and isinstance(c[1], Card):
                seen.add("(move, Card)")
        drawn += 1
        if bound and drawn > bound:
            raise ChooserAbort(player, [])
        return policy.sample(candidates, k) if k > 1 else [policy.choice(candidates)]

    rng: Any = RefusingRandom(seed) if is_chance_free(game) else random.Random(seed)
    try:
        play_game(game, rng, chooser=chooser)
    except ChooserAbort:
        pass  # the bound, not a failure — see the docstring
    return seen


# =============================================================================
# Axis 2 — every registered game, static answer against a played line
# =============================================================================


@pytest.mark.parametrize(
    "path", sorted(set(ogame.GAMES.values())), ids=lambda p: p.removesuffix(".cardlang")
)
def test_no_registered_game_offers_a_card_its_space_cannot_number(path: str) -> None:
    """The soundness direction, on the real corpus: whatever a played line
    offers, that game's space must already reserve the block that numbers it.

    One direction only, and deliberately. A line samples the decisions it
    reaches, so it can witness that a block is NEEDED but never that one is
    unnecessary — a game reserving a block this line does not exercise is not a
    defect, it is the over-approximation the derivation is built to make. What
    would be a defect is the converse, and that is what fails here.

    red under: drop the `n.TrickRound` arm from
    `encoding._decides_a_content_item` — belote, bridge, getaway, oh-hell,
    pinochle and spades then offer cards into a space with no card block
    (executed at authoring).
    """
    game = check_source(GAMES_DIR / path)
    space = ActionSpace.for_game(game)
    offered = _content_candidates_offered(game, seed=0, bound=400)
    if offered:
        assert CARD_VERB in space.verbs(), (
            f"{path}: a played line offers {sorted(offered)}, which only the "
            f"card block numbers, but this game's space reserves none — those "
            f"candidates have no action id"
        )
