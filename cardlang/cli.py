"""Command-line entry point: check a game file, play it, or watch it played.

    cardlang docs/games/hearts.cardlang                       # check only; silent on success
    cardlang docs/games/hearts.cardlang --emit-ir             # check, then print the IR JSON
    cardlang check docs/games/hearts.cardlang                 # the same check, named
    cardlang play docs/games/hearts.cardlang --vs all=random  # take a seat and play it
    cardlang demo docs/games/hearts.cardlang                  # one uniform-random self-play

`cardlang <file>` names no command: `main` reads it as `check`, so the two
spellings reach one parser rather than two code paths that can disagree about
what `--emit-ir` means.

This module owns one defect class — the values a caller supplies, which no
earlier layer sees: the path argument, the seats `--info-state`, `--view` and
`--seat` name, the files `--save` and `--resume` name, and the opponents `--vs`
seats (read and seated by `cardlang.play.opponents`). Everything else it
RENDERS rather than decides. The compile stages' [[failure-channel]] and the
runtime's are both already typed, and each
failure reaches the [[author]] who can act on it (`cardlang/runtime/errors.py`,
Contract): a `GameDescriptionError` the game author, an `InstallationError`
whoever installed this checkout. It never discriminates the `GameDescriptionError`
subtypes; which ROLE of guard fired is the suite's question, not a caller's.

`IllegalMove` is rendered beside them and means something else, which the
message says: the game's own `error(...)` refused, no player was offered the
move, and the game author is who can act — so the file is where to look
without the file being called illegal. Both carry the sentence they escaped
and print it the way a compile diagnostic prints one.

An exception outside those channels keeps its traceback. For the engine's own
assertions that is right — they address the engine maintainer, and the
traceback is what that reader needs.

Exit codes: 0 on success; 1 when the game file is where to look, whether a
compile stage or the runtime says so — which covers both a file that is at
fault and one whose own rule refused with nobody to tell; 2 when the
invocation cannot be carried out — an unreadable path, a seat the game does
not seat, opponents that do not seat every other seat once, a saved game that
cannot be resumed or saved, a game whose decisions the action space cannot
number, a broken checkout, an argparse usage error.
The two are split by who must act, not by how badly it went.
"""

from __future__ import annotations

import argparse
import json
import random
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any, NoReturn

from cardlang.ast import nodes as n
from cardlang.diagnostics import Diagnostic, DiagnosticError, Severity
from cardlang.openspiel.infostate import derive, render_information_state
from cardlang.openspiel.replay import HistoryMismatch, load, returns_for
from cardlang.pipeline import check_source, compile_path, game_identity
from cardlang.play.opponents import (
    ALL,
    EXAMPLE,
    REST,
    Item,
    Unnamed,
    as_flags,
    listing,
    read_item,
    recorded,
    seated,
    seats_named,
)
from cardlang.play.session import (
    SaveFailed,
    Session,
    command,
    path_word,
    read_saved,
    unwritable,
)
from cardlang.play.view import render_view
from cardlang.runtime.chooser import random_chooser, sequential_decisions
from cardlang.runtime.driver import GameResult, play_game
from cardlang.runtime.errors import GameDescriptionError, InstallationError, Located
from cardlang.runtime.observe import render
from cardlang.runtime.state import IllegalMove, RuntimeState
from cardlang.runtime.values import Player


def _add_check_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--emit-ir",
        action="store_true",
        help="print the validated IR as JSON on success",
    )


def _add_demo_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--seed",
        type=int,
        metavar="N",
        help="seed the playout — the shuffle and the uniform-random policy "
        "alike; with none given a seed is drawn and reported, so any run repeats",
    )
    parser.add_argument(
        "--info-state",
        type=int,
        metavar="SEAT",
        help="also print that seat's derived information state at the "
        "terminal position, or at the decision --at names",
    )
    parser.add_argument(
        "--view",
        type=int,
        metavar="SEAT",
        help="also print what that seat knows, laid out for a person to read, "
        "at the terminal position or at the decision --at names",
    )
    parser.add_argument(
        "--decisions",
        action="store_true",
        help="also list the playout's decisions, numbered the way --at numbers "
        "them — one entry per choice, so a call taking several cards is several "
        "— with who makes each and what it is chosen from",
    )
    parser.add_argument(
        "--at",
        type=int,
        metavar="N",
        help="print what --info-state and --view show at decision N — the "
        "position just before that one choice is made — instead of at the "
        "terminal position; --decisions lists the numbers",
    )


