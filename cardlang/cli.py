"""Command-line entry point: check a game file, or play one through.

    cardlang docs/games/hearts.cardlang            # check only; silent on success
    cardlang docs/games/hearts.cardlang --emit-ir  # check, then print the IR JSON
    cardlang check docs/games/hearts.cardlang      # the same check, named
    cardlang play docs/games/hearts.cardlang       # one uniform-random self-play

`cardlang <file>` names no command: `main` reads it as `check`, so the two
spellings reach one parser rather than two code paths that can disagree about
what `--emit-ir` means.

This module owns one defect class — the values a caller supplies, which no
earlier layer sees: the path argument, and the seat `--info-state` names.
Everything else it RENDERS rather than decides. The compile stages' [[failure-
channel]] and the runtime's are both already typed, and each failure reaches
the [[author]] who can act on it (`cardlang/runtime/errors.py`, Contract): a
`GameDescriptionError` the game author, an `InstallationError` whoever
installed this checkout. It never discriminates the `GameDescriptionError`
subtypes; which ROLE of guard fired is the suite's question, not a caller's.

An exception outside those channels keeps its traceback. For the engine's own
assertions that is right — they address the engine maintainer, and the
traceback is what that reader needs. `IllegalMove` reaches here classified as
neither, and issue #554 records it.

Exit codes: 0 on success; 1 when the game file is at fault, whether a compile
stage or the runtime says so; 2 when the invocation cannot be carried out —
an unreadable path, a seat the game does not seat, a broken checkout, an
argparse usage error.
"""

from __future__ import annotations

import argparse
import json
import random
import sys
from pathlib import Path
from typing import Any

from cardlang.ast import nodes as n
from cardlang.diagnostics import DiagnosticError
from cardlang.openspiel.infostate import information_state
from cardlang.openspiel.replay import returns_for
from cardlang.pipeline import check_source, compile_path
from cardlang.runtime.chooser import random_chooser, sequential_decisions
from cardlang.runtime.driver import GameResult, play_game
from cardlang.runtime.errors import GameDescriptionError, InstallationError
from cardlang.runtime.observe import render
from cardlang.runtime.state import RuntimeState
from cardlang.runtime.values import Player

# The command names, and the one place they are written. `main`'s dispatch
# reads it, the parser is built from it, and the surface grid derives its
# command axis from it (tests/test_cli_surface.py), so a command that exists
# cannot be one the grid does not cross.
COMMANDS: tuple[str, ...] = ("check", "play")

_EXIT_OK = 0
_EXIT_GAME_AT_FAULT = 1
_EXIT_CANNOT_PROCEED = 2


def build_parser() -> argparse.ArgumentParser:
    """The parser for every accepted invocation.

    Public because the surface grid derives its axes from it rather than from
    a second list that could drift out of step with the parser it describes.
    """
    parser = argparse.ArgumentParser(
        prog="cardlang",
        description="Check a card-game description, or play one through.",
    )
    # No `metavar`: argparse then spells the choices into every usage line it
    # prints, so a refusal that shows usage — a command in the wrong slot, a
    # command omitted — names what is valid without the message saying so.
    commands = parser.add_subparsers(dest="command", required=True)

    check = commands.add_parser(
        "check", help="parse and statically check a game file; silent on success"
    )
    check.add_argument(
        "file", help="game file (.cardlang raw DSL, or .md with a fenced DSL block)"
    )
    check.add_argument(
        "--emit-ir",
        action="store_true",
        help="print the validated IR as JSON on success",
    )

    play = commands.add_parser(
        "play", help="check a game file, then play one uniform-random self-play"
    )
    play.add_argument(
        "file", help="game file (.cardlang raw DSL, or .md with a fenced DSL block)"
    )
    play.add_argument(
        "--seed",
        type=int,
        metavar="N",
        help="seed the playout — the shuffle and the uniform-random policy "
        "alike; with none given a seed is drawn and reported, so any run repeats",
    )
    play.add_argument(
        "--info-state",
        type=int,
        metavar="SEAT",
        help="also print that seat's derived information state at the "
        "terminal position, or at the decision --at names",
    )
    play.add_argument(
        "--decisions",
        action="store_true",
        help="also list the playout's decisions, numbered the way --at numbers "
        "them — one entry per choice, so a call taking several cards is several "
        "— with who makes each and what it is chosen from",
    )
    play.add_argument(
        "--at",
        type=int,
        metavar="N",
        help="show the --info-state seat's view at decision N — the position "
        "just before that one choice is made — instead of at the terminal "
        "position; --decisions lists the numbers",
    )
    return parser


