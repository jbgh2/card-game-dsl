"""The native call boundary: arguments arrive in their declared type's shape.

A collection-typed expression has exactly two runtime shapes — a ``Zone``
(a zone reference or family subscript) and a plain ``list`` (a query, a
comprehension, a ``[...]`` literal, the joint-selection ``cards`` binder).
Every raw-Python consumer of such a value must handle both; the
evaluator's own sites (query/comprehension sources, ``in``, rule
fallbacks, ``turns`` participants) apply the canonical Zone-to-elements
coercion (``cardlang.runtime.state.elements``).  ``evaluate.native_call``
is the one boundary where user-expression values leave the evaluator for
bare Python adapters, and it coerces SIGNATURE-DRIVEN at its entry (via
``reads.coerce_args``, once, ahead of both dispatch homes): an
argument is stripped to its elements iff its declared param type is
``TCollection``.  A ``TAny`` param passes raw — polymorphic adapters
(``suit_of``: "a card or a single-card zone") dispatch on the shape
themselves, so a blanket coercion is a defect, not a stronger guard (it
turned the schnapsen trump indicator into a bare list; the playout
suite caught it).

Completeness ledger
    property:  every native argument reaches its adapter in the shape the
               adapter's declared param type promises — TCollection params
               as elements (never a raw TypeError on a Zone), TAny params
               untouched (the adapter's own shape dispatch still sees the
               Zone).
    domain:    {every function the boundary can be handed arguments against}
               x declared param type {TCollection, TAny, scalar} x
               {Zone, list} argument shapes.
    registry:  cardlang/builtins/signatures.py CALL_SIGS (the Builtins,
               pinned equal to `BUILTIN_CALL_FUNCS`), unioned with each
               registered Primitive's own signature through
               `primitives_block.implementation_sig` (`_signatures` below);
               the shape axis is the evaluator's value universe
               (cardlang/runtime/state.py `elements` names it).
    covered:   TCollection axis — gin_valid_meld, gin_arrange_ok x Zone:
               the pipeline probes below (true AND false witnesses, so the
               value is proven, not just the absence of a crash); x list —
               the corpus jointly path (tests/test_jointly_selection.py,
               test_playout_gin_rummy.py).  TAny axis — suit_of x Zone:
               the polymorphic probe below (plus the schnapsen playout
               suite, whose trump indicator exercises it for real).  Both
               probe tables are reconciled against the registry
               (test_every_collection_param_function_has_a_zone_probe,
               test_polymorphic_param_set_is_pinned), so a future
               collection-param or TAny-param primitive cannot land
               unprobed.
    sampled:   scalar params (TCard/TPlayer/TInteger/...) are single-shape
               by construction — no coercion, exercised by every corpus
               playout.
    residual:  a TCollection param with zone=True (an adapter wanting the
               Zone HANDLE under a collection type) would be stripped by
               the boundary; test_no_native_param_demands_a_zone guards the
               registry so adding one forces the boundary decision to be
               revisited instead of the handle being silently stripped.
"""

from __future__ import annotations

import random

import pytest

from cardlang.builtins.signatures import CALL_SIGS, Sig
from cardlang.pipeline import check_dsl
from cardlang.primitives_block import PRIMITIVE_IMPLEMENTATIONS, implementation_sig
from cardlang.runtime.driver import play_game
from cardlang.types import TAny, TCollection


def _signatures() -> dict[str, Sig]:
    """Every signature the boundary can be handed arguments against: the
    Builtins' table, plus each registered Primitive's own statement of its
    shape.

    Two tables because the halves state their signatures in two places —
    `CALL_SIGS` keys the Builtins exactly (pinned at
    tests/test_permissive_top.py) and a Primitive's shape is the `sig` column
    of its implementation row, read through `implementation_sig`."""
    sigs = dict(CALL_SIGS)
    for name in PRIMITIVE_IMPLEMENTATIONS:
        sig = implementation_sig(name)
        assert sig is not None, (
            f"{name} is registered as implemented and states no signature, so "
            f"the probe reconciliations below would silently skip it"
        )
        sigs[name] = sig
    return sigs


def _collection_param_funcs() -> set[str]:
    return {
        name
        for name, sig in _signatures().items()
        if any(isinstance(p, TCollection) for p in sig.params)
    }


def _polymorphic_param_funcs() -> set[str]:
    return {
        name
        for name, sig in _signatures().items()
        if any(isinstance(p, TAny) for p in sig.params)
    }


