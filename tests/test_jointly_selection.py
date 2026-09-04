"""Joint-predicate selection (decisions.md "Joint-predicate selection"):
`move chosen some cards from <zone> where jointly <pred> to <zone>`.

property:   a joint selection offers the chooser exactly the subsets of the
            source that satisfy the joint predicate (which binds `cards`,
            the candidate SET), sized per the amount (`some` = any non-empty
            size; an expression = exactly that size); every other
            grammar-accepted combination is implemented uniformly or
            statically rejected with a located diagnostic.
domain:     selection-mode (dealt/chosen/random) × amount (one/expr/all/
            some) × filter-mode (none/per-card/joint) × source arity,
            plus the runtime states (no satisfying subset; oversized
            enumeration pool).
registry:   the movement grammar matrix (cardlang.lark `movement`,
            `selection`, `amount`, `where_clause`); the `Transfer` node's
            (mode, amount, filter, joint) fields.
covered:    - `where jointly` parses with `joint=True`; plain `where` stays
              per-card [grammar/parse]
            - `jointly` requires `chosen` (dealt and random rejected,
              located) [resolve]
            - `some` requires `jointly` (rejected otherwise, located)
              [resolve]
            - `cards` binds ONLY inside the joint predicate, as a card
              collection; `card` does not bind there; outside the filter
              `cards` is unresolved [resolve/typecheck]
            - the chooser is offered exactly the satisfying subsets, in
              deterministic enumeration order — the order itself is pinned
              (a reversed-order mutant fails) [runtime]
            - subset sizes are >= 1: zero/negative counts and `all` over an
              empty pool fall to the loud no-subset error; negative amounts
              are typed errors on EVERY movement path and a zero `chosen`
              amount is a vacuous-decision refusal (`_check_count`)
              [runtime]
            - no satisfying subset → loud RuntimeError (no-implicit-actions)
              [runtime]
            - a source pool above the enumeration bound → loud RuntimeError
              naming the bound [runtime]
            - `to each` under `jointly` → located resolve rejection (each
              destination seat would become its own subset decider)
              [resolve]
            - fused amount typos (`onecards`, `allcards`) are loud, never a
              silent keyword-split parse (anchored amount keywords)
              [grammar]
            - a joint `some` return INTO the deck credits ONE card, not a
              refill — the over-credit accepted a mid-deal crash [deckcheck]
            - the action space guards an unregistered/inline joint predicate,
              a climb+joint game, and two distinct joint codecs — all three
              NotImplementedError guards probed [encoding]
sampled:    the single-dest destination shape shares the ordinary movement
            path after selection — pinned by one single-dest test.
residual:   `jointly` under `random` mode (uniform over satisfying subsets)
            is implementable but has no corpus user — rejected loudly,
            recorded in roadmap.md "Grammar surface deferred by the
            checker" alongside `some` without `jointly` and `to each`.
"""

from __future__ import annotations

import random
from typing import Any

import pytest

from cardlang.ast import nodes as n
from cardlang.diagnostics import DiagnosticError
from cardlang.parse import parse_text
from cardlang.pipeline import check_dsl
from cardlang.resolve import _walk
from cardlang.runtime.driver import play_game
from cardlang.runtime.errors import OwnerGuardError


def _game(body: str, block: str = "") -> str:
    """A probe game. `block` is its `primitives { }` entries, written by the
    cells whose joint predicate roots in a declared Primitive: gin's two are
    reached by declaration alone (`DECLARED_ONLY_CALL_FUNCS`), so a game with
    no block is refused at the name and the selection is never encoded."""
    return (
        "game G {\n"
        "  players: 2\n"
        "  max_length: 1000\n"
        "  cards: standard52\n"
        "  ranking: A K Q J 10 9 8 7 6 5 4 3 2\n"
        + block +
        "  zones { deck : Deck  hand[player] : Hand<player>\n"
        "          taken[player] : HiddenPile<player>\n"
        "          discard : Discard }\n"
        "  state { dealer : Player = 0\n"
        "          score[player] : Integer = 0 }\n"
        "  winner: highest score\n"
        f"{body}\n"
        "}\n"
    )


JOINT_PRED = "(number of cards in cards) >= 3"


