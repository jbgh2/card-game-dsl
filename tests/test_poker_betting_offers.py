"""What `poker_betting` offers at a betting decision, and to whom.

property:        the four imported move types PARTITION every betting decision
                 the family library can reach: exactly one of `check`/`call`
                 by whether the actor owes the standing bet, and at most one of
                 `bet`/`raise` by whether a bet is standing at all. A raise is
                 offered to a seat that still owes the bet, and to a seat that
                 has not yet taken a turn on the street — the big blind and the
                 bring-in poster, whose forced post already matches it.
domain:          every combination of the situation a `when:` in
                 `docs/libraries/poker_betting.cardlang` can read — a standing
                 bet or none, the actor owing or level, its turn taken or not,
                 the raise cap with room or without, an opponent able to answer
                 or none, and a stack that can exceed the call or cannot —
                 crossed and driven through a probe game that imports the real
                 library. The actor holds chips in every cell, which is the
                 whole domain of a betting decision: every ring in the family
                 filters on `pending`, and `pending` calls `can_act`, so a seat
                 with an empty stack is never offered a turn. The probe's own
                 ring names the seat rather than `pending`, so each cell asks
                 the GUARDS what they admit and not what the ring reached.
registry:        vocabulary and state surface: `n.Library.move_types`,
                 `.requires` and `.state` of `libraries.load_library`
                 ("poker_betting"); consumers: the `uses` lines of
                 `docs/games/*.cardlang`; the guard-input derivation:
                 `_names_read`. The chip arithmetic each offered move then
                 performs is pinned in tests/test_playout_holdem.py,
                 tests/test_playout_holdem_heads_up.py and
                 tests/test_holdem_settle.py.
does not prove:  the cells are driven at one bet size against one seat count,
                 so nothing here bounds a street's TOTAL aggression — that a
                 street stops at its declared number of bets is
                 tests/test_playout_holdem_heads_up.py's cap pin. And a zero in
                 the consumer sweep is a zero over the seeds swept; what makes
                 it a claim rather than a sample is the argument in
                 `test_only_a_forced_post_reaches_the_un_acted_level_seat`.
"""

from __future__ import annotations

import random
from dataclasses import fields, is_dataclass
from pathlib import Path
from typing import Any, Iterator, NamedTuple

import pytest

from cardlang.ast import nodes as n
from cardlang.libraries import load_library
from cardlang.parse import parse_text
from cardlang.pipeline import check_dsl, check_source
from cardlang.runtime.chooser import random_chooser
from cardlang.runtime.driver import play_game

GAMES = Path(__file__).resolve().parent.parent / "docs" / "games"

LIBRARY = load_library("poker_betting")

# The offer universe. Derived rather than spelled, so a fifth move type added to
# the library arrives as a name the expected column does not account for.
VOCABULARY: tuple[str, ...] = tuple(m.name for m in LIBRARY.move_types)

# The library's whole state surface — the two halves it declares, `requires`
# (the game's) and `state` (its own). This is the axis registry: every name here
# is either varied by a cell axis below or reads in no `when:` at all.
DECLARED_STATE: frozenset[str] = frozenset(
    [r.name for r in LIBRARY.requires]
    + ([d.name for d in LIBRARY.state.decls] if LIBRARY.state else [])
)


def _walk(node: object) -> Iterator[object]:
    if is_dataclass(node) and not isinstance(node, type):
        yield node
        for f in fields(node):
            yield from _walk(getattr(node, f.name))
    elif isinstance(node, tuple):
        for item in node:
            yield from _walk(item)


def _names_read(expr: object) -> frozenset[str]:
    """Every name an expression reads, following calls into the library's own
    functions — `raise` reaches `folded` only through `can_act`, so a walk that
    stopped at the call would report a guard input the grid does not vary."""
    functions = {f.name: f for f in LIBRARY.functions}
    seen: set[str] = set()
    pending: list[object] = [expr]
    while pending:
        node = pending.pop()
        for item in _walk(node):
            if isinstance(item, n.NameRef) and item.name not in seen:
                seen.add(item.name)
                if item.name in functions:
                    pending.append(functions[item.name].body)
    return frozenset(seen)


GUARD_INPUTS: frozenset[str] = frozenset(
    name for m in LIBRARY.move_types for name in _names_read(m.when)
)

