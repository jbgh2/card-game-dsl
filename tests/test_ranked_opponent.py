"""The opponent that plays by what a game declares: `--vs all=ranked`.

property:        `ranked` answers from its seat's view and the game's own
                 declarations, and states what it does with every block of
                 action ids the game's action space declares. At a card
                 decision it takes the trick with the cheapest card that takes
                 it, and where nothing on offer takes, throws the cheapest of
                 the suit the hand is long in or sheds the dearest card that
                 takes nothing, by the declared ranking and the direction the
                 game's `winner:` names; at a numeric
                 decision it answers near its hand's strength, counting a
                 fair share against the deck's suits; at a combination decision
                 it spends the fewest cards; at every other id it draws
                 uniformly, which the table states rather than leaves to be
                 noticed. A card of the trump suit takes a trick the suit led
                 cannot, the trump being the one the game's Trick Round
                 declares — read through the view where the round names a State
                 Variable rather than fixing a suit. A card decision is ranked
                 only while a trick is IN PROGRESS: an empty trick pile does not
                 mean a lead, and nothing the seat is handed tells a lead from a
                 hand passed to a neighbour. A game that declares a
                 `trick_order { }` of its own is one whose tricks it reads
                 nothing of, so those decisions are drawn too. A throw counts the suits of the zone
                 the decision plays from, which a game may seat with one player
                 and the cards with another. Seated at a table it reaches an
                 outcome a uniform draw does not: Spades' +500, which a uniform
                 table never scores.
domain:          Dispositions: every block `encoding.BLOCKS` declares, crossed
                 with what `ranked.DISPOSITIONS` says of it. The miniature,
                 `tests/fixtures/one_trick_known_best.cardlang`: ONE PLAYED
                 LINE per seed over `_SEEDS`, the ranked seat against `first`,
                 counted against what `first` and `random` take from that same
                 seat over those same seeds. That is a sample of lines and not
                 the position's tree — the tree's best line is computed knowing
                 the hidden hand, which no seat can know, so it is no standard
                 for a policy that sees only its own view. The table claims,
                 likewise one played line per seed: Spades over `_SPADES_SEEDS`
                 against `_SPADES_FLOOR`, Hearts over `_HEARTS_SEEDS` against
                 `_HEARTS_FLOOR`, each beside the uniform table on those seeds.
                 The delegated block: an offering decision compared against the
                 uniform draw it delegates to, and a card decision of a game
                 with its own Trick Order (Belote) against the same draw. The
                 trick rules, recomputed from the view and the declarations at
                 every decision they cover: the trump that takes where the suit
                 led cannot, and the number bid against the hand's strength
                 (Spades, the corpus's declared-trump game), and the trump a
                 Trick Round names in a State Variable rather than fixing (Oh
                 Hell). The card decision with no trick in progress is a built
                 view over Hearts, whose passing phase offers card ids exactly
                 as a lead does. The throw is three
                 built views, each a shape no corpus game reaches by chance: a
                 hand long in one suit with one card of it on offer; a decision
                 whose cards sit in another seat's zone (Bridge's dummy, played
                 by the declarer); and a doubled deck where two zones both hold
                 what is offered, which is drawn. Legality and purity over every
                 registered game come from the row pins in
                 tests/test_play_opponents.py, which `ranked` joins as a row.
                 The chooser-level ranking instrument (`tests/playout_policy.py`)
                 stays where it is and is not a second definition of this one:
                 it classifies Candidate VALUES at the runtime seam, and its
                 pin reconciles that domain against `runtime.observe.render`
                 and the OpenSpiel encoder — checks on the runtime's own
                 decision values, which nothing here covers.
registry:        blocks: `cardlang.openspiel.encoding.BLOCKS`; opponents:
                 `cardlang.openspiel.seat_policy.OPPONENTS`; games:
                 `cardlang.openspiel.registry.GAMES`; the declarations it
                 reads: the checked `n.Game` (`ranking`, `trick_order`,
                 `trump`, `winner`), and `stdlib.zones.ZONE_PROJECTIONS` for
                 which of its own zones are private to it. The zone a card
                 decision plays from is derived from the view instead, by the
                 cards on offer: no declaration says which zone a decision
                 draws from, and the registry states a zone's visibility and
                 its capacity but not whether it is one a seat plays from
                 (issue #711).
does not prove:  That `ranked` plays a game well. It reads no game's own
                 strategy: it ignores partners, position, what has already been
                 played, and every state variable, and it draws uniformly at
                 every offering — so a game whose decisions are offerings is
                 played as a uniform draw plays it, Tichu's calls included
                 (issue #703, and the wall issue #553 leaves standing). A game
                 that declares no ranking has nothing here to rank by, and the
                 disposition says so rather than pretending otherwise. A trump
                 a game keeps in a state variable rather than in `trump:` is
                 invisible here, and the opponent plays the suit led as though
                 there were none; the corpus declares no such game today, and a
                 declared `trick_order { }` is drawn rather than guessed at.
                 Two arms are STATED AND NOT MEASURED, because no corpus game
                 reaches either: a game declaring a second trick pile is drawn,
                 and no registered game declares two, so nothing here would
                 redden if the guard went; and the bid reads the seat's own
                 private zones, which the decision-source derivation cannot
                 correct for it, an integer carrying no card back to a zone —
                 a game that bid from a hand held by another seat would be
                 counted wrong and no cell would say so (issue #711). The
                 drawn arm costs play, and only where a deck repeats a card: of
                 the registered games that reach a throw at all over three
                 seeds — Bridge, Cribbage, Oh Hell, Pinochle, Spades — only
                 Pinochle's doubled deck ever leaves the source undecidable,
                 30 throws of 98 there and none in the other four (measured
                 2026-09-16 on this branch, `ranked` at every seat). Nothing
                 here measures it against a competent player; the claims are
                 all against a uniform draw.

                 Three limits are STATED, each with its measurement:

                 (1) It never chooses a LEAD. An empty trick pile cannot be told
                 from a pass or a discard, so every lead is drawn — about one
                 card decision in four at a 13-trick game. Issue #713 is the
                 fact that would return it: the view does not say which decision
                 a seat is at, though the game declares it as a phase.

                 (2) A number decision is answered as a BID on the hand, which
                 is what Oh Hell and Spades ask and NOT what Cheat asks — there
                 the number is the count a player claims to be playing and may
                 be lying about. Answering a bluff by hand strength plays a
                 different game; it is legal, and it is wrong. Drawing instead
                 is not the fix: measured 2026-09-17, Spades' +500 falls from 12
                 of 12 seeds to 0 of 12, so both arms are wrong and issue #713
                 is what settles it.

                 (3) Reading the trump costs play where the opponent has a
                 PARTNER it does not know about. Margin over the uniform seats
                 at seat 0 over 16 seeds, measured 2026-09-17: Oh Hell, a solo
                 game, +46.04 with the round's trump against +42.71 blind to it;
                 Bridge +873.33 against +1177.50; Pinochle +1.67 against +3.33 —
                 and Bridge and Pinochle are exactly the two of the three that
                 declare a team zone. An opponent that can now win a trick
                 deliberately also takes it from its partner. The rule is the
                 game's and it is implemented; the lower margin is the cost of
                 knowing one rule while ignoring another, and partner awareness
                 is in this opponent at no level.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from pathlib import Path

from cardlang.openspiel.encoding import BLOCKS
from cardlang.openspiel.infostate import SeatView
from cardlang.openspiel.ranked import DISPOSITIONS, RankedSeatPolicy
from cardlang.openspiel.registry import GAMES
from cardlang.openspiel.replay import LiveLine, load
from cardlang.openspiel.seat_policy import (
    OPPONENTS,
    FirstSeatPolicy,
    SeatBinding,
    SeatPolicy,
    UniformSeatPolicy,
)
from cardlang.runtime.errors import GameDescriptionError
from cardlang.runtime.values import Card, deck_suits
from tests.test_play_session import FIXTURES, _path

_SEED = 5
MINIATURE = str(FIXTURES / "one_trick_known_best.cardlang")


def _seated(path: str, name: str, seats: Sequence[int], seed: int) -> dict[int, object]:
    """`name` at each of `seats`, `random` at the rest."""
    game, space = load(path)
    rows = {seat: OPPONENTS[name if seat in seats else "random"] for seat in range(game.players.low)}
    return {
        seat: row.make(SeatBinding(game, space, seat, seed)) for seat, row in rows.items()
    }


# ---------------------------------------------------------------------------
# What it says it does.
# ---------------------------------------------------------------------------


def test_every_block_of_action_ids_has_a_disposition() -> None:
    """The closed domain is the action space's own blocks: a block with no
    disposition would be drawn uniformly with nobody having said so.

    red under: add a block to `encoding.BLOCKS` without a row here."""
    assert set(DISPOSITIONS) == set(BLOCKS), "decide what `ranked` does with each block"
    assert set(DISPOSITIONS.values()) <= {"ranked", "delegated"}


def test_the_opponent_names_no_game() -> None:
    """A ranker keyed on one game's move type is a per-game branch (CLAUDE.md).

    red under: rank `call_tichu` by name."""
    source = Path("cardlang/openspiel/ranked.py").read_text()
    for short_name, file_name in GAMES.items():
        stem = file_name.removesuffix(".cardlang")
        assert stem not in source and short_name not in source, f"{stem} is named in the source"
    assert "RuntimeState" not in source, "a Seat Policy reads the view, never the world"


# ---------------------------------------------------------------------------
# A position small enough that the trick logic is the only thing measured.
# ---------------------------------------------------------------------------

_SEEDS = tuple(range(24))


def _tricks(name: str, seed: int) -> float:
    """What `name` takes at seat 1 against `first` at seat 0, in one line."""
    game, space = load(MINIATURE)
    policy = OPPONENTS[name].make(SeatBinding(game, space, 1, seed))
    return LiveLine(MINIATURE, seed).play({0: FirstSeatPolicy(), 1: policy}).returns[1]


def test_the_ranked_seat_takes_more_tricks_than_either_baseline() -> None:
    """Three tricks, two seats, and the lead passing to whoever took the last:
    a position small enough that the trick logic is the only thing being
    measured, since no library decides anything here.

    The comparison is against the other opponents at the same seat over the
    same seeds, not against the best line the position allows: that best line
    is computed knowing the hidden hand, which no seat can know.

    red under: answer `legal[-1]` at a card decision, or read the direction as
    `lowest` whatever the game declares."""
    took = {name: sum(_tricks(name, seed) for seed in _SEEDS) for name in ("ranked", "first", "random")}
    assert took["ranked"] > took["first"] and took["ranked"] > took["random"], took
    assert took["first"] and took["random"], f"a baseline took nothing, so the cell compares little: {took}"


# ---------------------------------------------------------------------------
# What it reaches at a table.
# ---------------------------------------------------------------------------

# Games whose card play decides the score: the seeds each claim is measured
# over, and the floor it must clear. Measured 2026-09-15 on this branch: a
# ranked table reached Spades' +500 on 12 of 12 seeds and a uniform table on
# none; a ranked seat beat the uniform average at Hearts on 12 of 16.
_SPADES_SEEDS, _SPADES_FLOOR = 12, 8
_HEARTS_SEEDS, _HEARTS_FLOOR = 16, 10


def _line(path: str, name: str, seats: Sequence[int], seed: int) -> list[float] | None:
    line = LiveLine(path, seed)
    try:
        return list(line.play(_seated(path, name, seats, seed)).returns)  # type: ignore[arg-type]
    except GameDescriptionError:
        return None


def test_a_ranked_table_reaches_the_win_a_uniform_table_never_does() -> None:
    """Spades' +500 sits behind bidding a uniform draw overbids past, which is
    the witness `tests/test_playout_spades.py` holds at the chooser level.

    red under: answer a numeric decision uniformly."""
    path = _path("cardlang_spades")
    seeds = range(_SPADES_SEEDS)
    ranked = [_line(path, "ranked", range(4), seed) for seed in seeds]
    uniform = [_line(path, "random", [], seed) for seed in seeds]
    reached = sum(1 for returns in ranked if returns is not None and max(returns) >= 500)
    by_draw = sum(1 for returns in uniform if returns is not None and max(returns) >= 500)
    assert reached >= _SPADES_FLOOR, (
        f"a ranked table reached +500 on {reached} of {_SPADES_SEEDS} seeds"
    )
    assert by_draw == 0, "a uniform table now reaches +500 — the contrast is gone"


def test_a_ranked_seat_takes_fewer_penalties_than_the_uniform_seats_beside_it() -> None:
    """Hearts wants its score LOW, and the direction is the game's own
    `winner:` clause. One ranked seat against three uniform ones, so the
    comparison is inside a line rather than across two of them.

    red under: read the direction as `highest` whatever the game declares."""
    path = _path("cardlang_hearts")
    better = 0
    for seed in range(_HEARTS_SEEDS):
        returns = _line(path, "ranked", [0], seed)
        assert returns is not None, f"seed {seed}: hearts did not reach an end"
        # `winner: lowest cumulative_score`, so a return is better when higher:
        # the returns are the game's own, already signed by the winner clause.
        better += returns[0] > sum(returns[1:]) / 3
    assert better >= _HEARTS_FLOOR, (
        f"the ranked seat beat the uniform average on {better} of {_HEARTS_SEEDS} seeds"
    )


def test_a_trump_takes_a_trick_the_suit_led_cannot() -> None:
    """Spades declares `trump: spades` and takes its tricks with
    `highest_trump_or_led_suit`, so a seat void in the suit led takes the trick
    with its cheapest spade. The expectation is recomputed here from the view
    and the declarations, never asked of the policy.

    red under: read a card as taking the trick only when its suit is the one
    led."""
    path = _path("cardlang_spades")
    game, space = load(path)
    ranking = {rank: len(game.ranking) - place for place, rank in enumerate(game.ranking)}
    trick = frozenset(zone.name for zone in game.zones if zone.type_ref.name == "TrickPile")
    hands = frozenset(zone.name for zone in game.zones if zone.type_ref.name == "Hand")
    checked = 0

    def expected(view: SeatView, legal: Sequence[int]) -> int | None:
        """The cheapest trump that takes, where the seat holds no card of the
        suit led and some spade beats every spade on the table."""
        table = [card for label, shown in view.zones if label.split("[", 1)[0] in trick
                 for card in (shown if isinstance(shown, tuple) else ())]
        held = [card for label, shown in view.zones if label.split("[", 1)[0] in hands
                for card in (shown if isinstance(shown, tuple) else ())]
        cards = {aid: space.decode(aid) for aid in legal}
        if not table or not all(isinstance(card, Card) for card in cards.values()):
            return None
        led = table[0].suit
        if led == "spades" or any(card.suit == led for card in held):
            return None  # not the position this cell is about
        best = max((ranking[card.rank] for card in table if card.suit == "spades"), default=0)
        beats = {aid: card for aid, card in cards.items() if card.suit == "spades" and ranking[card.rank] > best}
        if not beats:
            return None
        return min(beats, key=lambda aid: (ranking[beats[aid].rank], aid))

    def watched(seat: int, policy: SeatPolicy) -> SeatPolicy:
        def answer(view: SeatView, legal: Sequence[int]) -> int:
            nonlocal checked
            picked: int = policy(view, legal)
            wanted = expected(view, legal)
            if wanted is not None:
                assert picked == wanted, (
                    f"seat {seat} played {space.to_string(picked)} where the cheapest "
                    f"trump that takes is {space.to_string(wanted)}"
                )
                checked += 1
            return picked

        return answer

    for seed in range(6):
        policies = {
            seat: watched(seat, OPPONENTS["ranked"].make(SeatBinding(game, space, seat, seed)))
            for seat in range(4)
        }
        LiveLine(path, seed).play(policies)
    assert checked, "no seat was ever void in the suit led holding a spade that takes"


def test_a_bid_counts_a_fair_share_of_the_decks_suits() -> None:
    """Spades' bid is a number, and the hand's strength is its cards in the top
    two declared ranks plus trump length past a fair share. The fair share is a
    share of the DECK's suits: a hand missing a suit is not thereby long in
    trumps. Recomputed here from the view and the declarations.

    red under: divide by the suits the hand happens to hold."""
    path = _path("cardlang_spades")
    game, space = load(path)
    ranking = {rank: len(game.ranking) - place for place, rank in enumerate(game.ranking)}
    hands = frozenset(zone.name for zone in game.zones if zone.type_ref.name == "Hand")
    top = len(game.ranking)
    checked = 0

    def watched(seat: int, policy: SeatPolicy) -> SeatPolicy:
        def answer(view: SeatView, legal: Sequence[int]) -> int:
            nonlocal checked
            picked: int = policy(view, legal)
            values = [space.decode(aid) for aid in legal]
            if not all(isinstance(value, int) for value in values):
                return picked
            held = [card for label, shown in view.zones if label.split("[", 1)[0] in hands
                    for card in (shown if isinstance(shown, tuple) else ())]
            strong = sum(1 for card in held if ranking.get(card.rank, 0) >= top - 1)
            share = len(held) // len(deck_suits(game.deck))
            strong += max(0, sum(1 for card in held if card.suit == game.trump) - share)
            wanted = min(legal, key=lambda aid: (abs(space.decode(aid) - strong), aid))
            assert picked == wanted, (
                f"seat {seat} bid {space.decode(picked)} where {strong} winners "
                f"make {space.decode(wanted)} the nearest on offer"
            )
            checked += 1
            return picked

        return answer

    for seed in range(4):
        policies = {
            seat: watched(seat, OPPONENTS["ranked"].make(SeatBinding(game, space, seat, seed)))
            for seat in range(4)
        }
        LiveLine(path, seed).play(policies)
    assert checked, "no seat was ever asked for a number"


def test_a_throw_counts_the_suits_the_seat_holds_not_the_cards_on_offer() -> None:
    """The view is built here rather than played into, because a rule that
    offers a multi-suit subset of a hand is a shape no corpus game reaches: the
    hand is long in clubs, only one club may be played, and the diamond is the
    cheaper card.

    red under: count the suits over `legal` instead of the seat's own cards."""
    path = _path("cardlang_spades")
    game, space = load(path)
    ranked = OPPONENTS["ranked"].make(SeatBinding(game, space, 1, _SEED))
    hand = (Card("3", "clubs"), Card("K", "clubs"), Card("2", "diamonds"))
    view = SeatView(
        player=1,
        zones=(("trick_pile", (Card("A", "hearts"),)), ("hand[1]", hand)),
        state=(),
        obs_log=(),
    )
    legal = sorted(space.encode(card) for card in (Card("K", "clubs"), Card("2", "diamonds")))
    # Spades wants its score high and holds no spade here, so nothing takes the
    # trick and the card thrown is the cheapest of the longest suit held.
    assert ranked(view, legal) == space.encode(Card("K", "clubs"))