def test_jointly_parses_with_joint_flag_and_some_amount() -> None:
    game = parse_text(
        _game(
            "  phase p { as dealer { move chosen some cards from hand[dealer]\n"
            f"            where jointly {JOINT_PRED} to discard }} }}"
        ),
        "t.cardlang",
    )
    mv = next(nd for nd in _walk(game) if isinstance(nd, n.Transfer))
    assert mv.joint is True
    assert mv.amount == "some"
    assert mv.selection_mode == "chosen"


def test_plain_where_stays_per_card() -> None:
    game = parse_text(
        _game(
            "  phase p { as dealer { move chosen one card from hand[dealer]\n"
            "            where card.suit is hearts to discard } }"
        ),
        "t.cardlang",
    )
    mv = next(nd for nd in _walk(game) if isinstance(nd, n.Transfer))
    assert mv.joint is False


def test_jointly_checks_clean() -> None:
    check_dsl(
        _game(
            "  phase p { as dealer { move chosen some cards from hand[dealer]\n"
            f"            where jointly {JOINT_PRED} to discard }} }}"
        ),
        "t.cardlang",
    )


# --- misuse probes (surface-totality rejection tests) ---


def test_jointly_requires_chosen_dealt_rejected() -> None:
    with pytest.raises(DiagnosticError) as e:
        check_dsl(
            _game(
                "  phase p { move some cards from hand[0]\n"
                f"            where jointly {JOINT_PRED} to discard }}"
            ),
            "t.cardlang",
        )
    assert "chosen" in e.value.diagnostic.message


def test_jointly_requires_chosen_random_rejected() -> None:
    with pytest.raises(DiagnosticError) as e:
        check_dsl(
            _game(
                "  phase p { move random some cards from hand[0]\n"
                f"            where jointly {JOINT_PRED} to discard }}"
            ),
            "t.cardlang",
        )
    assert "chosen" in e.value.diagnostic.message


def test_some_requires_jointly() -> None:
    with pytest.raises(DiagnosticError) as e:
        check_dsl(
            _game("  phase p { move chosen some cards from hand[0] to discard }"),
            "t.cardlang",
        )
    assert "jointly" in e.value.diagnostic.message


def test_cards_binder_does_not_leak_past_the_filter() -> None:
    with pytest.raises(DiagnosticError) as e:
        check_dsl(
            _game(
                "  phase p { as dealer { move chosen some cards from hand[dealer]\n"
                f"            where jointly {JOINT_PRED} to discard\n"
                "            score[0] += number of cards in cards } }"
            ),
            "t.cardlang",
        )
    assert "cards" in e.value.diagnostic.message


def test_card_does_not_bind_in_a_joint_filter() -> None:
    with pytest.raises(DiagnosticError) as e:
        check_dsl(
            _game(
                "  phase p { as dealer { move chosen some cards from hand[dealer]\n"
                "            where jointly card.suit is hearts to discard } }"
            ),
            "t.cardlang",
        )
    assert "card" in e.value.diagnostic.message


# --- runtime semantics ---


def _setup_game(stmt: str, hand_spec: str) -> str:
    # A deterministic 1-hand game: the setup deals nothing; the phase places
    # specific cards via per-card filtered moves from the deck, then runs the
    # joint selection under `as dealer`.
    return _game(
        f"  phase setup {{ {hand_spec} }}\n"
        f"  phase p {{ as dealer {{ {stmt} }} }}"
    )


SAME_RANK_PRED = (
    "(number of cards in cards) >= 3 and "
    "(highest rank_value(card) over cards in cards or 0) is "
    "(lowest rank_value(card) over cards in cards or 0)"
)


def _place(rank: str, suit: str) -> str:
    # Letter ranks are bare names; only numeric ranks are spelled as strings
    # (they would otherwise read as Integers) — the checker's own register.
    lit = f'"{rank}"' if rank.isdigit() else rank
    return (
        f"move one card from deck where card.rank is {lit} "
        f"and card.suit is {suit} to hand[0]"
    )


