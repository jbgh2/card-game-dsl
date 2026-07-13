"""What `state.` may name: the published-field registry, and every rejection cell.

    property:   `state.<field>` names a round form's PUBLISHED state — a closed,
                typed set — and nothing else. A form's private working memory is
                unreachable from the DSL, an unpublished name is a compile error,
                and a published name carries a real type (so the existing walls
                work through it).

    domain:     Two sides that must agree.
                (a) The SURFACE side: every field name a `state.<field>` expression
                    can spell — unbounded, so the registry is the whitelist and
                    everything else must be rejected.
                (b) The IMPLEMENTATION side: every key each round form actually
                    writes into its accumulator, ANYWHERE (`init` seeds it, but
                    `next_actor` / `on_move` / `outcome` all write during play). Each
                    such key is either published (nameable) or internal (not) — there
                    is no third category, and that is what
                    `test_every_form_key_is_classified` pins, by watching the real
                    accumulator through a real playout.

    registry:   `cardlang.stdlib.round_state` — TRICK_PUBLISHED / TRICK_INTERNAL,
                CLIMB_PUBLISHED / CLIMB_INTERNAL, AUCTION_PUBLISHED /
                AUCTION_INTERNAL, and their union ROUND_STATE_FIELDS.
                Consumers: `typecheck` (types the member, rejects the rest) and
                `runtime/mechanics` (the forms pinned against it here).

    covered:    Surface — exhaustive by construction: the whitelist is the
                registry, and `test_rejects_every_internal_field` sweeps every
                internal of every form (derived from the registry, not hand-listed).
                Implementation — exhaustive over what actually runs:
                `test_every_form_key_is_classified` instruments the accumulator and
                plays a trick game (hearts) and a climb game (president), asserting
                every key written partitions into published + internal. A form that
                starts writing a new key fails until it is classified.
                Typing — the five published fields each assert their declared type,
                and `test_a_typed_member_reaches_the_enum_wall` pins the
                consequence: `TAny` used to be contagious, and the enum-comparison
                wall was dark behind it.

    sampled:    The corpus is the witness that the published set is the RIGHT one:
                every `state.` reference in docs/games/*.cardlang and
                stdlib/rules.cardlang resolves against it (pinned by the corpus
                typecheck suite), and there are exactly five distinct members used.

    residual:   Which FRAME a `state.` read sees is a separate axis from which NAME
                it may spell, and only the name axis is closed here. A reference is
                not statically attached to a form — `MustFollowSuit` lives once in
                stdlib/rules.cardlang and is activated by games in context — so the
                checker validates against the UNION of the forms' published sets
                and cannot prove that the round actually running publishes the
                field read. `state.shed_first` inside a trick phase type-checks.
                Wall: the runtime now fails loudly rather than returning a stale or
                foreign frame (the AuctionForm `last_round_state` clear, pinned by
                `test_auction_does_not_leave_a_stale_trick_frame`). Recorded in
                roadmap.md; the design seam is
                open-questions/round-state-in-information-states.md.
"""

from __future__ import annotations

import pytest

from cardlang.diagnostics import DiagnosticError
from cardlang.pipeline import check_dsl
from cardlang.stdlib.round_state import (
    AUCTION_INTERNAL,
    AUCTION_PUBLISHED,
    CLIMB_INTERNAL,
    CLIMB_PUBLISHED,
    ROUND_STATE_FIELDS,
    TRICK_INTERNAL,
    TRICK_PUBLISHED,
)
from cardlang.types import TBoolean, TEnum, TOptional, TPlayer

TRICK_GAME = """
game H {{
  players: 4
  direction: clockwise
  max_length: 60
  cards: standard52
  ranking: A K Q J 10 9 8 7 6 5 4 3 2
  zones {{ deck : Deck  hand[player] : Hand<player>  trick_pile : TrickPile }}
  state {{ taken[player] : Integer = 0  leader : Player = 0 }}
  phase p {{
    deal 13 cards from deck to each hand
    round play_to_trick from leader over all players source hand into trick_pile
          outcome highest_of_led_suit
    if {pred} {{ taken[outcome] += 1 }}
    leader := outcome
  }}
  winner: highest taken
}}
move_type play_to_trick {{ effect {{ }} }}
"""


def check(pred: str) -> None:
    check_dsl(TRICK_GAME.format(pred=pred), "probe")


def rejects(pred: str, message: str) -> None:
    with pytest.raises(DiagnosticError) as excinfo:
        check(pred)
    assert message in str(excinfo.value)


# ---------------------------------------------------------------------------
# The surface: what `state.` may name
# ---------------------------------------------------------------------------


def test_a_published_field_is_accepted() -> None:
    check("state.trick_terminated_early")


def test_rejects_a_misspelled_field() -> None:
    """Before the wall this reached the runtime as a bare `KeyError: 'lead_suit'`,
    with no span — and only if the line happened to execute."""
    rejects("state.lead_suit is none", "a round publishes no `lead_suit`")


def test_rejects_an_unknown_field() -> None:
    rejects("state.totally_bogus is none", "a round publishes no `totally_bogus`")


