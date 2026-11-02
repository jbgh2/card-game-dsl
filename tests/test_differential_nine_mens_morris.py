"""Differential validation: the corpus game `docs/games/nine-mens-morris.cardlang`
against OpenSpiel's NATIVE `nine_mens_morris`.

At every node a walk reaches, the two implementations pose the same decision:
the same seat is to move, and the game's legal actions, mapped into the
oracle's action space, are exactly the oracle's legal set. A line the rules
end ends on both sides with the same returns. The oracle also ends every line
at its turn cap, `kMaxNumTurns` in its source (200 completed turns, an
external constant), with returns [0, 0]. That cap is not a rule of the game
(the game's header says so): there the walk stops comparing, asserts the game
still offers a decision, and counts the line as truncated.

The mapping (`to_native`) is a pure function of the decoded action. The
oracle numbers the points row by row from the top-left corner (`ORACLE_POINTS`
below); `place(at)` and `remove(at)` are the point's index, and `slide(from,
to)` and `fly(from, to)` are `24 + 24 * from + to`. Points are mapped by NAME:
the `morris9` registry's cell order is not the oracle's.
`test_mapping_anchors_against_native` reads every point's place off pyspiel's
own rendering of the board, so the table is checked against the oracle rather
than restated.

The walker. Layer (a) walks the replay adapter's paused nodes, `run` with a
history, as the OpenSpiel adapter does, through
`tests/native_oracle.py::assert_node_agrees`. The lines of layers (b) and (c)
are `tests/native_oracle.py::walk_paired_prefix`, one live run each, with the
oracle's turn cap as its `truncate_when` (`turn_cap`): it compares at every
decision, ends each line `Rules` or `Truncated`, and closes each with one
paused replay of its whole history. A script that runs out stops its line at a
live node, where the test reads the offer.

The oracle. This module walks open_spiel 2.0 or later, whose
`nine_mens_morris` offers slides onto point 0 (`a7`); open_spiel 1.6 never
does (issue #975). The census below plays slides onto `a7`, so an older wheel
reddens this module rather than passing it under a mask, and no mask is
carried.

Coverage:

(a) `test_exhaustive_prefix_walk_to_depth_2`: every prefix of the empty board
    to `PREFIX_DEPTH`, through the paused adapter.
(b) Scripted lines: a placing-phase mill whose removal excludes the men of an
    enemy mill; the every-man-in-a-mill removal offering the whole mill; a
    placement closing two mills earning one removal; a reduction win for each
    seat, the loser flying onto a point its man is not adjacent to; a
    blockade, the blocked seat losing with more than two men; a shuffle past
    the oracle's turn cap, where the truncation fires with no man removed.
(c) `test_random_trajectories_agree_with_native`: seeded uniform policies
    over `POLICY_SEEDS`, walked to a rules end or the truncation. The tally
    asserts both winners and a truncation; the census asserts every directed
    edge of the board played as a slide and every mill closed.
(d) Three tripwires: the mapping with `a7` and `d7` exchanged, a scratch copy
    of the game whose removal drops its in-mill conjunct, and the shuffle
    walked with a `truncate_when` that names nothing. Each must redden the
    comparison.

Completeness ledger (decisions.md "Closed-domain completeness")
---------------------------------------------------------------
property:   at every node a walk reaches, the game and the oracle agree on the
            seat to move and on the mapped legal-action set; a line the rules
            end ends on both sides with equal returns; where the oracle ends a
            line at its turn cap with returns [0, 0], the game still offers a
            decision.
domain:     the nodes of the prefix tree to `PREFIX_DEPTH`; the nodes of the
            scripted lines; the nodes of every line over `POLICY_SEEDS`.
            Outside it, by the ruling on issue #953, the tail of a line past
            the oracle's turn cap.
registry:   `tests/native_oracle.py::assert_node_agrees`;
            `tests/native_oracle.py::walk_paired_prefix`; `ORACLE_POINTS`;
            `cardlang.stdlib.boards.board_entry("morris9")`'s cells, edges and
            `lines(3)`, which the census reads.
held by:    the point table is a Born-Green Pin (the bijection, and every
            point's place in pyspiel's rendering); why not higher: the oracle's
            point order is external data with no source in the tree. The
            truncation is Derived: `turn_cap` reads the oracle's own terminal
            returns, the walker asks it only of a terminal oracle, and no code
            here counts turns or holds the cap's value. The oracle's version
            is held by the census, which plays slides onto `a7`.
does not prove:  that the game and the oracle agree past the oracle's turn
            cap, where the oracle has no game to compare; nor at a node no
            walk reaches: the census shows every edge played and every mill
            closed, not every position; and the tally asks no policy line to
            end in a blockade, which the scripted line carries.

red under (point table): exchanging `a7` and `d7` in `ORACLE_POINTS` reddens
the anchor test, the policy walk, every scripted line whose play tells the two
points apart (the double mill, both reduction wins, the blockade), and the
first tripwire, whose own exchange then restores the true table so nothing
raises. It leaves green the walks it cannot tell apart (the prefix walk, the
two removal lines whose mills lie on the top and bottom rows, the shuffle) and
the second tripwire, which walks one of those removal lines.
red under (removal rule): dropping the in-mill conjunct of `remove`'s When
Clause in the game reddens `test_scripted_mill_excludes_enemy_mill_men` and
the policy walk; the second tripwire then fails on its own precondition,
naming the conjunct it plants out as already gone.
"""

