"""The observer channel and zone-type retention (SP1 spec, Pillar 1)."""

from __future__ import annotations

import random
from typing import Any

from cardlang.ast import nodes as n
from cardlang.runtime.state import Ctx, RuntimeState, ZoneStore
from cardlang.runtime.values import Seating


def _store() -> ZoneStore:
    decls = (
        n.ZoneDecl(name="deck", index=None, type_ref=n.TypeRef(name="Deck")),
        n.ZoneDecl(name="hand", index="player", type_ref=n.TypeRef(name="Hand")),
        n.ZoneDecl(name="captured", index="team", type_ref=n.TypeRef(name="TeamPile")),
    )
    return ZoneStore(decls, players=(0, 1, 2, 3), teams=(0, 1))


def test_zone_store_retains_declared_types_and_index() -> None:
    zs = _store()
    assert zs.zone_type == {"deck": "Deck", "hand": "Hand", "captured": "TeamPile"}
    assert zs.zone_index == {"deck": None, "hand": "player", "captured": "team"}


def test_locate_finds_singles_and_family_instances() -> None:
    zs = _store()
    assert zs.locate(zs.single("deck")) == ("deck", None)
    assert zs.locate(zs.instance("hand", 2)) == ("hand", 2)
    assert zs.locate(zs.instance("captured", 1)) == ("captured", 1)


def test_ctx_observer_defaults_to_none_and_observe_is_noop() -> None:
    rs = RuntimeState(Seating(4), _store(), random.Random(0))
    ctx = Ctx(rs=rs, chooser=lambda p, c, k: list(c)[:k])
    ctx.observe(0, ("announce", 1, "pass"))  # must not raise


def test_ctx_observe_delivers_to_installed_observer() -> None:
    rs = RuntimeState(Seating(4), _store(), random.Random(0))
    seen: list[tuple[int, tuple[Any, ...]]] = []
    ctx = Ctx(
        rs=rs,
        chooser=lambda p, c, k: list(c)[:k],
        observer=lambda pl, ev: seen.append((pl, ev)),
    )
    ctx.observe(2, ("chose", "Q spades"))
    assert seen == [(2, ("chose", "Q spades"))]


# Task 3: Observation emitter tests

from cardlang.runtime import observe
from cardlang.runtime.values import Card


def _ctx_with_log() -> tuple[Ctx, dict[int, list[tuple[Any, ...]]]]:
    rs = RuntimeState(Seating(4), _store(), random.Random(0))
    rs.team_of = {0: 0, 1: 1, 2: 0, 3: 1}
    logs: dict[int, list[tuple[Any, ...]]] = {p: [] for p in range(4)}
    ctx = Ctx(
        rs=rs,
        chooser=lambda p, c, k: list(c)[:k],
        observer=lambda pl, ev: logs[pl].append(ev),
    )
    return ctx, logs


def test_render_shapes() -> None:
    assert observe.render(Card("Q", "spades")) == str(Card("Q", "spades"))
    assert observe.render(("bid", None)) == "bid"
    assert observe.render(("bid", "hearts")) == "bid(hearts)"
    assert observe.render(7) == 7
    assert observe.render("pass") == "pass"
    two = [Card("2", "clubs"), Card("A", "spades")]
    assert observe.render(two) == tuple(sorted(str(c) for c in two))


def test_choice_reaches_only_the_actor() -> None:
    ctx, logs = _ctx_with_log()
    observe.choice(ctx, 2, Card("Q", "spades"))
    assert logs[2] == [("chose", str(Card("Q", "spades")))]
    assert logs[0] == logs[1] == logs[3] == []


def test_announce_reaches_everyone() -> None:
    ctx, logs = _ctx_with_log()
    observe.announce(ctx, 1, ("bid", 3))
    for p in range(4):
        assert logs[p] == [("announce", 1, "bid(3)")]


def test_movement_projects_per_observer() -> None:
    ctx, logs = _ctx_with_log()
    cards = [Card("2", "clubs"), Card("9", "hearts")]
    # deck (count_only to all) -> hand[1] (identity to owner, count to others)
    observe.movement(ctx, ("deck", None), ("hand", 1), cards)
    ident = tuple(sorted(str(c) for c in cards))
    assert logs[1] == [("move", "deck", 2, "hand[1]", ident)]
    for p in (0, 2, 3):
        assert logs[p] == [("move", "deck", 2, "hand[1]", 2)]


def test_movement_identity_zone_is_public() -> None:
    ctx, logs = _ctx_with_log()
    card = [Card("Q", "spades")]
    # hand[0] -> captured[1] (TeamPile: identity to all)
    observe.movement(ctx, ("hand", 0), ("captured", 1), card)
    ident = (str(Card("Q", "spades")),)
    assert logs[0] == [("move", "hand[0]", ident, "captured[1]", ident)]
    for p in (1, 2, 3):
        assert logs[p] == [("move", "hand[0]", 1, "captured[1]", ident)]


def test_team_owner_resolution() -> None:
    ctx, _ = _ctx_with_log()
    # captured is team-indexed; player 2 is on team 0.
    assert observe.view_of(ctx.rs, "captured", 0, 2, [Card("2", "clubs")]) == (
        str(Card("2", "clubs")),
    )


def test_render_refuses_undeclared_decision_value_shapes() -> None:
    """Closed-domain completeness: a decision value outside the declared
    shapes (Card, multi-card list, (move, param) candidate, .cards combo,
    int/bool, str, None) must fail loudly, never pass through verbatim."""
    import pytest

    from cardlang.runtime.observe import render

    assert render(7) == 7
    assert render("pass") == "pass"
    assert render(None) is None

    class Alien:
        pass

    with pytest.raises(AssertionError, match="no declared rendering"):
        render(Alien())
    with pytest.raises(AssertionError, match="no declared rendering"):
        render((1, 2, 3))  # a tuple that is not a (move_type, param) candidate


def test_every_emitted_event_type_is_registered() -> None:
    """Closed-domain completeness: sweep real observation logs across games
    with distinct emission profiles (trick play, rank-probing transfers,
    challenge windows + reveals) and assert every event tag is in the
    declared EVENT_TYPES vocabulary — a typo at an emission site cannot
    silently mint a new event kind."""
    from pathlib import Path as _Path

    from cardlang.openspiel.replay import Pause, run
    from cardlang.runtime.observe import EVENT_TYPES

    games_dir = _Path(__file__).parent.parent / "docs" / "games"
    seen: set[str] = set()
    for fname, depth in (("hearts.cardlang", 12), ("go-fish.cardlang", 10), ("coup.cardlang", 14)):
        path = str(games_dir / fname)
        history: list[int] = []
        r = run(path, 5, ())
        for _ in range(depth):
            assert isinstance(r, Pause)
            for log in r.obs_logs.values():
                for event in log:
                    assert event[0] in EVENT_TYPES, (
                        f"{fname}: unregistered event type {event[0]!r} — "
                        f"declare it in observe.EVENT_TYPES deliberately"
                    )
                    seen.add(str(event[0]))
            history.append(r.legal[0])
            r = run(path, 5, tuple(history))
    # the sweep must exercise the vocabulary, not pass vacuously
    assert seen == set(EVENT_TYPES) - {"reveal"} or seen == set(EVENT_TYPES), (
        f"sweep exercised only {sorted(seen)} — extend the game/depth list"
    )
