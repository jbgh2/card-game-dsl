"""Axis derivation for the `teams:` partition grid.

Separate from the grid module so the derivation can be replayed against the
merge base: the review reads the HEAD-derived cell list and runs it on the
base tree, where the cells that fail (plus the cells that cannot exist) are
the change's behavioral delta. A base tree re-deriving its own cell list
would lose exactly the rows the change adds.

Every axis reads a registry or a grammar production; none is a list held in
this module's head.
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass

from cardlang.ast import nodes as n

# --- axis: the shape of the `players:` declaration --------------------------
# DERIVED by CROSSING the node's own predicates rather than by listing the two
# spellings. `PlayersSpec` answers three independent questions — is it written
# as a range, does the seat count actually vary, are the bounds well formed —
# and the cells below are the reachable combinations of those answers. Reading
# the axis off the spelling instead is what left a degenerate `players: 4..4`
# out of the domain: it is written as a range, denotes a fixed four seats, and
# so belongs to a cell that "fixed vs range" cannot express.
#
# The axis is a list of CLAUSES, and `shape_of` recomputes each one's identity
# from the parsed node, so a clause whose classification changes reddens the
# grid rather than silently moving cells.
PLAYERS_CLAUSES: dict[str, str] = {
    "fixed": "players: 4",
    "degenerate_range": "players: 4..4",
    "varying_range": "players: 4..6",
    "malformed_zero": "players: 0",
    "malformed_descending": "players: 4..3",
}


def shape_of(spec: n.PlayersSpec) -> str:
    """Classify a parsed `players:` spec by the node's own predicates."""
    if not spec.is_well_formed:
        return "malformed"
    if spec.varies:
        return "varying"
    return "fixed"  # a degenerate range lands here, which is the point


PLAYERS_SHAPES: tuple[str, ...] = tuple(PLAYERS_CLAUSES)

assert {f.name for f in n.PlayersSpec.__dataclass_fields__.values()} >= {
    "low",
    "high",
}, "PlayersSpec changed shape — re-derive the players axis from it"
assert all(
    hasattr(n.PlayersSpec, p) for p in ("is_range", "varies", "is_well_formed")
), "PlayersSpec lost a predicate the players axis is crossed from"


# --- axis: how a candidate `teams:` value relates to the seat set -----------
# The property under guard is that the declared teams PARTITION the seats:
# read as a map from seat to team, every seat 0..count-1 appears exactly once
# across all teams. That property is a conjunction of three independent
# clauses, and the axis is the exhaustive set of ways to violate exactly one
# of them plus the satisfying case — derived below by CLASSIFYING a candidate
# value, so a cell's name is computed from the value rather than asserted
# about it.


@dataclass(frozen=True)
class SeatVerdict:
    """How one `teams:` value stands against a seat count."""

    out_of_range: tuple[int, ...]  # declared members that are not seats
    repeated_within: tuple[int, ...]  # a seat listed twice inside one team
    repeated_across: tuple[int, ...]  # a seat listed in two different teams
    missing: tuple[int, ...]  # a seat no team lists

    @property
    def is_partition(self) -> bool:
        return not (
            self.out_of_range
            or self.repeated_within
            or self.repeated_across
            or self.missing
        )

    @property
    def label(self) -> str:
        if self.is_partition:
            return "partition"
        return "+".join(
            name
            for name, members in (
                ("out_of_range", self.out_of_range),
                ("repeated_within", self.repeated_within),
                ("repeated_across", self.repeated_across),
                ("missing", self.missing),
            )
            if members
        )


def classify(teams: tuple[tuple[int, ...], ...], seat_count: int) -> SeatVerdict:
    """Classify a `teams:` value against a seat count.

    The one place the partition property is spelled out, so the grid's
    expected column and the cell labels read the same definition. Note that
    `repeated_within` and `repeated_across` are counted separately: they are
    the same broken clause (a seat appears more than once) but reach a
    designer as different mistakes, and the implementation is free to give
    them one diagnostic or two — the grid records which.
    """
    seats = range(seat_count)
    out_of_range = tuple(
        sorted({s for team in teams for s in team if s not in seats})
    )
    repeated_within = tuple(
        sorted({s for team in teams for s in team if team.count(s) > 1})
    )
    holding = {s: sum(1 for team in teams if s in team) for s in seats}
    repeated_across = tuple(sorted(s for s, k in holding.items() if k > 1))
    missing = tuple(sorted(s for s, k in holding.items() if k == 0))
    return SeatVerdict(out_of_range, repeated_within, repeated_across, missing)


# The candidate values the grid crosses, on a four-seat game.
#
# The four violation clauses are NOT independent at a fixed seat count: drop
# a seat from one team to duplicate it in another and the partition is short
# a seat as well, so the obvious candidates all classify as compounds. The
# isolating candidates below were derived by running `classify` over them
# until each reported exactly one clause — which is why the label is
# COMPUTED rather than asserted: authoring these by name would have shipped
# four cells claiming to isolate a clause while each tested two.
#
# Both forms are carried. The isolating rows say which clause a diagnostic
# answers for; the compound rows are what a designer actually mistypes (the
# first is issue #155's own example) and say what they read when two clauses
# break at once.
CANDIDATES: tuple[tuple[str, tuple[tuple[int, ...], ...]], ...] = (
    ("absent", ()),
    ("partition_pairs", ((0, 2), (1, 3))),
    ("partition_single_team", ((0, 1, 2, 3),)),
    # isolating: exactly one clause broken
    ("only_out_of_range", ((0, 2), (1, 3, 5))),
    ("only_repeated_within", ((0, 0, 1), (2, 3))),
    ("only_repeated_across", ((0, 1), (0, 2, 3))),
    ("only_missing", ((0, 1), (2,))),
    # compound: the plausible typos, which break two clauses at once
    ("typo_phantom_seat", ((0, 2), (1, 5))),
    ("typo_duplicate_seat", ((0, 0), (1, 2))),
    ("typo_seat_on_two_teams", ((0, 1), (0, 2))),
)


def cells(seat_count: int = 4) -> Iterator[tuple[str, tuple[tuple[int, ...], ...], str]]:
    """(cell id, teams value, derived verdict label) for every candidate.

    `absent` is the one candidate with no seats to partition; it is carried
    as a cell because "declares no teams" is a legal game and the guard must
    not fire on it.
    """
    for name, value in CANDIDATES:
        label = "absent" if not value else classify(value, seat_count).label
        yield name, value, label
