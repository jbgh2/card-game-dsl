"""What an observer learns from a simultaneous block, and when.

property:        While an `each … simultaneously` block runs, an observer
                 receives nothing but its own `asked` and `chose` records; at
                 block-exit it receives the block's moves as one batch — one
                 `move` event per seat that passed cards, in seat order, with
                 nothing between them (decisions.md, "Simultaneous moves and
                 atomic effect", "Observation semantics").
domain:          Every game in the adapter registry (`GAMES`), played natively
                 at each seed in `_SEEDS`, under the game's reference policy
                 where a uniform draw does not finish it
                 (`tests/playout_policy.REFERENCE_POLICIES`); the blocks are found by execution
                 (every entry to `execute._each_simultaneous`), not by name, so
                 a game that gains a block joins the domain. The witness guard
                 below fails when no game reaches one.
registry:        games: `cardlang.openspiel.registry.GAMES`; event kinds:
                 `cardlang.runtime.observe.EVENT_PAYLOADS`.
does not prove:  The count for a transfer both of whose sides are trivial to
                 an observer, which emits nothing: no corpus block moves cards
                 between trivial zones, so the expected count is every seat
                 that passed. The seat order is read off each event's source
                 label, which names the passing seat in every corpus block.
"""

from __future__ import annotations

import random
import re
from pathlib import Path
from typing import Any

import pytest

from cardlang.openspiel.registry import GAMES
from cardlang.openspiel.replay import generator_for, load
from cardlang.runtime import execute
from cardlang.runtime.chooser import random_chooser
from cardlang.runtime.driver import play_game
from cardlang.runtime.state import Ctx
from tests.playout_policy import reference_policy_for

GAMES_DIR = Path(__file__).resolve().parent.parent / "docs" / "games"

_SEEDS = (0, 1, 2)

# One entry of the shared record: a mark, or an event one observer received.
Entry = tuple[str, Any, Any]


def _record(short_name: str, seed: int, monkeypatch: pytest.MonkeyPatch) -> list[Entry]:
    path = str(GAMES_DIR / GAMES[short_name])
    game, _ = load(path)
    record: list[Entry] = []
    block = execute._each_simultaneous

    def marked(stmt: Any, ctx: Ctx) -> None:
        record.append(("enter", None, None))
        block(stmt, ctx)
        record.append(("exit", None, None))

    monkeypatch.setattr(execute, "_each_simultaneous", marked)
    rng = random.Random(seed)
    play_game(
        game,
        generator_for(path, seed),
        chooser=reference_policy_for(Path(path).stem, rng) or random_chooser(rng),
        observer=lambda seat, event: record.append(("event", seat, event)),
    )
    return record


def _blocks(record: list[Entry]) -> list[list[Entry]]:
    """The entries between each block's entry and its exit."""
    found: list[list[Entry]] = []
    current: list[Entry] | None = None
    for entry in record:
        if entry[0] == "enter":
            assert current is None, "a block entered inside a block"
            current = []
        elif entry[0] == "exit":
            assert current is not None
            found.append(current)
            current = None
        elif current is not None:
            current.append(entry)
    return found


_SEAT_KEY = re.compile(r"\[(\d+)\]$")


@pytest.mark.parametrize("seed", _SEEDS)
@pytest.mark.parametrize("short_name", sorted(GAMES))
def test_a_simultaneous_block_lands_as_one_batch_at_block_exit(
    short_name: str, seed: int, monkeypatch: pytest.MonkeyPatch
) -> None:
    """red under: apply each seat's transfer as soon as it has chosen, in the
    selection loop of `execute._each_simultaneous`; a later seat's `asked` and
    `chose` then land after an earlier seat's movement, before block-exit."""
    blocks = _blocks(_record(short_name, seed, monkeypatch))
    seats = load(str(GAMES_DIR / GAMES[short_name]))[0].players.count
    for number, entries in enumerate(blocks):
        where = f"{short_name} seed {seed}, block {number}"
        passed = sorted(
            {seat for _, seat, event in entries if event[0] == "chose"}
        )
        for observer in range(seats):
            events = [event for _, seat, event in entries if seat == observer]
            kinds = [event[0] for event in events]
            first_move = kinds.index("move") if "move" in kinds else len(kinds)
            before, batch = events[:first_move], events[first_move:]
            assert all(event[0] in ("asked", "chose") for event in before), (
                f"{where}: P{observer} learned {[e for e in before if e[0] not in ('asked', 'chose')]} "
                f"before block-exit"
            )
            assert all(event[0] == "move" for event in batch), (
                f"{where}: P{observer}'s batch holds {[e[0] for e in batch]}, "
                f"not movement events alone"
            )
            assert all(event[0] != "asked" or observer in passed for event in before)
            assert len(batch) == len(passed), (
                f"{where}: P{observer} received {len(batch)} movement events for "
                f"{len(passed)} seats' transfers"
            )
            order = [
                int(match.group(1))
                for event in batch
                if (match := _SEAT_KEY.search(str(event[1]))) is not None
            ]
            assert order == passed, (
                f"{where}: P{observer}'s batch runs in the order {order}, not seat order {passed}"
            )


def test_some_game_reaches_a_simultaneous_block(monkeypatch: pytest.MonkeyPatch) -> None:
    """The witness guard: the cell above is vacuous for a game that reaches no
    block, so the corpus must hold one that does."""
    reached = [name for name in sorted(GAMES) if _blocks(_record(name, _SEEDS[0], monkeypatch))]
    assert reached, "no registered game reaches an `each … simultaneously` block"