# The situation axes, and the value each one is driven at. `bet_to_match` and
# `bet_by` carry the standing bet and the actor's debt; `acted` carries whether
# the turn is taken; `raises` against `raise_cap` the cap; `folded` the field
# (`can_act` reads it); `stack` the purse (and `can_act` reads it too).
AXIS_VARIABLES: frozenset[str] = frozenset(
    ["bet_to_match", "bet_by", "acted", "raises", "raise_cap", "folded", "stack"]
)

STANDING = 4  # the standing bet, where a cell has one
LIMIT = 2  # the street's bet size, what one aggression adds


class Cell(NamedTuple):
    """One betting situation, as the probe game's own numbers."""

    bet_to_match: int
    bet_by: int
    acted: bool
    raises: int
    raise_cap: int
    field: bool
    stack: int
    purse: str

    @property
    def owed(self) -> int:
        return self.bet_to_match - self.bet_by

    @property
    def id(self) -> str:
        standing = "standing" if self.bet_to_match else "open"
        debt = "owes" if self.owed else "level"
        return (
            f"{standing}-{debt}-{'acted' if self.acted else 'unacted'}-"
            f"{'room' if self.raises < self.raise_cap else 'capped'}-"
            f"{'field' if self.field else 'nofield'}-{self.purse}"
        )


def _cells() -> list[Cell]:
    """The crossed domain. A purse the actor cannot hold is not a cell: an
    empty stack fails `can_act`, so no ring in the family offers that seat a
    turn, and the situation is outside what a betting decision can be."""
    out: list[Cell] = []
    for bet_to_match in (0, STANDING):
        for bet_by in sorted({0, bet_to_match}):
            owed = bet_to_match - bet_by
            purses = {"short": owed, "partial": owed + 1, "full": owed + LIMIT + 1}
            for purse, stack in sorted(purses.items()):
                if stack <= 0:
                    continue
                for acted in (False, True):
                    for raises, raise_cap in ((1, 4), (4, 4)):
                        for field in (True, False):
                            out.append(
                                Cell(
                                    bet_to_match=bet_to_match,
                                    bet_by=bet_by,
                                    acted=acted,
                                    raises=raises,
                                    raise_cap=raise_cap,
                                    field=field,
                                    stack=stack,
                                    purse=purse,
                                )
                            )
    return out


CELLS = _cells()


def _expected(cell: Cell) -> frozenset[str]:
    """The offered set the rules of fixed-limit poker call for.

    Authored from the rules, never read off the guards. `check` and `call`
    divide by whether the actor owes the standing bet. `bet` opens a street that
    has none. `raise` needs a bet standing to raise, a seat that has either not
    yet taken its turn (Pagat's big-blind option) or still owes, a cap with room
    left, an opponent who can answer, and chips that exceed the call.

    The one clause here that the library does not carry is `bet`'s field: an
    opening bet is offered even when nobody can answer it, which is issue #429
    — the `open-…-nofield` cells capture that, and flip when it lands.
    """
    owes = cell.owed > 0
    offered = {"call" if owes else "check"}
    if cell.bet_to_match == 0:
        offered.add("bet")
    elif (
        (owes or not cell.acted)
        and cell.raises < cell.raise_cap
        and cell.field
        and cell.stack > cell.owed
    ):
        offered.add("raise")
    return frozenset(offered)


_PROBE = """
game Probe {{
  uses poker_betting
  players: 3
  cards: kuhn3
  max_length: 100
  zones {{ deck : Deck }}
  state {{
    hero              : Player = 0
    stack[player]     : Integer = 10
    committed[player] : Integer = 0
    bet_by[player]    : Integer = 0
    folded[player]    : Boolean = false
    bet_to_match      : Integer = 0
    raises            : Integer = 0
    raise_cap         : Integer = 4
  }}
  phase play {{
    run open_street({limit})
{prime}    bet_to_match := {bet_to_match}
    raises := {raises}
    raise_cap := {raise_cap}
    for each player p: bet_by[p] := {bet_by}
    for each player p: stack[p] := {stack}
{fold}    round offering [{vocabulary}] from 0
          over players where player is hero
          until false
  }}
  winner: highest stack
}}
"""

# `acted` is the library's own state, so the probe game may not write it: the
# seat reaches "turn taken" by taking one, on a street `open_street` has just
# zeroed, where `check` is legal and moves no chips.
_PRIME = """    round offering [check] from 0
          over players where player is hero and not acted[player]
          until (number of players where acted[player]) is 1
"""