from __future__ import annotations

import re
from collections import Counter
from collections.abc import Callable, Iterable, Iterator, Sequence
from dataclasses import dataclass, field
from itertools import chain, cycle
from math import perm
from pathlib import Path
from typing import Any

import pytest

pyspiel = pytest.importorskip("pyspiel")

from cardlang.openspiel.encoding import ActionSpace
from cardlang.openspiel.replay import DecisionNode, load, run
from cardlang.stdlib.boards import board_entry
from tests.native_oracle import (
    Choose,
    LineEnd,
    Rules,
    Truncated,
    assert_node_agrees,
    tally_line_ends,
    uniform,
    walk_paired_prefix,
)

PATH = str(Path(__file__).parent.parent / "docs" / "games" / "nine-mens-morris.cardlang")
NATIVE = "nine_mens_morris"
NUM_POINTS = 24

# The oracle's point indices, by name: row by row from the top-left corner.
ORACLE_POINTS: tuple[str, ...] = (
    "a7", "d7", "g7",
    "b6", "d6", "f6",
    "c5", "d5", "e5",
    "a4", "b4", "c4", "e4", "f4", "g4",
    "c3", "d3", "e3",
    "b2", "d2", "f2",
    "a1", "d1", "g1",
)

# No mill closes before White's third placement, the fifth ply, so a deeper
# prefix adds only placements on vacant points, at a cost that grows by the
# branching factor per ply; the scripted lines and the policies reach the mills.
PREFIX_DEPTH = 2
POLICY_SEEDS: tuple[int, ...] = tuple(range(20))

Step = str | tuple[str, str]  # a point (place, remove) or a (from, to) pair
ToNative = Callable[[Any], int]


def point_index(points: Sequence[str]) -> dict[str, int]:
    return {name: i for i, name in enumerate(points)}


def mapping(points: Sequence[str]) -> ToNative:
    """The `to_native` a point table induces."""
    index = point_index(points)

    def to_native(decoded: Any) -> int:
        name, args = decoded
        if name in ("place", "remove"):
            return index[args]
        assert name in ("slide", "fly"), f"morris has no move type {name!r}"
        frm, to = args
        return NUM_POINTS + NUM_POINTS * index[frm] + index[to]

    return to_native


TO_NATIVE = mapping(ORACLE_POINTS)


def turn_cap(native: Any) -> bool:
    """The oracle's turn cap, read off its own terminal: its one drawn end."""
    return list(native.returns()) == [0.0, 0.0]


class _Stopped(Exception):
    """The script has no further step; the walk ends at a live node."""


