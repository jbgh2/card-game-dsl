"""A window's state is idle at the decision that opens the next Decision Episode.

A game whose rules run a decision window — a challenge, a block, a
showdown, a meld attempt — needs [[state-variable]]s to carry the window's
subject: whose play stands, what it claims, who called it, where the
rotation cursor is. Those variables are declared in a phase (or at game
level), so their frame outlives the window many times over, and the
[[observation-log]] string renders every frame merged and sorted with
nothing marking which moment a value belongs to. A window variable still
holding its last [[decision-episode]]'s value therefore reads as a claim
about the present: `claimant=3;challenged=True` at Cheat's announce
decision says a play stands and was called, while the seat being asked is
about to make the first play of a new cycle step.

So the guarantee is the game's, not the renderer's — a game clears a
window's variables where the episode ends, and idleness is a fact about
the world rather than a convention its reader has to know. That is what
makes the record legible to a consumer reading it as one moment: the
OpenSpiel adapter's string, and any tensor derived from it.

Info-set derivation is orthogonal. Every one of these variables is public
state, projected identically to every observer, so indistinguishability
holds either way; what an idle value removes is a spurious distinction
between worlds differing only in resolved history the [[observation-log]]
already carries.

property:        in a game that runs a flag-gated decision window, every
                 window-scoped [[state-variable]] holds its idle value at
                 the decision that opens the next Decision Episode
domain:          the corpus games that declare a flag window — an
                 offer-bearing `repeat until` gated on a declared Boolean
                 state variable. A window written as `round offering ...
                 until <state>` is a different construct and belongs to
                 tests/test_offering_round_state_freshness.py, whose property quantifies
                 over every decision outside the poll: a poll opens idle, so
                 the entry anchor below is satisfied there, and the staleness
                 shows at another episode's decisions. Crossed with each such game's
                 window-scoped variables. Each game's state declarations
                 partition, totally, into the window-scoped set checked
                 here and the persistent set that outlives an episode by
                 design; the partition is pinned against the declarations,
                 so a new variable is unclassified and red. Episode-entry
                 decisions are those offering the game's declared entry
                 move, which names exactly one offering vocabulary in the
                 game's own AST; a game reachable only through a different
                 vocabulary at that moment (Canasta's stock-empty forced
                 take) is outside the walk, and each walk asserts it saw
                 enough entries to have left its first episode.
registry:        the game axis derives from
                 `cardlang.openspiel.registry.GAMES` filtered by
                 `_flag_window_games`; the variable axis from
                 `cardlang.ast.nodes.state_blocks`; the offering
                 vocabularies from the `Offer` nodes of each game's AST.
                 The renderer these values reach:
                 `cardlang.openspiel.infostate.information_state`, whose
                 determinism is pinned at tests/openspiel_ready/harness.py.
does not prove:  nothing about freshness at a decision INSIDE an episode.
                 The check is anchored at episode entry, where "no episode
                 is live" is a fact about the game; inside one, which
                 fields are live varies with the window's own progress, and
                 this module quantifies over neither.
"""

from __future__ import annotations

import dataclasses
import random
from collections.abc import Iterator
from dataclasses import dataclass
from functools import cache
from pathlib import Path
from typing import Any

import pytest

from cardlang.ast import nodes as n
from cardlang.openspiel.registry import GAMES
from cardlang.openspiel.replay import load
from cardlang.runtime.driver import play_game
from cardlang.runtime.state import RuntimeState

GAMES_DIR = Path(__file__).resolve().parent.parent / "docs" / "games"

# Decisions walked per game before the walk gives up. Linear: one simulation
# per game, reading the live world inside the chooser, not one replay per step.
WALK_STEPS = 240

# The walk must leave the FIRST episode before it proves anything: every
# window variable is idle at the opening decision by its declared default,
# so a walk that saw one entry would pass against a game that never clears.
#
# red under (the vacuity guard itself): set WALK_STEPS to 2 — the walk stops
# inside the first episode, every cell's assertion is trivially satisfied,
# and this floor is the only thing that notices.
MIN_ENTRIES = 4


def _subnodes(obj: Any) -> Iterator[Any]:
    """Every AST node reachable from `obj` (nodes hold dataclasses, tuples,
    and leaves)."""
    if dataclasses.is_dataclass(obj) and not isinstance(obj, type):
        yield obj
        for field in dataclasses.fields(obj):
            yield from _subnodes(getattr(obj, field.name))
    elif isinstance(obj, tuple):
        for item in obj:
            yield from _subnodes(item)


