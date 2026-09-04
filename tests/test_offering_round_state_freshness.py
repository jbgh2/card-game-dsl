"""An offering round's bookkeeping is idle at every decision outside the round.

A `round offering [...] until <state>` — a quiescence-lap poll, an auction
ring, a declaration round — is a [[decision-episode]] with bookkeeping of
its own: the lap counter the declines accumulate into, the acted flags
that shrink the ring, the pass that ends the Reizen. Those variables are
read by nothing but the round's own `until` and `over`, yet their frame is
the phase, so they outlive the round many times over, and the
[[observation-log]] string renders every frame merged with nothing marking
which moment a value belongs to. Bookkeeping still holding the value that
closed the last round therefore reads as a claim about the present at
every decision between rounds: `quiet=4` at a seat asked to play a card
says four consecutive declines describe this moment; `acted` true for every
seat during the tricks says an auction is closing now.

The entry-anchored sibling, tests/test_window_state_freshness.py, cannot
reach this: a round game clears its bookkeeping before each round, so the
decision that opens one reads idle, and the staleness shows only at the
decisions of OTHER episodes. So this module quantifies over every decision
a round does not own, and the guarantee is the game's: the game clears the
bookkeeping where the round closes — or declares it in a sub-phase whose
frame ends with the round — and idleness between rounds is a fact about
the world rather than a convention its reader has to know. A round's
RESULT is not bookkeeping: the taker, the contract, the trump suit are
read all through the play that follows and stay.

Info-set derivation is orthogonal. Bookkeeping is public state, projected
identically to every observer, so indistinguishability holds either way;
what an idle value removes is a spurious distinction between worlds
differing only in resolved history the observation log already carries.

property:        in a game that runs an offering round, every round-scoped
                 [[state-variable]] holds its idle value at every decision
                 outside the round — the declared idle value, or absence
                 where the declaring sub-phase has ended
domain:          the corpus games that run a `round offering ... until`
                 window, classified totally: the games whose rounds carry
                 bookkeeping (`ROUNDS`), the betting family, in which every
                 decision is inside a betting round so no decision is
                 outside one (`NO_DECISION_OUTSIDE`, executed), and
                 Schnapsen, whose round is the trick play terminating on the
                 pile with no bookkeeping of its own (`NO_BOOKKEEPING`, the
                 termination's reads executed). A game in none is red.
                 Within a round game every offering round belongs to exactly
                 one window, and each state declaration partitions, totally,
                 into the round-scoped set checked here and the persistent
                 set that outlives a round by design; both are pinned
                 against the game's AST, so a new round site or a new
                 variable is unclassified and red. A decision is inside a
                 window when its legal subset fits one of that window's
                 vocabularies and no other offering of the game; every other
                 decision — a card pick, a combination, another window's
                 turn, a plain offer — is outside it, and each walk asserts it
                 saw enough of both to have left the window. The other
                 looping constructs whose conditions read state — `turns
                 ... until`, a phase's `repeat until`, `round climb ...
                 until`, an `over` filter — carry no offering round and are
                 outside this module.
registry:        the game axis derives from
                 `cardlang.openspiel.registry.GAMES` filtered by
                 `_offering_round_games`; the variable axis from
                 `cardlang.ast.nodes.state_blocks`; the vocabularies from the
                 `AuctionRound` and `Offer` nodes of each game's AST. The
                 entry-anchored property this module completes:
                 tests/test_window_state_freshness.py. The renderer these
                 values reach: `cardlang.openspiel.infostate.information_state`,
                 whose determinism is pinned at tests/openspiel_ready/harness.py.
does not prove:  nothing about a round-scoped variable at a decision INSIDE
                 its round, where its liveness varies with the ring's own
                 progress. Nothing beyond the lines walked: a uniformly
                 random walk of `WALK_STEPS` decisions over `WALK_SEEDS`, so
                 a decision the walk never reaches — a hand's late tricks —
                 is unchecked, and the floors bound only that the walk left
                 the window.
"""