@dataclass
class Line:
    """How one paired line ended, and what it passed through."""

    label: str
    end: LineEnd | None = None  # None: the script stopped the line at a live node
    returns: list[float] = field(default_factory=list)
    history: list[int] = field(default_factory=list)
    decoded: list[Any] = field(default_factory=list)
    offer: list[Any] = field(default_factory=list)  # the decoded offer where the script stopped
    players: list[int] = field(default_factory=list)


def paired_line(
    choose: Choose,
    *,
    label: str,
    path: str = PATH,
    to_native: ToNative = TO_NATIVE,
    truncate_when: Callable[[Any], bool] = turn_cap,
) -> Line:
    """One line of `walk_paired_prefix`, the oracle's turn cap its truncation.
    A line the rules end ends on both sides with equal returns."""
    _, space = load(path)
    line = Line(label)

    def advance(player: int, decoded: Any) -> None:
        line.history.append(space.encode(decoded))
        line.decoded.append(decoded)
        line.players.append(player)

    def recording(legal: list[int], space: ActionSpace) -> int:
        line.offer = [space.decode(a) for a in legal]
        return choose(legal, space)

    try:
        line.end = walk_paired_prefix(
            path, NATIVE, to_native, truncate_when, 0, recording,
            label=label, advance=advance,
        )
    except _Stopped:
        return line
    if isinstance(line.end, Rules):
        assert line.end.ours == line.end.native, (
            f"{label} step {line.end.ply}: returns diverge — ours "
            f"{list(line.end.ours)} native {list(line.end.native)}"
        )
        line.returns = list(line.end.ours)
    return line


def scripted(steps: Iterable[Step]) -> Choose:
    """A chooser that plays `steps` in order and stops when they run out. A
    step names points only; the move type is the position's, so the step is the
    one legal action on those points."""
    it: Iterator[Step] = iter(steps)

    def choose(legal: list[int], space: ActionSpace) -> int:
        step = next(it, None)
        if step is None:
            raise _Stopped
        hits = [a for a in legal if space.decode(a)[1] == step]
        assert len(hits) == 1, f"scripted step {step!r} matches {hits} in our game"
        return hits[0]

    return choose


def paused_offer(line: Line) -> list[Any]:
    """The decoded offer of the paused adapter at the end of the line."""
    node = run(PATH, 0, tuple(line.history))
    assert isinstance(node, DecisionNode), f"{line.label}: the line ends at a terminal"
    _, space = load(PATH)
    return [space.decode(a) for a in node.legal]


def kinds(line: Line) -> Counter[str]:
    return Counter(name for name, _ in line.decoded)


def far_flies(line: Line) -> list[tuple[str, str]]:
    """The line's flies onto a point not adjacent to the flying man's own."""
    entry = board_entry("morris9", ())
    return [
        args for name, args in line.decoded
        if name == "fly" and args[1] not in entry.neighbors(args[0])
    ]


def _dfs(
    space: Any,
    native: Any,
    history: list[int],
    depth: int,
    max_depth: int,
    to_native: ToNative,
) -> int:
    ours = run(PATH, 0, tuple(history))
    assert isinstance(ours, DecisionNode), f"prefix walk: unexpected terminal at depth {depth}"
    assert_node_agrees(
        native, ours, to_native, space,
        label="prefix walk", step=depth,
        history=[space.decode(a) for a in history],
    )
    if depth == max_depth:
        return 1
    visited = 1
    for action in ours.legal:
        visited += _dfs(
            space, native.child(to_native(space.decode(action))),
            history + [action], depth + 1, max_depth, to_native,
        )
    return visited


# Black closes a mill on the bottom row and removes a white man; White then
# closes the top row with one black man, f2, standing outside Black's mill.
MILL_EXCLUDES: tuple[Step, ...] = (
    "a7", "a1", "d7", "d1", "b6", "f2", "d6", "g1", "b6", "g7",
)

# The same, with every black man on the board in Black's mill.
ALL_IN_MILL: tuple[Step, ...] = ("a7", "a1", "d7", "d1", "b6", "g1", "b6", "g7")

# White's a7 closes the top row and the a-file at once; one removal follows.
DOUBLE_MILL: tuple[Step, ...] = (
    "d7", "b6", "g7", "f6", "a4", "c5", "a1", "e5", "a7", "b6",
)