def _normalize(argv: list[str]) -> list[str]:
    """`cardlang <file>` reads as `cardlang check <file>`.

    Only a first token that could not be a command is rewritten, so `-h` still
    reaches the top parser and an explicit command passes through untouched.
    """
    if not argv or argv[0] in COMMANDS or argv[0] in ("-h", "--help"):
        return argv
    return ["check", *argv]


def _unreadable(path: Path) -> str | None:
    """Why the front end cannot read `path`, or None when it can.

    The Owner Guard for the path argument, and it covers that argument's whole
    failure class rather than its commonest member: a name that is nothing, a
    name that is a directory, and a file the process cannot decode as text all
    reach `pipeline.check_source`'s unguarded `read_text` otherwise, where they
    surface as a traceback addressed to nobody. The probe read is what makes
    the last two answerable here instead of there.

    Its result is discarded and the file is read a second time by the pipeline,
    deliberately: threading the text through `check_source` would change a
    pipeline signature — and the extension dispatch that reads it — for one
    caller's convenience, at a cost no game file's size makes worth paying.
    """
    if not path.exists():
        return f"cannot read {path}: no such file"
    if not path.is_file():
        return f"cannot read {path}: not a file"
    try:
        path.read_text()
    except OSError as exc:
        return f"cannot read {path}: {exc.strerror or exc}"
    except UnicodeDecodeError:
        return f"cannot read {path}: not text this front end can decode"
    return None


def main(argv: list[str] | None = None) -> int:
    raw = list(sys.argv[1:] if argv is None else argv)
    args = build_parser().parse_args(_normalize(raw))
    implicit = bool(raw) and raw[0] not in COMMANDS and raw[0] not in ("-h", "--help")

    path = Path(args.file)
    refusal = _unreadable(path)
    if refusal is not None:
        print(f"cardlang: {refusal}", file=sys.stderr)
        if implicit:
            # The token stood where a command may also stand, so the refusal
            # answers both readings rather than picking one.
            print(
                f"cardlang: if you meant a command, they are: {', '.join(COMMANDS)}",
                file=sys.stderr,
            )
        return _EXIT_CANNOT_PROCEED

    try:
        if args.command == "play":
            return _play(path, args.seed, args.info_state, args.at, args.decisions)
        return _check(path, args.emit_ir)
    except DiagnosticError as exc:
        print(exc.diagnostic.format(), file=sys.stderr)
        for note in getattr(exc, "__notes__", []):
            print(note, file=sys.stderr)
        return _EXIT_GAME_AT_FAULT
    except GameDescriptionError as exc:
        print(f"cardlang: playing {path} failed", file=sys.stderr)
        print(f"  {exc}", file=sys.stderr)
        print(
            "  the static checks passed — this is a rule only a playout "
            "reaches, and the line played was uniform-random",
            file=sys.stderr,
        )
        return _EXIT_GAME_AT_FAULT
    except InstallationError as exc:
        print("cardlang: this checkout of cardlang is incomplete", file=sys.stderr)
        print(f"  {exc}", file=sys.stderr)
        print("  reinstall the package, or restore what the message names", file=sys.stderr)
        return _EXIT_CANNOT_PROCEED


def _check(path: Path, emit_ir: bool) -> int:
    if emit_ir:
        print(json.dumps(compile_path(path), indent=2))
    else:
        check_source(path)
    return _EXIT_OK


