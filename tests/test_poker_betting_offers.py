"""What `poker_betting` offers at a betting decision, and to whom.

property:        the imported move types PARTITION every betting decision the
                 family library can reach: exactly one of `check`/`call`
                 by whether the actor owes the standing bet, and at most one of
                 `bet`/`raise` by whether a bet is standing at all. A raise is
                 offered to a seat with a TURN OUTSTANDING — the big blind and
                 the bring-in poster, whose forced post is no turn taken — and
                 to any seat facing a bet ABOVE THE LEVEL, spent turn or not —
                 a standing bet above the last full wager is one nobody has
                 yet made in full, and bringing it up to one is the
                 COMPLETION Robert's Rules 5 grants the very seat it has closed
                 the betting to.
domain:          every combination of the situation a `when:` in
                 `docs/libraries/poker_betting.cardlang` can read — a standing
                 bet or none, at the last full wager or above it, the actor
                 owing or square, its turn taken or not, the raise cap with room or without, an opponent able to answer
                 or none, and a stack that can exceed the call or cannot —
                 crossed and driven through a probe game that imports the real
                 library. The actor holds chips in every cell, which is the
                 whole domain of a betting decision: every ring in the family
                 filters on `pending`, and `pending` calls `can_act`, so a seat
                 with an empty stack is never offered a turn. The probe's own
                 ring names the seat rather than `pending`, so each cell asks
                 the GUARDS what they admit and not what the ring reached. The
                 axes are crossed freely rather than restricted to what the
                 library's own moves produce, because every axis except `acted`
                 sits on `requires` state the GAME writes — Stud's bring-in
                 sets `bet_to_match` by hand, the Hold'ems set `level` at the
                 blinds — so a combination no move of the library reaches is
                 still a combination a designer can declare into being. The
                 crossing is bounded by the rules' own band, the level up to
                 but not including the level plus the street, because outside
                 it a wager would have become the level itself. Three things are held fixed rather than
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
does not prove:  `floor` is crossed only at the value `open_street` leaves it
                 — the street's small size. Every cell writes its standing bet
                 rather than playing to one, and only a PLACED big wager moves
                 the floor, so `raise`'s `limit >= floor` term is true in all
                 777 of them. The term is driven false in exactly one place,
                 `test_a_placed_big_bet_withdraws_the_small_raise_only_on_the_
                 casino_arm` below, which plays the wager and asserts both arms;
                 that test, and not this grid, is what makes `big_raise_only`
                 more than a declaration. The cells are driven at one seat count,
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
        "limit",
        "big_limit",
        "floor",
        "big_raise_only",
        "bet_to_match",
        "bet_by",
        "acted",
        "raises",
        "raise_cap",
        "folded",
        "stack",
        "level",
    ]
)

# State a probe game CANNOT drive, and so cannot cross. The membership is not a
# judgment: a game may write the library's `requires` and may not write what the
# library declares in its own `state`, so the excusable set is exactly the
# library-owned guard inputs — asserted below rather than trusted here. What the
# exclusion costs is named with it: these axes are driven by PLAYING to them, in
# tests/test_poker_betting_transitions.py.
LIBRARY_OWNED: frozenset[str] = frozenset(
    d.name for d in (LIBRARY.state.decls if LIBRARY.state else ())
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

# The street's SECOND size, and the arm the game plays. 0 is a one-size street
# — every street in the family before this one — and a positive value is the
# open-pair street, where the rules leave both sizes legal. Twice the small bet
# is the family's own ladder.
#
# `big_raise_only` reads in NO guard: the ratchet reaches the offered set one
# decision later, through `floor`, which a big wager writes. The axis registry
# below would therefore excuse it as "reads in no guard" — and that excusal
# would be wrong, because a variable an effect writes into a guard input is an
# offer axis whatever the guards mention. It is crossed here, and what these
# cells prove is that it changes nothing until a big wager lands.
BIGS: tuple[int, ...] = (0, 2)
RATCHETS: tuple[bool, ...] = (False, True)


class Cell(NamedTuple):
    """One betting situation, as the probe game's own numbers."""

    limit: int
    level: int
    bet_to_match: int
    bet_by: int
    acted: bool
    raises: int
    raise_cap: int
    field: bool
    stack: int
    purse: str
    big: int          # the street's second size, 0 on a one-size street
    ratchet: bool     # `big_raise_only`: the arm the game plays

    @property
    def owed(self) -> int:
        return self.bet_to_match - self.bet_by

    @property
    def id(self) -> str:
        if not self.bet_to_match:
            standing = "open"
        elif self.bet_to_match > self.level:
            standing = "sub"
        else:
            standing = "standing"
        debt = "owes" if self.owed else "level"
        return (
            f"limit{self.limit}-{standing}-{debt}-"
            f"{'acted' if self.acted else 'unacted'}-"
            f"{'room' if self.raises < self.raise_cap else 'capped'}-"
            f"{'field' if self.field else 'nofield'}-{self.purse}-"
            f"{'twosize' if self.big else 'onesize'}-"
            f"{'ratchet' if self.ratchet else 'soft'}"
        )