def _usage(refusal: str) -> NoReturn:
    """Refuse a value an option's `type=` cannot read. argparse prints the
    refusal as the usage error naming the option, before any game is read."""
    raise argparse.ArgumentTypeError(refusal)


def _file(value: str) -> str:
    if not value:
        _usage("an empty name names no file")
    return value


def _item(value: str) -> Item:
    read = read_item(value)
    if isinstance(read, str):
        _usage(read)
    return read


def _add_play_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--seat",
        type=int,
        metavar="SEAT",
        help="the seat you take, seat 0 unless named",
    )
    parser.add_argument(
        "--vs",
        type=_item,
        action="append",
        metavar="WHO=OPPONENT",
        help="who plays a seat you do not take: WHO is a seat number, all for "
        "every other seat, or rest for the seats no other --vs names; OPPONENT "
        f"is one of {listing()}. Give --vs once for each, as in --vs 1=first "
        f"--vs rest={EXAMPLE}",
    )
    parser.add_argument(
        "--seed",
        type=int,
        metavar="N",
        help="seed the deal and the other seats' picks; with none given a seed "
        "is drawn and reported, so any game repeats",
    )
    parser.add_argument(
        "--save",
        type=_file,
        metavar="FILE",
        help="keep the game in FILE before each of your picks and when you "
        "leave, so --resume can go on with it",
    )
    parser.add_argument(
        "--resume",
        type=_file,
        metavar="FILE",
        help="go on with the game saved in FILE, at the seat and seed and "
        "against the opponents it was played with, saving back to FILE unless "
        "--save names another",
    )


# The commands, and the one place they are written: `build_parser` registers a
# subparser per row and `COMMANDS` is derived from the same rows, so the
# dispatch, the parser and the surface grid's command axis cannot disagree
# about which commands exist. Every row gets the `file` positional from the
# loop rather than from its own adder, which is what lets `main` read
# `args.file` before it knows which command ran.
_COMMAND_TABLE: dict[str, tuple[str, Callable[[argparse.ArgumentParser], None]]] = {
    "check": (
        "parse and statically check a game file; silent on success",
        _add_check_arguments,
    ),
    "play": (
        "check a game file, then take a seat and play it",
        _add_play_arguments,
    ),
    "demo": (
        "check a game file, then play one uniform-random self-play",
        _add_demo_arguments,
    ),
}

COMMANDS: tuple[str, ...] = tuple(_COMMAND_TABLE)

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

    for name, (help_text, add_arguments) in _COMMAND_TABLE.items():
        command = commands.add_parser(name, help=help_text)
        command.add_argument(
            "file", help="game file (.cardlang raw DSL, or .md with a fenced DSL block)"
        )
        add_arguments(command)
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
        if args.command == "demo":
            return _demo(
                path, args.seed, args.info_state, args.view, args.at, args.decisions
            )
        if args.command == "play":
            return _play(path, args.seat, args.seed, args.save, args.resume, args.vs)
        return _check(path, args.emit_ir)
    except DiagnosticError as exc:
        print(exc.diagnostic.format(), file=sys.stderr)
        for note in getattr(exc, "__notes__", []):
            print(note, file=sys.stderr)
        return _EXIT_GAME_AT_FAULT
    except GameDescriptionError as exc:
        print(f"cardlang: playing {path} failed", file=sys.stderr)
        _print_refusal(exc)
        print(
            "  the static checks passed — this is a rule only a playout "
            "reaches, and the line played was uniform-random",
            file=sys.stderr,
        )
        return _EXIT_GAME_AT_FAULT
    except IllegalMove as exc:
        print(f"cardlang: playing {path} failed", file=sys.stderr)
        _print_refusal(exc)
        # `error(...)` is writable in any expression the engine evaluates, so
        # the message names the position it most often guards without claiming
        # the refusal came from there.
        print(
            "  this is your game's own `error(...)` refusing, and a playout "
            "has no player to tell",
            file=sys.stderr,
        )
        print(
            "  from a rule's `if_impossible:` it means no card satisfied that "
            "rule: widen its `demands:`, or give it a card set to fall back on",
            file=sys.stderr,
        )
        return _EXIT_GAME_AT_FAULT
    except InstallationError as exc:
        print("cardlang: this checkout of cardlang is incomplete", file=sys.stderr)
        print(f"  {exc}", file=sys.stderr)
        print("  reinstall the package, or restore what the message names", file=sys.stderr)
        return _EXIT_CANNOT_PROCEED