def _play(
    path: Path, seed: int | None, seat: int | None, at: int | None, listing: bool
) -> int:
    game = check_source(path)
    seats = game.players.low
    if seat is not None and not 0 <= seat < seats:
        # Nothing downstream would notice: `information_state` takes any int
        # and projects zones through whatever observer it is handed, so an
        # out-of-range seat renders a plausible string for nobody's view.
        print(
            f"cardlang: {path} seats 0..{seats - 1}; --info-state {seat} names "
            "no seat at this table",
            file=sys.stderr,
        )
        return _EXIT_CANNOT_PROCEED
    # Both `--at` refusals a playout cannot inform are taken here, beside the
    # seat check and before the game runs; the range refusal needs the count
    # only the playout produces and waits below.
    if at is not None and seat is None:
        print(
            f"cardlang: --at {at} says which decision to look at; add "
            "--info-state SEAT to say whose view to show",
            file=sys.stderr,
        )
        return _EXIT_CANNOT_PROCEED
    if at is not None and at < 0:
        print(
            f"cardlang: --at {at} names no decision; a playout's decisions "
            "start at 0",
            file=sys.stderr,
        )
        return _EXIT_CANNOT_PROCEED

    drawn = random.randrange(2**31) if seed is None else seed
    logs: dict[Player, list[tuple[Any, ...]]] = {p: [] for p in range(seats)}
    snapshot: list[str] = []
    world: list[RuntimeState] = []
    # One entry per decision the playout makes, in order: its description
    # where a line will be shown, None otherwise. `len` is the count `--at`
    # indexes. A line renders every candidate OFFERED — a far wider set than
    # the cards taken, and the one place `observe.render` can meet a shape no
    # playout hands it — so only a line that will be shown is rendered at all.
    decisions: list[str | None] = []

    def observe(player: Player, event: tuple[Any, ...]) -> None:
        logs[player].append(event)

    def hold(rs: RuntimeState) -> None:
        # `on_first_decision` is the only seam handing a caller the world at
        # all, and it fires inside the first Chooser call — so `world[0]` is
        # already there when `choose` first runs, and it is the LIVE world, not
        # a capture: every reader below renders from it at the moment it reads.
        # Issue #555 is the driver returning that world instead.
        world.append(rs)

    def trace(event: str, _data: Any) -> None:
        # `driver.play_game` emits `game_end` after the last phase and BEFORE
        # it pops the game-level frame, which is what makes this the terminal
        # position rather than a picture of one: taken after `play_game`
        # returns, the frame is gone and the state variables render empty.
        # Moving the emit past the pop would empty them here too, silently;
        # tests/test_cli_surface.py pins the segment against that.
        if event == "game_end" and seat is not None and at is None and world:
            snapshot.append(information_state(seat, world[0], logs[seat]))

    rng = random.Random(drawn)
    # The one generator, driving the shuffle and the uniform-random policy
    # alike — `play_game` builds exactly this chooser from the generator it is
    # handed when a caller supplies none, so numbering the decisions leaves
    # the seeded playout where it was.
    play_uniformly = random_chooser(rng)

    def choose(player: Player, candidates: list[Any], count: int) -> list[Any]:
        # The candidates are drawn in ONE call, which is what keeps a seeded
        # playout where it was: `play_game` would draw them in one call too.
        # Numbering walks them afterwards through `sequential_decisions`, the
        # tree's own reading of a multi-card call, so the command and the
        # adapter reach the same positions in the same order and record the
        # same choices.
        taken = iter(play_uniformly(player, candidates, count))

        def decide(actor: Player, pool: list[Any]) -> Any:
            # A decision runs while the frames still stand — the same window
            # the terminal snapshot needs, reached at a decision rather than at
            # the end. The view is rendered here rather than held, because
            # `world[0]` is the live world and goes on changing; the seat's log
            # is complete for this position and grows only forward (perfect
            # recall), so nothing needs trimming.
            index = len(decisions)
            decisions.append(
                _decision(actor, pool) if listing or index == at else None
            )
            if index == at and seat is not None:
                snapshot.append(information_state(seat, world[0], logs[seat]))
            return next(taken)

        return sequential_decisions(player, candidates, count, decide, observe)

    result = play_game(
        game,
        rng,
        trace,
        chooser=choose,
        observer=observe,
        on_first_decision=hold,
    )
    # The driver's own count, not a second one taken off the list: the two are
    # the same unit and `tests/test_cli_surface.py` pins them equal.
    made = world[0].decisions_made if world else 0
    print(_summary(game, result, made, drawn))
    if listing:
        print()
        print(_listing(decisions))

    if seat is None:
        return _EXIT_OK
    if not decisions:
        # No decision means `on_first_decision` never fired, so there is no
        # world to project from — at a decision or at the end alike.
        print(
            f"cardlang: {path} reached its end without a decision, so the "
            "engine exposes no world to project a seat's view from",
            file=sys.stderr,
        )
        return _EXIT_CANNOT_PROCEED
    if at is not None and at >= len(decisions):
        # Naming the range rather than clamping: the nearest decision is an
        # answer to a question nobody asked, and it would read as the one
        # asked for.
        print(
            f"cardlang: this playout has {len(decisions)} decisions, so --at "
            f"takes 0..{len(decisions) - 1}; --at {at} names none of them",
            file=sys.stderr,
        )
        return _EXIT_CANNOT_PROCEED
    if at is None:
        print(f"\ninformation state, seat {seat}, at the terminal position:")
    else:
        where = decisions[at]
        assert where is not None, "a named decision always renders its line"
        print(f"\ninformation state, seat {seat}, at decision {at} ({where}):")
    print(snapshot[0])
    return _EXIT_OK