from __future__ import annotations

import copy
import random
from dataclasses import dataclass
from functools import cache
from typing import Any

import pytest

from cardlang.ast import nodes as n
from cardlang.openspiel.registry import GAMES
from cardlang.openspiel.replay import load
from cardlang.runtime.driver import play_game
from cardlang.runtime.state import RuntimeState
from tests.test_window_state_freshness import (
    GAMES_DIR,
    _declared_state,
    _move_names,
    _offering_vocabularies,
    _subnodes,
)

# Decisions walked per game before the walk gives up. Linear: one simulation
# per game, reading the live world inside the chooser.
WALK_STEPS = 240

# The walk must see a window close and then keep going before it proves
# anything: bookkeeping is idle at every decision before the first round by
# its declared default, so a walk that never reached a round, or stopped
# inside its first, would pass against a game that never clears.
#
# red under (the vacuity guard itself): set WALK_STEPS to 2 — the walk stops
# before any round has closed and these floors are the only thing that notices.
MIN_INSIDE_DECISIONS = 4
MIN_OUTSIDE_DECISIONS = 20

WALK_SEEDS = (0, 1, 2)


class _Gone:
    """The idle value of bookkeeping declared in a sub-phase that ends with
    the round: outside it the variable is not in any live frame at all."""

    def __repr__(self) -> str:
        return "GONE"


GONE = _Gone()


@dataclass(frozen=True)
class Indexed:
    """The idle value of a seat-indexed variable: every seat holds `value`."""

    value: Any


def _round_vocabularies(game: n.Game) -> list[tuple[str, ...]]:
    return [x.offering for x in _subnodes(game) if isinstance(x, n.AuctionRound)]


def _offering_round_games() -> dict[str, tuple[tuple[str, ...], ...]]:
    """Axis A: corpus filename -> the vocabularies of its `round offering`
    windows, over the whole registry.

    Every offering round, not the ones whose `until` names a state variable:
    a termination can reach state through a function (`pending(player)`) or
    a Primitive's declared reads, and a predicate keyed to the `NameRef`
    shape would drop exactly those games silently. The superset arrives for
    classification, which is loud and correct.
    """
    found: dict[str, tuple[tuple[str, ...], ...]] = {}
    for filename in sorted(set(GAMES.values())):
        game, _space = load(str(GAMES_DIR / filename))
        vocabularies = tuple(dict.fromkeys(_round_vocabularies(game)))
        if vocabularies:
            found[filename] = vocabularies
    return found


@dataclass(frozen=True)
class Window:
    """One Decision Episode of a game: the offering-round sites that run it
    and the bookkeeping that is its own.

    `vocabularies` are the sites' offerings — one window may be written at
    several sites (Belote's two take rounds share `acted`; Doppelkopf polls
    at four). A decision inside the window shows a legal subset of one of
    them. `idle` is the value each round-scoped variable holds outside the
    window: a declared value, `Indexed(v)` for a seat-indexed one, or `GONE`
    where the declaring sub-phase ends with the round. A window with no
    bookkeeping of its own (a one-draw declaration whose `until` reads its
    result) has an empty `idle` and classifies its site without a cell.
    """

    vocabularies: tuple[tuple[str, ...], ...]
    idle: tuple[tuple[str, Any], ...]


@dataclass(frozen=True)
class Rounds:
    """One game's declarations, classified against its windows. The
    classification is authored, not derived — what is pinned is that it is
    TOTAL against the game's own offering rounds and state declarations, so
    a site or a variable nobody classified reddens rather than going
    unchecked."""

    windows: tuple[Window, ...]
    persistent: frozenset[str]


_DOPPELKOPF_POLL = (
    "announce_re", "announce_kontra", "announce_re_no90", "announce_re_no60",
    "announce_re_no30", "announce_re_schwarz", "announce_kontra_no90",
    "announce_kontra_no60", "announce_kontra_no30", "announce_kontra_schwarz",
    "no_announcement",
)