def _print_refusal(exc: Located) -> None:
    """A refusal, at the sentence that refused.

    Rendered through the checker's own `Diagnostic`, so the two halves of the
    [[failure-channel]] print one shape and cannot drift into two spellings of
    a file position. A refusal that reached no stamping site prints without a
    locator — the engine's own guards, which refuse a world rather than a
    sentence — and an invented span would point the reader at a line where
    nothing happened.
    """
    if exc.span is None:
        print(f"  {exc}", file=sys.stderr)
    else:
        print(Diagnostic(Severity.ERROR, str(exc), exc.span).format(), file=sys.stderr)
    where = [w for w in (
        None if exc.phase is None else f"in phase {exc.phase}",
        None if exc.zone is None else f"moving from {exc.zone}",
    ) if w is not None]
    if where:
        print(f"  {', '.join(where)}", file=sys.stderr)


def _check(path: Path, emit_ir: bool) -> int:
    if emit_ir:
        print(json.dumps(compile_path(path), indent=2))
    else:
        check_source(path)
    return _EXIT_OK


def _cannot(message: str) -> int:
    print(f"cardlang: {message}", file=sys.stderr)
    return _EXIT_CANNOT_PROCEED


def _unnamed(
    path: Path,
    seat: int | None,
    seed: int | None,
    save: str | None,
    items: list[Item],
    unnamed: Unnamed,
) -> str:
    """The refusal of a composition that leaves seats unnamed, with a command
    that seats them: the person's own options, and `EXAMPLE` for the rest."""
    words = [path_word(str(path))]
    words += [] if seat is None else ["--seat", str(seat)]
    words += [] if seed is None else ["--seed", str(seed)]
    words += [] if save is None else ["--save", path_word(save)]
    for item in items:
        words += ["--vs", str(item)]
    words += ["--vs", f"{REST if items else ALL}={EXAMPLE}"]
    verb = "needs" if len(unnamed.seats) == 1 else "need"
    return (
        f"name who plays the other seats: you are P{0 if seat is None else seat}, and "
        f"{seats_named(unnamed.seats)} {verb} an opponent, for example\n"
        f"    {command(words)}\n"
        f"the opponents: {listing()}"
    )


def _play(
    path: Path,
    seat: int | None,
    seed: int | None,
    save: str | None,
    resume: str | None,
    vs: list[Item] | None,
) -> int:
    try:
        game, space = load(str(path))
    except NotImplementedError as exc:
        # `ActionSpace.for_game` refuses a decision it has no numbering for; the
        # game is sound and plays in `demo`, and what cannot proceed is a table
        # whose picks are action ids.
        return _cannot(
            f"{path} cannot be played at a table yet: one of its decisions has no "
            f"numbering for its picks ({exc})"
        )
    seats = game.players.count
    if seat is not None and not 0 <= seat < seats:
        return _cannot(f"{path} seats 0..{seats - 1}; --seat {seat} names no seat at this table")
    history: list[Any] = []
    on_file: dict[int, str] | None = None
    if resume is not None:
        saved = read_saved(Path(resume), game_identity(game))
        if isinstance(saved, str):
            return _cannot(f"cannot resume {resume}: {saved}")
        if seat is not None and seat != saved.seat:
            return _cannot(
                f"cannot resume {resume}: it was played at seat {saved.seat}, and "
                f"--seat {seat} names another; leave --seat out to go on with it"
            )
        if seed is not None and seed != saved.seed:
            return _cannot(
                f"cannot resume {resume}: it was dealt with seed {saved.seed}, and "
                f"--seed {seed} names another; leave --seed out to go on with it"
            )
        if not 0 <= saved.seat < seats:
            return _cannot(
                f"cannot resume {resume}: it was played at seat {saved.seat}, and "
                f"{path} seats 0..{seats - 1}"
            )
        read = recorded(saved.opponents, seats, saved.seat, str(path))
        if isinstance(read, str):
            return _cannot(f"cannot resume {resume}: {read}")
        seat, seed, history, on_file = saved.seat, saved.seed, saved.history, read
    person = 0 if seat is None else seat
    if vs is None and on_file is not None:
        opponents = on_file
    else:
        chosen = seated(vs or [], seats, person, str(path))
        if isinstance(chosen, str):
            return _cannot(chosen if resume is None else f"cannot resume {resume}: {chosen}")
        if on_file is not None:
            if chosen != on_file:
                return _cannot(
                    f"cannot resume {resume}: it was played with {as_flags(on_file)}, and "
                    "--vs does not name the same opponents; leave --vs out to go on with it"
                )
            opponents = on_file
        elif isinstance(chosen, Unnamed):
            return _cannot(_unnamed(path, seat, seed, save, vs or [], chosen))
        else:
            opponents = chosen
    save_to = Path(save) if save is not None else None if resume is None else Path(resume)
    if save_to is not None:
        refusal = unwritable(save_to)
        if refusal is not None:
            return _cannot(f"cannot save to {save_to}: {refusal}")
    session = Session(
        str(path),
        game,
        space,
        person,
        random.randrange(2**31) if seed is None else seed,
        opponents,
        history,
        sys.stdin,
        sys.stdout,
        save_to,
    )
    try:
        session.run()
    except SaveFailed as exc:
        return _cannot(str(exc))
    except HistoryMismatch as exc:
        if resume is None:
            raise
        return _cannot(f"cannot resume {resume}: its picks no longer replay in {path} ({exc})")
    except GameDescriptionError as exc:
        print(f"cardlang: playing {path} failed", file=sys.stderr)
        _print_refusal(exc)
        print(
            "  the static checks passed — this is a rule only play reaches; "
            f"{session.who_played()}",
            file=sys.stderr,
        )
        return _EXIT_GAME_AT_FAULT
    except IllegalMove as exc:
        print(f"cardlang: playing {path} failed", file=sys.stderr)
        _print_refusal(exc)
        print("  this is your game's own `error(...)` refusing", file=sys.stderr)
        print(
            "  from a rule's `if_impossible:` it means no card satisfied that "
            "rule: widen its `demands:`, or give it a card set to fall back on",
            file=sys.stderr,
        )
        return _EXIT_GAME_AT_FAULT
    return _EXIT_OK