def _declared_state(game: n.Game) -> frozenset[str]:
    return frozenset(d.name for b in n.state_blocks(game) for d in b.decls)


def _offering_vocabularies(game: n.Game) -> list[tuple[str, ...]]:
    return [x.offering for x in _subnodes(game) if isinstance(x, n.Offer)]


def _flag_windows(game: n.Game) -> frozenset[str]:
    """The Boolean state variables that gate an offer-bearing `repeat until`
    — the structural signature of a decision window, as opposed to a loop
    gated on a count or a quantifier over the table.

    Any MENTION of such a variable in the condition counts, not a match
    against the spellings the corpus happens to use: `not window_open`,
    `window_open is false` and `turn_done` are one shape to a designer, and a
    predicate keyed to two of them would drop the third silently. The cost of
    the superset is a loop gated on a count AND a flag arriving for
    classification, which is loud and correct; the cost of the subset is a
    window nobody checks.
    """
    booleans = frozenset(
        d.name
        for b in n.state_blocks(game)
        for d in b.decls
        if d.type_name == "Boolean" and d.index is None
    )
    flags: set[str] = set()
    for node in _subnodes(game):
        if not isinstance(node, n.RepeatUntil):
            continue
        if not any(isinstance(x, n.Offer) for x in _subnodes(node.body)):
            continue
        named = {x.name for x in _subnodes(node.until) if isinstance(x, n.NameRef)}
        flags |= named & booleans
    # `RepeatUntil` only: a `round offering ... until` window is the same
    # defect in another construct, and reaching it needs a stronger property
    # than this module's entry anchor, not a wider predicate — the one
    # tests/test_offering_round_state_freshness.py quantifies over.
    return frozenset(flags)


def _flag_window_games() -> dict[str, frozenset[str]]:
    """Axis A: corpus filename -> its flag windows, over the whole registry."""
    found: dict[str, frozenset[str]] = {}
    for filename in sorted(set(GAMES.values())):
        game, _space = load(str(GAMES_DIR / filename))
        flags = _flag_windows(game)
        if flags:
            found[filename] = flags
    return found


@dataclass(frozen=True)
class Episode:
    """One game's declarations, classified against its Decision Episode.

    `entry` is the episode-opening offer's whole vocabulary: the decision at
    which no episode is live. Matching the VOCABULARY rather than one of its
    moves is what keeps the walk total over guarded openings — Coup's turn
    entry is a forced `coup` once a seat holds ten coins, and keying on
    `income` (guarded `coins[actor] < 10`) silently dropped exactly those
    decisions. `idle` is the value each window-scoped variable holds
    between episodes; `persistent` names the declarations that outlive one by
    design. The classification is authored, not derived — what is pinned is
    that it is TOTAL against the game's own declarations, so a variable
    nobody classified reddens rather than going unchecked.
    """

    entry: tuple[str, ...]
    idle: tuple[tuple[str, Any], ...]
    persistent: frozenset[str]


# Axis B, per game. `idle` values are runtime values, not their rendering:
# a DSL `none` is Python `None`, a Player is its seat index.
EPISODES: dict[str, Episode] = {
    "canasta.cardlang": Episode(
        # The turn's draw, then the meld attempt it may open. Canasta closes
        # the attempt where the attempt ends — `close_meld` clears both — so
        # its rows hold on the game as written, which is what makes them the
        # grid's control: they cannot all be failing for a shared reason.
        entry=("draw_stock", "take_pile"),
        idle=(("turn_done", False), ("taking_pile", False), ("meld_rank", None)),
        persistent=frozenset(
            {
                "dealer", "deals_played", "hand_over", "opener", "pile_frozen",
                "score", "team_melded", "went_out",
            }
        ),
    ),
    "cheat.cardlang": Episode(
        # One play: the announce, the count, the face-down discard, the
        # challenge window. `claim_rank` is the table's cycle position, not the
        # play's — it advances once per play and belongs to no episode.
        entry=("play_cards",),
        idle=(
            ("claimant", None),
            ("claim_count", 0),
            ("challenged", False),
            ("challenger", None),
            ("responder", None),
            ("window_open", False),
        ),
        persistent=frozenset({"claim_rank", "won"}),
    ),
    "coup.cardlang": Episode(
        # One turn action and the block/challenge windows it opens.
        # `challenge_stands` idles TRUE: it reads "the claim was not
        # disproved", which is what holds when no claim is pending.
        entry=(
            "income", "foreign_aid", "tax", "steal", "exchange", "coup",
            "assassinate",
        ),
        idle=(
            ("challenged", False),
            ("challenger", None),
            ("block_claim", None),
            ("blocker", None),
            ("responder", None),
            ("window_open", False),
            ("challenge_stands", True),
            ("block_stands", False),
        ),
        persistent=frozenset({"alive", "coins", "treasury", "turn"}),
    ),
    "gin-rummy.cardlang": Episode(
        # The two showdown windows, which open only after a knock; every
        # draw-discard turn happens with neither live.
        entry=("draw_stock", "take_discard"),
        idle=(("arranging", False), ("defending", False)),
        persistent=frozenset(
            {
                "champion", "dealer", "hands_won", "knocked", "knocker",
                "match_score", "opener", "upcard_taken", "went_gin",
            }
        ),
    ),
}

