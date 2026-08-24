"""What this checkout has billed, recorded so it outlives the process.

A `token_budget` cap is only a ceiling over the spend it can see, and the
provider registry sees one invocation: its `Usage` counters are in-memory
objects that start at zero every time `run_eval` is entered. The spend log is
the record that does not. Every path that bills the API appends its usage to
`<results_dir>/spend/log.jsonl` as it happens, and `Window` decides which of
those lines a cap counts.

The log is append-only and machine-local. It is operational, never evidence:
the published record is the transcript archive (`layout.py`), and nothing here
is committed.

**Appended as it is billed, not derived afterwards.** A log summed from each
run's `summary.json` is wrong exactly when a run dies before writing one,
which is the case the cap exists for. Each game's usage is written when the
game ends, so a run that dies has already recorded everything it spent up to
the game it died in, and the residual for that game is flushed when the
matchup unwinds.

**Windows, and why `invocation` is one of them.** A window is a predicate over
lines, so the cap has one expression -- what the window admits, plus what has
been billed and not yet written -- rather than a branch per window with its
own arithmetic. `invocation` is the predicate "this log object wrote it",
which makes the pre-existing per-process ceiling a window like the others
instead of a special case.

Each line is written whole, in one `write` to a file opened for append, so a
second invocation reading the same log between its own games sees complete
lines and counts them. Two invocations against one results tree therefore
share a cap rather than getting one each.

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
from collections.abc import Iterator, Mapping, Sequence
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

    def spelling(self) -> str:
        return f"{self.hours}h" if self.kind == "rolling" else self.kind

    def admits(self, entry: Mapping[str, Any], *, now: datetime, session: str) -> bool:
        if self.kind == "all":
            return True
        if self.kind == "invocation":
            return bool(entry.get("session") == session)
        if self.kind == "day":
            return str(entry.get("ts", ""))[:10] == now.strftime("%Y-%m-%d")
        return _parse_stamp(str(entry.get("ts", ""))) >= now - timedelta(hours=self.hours)


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

    `written` is per model reference rather than one running total, because
    the residual it feeds is asked about a PARTICULAR registry: `smoke` bills
    through a registry of its own, and a scalar would subtract that spend from
    a later registry that never held those providers.
    """

    path: Path
    session: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    written: dict[str, Spend] = field(default_factory=dict)

    @property
    def appended(self) -> Spend:
        """Everything this object has written, across models."""
        total = Spend()
        for spend in self.written.values():
            total = total + spend
        return total

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
            json.dumps(
                {
                    "ts": stamp,
                    "session": self.session,
                    "run": run,
                    "matchup": matchup,
                    "model_ref": b.model_ref,
                    "model": b.model,
                    "calls": b.calls,
                    "input_tokens": b.spend.input_tokens,
                    "output_tokens": b.spend.output_tokens,
                    "cost_usd": round(b.spend.cost_usd, 6),
                },
                ensure_ascii=False,
            )
            + "\n"
            for b in rows
        )
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(payload)
        for row in rows:
            self.written[row.model_ref] = (
                self.written.get(row.model_ref, Spend()) + row.spend
            )

    def entries(self) -> Iterator[dict[str, Any]]:
        """Every line, oldest first.

        Absent is legitimately zero — the first run into a tree has spent
        nothing. A line that will not parse is NOT: reading past it would
        subtract real spend from the total and quietly widen the ceiling,
        which is the failure the cap exists to prevent. So a damaged log
        refuses rather than under-reports.
        """
        if not self.path.exists():
            return
        with self.path.open(encoding="utf-8") as handle:
            for number, line in enumerate(handle, start=1):
                if not line.strip():
                    continue
                try:
                    loaded: dict[str, Any] = json.loads(line)
                except json.JSONDecodeError as exc:
                    raise ValueError(
                        f"{self.path}:{number} is not a spend entry ({exc}). The "
                        f"log is what a `token_budget` window counts, so reading "
                        f"past a damaged line would raise the ceiling by whatever "
                        f"that line recorded. Repair or move the file aside "
                        f"deliberately."
                    ) from None
                if not isinstance(loaded, dict):
                    raise ValueError(
                        f"{self.path}:{number} holds a {type(loaded).__name__}, "
                        f"not a spend entry. See above — a line this cannot read "
                        f"is spend this cannot count."
                    )
                yield loaded

    def total(self, window: Window, *, now: datetime | None = None) -> Spend:
        """What the window admits, re-read from disk on every call.

        Re-read rather than cached: a second invocation running against the
        same results tree appends while this one is playing, and a cached
        total would not see it.
        """
        moment = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
        total = Spend()
        for entry in self.entries():
            if window.admits(entry, now=moment, session=self.session):
                total = total + Spend(
                    int(entry.get("input_tokens", 0)),
                    int(entry.get("output_tokens", 0)),
                    float(entry.get("cost_usd", 0.0)),
                )
        return total

    def unrecorded(self, registry: Mapping[str, Provider]) -> Spend:
        """Billed by the live providers in `registry` but not yet written.

        Zero between games in the ordinary run, where a game's usage is
        recorded before the next cap check. It is what keeps the cap correct
        at any other moment --- and what makes `invocation` arithmetic come
        out at the registry's own totals, since a window admitting exactly
        this object's lines plus the unwritten remainder IS everything the
        registry holds.

        Per provider, so it answers about the registry it was handed: a model
        this log wrote lines for but that this registry does not hold
        contributes nothing, rather than subtracting spend the registry never
        billed.
        """
        total = Spend()
        for ref, provider in registry.items():
            billed = Spend(
                provider.usage.input_tokens,
                provider.usage.output_tokens,
                provider.usage.cost(provider.model),
            )
            total = total + (billed - self.written.get(ref, Spend()))
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


def billed_since(
    providers: Mapping[str, Provider], before: Mapping[str, Billed]
) -> list[Billed]:
    """Each provider's usage beyond an earlier `snapshot`, as loggable lines."""
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
