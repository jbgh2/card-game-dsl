"""Standard-library zone types, as data.

The library zone aliases from library.md, recorded as a table the resolver
checks references against. ``takes_owner`` records whether the type is
parameterized by an owner/role (``Hand<Owner>``) or is a singleton
(``Deck``). Seeded with what the walking skeleton needs; extended
corpus-first as games require new aliases.
"""

from __future__ import annotations

from dataclasses import dataclass

# zone type name -> whether it takes a single owner/role type argument
LIBRARY_ZONE_TYPES: dict[str, bool] = {
    "Deck": False,
    "Hand": True,
    "PublicHand": True,
    "TrickPile": False,
    "Discard": False,
    "Muck": False,
    "ChipStack": True,
    "PlayerPile": True,
    "TeamPile": True,  # a capture pile owned by a partnership (Spades)
    "FaceDownPile": False,  # a face-down stock (Schnapsen's talon)
    "Burn": False,  # the per-street burned-card pile (Stud)
    "HiddenPile": True,  # a resting pile a player owns but conceals (Tarot's discards)
    # Positional-layout types (decisions.md "Position domains and positional
    # zones"). All four take an index argument — a position domain, or a
    # seat/team role for the uniform-projection ones. Klondike + FreeCell.
    "Cascade": True,  # a face-up ordered pile; order public (arrival events)
    "HiddenStack": True,  # a face-down pile family (Klondike's tableau_down)
    "Foundation": True,  # an ascending suit pile (A up to K), face up
    "Cell": True,  # a one-card holding space (FreeCell's free cells)
}


@dataclass(frozen=True)
class ZoneVisibility:
    """Per-observer projection of a zone's contents (decisions.md "Knowledge,
    visibility, and the projection model"). `owner` applies to the observer the
    zone's index names (the owning player, or a member of the owning team);
    `others` to everyone else. Unowned zones use the same projection for both."""

    owner: str
    others: str


# library type name -> per-observer composition, from library.md "Library zone
# types". The corpus exercises identity / count_only / trivial; the remaining
# lattice levels gain emission rules when a game first uses them.
ZONE_PROJECTIONS: dict[str, ZoneVisibility] = {
    "Deck": ZoneVisibility("count_only", "count_only"),
    "Hand": ZoneVisibility("identity", "count_only"),
    "PublicHand": ZoneVisibility("identity", "identity"),
    "TrickPile": ZoneVisibility("identity", "identity"),
    "Discard": ZoneVisibility("identity", "identity"),
    "Muck": ZoneVisibility("trivial", "trivial"),
    "ChipStack": ZoneVisibility("count_only", "count_only"),
    "PlayerPile": ZoneVisibility("identity", "identity"),
    "TeamPile": ZoneVisibility("identity", "identity"),
    "FaceDownPile": ZoneVisibility("count_only", "count_only"),
    "Burn": ZoneVisibility("trivial", "trivial"),
    "HiddenPile": ZoneVisibility("identity", "count_only"),  # same profile as Hand
    "Cascade": ZoneVisibility("identity", "identity"),
    "HiddenStack": ZoneVisibility("count_only", "count_only"),
    "Foundation": ZoneVisibility("identity", "identity"),
    "Cell": ZoneVisibility("identity", "identity"),
}


def zone_projection(zone_type: str, is_owner: bool) -> str:
    """The projection an observer gets of a zone of this library type. Raises
    KeyError for an unknown type — a zone with no declared visibility cannot be
    projected, and silently guessing would leak information."""
    vis = ZONE_PROJECTIONS[zone_type]
    return vis.owner if is_owner else vis.others