# A reduction win for White, Black flying c5 -> c3 on the way. The line is a
# driver's over the oracle: the winner closes a mill whenever it can, and the
# loser never closes one and flies away from its men's neighbours.
P0_REDUCTION: tuple[Step, ...] = (
    "e5", "b4", "g1", "f6", "a4", "d6", "e4", "c4", "e3", "d6", "d5", "d2",
    "d6", "a7", "b2", "a1", "b2", "g7", "d1", "d6", "b6", ("e3", "d3"), "d5",
    ("c4", "c5"), ("d3", "e3"), "f6", ("b6", "d6"), ("e3", "d3"), "b4",
    ("c5", "c3"), ("d3", "e3"), "c3",
)

# A reduction win for Black, White flying d3 -> f2 on the way; the same driver.
P1_REDUCTION: tuple[Step, ...] = (
    "d2", "b6", "e4", "b4", "a7", "b2", "d2", "d7", "e5", "f4", "a4", "c4",
    "d6", "f2", "f6", "c4", "c3", "c4", "d7", "e3", "d5", ("c3", "d3"),
    ("c4", "c5"), "e4", ("f2", "d2"), ("c5", "c4"), "a7", ("f4", "g4"),
    ("c4", "c5"), "g4", ("d3", "f2"), ("c5", "c4"), "f2",
)

# White left with no legal move on its turn. The line is a driver's over the
# oracle whose Black closes a mill when it can and otherwise leaves White the
# fewest moves.
BLOCKADE: tuple[Step, ...] = (
    "e4", "f4", "f6", "f2", "g7", "d7", "g1", "b4", "d1", "d6", "a4", "d5",
    "a4", "c3", "d3", "d2", "a1", "a4", "g4", ("e4", "e5"), ("f4", "e4"),
    ("a4", "a7"), ("f2", "f4"), "c3", ("a7", "a4"), ("f4", "f2"),
    ("d2", "b2"), ("f2", "f4"), "a4", ("b2", "d2"), ("b4", "b2"),
    ("d2", "f2"), ("b2", "d2"),
)

# Eighteen placements closing no mill, then White's d3 and Black's f4 stepping
# out and back for as long as the line runs.
SHUFFLE_PLACEMENTS: tuple[Step, ...] = (
    "a7", "d7", "g7", "b6", "d6", "f6", "c5", "d5", "e5",
    "a4", "b4", "c4", "e4", "f4", "g4", "c3", "d3", "e3",
)
SHUFFLE_CYCLE: tuple[Step, ...] = (("d3", "d2"), ("f4", "f2"), ("d2", "d3"), ("f2", "f4"))

# The in-mill conjunct of `remove`'s When Clause, whatever its line breaks.
IN_MILL_CONJUNCT = re.compile(
    r"\s+and\s+\(\(not\s+in_mill\(at\)\)\s+or\s+all_in_mill\(opponent_of\(actor\)\)\)"
)


def test_mapping_anchors_against_native() -> None:
    """The point table bijects onto the oracle's points and the board's cells,
    and every point sits where pyspiel's own rendering puts a man placed on its
    index: files left to right, ranks bottom to top. Slide ids are anchored on
    the oracle's own move rendering."""
    assert sorted(point_index(ORACLE_POINTS).values()) == list(range(NUM_POINTS))
    assert sorted(ORACLE_POINTS) == sorted(board_entry("morris9", ()).cells)

    game = pyspiel.load_game(NATIVE)
    blank = str(game.new_initial_state()).splitlines()
    places: dict[int, tuple[int, int]] = {}
    for point in range(NUM_POINTS):
        state = game.new_initial_state()
        state.apply_action(point)
        hits = [
            (r, c)
            for r, (before, after) in enumerate(zip(blank, str(state).splitlines()))
            for c, (x, y) in enumerate(zip(before, after))
            if x != y and y == "W"
        ]
        assert len(hits) == 1, f"point {point} renders at {hits}"
        places[point] = hits[0]
    columns = sorted({c for _, c in places.values()})
    rows = sorted({r for r, _ in places.values()})
    assert len(columns) == 7 and len(rows) == 7
    rendered = {
        point: f"{'abcdefg'[columns.index(c)]}{7 - rows.index(r)}"
        for point, (r, c) in places.items()
    }
    assert [rendered[p] for p in range(NUM_POINTS)] == list(ORACLE_POINTS)
    assert rendered[0] == "a7" and rendered[NUM_POINTS - 1] == "g1"

    state = game.new_initial_state()
    assert state.action_to_string(0, TO_NATIVE(("slide", ("a7", "d7")))) == "Move 0 -> 1"
    assert state.action_to_string(0, TO_NATIVE(("fly", ("g1", "a7")))) == "Move 23 -> 0"
    assert state.action_to_string(0, TO_NATIVE(("place", "g1"))) == "Point 23"


