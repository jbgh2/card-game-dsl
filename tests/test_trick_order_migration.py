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

What the hash deliberately does NOT cover: the TRACE events a migration moves
(below) -- and the OpenSpiel information-state string, which renders every
public state variable and therefore moves by the variables a migration retires
or hoists (Doppelkopf: `led_trump`, `led_suit`); the openspiel_ready proof
modules own that surface per manifest seed. The playout oracles
(`tests/test_playout_<game>.py`) are the INDEPENDENT recomputation of the
rules; this module is the regression pin that the engine's answer did not
move.

WHICH trace events a migration moves, and HOW, are both per-game facts, so
each row declares them and each half carries the OPPOSITE executed claim:

* `retired_traces` -- events the migrated game no longer emits at all. In a
  game whose tricks are hand-rolled movements, the retiring Primitive winner
  was the only emitter of `play` and `trick`, and the kernel's call form emits
  none (Architect counsel, #250 PR 1, Q7); Skat's and 500's also carried
  `trick_end` with the contract. `test_retired_traces_are_actually_gone`
  executes the claim: a row naming a trace the migrated game STILL emits is
  red, so an exclusion cannot silence a live event.
* `reshaped_traces` -- events the migrated game still emits with a moved
  PAYLOAD. Belote's tricks are a `round`, so `play`, `trick` and `trick_end`
  all come from `runtime/mechanics.py` and none of them retires; what moves is
  the one field `trick_end` echoes from the ROUND's configuration, because a
  block game has no round `trump` clause to echo (`{"trump": "diamonds"}` ->
  `{"trump": null}`; measured 2026-08-19 over seeds 0-2: 96/72/72 of 1042/787/790
  trace events differ, all of them `trick_end`, and the per-observer
  observation stream is identical). No info-set consequence -- the trace
  channel is HARNESS-only and distinct from `observe`, which is the ruling
  tests/test_trump_slot_class.py's residual (7) already made for french-tarot's
  identical `"atouts"` -> `null` move. `test_reshaped_traces_are_still_emitted`
  executes THIS claim: a row calling a retirement a reshaping is red.

There is no global base. A `_BASE_RETIRED_TRACES` union over `play`/`trick`
held only while every migrated game hand-rolled its tricks; Belote is the
first to migrate a `round` trick form, where both events survive, and the
union would have silenced two live ones -- the silencer failure mode, in the
registry that exists to prevent it.

Completeness ledger (decisions.md "Closed-domain completeness")
---------------------------------------------------------------
property:   a migrated game's per-observer observation stream, decision
            trace and final scores are byte-identical to the pre-migration
            tree on every seed of the pin.
domain:     `MIGRATIONS` x `SEEDS` (200 seeds: the coverage-manifest head
            plus the long tail; the first 40 coincide with the score golden's
            seeds), and `MIGRATIONS` x each row's declared exclusions, in
            BOTH halves (`retired_traces`, `reshaped_traces`).
registry:   `MIGRATIONS` below -- one row per migrated game, keyed by its
            hash file; the row is added in the PR that migrates the game and
            its hash file is captured on the parent commit. Each row declares
            its own exclusions outright, in the half that says what happened
            to the event; there is no shared base to widen.
covered:    `test_stream_hash_is_byte_identical` (every game x every seed);
            `test_hash_file_covers_every_seed` (a hash file with a missing
            or extra seed is a stale capture, not a pass);
            `test_retired_traces_are_actually_gone` (every row x every trace
            it claims to retire -- the claim executed, so an exclusion
            cannot silence a live event);
            `test_reshaped_traces_are_still_emitted` (every row x every trace
            it claims merely moved -- the opposite claim, executed, so a row
            cannot label a retirement a reshaping and cover strictly less
            than it says);
            `test_the_two_exclusion_halves_are_disjoint` (an event is gone or
            it is not; a name in both halves would make one of the two claims
            unfalsifiable).
sampled:    nothing -- the pin is exact. The two trace-claim tests run one
            seed per row: a trace emitted from a trick site fires in every
            seed that plays a trick, so a second seed adds no cell.
            A row that excludes NOTHING contributes zero cells to BOTH
            exclusion tests, which is french-tarot's case and is stated at
            that row: an empty exclusion is the claim "this migration moves
            no trace", and what executes it is the primary pin, which then
            hashes the whole trace channel rather than a subset of it. Not a
            gap in the domain -- the domain is `MIGRATIONS` x each row's
            declared exclusions, and this row declares none.
residual:   (1) the information-state string, moved BY DESIGN and owned by
            the openspiel_ready proof modules (above); R4, this ledger owns
            the record. (2) A row could under-declare -- omit a trace the
            migration really does retire -- which no pin here catches,
            because the hash then simply moves and
            `test_stream_hash_is_byte_identical` reports it as the
            byte-identity failure it is. That is the wanted direction: the
            unsafe error (silencing a live event) is guarded, the safe one
            (forgetting an exclusion) is loud through the primary pin. R4,
            this ledger owns the record. (3) A `reshaped_traces` row excludes
            a WHOLE event, where what moved is one field of its payload, so a
            second, unrelated change to a reshaped event's payload would ride
            along unseen. Bounded and measured rather than guarded: the
            excluded event is `trick_end`, whose payload is two fields, and
            the other (`early`) is constant for a game that declares no
            `early` predicate -- which the presence partition REFUSES beside a
            block (`TRICK_ORDER_EARLY_PREDICATES`, empty), so no row here can
            have a moving one. R4, this ledger owns the record.

A HAZARD EVERY MIGRATION AFTER THE FIRST INHERITS, stated once here because
the next row added will meet it. A `trick_order` block is a game clause and
sees game state only, so a game whose rows read a declared contract must HOIST
those variables out of the phase that declared them -- and hoisting trades a
guarantee for a line of code: phase-scoped state is re-initialized BY THE
LANGUAGE on every phase entry, game-scoped state is not, so the reset becomes
a hand-written assignment that nothing checks. Dropping one is silent in the
general case -- the value simply carries into the next hand -- and whether
that is visible at all depends on the game. So each such clear needs its OWN
witness, and the witness may sit far outside these seeds: 500's
`joker_suit := none` is first read at seed 353, and only three of the five
seeds under 600 with the right shape redden when it is dropped
(tests/test_playout_five_hundred.py, `test_the_nomination_clears_between_hands`).
A clear that no witness can reach is then a decision rather than an oversight,
and says so where it stands -- 500's `trump_suit := none` is the worked
example.

Born red: each row is committed with its hash file captured on that game's
pre-migration tree, so every row is GREEN at its own commit by construction;
capacity to fail is proven per row by the planted mutations recorded below.
Nothing here was ever re-blessed.

The two trace-claim tests are born green for every row -- each asserts what
the tree already does -- so their reddening mutations are recorded here
instead, executed 2026-08-19 on the pre-migration tree:
* belote's `trick_end` moved from `reshaped_traces` into `retired_traces`:
  `test_retired_traces_are_actually_gone[belote.cardlang]` -- "belote.cardlang
  still emits ['trick_end'], which its `Migration` row excludes as RETIRED".
* skat's `trick_end` moved the other way, into `reshaped_traces`:
  `test_reshaped_traces_are_still_emitted[skat.cardlang]` -- "skat.cardlang
  does not emit ['trick_end'] ... excludes as merely RESHAPED".
* belote's `trick_end` declared in BOTH halves:
  `test_the_two_exclusion_halves_are_disjoint[belote.cardlang]` --
  "['trick_end'] claimed retired AND reshaped", alongside the retirement cell,
  which is the point: a name in both halves makes one claim unfalsifiable.

red under, PER ROW -- because a mutation that reddens one row does not
thereby redden another, and reading one row's witness as the module's is how
a row could sit green over a hash nothing can move:

* THE TIE-BREAK WITNESS IS PACK-SPECIFIC, and this is the record that says so.
  [[first-of-equals]] (`>` to `>=` in `winners.highest_by_trick_order`, and
  its pre-migration twin in `doko.py`) can only change an answer where two
  CANDIDATES compare equal, which needs two identical cards in one trick --
  a doubled pack. Measured over three seeds per game (2026-08-19): of the
  winner calls whose candidate set holds an equal-strength pair, Doppelkopf
  36 of 144, Skat 0 of 960, Five Hundred 0 of 30, Belote 0 of 1887, French
  Tarot 0 of 1944 -- and Tarot's zero is structural rather than lucky, since
  its `card_strength:` row is injective within any one candidate set (the
  atouts are 101-121, and a plain candidate set is one suit's 1-14). So:
    - doppelkopf: pre-migration, `doko.py`'s trump comparison flipped -- 33
      of the first 40 seeds moved (`33 failed, 8 passed`, the not-slow
      selection); post-migration, the same flip in the kernel --
      `200 failed, 409 deselected`.
    - skat, five-hundred, belote, french-tarot: the SAME kernel flip leaves
      all four rows `200 passed` (executed 2026-08-19). That is the pack, not
      a dead row, and the witnesses below prove it.
* A KERNEL WITNESS, AND IT IS NOT ONE MUTATION FOR EVERY ROW.
  `winners.follows_lead_lazily`'s class comparison inverted (`==` to `!=`)
  reaches every row whose game filters through `follows_lead`: doppelkopf
  `200 failed`, skat `200 failed`, five-hundred `200 failed` (2026-08-19).
  It leaves BELOTE `200 passed`, and that is the row being different rather
  than dead: Belote's follow filter is the library rule `MustFollowSuit`
  over the literal `state.led_suit`, so its only consumer of the block is
  the winner. That is sound because Belote declares no `follow_class:` remap
  and holds no class-less card, and the soundness is EXECUTED rather than
  argued -- adding a remap (`if card.rank is J then trump_suit else
  card.suit`) reds this row `200 failed` AND the playout oracle at seed 0
  hand 2 trick 2, where the legality the rule computed and the classes the
  winner reads have come apart ("P2 was offered [six cards] ... give ['J♣',
  'K♣'] (must-trump)"). So a future remap cannot land beside the library
  rule in silence (executed 2026-08-19). The
  It reaches FRENCH TAROT, whose follow demand is `follows_lead` over the
  whole cascade: `200 failed` (2026-08-19). The
  mutation that reaches ALL FIVE is therefore in the winner:
  `winners.highest_by_trick_order`'s trump-candidate filter inverted
  (`if a.is_trump` -> `if not a.is_trump`) -- doppelkopf `200 failed`, skat
  `200 failed`, five-hundred `186 failed, 14 passed` (the 14 are no-trump
  and misere contracts, where the filter selects nothing either way),
  belote `200 failed`, french-tarot `202 failed, 2 passed` (2026-08-19) --
  where Tarot's two EXTRA failures are the row's own trace-claim tests, which
  play a game and meet the winner's "no card can win" Owner Guard once the
  filter selects the class-less Excuse: a louder red than the hash, through a
  second channel, and recorded as such rather than counted as the same one.
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
    - belote.cardlang, the top two trumps swapped in `card_strength:`
      (108 <-> 107, the jack under the nine): `200 failed` -- every seed,
      because a Belote game runs to 1000 over many hands and the trump band
      decides a trick in all of them.
    - french-tarot.cardlang, the atout band reversed inside its own row
      (`100 + numeral(card)` -> `100 - numeral(card)`, which keeps the band
      above the plain suits and only inverts the order within it):
      `200 failed` -- every seed, since a Tarot match is 36 hands of 18
      atout-trump tricks.
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

@dataclass(frozen=True)
class Migration:
    """One migrated game's pin. The hash file is captured on the commit
    BEFORE the migration lands, so its provenance is the git log.

    The two exclusion halves are claims about the post-migration tree, each
    executed by its own test, and never a way to quiet a diff:
    `retired_traces` says the migrated game no longer emits the event at all;
    `reshaped_traces` says it still does, with a payload the migration moved.
    Which half a name goes in is what makes the exclusion falsifiable, so
    there is no combined field to declare and no shared base to widen."""

    game_file: str
    hash_file: str
    retired_traces: frozenset[str] = frozenset()
    reshaped_traces: frozenset[str] = frozenset()

    @property
    def excluded_traces(self) -> frozenset[str]:
        return self.retired_traces | self.reshaped_traces


# One row per migrated game.
_HAND_ROLLED_TRICK = frozenset({"play", "trick"})


MIGRATIONS: tuple[Migration, ...] = (
    # `doko_trick_winner` was the only emitter of `play` and `trick`: the
    # tricks are hand-rolled movements, and the kernel's call form emits
    # neither.
    Migration(
        "doppelkopf.cardlang",
        "doppelkopf_stream_hashes.json",
        retired_traces=_HAND_ROLLED_TRICK,
    ),
    # `skat_trick_winner` emitted `trick_end` carrying the declared contract
    # ({game_type, trump}) as well, and was Skat's only emitter of it -- the
    # ten tricks are hand-rolled movements, not a trick `round`, so no round
    # form emits one here.
    Migration(
        "skat.cardlang",
        "skat_stream_hashes.json",
        retired_traces=_HAND_ROLLED_TRICK | {"trick_end"},
    ),
    # `five_hundred_trick_winner` likewise emitted `trick_end` carrying the
    # declared contract ({trump, misere, joker_suit}): the ten tricks are
    # hand-rolled movements and the game's one `round` is the auction, which
    # emits no trick.
    Migration(
        "five-hundred.cardlang",
        "five_hundred_stream_hashes.json",
        retired_traces=_HAND_ROLLED_TRICK | {"trick_end"},
    ),
    # Belote retires NOTHING: its tricks are a `round`, so `play`, `trick` and
    # `trick_end` all come from `runtime/mechanics.py` and outlive
    # `belote_trick_winner`. What moves is one FIELD of `trick_end` -- the
    # round's `trump` clause, which a block game may not carry.
    Migration(
        "belote.cardlang",
        "belote_stream_hashes.json",
        reshaped_traces=frozenset({"trick_end"}),
    ),
    # French Tarot excludes NOTHING, in either half, and that is the row's own
    # claim rather than an omission. Its tricks are a `round`, so `play`,
    # `trick` and `trick_end` all come from `runtime/mechanics.py` and outlive
    # `tarot_trick_winner` -- which was a winner CALLBACK and never an emitter.
    # Belote's one reshaping does not recur either: `trick_end` echoes the
    # ROUND's `trump` clause, and Tarot's trick round has never carried one
    # (the pre-migration golden IR reads `"trump": null` at both the game and
    # the round), so the field that moved for Belote is already `null` here.
    #
    # Both exclusion tests are therefore VACUOUS for this row -- an empty set
    # intersects nothing -- and the coverage that buys is the maximum, not the
    # minimum: with no name excluded, `_stream_digest` hashes the WHOLE trace
    # channel, so every event those two tests would have argued about sits
    # inside the primary pin instead. The tests exist for the rows that DO
    # exclude; this row is what they look like when a migration moves nothing.
    Migration("french-tarot.cardlang", "french_tarot_stream_hashes.json"),
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
def test_the_two_exclusion_halves_are_disjoint(migration: Migration) -> None:
    """An event is gone or it is not. A name in both halves would satisfy one
    of the two claim tests vacuously -- and which half a name sits in is the
    whole reason the exclusion is falsifiable."""
    both = sorted(migration.retired_traces & migration.reshaped_traces)
    assert not both, f"{migration.game_file}: {both} claimed retired AND reshaped"


def _emitted(game_file: str) -> set[str]:
    """The trace names one seeded playout of the MIGRATED game emits."""
    seen: set[str] = set()
    game = check_source(GAMES / game_file)
    rng = random.Random(0)
    play_game(game, rng, lambda name, data: seen.add(name), random_chooser(rng))
    return seen


@pytest.mark.parametrize("migration", MIGRATIONS, ids=_IDS)
def test_retired_traces_are_actually_gone(migration: Migration) -> None:
    """A row's `retired_traces` is a CLAIM -- "the migration retired this
    event" -- and this executes it: every name must be absent from the trace
    channel of the migrated game.

    Without this, an exclusion is a silencer: naming an event that still
    fires would drop it from the hashed rendering, and the pin would go on
    passing while covering strictly less than its docstring says. That is
    the vacuously-green class, in the one place this module could grow it."""
    still_emitted = sorted(migration.retired_traces & _emitted(migration.game_file))
    assert not still_emitted, (
        f"{migration.game_file} still emits {still_emitted}, which its "
        f"`Migration` row excludes as RETIRED: the exclusion is silencing a "
        f"live event rather than recording a retired one -- if the event "
        f"survives with a moved payload, it belongs in `reshaped_traces`"
    )


@pytest.mark.parametrize("migration", MIGRATIONS, ids=_IDS)
def test_reshaped_traces_are_still_emitted(migration: Migration) -> None:
    """The OPPOSITE claim, executed: a `reshaped_traces` name says the
    migrated game still emits the event and only its payload moved, so the
    event must actually be there.

    A row that labelled a RETIREMENT a reshaping would read as the weaker,
    better-covered case while covering the same nothing -- and would carry no
    record that the emitter had gone. Absent here means the row is wrong about
    its own migration, whichever way."""
    absent = sorted(migration.reshaped_traces - _emitted(migration.game_file))
    assert not absent, (
        f"{migration.game_file} does not emit {absent}, which its `Migration` "
        f"row excludes as merely RESHAPED: the event retired, so the row "
        f"belongs in `retired_traces`"
    )