_BELOTE_DECLARATIONS = (
    "declare_tierce", "declare_tierce_trump", "declare_quarte",
    "declare_quarte_trump", "declare_quinte", "declare_quinte_trump",
    "declare_carre", "no_declaration",
)

# Axis B, per round game. A cell green on the game as written is a control:
# its comment names the edit that reddens it.
ROUNDS: dict[str, Rounds] = {
    "belote.cardlang": Rounds(
        # The two take rounds are one window: the second runs only when the
        # first names no taker, over the same acted flags. The declaration
        # round after the first trick is the other. `taker` and everything the
        # declarations compute are results the hand reads.
        windows=(
            Window(
                vocabularies=(("take", "pass"), ("take_suit", "pass")),
                idle=(("acted", Indexed(False)),),
            ),
            Window(
                vocabularies=(_BELOTE_DECLARATIONS,),
                idle=(("decl_acted", Indexed(False)),),
            ),
        ),
        persistent=frozenset(
            {
                "ann_meld", "belote_holder", "belote_resolved", "belote_said",
                "best_holder", "best_str", "dealer", "decl_class",
                "decl_height", "decl_points", "decl_trump", "last_winner",
                "leader", "meld_score", "score", "show_k", "taker", "total",
                "trick_no", "tricks_won", "trump_suit",
            }
        ),
    ),
    "bridge.cardlang": Rounds(
        # The auction is its own sub-phase, so its bookkeeping and the
        # standing bid it hands to the outcome function end with it. Green as
        # written; red under: declare `passes` in the hand's state block
        # instead — the frame then outlives the auction and the closing count
        # is read at every trick.
        windows=(
            Window(
                vocabularies=(("pass", "submit_bid", "double", "redouble"),),
                idle=(("passes", GONE), ("made_bid", GONE)),
            ),
        ),
        persistent=frozenset(
            {
                "below_current", "contract_level", "cur_level", "cur_strain",
                "dealer", "declarer", "doubled", "doubled_mult", "dummy",
                "games_won", "high_bidder", "leader", "total_score",
                "tricks_taken", "trump_suit",
            }
        ),
    ),
    "doppelkopf.cardlang": Rounds(
        # The announcement poll before every card play. Every announcement is
        # a result the ladder and the settlement read all hand long; only the
        # decline count is the poll's own. Green as written; red under: drop
        # the `quiet := 0` that follows any one poll site.
        windows=(Window(vocabularies=(_DOPPELKOPF_POLL,), idle=(("quiet", 0),)),),
        persistent=frozenset(
            {
                "charlie1_player", "charlie2_player", "cj_seen", "cq_seen",
                "dealer", "dk_tricks", "extras_kontra", "extras_re",
                "fox1_victim", "fox1_winner", "fox2_victim", "fox2_winner",
                "fox_seen", "hands_played", "kontra_level", "kontra_pts",
                "kontra_said", "kontra_tricks", "last_winner", "leader",
                "re_known", "re_level", "re_pts", "re_said", "re_tricks",
                "score", "trick_no", "tricks_won",
            }
        ),
    ),
    "five-hundred.cardlang": Rounds(
        # One auction ring; a pass drops the seat for the rest of it. The
        # standing bid, its bidder and the ring's opener are results.
        windows=(
            Window(
                vocabularies=(("submit_bid", "bid_misere", "bid_open_misere", "pass"),),
                idle=(("passed", Indexed(False)),),
            ),
        ),
        persistent=frozenset(
            {
                "bid_rank", "champion", "dealer", "declarer", "declarer_tricks",
                "high_bidder", "is_misere", "is_open_misere", "joker_suit",
                "leader", "opener", "score", "team_tricks", "tricks_played",
                "trump_suit",
            }
        ),
    ),
    "french-tarot.cardlang": Rounds(
        # The auction is its own sub-phase (the Bridge shape). Green as
        # written; red under: declare `acted` in the hand's state block.
        windows=(
            Window(
                vocabularies=(
                    ("pass", "bid_petite", "bid_garde", "bid_garde_sans", "bid_garde_contre"),
                ),
                idle=(("acted", GONE),),
            ),
        ),
        persistent=frozenset(
            {
                "bid_level", "current_level", "dealer", "hands_played",
                "lead_taker", "leader", "opener", "petit_in_last", "score",
                "taker",
            }
        ),
    ),
    "pinochle.cardlang": Rounds(
        # The auction is its own sub-phase, whose whole state block is the
        # ring's own (the outcome function reads it as the ring closes). The
        # trump declaration is a one-draw window whose `until` reads its
        # result. Green as written; red under: declare `bids` in the hand's
        # state block.
        windows=(
            Window(
                vocabularies=(("submit_bid", "pass"),),
                idle=(
                    ("passed", GONE),
                    ("bids", GONE),
                    ("lead_bidder", GONE),
                    ("working_bid", GONE),
                ),
            ),
            Window(vocabularies=(("declare_trump_suit",),), idle=()),
        ),
        persistent=frozenset(
            {
                "bid_abandoned", "current_bid", "dealer", "high_bidder",
                "leader", "meld_score", "opener", "score", "trick_score",
                "trump_suit",
            }
        ),
    ),
    "skat.cardlang": Rounds(
        # The Reizen is one window at two sites: middlehand against forehand,
        # then rearhand against the survivor, over the same three ring roles.
        # `working_bid` is the result the settlement reads. The suit
        # declaration is a one-draw window whose `until` reads its result.
        windows=(
            Window(
                vocabularies=(("bid", "yes", "pass"),),
                idle=(("passer", None), ("speaker", None), ("responder", None)),
            ),
            Window(vocabularies=(("declare_suit",),), idle=()),
        ),
        persistent=frozenset(
            {
                "dealer", "declarer", "declarer_tricks", "hand_mode",
                "hands_played", "is_grand", "is_null", "leader", "score",
                "thrown", "trump_suit", "working_bid",
            }
        ),
    ),
    "tichu.cardlang": Rounds(
        # The small-tichu poll before the push, after it, and before each
        # climbing trick. A call is a result (`called`); the lap count is the
        # poll's own. Green as written; red under: drop the `quiet := 0` that
        # follows any one poll site.
        windows=(Window(vocabularies=(("call_tichu", "no_call"),), idle=(("quiet", 0),)),),
        persistent=frozenset(
            {
                "called", "leader", "out_first", "out_second", "poll_anchor",
                "push_done", "score",
            }
        ),
    ),
}