def test_chooser_is_offered_exactly_the_satisfying_subsets() -> None:
    # Hand: 7♣ 7♦ 7♥ K♠. Same-rank-of-3+ joint pred → the single 7-triple.
    game = check_dsl(
        _setup_game(
            "move chosen some cards from hand[dealer]\n"
            f"            where jointly {SAME_RANK_PRED} to discard",
            "\n    ".join(
                [_place("7", "clubs"), _place("7", "diamonds"),
                 _place("7", "hearts"), _place("K", "spades")]
            ),
        ),
        "t.cardlang",
    )
    seen: list[Any] = []

    def chooser(p: int, cands: list[Any], k: int) -> list[Any]:
        seen.append((p, [tuple(str(c) for c in cand.cards) for cand in cands]))
        return list(cands[:k])

    play_game(game, random.Random(0), chooser=chooser)
    assert len(seen) == 1
    player, cands = seen[0]
    assert player == 0
    assert len(cands) == 1  # exactly the one satisfying subset — the 7-triple
    assert all("7" in c for c in cands[0]) and len(cands[0]) == 3


def test_no_satisfying_subset_is_a_loud_error() -> None:
    game = check_dsl(
        _setup_game(
            "move chosen some cards from hand[dealer]\n"
            f"            where jointly {SAME_RANK_PRED} to discard",
            "\n    ".join([_place("7", "clubs"), _place("K", "spades")]),
        ),
        "t.cardlang",
    )
    with pytest.raises(OwnerGuardError, match="no subset"):
        play_game(game, random.Random(0))


def test_enumeration_bound_is_a_loud_error() -> None:
    game = check_dsl(
        _game(
            "  phase setup { deal 17 cards from deck to hand[0] }\n"
            "  phase p { as dealer { move chosen some cards from hand[dealer]\n"
            f"            where jointly {JOINT_PRED} to discard }} }}"
        ),
        "t.cardlang",
    )
    with pytest.raises(OwnerGuardError, match="enumeration bound"):
        play_game(game, random.Random(0))


def test_exact_count_jointly_offers_only_that_size() -> None:
    # Hand: 7♣ 7♦ 7♥ 7♠. `chosen 3` + same-rank pred → the four 3-subsets,
    # never the 4-subset.
    game = check_dsl(
        _setup_game(
            "move chosen 3 cards from hand[dealer]\n"
            f"            where jointly {SAME_RANK_PRED} to discard",
            "\n    ".join(
                [_place("7", "clubs"), _place("7", "diamonds"),
                 _place("7", "hearts"), _place("7", "spades")]
            ),
        ),
        "t.cardlang",
    )
    seen: list[Any] = []

    def chooser(p: int, cands: list[Any], k: int) -> list[Any]:
        seen.append(list(cands))
        return list(cands[:k])

    play_game(game, random.Random(0), chooser=chooser)
    assert len(seen) == 1
    assert len(seen[0]) == 4 and all(len(c.cards) == 3 for c in seen[0])
    # The enumeration-order pin (a reversed-order mutant passed every other
    # local test): combinations in source order — the subset OMITTING the
    # last-placed card (7♠) first, the one omitting the first (7♣) last.
    suits_per_candidate = [tuple(c.suit for c in cand.cards) for cand in seen[0]]
    assert suits_per_candidate == [
        ("clubs", "diamonds", "hearts"),
        ("clubs", "diamonds", "spades"),
        ("clubs", "hearts", "spades"),
        ("diamonds", "hearts", "spades"),
    ]


def test_fused_amount_typos_are_loud() -> None:
    # The anchored amount keywords: unanchored, `onecards`/`allcards` would
    # split as `one cards` / `all cards` (a real second parse — the expr
    # alternative makes the amount position genuinely ambiguous for unanchored
    # keywords) and compile clean. Anchored they fail loudly — `onecards` reparses
    # as amount-expr `chosen` + item `onecards` and dies in resolve;
    # `allcards` is a plain syntax error. Loud in SOME located channel is
    # the property; the split parse is the defect.
    with pytest.raises(DiagnosticError):
        check_dsl(
            _game("  phase p { move chosen onecards from hand[0] to discard }"),
            "t.cardlang",
        )
    with pytest.raises(DiagnosticError, match="syntax"):
        check_dsl(
            _game("  phase p { move allcards from deck to discard }"),
            "t.cardlang",
        )


