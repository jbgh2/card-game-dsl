"""A window's state is idle at the decision that opens the next episode.

A game whose rules run a *decision window* — a challenge, a block, a
showdown, a meld attempt — needs state variables to carry the window's
subject: whose play stands, what it claims, who called it, where the
rotation cursor is. Those variables are declared in a phase (or at game
level), so their frame outlives the window many times over, and the
[[information-state]] renders every frame merged and sorted with nothing
marking which moment a value belongs to. A window variable left holding
its last episode's value is therefore read as a claim about the present:
at Cheat's announce decision, `claimant=3;challenged=True` says a play
stands and was called, while the seat being asked is about to make the
first play of a new cycle step.

The property below is what makes the record legible to a consumer that
reads it as one moment — the OpenSpiel adapter's string, and any tensor
derived from it — and it is a property of the GAME, not of the renderer:
the fix is that the game clears a window's variables when the window's
episode ends, so idleness is a fact about the world rather than a
convention the reader must know.

Info-set derivation is untouched by all of this. Every one of these
variables is public state, projected identically to every observer, so
indistinguishability holds either way; what an idle value removes is a
spurious distinction between worlds that differ only in resolved history
the [[observation-log]] already carries.

property:        in a game that runs a flag-gated decision window, every
                 window-scoped state variable holds its idle value at the
                 decision that opens the next episode
domain:          the corpus games that declare a flag window — an
                 offer-bearing `repeat until` gated on a declared Boolean
                 state variable — crossed with each such game's
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
                 enough entries to have left the first episode.
registry:        the game axis derives from
                 `cardlang.openspiel.registry.GAMES` filtered by
                 `_flag_window_games`; the variable axis from
                 `cardlang.ast.nodes.state_blocks`; the offering
                 vocabularies from the `Offer` nodes of each game's AST.
                 The renderer these values reach:
                 `cardlang.openspiel.infostate.information_state`, whose
                 own determinism is pinned at
                 tests/openspiel_ready/harness.py.
does not prove:  nothing about freshness at a decision INSIDE an episode.
                 The check is anchored at episode entry, where "no episode is
                 live" is a fact about the game; inside one, which fields are
                 live varies with the window's own progress, and this module
                 quantifies over neither.
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
    gated on a count or a quantifier over the table."""
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
        cond = node.until
        if isinstance(cond, n.Not):
            cond = cond.operand
        if isinstance(cond, n.NameRef) and cond.name in booleans:
            flags.add(cond.name)
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
    """One game's window bookkeeping, as the game declares it.

    `entry_move` names the episode-opening offer: the decision at which no
    episode is live. `idle` is the value each window-scoped variable holds
    between episodes; `persistent` names the declarations that outlive one
    by design, so that the two together account for every declaration.
    """

    entry_move: str
    idle: tuple[tuple[str, Any], ...]
    persistent: frozenset[str]


# Axis B, per game. `idle` values are runtime values, not their rendering:
# a DSL `none` is Python `None`, a Player is its seat index.
EPISODES: dict[str, Episode] = {
    "canasta.cardlang": Episode(
        # The turn's draw, then the meld attempt it may open. Canasta already
        # closes its attempt where it ends (`close_meld` clears both), which
        # is why its rows are green with no change to the game.
        entry_move="draw_stock",
        idle=(("turn_done", False), ("taking_pile", False), ("meld_rank", None)),
        persistent=frozenset(
            {
                "dealer", "deals_played", "hand_over", "opener", "pile_frozen",
                "score", "team_melded", "went_out",
            }
        ),
    ),
    "cheat.cardlang": Episode(
        # One play: the announce, the face-down discard, the challenge window.
        # `claim_rank` is the table's cycle position, not the play's — it
        # advances once per play and belongs to no episode.
        entry_move="play_one",
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
        entry_move="income",
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
        entry_move="draw_stock",
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
        elif isinstance(candidate, tuple) and candidate and isinstance(candidate[0], str):
            names.add(candidate[0])
    return frozenset(names)


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
        if episode.entry_move in _move_names(candidates):
            merged: dict[str, Any] = {}
            for frame in live[0].frames:
                merged.update(frame)
            seen.append(merged)
        pool = list(candidates)
        picked: list[Any] = []
        for _ in range(k):
            choice = pool[rng.randrange(len(pool))]
            pool.remove(choice)
            picked.append(choice)
        return picked

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
                f"{episode.entry_move}), `{var}` is {merged[var]!r}, not its "
                f"idle value {idle!r} — the record states a fact about an "
                f"episode that has already resolved"
            )
    assert entries >= MIN_ENTRIES, (
        f"{filename}: the walk reached only {entries} episode-entry decisions "
        f"over {len(WALK_SEEDS)} seeds; fewer than {MIN_ENTRIES} cannot have "
        f"left the first episode, whose idle values come from the declarations"
    )


def test_flag_window_games_are_exactly_the_specified_ones() -> None:
    """Axis A is derived from the corpus, not listed here: a new game that
    runs a flag-gated window arrives as an unspecified key."""
    assert set(_flag_window_games()) == set(EPISODES)


@pytest.mark.parametrize("filename", sorted(EPISODES), ids=lambda f: f.removesuffix(".cardlang"))
def test_state_declarations_partition(filename: str) -> None:
    """Axis B is total: every declaration is either window-scoped (checked
    above) or persistent by design, and none is both."""
    game, _space = load(str(GAMES_DIR / filename))
    episode = EPISODES[filename]
    scoped = frozenset(var for var, _idle in episode.idle)
    assert not (scoped & episode.persistent)
    assert scoped | episode.persistent == _declared_state(game)


@pytest.mark.parametrize("filename", sorted(EPISODES), ids=lambda f: f.removesuffix(".cardlang"))
def test_entry_move_names_one_offering(filename: str) -> None:
    """The entry decision is identified by a move the game offers in exactly
    one place, so `_entry_states` cannot silently match a different offer."""
    game, _space = load(str(GAMES_DIR / filename))
    vocabularies = [v for v in _offering_vocabularies(game) if EPISODES[filename].entry_move in v]
    assert len({frozenset(v) for v in vocabularies}) == 1, (
        f"{filename}: `{EPISODES[filename].entry_move}` appears in "
        f"{len(vocabularies)} distinct offering vocabularies"
    )
