"""What `poker_betting` offers at a betting decision, and to whom.

property:        the imported move types PARTITION every betting decision the
                 family library can reach: exactly one of `check`/`call`
                 by whether the actor owes the standing bet, and at most one of
                 `bet`/`raise` by whether a bet is standing at all. A raise is
                 offered to a seat with a TURN OUTSTANDING — the big blind and
                 the bring-in poster, whose forced post is no turn taken — and
                 to any seat facing a bet SHORT of the street's size, spent turn
                 or not, because bringing a short bet up to size is the
                 COMPLETION Robert's Rules 5 grants the very seat it has closed
                 the betting to.
domain:          every combination of the situation a `when:` in
                 `docs/libraries/poker_betting.cardlang` can read — a standing
                 bet or none, against a street size that leaves it short of a
                 full wager or at one, the actor owing or level, its turn taken
                 or not,
                 the raise cap with room or without, an opponent able to answer
                 or none, and a stack that can exceed the call or cannot —
                 crossed and driven through a probe game that imports the real
                 library. The actor holds chips in every cell, which is the
                 whole domain of a betting decision: every ring in the family
                 filters on `pending`, and `pending` calls `can_act`, so a seat
                 with an empty stack is never offered a turn. The probe's own
                 ring names the seat rather than `pending`, so each cell asks
                 the GUARDS what they admit and not what the ring reached. The
                 axes are crossed freely rather than restricted to what the
                 library's own moves produce, because five of the six sit on
                 `requires` state the GAME writes — Stud's bring-in sets
                 `bet_to_match` and `raises` by hand — so a combination no move
                 of the library reaches is still a combination a designer can
                 declare into being. Three things are held fixed rather than
                 crossed, and each is held by an argument. The OFFERING LIST is
                 the library's whole vocabulary: a consumer may name a subset
                 (Kuhn omits `raise`), but a move a game does not name is not
                 offered whatever its guard says, which is decisions.md's "A
                 member offers a subset of the family vocabulary, at no cost"
                 and is pinned at the OpenSpiel target by
                 tests/openspiel_ready/test_kuhn_poker.py. The game-local `fold`
                 is outside the library and so outside this module: every
                 consumer guards it on `bet_to_match > bet_by[actor]`, which
                 makes it `check`'s exact complement, and its ABSENCE from the
                 seat this change admits — a seat owing nothing has nothing to
                 fold against — is asserted in
                 tests/test_playout_holdem_heads_up.py. The DECISION SITE is the
                 `round` form; `execute._offer` enumerates candidates a second
                 time for `offer to`, which no game in this family uses.
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
                 the consumer sweep is a zero over the seeds swept, however wide
                 the sweep; what makes it a claim rather than a sample is the
                 argument in
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
    [
        "bet_to_match",
        "bet_by",
        "acted",
        "raises",
        "raise_cap",
        "folded",
        "stack",
        "limit",
    ]
)

# The street's bet size is an AXIS, not a constant. `raise`'s guard reads it —
# a standing bet short of a full one is a bet anybody may complete, spent turn
# or not — so a cell that held it fixed would leave that comparison driven from
# one side. The two values are chosen so ONE standing bet sits on either side of
# them: 4 is short of a 10-chip street and full on a 2-chip one. A guard
# comparing against the street size and a guard comparing against the number 4
# agree on every cell but those, which is the whole reason to cross them.
LIMITS: tuple[int, ...] = (2, 10)
STANDING: tuple[int, ...] = (0, 4)


class Cell(NamedTuple):
    """One betting situation, as the probe game's own numbers."""

    limit: int
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
        if not self.bet_to_match:
            standing = "open"
        elif self.bet_to_match < self.limit:
            standing = "sub"
        else:
            standing = "standing"
        debt = "owes" if self.owed else "level"
        return (
            f"limit{self.limit}-{standing}-{debt}-"
            f"{'acted' if self.acted else 'unacted'}-"
            f"{'room' if self.raises < self.raise_cap else 'capped'}-"
            f"{'field' if self.field else 'nofield'}-{self.purse}"
        )