def test_jointly_with_to_each_is_rejected() -> None:
    # `to each` would make every destination seat its own subset decider over
    # the shrinking pool — guarded until a game wants that shape.
    with pytest.raises(DiagnosticError) as e:
        check_dsl(
            _game(
                "  phase p { move chosen some cards from discard\n"
                f"            where jointly {JOINT_PRED} to each hand }}"
            ),
            "t.cardlang",
        )
    assert "to each" in e.value.diagnostic.message


def test_negative_and_zero_amounts_are_loud() -> None:
    # The amount-expression domain guard: a negative amount would silently
    # slice from the wrong end (`deal -2` would move 50 of 52 cards); a
    # zero `chosen` is a vacuous decision node.
    game = check_dsl(
        _game("  phase p { deal (0 - 2) cards from deck to discard }"),
        "t.cardlang",
    )
    with pytest.raises(OwnerGuardError, match="negative"):
        play_game(game, random.Random(0))

    game = check_dsl(
        _game(
            "  phase setup { deal 3 cards from deck to hand[0] }\n"
            "  phase p { as dealer { move chosen (1 - 1) cards from hand[dealer] to discard } }"
        ),
        "t.cardlang",
    )
    with pytest.raises(OwnerGuardError, match="0"):
        play_game(game, random.Random(0))


def test_empty_pool_all_jointly_is_loud_like_some() -> None:
    # Left unwalled, `all` over an empty pool would mint one empty-subset
    # "decision"; subset sizes are >= 1, so it falls to the loud no-subset
    # error.
    game = check_dsl(
        _game(
            "  phase p { as dealer { move chosen all cards from hand[dealer]\n"
            "            where jointly (number of cards in cards) >= 0 to discard } }"
        ),
        "t.cardlang",
    )
    with pytest.raises(OwnerGuardError, match="no subset"):
        play_game(game, random.Random(0))


def test_deckcheck_credits_a_some_return_as_one_card_not_a_refill() -> None:
    # A joint `some` return to the deck puts back AT LEAST one card, never
    # the pack — a full-refill credit would statically accept a program that
    # dies mid-deal (`deal 14` from a 13-card stock).
    dsl = _game(
        "  phase p {\n"
        "    deal 36 cards from deck to discard\n"
        "    deal 4 cards from deck to hand[0]\n"
        "    as dealer { move chosen some cards from hand[dealer]\n"
        f"            where jointly {JOINT_PRED} to deck }}\n"
        "    deal 14 cards from deck to discard\n"
        "  }"
    )
    with pytest.raises(DiagnosticError) as e:
        check_dsl(dsl, "t.cardlang")
    assert "deck" in e.value.diagnostic.message.lower()


def test_joint_flag_survives_into_the_ir() -> None:
    # If the movement emitter dropped `joint`, a subset decision binding
    # `cards` would be IR-indistinguishable from a per-card filter binding
    # `card`. A mechanical sweep confirmed `joint` was the only dropped field
    # across the Stmt union; this pins that cell.
    from cardlang.ir import emit

    game = check_dsl(
        _game(
            "  phase p { as dealer {\n"
            "    move chosen some cards from hand[dealer]\n"
            f"         where jointly {JOINT_PRED} to discard\n"
            "    move chosen one card from hand[dealer]\n"
            "         where card.suit is hearts to discard\n"
            "  } }"
        ),
        "t.cardlang",
    )
    ir = emit(game)

    def movements(node: Any) -> list[dict[str, Any]]:
        found: list[dict[str, Any]] = []
        if isinstance(node, dict):
            if node.get("kind") == "transfer":
                found.append(node)
            for v in node.values():
                found.extend(movements(v))
        elif isinstance(node, list):
            for v in node:
                found.extend(movements(v))
        return found

    filtered = [m for m in movements(ir) if "where" in m]
    assert len(filtered) == 2
    joint_flags = sorted(m.get("joint", False) for m in filtered)
    assert joint_flags == [False, True]  # the per-card one carries no flag