# The betting family: every decision the game offers is a betting round's
# turn, so no decision is outside one and the property has nothing to range
# over. Executed below, not asserted: each game is walked and the walk must
# see betting turns and nothing else.
NO_DECISION_OUTSIDE: frozenset[str] = frozenset(
    {
        "holdem-heads-up.cardlang",
        "holdem.cardlang",
        "kuhn-poker.cardlang",
        "leduc-poker.cardlang",
        "seven-card-stud.cardlang",
    }
)

# Schnapsen's offering round is the trick play — the leader's free actions
# and the lead — terminating on the pile, and no bookkeeping of the round's
# own exists: its `until` reads no declared state (executed below), and its
# moves write only results (the closed talon, the marriage points).
NO_BOOKKEEPING: frozenset[str] = frozenset({"schnapsen.cardlang"})

CELLS: list[tuple[str, int, str]] = [
    (filename, index, var)
    for filename, rounds in sorted(ROUNDS.items())
    for index, window in enumerate(rounds.windows)
    for var, _idle in window.idle
]

PARAMS = [
    pytest.param(filename, index, var, id=f"{filename.removesuffix('.cardlang')}:{var}")
    for filename, index, var in CELLS
]


def _window_of(
    names: frozenset[str], windows: tuple[Window, ...], offers: list[frozenset[str]]
) -> int | None:
    """Which window this decision came from, or None for a decision outside
    every window.

    A decision shows the LEGAL subset of its window's vocabulary, so
    membership is subset rather than equality — and a subset that would
    equally fit another window, or a plain `offer` of the game, names no
    window unambiguously. Such a decision is attributed to nothing: neither
    inside any window nor outside one, so it can neither hide staleness nor
    be blamed for it. A decision with no move names at all (a card, a
    combination) is outside every window.
    """
    if not names:
        return None
    fits = [
        index
        for index, window in enumerate(windows)
        if any(names <= frozenset(v) for v in window.vocabularies)
    ]
    if len(fits) != 1 or any(names <= offer for offer in offers):
        return -1 if fits else None
    return fits[0]


