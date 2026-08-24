"""What this checkout has billed, recorded so it outlives the process.

A `token_budget` cap is only a ceiling over the spend it can see, and the
provider registry sees one invocation: its `Usage` counters are in-memory
objects that start at zero every time `run_eval` is entered. The spend log is
the record that does not. Every path that bills the API appends its usage to
the log (`layout.spend_log_path`) as it happens, and `Window` decides which of
those lines a cap counts.

The log is append-only and operational, never evidence: the published record
is the transcript archive (`layout.py`). At its default location it is
gitignored; a `spend_log:` naming somewhere else is the operator's to place,
and the repo is public.

**Appended as it is billed, not derived afterwards.** A log summed from each
run's `summary.json` is wrong exactly when a run dies before writing one,
which is the case the cap exists for. Each game's usage is written when the
game ends, so a run that dies has already recorded everything it spent up to
the game it died in, and the residual for that game is flushed when the
matchup unwinds.

**Windows.** A window is a predicate over lines, so the cap has one expression
-- what the window admits, plus what has been billed and not yet written --
rather than a branch per window with its own arithmetic. `invocation` is the
one exception, and deliberately: it is answered from `appended`, this object's
own record of what it wrote, because reading the file back to recompute it
would re-derive a fact `record` establishes -- and would make the default
ceiling, the one every shipped config uses, depend on a file it needs nothing
from.

Each line is written whole, in one `write` to a file opened for append, so a
second invocation reading the same log between its own games sees complete
lines and counts them. Two invocations against one results tree therefore
share a cap rather than getting one each -- to within one game apiece, since
each checks the cap before playing and both can pass a check the pair then
crosses.

Dollars are stored per line rather than recomputed from tokens at read time:
`providers.PRICES` is today's list price, and re-pricing history against it
would silently restate what a past run cost.

Contract
--------
Assumes: `path`'s parent can be created; entries are appended in the order
they were billed.
Establishes: a JSONL line per model per recording, carrying the tokens, the
dollars billed at the time, and the session that billed them; `appended` is
the running total this object has written.
Illegal after: deriving a spend figure from anything but `Spend` --- a cap
that reads token counts from one source and dollars from another can disagree
with itself.
"""

from __future__ import annotations

import json
import re
import uuid
from collections.abc import Iterable, Iterator, Mapping, Sequence
from dataclasses import dataclass, field, replace
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Final

from .providers import Provider

#: The stamp every line carries. UTC and ISO-8601, so `[:10]` is the calendar
#: date the `day` window compares against and the whole string parses back for
#: the rolling one.
STAMP_FORMAT: Final = "%Y-%m-%dT%H:%M:%SZ"

#: The closed set of window kinds a cap may be read through. Three are spelled
#: by their own name; `rolling` is spelled `<N>h` (`24h`), which is why the
#: kind and the spelling are separate things.
WINDOW_KINDS: Final[tuple[str, ...]] = ("invocation", "day", "all", "rolling")

#: A rolling window's spelling. At least one hour, no sign, no fraction, no
#: unit but `h` and no capital: one name, one shape.
ROLLING_SPELLING: Final = re.compile(r"[1-9][0-9]*h")

#: One spelling per kind, for anything that has to name a whole kind --- the
#: grid's window axis derives from this rather than listing the four again.
WINDOW_SPELLINGS: Final[Mapping[str, str]] = {
    kind: ("24h" if kind == "rolling" else kind) for kind in WINDOW_KINDS
}

#: Every field a line carries, against the kind the reader requires of it.
#: ONE table: `record` writes exactly these keys and `_read_entry` admits
#: exactly these, so what the writer produces and what the reader accepts
#: cannot drift. Every field a total reads is here, because a line missing one
#: would otherwise default to zero --- and a ceiling that counts a damaged
#: line as no spend is wider than the one its author wrote down.
ENTRY_FIELDS: Final[Mapping[str, str]] = {
    "ts": "stamp",
    "session": "text",
    "run": "text",
    "matchup": "text",
    "model_ref": "text",
    "model": "text",
    "calls": "count",
    "input_tokens": "count",
    "output_tokens": "count",
    "cost_usd": "amount",
}


@dataclass(frozen=True)
class Spend:
    """Tokens and dollars, added and subtracted as one quantity."""

    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float = 0.0

    def __add__(self, other: Spend) -> Spend:
        return Spend(
            self.input_tokens + other.input_tokens,
            self.output_tokens + other.output_tokens,
            self.cost_usd + other.cost_usd,
        )

    def __sub__(self, other: Spend) -> Spend:
        return Spend(
            self.input_tokens - other.input_tokens,
            self.output_tokens - other.output_tokens,
            self.cost_usd - other.cost_usd,
        )


@dataclass(frozen=True)
class Billed:
    """One model's newly billed usage --- one line of the log."""

    model_ref: str
    model: str
    calls: int
    spend: Spend