def _game(body: str, clauses: str = "") -> str:
    return (
        "game G {\n"
        + clauses +
        "  players: 2\n"
        "  max_length: 1000\n"
        "  cards: standard52\n"
        "  ranking: A K Q J 10 9 8 7 6 5 4 3 2\n"
        "  zones { deck : Deck  hand[player] : Hand<player>\n"
        "          taken[player] : HiddenPile<player>  discard : Discard\n"
        # The gin probes call declared Primitives, so the binder materialises
        # the ENTRY's own row — `hand`/`taken` for the arrangement guard, and
        # nothing at all for the meld predicate, which is pure over its
        # argument. The remaining zones are here because the deal writes them,
        # not because a bundle demands them.
        "          shown_deadwood[player] : Discard\n"
        "          meldA[player] : Discard  meldB[player] : Discard\n"
        "          meldC[player] : Discard }\n"
        "  state { dealer : Player = 0\n"
        "          score[player] : Integer = 0 }\n"
        "  winner: highest score\n"
        f"{body}\n"
        "}\n"
    )


# hand[0]: the four 7s — a valid set (and, meld declared, an empty remainder,
# so `gin_arrange_ok` is also true).  hand[1]: kings and queens — eight cards
# of two ranks, neither a set nor a run, so both predicates are false.
_DEAL = (
    "    move all cards to deck\n"
    '    move all cards from deck where card.rank is "7" to hand[dealer]\n'
    "    move all cards from deck where card.rank is K or card.rank is Q to hand[1]\n"
)

# One probe per registry member: the function called with a ZONE argument
# (`hand[...]`), scoring 1 for the true witness and attempting the false one.
_ZONE_PROBES: dict[str, str] = {
    "gin_valid_meld": _game(
        "  phase p {\n" + _DEAL +
        "    if gin_valid_meld(hand[dealer]) { score[dealer] += 1 }\n"
        "    if gin_valid_meld(hand[1]) { score[1] += 1 }\n"
        "  }",
        clauses="  primitives { gin_valid_meld(cards : Collection<Card>) : Boolean }\n",
    ),
    "gin_arrange_ok": _game(
        "  phase p {\n" + _DEAL +
        "    if gin_arrange_ok(dealer, hand[dealer]) { score[dealer] += 1 }\n"
        "    if gin_arrange_ok(1, hand[1]) { score[1] += 1 }\n"
        "  }",
        clauses=(
            "  primitives { gin_arrange_ok(p : Player, cards : Collection<Card>)"
            " : Boolean reads hand[p], taken[p] }\n"
        ),
    ),
    # `top_of`/`bottom_of` (decisions.md "Position domains and positional
    # zones"): each reads a card off a ZONE argument. The filtered deal
    # preserves deck order (suit-major, 2..A rank-minor), so hand[dealer] is
    # 7♣ 7♦ 7♥ 7♠ (both ends rank 7 — the true witness) and hand[1] is
    # Q♣ K♣ … Q♠ K♠ (bottom Q♣, top K♠ — each false arm probes the end the
    # order refutes), matching the gin probes' {0: 1, 1: 0} contract.
    "top_of": _game(
        "  phase p {\n" + _DEAL +
        '    if top_of(hand[dealer]).rank is "7" { score[dealer] += 1 }\n'
        "    if top_of(hand[1]).rank is Q { score[1] += 1 }\n"
        "  }"
    ),
    "bottom_of": _game(
        "  phase p {\n" + _DEAL +
        '    if bottom_of(hand[dealer]).rank is "7" { score[dealer] += 1 }\n'
        "    if bottom_of(hand[1]).rank is K { score[1] += 1 }\n"
        "  }"
    ),
}


def test_every_collection_param_function_has_a_zone_probe() -> None:
    """The probe table is registry-derived: a new TCollection-param native
    function fails here until it gets a zone-argument probe."""
    assert _collection_param_funcs() == set(_ZONE_PROBES), (
        "a native function with a TCollection param has no zone-argument "
        "probe in _ZONE_PROBES — its adapter would be one Zone subscript "
        "away from a raw TypeError; add the probe"
    )


def test_no_native_param_demands_a_zone() -> None:
    """The boundary coerces Zone -> elements for every argument, so no
    CALL_SIGS param may claim it wants the Zone handle itself; a zone=True
    param must revisit `coerce_args` in cardlang/runtime/reads.py."""
    offenders = [
        name
        for name, sig in _signatures().items()
        for p in sig.params
        if isinstance(p, TCollection) and p.zone
    ]
    assert not offenders, (
        f"{offenders} declare zone-handle params, but the native call "
        "boundary strips Zone to its elements — a zone-wanting primitive "
        "needs the boundary decision revisited, not a silent strip"
    )


@pytest.mark.parametrize("func", sorted(_ZONE_PROBES))
def test_zone_argument_reaches_the_adapter_as_its_elements(func: str) -> None:
    """A zone expression is a legal TCollection argument (the zone facet is
    not part of assignability), so it must EVALUATE — seat 0 holds a meld
    (true), seat 1 holds junk (false) — not die on `list(Zone)`."""
    game = check_dsl(_ZONE_PROBES[func], "probe.cardlang")
    result = play_game(game, rng=random.Random(0))
    assert result.scores == {0: 1, 1: 0}


