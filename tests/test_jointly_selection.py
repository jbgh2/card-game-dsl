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
            `selection`, `amount`, `where_clause`); the `Movement` node's
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
              deterministic enumeration order (sizes ascending,
              combinations in source order) [runtime]
            - no satisfying subset → loud RuntimeError (no-implicit-actions)
              [runtime]
            - a source pool above the enumeration bound → loud RuntimeError
              naming the bound [runtime]
sampled:    destination shapes (single zone / `to each`) share the ordinary
            movement path after selection — the joint branch only changes
            WHICH cards are picked, pinned by one single-dest test.
residual:   `jointly` under `random` mode (uniform over satisfying subsets)
            is implementable but has no corpus user — rejected loudly,
            recorded in roadmap.md "Grammar surface deferred by the
            checker" alongside `some` without `jointly`.
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


def _game(body: str) -> str:
    return (
        "game G {\n"
        "  players: 2\n"
        "  max_length: 1000\n"
        "  cards: standard52\n"
        "  ranking: A K Q J 10 9 8 7 6 5 4 3 2\n"
        "  zones { deck : Deck  hand[player] : Hand<player>\n"
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
    mv = [nd for nd in _walk(game) if isinstance(nd, n.Movement)][0]
    assert mv.joint is True
    assert mv.amount == "some"
    assert mv.mode == "chosen"


def test_plain_where_stays_per_card() -> None:
    game = parse_text(
        _game(
            "  phase p { as dealer { move chosen one card from hand[dealer]\n"
            "            where card.suit is hearts to discard } }"
        ),
        "t.cardlang",
    )
    mv = [nd for nd in _walk(game) if isinstance(nd, n.Movement)][0]
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
    with pytest.raises(RuntimeError, match="no subset"):
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
    with pytest.raises(RuntimeError, match="enumeration bound"):
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


def test_action_space_walls_an_unregistered_joint_predicate() -> None:
    # The OpenSpiel action space needs the joint predicate's subset universe
    # (a registered codec, the climb-engine pattern). An inline predicate has
    # none — the wall must be loud, never a silently absent combo block.
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


def test_leading_jointly_identifier_still_lexes_as_a_name() -> None:
    # `jointly_valid` / `some_var` must stay single NAMEs (the `is_re` trap).
    dsl = (
        "game G {\n"
        "  players: 2\n"
        "  max_length: 1000\n"
        "  cards: standard52\n"
        "  ranking: A K Q J 10 9 8 7 6 5 4 3 2\n"
        "  zones { hand[player] : Hand<player> }\n"
        "  state { jointly_valid : Integer = 0  some_var : Integer = 0 }\n"
        "  winner: highest jointly_valid\n"
        "  phase p { jointly_valid := 1\n"
        "            some_var := 2 }\n"
        "}\n"
    )
    check_dsl(dsl, "t.cardlang")