def _demo(
    path: Path,
    seed: int | None,
    seat: int | None,
    view_seat: int | None,
    at: int | None,
    listing: bool,
) -> int:
    game = check_source(path)
    seats = game.players.count
    for flag, named in (("--info-state", seat), ("--view", view_seat)):
        if named is not None and not 0 <= named < seats:
            # A Shadow Guard of the derivation's own (`infostate._facts`), which
            # refuses a seat nobody sits in only once the playout has run, and
            # in the engine maintainer's channel. Taken here, the refusal comes
            # before the game is played and in the words of the caller who
            # named the seat.
            print(
                f"cardlang: {path} seats 0..{seats - 1}; {flag} {named} names "
                "no seat at this table",
                file=sys.stderr,
            )
            return _EXIT_CANNOT_PROCEED
    named_seats = sorted({s for s in (seat, view_seat) if s is not None})
    # Both `--at` refusals a playout cannot inform are taken here, beside the
    # seat check and before the game runs; the range refusal needs the count
    # only the playout produces and waits below.
    if at is not None and not named_seats:
        print(
            f"cardlang: --at {at} says which decision to look at; add "
            "--view SEAT or --info-state SEAT to say whose view to show",
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
    # What each seat flag prints, keyed by the flag, taken at one position.
    shown: dict[str, str] = {}
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

    def show(rs: RuntimeState, deciding: Player | None) -> None:
        # One derivation per seat named, and every rendering reads it, so the
        # string and the text are of one position.
        views = {named: derive(named, rs, logs[named]) for named in named_seats}
        if seat is not None:
            shown["--info-state"] = render_information_state(views[seat])
        if view_seat is not None:
            shown["--view"] = render_view(
                game, views[view_seat], your_turn=deciding == view_seat
            )

    def trace(event: str, _data: Any) -> None:
        # `driver.play_game` emits `game_end` after the last phase and BEFORE
        # it pops the game-level frame, which is what makes this the terminal
        # position rather than a picture of one: taken after `play_game`
        # returns, the frame is gone and the state variables render empty.
        # Moving the emit past the pop would empty them here too, silently;
        # tests/test_cli_surface.py pins the segment against that.
        if event == "game_end" and named_seats and at is None and world:
            show(world[0], None)

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
            if index == at and named_seats:
                show(world[0], actor)
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

    if not named_seats:
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
        where = "at the terminal position"
    else:
        line = decisions[at]
        assert line is not None, "a named decision always renders its line"
        where = f"at decision {at} ({line})"
    if seat is not None:
        print(f"\ninformation state, seat {seat}, {where}:")
        print(shown["--info-state"])
    if view_seat is not None:
        print(f"\nview, seat {view_seat}, {where}:")
        print(shown["--view"])
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
        f"{game.name} — {game.players.count} seats, uniform-random self-play\n"
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