def test_a_throw_counts_the_zone_the_decision_plays_from() -> None:
    """Bridge routes the dummy's plays to the declarer, who decides them from
    the exposed hand rather than from its own: the suit the hand is long in is
    the dummy's, and the declarer's own holding says nothing about it.

    red under: count the suits over the seat's private zones."""
    path = _path("cardlang_bridge")
    game, space = load(path)
    ranked = OPPONENTS["ranked"].make(SeatBinding(game, space, 0, _SEED))
    mine = (Card("3", "clubs"), Card("7", "clubs"), Card("9", "clubs"))
    dummy = (Card("K", "diamonds"), Card("2", "diamonds"), Card("5", "clubs"))
    view = SeatView(
        player=0,
        zones=(
            ("trick_pile", (Card("A", "hearts"),)),
            ("hand[0]", mine),
            ("dummy_hand[2]", dummy),
        ),
        state=(),
        obs_log=(),
    )
    legal = sorted(space.encode(card) for card in dummy)
    # Nothing on offer takes a led ace, so the throw is the cheapest card of the
    # suit the DUMMY is long in. Counting the declarer's own three clubs instead
    # makes clubs the long suit and throws the five.
    assert ranked(view, legal) == space.encode(Card("2", "diamonds"))


def test_a_throw_is_drawn_where_two_zones_could_be_the_source() -> None:
    """Pinochle deals a doubled deck, so the card on offer can sit both in the
    hand and in a pile already won. Which of them the decision plays from is
    not a fact the view carries, and a length counted over the wrong one is the
    Bridge defect with a different cause.

    red under: return the first zone holding the cards instead of refusing."""
    path = _path("cardlang_pinochle")
    game, space = load(path)
    ranked = OPPONENTS["ranked"].make(SeatBinding(game, space, 0, _SEED))
    played = (Card("Q", "spades"), Card("10", "spades"))
    view = SeatView(
        player=0,
        zones=(
            ("trick_pile", (Card("A", "hearts"),)),
            ("hand[0]", (*played, Card("9", "clubs"), Card("J", "clubs"))),
            ("captured[0]", played),
        ),
        state=(),
        obs_log=(),
    )
    legal = sorted(space.encode(card) for card in played)
    assert ranked(view, legal) == UniformSeatPolicy(_SEED)(view, legal)