def test_exhaustive_prefix_walk_to_depth_2() -> None:
    """Layer (a): every prefix of depth <= 2 poses the same mapped legal set in
    the paused adapter and natively; every node is a placement on the vacant
    points."""
    _, space = load(PATH)
    native = pyspiel.load_game(NATIVE).new_initial_state()
    visited = _dfs(space, native, [], 0, PREFIX_DEPTH, TO_NATIVE)
    expected = sum(perm(NUM_POINTS, d) for d in range(PREFIX_DEPTH + 1))
    assert visited == expected, f"the prefix tree has {expected} nodes, walked {visited}"


def test_scripted_mill_excludes_enemy_mill_men() -> None:
    """A placing-phase mill: the removal offers the one black man outside
    Black's mill, on both sides."""
    line = paired_line(scripted(MILL_EXCLUDES), label="mill excludes")
    assert line.end is None
    assert line.offer == [("remove", "f2")], line.offer


def test_scripted_every_man_in_a_mill_offers_the_mill() -> None:
    """Every black man stands in Black's mill, so the removal offers all of it."""
    line = paired_line(scripted(ALL_IN_MILL), label="all in mill")
    assert line.end is None
    assert line.offer == [("remove", c) for c in ("a1", "d1", "g1")], line.offer


def test_scripted_double_mill_earns_one_removal() -> None:
    """A placement closing two mills earns one removal: the next decision is
    Black's placement on both sides."""
    line = paired_line(scripted(DOUBLE_MILL), label="double mill")
    assert line.end is None
    assert _closed_mills(line, board_entry("morris9", ())) == {
        frozenset(("a7", "d7", "g7")), frozenset(("a7", "a4", "a1")),
    }
    assert kinds(line)["remove"] == 1
    assert line.players[-2:] == [0, 0], "the closing placement and its removal are White's"
    assert {name for name, _ in line.offer} == {"place"}


@pytest.mark.parametrize(
    ("script", "returns", "flier"),
    [(P0_REDUCTION, [1.0, -1.0], "c5"), (P1_REDUCTION, [-1.0, 1.0], "d3")],
    ids=["white", "black"],
)
def test_scripted_reduction_win(
    script: tuple[Step, ...], returns: list[float], flier: str
) -> None:
    """Each seat wins by reducing the other to two men, the loser having flown
    onto a point its man was not adjacent to."""
    line = paired_line(scripted(script), label=f"reduction {returns}")
    assert isinstance(line.end, Rules) and line.returns == returns
    assert [frm for frm, _ in far_flies(line)] == [flier]


def test_scripted_blockade() -> None:
    """White, still holding more than two men, has no legal move and loses."""
    line = paired_line(scripted(BLOCKADE), label="blockade")
    assert isinstance(line.end, Rules) and line.returns == [-1.0, 1.0]
    taken_from_white = sum(
        1 for player, (name, _) in zip(line.players, line.decoded)
        if name == "remove" and player == 1
    )
    assert 9 - taken_from_white > 2, "White still holds more than two men"
    assert line.players[-1] == 1, "Black's move leaves White without one"


