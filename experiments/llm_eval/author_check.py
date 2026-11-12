"""The authoring benchmark's checker interface: run `cardlang check` on a
draft and read what it said into typed records.

The checker runs as a subprocess, `python -m cardlang check game.cardlang`,
in a directory holding nothing but the draft, with the rig's own checkout
first on the import path. Three properties ride on that shape: the model
reads exactly the words a designer at a terminal reads (the path in them is
the constant `DRAFT_NAME`, never a scratch path); a checker that crashes or
hangs is a recorded outcome of the round rather than the end of the run; and
the checker that judged a draft is the one in this checkout, which
`checker_import_root` reports and the run records.

`read_check` is the one reader. Every round's output goes through it, and it
is where the reader switches to `cardlang check --json` once issue #1046
gives the checker a machine-readable form (`CHECK_FORMS`, and the marked
seam in `read_check`). `refusal_key` is the one definition of which
refusals are "the same refusal"; it keys on the diagnostic code when the
record carries one, and on the message with its offers removed until then.

Contract
--------
Assumes: the checker's text form prints one diagnostic per line as
`file:line:col: severity: message`, a `note:` line after the diagnostic it
belongs to, and an unlocated `cardlang: ...` line for an invocation it
cannot carry out; and that exit 0 means green, 1 means the game file is at
fault, and 2 means the invocation could not be carried out
(`cardlang/cli.py`, module docstring).
Establishes: a `CheckResult` whose `verdict` is one of `CheckVerdict` and
whose `refusals` are the distinct diagnostics printed, in printed order.
Illegal after: reading a crash, a timeout, an exit 2 or an output the reader
cannot parse as a refusal; keying "the same refusal" anywhere but
`refusal_key`.
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
import time
from collections.abc import Sequence
from dataclasses import asdict, dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Final

from cardlang.diagnostics import NOTE, line_kind

#: The one name every draft is checked under. `.cardlang` because any other
#: suffix is read as a Markdown game file; constant because the name appears
#: in every diagnostic the model reads, and a name that moved between rounds
#: would move the words.
DRAFT_NAME: Final = "game.cardlang"

#: The checker output forms the reader can read. `json` is issue #1046's
#: `cardlang check --json`; until it exists the reader refuses the form
#: rather than guessing at a record nobody has specified.
CHECK_FORMS: Final[tuple[str, ...]] = ("text", "json")

#: What a crashing interpreter prints. Its presence anywhere in the output
#: makes the round a crash, whatever else was printed.
TRACEBACK: Final = "Traceback (most recent call last)"

#: A diagnostic line's fields. Which lines open a diagnostic at all is the
#: checker's own `line_kind`, so the kinds are read from `LINE_KINDS` and
#: never listed here.
_LOCATED = re.compile(r"^(?P<file>.+?):(?P<line>\d+):(?P<column>\d+): (?P<kind>[a-z]+): (?P<message>.*)$")
_UNLOCATED = re.compile(r"^(?P<kind>[a-z]+): (?P<message>.*)$")
_OFFERS = re.compile(r"; did you mean (?P<offers>.+)\?$")
_OFFER = re.compile(r"`([^`]*)`")


class CheckVerdict(Enum):
    """How one check of one draft ended."""

    GREEN = "green"
    #: Exit 1 with at least one diagnostic the reader parsed and no crash.
    REFUSED = "refused"
    #: The interpreter crashed (a traceback), or the checker exited with a
    #: code it does not document.
    CRASHED = "crashed"
    #: Exit 1 with nothing the reader can parse as a diagnostic.
    UNREADABLE = "unreadable"
    #: Exit 2: the invocation could not be carried out, which is the rig's
    #: fault and never the draft's.
    CANNOT_PROCEED = "cannot_proceed"
    TIMED_OUT = "timed_out"


@dataclass(frozen=True)
class Note:
    file: str | None
    line: int | None
    column: int | None
    message: str


@dataclass(frozen=True)
class Refusal:
    """One diagnostic the checker printed.

    `code` is the diagnostic's stable code once the checker reports one
    (issue #1046); the text form carries none. `near_misses` are the
    `did you mean` offers, as data.
    """

    file: str | None
    line: int | None
    column: int | None
    severity: str
    message: str
    near_misses: tuple[str, ...] = ()
    notes: tuple[Note, ...] = ()
    code: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)

    @staticmethod
    def from_dict(data: dict[str, Any]) -> Refusal:
        return Refusal(
            file=data["file"],
            line=data["line"],
            column=data["column"],
            severity=data["severity"],
            message=data["message"],
            near_misses=tuple(data.get("near_misses", ())),
            notes=tuple(Note(**n) for n in data.get("notes", ())),
            code=data.get("code"),
        )


def refusal_key(refusal: Refusal) -> str:
    """Which refusals are the same refusal: the code where the checker gives
    one, else the message without its `did you mean` offers (the offers name
    the file's declared names, which move as the file does)."""
    if refusal.code is not None:
        return f"code:{refusal.code}"
    return f"message:{refusal.message}"


@dataclass(frozen=True)
class CheckResult:
    verdict: CheckVerdict
    exit_code: int | None
    stdout: str
    stderr: str
    refusals: tuple[Refusal, ...] = ()
    wall_seconds: float = 0.0

    @property
    def said(self) -> str:
        """The checker's words as the model is shown them: everything it
        printed, in the order of its two streams."""
        return (self.stdout + self.stderr).strip()

    def as_dict(self) -> dict[str, Any]:
        return {
            "verdict": self.verdict.value,
            "exit_code": self.exit_code,
            "stdout": self.stdout,
            "stderr": self.stderr,
            "refusals": [r.as_dict() for r in self.refusals],
            "wall_seconds": self.wall_seconds,
        }

    @staticmethod
    def from_dict(data: dict[str, Any]) -> CheckResult:
        return CheckResult(
            verdict=CheckVerdict(data["verdict"]),
            exit_code=data["exit_code"],
            stdout=data["stdout"],
            stderr=data["stderr"],
            refusals=tuple(Refusal.from_dict(r) for r in data.get("refusals", ())),
            wall_seconds=float(data.get("wall_seconds", 0.0)),
        )


def parse_text(output: str) -> tuple[Refusal, ...]:
    """The diagnostics in the checker's text form, each once, in printed
    order.

    A line the location pattern does not open continues the message before
    it. An exact repeat of a diagnostic already read is dropped: the text
    form prints the first diagnostic of a several-error check twice (issue
    #606), and one refusal counted twice would be two refusals the model
    could not act on where it met one.
    """
    building: list[dict[str, Any]] = []
    for raw in output.splitlines():
        line = raw.rstrip()
        if not line.strip():
            continue
        kind = line_kind(line)
        if kind is not None:
            found = _LOCATED.match(line)
            match = found or _UNLOCATED.match(line)
            assert match is not None, f"line_kind read {line!r} as a diagnostic"
            message = match.group("message")
            file = found.group("file") if found else None
            line_no = int(found.group("line")) if found else None
            column = int(found.group("column")) if found else None
            if kind == NOTE and building:
                building[-1]["notes"].append(Note(file, line_no, column, message))
                continue
            building.append(
                {
                    "file": file,
                    "line": line_no,
                    "column": column,
                    "severity": kind,
                    "message": message,
                    "notes": [],
                }
            )
        elif building:
            building[-1]["message"] += "\n" + line
    out: list[Refusal] = []
    for item in building:
        message = item["message"]
        offers: tuple[str, ...] = ()
        tail = _OFFERS.search(message)
        if tail is not None:
            offers = tuple(_OFFER.findall(tail.group("offers")))
            message = message[: tail.start()]
        refusal = Refusal(
            file=item["file"],
            line=item["line"],
            column=item["column"],
            severity=item["severity"],
            message=message,
            near_misses=offers,
            notes=tuple(item["notes"]),
        )
        if refusal not in out:
            out.append(refusal)
    return tuple(out)


def read_check(
    exit_code: int | None,
    stdout: str,
    stderr: str,
    *,
    form: str = "text",
    timed_out: bool = False,
    wall_seconds: float = 0.0,
) -> CheckResult:
    """The one reader of a check: what the checker said, as a verdict and
    records."""
    if form not in CHECK_FORMS:
        raise ValueError(f"unknown checker form {form!r} (known: {', '.join(CHECK_FORMS)})")
    if form == "json":
        # THE SEAM (issue #1046). Once `cardlang check --json` exists, parse
        # its versioned record here into the same `Refusal`s, carrying each
        # diagnostic's `code`, refuse a record version this reader does not
        # know, and leave the verdict rules below unchanged.
        raise NotImplementedError(
            "the checker has no JSON form yet (issue #1046); run with "
            "checker.form: text"
        )
    def result(verdict: CheckVerdict, refusals: Sequence[Refusal] = ()) -> CheckResult:
        return CheckResult(
            verdict, exit_code, stdout, stderr, tuple(refusals), round(wall_seconds, 3)
        )

    if timed_out:
        return result(CheckVerdict.TIMED_OUT)
    if TRACEBACK in stdout or TRACEBACK in stderr:
        return result(CheckVerdict.CRASHED)
    refusals = parse_text(stdout + "\n" + stderr)
    if exit_code == 0:
        return result(CheckVerdict.GREEN, refusals)
    if exit_code == 2:
        return result(CheckVerdict.CANNOT_PROCEED, refusals)
    if exit_code == 1:
        if any(r.severity == "error" for r in refusals):
            return result(CheckVerdict.REFUSED, refusals)
        return result(CheckVerdict.UNREADABLE, refusals)
    return result(CheckVerdict.CRASHED, refusals)


def repo_root() -> Path:
    """The checkout this rig belongs to."""
    return Path(__file__).resolve().parents[2]


def checker_env(root: Path) -> dict[str, str]:
    """This process's environment with `root` first on the import path."""
    env = dict(os.environ)
    env["PYTHONPATH"] = str(root) + (
        os.pathsep + env["PYTHONPATH"] if env.get("PYTHONPATH") else ""
    )
    return env


def checker_import_root(python: str, root: Path) -> Path:
    """Where the checker subprocess imports `cardlang` from, asked of the
    subprocess itself."""
    done = subprocess.run(
        [python, "-c", "import cardlang, pathlib; print(pathlib.Path(cardlang.__file__).resolve().parent.parent)"],
        cwd="/",
        env=checker_env(root),
        capture_output=True,
        text=True,
        timeout=120,
        check=True,
    )
    return Path(done.stdout.strip())


@dataclass(frozen=True)
class Checker:
    """How a draft is checked: the command, the checkout it runs against,
    the output form it is read in, and the wall-clock bound."""

    root: Path = field(default_factory=repo_root)
    python: str = sys.executable
    form: str = "text"
    timeout_seconds: float = 120.0
    #: The command, `{draft}` standing for the draft's name. Replaceable so a
    #: test can stand a crashing command in for the checker.
    argv: tuple[str, ...] = ("{python}", "-m", "cardlang", "check", "{draft}")

    def command(self) -> list[str]:
        return [a.format(python=self.python, draft=DRAFT_NAME) for a in self.argv]

    def check(self, draft: str, workdir: Path) -> CheckResult:
        """Write `draft` as `DRAFT_NAME` in `workdir` and check it there."""
        (workdir / DRAFT_NAME).write_text(draft, encoding="utf-8")
        started = time.monotonic()
        try:
            done = subprocess.run(
                self.command(),
                cwd=workdir,
                env=checker_env(self.root),
                capture_output=True,
                text=True,
                timeout=self.timeout_seconds,
            )
        except subprocess.TimeoutExpired as exc:
            return read_check(
                None,
                _text(exc.stdout),
                _text(exc.stderr),
                form=self.form,
                timed_out=True,
                wall_seconds=time.monotonic() - started,
            )
        return read_check(
            done.returncode,
            done.stdout,
            done.stderr,
            form=self.form,
            wall_seconds=time.monotonic() - started,
        )


def _text(value: str | bytes | None) -> str:
    if value is None:
        return ""
    return value.decode("utf-8", "replace") if isinstance(value, bytes) else value