def test_a_round_local_trump_takes_the_trick_the_led_suit_cannot() -> None:
    """Oh Hell, Bridge and Pinochle name their trump in a State Variable their
    Trick Round points at, not in a game-level `trump:`. The round's own
    declaration says which variable, and the view carries its value.

    red under: read `game.trump` alone, which is None for all three."""
    path = _path("cardlang_oh_hell")
    game, space = load(path)
    ranked = OPPONENTS["ranked"].make(SeatBinding(game, space, 1, _SEED))
    hand = (Card("2", "diamonds"), Card("A", "clubs"))
    view = SeatView(
        player=1,
        zones=(("trick_pile", (Card("K", "clubs"),)), ("hand[1]", hand)),
        state=(("trump_suit", "diamonds"),),
        obs_log=(),
    )
    legal = sorted(space.encode(card) for card in hand)
    # Clubs led. The two of the round's trump suit takes; the ace of the suit
    # led does not. Oh Hell wants its score high, so it takes the trick.
    assert ranked(view, legal) == space.encode(Card("2", "diamonds"))


def test_a_card_decision_with_no_trick_in_progress_is_drawn() -> None:
    """Hearts hands three cards to a neighbour before play. That decision
    offers card ids exactly as a trick lead does, and nothing the seat is
    handed tells the two apart — so ranking it would be ranking a decision
    this opponent cannot identify.

    red under: rank a card decision whenever the trick pile is empty."""
    path = _path("cardlang_hearts")
    game, space = load(path)
    ranked = OPPONENTS["ranked"].make(SeatBinding(game, space, 0, _SEED))
    hand = (Card("2", "clubs"), Card("Q", "spades"), Card("A", "hearts"))
    view = SeatView(
        player=0,
        zones=(("trick_pile", ()), ("hand[0]", hand)),
        state=(),
        obs_log=(),
    )
    legal = sorted(space.encode(card) for card in hand)
    assert ranked(view, legal) == UniformSeatPolicy(_SEED)(view, legal)