def test_scripted_line_truncates_at_the_turn_cap() -> None:
    """A line no rule ends: the oracle's cap ends it, the game asks on, and no
    man was ever removed, so no rules end is what fired."""
    steps = chain(SHUFFLE_PLACEMENTS, cycle(SHUFFLE_CYCLE))
    line = paired_line(scripted(steps), label="shuffle")
    assert isinstance(line.end, Truncated)
    assert kinds(line)["remove"] == 0
    assert {name for name, _ in paused_offer(line)} == {"slide"}


def test_truncation_predicate_is_load_bearing() -> None:
    """The prefix walk FAILS when nothing names the oracle's turn cap: the cap
    ends the shuffle natively while the game still offers a decision.

    red under: the walker treating every terminal oracle at one of our
    decisions as a truncation, without asking `truncate_when`."""
    steps = chain(SHUFFLE_PLACEMENTS, cycle(SHUFFLE_CYCLE))
    with pytest.raises(
        AssertionError, match="native is already terminal while our game still offers a decision"
    ):
        paired_line(scripted(steps), label="shuffle", truncate_when=lambda native: False)


def test_random_trajectories_agree_with_native() -> None:
    """Layer (c): the seeded policies agree at every node, the tally holds both
    winners and a truncation, and the census holds every directed edge played
    as a slide and every mill closed."""
    entry = board_entry("morris9", ())
    slides: set[tuple[str, str]] = set()
    mills: set[frozenset[str]] = set()
    ends: list[LineEnd] = []
    for seed in POLICY_SEEDS:
        line = paired_line(uniform(seed), label=f"policy {seed}")
        assert line.end is not None
        ends.append(line.end)
        slides |= {args for name, args in line.decoded if name == "slide"}
        mills |= _closed_mills(line, entry)
    tally = tally_line_ends(ends)
    assert tally["p0"] and tally["p1"] and tally["truncated"], dict(tally)
    assert "draw" not in tally
    edges = {(a, b) for edge in entry.edges or () for a, b in (tuple(edge), tuple(edge)[::-1])}
    assert edges <= slides, sorted(edges - slides)
    assert mills == {frozenset(line) for line in entry.lines(3)}, len(mills)


def _closed_mills(line: Line, entry: Any) -> set[frozenset[str]]:
    """The mills the line's moves closed: each removal follows a move whose
    destination completes them."""
    board: dict[str, int] = {}
    closed: set[frozenset[str]] = set()
    for player, (name, args) in zip(line.players, line.decoded):
        if name == "remove":
            del board[args]
            continue
        if name == "place":
            board[args] = player
            dest = args
        else:
            del board[args[0]]
            board[args[1]] = player
            dest = args[1]
        for mill in entry.lines(3):
            if dest in mill and all(board.get(c) == player for c in mill):
                closed.add(frozenset(mill))
    return closed


def test_swapped_points_are_a_tripwire() -> None:
    """The comparison FAILS under a wrong point table. Exchanging `a7` and `d7`
    is invisible to the placements, and surfaces where the two boards' mills
    disagree: White's d7, a4, a1 complete the a-file natively and no mill here,
    so the oracle keeps White to move for the removal."""
    swapped = list(ORACLE_POINTS)
    swapped[0], swapped[1] = swapped[1], swapped[0]
    with pytest.raises(AssertionError, match="current player diverges — ours P1 native P0"):
        paired_line(scripted(DOUBLE_MILL), label="a7<->d7", to_native=mapping(swapped))


def test_dropped_in_mill_conjunct_is_a_tripwire(tmp_path: Path) -> None:
    """The comparison FAILS when the game's removal forgets the in-mill
    restriction: the scratch copy offers Black's mill men beside f2."""
    source = Path(PATH).read_text()
    found = IN_MILL_CONJUNCT.findall(source)
    assert len(found) == 1, (
        f"the plant expects one in-mill conjunct in `remove`'s When Clause and "
        f"finds {len(found)}: re-spell IN_MILL_CONJUNCT to the game's text"
    )
    planted = tmp_path / "nine-mens-morris-planted.cardlang"
    planted.write_text(IN_MILL_CONJUNCT.sub("", source))
    with pytest.raises(AssertionError, match="mill excludes step 10: legal actions diverge"):
        paired_line(scripted(MILL_EXCLUDES), label="mill excludes", path=str(planted))