class _WalkDone(Exception):
    """Ends the walk at WALK_STEPS without ending the game."""


@dataclass(frozen=True)
class Walk:
    """What one seeded line saw, per window: how many decisions were inside
    it, and the merged state frame at every decision outside it once one of
    its own decisions had been seen."""

    inside: tuple[int, ...]
    outside: tuple[tuple[dict[str, Any], ...], ...]


@cache
def _walk(filename: str, seed: int) -> Walk:
    """One seeded, uniformly-random line of `WALK_STEPS` decisions.

    Linear in the line's length: `on_first_decision` hands over the LIVE
    world, which the driver mutates in place, so every later chooser call
    reads the same object rather than re-simulating the prefix.
    """
    game, _space = load(str(GAMES_DIR / filename))
    windows = ROUNDS[filename].windows
    offers = [frozenset(v) for v in _offering_vocabularies(game)]
    live: list[RuntimeState] = []
    inside = [0] * len(windows)
    outside: list[list[dict[str, Any]]] = [[] for _ in windows]
    rng = random.Random(seed ^ 0x5EED)
    steps = 0

    def capture(rs: RuntimeState) -> None:
        live.append(rs)

    def chooser(player: int, candidates: list[Any], k: int) -> list[Any]:
        nonlocal steps
        steps += 1
        if steps > WALK_STEPS:
            raise _WalkDone
        here = _window_of(_move_names(candidates), windows, offers)
        if here is not None and here >= 0:
            inside[here] += 1
        if here is None or here >= 0:
            merged: dict[str, Any] = {}
            for frame in live[0].frames:
                merged.update(frame)
            # A snapshot, not a view: a seat-indexed variable's value IS the
            # live table, which the game goes on mutating, so a shallow copy
            # would read every earlier decision as the walk's last one.
            snapshot = copy.deepcopy(merged)
            for index in range(len(windows)):
                if index != here and inside[index]:
                    outside[index].append(snapshot)
        pool = list(candidates)
        # `pop`, not `remove`: two equal candidates would otherwise drop the
        # first one twice and never offer the second.
        return [pool.pop(rng.randrange(len(pool))) for _ in range(k)]

    try:
        play_game(game, random.Random(seed), chooser=chooser, on_first_decision=capture)
    except _WalkDone:
        pass
    return Walk(tuple(inside), tuple(tuple(o) for o in outside))


def _is_idle(merged: dict[str, Any], var: str, idle: Any) -> bool:
    if idle is GONE:
        return var not in merged
    if var not in merged:
        return False
    if isinstance(idle, Indexed):
        return all(v == idle.value for v in merged[var].values())
    return bool(merged[var] == idle)


@pytest.mark.parametrize(("filename", "index", "var"), PARAMS)
def test_round_variable_is_idle_outside_its_window(
    filename: str, index: int, var: str
) -> None:
    window = ROUNDS[filename].windows[index]
    idle = dict(window.idle)[var]
    for seed in WALK_SEEDS:
        for merged in _walk(filename, seed).outside[index]:
            assert _is_idle(merged, var, idle), (
                f"{filename}: at a decision outside the window offering "
                f"{[list(v) for v in window.vocabularies]}, `{var}` is "
                f"{merged.get(var, GONE)!r}, not its idle value {idle!r} — the "
                f"record states a fact about a round that has already closed"
            )


