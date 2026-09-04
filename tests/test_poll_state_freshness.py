"""A poll's bookkeeping is idle at every decision outside the poll.

A quiescence-lap poll (decisions.md "Off-the-clock windows") is a
[[decision-episode]] written as `round offering [...] until <state>`: a
counter the declines accumulate into and the window moves reset, read by
nothing but the poll's own `until`. The counter's frame is the phase, so it
outlives every poll many times over, and the [[observation-log]] string
renders every frame merged with nothing marking which moment a value belongs
to. A counter still holding the lap that closed the last poll therefore
reads as a claim about the present at every decision between polls:
`quiet=4` at a seat being asked to play a card says four consecutive
declines describe this moment, while the seat is in the middle of a trick.

The entry-anchored sibling, tests/test_window_state_freshness.py, cannot
reach this: a poll game clears its counter before each poll, so the
decision that opens a poll reads idle, and the staleness shows only at the
decisions of OTHER episodes. So this module quantifies over every decision
the poll does not own, and the guarantee is the game's: the game clears
the counter where the poll closes, and idleness between polls is a fact
about the world rather than a convention its reader has to know.

Info-set derivation is orthogonal. The counter is public state, projected
identically to every observer, so indistinguishability holds either way;
what an idle value removes is a spurious distinction between worlds
differing only in resolved history the observation log already carries.

property:        in a game that runs a quiescence-lap poll, every poll-scoped
                 [[state-variable]] holds its idle value at every decision
                 outside the poll
domain:          the corpus games that run a `round offering ... until`
                 window, classified totally: the poll games checked here
                 (`POLLS`), and the games whose window variables split
                 between bookkeeping and result — every auction and betting
                 round — which are the ruling issue #557 names (`DEFERRED`).
                 A game in neither is red. Within a poll game, each state
                 declaration partitions, totally, into the poll-scoped set
                 checked here and the persistent set that outlives a poll by
                 design; the partition is pinned against the declarations,
                 so a new variable is unclassified and red. A decision is
                 inside the poll when its legal subset fits the poll's
                 vocabulary and no other offering of the game; every other
                 decision — a card pick, a combination, another offer — is
                 outside, and each walk asserts it saw enough of both to have
                 left a poll. The other looping constructs whose conditions
                 read state — `turns ... until`, a phase's `repeat until`,
                 `round climb ... until`, an `over` filter — carry no poll
                 and are the same issue's inventory, outside this module.
registry:        the game axis derives from
                 `cardlang.openspiel.registry.GAMES` filtered by
                 `_offering_round_games`; the variable axis from
                 `cardlang.ast.nodes.state_blocks`; the vocabularies from the
                 `AuctionRound` and `Offer` nodes of each game's AST. The
                 entry-anchored property this module completes:
                 tests/test_window_state_freshness.py. The renderer these
                 values reach: `cardlang.openspiel.infostate.information_state`,
                 whose determinism is pinned at tests/openspiel_ready/harness.py.
does not prove:  nothing about a poll-scoped variable at a decision INSIDE
                 the poll, where its liveness varies with the lap's own
                 progress (issue #438). Nothing beyond the lines walked: a
                 uniformly random walk of `WALK_STEPS` decisions over
                 `WALK_SEEDS`, so a decision the walk never reaches — a
                 hand's late tricks, a poll skipped because every seat has
                 called — is unchecked, and the floors bound only that the
                 walk left a poll.
"""

from __future__ import annotations

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

# The walk must see a poll close and then keep going before it proves
# anything: the counter is idle at every decision before the first poll by its
# declared default, so a walk that never reached a poll, or stopped inside its
# first, would pass against a game that never clears.
#
# red under (the vacuity guard itself): set WALK_STEPS to 2 — the walk stops
# before any poll has closed and these floors are the only thing that notices.
MIN_POLL_DECISIONS = 4
MIN_OUTSIDE_DECISIONS = 20

WALK_SEEDS = (0, 1, 2)


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
class Poll:
    """One game's declarations, classified against its poll.

    `vocabulary` is the poll's whole offering: a decision inside the poll
    shows a legal subset of it. `idle` is the value each poll-scoped variable
    holds outside the poll; `persistent` names the declarations that outlive
    one by design. The classification is authored, not derived — what is
    pinned is that it is TOTAL against the game's own declarations, so a
    variable nobody classified reddens rather than going unchecked.
    """

    vocabulary: tuple[str, ...]
    idle: tuple[tuple[str, Any], ...]
    persistent: frozenset[str]


