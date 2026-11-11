"""The Checker Query's per-seat answer agrees with what play shows each seat.

Completeness ledger (decisions.md "Closed-domain completeness"):

property:        At every movement, reveal, shuffle and decision of every
                 corpus game that a bounded seeded line runs, what the query
                 answers there agrees with what the engine delivers each
                 seat: each moved end is a zone the answer names (or an end
                 it says only play settles), each seat's observation of the
                 move has the projection the answer gives that seat's kind,
                 a seat the answer says learns nothing receives no event of
                 it and one it says learns receives one; a decision is asked
                 by the construct the answer names, by the acting seat where
                 the answer says so, and its pick is heard by every seat
                 exactly where `observe.PICK_SHOWN`'s row says it is; a
                 reveal reaches every seat and a shuffle reaches none; and a
                 part of the game the answer says moves nothing and asks no
                 seat emits nothing while it runs. The pick table names every
                 construct, and every row holding a claim is witnessed.
domain:          Every `.cardlang` game of `docs/games/` and the witness
                 `tests/fixtures/query_witness.cardlang`, each played along
                 `ORACLE_SEEDS`'s first seed in the default run and its others
                 under `slow`, each line bounded at `ORACLE_DECISIONS`
                 decisions. Every observation event is attributed to the
                 statement, or the `choose`, the runtime was running when it
                 was emitted (the oracle wraps `execute._dispatch`,
                 `evaluate._choose` and `observe.movement`), and each seat's
                 holding of each end is the emitter's own
                 (`observe._is_owner`). Library text is outside the domain: its
                 sites are asked about in the library's file (issue #1110).
registry:        the games -- `docs/games/*.cardlang`; the constructs --
                 `cardlang.runtime.delegation.CONSTRUCTS`; the pick table --
                 `cardlang.runtime.observe.PICK_SHOWN`.
held by:         Derived and Pinned: the oracle reads only what the runtime
                 emits and the emitter's own ownership test, never the query's
                 reasoning, so a wrong answer at a site a line reaches is a
                 red cell; the answers' agreement is not a type any pass
                 holds, because the query's site rules restate the runtime's
                 (`cardlang.query`, Contract).
does not prove:  agreement at a site no line reaches: each game's cell records
                 the answered sites its lines never ran as its `unreached`
                 property, derived per run. A construct a line reaches only
                 rarely is held only where it is reached: the `joint` row's
                 one witness is Scopa (measured 2026-11-11). Whether a seat
                 holds an end is read from the emitter, so an answer that
                 names the wrong holder for a team-keyed or position-keyed
                 family agrees here exactly when the emitter does.
"""

from __future__ import annotations

import random
from collections import defaultdict
from dataclasses import dataclass, field
from functools import cache
from pathlib import Path
from typing import Any

import pytest

from cardlang import query as q
from cardlang.ast import nodes as n
from cardlang.diagnostic_codes import Code
from cardlang.diagnostics import Told
from cardlang.pipeline import check_source
from cardlang.runtime import evaluate, execute, observe
from cardlang.runtime.chooser import random_chooser
from cardlang.runtime.delegation import CONSTRUCTS
from cardlang.runtime.driver import play_game
from cardlang.runtime.errors import GameDescriptionError
from cardlang.runtime.state import IllegalMove

REPO = Path(__file__).resolve().parent.parent
# The corpus, and a witness for the movements no corpus game makes (both
# ends showing nothing, an end a `let` names, a team's concealed pile).
GAMES = [*sorted((REPO / "docs" / "games").glob("*.cardlang")), REPO / "tests" / "fixtures" / "query_witness.cardlang"]
ORACLE_SEEDS = (1, 2, 3)
ORACLE_DECISIONS = 300

_SHAPE: dict[str, type] = {"identity": tuple, "count_only": int, "trivial": type(None)}


class _Enough(Exception):
    pass