def _cells() -> list[Cell]:
    """The crossed domain. A purse the actor cannot hold is not a cell: an
    empty stack fails `can_act`, so no ring in the family offers that seat a
    turn, and the situation is outside what a betting decision can be."""
    out: list[Cell] = []
    for limit in LIMITS:
        for bet_to_match in STANDING:
          # A standing bet is at least the last full wager and short of the next
          # one, because a wager reaching that BECOMES the level. Derived rather
          # than listed, so a cell can never name a state no play reaches — the
          # defect that put three rungs of the sizing grid outside the rules.
          for level in sorted(
              {
                  lvl
                  for lvl in range(bet_to_match + 1)
                  if lvl <= bet_to_match < lvl + limit
              }
              & {bet_to_match, max(0, bet_to_match - limit + 1)}
          ):
              for bet_by in sorted({0, bet_to_match}):
                  owed = bet_to_match - bet_by
                  purses = {"short": owed, "partial": owed + 1, "full": owed + limit + 1}
                  for purse, stack in sorted(purses.items()):
                      if stack <= 0:
                          continue
                      for acted in (False, True):
                          for raises, raise_cap in ((1, 4), (4, 4)):
                              for field in (True, False):
                                for big in BIGS:
                                  for ratchet in RATCHETS:
                                    out.append(
                                      Cell(
                                          limit=limit,
                                          level=level,
                                          bet_to_match=bet_to_match,
                                          bet_by=bet_by,
                                          acted=acted,
                                          raises=raises,
                                          raise_cap=raise_cap,
                                          field=field,
                                          stack=stack,
                                          purse=purse,
                                          big=big * limit,
                                          ratchet=ratchet,
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
    seat the third option, and a standing bet short of a full wager is exactly
    what there is to complete: nobody has yet wagered one, so bringing it up to
    one is not the reopening the seat has been refused. `raise` is the move that
    carries it — from such a bet its target IS the completion, which is why no
    fifth move type appears in the offered set.

    WHICH IS WHY `acted` DOES NOT APPEAR ABOVE. Every cell in this module writes
    its standing bet rather than playing to it, and `level` — the last wager
    made in full — is state the LIBRARY owns, which a probe game may not write.
    So every cell sits at a level of zero, every standing bet in it is short of
    a full wager, and the completion is open to every seat. The other half of
    the rule, that a spent turn is REFUSED a raise once a full wager stands, can
    only be driven by playing to that wager: it lives in
    tests/test_poker_betting_transitions.py, whose `level` cells hold it.

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
        if cell.big:
            offered.add("bet_big")
    elif (
        (not cell.acted or cell.bet_to_match > cell.level)
        and cell.raises < cell.raise_cap
        and cell.field
        and cell.stack > cell.owed
    ):
        offered.add("raise")
        if cell.big:
            offered.add("raise_big")
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
    level             : Integer = 0
    raises            : Integer = 0
    raise_cap         : Integer = 4
    big_raise_only    : Boolean = {ratchet}
  }}
  phase play {{
    run open_street({limit}, {big})
{prime}    bet_to_match := {bet_to_match}
    level := {level}
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
        big=cell.big,
        ratchet="true" if cell.ratchet else "false",
        prime=_PRIME if cell.acted else "",
        bet_to_match=cell.bet_to_match,
        level=cell.level,
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

    red under: drop `limit` from `AXIS_VARIABLES` — `raise` reads it against
    the street's floor, which is how the casino arm withdraws the small raise,
    so the second assertion names it at once. It is the FLOOR comparison that
    puts `limit` in a guard, not the standing bet's position: telling a bet
    short of a full wager from one at a full wager is `level`'s job, and a
    plant that names `limit` for that reason describes a guard the library does
    not have.
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
    assert set(VOCABULARY) == {
        "check",
        "bet",
        "bet_big",
        "call",
        "raise",
        "raise_big",
    }
    probe = parse_text(
        _PROBE.format(
            limit=LIMITS[0],
            big=0,
            ratchet="false",
            prime="",
            bet_to_match=0,
            level=0,
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
    "five-card-draw": False,  # antes
    "five-card-stud": True,  # the bring-in
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


# --- the ratchet: the one guard term the cells above cannot drive -------------

# Every cell writes its standing bet rather than playing to it, so `floor` sits
# where `open_street` put it — the street's small size — and `raise`'s
# `limit >= floor` term is true in all of them. The term goes false only after a
# big wager is PLACED, which is a state reached by playing, not by writing. This
# probe plays one.
_RATCHET_PROBE = """
game Ratchet {{
  uses poker_betting
  players: 2
  cards: kuhn3
  max_length: 100
  zones {{ deck : Deck }}
  state {{
    stack[player]     : Integer = 100
    committed[player] : Integer = 0
    bet_by[player]    : Integer = 0
    folded[player]    : Boolean = false
    bet_to_match      : Integer = 0
    level             : Integer = 0
    raises            : Integer = 0
    raise_cap         : Integer = 4
    big_raise_only    : Boolean = {ratchet}
  }}
  phase play {{
    run open_street(5, 10)
    round offering [{vocabulary}] from 0
          over players where can_act(player)
          until false
  }}
  winner: highest stack
}}
"""


def _offer_after_a_big_bet(ratchet: bool) -> frozenset[str]:
    """What the seat behind a placed big bet is offered."""
    game = check_dsl(_RATCHET_PROBE.format(
        ratchet="true" if ratchet else "false", vocabulary=", ".join(VOCABULARY)
    ), "r.cardlang")
    drawn = 0

    def chooser(player: int, candidates: list[Any], count: int) -> list[Any]:
        nonlocal drawn
        drawn += 1
        if drawn == 1:
            picked = [c for c in candidates if c[0] == "bet_big"]
            assert picked, f"the opener was not offered bet_big: {sorted(c[0] for c in candidates)}"
            return picked
        raise _Offered(frozenset(name for name, _ in candidates))

    try:
        play_game(game, random.Random(0), None, chooser)
    except _Offered as offered:
        return offered.names
    raise AssertionError("the probe reached no second decision")


def test_a_placed_big_bet_withdraws_the_small_raise_only_on_the_casino_arm() -> None:
    """Pagat states the ratchet as an option, so the corpus plays both arms and
    the game declares which: "if the rule is played that each raise must be at
    least as large as the last bet or raise, then after a player places a big
    bet, only big raises are allowed in that round. However, many home poker
    games do not have this rule, in which case a player may respond to a big
    bet with a small raise".

    This is the discriminating pin between the two arms, and the only place the
    `limit >= floor` term is driven false. Both arms are asserted, because an
    arm that changed nothing would be a knob in name only.

    red under: drop `and limit >= floor` from `raise`'s guard — the casino arm
    then offers the small raise and this reddens on that half.
    """
    casino = _offer_after_a_big_bet(ratchet=True)
    home = _offer_after_a_big_bet(ratchet=False)

    assert "raise" not in casino, (
        f"the casino arm offered the small raise after a big bet: {sorted(casino)}"
    )
    assert "raise" in home, (
        f"the home arm withdrew the small raise, which is the casino rule: {sorted(home)}"
    )
    # The big raise survives on both arms, or the ratchet has closed the street
    # rather than sized it.
    assert "raise_big" in casino and "raise_big" in home
    # Nothing else moves with the arm.
    assert casino | {"raise"} == home
