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

What the hash deliberately does NOT cover: the `play` / `trick` TRACE events
-- the retiring Primitive winners were their only emitters in the hand-rolled
games and the kernel's call form emits none (Architect counsel, #250 PR 1,
Q7) -- and the OpenSpiel information-state string, which renders every
public state variable and therefore moves by the variables a migration
retires (Doppelkopf: `led_trump`, `led_suit`); the openspiel_ready proof
modules own that surface per manifest seed. The playout oracles
(`tests/test_playout_<game>.py`) are the INDEPENDENT recomputation of the
rules; this module is the regression pin that the engine's answer did not
move.

Completeness ledger (decisions.md "Closed-domain completeness")
---------------------------------------------------------------
property:   a migrated game's per-observer observation stream, decision
            trace and final scores are byte-identical to the pre-migration
            tree on every seed of the pin.
domain:     `MIGRATIONS` x `SEEDS` (200 seeds: the coverage-manifest head
            plus the long tail; the first 40 coincide with the score golden's
            seeds).
registry:   `MIGRATIONS` below -- one row per migrated game, keyed by its
            hash file; the row is added in the PR that migrates the game and
            its hash file is captured on the parent commit.
covered:    `test_stream_hash_is_byte_identical` (every game x every seed);
            `test_hash_file_covers_every_seed` (a hash file with a missing
            or extra seed is a stale capture, not a pass).
sampled:    nothing -- the pin is exact.
residual:   the trace channel's `play`/`trick` events and the information-
            state string, both moved BY DESIGN and owned elsewhere (above);
            R4, this ledger owns the record.

Born red: this module is committed with the Doppelkopf hash file captured on
the pre-migration tree, so it is GREEN at that commit by construction; its
capacity to fail is proven by the planted mutation recorded below.

red under, executed twice -- once on each side of the migration, which is
what makes the pin's capacity to fail a property of the CLAIM rather than of
one implementation:

* pre-migration, in `doko.py`'s trump comparison (`>` to `>=`): 33 of the
  first 40 seeds' hashes moved (`33 failed, 8 passed`, the not-slow
  selection);
* post-migration, the same flip in `winners.highest_by_trick_order`: 200 of
  200 seeds moved (`200 failed, 1 passed` -- the one pass is the hash-file
  coverage cell, which reads the file rather than a playout).

The kernel plant moves every seed where the module plant moved four in five,
because the kernel comparison runs for every game that declares a Trick Order
rather than for one game's winner. Neither was re-blessed.
"""

from __future__ import annotations

import hashlib
import json
import os
import random
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

# (game file, hash file). One row per migrated game; the hash file is captured
# on the commit BEFORE the migration lands.
MIGRATIONS: tuple[tuple[str, str], ...] = (
    ("doppelkopf.cardlang", "doppelkopf_stream_hashes.json"),
)

SEEDS: tuple[int, ...] = tuple(range(200))

# The trace events a migration retires by design (see the docstring); every
# other trace event is part of the hashed rendering.
_TRACE_EXCLUDED = frozenset({"play", "trick"})


def _stream_digest(game_file: str, seed: int) -> str:
    game = check_source(GAMES / game_file)
    rng = random.Random(seed)
    events: list[tuple[Player, tuple[Any, ...]]] = []
    traces: list[tuple[str, Any]] = []

    def observer(player: Player, event: tuple[Any, ...]) -> None:
        events.append((player, event))

    def tracer(name: str, data: Any) -> None:
        if name not in _TRACE_EXCLUDED:
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


@pytest.mark.parametrize(("game_file", "hash_file"), MIGRATIONS, ids=[g for g, _ in MIGRATIONS])
def test_hash_file_covers_every_seed(game_file: str, hash_file: str) -> None:
    """The capture is exactly `SEEDS` -- a missing seed is a stale capture and
    an extra one a capture from another manifest, and neither may pass."""
    if BLESS:
        pytest.skip("blessing")
    assert set(_load(hash_file)) == {str(s) for s in SEEDS}


def _cells() -> list[Any]:
    return [
        pytest.param(g, h, s, id=f"{g}-{s}", marks=() if s < 40 else pytest.mark.slow)
        for g, h in MIGRATIONS
        for s in SEEDS
    ]


@pytest.mark.parametrize(("game_file", "hash_file", "seed"), _cells())
def test_stream_hash_is_byte_identical(game_file: str, hash_file: str, seed: int) -> None:
    digest = _stream_digest(game_file, seed)
    if BLESS:
        path = _hash_path(hash_file)
        current = json.loads(path.read_text()) if path.exists() else {}
        current[str(seed)] = digest
        path.write_text(json.dumps(dict(sorted(current.items(), key=lambda kv: int(kv[0]))), indent=2) + "\n")
        return
    expected = _load(hash_file)
    assert str(seed) in expected, f"seed {seed} is not in {hash_file}: re-capture on the pre-migration tree"
    assert digest == expected[str(seed)], (
        f"{game_file} seed {seed}: the observation stream / decisions / scores moved "
        f"against the pre-migration capture ({hash_file}); the migration is not "
        f"byte-identical -- diff the two trees' event streams for the first divergence"
    )