def test_action_space_walls_an_unregistered_joint_predicate() -> None:
    # The OpenSpiel action space needs the joint predicate's subset universe
    # (a registered codec, the climb-engine pattern). An inline predicate has
    # none — the guard must be loud, never a silently absent combo block.
    from cardlang.openspiel.encoding import ActionSpace

    game = check_dsl(
        _game(
            "  phase p { as dealer { move chosen some cards from hand[dealer]\n"
            f"            where jointly {JOINT_PRED} to discard }} }}"
        ),
        "t.cardlang",
    )
    with pytest.raises(NotImplementedError, match="jointly"):
        ActionSpace.for_game(game)


def test_action_space_walls_a_climb_plus_joint_game() -> None:
    # The combo block serves ONE subset universe: a game with both a climb
    # round and a joint selection needs a composed block no game has forced.
    from cardlang.openspiel.encoding import ActionSpace

    dsl = (
        "game G {\n"
        "  players: 3\n"
        "  max_length: 1000\n"
        "  cards: standard52\n"
        "  ranking: A K Q J 10 9 8 7 6 5 4 3 2\n"
        "  primitives { gin_valid_meld(cards : Collection<Card>) : Boolean }\n"
        "  zones { deck : Deck  hand[player] : Hand<player>\n"
        "          trick_pile : TrickPile  discard : Discard }\n"
        "  state { dealer : Player = 0  score[player] : Integer = 0 }\n"
        "  winner: highest score\n"
        "  phase p {\n"
        "    round climb play_combination from 0 over all players\n"
        "          source hand into trick_pile\n"
        "          combinations president_lead_options follows president_follows\n"
        "          until false\n"
        "    as dealer { move chosen some cards from hand[dealer]\n"
        "            where jointly gin_valid_meld(cards) to discard }\n"
        "  }\n"
        "}\n"
        "move_type play_combination { effect { } }\n"
    )
    game = check_dsl(dsl, "t.cardlang")
    with pytest.raises(NotImplementedError, match="climb"):
        ActionSpace.for_game(game)


def test_action_space_walls_two_distinct_joint_codecs(monkeypatch: Any) -> None:
    # Two joint predicates whose registered codecs are DIFFERENT objects need
    # a composed combo block — guarded until a game forces the design. The
    # registry is monkeypatched because today's only registered codecs (both
    # gin roots) deliberately share one singleton.
    from cardlang.openspiel.encoding import ActionSpace
    from cardlang.runtime import primitives as runtime_stdlib

    class _StubCodec:
        size = 1

    codecs = {"gin_valid_meld": _StubCodec(), "gin_arrange_ok": _StubCodec()}
    monkeypatch.setattr(
        runtime_stdlib, "joint_codec_function", lambda name: codecs.get(name)
    )
    dsl = _game(
        "  phase p { as dealer {\n"
        "    move chosen some cards from hand[dealer]\n"
        "         where jointly gin_valid_meld(cards) to discard\n"
        "    move chosen some cards from hand[dealer]\n"
        "         where jointly gin_arrange_ok(dealer, cards) to discard\n"
        "  } }",
        block=(
            "  primitives { gin_valid_meld(cards : Collection<Card>) : Boolean\n"
            "               gin_arrange_ok(p : Player, cards : Collection<Card>)"
            " : Boolean reads hand[p], taken[p] }\n"
        ),
    )
    game = check_dsl(dsl, "t.cardlang")
    with pytest.raises(NotImplementedError, match="different subset codecs"):
        ActionSpace.for_game(game)


def test_leading_jointly_identifier_still_lexes_as_a_name() -> None:
    # `jointly_valid` / `some_var` must stay single NAMEs (the `is_re` trap).
    dsl = (
        "game G {\n"
        "  players: 2\n"
        "  max_length: 1000\n"
        "  cards: standard52\n"
        "  ranking: A K Q J 10 9 8 7 6 5 4 3 2\n"
        "  zones { hand[player] : Hand<player> }\n"
        "  state { jointly_valid[player] : Integer = 0  some_var : Integer = 0 }\n"
        "  winner: highest jointly_valid\n"
        "  phase p { jointly_valid[0] := 1\n"
        "            some_var := 2 }\n"
        "}\n"
    )
    check_dsl(dsl, "t.cardlang")