_WINDOW_PARAMS = [
    pytest.param(filename, index, id=f"{filename.removesuffix('.cardlang')}:{index}")
    for filename, rounds in sorted(ROUNDS.items())
    for index, window in enumerate(rounds.windows)
    if window.idle
]


@pytest.mark.parametrize(("filename", "index"), _WINDOW_PARAMS)
def test_walk_leaves_the_window(filename: str, index: int) -> None:
    """The floor the cells above stand on, kept apart from them so a cell's
    red is the idle assertion and nothing else."""
    inside = sum(_walk(filename, seed).inside[index] for seed in WALK_SEEDS)
    outside = sum(len(_walk(filename, seed).outside[index]) for seed in WALK_SEEDS)
    assert inside >= MIN_INSIDE_DECISIONS, (
        f"{filename}: the walk reached only {inside} decisions inside window "
        f"{index} over {len(WALK_SEEDS)} seeds; fewer than "
        f"{MIN_INSIDE_DECISIONS} cannot have closed a round, before which the "
        f"idle value comes from the declaration"
    )
    assert outside >= MIN_OUTSIDE_DECISIONS, (
        f"{filename}: the walk reached only {outside} decisions outside window "
        f"{index} after its first turn; fewer than {MIN_OUTSIDE_DECISIONS} "
        f"cannot have left the window"
    )


def test_offering_round_games_are_exactly_the_classified_ones() -> None:
    """Axis A is derived from the corpus, not listed here: a new game that
    runs an offering round arrives as an unclassified key, and a game that
    stops running one leaves a stale entry behind.

    red under: rewrite all three of Tichu's small-tichu poll sites as a
    plain `offer` per seat — the game leaves the derived set and the two
    sides disagree (one site rewritten leaves the other two, and the game,
    in the set)."""
    classified = [set(ROUNDS), NO_DECISION_OUTSIDE, NO_BOOKKEEPING]
    assert sum(len(c) for c in classified) == len(set().union(*classified))
    assert set(_offering_round_games()) == set().union(*classified)


@pytest.mark.parametrize("filename", sorted(ROUNDS), ids=lambda f: f.removesuffix(".cardlang"))
def test_state_declarations_partition(filename: str) -> None:
    """Axis B is total: every declaration is either round-scoped (checked
    above) or persistent by design, and none is both.

    red under: declare one more variable in Tichu's `play` state block — it
    belongs to neither side and the partition stops covering the game."""
    game, _space = load(str(GAMES_DIR / filename))
    rounds = ROUNDS[filename]
    scoped = frozenset(var for w in rounds.windows for var, _idle in w.idle)
    assert len(scoped) == sum(len(w.idle) for w in rounds.windows)
    assert not (scoped & rounds.persistent)
    assert scoped | rounds.persistent == _declared_state(game)


@pytest.mark.parametrize("filename", sorted(ROUNDS), ids=lambda f: f.removesuffix(".cardlang"))
def test_every_offering_round_belongs_to_one_window(filename: str) -> None:
    """The windows' vocabularies are the game's offering rounds, each in
    exactly one window — so a round site that is renamed, re-scoped or
    added reddens rather than silently matching nothing, and a second round
    with variables nobody classified cannot arrive unseen.

    red under: drop `no_call` from any one of Tichu's three poll offerings —
    that site's vocabulary is then an offering round no window names."""
    game, _space = load(str(GAMES_DIR / filename))
    declared = {frozenset(v) for v in _round_vocabularies(game)}
    authored = [frozenset(v) for w in ROUNDS[filename].windows for v in w.vocabularies]
    assert len(authored) == len(set(authored))
    assert declared == set(authored), (
        f"{filename}: the game's offering rounds are not exactly the authored "
        f"windows; it offers {sorted(sorted(v) for v in declared)}"
    )