# How many candidates a decision's line names before it trails off. A line is
# for recognizing the decision, not for reading the whole pool.
_CANDIDATES_SHOWN = 6


def _decision(player: Player, candidates: list[Any]) -> str:
    """One decision, as both the listing and the `--at` echo name it.

    The candidates are what tell a designer WHICH decision this is — a discard
    offers cards where a betting round offers `call, fold, raise` — so they
    carry the line. `observe.render` is the rendering the observation log
    already uses, so a candidate reads the same way in both places. A call
    taking several cards reads as several lines, each offering what the ones
    before it left.

    Two betting rounds offer the same candidates and so read alike; the phase
    is the name that would separate them, and the Chooser seam carries no
    phase to put there (issue #605).
    """
    shown = [str(render(c)) for c in candidates[:_CANDIDATES_SHOWN]]
    if len(candidates) > _CANDIDATES_SHOWN:
        shown.append("...")
    return f"P{player} chooses 1 of {len(candidates)}: " + ", ".join(shown)


def _listing(decisions: list[str | None]) -> str:
    """Every decision the playout made, numbered the way `--at` numbers them.

    One entry per choice made, which is the unit throughout: the game tree
    branches once per card of a multi-card call, the adapter replays one action
    for each, `max_length` bounds that same count (`docs/decisions.md`, "Game
    length as a declared contract"), and the summary's `decisions` line reports
    it. A second unit here would put a number on the screen that `--at` does
    not accept.
    """
    total = len(decisions)
    if total == 0:
        return "this playout makes no decisions, so --at names none"
    head = f"{total} decisions; --at takes 0..{total - 1}"
    width = len(str(total - 1))
    rows = [
        f"  {index:>{width}}  {line}"
        for index, line in enumerate(decisions)
        if line is not None
    ]
    return "\n".join([head, *rows])


def _summary(game: n.Game, result: GameResult, decisions: int, seed: int) -> str:
    """The outcome in per-seat returns.

    `result.scores` is keyed by the `winner:` target's own index domain, so a
    team-scored game's keys are teams and a `loser:` game has none at all
    (`driver.GameResult`). `returns_for` is where that inversion already lives;
    reading the dict here instead would pay the wrong seats in exactly the
    games where nobody would notice.

    It inverts the seat-anchored roles `replay._RETURNS_KEYED_ROLES` names, and
    raises on any other — so a `winner:` target indexed by a role added later
    stops this command with an engine assertion rather than printing a plausible
    line. That refusal is what makes reading returns here safe; it is not a
    claim that every index role is handled.
    """
    returns = returns_for(game, result)
    best = max(returns)
    seats = ", ".join(f"P{p} {_trim(r)}" for p, r in enumerate(returns))
    top = ", ".join(f"P{p}" for p, r in enumerate(returns) if r == best)
    length = str(decisions)
    if result.hands_played:
        length += f" across {result.hands_played} hands"
    return (
        f"{game.name} — {game.players.low} seats, uniform-random self-play\n"
        f"  returns      {seats}\n"
        f"  best return  {top}\n"
        f"  decisions    {length}\n"
        f"  seed         {seed}"
    )


def _trim(value: float) -> str:
    """An integral return prints without its decimal tail; scores are counts."""
    return str(int(value)) if value == int(value) else str(value)


if __name__ == "__main__":
    raise SystemExit(main())
