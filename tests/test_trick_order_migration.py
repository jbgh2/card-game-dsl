"""Byte-identity of a game migrated onto the `trick_order { }` construct.

Issue #250, PR 1 (Doppelkopf; PRs 2-5 add Skat, Five Hundred, Belote, French
Tarot by adding a hash file each and a row to `MIGRATIONS`). Each migration
replaces a game-local Python trick winner (and, where the game had one, its
in-DSL follow filter) with the kernel's Trick Order, and claims that NOTHING an
observer sees changes: every player's observation stream, every decision, and
the final scores are byte-identical on every seed. That claim is executed here,
not stated:

* `tests/golden/<game>_stream_hashes.json` holds, per seed, the SHA-256 of the
  canonical rendering of the whole per-observer observation stream (every
  `chose` / `announce` / `move` event each seat sees, in order), the round
  forms' `decision` trace, and the final scores. The file is CAPTURED on the
  pre-migration tree (`CARDLANG_STREAM_BLESS=1`) and committed BEFORE the
  game moves, so its provenance is the git log; after the migration the same
  module recomputes and compares. Capture and check share one rendering
  (this module), so the pin cannot drift into a second, vacuous rendering.
* The existing per-seed score goldens (`tests/golden/<game>_scores.json`,
  owned by each game's playout module) stay byte-identical -- pinned there.

What the hash deliberately does NOT cover: the TRACE events a migration
retires -- the retiring Primitive winners were their only emitters in the
hand-rolled games and the kernel's call form emits none (Architect counsel,
#250 PR 1, Q7) -- and the OpenSpiel information-state string, which renders
every public state variable and therefore moves by the variables a migration
retires (Doppelkopf: `led_trump`, `led_suit`); the openspiel_ready proof
modules own that surface per manifest seed. The playout oracles
(`tests/test_playout_<game>.py`) are the INDEPENDENT recomputation of the
rules; this module is the regression pin that the engine's answer did not
move.

WHICH trace events those are is a per-game fact, not a global one, so it is
declared per row (`Migration.retired_traces`) over the pair every hand-rolled
winner emitted (`_BASE_RETIRED_TRACES`). Skat's Primitive also emitted
`trick_end` carrying the contract, and was the game's only emitter of it; the
round form emits `trick_end` too (`runtime/mechanics.py`), so a game migrating
ONTO a round form keeps it. Excluding it globally would therefore stop
covering a trace that, in some other game, did not move -- the silencer
failure mode. An exclusion is a CLAIM that the event is gone, and
`test_retired_traces_are_actually_gone` executes that claim: a row naming a
trace the migrated game still emits is red.

Completeness ledger (decisions.md "Closed-domain completeness")
---------------------------------------------------------------
property:   a migrated game's per-observer observation stream, decision
            trace and final scores are byte-identical to the pre-migration
            tree on every seed of the pin.
domain:     `MIGRATIONS` x `SEEDS` (200 seeds: the coverage-manifest head
            plus the long tail; the first 40 coincide with the score golden's
            seeds), and `MIGRATIONS` x each row's declared `retired_traces`.
registry:   `MIGRATIONS` below -- one row per migrated game, keyed by its
            hash file; the row is added in the PR that migrates the game and
            its hash file is captured on the parent commit. Each row's
            `retired_traces` is that game's own widening of
            `_BASE_RETIRED_TRACES`.
covered:    `test_stream_hash_is_byte_identical` (every game x every seed);
            `test_hash_file_covers_every_seed` (a hash file with a missing
            or extra seed is a stale capture, not a pass);
            `test_retired_traces_are_actually_gone` (every row x every trace
            it claims to retire -- the claim executed, so an exclusion
            cannot silence a live event);
            `test_retired_traces_do_not_restate_the_base` (a row widening by
            a name the base already holds would read as a widening while
            covering nothing new).
sampled:    nothing -- the pin is exact. `test_retired_traces_are_actually_gone`
            runs one seed per row: a trace emitted from a trick site fires in
            every seed that plays a trick, so a second seed adds no cell.
residual:   (1) the information-state string, moved BY DESIGN and owned by
            the openspiel_ready proof modules (above); R4, this ledger owns
            the record. (2) A row could under-declare -- omit a trace the
            migration really does retire -- which no pin here catches,
            because the hash then simply moves and
            `test_stream_hash_is_byte_identical` reports it as the
            byte-identity failure it is. That is the wanted direction: the
            unsafe error (silencing a live event) is guarded, the safe one
            (forgetting an exclusion) is loud through the primary pin. R4,
            this ledger owns the record.

Born red: each row is committed with its hash file captured on that game's
pre-migration tree, so every row is GREEN at its own commit by construction;
capacity to fail is proven per row by the planted mutations recorded below.
Nothing here was ever re-blessed.

red under, PER ROW -- because a mutation that reddens one row does not
thereby redden another, and reading one row's witness as the module's is how
a row could sit green over a hash nothing can move:

* THE TIE-BREAK WITNESS IS PACK-SPECIFIC, and this is the record that says so.
  [[first-of-equals]] (`>` to `>=` in `winners.highest_by_trick_order`, and
  its pre-migration twin in `doko.py`) can only change an answer where two
  CANDIDATES compare equal, which needs two identical cards in one trick --
  a doubled pack. Measured over three seeds per game (2026-08-19): of the
  winner calls whose candidate set holds an equal-strength pair, Doppelkopf
  36 of 144, Skat 0 of 960, Five Hundred 0 of 30. So:
    - doppelkopf: pre-migration, `doko.py`'s trump comparison flipped -- 33
      of the first 40 seeds moved (`33 failed, 8 passed`, the not-slow
      selection); post-migration, the same flip in the kernel --
      `200 failed, 409 deselected`.
    - skat, five-hundred: the SAME kernel flip leaves both rows
      `200 passed` (executed 2026-08-19). That is the pack, not a dead row,
      and the witnesses below prove it.
* A KERNEL WITNESS EVERY ROW ANSWERS TO. `winners.follows_lead_lazily`'s
  class comparison inverted (`==` to `!=`), which every follow filter routes
  through whatever the pack: doppelkopf `200 failed`, skat `200 failed`,
  five-hundred `200 failed` (2026-08-19). This is the mutation that shows
  all three rows live over shared machinery.
* PER-ROW ORDER WITNESSES, each in that game's own declaration, so a row
  cannot be green over a game file nothing in it matters to:
    - doppelkopf.cardlang, the queen band reversed
      (`200 + suit_order(...)` -> `200 - suit_order(...)`): `200 failed`.
    - skat.cardlang, the jack band reversed
      (`100 + suit_order(...)` -> `100 - suit_order(...)`): `200 failed`.
    - five-hundred.cardlang, the two bowers swapped in `card_strength:`
      (101 <-> 100): `3 failed, 197 passed` -- fewer seeds because a 500 game
      is one to three hands and only some deals put a bower in a decided
      trick, which is the reachability the count reports rather than hides.
"""