@pytest.mark.parametrize(
    "filename", sorted(NO_DECISION_OUTSIDE), ids=lambda f: f.removesuffix(".cardlang")
)
def test_betting_family_offers_no_decision_outside_a_round(filename: str) -> None:
    """The betting family's boundary, executed: a walk of each game sees
    betting turns and no other decision, so nothing exists for the property
    to range over.

    red under: give Kuhn's hand a `move chosen one card` before the betting
    round — the walk meets a card decision outside every round."""
    game, _space = load(str(GAMES_DIR / filename))
    vocabularies = [frozenset(v) for v in _round_vocabularies(game)]
    inside = 0
    outside: list[frozenset[str]] = []
    rng = random.Random(0x5EED)
    steps = 0

    def chooser(player: int, candidates: list[Any], k: int) -> list[Any]:
        nonlocal steps, inside
        steps += 1
        if steps > WALK_STEPS:
            raise _WalkDone
        names = _move_names(candidates)
        if names and any(names <= v for v in vocabularies):
            inside += 1
        else:
            outside.append(names)
        pool = list(candidates)
        return [pool.pop(rng.randrange(len(pool))) for _ in range(k)]

    for seed in WALK_SEEDS:
        steps = 0
        try:
            play_game(game, random.Random(seed), chooser=chooser)
        except _WalkDone:
            pass
    assert inside >= MIN_INSIDE_DECISIONS
    assert not outside, f"{filename}: decisions outside every betting round: {outside[:3]}"


@pytest.mark.parametrize(
    "filename", sorted(NO_BOOKKEEPING), ids=lambda f: f.removesuffix(".cardlang")
)
def test_no_bookkeeping_round_reads_no_declared_state(filename: str) -> None:
    """The half of Schnapsen's boundary a derivation can execute: its
    round's termination names no declared state variable, so there is no
    accumulator for the `until` to read.

    red under: terminate Schnapsen's round on a declared flag instead of the
    pile — the flag is then a name this reads."""
    game, _space = load(str(GAMES_DIR / filename))
    declared = _declared_state(game)
    for node in _subnodes(game):
        if isinstance(node, n.AuctionRound):
            named = {x.name for x in _subnodes(node.until) if isinstance(x, n.NameRef)}
            assert not (named & declared), sorted(named & declared)


# The matcher's own boundary, probed directly. The corpus never offers a
# subset that fits two windows or a window and a plain offer, so the clauses
# that refuse an ambiguous subset have no witness in the walk and get one
# here.
_BID = Window(vocabularies=(("bid", "pass"), ("bid_suit", "pass")), idle=())
_DECLARE = Window(vocabularies=(("declare", "no_declaration"),), idle=())


@pytest.mark.parametrize(
    ("names", "offers", "expected", "why"),
    [
        (frozenset({"pass"}), [], 0, "a subset shared by one window's two sites is that window's"),
        (frozenset({"bid_suit", "pass"}), [], 0, "a whole site vocabulary is its window's"),
        (frozenset({"no_declaration"}), [], 1, "a lone decline is the declaration window's"),
        (
            frozenset({"pass"}),
            [frozenset({"pass", "play_on"})],
            -1,
            "a subset a plain offer also fits is attributed to nothing",
        ),
        (frozenset({"lead"}), [], None, "a move of no window is outside every window"),
        (frozenset(), [], None, "no move names at all (a card decision) is outside"),
    ],
)
def test_window_matching_refuses_an_ambiguous_subset(
    names: frozenset[str], offers: list[frozenset[str]], expected: int | None, why: str
) -> None:
    assert _window_of(names, (_BID, _DECLARE), offers) == expected, why


def test_window_matching_refuses_a_subset_two_windows_fit() -> None:
    both = (
        Window(vocabularies=(("bid", "pass"),), idle=()),
        Window(vocabularies=(("take", "pass"),), idle=()),
    )
    assert _window_of(frozenset({"pass"}), both, []) == -1
