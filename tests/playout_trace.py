"""Harness-side reconstruction of playout facts that no game text reports.

The playout harness consumes per-game facts that used to arrive as `ctx.trace`
events from registered "primitives": Coup's influence-flip sequence
(`coup_reveal`), Tichu's per-hand double-victory flag and captured card points
(`tichu_hand`), and Coup's end-of-game coins, alive vector and conservation
totals (`coup_game`). They derive here, at the harness layer, so the rules text
carries no instrumentation calls.

Which channel a fact derives from follows the law that decides where the fact
lives (decisions.md, "Hidden information lives only in zones; state is
public"). Hidden information rides zones, so a zone fact derives from the
kernel's per-observer [[observation-event]]s (cardlang/runtime/observe.py) —
the same substrate the OpenSpiel adapter projects information sets from. A
[[state]] variable is public to every observer and rides no observation event,
so a state fact is read off the live world at the terminal moment, where the
information state and the command line read it (`TerminalState`).

Each observation reconstructor installs as `play_game(..., observer=log.observer)`
and reads a single observer's stream (player 0). One observer suffices: every
fact consumed that way rides a zone whose declared projection is identity for
every observer (Coup's `revealed` is a PlayerPile, Tichu's `captured` a
TeamPile and its trick pile a TrickPile — cardlang/stdlib/zones.py,
ZONE_PROJECTIONS), so observer 0's `move` events carry full card identity at
every consumed transfer.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from cardlang.runtime.state import RuntimeState
from cardlang.runtime.values import Player

# Suit renderings of cardlang.runtime.values.Card.__str__: the four French
# symbols plus Tarot's atout/excuse stars; any other suit renders as
# ":<suit>" (Tichu's specials, Coup's court).
_SUIT_SYMBOLS = frozenset("♣♦♥♠★☆")

# Tichu's card-point table, kept literal rather than imported from
# cardlang.runtime.tichu_combinations so the harness recomputation stays an
# independent oracle for the routing it audits.
_TICHU_POINTS = {"K": 10, "10": 10, "5": 5, "Dragon": 25, "Phoenix": -25}


def rank_of(card_str: str) -> str:
    """The rank of a rendered card string (`K♣` -> `K`, `Dog:special` -> `Dog`)."""
    if card_str[-1] in _SUIT_SYMBOLS:
        return card_str[:-1]
    return card_str.split(":", 1)[0]


def _key_of(label: str, family: str) -> int:
    """The instance key of a family zone label (`revealed[2]` -> 2)."""
    return int(label[len(family) + 1 : -1])


def _moved(view: Any) -> int:
    """How many cards a movement view reports: identity views are card-string
    tuples, count_only views are ints, trivial views are None."""
    if isinstance(view, tuple):
        return len(view)
    return int(view) if isinstance(view, int) else 0


class TerminalState:
    """Named [[state]] variables, read off the world at the terminal position.

    A state variable is public to every observer and rides no
    [[observation-event]] (decisions.md, "Hidden information lives only in
    zones; state is public"), so a harness reads one where the information
    state reads it: off the live world. `play_game`'s `on_first_decision` seam
    is what hands a caller that world, and the `game_end` trace fires after the
    last phase and BEFORE the game-level frame pops, which is what makes this
    read the terminal position rather than a picture of one — after `play_game`
    returns, the frame is gone and every state variable is out of scope. That
    ordering is owned by
    `tests/test_cli_surface.py::test_info_state_carries_the_state_variables`,
    which reddens if the emit moves past the pop; this reader is a second
    consumer of the same fact and asserts nothing about it independently. The
    event that promotes the fact to a return value on `GameResult` — where it
    could not be read at the wrong moment — is a third consumer, or a game
    whose playout makes no decision, for which the seam never fires at all.

    Install on one `play_game` call as both `tracer=` and `on_first_decision=`:

        terminal = TerminalState(("coins", "treasury"))
        play_game(game, rng, terminal.tracer, on_first_decision=terminal.hold)

    Captured values are detached from the frame they are read out of: the
    frames this reads are mutated and popped after the capture, so a reference
    would record the terminal state only by accident. One level is the whole
    depth — a declared state variable is a scalar, or a per-member dict of
    them (`runtime/driver._declare_state`), and nothing nests below that.
    """

    def __init__(self, names: Sequence[str]) -> None:
        self._names = tuple(names)
        self._world: list[RuntimeState] = []
        self._at_end: tuple[dict[str, Any], dict[str, int]] | None = None

    def hold(self, rs: RuntimeState) -> None:
        """`play_game(..., on_first_decision=...)` — the live world."""
        self._world.append(rs)

    def tracer(self, event: str, data: Any) -> None:
        """`play_game(..., tracer=...)` — the terminal moment."""
        if event != "game_end" or not self._world:
            return
        rs = self._world[0]
        captured = {name: _copied(rs.get(name)) for name in self._names}
        self._at_end = (captured, dict(data))

    def _captured(self) -> tuple[dict[str, Any], dict[str, int]]:
        if self._at_end is None:
            raise AssertionError(
                "no terminal capture: install this reader as BOTH `tracer=` "
                "and `on_first_decision=` on the same `play_game` call, and "
                "give it a game whose playout reaches a decision"
            )
        return self._at_end

    @property
    def state(self) -> dict[str, Any]:
        """The named state variables as they stood at `game_end`."""
        return self._captured()[0]

    @property
    def total_cards(self) -> int:
        """Cards across every zone — the driver's own terminal census
        (`cardlang/runtime/driver.py`, `_final_card_census`), which it emits
        for every game."""
        return self._captured()[1]["total"]


def _copied(value: Any) -> Any:
    """One state variable, detached from the frame it was read out of. An
    indexed variable is a per-member dict of scalars; a whole one is a scalar,
    so the shallow copy is the deep one."""
    return dict(value) if isinstance(value, dict) else value


def coup_totals(terminal: TerminalState) -> dict[str, int]:
    """Coup's two conservation totals from a `("coins", "treasury")` capture:
    50 coins (the treasury plus every player's) and 15 influence cards."""
    coins = terminal.state["coins"]
    return {
        "total_coins": int(terminal.state["treasury"])
        + sum(int(c) for c in coins.values()),
        "total_cards": terminal.total_cards,
    }


class CoupReveals:
    """The influence-flip sequence, in flip order, as `[victim, rank]` pairs.

    Every influence loss is one `move chosen one card from influence[victim]
    to revealed[victim]` (coup.cardlang, `lose_influence`), and nothing else
    moves cards into `revealed` — so the flips are exactly observer 0's
    `move` events whose destination is a `revealed` instance, and the
    PlayerPile destination view carries each flipped card's identity.
    """

    def __init__(self) -> None:
        self.reveals: list[list[int | str]] = []

    def observer(self, player: Player, event: tuple[Any, ...]) -> None:
        if player != 0 or event[0] != "move":
            return
        _, _src, _src_view, dst, dst_view = event
        if isinstance(dst, str) and dst.startswith("revealed["):
            victim = _key_of(dst, "revealed")
            for card_str in dst_view:
                self.reveals.append([victim, rank_of(card_str)])


class TichuHands:
    """Per-hand double-victory flag and captured card points.

    Card points accumulate over the identity views of every movement into or
    out of a `captured` instance (the TeamPile projection is identity for all
    observers), so at `hand_end` the running total equals the points sitting
    in the two piles after routing. The finishing order derives from hand
    sizes tracked through movement counts, with one deliberate exception
    mirrored from the game text (tichu.cardlang, the Dog branch): a shed on a
    trick-ending Dog lead enters no finishing order, so a lone Dog played
    into the trick pile records no shed here either. The hand boundary is
    the gather (`move all cards to deck` in `before_each`): the first
    movement into the deck resets the per-hand trackers, and its
    captured-side identity views unwind the point total on their own.

    Read `hand_summary()` at each `hand_end` tracer event; nothing else needs
    resetting between hands.
    """

    def __init__(self, team_of: dict[Player, int]) -> None:
        self._team_of = team_of
        self._points = 0
        self._hand_sizes: dict[int, int] = {}
        self._out_order: list[int] = []

    def observer(self, player: Player, event: tuple[Any, ...]) -> None:
        if player != 0 or event[0] != "move":
            return
        _, src, src_view, dst, dst_view = event
        if dst == "deck":
            self._hand_sizes.clear()
            self._out_order.clear()
        if isinstance(dst, str) and dst.startswith("captured["):
            self._points += sum(_TICHU_POINTS.get(rank_of(c), 0) for c in dst_view)
        if isinstance(src, str) and src.startswith("captured["):
            self._points -= sum(_TICHU_POINTS.get(rank_of(c), 0) for c in src_view)
        if isinstance(dst, str) and dst.startswith("hand["):
            key = _key_of(dst, "hand")
            self._hand_sizes[key] = self._hand_sizes.get(key, 0) + _moved(dst_view)
        if isinstance(src, str) and src.startswith("hand[") and dst != "deck":
            key = _key_of(src, "hand")
            before = self._hand_sizes.get(key, 0)
            self._hand_sizes[key] = before - _moved(src_view)
            dog_shed = (
                dst == "trick_pile"
                and isinstance(dst_view, tuple)
                and len(dst_view) == 1
                and rank_of(dst_view[0]) == "Dog"
            )
            if before > 0 and self._hand_sizes[key] == 0 and not dog_shed:
                self._out_order.append(key)

    def hand_summary(self) -> list[int]:
        """`[double_victory, card_points]` for the hand just ended — the
        shape the per-hand golden rows append."""
        out = self._out_order
        double_victory = (
            len(out) >= 2 and self._team_of[out[0]] == self._team_of[out[1]]
        )
        return [int(double_victory), self._points]