# Axis B, per poll game.
POLLS: dict[str, Poll] = {
    "doppelkopf.cardlang": Poll(
        # The announcement poll before every card play. Every announcement
        # is a result the ladder and the settlement read all hand long; only
        # the decline count is the poll's own.
        vocabulary=(
            "announce_re", "announce_kontra", "announce_re_no90",
            "announce_re_no60", "announce_re_no30", "announce_re_schwarz",
            "announce_kontra_no90", "announce_kontra_no60",
            "announce_kontra_no30", "announce_kontra_schwarz",
            "no_announcement",
        ),
        idle=(("quiet", 0),),
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
    "tichu.cardlang": Poll(
        # The small-tichu poll before the push, after it, and before each
        # climbing trick. A call is a result (`called`); the lap count is the
        # poll's own.
        vocabulary=("call_tichu", "no_call"),
        idle=(("quiet", 0),),
        persistent=frozenset(
            {
                "called", "leader", "out_first", "out_second", "poll_anchor",
                "push_done", "score",
            }
        ),
    ),
}

# The offering-round games whose window variables are not uniformly
# bookkeeping: an auction's `passes` is the round's own, its `trump_suit` is
# the result play reads all hand long, and which side each declaration falls
# on is the ruling issue #557 asks for. Undecided, so no cell here carries an
# expected value for them; the pin below is their guard.
DEFERRED: frozenset[str] = frozenset(
    {
        "belote.cardlang",
        "bridge.cardlang",
        "five-hundred.cardlang",
        "french-tarot.cardlang",
        "holdem-heads-up.cardlang",
        "holdem.cardlang",
        "kuhn-poker.cardlang",
        "leduc-poker.cardlang",
        "pinochle.cardlang",
        "schnapsen.cardlang",
        "seven-card-stud.cardlang",
        "skat.cardlang",
    }
)

CELLS: list[tuple[str, str]] = [
    (filename, var)
    for filename, poll in sorted(POLLS.items())
    for var, _idle in poll.idle
]

PARAMS = [
    pytest.param(
        filename,
        var,
        id=f"{filename.removesuffix('.cardlang')}:{var}",
        marks=pytest.mark.xfail(
            strict=True, raises=AssertionError, reason="issue #444: authored red"
        ),
    )
    for filename, var in CELLS
]


def _is_inside(
    names: frozenset[str], vocabulary: tuple[str, ...], others: list[frozenset[str]]
) -> bool:
    """Did this decision come from the poll?

    A decision shows the LEGAL subset of its offering's vocabulary, so
    membership is subset rather than equality — and a subset that would
    equally fit some other offering of the same game names no offering
    unambiguously, so it is not counted as the poll's. A decision with no
    move names at all (a card, a combination) is never the poll's.
    """
    if not names or not names <= frozenset(vocabulary):
        return False
    return not any(names <= other for other in others)


class _WalkDone(Exception):
    """Ends the walk at WALK_STEPS without ending the game."""


@dataclass(frozen=True)
class Walk:
    """What one seeded line saw: the merged state frame at every decision
    outside the poll once a poll decision has been seen, and how many poll
    decisions the line reached."""

    outside: tuple[dict[str, Any], ...]
    polls: int


@cache
def _walk(filename: str, seed: int) -> Walk:
    """One seeded, uniformly-random line of `WALK_STEPS` decisions.

    Linear in the line's length: `on_first_decision` hands over the LIVE
    world, which the driver mutates in place, so every later chooser call
    reads the same object rather than re-simulating the prefix.
    """
    game, _space = load(str(GAMES_DIR / filename))
    poll = POLLS[filename]
    vocabulary = frozenset(poll.vocabulary)
    others = [
        frozenset(v)
        for v in _offering_vocabularies(game) + _round_vocabularies(game)
        if frozenset(v) != vocabulary
    ]
    live: list[RuntimeState] = []
    outside: list[dict[str, Any]] = []
    polls = 0
    rng = random.Random(seed ^ 0x5EED)
    steps = 0

    def capture(rs: RuntimeState) -> None:
        live.append(rs)

    def chooser(player: int, candidates: list[Any], k: int) -> list[Any]:
        nonlocal steps, polls
        steps += 1
        if steps > WALK_STEPS:
            raise _WalkDone
        if _is_inside(_move_names(candidates), poll.vocabulary, others):
            polls += 1
        elif polls:
            merged: dict[str, Any] = {}
            for frame in live[0].frames:
                merged.update(frame)
            outside.append(merged)
        pool = list(candidates)
        # `pop`, not `remove`: two equal candidates would otherwise drop the
        # first one twice and never offer the second.
        return [pool.pop(rng.randrange(len(pool))) for _ in range(k)]

    try:
        play_game(game, random.Random(seed), chooser=chooser, on_first_decision=capture)
    except _WalkDone:
        pass
    return Walk(tuple(outside), polls)


@pytest.mark.parametrize(("filename", "var"), PARAMS)
def test_poll_variable_is_idle_outside_the_poll(filename: str, var: str) -> None:
    poll = POLLS[filename]
    idle = dict(poll.idle)[var]
    for seed in WALK_SEEDS:
        for merged in _walk(filename, seed).outside:
            assert merged[var] == idle, (
                f"{filename}: at a decision outside the poll (offering "
                f"{list(poll.vocabulary)}), `{var}` is {merged[var]!r}, not its "
                f"idle value {idle!r} — the record states a fact about a poll "
                f"that has already closed"
            )


@pytest.mark.parametrize("filename", sorted(POLLS), ids=lambda f: f.removesuffix(".cardlang"))
def test_walk_leaves_a_poll(filename: str) -> None:
    """The floor the cells above stand on, kept apart from them so a cell's
    red is the idle assertion and nothing else."""
    polls = sum(_walk(filename, seed).polls for seed in WALK_SEEDS)
    outside = sum(len(_walk(filename, seed).outside) for seed in WALK_SEEDS)
    assert polls >= MIN_POLL_DECISIONS, (
        f"{filename}: the walk reached only {polls} poll decisions over "
        f"{len(WALK_SEEDS)} seeds; fewer than {MIN_POLL_DECISIONS} cannot have "
        f"closed a poll, before which the idle value comes from the declaration"
    )
    assert outside >= MIN_OUTSIDE_DECISIONS, (
        f"{filename}: the walk reached only {outside} decisions outside the "
        f"poll after its first poll decision; fewer than "
        f"{MIN_OUTSIDE_DECISIONS} cannot have left the poll"
    )


def test_offering_round_games_are_exactly_the_classified_ones() -> None:
    """Axis A is derived from the corpus, not listed here: a new game that
    runs an offering round arrives as an unclassified key, and a game that
    stops running one leaves a stale entry behind.

    red under: give Tichu's small-tichu poll a plain `offer` per seat instead
    of the offering round — it leaves the derived set and the two sides
    disagree."""
    assert not (set(POLLS) & DEFERRED)
    assert set(_offering_round_games()) == set(POLLS) | DEFERRED


@pytest.mark.parametrize("filename", sorted(POLLS), ids=lambda f: f.removesuffix(".cardlang"))
def test_state_declarations_partition(filename: str) -> None:
    """Axis B is total: every declaration is either poll-scoped (checked
    above) or persistent by design, and none is both.

    red under: declare one more variable in Tichu's `play` state block — it
    belongs to neither side and the partition stops covering the game."""
    game, _space = load(str(GAMES_DIR / filename))
    poll = POLLS[filename]
    scoped = frozenset(var for var, _idle in poll.idle)
    assert not (scoped & poll.persistent)
    assert scoped | poll.persistent == _declared_state(game)


@pytest.mark.parametrize("filename", sorted(POLLS), ids=lambda f: f.removesuffix(".cardlang"))
def test_poll_vocabulary_is_one_the_game_offers(filename: str) -> None:
    """The poll's vocabulary is a real offering round of the game, not a
    list authored here — so a game that renames or re-scopes its poll
    reddens rather than silently matching nothing.

    red under: drop `no_call` from Tichu's poll offering — the declared
    vocabulary then matches no offering round in the game."""
    game, _space = load(str(GAMES_DIR / filename))
    declared = {frozenset(v) for v in _round_vocabularies(game)}
    assert frozenset(POLLS[filename].vocabulary) in declared, (
        f"{filename}: the declared poll vocabulary matches no offering round "
        f"in the game; it offers {sorted(sorted(v) for v in declared)}"
    )