from __future__ import annotations

import hashlib
import json
import os
import random
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest

from cardlang.pipeline import check_source
from cardlang.runtime.chooser import random_chooser
from cardlang.runtime.driver import play_game
from cardlang.runtime.values import Player

GAMES = Path(__file__).parent.parent / "docs" / "games"
GOLDEN = Path(__file__).parent / "golden"

BLESS = os.environ.get("CARDLANG_STREAM_BLESS") == "1"

# The two trace events EVERY hand-rolled trick winner emitted, which the
# kernel's call form emits from nowhere; every migration retires both.
_BASE_RETIRED_TRACES = frozenset({"play", "trick"})


@dataclass(frozen=True)
class Migration:
    """One migrated game's pin. The hash file is captured on the commit
    BEFORE the migration lands, so its provenance is the git log.

    `retired_traces` is this game's own widening of `_BASE_RETIRED_TRACES` --
    the trace events its RETIRING Primitive was the game's only emitter of.
    It is a claim about the post-migration tree, executed by
    `test_retired_traces_are_actually_gone`, never a way to quiet a diff."""

    game_file: str
    hash_file: str
    retired_traces: frozenset[str] = frozenset()

    @property
    def excluded_traces(self) -> frozenset[str]:
        return _BASE_RETIRED_TRACES | self.retired_traces


# One row per migrated game.
MIGRATIONS: tuple[Migration, ...] = (
    Migration("doppelkopf.cardlang", "doppelkopf_stream_hashes.json"),
    # `skat_trick_winner` emitted `trick_end` carrying the declared contract
    # ({game_type, trump}) and was Skat's only emitter of it -- the ten tricks
    # are hand-rolled movements, not a trick `round`, so no round form emits
    # one here.
    Migration(
        "skat.cardlang",
        "skat_stream_hashes.json",
        retired_traces=frozenset({"trick_end"}),
    ),
    # `five_hundred_trick_winner` emitted `trick_end` carrying the declared
    # contract ({trump, misere, joker_suit}) and was 500's only emitter of it:
    # the ten tricks are hand-rolled movements and the game's one `round` is
    # the auction, which emits no trick.
    Migration(
        "five-hundred.cardlang",
        "five_hundred_stream_hashes.json",
        retired_traces=frozenset({"trick_end"}),
    ),
)