@dataclass
class _Line:
    """What one seeded line delivered, each event with the stack of parts of
    the game running when it was emitted, innermost last."""

    events: list[tuple[tuple[n.NodeKey | None, ...], int, int, tuple[Any, ...], int | None]] = field(
        default_factory=list
    )
    moves: list[dict[str, Any]] = field(default_factory=list)
    actors: dict[int, int | None] = field(default_factory=dict)
    ran: set[n.NodeKey] = field(default_factory=set)


def _play(path: Path, seed: int) -> _Line:
    line = _Line()
    stack: list[tuple[n.NodeKey | None, int]] = []
    count = [0]
    moving: list[int | None] = [None]
    dispatch, choose, movement = execute._dispatch, evaluate._choose, observe.movement

    def enter(node: object, ctx: Any, run: Any) -> Any:
        key = n.node_key(node)
        if key is not None:
            line.ran.add(key)
            if isinstance(node, n.EachSimultaneous) and (inner := n.node_key(node.body)) is not None:
                line.ran.add(inner)
        count[0] += 1
        line.actors[count[0]] = ctx.current_player
        stack.append((key, count[0]))
        try:
            return run(node, ctx)
        finally:
            stack.pop()

    def moved(ctx: Any, src: Any, dst: Any, cards: Any) -> None:
        if ctx.observer is None or not cards:
            movement(ctx, src, dst, cards)
            return
        rs = ctx.rs
        holds = {
            p: (observe._is_owner(rs, src[0], src[1], p), observe._is_owner(rs, dst[0], dst[1], p))
            for p in rs.seating.players
        }
        line.moves.append(
            dict(at=len(line.moves), site=stack[-1][0] if stack else None, src=src, dst=dst, holds=holds)
        )
        moving[0] = len(line.moves) - 1
        try:
            movement(ctx, src, dst, cards)
        finally:
            moving[0] = None

    game = check_source(path)
    rng = random.Random(seed)
    uniform = random_chooser(rng)
    made = [0]

    def chooser(player: int, candidates: list[Any], amount: int) -> list[Any]:
        if made[0] >= ORACLE_DECISIONS:
            raise _Enough
        made[0] += 1
        return uniform(player, candidates, amount)

    def observed(seat: int, event: tuple[Any, ...]) -> None:
        keys = tuple(k for k, _ in stack)
        line.events.append((keys, stack[-1][1] if stack else 0, seat, event, moving[0]))

    execute._dispatch = lambda stmt, ctx: enter(stmt, ctx, dispatch)
    evaluate._choose = lambda e, ctx: enter(e, ctx, choose)
    observe.movement = moved
    try:
        play_game(game, rng, None, chooser=chooser, observer=observed)
    except (_Enough, GameDescriptionError, IllegalMove):
        pass
    finally:
        execute._dispatch, evaluate._choose, observe.movement = dispatch, choose, movement
    return line


@cache
def _answers(path: Path) -> tuple[q.Checked, dict[n.NodeKey, q.Seats | Told], dict[tuple[str, int, int], n.NodeKey]]:
    """The query's per-seat answer at every node of the game's own text, by
    the node's key, and each `run`'s key by its span (the runtime runs the
    procedure it names as a block standing where the `run` stands)."""
    checked = q.checked_text(path.read_text(), str(path), markdown=False)
    answers: dict[n.NodeKey, q.Seats | Told] = {}
    runs: dict[tuple[str, int, int], n.NodeKey] = {}
    for node, chain in q._walk(checked.game, ()):
        key = n.node_key(node)
        if key is None or key[0] != checked.source_name:
            continue
        answers.setdefault(key, q.seats_at(checked, chain))
        if isinstance(node, n.RunStmt):
            runs[key[:3]] = key
    return checked, answers, runs