def test_a_game_that_declares_its_own_trick_order_is_drawn() -> None:
    """Belote states its trumps and card strengths in a `trick_order { }` of its
    own, which this opponent reads nothing of, so its card decisions are the
    draw's.

    red under: rank a card decision whatever the game's Trick Order says."""
    path = _path("cardlang_belote")
    game, space = load(path)
    ranked = OPPONENTS["ranked"].make(SeatBinding(game, space, 0, _SEED))
    uniform = UniformSeatPolicy(_SEED)
    asked = 0

    def compare(view: SeatView, legal: Sequence[int]) -> int:
        nonlocal asked
        picked: int = ranked(view, legal)
        if all(space.block_of(aid) == "card" for aid in legal):
            assert picked == uniform(view, legal), "a card decision was ranked"
            asked += 1
        return picked

    LiveLine(path, _SEED).play({0: compare, **{seat: FirstSeatPolicy() for seat in range(1, 4)}})
    assert asked, "no card decision was reached"


def test_an_offering_is_the_uniform_draw_the_table_says_it_is() -> None:
    """The delegated blocks are delegated to the draw, not to something else
    that happens to be uniform-looking.

    red under: delegate to a second `random.Random` stream."""
    path = _path("cardlang_kuhn_poker")
    game, space = load(path)
    binding = SeatBinding(game, space, 1, _SEED)
    ranked = RankedSeatPolicy(binding)
    uniform = UniformSeatPolicy(_SEED)
    asked = 0

    def compare(view: SeatView, legal: Sequence[int]) -> int:
        nonlocal asked
        picked = ranked(view, legal)
        if all(space.block_of(aid) in _delegated() for aid in legal):
            assert picked == uniform(view, legal), "a delegated decision answered otherwise"
            asked += 1
        return picked

    LiveLine(path, _SEED).play({0: FirstSeatPolicy(), 1: compare})
    assert asked, "no delegated decision was reached"


def _delegated() -> set[str]:
    return {block for block, disposition in DISPOSITIONS.items() if disposition == "delegated"}


def test_the_help_and_the_table_carry_the_new_row() -> None:
    """The row joins the table, so every listing renders it (tests/test_play_opponents.py)."""
    assert "ranked" in OPPONENTS
    assert re.fullmatch(r"[a-z][a-z0-9-]*", OPPONENTS["ranked"].name)