@pytest.mark.parametrize(
    "field", sorted(TRICK_INTERNAL | CLIMB_INTERNAL | AUCTION_INTERNAL)
)
def test_rejects_every_internal_field(field: str) -> None:
    """The severe cell, swept over every internal of every form — derived from the
    registry, not hand-listed.

    `state.idx` is the one that proves why this matters: it is `TrickForm`'s
    private ring cursor. It type-checked, it ran to completion, and it silently
    changed the game (in Hearts it moved the winner from player 2 to player 0). A
    typo at least crashed; a leak did not. A round's working memory was part of the
    language's surface by accident, and this is the wall that takes it back."""
    rejects(f"state.{field} is none", f"a round publishes no `{field}`")


def test_the_error_names_the_published_set() -> None:
    """A wall that only says 'no' teaches nothing; this one lists what IS nameable."""
    with pytest.raises(DiagnosticError) as excinfo:
        check("state.idx is none")
    message = str(excinfo.value)
    for field in ROUND_STATE_FIELDS:
        assert f"`{field}`" in message


# ---------------------------------------------------------------------------
# The types: the second half of the win
# ---------------------------------------------------------------------------


def test_published_fields_carry_their_declared_types() -> None:
    assert TRICK_PUBLISHED == {
        "led_suit": TOptional(TEnum("Suit")),
        "trick_terminated_early": TBoolean(),
    }
    assert CLIMB_PUBLISHED == {
        "lead_ended_trick": TBoolean(),
        "shed_first": TOptional(TPlayer()),
        "shed_second": TOptional(TPlayer()),
    }
    # Deliberately empty, and load-bearing: it makes "the auction form has no
    # `state.`" a checkable fact rather than something you learn from a stale read.
    assert AUCTION_PUBLISHED == {}


def test_a_typed_member_reaches_the_enum_wall() -> None:
    """`state.led_suit` used to infer `TAny`, and `TAny` is contagious: comparing it
    to anything slipped past the enum-comparison wall. Now that it is `Suit?`, that
    wall reaches through it."""
    rejects("state.led_suit is 10", "comparing Suit with Integer can never be equal")


def test_led_suit_still_compares_against_a_suit_and_none() -> None:
    check("state.led_suit is none")
    check("state.led_suit is hearts")


# ---------------------------------------------------------------------------
# The implementation side: the forms are pinned to the registry
# ---------------------------------------------------------------------------


def test_every_form_key_is_classified() -> None:
    """The two-sided pin. Every key a round form actually writes into its accumulator
    must be either published (nameable from the DSL) or internal (not) — there is no
    third category, and a form that starts writing a new key fails here until someone
    decides which it is. That is what stops the surface from widening by accident.

    It watches the REAL accumulator through a real playout rather than grepping
    `init`'s source for `state["…"]` literals, which was the first attempt and was
    narrower than the domain it claimed: it saw only `init`, and only literal
    subscripts, so a key written during play (`next_actor`, `on_move`, `outcome` all
    write), or through a variable, or as the second target of a tuple-unpack, was
    invisible to it — the pin would stay green while the language quietly grew."""
    import random
    from pathlib import Path
    from typing import Any, Callable

    from cardlang.pipeline import check_source
    from cardlang.runtime import mechanics
    from cardlang.runtime.driver import play_game

    seen: set[str] = set()

    class _Watched(dict[str, Any]):
        def __setitem__(self, key: str, value: Any) -> None:
            seen.add(key)
            super().__setitem__(key, value)

    original: Callable[..., Any] = mechanics.run_decision_round

    def watched(form_obj: Any, _state: Any, ctx: Any) -> Any:
        # The executor seeds each round with a fresh `{}`; hand the form a dict that
        # records every key it is ever given, wherever in the form that happens.
        return original(form_obj, _Watched(), ctx)

    root = Path(__file__).parent.parent / "docs" / "games"
    forms = (
        ("trick", "hearts", set(TRICK_PUBLISHED) | TRICK_INTERNAL),
        ("climb", "president", set(CLIMB_PUBLISHED) | CLIMB_INTERNAL),
    )
    for form, game_name, classified in forms:
        seen.clear()
        game = check_source(root / f"{game_name}.cardlang")
        setattr(mechanics, "run_decision_round", watched)
        try:
            play_game(game, random.Random(0), None)
        finally:
            setattr(mechanics, "run_decision_round", original)

        assert seen, f"no {form} round ran in {game_name}"
        unclassified = seen - classified
        assert not unclassified, (
            f"the {form} form writes {sorted(unclassified)}, which "
            f"stdlib/round_state.py classifies as neither published nor internal"
        )


def test_auction_does_not_leave_a_stale_trick_frame() -> None:
    """The frame axis, walled as far as it can be. `state.` read during or after an
    auction used to find `mech_state` empty, fall through to the fallback, and
    silently return the state of whatever trick ran LAST — a live frame from a
    different form. The auction now clears it, so the read fails loudly instead."""
    import inspect

    from cardlang.runtime import mechanics

    assert "last_round_state = None" in inspect.getsource(mechanics.AuctionForm.init)