def _observer(move: q.TransferRoute, holds: tuple[bool, bool]) -> q.Observer | None:
    """The kind of seat a seat holding (source, destination) is, an end the
    answer leaves to play matching either holding."""
    rows = [
        o
        for o in move.observers
        if (o.holds_source is None or o.holds_source == holds[0])
        and (o.holds_destination is None or o.holds_destination == holds[1])
    ]
    return rows[0] if rows else None


def _case(seats: q.Seats, src: str, dst: str) -> q.TransferRoute | None:
    for move in seats.moves:
        if move.source.zone in (None, src) and move.destination.zone in (None, dst):
            return move
    return None


def _findings(path: Path, seed: int) -> tuple[list[str], set[n.NodeKey]]:
    checked, answers, runs = _answers(path)
    line = _play(path, seed)
    found: list[str] = []
    here = checked.source_name

    def at(key: n.NodeKey) -> str:
        pre = checked.program[: key[1]]
        return f"{path.name}:{pre.count(chr(10)) + 1}:{key[1] - pre.rfind(chr(10))} {key[3]}"

    by_move: dict[int, dict[int, tuple[Any, ...]]] = defaultdict(dict)
    for _keys, _exec, seat, emitted, moving in line.events:
        if moving is not None and emitted[0] == "move":
            by_move[moving][seat] = emitted

    for mv in line.moves:
        key = mv["site"]
        if key is None or key[0] != here:
            continue
        seats = answers.get(key)
        if not isinstance(seats, q.Seats):
            found.append(f"{at(key)}: play moves {mv['src']} -> {mv['dst']}; the query answers none")
            continue
        move = _case(seats, mv["src"][0], mv["dst"][0])
        if move is None:
            found.append(f"{at(key)}: play moves {mv['src'][0]} -> {mv['dst'][0]}; the query names no such movement")
            continue
        for seat, holds in mv["holds"].items():
            obs = _observer(move, holds)
            event: tuple[Any, ...] | None = by_move[mv["at"]].get(seat)
            if obs is None:
                found.append(f"{at(key)}: seat {seat} holds {holds}; the query has no such kind of seat")
                continue
            if obs.learns is True and event is None:
                found.append(f"{at(key)}: {obs.who} (seat {seat}) learns, says the query; play delivers nothing")
            if obs.learns is False and event is not None:
                found.append(f"{at(key)}: {obs.who} (seat {seat}) learns nothing, says the query; play delivers {event}")
            if event is not None:
                for projection, view in ((obs.source, event[2]), (obs.destination, event[4])):
                    if projection is not None and not isinstance(view, _SHAPE.get(projection, object)):
                        found.append(f"{at(key)}: {obs.who} (seat {seat}) sees {view!r}; the query says {projection}")

    by_exec: dict[int, list[tuple[tuple[n.NodeKey | None, ...], int, tuple[Any, ...]]]] = defaultdict(list)
    for keys, exec_id, seat, event, _moving in line.events:
        by_exec[exec_id].append((keys, seat, event))
        if event[0] == "was":
            continue
        for key in keys:
            if key is None:
                continue
            if key[3] == "Block":
                key = runs.get(key[:3], key)
            answer = answers.get(key)
            if isinstance(answer, Told) and answer.diagnostic.code is Code.NOTHING_SEEN_HERE:
                found.append(f"{at(key)}: moves no card and asks no seat, says the query; play emits {event[0]}")

    for exec_id, evs in by_exec.items():
        key = evs[0][0][-1] if evs[0][0] else None
        if key is None or key[0] != here:
            continue
        seats = answers.get(key)
        if not isinstance(seats, q.Seats):
            continue
        kinds = {event[0] for _keys, _seat, event in evs}
        if seats.site == "reveal" and {s for _k, s, e in evs if e[0] == "reveal"} != set(range(checked.game.players.count)):
            found.append(f"{at(key)}: a reveal that does not reach every seat")
        if seats.site == "shuffle" and kinds - {"was"}:
            found.append(f"{at(key)}: a shuffle that emits {sorted(kinds)}")
        for _keys, seat, event in evs:
            if event[0] != "asked":
                continue
            if seats.construct is not None and event[2] != seats.construct:
                found.append(f"{at(key)}: asked as {event[2]!r}; the query says {seats.construct!r}")
            if seats.decider == "the acting seat" and seat != line.actors.get(exec_id):
                found.append(f"{at(key)}: asked seat {seat}; the acting seat was {line.actors.get(exec_id)}")
        for announced in _picks(evs):
            if seats.pick == "announced" and not announced:
                found.append(f"{at(key)}: a {seats.construct} pick no seat heard; the query says every seat hears it")
            if seats.pick == "moved" and announced:
                found.append(f"{at(key)}: a {seats.construct} pick every seat heard; the query says none does")
    return found, line.ran


