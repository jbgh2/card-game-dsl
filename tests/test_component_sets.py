"""Component sets: the one registry behind `cards:` and `pieces:`.

property:   every COMPONENT_SETS row is well-formed; DECKS is exactly its
            card-flavored projection; sizes pin to build_deck; every
            ComponentSet construction either satisfies the axes wall or
            raises ValueError naming the violated invariant; every
            build_deck lookup miss raises NotImplementedError naming
            component sets
domain:     COMPONENT_SETS rows x {flavor, axes, deck payload, size};
            ComponentSet.__post_init__'s wall x {axes distinct, both axes
            identifiers, piece flavor vs the ("suit","rank") reserved
            spelling} x {pass, fail}; build_deck's name lookup x {known,
            unknown}; component_set()'s {hit, miss}
registry:   cardlang.runtime.values.COMPONENT_SETS,
            cardlang.runtime.values.ComponentSet.__post_init__,
            cardlang.runtime.values.build_deck,
            cardlang.runtime.values.component_set
covered:    all rows, exhaustively parametrized below; DECKS-view equality;
            xo_marks composition pinned card-by-card; each of the wall's
            three branches fired directly (duplicate axes, non-identifier
            axis, piece flavor spelling "suit"/"rank"); build_deck's
            unknown-name refusal (message pinned to name component sets and
            list known ones) and component_set's graceful None on a miss —
            two distinct miss behaviors, each pinned as itself
sampled:    build_deck ordering, pinned against frozen expected values on
            standard52 (the suits x ranks cross-product path, first suit)
            and xo_marks (the explicit-list path, verbatim) — every other
            component set takes one of these two paths (a `ranks` cross
            product, or an explicit `cards` list for the non-uniform sets),
            so both build_deck order paths are sampled
residual:   none
"""

from __future__ import annotations

import pytest

from cardlang.runtime.values import COMPONENT_SETS, DECKS, ComponentSet, build_deck, component_set
from cardlang.stdlib.values import deck_size


def test_decks_is_the_card_flavored_projection() -> None:
    assert DECKS == {
        n: cs.deck for n, cs in COMPONENT_SETS.items() if cs.flavor == "card"
    }


@pytest.mark.parametrize("name", sorted(COMPONENT_SETS))
def test_every_set_declares_two_axes_and_a_size(name: str) -> None:
    cs = COMPONENT_SETS[name]
    assert len(cs.axes) == 2 and all(a.isidentifier() for a in cs.axes)
    assert cs.flavor in ("card", "piece")
    assert deck_size(name) == len(build_deck(name))


def test_card_sets_spell_the_deck_axes() -> None:
    assert all(
        cs.axes == ("suit", "rank")
        for cs in COMPONENT_SETS.values()
        if cs.flavor == "card"
    )


def test_xo_marks_composition() -> None:
    marks = build_deck("xo_marks")
    assert len(marks) == 9
    assert sum(1 for m in marks if m.suit == "x") == 5
    assert sum(1 for m in marks if m.suit == "o") == 4
    assert all(m.rank == "mark" for m in marks)


def test_build_deck_preserves_registry_literal_order() -> None:
    """Order is the registry-literal order by construction: the suits x
    ranks cross product for a uniform deck (sampled on standard52's first
    suit), the `cards` list verbatim for an explicit-list set (xo_marks).
    Frozen expected values, not derived from the registry's own constants,
    so a construction-order regression cannot pass by measuring itself."""
    standard = build_deck("standard52")
    assert [c.rank for c in standard[:13]] == [
        "2", "3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K", "A",
    ]
    assert {c.suit for c in standard[:13]} == {"clubs"}

    marks = build_deck("xo_marks")
    assert [m.suit for m in marks] == ["x"] * 5 + ["o"] * 4


# --- misuse probes: the ComponentSet construction wall -----------------
#
# Each probe is a plausible mistake a future caller (the pieces: clause
# lands in a later task) could make when building a ComponentSet by hand.
# Every one must fail loud as a ValueError naming the violated invariant --
# never a silent bad row landing in COMPONENT_SETS.


def test_duplicate_axes_reject() -> None:
    with pytest.raises(ValueError, match="distinct"):
        ComponentSet("card", ("suit", "suit"), COMPONENT_SETS["standard52"].deck)


def test_non_identifier_axis_rejects() -> None:
    with pytest.raises(ValueError, match="identifier"):
        ComponentSet("piece", ("side", "top-left"), COMPONENT_SETS["xo_marks"].deck)


def test_piece_flavor_cannot_spell_the_card_axes() -> None:
    with pytest.raises(ValueError, match="card flavor"):
        ComponentSet("piece", ("suit", "rank"), COMPONENT_SETS["xo_marks"].deck)


# --- misuse probes: unknown-name lookups --------------------------------


def test_component_set_accessor_returns_none_for_unknown_name() -> None:
    assert component_set("nosuchset") is None


def test_build_deck_unknown_name_names_component_sets() -> None:
    with pytest.raises(NotImplementedError, match="component set"):
        build_deck("nosuchset")


def test_build_deck_unknown_name_lists_known_names() -> None:
    with pytest.raises(NotImplementedError) as exc:
        build_deck("nosuchset")
    assert "xo_marks" in str(exc.value)
    assert "standard52" in str(exc.value)