# The field axis. Folding the other seats is what empties `can_act` for them;
# their stacks stay untouched, so nothing else about the cell moves with it.
_FOLD = "    for each player p: if not (p is hero) { folded[p] := true }\n"


class _Offered(Exception):
    """Carries the offer out of the probe's first real decision.

    The probe's round has no terminator — the cell is one decision, and every
    way of writing a round that stops after one would have the offered move's
    own effect decide when. Reading the candidates and leaving is what asks the
    guards a question and nothing else."""

    def __init__(self, names: frozenset[str]) -> None:
        self.names = names


def _offer(cell: Cell) -> frozenset[str]:
    source = _PROBE.format(
        limit=LIMIT,
        prime=_PRIME if cell.acted else "",
        bet_to_match=cell.bet_to_match,
        raises=cell.raises,
        raise_cap=cell.raise_cap,
        bet_by=cell.bet_by,
        stack=cell.stack,
        fold="" if cell.field else _FOLD,
        vocabulary=", ".join(VOCABULARY),
    )
    game = check_dsl(source, "probe.cardlang")
    drawn = 0

    def chooser(player: int, candidates: list[Any], count: int) -> list[Any]:
        nonlocal drawn
        drawn += 1
        if cell.acted and drawn == 1:
            return list(candidates[:count])  # the priming check
        raise _Offered(frozenset(name for name, _ in candidates))

    try:
        play_game(game, random.Random(0), None, chooser)
    except _Offered as offered:
        return offered.names
    raise AssertionError(f"{cell.id}: the probe reached no decision")


def test_every_declared_variable_is_an_axis_or_reads_in_no_guard() -> None:
    """The grid's axes cover the library's state surface, or say why not.

    Completeness by superset: the axes are checked against what the library
    DECLARES, not against what its guards happen to read — a guard that starts
    reading a variable the cells hold fixed is exactly the drift a
    guard-derived axis list cannot see. What the axes leave out must then earn
    it by reading in no `when:` at all, which is computed here rather than
    asserted: `committed` is side-pot bookkeeping and `limit` sizes an
    aggression's payment, and neither decides whether a move is legal.

    red under: add `and limit > 0` to any `when:` in the library — `limit`
    becomes a guard input no axis varies, and the second assertion names it.
    """
    unvaried = DECLARED_STATE - AXIS_VARIABLES
    assert AXIS_VARIABLES <= DECLARED_STATE, (
        f"{sorted(AXIS_VARIABLES - DECLARED_STATE)} is varied by an axis but no "
        f"longer declared by the library — the grid drives a name that is gone"
    )
    assert not (unvaried & GUARD_INPUTS), (
        f"{sorted(unvaried & GUARD_INPUTS)} decides whether a move is legal and "
        f"no cell axis varies it — every combination of it is untested"
    )


def _not_yet_admitted(cell: Cell) -> bool:
    """The seat `raise` does not yet reach: a bet standing, the seat level
    against it because a forced post placed it there, and its turn not taken."""
    return (
        cell.bet_to_match > 0
        and cell.owed == 0
        and not cell.acted
        and cell.raises < cell.raise_cap
        and cell.field
        and cell.stack > cell.owed
    )


_PARAMS = [
    pytest.param(
        cell,
        id=cell.id,
        marks=(
            pytest.mark.xfail(
                strict=True,
                raises=AssertionError,
                reason="issue #237: `raise` gates on debt, so the seat whose "
                "forced post already matched the bet is offered `check` alone",
            )
            if _not_yet_admitted(cell)
            else ()
        ),
    )
    for cell in CELLS
]


@pytest.mark.parametrize("cell", _PARAMS)
def test_the_offer_partitions_the_library_vocabulary(cell: Cell) -> None:
    """Every cell's whole offered set, against the rules.

    Asserting the SET rather than one move's presence is what makes this a
    partition pin: `check`/`call` complement each other and `bet`/`raise`
    exclude each other, so a guard drifting out of step with its opposite shows
    up here as a cell offering both or neither, whichever move type moved.
    """
    assert _offer(cell) == _expected(cell), (
        f"{cell.id}: offered {sorted(_offer(cell))}, "
        f"the rules give {sorted(_expected(cell))}"
    )