def _picks(evs: list[tuple[tuple[n.NodeKey | None, ...], int, tuple[Any, ...]]]) -> list[bool]:
    """Each pick made in one run of a site, and whether its decider's pick was
    announced before the next ask: a pick counts once its decider chose."""
    out: list[bool] = []
    asker: int | None = None
    chose = announced = False
    for _keys, seat, event in [*evs, ((), -1, ("asked", "", "", 1, None))]:
        if event[0] == "asked":
            if asker is not None and chose:
                out.append(announced)
            asker, chose, announced = seat, False, False
        elif event[0] == "chose" and seat == asker:
            chose = True
        elif event[0] == "announce" and event[1] == asker:
            announced = True
    return out


def _unreached(path: Path, ran: set[n.NodeKey]) -> list[str]:
    _checked, answers, _runs = _answers(path)
    return sorted(
        f"{k[3]}@{k[1]}"
        for k, a in answers.items()
        if isinstance(a, q.Seats) and k not in ran
    )


@pytest.mark.parametrize("path", GAMES, ids=lambda p: p.stem)
def test_the_query_agrees_with_play(path: Path, record_property: Any) -> None:
    """red under: in `query._observers`, `learns = True` for every kind of
    seat; the trick round's source read from its own field alone
    (`play_source_for` ignored); an end the query cannot name read as
    `trivial`; a `run` answered `nothing-seen-here`; `PICK_SHOWN["climb"]`
    set to "moved"."""
    found, ran = _findings(path, ORACLE_SEEDS[0])
    record_property("unreached", _unreached(path, ran))
    assert not found, "\n".join(dict.fromkeys(found))


@pytest.mark.slow
@pytest.mark.parametrize("seed", ORACLE_SEEDS[1:])
@pytest.mark.parametrize("path", GAMES, ids=lambda p: p.stem)
def test_the_query_agrees_with_play_on_more_lines(path: Path, seed: int, record_property: Any) -> None:
    found, ran = _findings(path, seed)
    record_property("unreached", _unreached(path, ran))
    assert not found, "\n".join(dict.fromkeys(found))


# --- the pick table --------------------------------------------------------------


def test_the_pick_table_names_every_construct() -> None:
    """red under: delete the `"joint"` row of `observe.PICK_SHOWN`."""
    assert set(observe.PICK_SHOWN) == set(CONSTRUCTS)


@cache
def _asked_constructs() -> dict[str, set[str]]:
    """Each construct, and the corpus games whose first oracle line asks it."""
    out: dict[str, set[str]] = defaultdict(set)
    for path in GAMES:
        line = _play(path, ORACLE_SEEDS[0])
        for _keys, _exec, _seat, event, _moving in line.events:
            if event[0] == "asked":
                out[event[2]].add(path.stem)
    return out


def test_every_construct_is_asked_somewhere() -> None:
    """Every row of the pick table is held by some line of the corpus, so no
    row's claim stands unrun."""
    asked = _asked_constructs()
    assert set(asked) == set(CONSTRUCTS), sorted(set(CONSTRUCTS) - set(asked))