@dataclass(frozen=True)
class Window:
    """Which lines of the log a cap counts.

    `hours` is meaningful for the `rolling` kind and zero for the rest; the
    two are one object because a window is one config value, and splitting it
    into a kind field plus an hours field would admit the combinations
    (`day` with hours, `rolling` without) that then have to be rejected.
    """

    kind: str
    hours: int = 0

    def __post_init__(self) -> None:
        # The type owns "is this a window at all"; `admits` below owns "does
        # this registered kind have an arm". Two classes, two guards: a kind
        # the registry never had, and a kind it gained without an arm.
        if self.kind not in WINDOW_KINDS:
            raise ValueError(
                f"no window kind {self.kind!r} (known: {', '.join(WINDOW_KINDS)})"
            )
        if (self.kind == "rolling") != (self.hours > 0):
            raise ValueError(
                f"window {self.kind!r} with hours={self.hours}: `rolling` is the "
                f"only kind that spans hours, and it spans at least one. A "
                f"rolling window of zero hours admits nothing while reading "
                f"like a window."
            )

    def spelling(self) -> str:
        return f"{self.hours}h" if self.kind == "rolling" else self.kind

    def admits(self, entry: Mapping[str, Any], *, now: datetime, session: str) -> bool:
        if self.kind == "all":
            return True
        if self.kind == "invocation":
            return bool(entry["session"] == session)
        if self.kind == "day":
            return str(entry["ts"])[:10] == now.strftime("%Y-%m-%d")
        if self.kind == "rolling":
            return _parse_stamp(str(entry["ts"])) >= now - timedelta(hours=self.hours)
        # The remainder, refused rather than fallen through: a kind added to
        # `WINDOW_KINDS` with no arm here would otherwise inherit whichever
        # branch sits last and admit nearly nothing, silently.
        raise ValueError(
            f"no window arm for kind {self.kind!r} (known: {', '.join(WINDOW_KINDS)})"
        )


def parse_window(value: object) -> Window:
    """The window a config's `token_budget.window` names.

    Refused rather than defaulted: a value this does not know would otherwise
    silently read as the narrowest window, which is the ceiling the operator
    was trying to widen.
    """
    if not isinstance(value, str):
        raise ValueError(
            f"token_budget.window must be a string, not {type(value).__name__} "
            f"({value!r}). Known: {', '.join(sorted(WINDOW_SPELLINGS.values()))} "
            f"(and any `<N>h`)."
        )
    if value in WINDOW_KINDS and value != "rolling":
        return Window(kind=value)
    if ROLLING_SPELLING.fullmatch(value):
        return Window(kind="rolling", hours=int(value[:-1]))
    raise ValueError(
        f"unknown token_budget.window {value!r}. Known: "
        f"{', '.join(sorted(WINDOW_SPELLINGS.values()))} (and any `<N>h`, "
        f"whole hours from 1)."
    )


def _parse_stamp(text: str) -> datetime:
    return datetime.strptime(text, STAMP_FORMAT).replace(tzinfo=timezone.utc)


def _readable(value: object, kind: str) -> bool:
    """Whether `value` is what a field of this kind has to be to be counted."""
    if kind == "text":
        return isinstance(value, str)
    if kind == "stamp":
        if not isinstance(value, str):
            return False
        try:
            _parse_stamp(value)
        except ValueError:
            return False
        return True
    # `bool` is an `int` in Python and is not a quantity here.
    if kind == "count":
        return isinstance(value, int) and not isinstance(value, bool)
    if kind == "amount":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    raise ValueError(f"no reader for field kind {kind!r}")


def _line(
    stamp: str, session: str, run: str, matchup: str, billed: Billed
) -> dict[str, Any]:
    """One line's fields. Its keys are `ENTRY_FIELDS`' keys, which is what the
    reader admits — pinned so the two cannot part company."""
    return {
        "ts": stamp,
        "session": session,
        "run": run,
        "matchup": matchup,
        "model_ref": billed.model_ref,
        "model": billed.model,
        "calls": billed.calls,
        "input_tokens": billed.spend.input_tokens,
        "output_tokens": billed.spend.output_tokens,
        "cost_usd": round(billed.spend.cost_usd, 6),
    }


def registry_spend(registry: Mapping[str, Provider]) -> Spend:
    """Everything the in-memory providers have billed, summed across models.

    Dollars add across models and so do token counts, so a cap cannot be
    evaluated one provider at a time.
    """
    total = Spend()
    for provider in registry.values():
        total = total + Spend(
            provider.usage.input_tokens,
            provider.usage.output_tokens,
            provider.usage.cost(provider.model),
        )
    return total