CELLS: list[tuple[str, str]] = [
    (filename, var)
    for filename, episode in sorted(EPISODES.items())
    for var, _idle in episode.idle
]

PARAMS = [
    pytest.param(filename, var, id=f"{filename.removesuffix('.cardlang')}:{var}")
    for filename, var in CELLS
]


def _move_names(candidates: list[Any]) -> frozenset[str]:
    """The move-type names among a chooser's candidates. A card, an integer
    or a combination is not one, and yields nothing."""
    names: set[str] = set()
    for candidate in candidates:
        if isinstance(candidate, str):
            names.add(candidate)
        elif (
            isinstance(candidate, tuple)
            and len(candidate) == 2  # the action space's (name, packed params)
            and isinstance(candidate[0], str)
        ):
            names.add(candidate[0])
    return frozenset(names)


def _is_entry(
    names: frozenset[str], entry: tuple[str, ...], others: list[frozenset[str]]
) -> bool:
    """Did this decision come from the episode-entry offer?

    A decision shows the LEGAL subset of its offer's vocabulary, so membership
    is subset rather than equality — and a subset that would equally fit some
    other offer of the same game names no offer unambiguously, so it is not
    counted. Conservative in the safe direction: an ambiguous decision is
    skipped, never attributed, and the walk's own floor catches a game whose
    entries all turn out ambiguous.
    """
    if not names or not names <= frozenset(entry):
        return False
    return not any(names <= other for other in others)


class _WalkDone(Exception):
    """Ends the walk at WALK_STEPS without ending the game."""


@cache
def _entry_states(
    filename: str, seed: int
) -> tuple[dict[str, Any], ...]:
    """The merged state frame at every episode-entry decision of one seeded,
    uniformly-random line.

    Linear in the line's length: `on_first_decision` hands over the LIVE
    world, which the driver mutates in place, so every later chooser call
    reads the same object rather than re-simulating the prefix.
    """
    path = str(GAMES_DIR / filename)
    game, _space = load(path)
    episode = EPISODES[filename]
    entry = frozenset(episode.entry)
    others = [
        frozenset(v) for v in _offering_vocabularies(game) if frozenset(v) != entry
    ]
    live: list[RuntimeState] = []
    seen: list[dict[str, Any]] = []
    rng = random.Random(seed ^ 0x5EED)
    steps = 0

    def capture(rs: RuntimeState) -> None:
        live.append(rs)

    def chooser(player: int, candidates: list[Any], k: int) -> list[Any]:
        nonlocal steps
        steps += 1
        if steps > WALK_STEPS:
            raise _WalkDone
        if _is_entry(_move_names(candidates), episode.entry, others):
            merged: dict[str, Any] = {}
            for frame in live[0].frames:
                merged.update(frame)
            seen.append(merged)
        pool = list(candidates)
        # `pop`, not `remove`: two equal candidates would otherwise drop the
        # first one twice and never offer the second.
        return [pool.pop(rng.randrange(len(pool))) for _ in range(k)]

    try:
        play_game(game, random.Random(seed), chooser=chooser, on_first_decision=capture)
    except _WalkDone:
        pass
    return tuple(seen)


WALK_SEEDS = (0, 1, 2)