SEEDS: tuple[int, ...] = tuple(range(200))


def _stream_digest(game_file: str, seed: int, excluded: frozenset[str]) -> str:
    game = check_source(GAMES / game_file)
    rng = random.Random(seed)
    events: list[tuple[Player, tuple[Any, ...]]] = []
    traces: list[tuple[str, Any]] = []

    def observer(player: Player, event: tuple[Any, ...]) -> None:
        events.append((player, event))

    def tracer(name: str, data: Any) -> None:
        if name not in excluded:
            traces.append((name, data))

    result = play_game(game, rng, tracer, random_chooser(rng), observer=observer)
    rendering = "\n".join(
        [
            *(f"{p} {event!r}" for p, event in events),
            *(f"trace {name} {data!r}" for name, data in traces),
            f"scores {sorted(result.scores.items())!r}",
            f"winner {result.winner!r}",
            f"hands {result.hands_played!r}",
        ]
    )
    return hashlib.sha256(rendering.encode("utf-8")).hexdigest()


def _hash_path(hash_file: str) -> Path:
    return GOLDEN / hash_file


def _load(hash_file: str) -> dict[str, str]:
    data = json.loads(_hash_path(hash_file).read_text())
    assert isinstance(data, dict)
    return {str(k): str(v) for k, v in data.items()}


_IDS = [m.game_file for m in MIGRATIONS]


@pytest.mark.parametrize("migration", MIGRATIONS, ids=_IDS)
def test_hash_file_covers_every_seed(migration: Migration) -> None:
    """The capture is exactly `SEEDS` -- a missing seed is a stale capture and
    an extra one a capture from another manifest, and neither may pass."""
    if BLESS:
        pytest.skip("blessing")
    assert set(_load(migration.hash_file)) == {str(s) for s in SEEDS}


def _cells() -> list[Any]:
    return [
        pytest.param(
            m, s, id=f"{m.game_file}-{s}", marks=() if s < 40 else pytest.mark.slow
        )
        for m in MIGRATIONS
        for s in SEEDS
    ]


@pytest.mark.parametrize(("migration", "seed"), _cells())
def test_stream_hash_is_byte_identical(migration: Migration, seed: int) -> None:
    digest = _stream_digest(migration.game_file, seed, migration.excluded_traces)
    if BLESS:
        path = _hash_path(migration.hash_file)
        current = json.loads(path.read_text()) if path.exists() else {}
        current[str(seed)] = digest
        path.write_text(json.dumps(dict(sorted(current.items(), key=lambda kv: int(kv[0]))), indent=2) + "\n")
        return
    expected = _load(migration.hash_file)
    assert str(seed) in expected, (
        f"seed {seed} is not in {migration.hash_file}: re-capture on the "
        f"pre-migration tree"
    )
    assert digest == expected[str(seed)], (
        f"{migration.game_file} seed {seed}: the observation stream / decisions / scores moved "
        f"against the pre-migration capture ({migration.hash_file}); the migration is not "
        f"byte-identical -- diff the two trees' event streams for the first divergence"
    )


@pytest.mark.parametrize("migration", MIGRATIONS, ids=_IDS)
def test_retired_traces_do_not_restate_the_base(migration: Migration) -> None:
    """A row widens the exclusion or it does not. Restating a base name would
    read as a widening while covering nothing new -- the shape a reviewer
    would take at face value."""
    assert not (migration.retired_traces & _BASE_RETIRED_TRACES), migration.game_file


@pytest.mark.parametrize("migration", MIGRATIONS, ids=_IDS)
def test_retired_traces_are_actually_gone(migration: Migration) -> None:
    """A row's exclusion is a CLAIM -- "the migration retired this event" --
    and this executes it: one seeded playout of the MIGRATED game, and every
    excluded name must be absent from the trace channel.

    Without this, an exclusion is a silencer: naming an event that still
    fires would drop it from the hashed rendering, and the pin would go on
    passing while covering strictly less than its docstring says. That is
    the vacuously-green class, in the one place this module could grow it."""
    seen: set[str] = set()

    def tracer(name: str, data: Any) -> None:
        seen.add(name)

    game = check_source(GAMES / migration.game_file)
    rng = random.Random(0)
    play_game(game, rng, tracer, random_chooser(rng))
    still_emitted = sorted(migration.excluded_traces & seen)
    assert not still_emitted, (
        f"{migration.game_file} still emits {still_emitted}, which its "
        f"`Migration` row excludes from the hashed rendering: the exclusion "
        f"is silencing a live event rather than recording a retired one"
    )