def _cells() -> list[Cell]:
    """The crossed domain. A purse the actor cannot hold is not a cell: an
    empty stack fails `can_act`, so no ring in the family offers that seat a
    turn, and the situation is outside what a betting decision can be."""
    out: list[Cell] = []
    for limit in LIMITS:
        for bet_to_match in STANDING:
            for bet_by in sorted({0, bet_to_match}):
                owed = bet_to_match - bet_by
                purses = {"short": owed, "partial": owed + 1, "full": owed + limit + 1}
                for purse, stack in sorted(purses.items()):
                    if stack <= 0:
                        continue
                    for acted in (False, True):
                        for raises, raise_cap in ((1, 4), (4, 4)):
                            for field in (True, False):
                                out.append(
                                    Cell(
                                        limit=limit,
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
    has none. `raise` needs a bet standing to raise, a seat with a LIVE RIGHT TO
    ACT — one that has not taken a turn since anything last re-opened the
    betting to it — a cap with room left, an opponent who can answer, and chips
    that exceed the call.

Robert's Rules 5 (`pagat.com/docs/RobsPkrRulesHome.pdf`) settles
    who may, and it settles two things in one breath: after an all-in "of less
    than half a bet", a seat "who has already acted and is in the pot for all
    previous bets" may "fold, call, or complete the wager".

    OWING IS NOT A RIGHT TO RAISE. That seat owes the short difference and still
    may not raise over it, so `acted` and not `owes` is what carries the right.
    The no-limit sibling names the restricted class outright — "a player who has
    already checked or called" — and its parenthesis, that "the half-the-size
    rule for reopening the betting is for limit poker only", is what makes the
    two one rule at two thresholds.

    COMPLETING IS STILL OPEN TO IT. The same sentence grants that same closed-out
    seat the third option, and a standing bet short of the street's size is
    exactly what there is to complete: nobody has yet wagered a full bet, so
    bringing it up to one is not the reopening the seat has been refused. Stud's
    bring-in is the everyday case and a short all-in opening bet reaches it
    mid-street. `raise` is the move that carries it — from a standing bet below
    `limit` its target IS the completion, which is why no fifth move type
    appears in the offered set.

    `bet`'s row is the exception: it CAPTURES what the library does rather than
    what the rules say, because `bet` carries only `bet_to_match is 0` where
    `raise` carries four conjuncts. So an opening bet is offered into a field
    that cannot answer it, and offered at a cap with no room — issue #429. The
    `open-…-nofield` and `open-…-capped` cells hold that behaviour and flip when
    it lands, which is the point of capturing it rather than asserting the rule
    over a guard nobody has decided to change.
    """
    owes = cell.owed > 0
    offered = {"call" if owes else "check"}
    if cell.bet_to_match == 0:
        offered.add("bet")
    elif (
        (not cell.acted or cell.bet_to_match < cell.limit)
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
        limit=cell.limit,
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
    asserted: `committed` is side-pot bookkeeping, and it decides no move's
    legality.

    It is not inert, though. `committed` accumulates for the side-pot query
    alone, so what it holds shapes a SETTLEMENT and never an offer; what the
    chips then do is the playout modules' to pin.

    red under: drop `limit` from `AXIS_VARIABLES` — `raise` reads it to tell a
    standing bet short of a full wager from one at a full wager, so the second
    assertion names it at once.
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


@pytest.mark.parametrize("cell", CELLS, ids=[c.id for c in CELLS])
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
            limit=LIMITS[0],
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

# The sweep width follows what each half of the claim needs, not one number for
# both. A POSITIVE needs a single decision, and the games that post reach it in
# hundreds within one seed; a ZERO is a claim about absence and is swept wider —
# affordably, because the two games that must come back zero are also the two
# cheapest to play, a handful of decisions each.
SEEDS_FOR_A_ZERO = 40
SEEDS_FOR_A_POSITIVE = 12


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
    posts = POSTS_BEFORE_THE_ROUND[name]
    hits = _un_acted_level_decisions(
        name, seeds=SEEDS_FOR_A_POSITIVE if posts else SEEDS_FOR_A_ZERO
    )
    if posts:
        assert hits > 0, (
            f"{name} posts a forced bet, so a seat should reach the standing "
            f"bet it already matches without having taken a turn"
        )
    else:
        assert hits == 0, (
            f"{name} posts no forced bet, so no seat can be level against a "
            f"standing bet without having acted — {hits} decisions were"
        )