@pytest.mark.parametrize(("filename", "var"), PARAMS)
def test_window_variable_is_idle_at_episode_entry(filename: str, var: str) -> None:
    episode = EPISODES[filename]
    idle = dict(episode.idle)[var]
    entries = 0
    for seed in WALK_SEEDS:
        for merged in _entry_states(filename, seed):
            entries += 1
            assert merged[var] == idle, (
                f"{filename}: at an episode-entry decision (offering "
                f"{list(episode.entry)}), `{var}` is {merged[var]!r}, not its "
                f"idle value {idle!r} — the record states a fact about an "
                f"episode that has already resolved"
            )
    assert entries >= MIN_ENTRIES, (
        f"{filename}: the walk reached only {entries} episode-entry decisions "
        f"over {len(WALK_SEEDS)} seeds; fewer than {MIN_ENTRIES} cannot have "
        f"left the first episode, whose idle values come from the declarations"
    )


# The matcher's own boundary, probed directly. A random walk does not reach a
# Coup seat holding ten coins within the step budget, so the forced-`coup`
# turn — the case a single-move matcher drops — has no witness in the walk and
# gets one here instead.
_COUP = "coup.cardlang"


@pytest.mark.parametrize(
    ("names", "expected", "why"),
    [
        (frozenset({"coup"}), True, "a forced coup IS the turn entry"),
        (frozenset({"income", "tax", "coup"}), True, "a partly-guarded turn entry"),
        (frozenset({"challenge", "allow"}), False, "a challenge window is not entry"),
        (frozenset({"block_claiming_duke", "allow"}), False, "a block window is not"),
        (frozenset(), False, "no move names at all (a card or integer decision)"),
    ],
)
def test_entry_matching_covers_guarded_openings(
    names: frozenset[str], expected: bool, why: str
) -> None:
    game, _space = load(str(GAMES_DIR / _COUP))
    entry = EPISODES[_COUP].entry
    others = [
        frozenset(v)
        for v in _offering_vocabularies(game)
        if frozenset(v) != frozenset(entry)
    ]
    assert _is_entry(names, entry, others) is expected, why


def test_entry_matching_skips_an_ambiguous_subset() -> None:
    """Canasta offers `[take_pile]` alone when the stock is empty, so a lone
    `take_pile` fits both that offer and the turn entry. Attributing it would
    be a guess; the walk skips it and says so in `domain:`."""
    game, _space = load(str(GAMES_DIR / "canasta.cardlang"))
    entry = EPISODES["canasta.cardlang"].entry
    others = [
        frozenset(v)
        for v in _offering_vocabularies(game)
        if frozenset(v) != frozenset(entry)
    ]
    assert _is_entry(frozenset({"take_pile"}), entry, others) is False
    assert _is_entry(frozenset({"draw_stock"}), entry, others) is True


def test_flag_window_games_are_exactly_the_specified_ones() -> None:
    """Axis A is derived from the corpus, not listed here: a new game that
    runs a flag-gated window arrives as an unspecified key.

    red under: give Canasta's turn loop a non-flag condition
    (`repeat until turn_done` -> `repeat until (number of cards in hand[t])
    is 0`) — it leaves the derived set and the two sides disagree."""
    assert set(_flag_window_games()) == set(EPISODES)


@pytest.mark.parametrize("filename", sorted(EPISODES), ids=lambda f: f.removesuffix(".cardlang"))
def test_state_declarations_partition(filename: str) -> None:
    """Axis B is total: every declaration is either window-scoped (checked
    above) or persistent by design, and none is both.

    red under: declare one more variable in Cheat's `state` block — it
    belongs to neither side and the partition stops covering the game."""
    game, _space = load(str(GAMES_DIR / filename))
    episode = EPISODES[filename]
    scoped = frozenset(var for var, _idle in episode.idle)
    assert not (scoped & episode.persistent)
    assert scoped | episode.persistent == _declared_state(game)


@pytest.mark.parametrize("filename", sorted(EPISODES), ids=lambda f: f.removesuffix(".cardlang"))
def test_entry_vocabulary_is_one_the_game_offers(filename: str) -> None:
    """The entry vocabulary is a real offer of the game, not a list authored
    here — so a game that renames or re-scopes its turn offering reddens
    rather than silently matching nothing.

    red under: drop `assassinate` from Coup's turn offering — the declared
    vocabulary then matches no `offer` in the game."""
    game, _space = load(str(GAMES_DIR / filename))
    declared = {frozenset(v) for v in _offering_vocabularies(game)}
    assert frozenset(EPISODES[filename].entry) in declared, (
        f"{filename}: the declared entry vocabulary matches no `offer` in the "
        f"game; it offers {sorted(sorted(v) for v in declared)}"
    )
