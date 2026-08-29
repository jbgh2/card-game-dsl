"""The known-findings ledger: every crash the T2 mutation sweep has found so
far, recorded — not fixed (module docstring of `oracle.py`, "Feed-forward
rule"; the CLAUDE.md instruction under which this package was built:
concurrent work is touching resolve/typecheck, so this package makes zero
`cardlang/` edits).

Each `Finding` names a minimal (by-hand-shrunk; see `oracle.py`'s "Residual")
input file under `known_findings/*.cardlang`, FROZEN at discovery time —
copied out of a live corpus mutant, not recomputed from `docs/games/` +
`mutate.py` at test time, so a later corpus edit can never silently drift or
un-reproduce a pinned finding. `test_fuzz.py`'s
`test_known_findings_still_reproduce` replays every entry here and asserts
the SAME outcome kind, exception type, and a message substring — "loud and
pinned" (grammar-fuzzing.md via the task brief that built this package): if
someone fixes the underlying guard without updating this ledger, that test
starts failing, which is the intended prompt to do the other half of the
feed-forward rule below.

Two classes (only `delete_line` has produced findings across the discovery
sweep this ledger is built from — the whole corpus x every operator x
seeds 0..4; every finding currently recorded is playout-class, the
wrong-channel entries having been fixed and fed forward to
`tests/rejections/`):

- `"wrong-channel-crash"`: `run_oracle` (T1) returns `"crash"` — the front
  end let something other than `DiagnosticError` escape `check_dsl`.
- `"accepted-then-crashes-at-playout"`: `run_oracle` returns `"passed"` but
  `run_playout` (T3) returns `"crash"` — the mutant is a well-typed program
  that breaks a runtime-net invariant only execution can see (a hand drained
  faster than a loop that draws from it terminates, a trick left with the
  wrong card count, non-termination against the declared `max_length`).

Feed-forward rule. When a finding below is fixed (a separate, later change,
NOT this package): delete its `Finding` entry here, delete its
`known_findings/<slug>.cardlang`, and add `tests/rejections/<slug>.cardlang`
+ `.expected` (if the fix makes it a proper `DiagnosticError`) so the fix
becomes a permanent regression case — `test_rejections.py`'s own module
docstring is the authority on that pair's format. A playout-class finding
whose fix is a NEW static guard (rather than an accepted runtime behavior)
follows the same path; a playout-class finding whose fix only improves the
runtime's own error message stays a `RuntimeError`/`AssertionError` outside
`DiagnosticError`'s channel and does not migrate to `tests/rejections/` —
it just gets deleted from this ledger once the message is re-pinned wherever
that runtime path already has its own test.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

FINDINGS_DIR = Path(__file__).resolve().parent / "known_findings"

Classification = Literal["wrong-channel-crash", "accepted-then-crashes-at-playout"]


@dataclass(frozen=True)
class Finding:
    slug: str
    classification: Classification
    # Which stage crashes: T1 (`run_oracle`) for wrong-channel, T3
    # (`run_playout`, on a game `run_oracle` accepted) for playout findings.
    stage: Literal["oracle", "playout"]
    exception_type_name: str  # `type(exception).__name__` — pinned by name,
    # not by importing the type, since the wrong-channel case's exception
    # (`lark.exceptions.VisitError`) lives in a dependency this package
    # otherwise has no reason to import directly.
    message_substring: str
    note: str

    @property
    def path(self) -> Path:
        return FINDINGS_DIR / f"{self.slug}.cardlang"

    @property
    def text(self) -> str:
        return self.path.read_text()


KNOWN_FINDINGS: tuple[Finding, ...] = (
    Finding(
        slug="klondike_flip_from_empty_stack",
        classification="accepted-then-crashes-at-playout",
        stage="playout",
        exception_type_name="OwnerGuardError",
        message_substring="cannot deal 1 cards from a source holding 0",
        note=(
            "docs/games/klondike.cardlang, `delete_line` seed 0, deleting "
            "the setup `deal 4 cards from deck to tableau_down[4]` (line 58 "
            "at discovery time). The setup flip `draw 1 card from "
            "tableau_down[4] to tableau_up[4]` then draws from an empty "
            "hidden stack and dies on the movement executor's "
            "exhausted-source ValueError before any decision. Checker-green "
            "because the deck-capacity gate's declared domain is DECK usage "
            "only (deckcheck.py) — an intermediate zone's balance is "
            "invisible to it; the general static net for non-deck source "
            "balances is the same recorded residual class."
        ),
    ),
    Finding(
        slug="cribbage_repeat_until_nonterminate",
        classification="accepted-then-crashes-at-playout",
        stage="playout",
        exception_type_name="OwnerGuardError",
        message_substring="exceeded the game's declared max_length",
        note=(
            "docs/games/cribbage.cardlang, `delete_line` seed 2, deleting "
            "the pegging loop's `move chosen one card from hand[active] "
            "where total + peg_value(card) <= 31 to play_pile` (line 87 at "
            "discovery time). With no card ever leaving `hand[active]`, the "
            "enclosing `repeat until` never reaches its exit condition and "
            "hits the runtime's own `max_length` (1500) iteration backstop "
            "after only 2 real decisions — a well-typed program whose "
            "non-termination only execution can observe. The live-corpus "
            "key drifted when the card_points clause landed (issue #249): "
            "seed 2 now deletes a `repeat until ... {` opener and the "
            "mutant is rejected at parse, so this finding is carried by its "
            "frozen fixture alone (no EXCUSED row)."
        ),
    ),
    Finding(
        slug="getaway_missing_deal_no_hand_holder",
        classification="accepted-then-crashes-at-playout",
        stage="playout",
        exception_type_name="OwnerGuardError",
        message_substring="player_holding: no hand contains",
        note=(
            "docs/games/getaway.cardlang, `delete_line` seed 0, deleting "
            "the setup `deal all cards from deck as-equally-as-possible to "
            "each hand` (line 37 at discovery time). No card ever leaves "
            "`deck`, so the very first `player_holding` lookup at the first "
            "decision point fails to find a holder for the queried card — "
            "crashes on the FIRST decision (0 completed)."
        ),
    ),
    Finding(
        slug="getaway_no_legal_play_no_if_impossible",
        classification="accepted-then-crashes-at-playout",
        stage="playout",
        exception_type_name="OwnerGuardError",
        message_substring="has no legal play in the trick",
        note=(
            "docs/games/getaway.cardlang, `delete_line` seed 4, deleting "
            "the end-of-hand elimination check `for each player p: if "
            "hand[p] is empty { eliminated[p] := true }` (line 69 at "
            "discovery time). A player who should have been marked "
            "eliminated stays a trick participant with an empty hand, and "
            "47 decisions in, the trick-following constraint has no legal "
            "card left to offer them."
        ),
    ),
    Finding(
        slug="cheat_empty_count_range",
        classification="accepted-then-crashes-at-playout",
        stage="playout",
        exception_type_name="OwnerGuardError",
        message_substring="has no value to choose (empty range)",
        note=(
            "docs/games/cheat.cardlang, `delete_line` seed 0, deleting the "
            "setup `deal 13 cards from deck to each hand` (line 97 at "
            "discovery time). Every hand stays empty, so the first play's "
            "`choose integer in 1 .. (number of cards in hand[actor])` is "
            "asked for a value from the empty range 1 .. 0 and refuses — "
            "crashes on the FIRST decision. The same missing-deal shape as "
            "`getaway_missing_deal_no_hand_holder`, surfacing through the "
            "integer-choice channel rather than a card lookup: the count's "
            "range is bounded by a hand the setup never filled."
        ),
    ),
    Finding(
        slug="gops_empty_legal_set",
        classification="accepted-then-crashes-at-playout",
        stage="playout",
        exception_type_name="AssertionError",
        message_substring="playout invariant violated",
        note=(
            "docs/games/gops.cardlang, `delete_line` seed 2, deleting the "
            "round's `move one card from prize_deck to prize` (line 61 at "
            "discovery time) — the harness's OWN T3 invariant "
            "('the legal-move set is non-empty until terminal', "
            "implementation.md) catching a real bug: with `prize_deck` "
            "never draining, the `repeat until prize_deck is empty` loop "
            "outlives both players' 13-card hands, and the 14th round's "
            "`move chosen 1 card from hand[player] to bid[player]` is "
            "asked to choose from an empty hand at decision 27."
        ),
    ),
)