def test_polymorphic_param_set_is_pinned() -> None:
    """The TAny-param functions are the boundary's OTHER shape-sensitive
    class: their adapters dispatch on the runtime shape themselves, so the
    boundary must pass their arguments raw.  A new TAny-param function must
    decide its shape handling here and gets a probe like suit_of's."""
    assert _polymorphic_param_funcs() == {
        "suit_of",
        "highest_trump_or_led_suit",
        "highest_by_trick_order",
        "follows_lead",
    }, (
        "a native function with a TAny (polymorphic) param joined the "
        "boundary — its adapter sees raw shapes (no coercion); add a "
        "zone-argument probe for it beside test_polymorphic_suit_of_"
        "still_sees_the_zone"
    )


def test_polymorphic_trick_winner_still_sees_the_zone() -> None:
    """`highest_trump_or_led_suit` declares TAny for its zone argument
    because the runtime needs the Zone HANDLE — the Arrival Record rides the
    zone, and a coerced element list would strip it (issue #256). The probe:
    the dealer plays a chosen heart into the public discard; the winner over
    that one recorded play is the dealer, which only computes if the adapter
    received the zone with its record intact."""
    game = check_dsl(
        _game(
            "  phase p {\n"
            "    move all cards to deck\n"
            "    as dealer { move chosen one card from deck where card.suit is hearts to discard }\n"
            "    if highest_trump_or_led_suit(discard, clubs) is dealer { score[dealer] += 1 }\n"
            "  }"
        ),
        "probe.cardlang",
    )
    result = play_game(game, rng=random.Random(0))
    assert result.scores == {0: 1, 1: 0}


_TRICK_ORDER_PROBE = "  trick_order { trump: card.suit is clubs }\n"


def test_polymorphic_trick_order_winner_still_sees_the_zone() -> None:
    """`highest_by_trick_order` declares TAny for the same reason its sibling
    does: the [[arrival-record]] rides the Zone, and a coerced element list
    would strip it. Same probe shape — the dealer plays one heart into the
    public discard, and the winner over that one recorded play is the dealer,
    which only computes if the adapter received the zone with its record
    intact. Under this block hearts are not trumps, so the winner comes from
    the Effective Lead's class, exercising the non-trump branch."""
    game = check_dsl(
        _game(
            "  phase p {\n"
            "    move all cards to deck\n"
            "    as dealer { move chosen one card from deck where card.suit is hearts to discard }\n"
            "    if highest_by_trick_order(discard) is dealer { score[dealer] += 1 }\n"
            "  }",
            clauses=_TRICK_ORDER_PROBE,
        ),
        "probe.cardlang",
    )
    result = play_game(game, rng=random.Random(0))
    assert result.scores == {0: 1, 1: 0}


def test_polymorphic_follows_lead_still_sees_the_zone() -> None:
    """`follows_lead`'s PILE argument is the polymorphic one (its card is
    `TCard` and coerced). The probe drives the answer both ways off one
    recorded play: a heart follows the led heart, a club does not — and
    neither answer is computable unless the adapter received the zone with
    its Arrival Record intact, because an empty record makes `follows_lead`
    false for everything."""
    game = check_dsl(
        _game(
            "  phase p {\n"
            "    move all cards to deck\n"
            "    as dealer { move chosen one card from deck where card.suit is hearts to discard }\n"
            "    if any card in deck where card.suit is hearts and follows_lead(card, discard) { score[dealer] += 1 }\n"
            "    if any card in deck where card.suit is clubs and follows_lead(card, discard) { score[1] += 1 }\n"
            "  }",
            clauses=_TRICK_ORDER_PROBE,
        ),
        "probe.cardlang",
    )
    result = play_game(game, rng=random.Random(0))
    assert result.scores == {0: 1, 1: 0}


def test_polymorphic_suit_of_still_sees_the_zone() -> None:
    """The counter-direction of the guard: `suit_of` declares TAny and
    dispatches on shape ("a card or a single-card zone"), so the boundary
    must NOT strip its Zone argument — the schnapsen trump indicator is the
    corpus witness.  Blanket coercion broke exactly this."""
    game = check_dsl(
        _game(
            "  phase p {\n"
            "    move all cards to deck\n"
            "    move 1 cards from deck where card.suit is hearts to discard\n"
            "    if suit_of(discard) is hearts { score[dealer] += 1 }\n"
            "  }"
        ),
        "probe.cardlang",
    )
    result = play_game(game, rng=random.Random(0))
    assert result.scores == {0: 1, 1: 0}