@dataclass
class SpendLog:
    """The append-only record at `path`, plus what this object has written.

    `session` identifies one invocation's lines. It is generated per object
    rather than read from the process, so a library caller that builds two
    logs gets two sessions --- which is what `invocation` then means.

    `appended` is what this object has written, and it is all the log knows
    about live spend. What has been billed and NOT yet written is the
    caller's to say, because only the caller holds the mark it is measured
    from: a model reference names a config entry, not a provider's lifetime,
    and `smoke` and a later matchup can bill through two different providers
    under one name.
    """

    path: Path
    session: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    appended: Spend = Spend()

    def record(
        self,
        run: str,
        matchup: str,
        billed: Sequence[Billed],
        *,
        now: datetime | None = None,
    ) -> None:
        """Append one line per model, and add them to `appended`.

        A whole-line write in append mode is what lets a concurrent
        invocation read the file mid-run and see entries rather than halves.
        """
        rows = [b for b in billed if b.calls or b.spend != Spend()]
        if not rows:
            return
        stamp = (now or datetime.now(timezone.utc)).astimezone(timezone.utc).strftime(
            STAMP_FORMAT
        )
        payload = "".join(
            json.dumps(_line(stamp, self.session, run, matchup, b), ensure_ascii=False)
            + "\n"
            for b in rows
        )
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(payload)
        for row in rows:
            self.appended = self.appended + row.spend

    def entries(self) -> Iterator[dict[str, Any]]:
        """Every line, oldest first.

        Absent is legitimately zero — the first run into a tree has spent
        nothing. A line a total cannot read correctly is NOT, and every way
        that can happen refuses the same way: unparseable JSON, a line that is
        not an object, a missing field, and a field of the wrong kind. All
        four end in a total that is lower than what was billed, and a ceiling
        counting a damaged line as no spend is wider than the one its author
        wrote down.
        """
        if not self.path.exists():
            return
        with self.path.open(encoding="utf-8") as handle:
            for number, line in enumerate(handle, start=1):
                if line.strip():
                    yield self._read_entry(line, number)

    def _read_entry(self, line: str, number: int) -> dict[str, Any]:
        where = f"{self.path}:{number}"
        why = (
            "The log is what a `token_budget` window counts, so a line it "
            "cannot read is spend it cannot count — and a ceiling short by "
            "that much is wider than the one written down. Repair the file, "
            "or move it aside deliberately."
        )
        try:
            loaded: object = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"{where} is not a spend entry ({exc}). {why}") from None
        if not isinstance(loaded, dict):
            raise ValueError(
                f"{where} holds a {type(loaded).__name__}, not a spend entry. {why}"
            )
        for field_name, kind in ENTRY_FIELDS.items():
            if field_name not in loaded:
                raise ValueError(
                    f"{where} has no {field_name!r} field. {why}"
                )
            if not _readable(loaded[field_name], kind):
                raise ValueError(
                    f"{where} carries {field_name}={loaded[field_name]!r}, which "
                    f"is not a readable {kind}. {why}"
                )
        return loaded

    def total(self, window: Window, *, now: datetime | None = None) -> Spend:
        """What the window admits, re-read from disk on every call.

        Re-read rather than cached: a second invocation running against the
        same results tree appends while this one is playing, and a cached
        total would not see it.

        Except for `invocation`, which is answered from `written` — this
        object's own record of what it wrote, so reading the file back would
        re-derive a fact `record` already established. The two agree by
        construction, and the difference is that a ceiling over one process
        then depends on nothing another process can damage.
        """
        if window.kind == "invocation":
            return self.appended
        moment = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
        total = Spend()
        for entry in self.entries():
            if window.admits(entry, now=moment, session=self.session):
                total = total + Spend(
                    entry["input_tokens"], entry["output_tokens"], entry["cost_usd"]
                )
        return total



def snapshot(providers: Mapping[str, Provider]) -> dict[str, Billed]:
    """Each provider's CUMULATIVE usage right now, keyed by config reference."""
    return {
        ref: Billed(
            model_ref=ref,
            model=p.model,
            calls=p.usage.calls,
            spend=Spend(
                p.usage.input_tokens, p.usage.output_tokens, p.usage.cost(p.model)
            ),
        )
        for ref, p in providers.items()
    }


def spent(billed: Iterable[Billed]) -> Spend:
    """What a set of loggable lines comes to, summed across models."""
    total = Spend()
    for row in billed:
        total = total + row.spend
    return total


def billed_since(
    providers: Mapping[str, Provider], before: Mapping[str, Billed]
) -> list[Billed]:
    """Each provider's usage beyond an earlier `snapshot`, as loggable lines.

    The mark lives with the caller, not with the log, because a model
    reference names a config entry rather than a provider's lifetime: two
    providers can carry the same name in one process, and a mark kept by name
    would measure one against the other.
    """
    zero = Billed(model_ref="", model="", calls=0, spend=Spend())
    rows = []
    for ref, current in snapshot(providers).items():
        mark = before.get(ref, zero)
        rows.append(
            replace(
                current,
                calls=current.calls - mark.calls,
                spend=current.spend - mark.spend,
            )
        )
    return rows