def test_the_probe_drives_the_library_the_corpus_uses() -> None:
    """The control: the cells above mean nothing if the probe imports a stub.

    Its assertion is the vocabulary, because that is what every cell's expected
    set is written over — a probe offering a vocabulary the library does not
    hold would fail every cell, but a probe holding EXTRA moves would quietly
    widen the offered set and read as a partition failure.
    """
    assert set(VOCABULARY) == {"check", "bet", "call", "raise"}
    probe = parse_text(
        _PROBE.format(
            limit=LIMIT,
            prime="",
            bet_to_match=0,
            raises=0,
            raise_cap=4,
            bet_by=0,
            stack=1,
            fold="",
            vocabulary=", ".join(VOCABULARY),
        ),
        "probe.cardlang",
    )
    assert [u.name for u in probe.uses] == ["poker_betting"]


# --- the consumers: which of them the un-acted level seat reaches -------------

CONSUMERS: tuple[str, ...] = tuple(
    sorted(
        path.stem
        for path in GAMES.glob("*.cardlang")
        if any(
            u.name == "poker_betting"
            for u in parse_text(path.read_text(), path.name).uses
        )
    )
)

# Which consumers open a street with a FORCED POST — a bet placed before the
# round begins, by a seat that takes no turn to place it. Authored per member:
# a new game joining the family arrives as a name this table does not hold.
POSTS_BEFORE_THE_ROUND: dict[str, bool] = {
    "holdem": True,  # the blinds
    "holdem-heads-up": True,  # the blinds
    "kuhn-poker": False,  # antes, and an ante is not a bet
    "leduc-poker": False,  # antes
    "seven-card-stud": True,  # the bring-in
}


def _un_acted_level_decisions(name: str, seeds: int) -> int:
    """Decisions where the actor owes nothing, a bet stands, and its turn is
    not taken — the situation `raise` newly admits."""
    game = check_source(GAMES / f"{name}.cardlang")
    hits = 0
    for seed in range(seeds):
        rng = random.Random(seed)
        inner = random_chooser(rng)
        box: list[Any] = []

        def on_first(state: Any) -> None:
            box.append(state)

        def chooser(player: int, candidates: list[Any], count: int) -> list[Any]:
            nonlocal hits
            if box:
                state = box[0]
                standing = state.get("bet_to_match")
                if (
                    standing > 0
                    and state.get("bet_by")[player] == standing
                    and not state.get("acted")[player]
                ):
                    hits += 1
            chosen: list[Any] = list(inner(player, candidates, count))
            return chosen

        play_game(game, rng, None, chooser, None, on_first)
    return hits


def test_the_family_membership_is_derived_and_classified() -> None:
    """Every consumer is classified, and every classification names a consumer.

    red under: add a `uses poker_betting` line to any other game in
    `docs/games/` — the glob finds a consumer the table does not classify, and
    the first assertion names it.
    """
    assert set(CONSUMERS) == set(POSTS_BEFORE_THE_ROUND), (
        f"consumers {sorted(set(CONSUMERS) - set(POSTS_BEFORE_THE_ROUND))} are "
        f"unclassified and {sorted(set(POSTS_BEFORE_THE_ROUND) - set(CONSUMERS))} "
        f"name no game that uses the library"
    )


@pytest.mark.parametrize("name", CONSUMERS)
def test_only_a_forced_post_reaches_the_un_acted_level_seat(name: str) -> None:
    """The change's blast radius, measured per consumer.

    A game with no forced post cannot reach the situation at all, and the
    argument is structural rather than statistical: with no post, a standing
    bet exists only because `bet` or `raise` created it, and both set the
    aggressor's `acted` while leaving every seat whose `acted` they cleared
    OWING — so no seat is ever both level and un-acted against a standing bet.
    A forced post is the one bet placed before the round begins, so its poster
    matches the bet without having taken a turn.

    That is why the antes do not count: an ante pays into the pot without
    setting `bet_to_match`, so Kuhn's and Leduc's first street opens with
    nothing standing.
    """
    hits = _un_acted_level_decisions(name, seeds=40)
    if POSTS_BEFORE_THE_ROUND[name]:
        assert hits > 0, (
            f"{name} posts a forced bet, so a seat should reach the standing "
            f"bet it already matches without having taken a turn"
        )
    else:
        assert hits == 0, (
            f"{name} posts no forced bet, so no seat can be level against a "
            f"standing bet without having acted — {hits} decisions were"
        )
