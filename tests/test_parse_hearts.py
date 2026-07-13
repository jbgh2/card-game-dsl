"""The formalized Hearts parses into a complete typed AST.

This is the first real corpus game flowing through the typed pipeline (not
just grammar acceptance). It exercises the whole node set — header blocks,
nested phases, the statement vocabulary, rules, and the expression
sublanguage — so a transform gap anywhere surfaces here.
"""

from __future__ import annotations

from pathlib import Path

from cardlang.ast import nodes as n
from cardlang.parse import parse_text

HEARTS = Path(__file__).parent.parent / "docs" / "games" / "hearts.cardlang"


def _game() -> n.Game:
    return parse_text(HEARTS.read_text(), str(HEARTS))


def _phase(parent: n.Phase | n.Game, name: str) -> n.Phase:
    phases = parent.phases if isinstance(parent, n.Game) else [
        i for i in parent.items if isinstance(i, n.Phase)
    ]
    return next(p for p in phases if p.name == name)


def test_header_blocks() -> None:
    g = _game()
    assert g.name == "Hearts"
    assert g.players == n.PlayersSpec(low=4, high=None, span=g.players.span)
    assert g.deck == "standard52"
    assert g.direction == "clockwise"
    assert g.ranking[0] == "A" and g.ranking[-1] == "2" and len(g.ranking) == 13
    assert [z.name for z in g.zones] == ["deck", "hand", "trick_pile", "captured"]
    assert g.state is not None and g.state.decls[0].name == "cumulative_score"
    assert g.winner is not None
    assert (g.winner.rank_dir, g.winner.target) == ("lowest", "cumulative_score")
    # The file defines only the Hearts-specific rules; MustFollowSuit and
    # NoLeadingSuitUntilBroken(hearts) splice in from the standard library at
    # resolve time (see test_demands_two_forms).
    assert {r.name for r in g.rules} == {
        "MustLeadTwoOfClubsOnFirstPlay",
        "NoPenaltyCardsOnFirstTrick",
        "PassExactlyThreeCards",
    }


def test_phase_tree_and_qualifier() -> None:
    g = _game()
    hand_seq = _phase(g, "hand_sequence")
    assert hand_seq.qualifier is not None and hand_seq.qualifier.kind == "repeats"
    nested = [i.name for i in hand_seq.items if isinstance(i, n.Phase)]
    assert nested == ["passing", "first_trick", "play", "scoring"]
    # setup is now a before_each lifecycle hook, not a sub-phase.
    assert any(isinstance(i, n.BeforeEach) for i in hand_seq.items)


def test_transition_predicate_binds_action() -> None:
    g = _game()
    play = _phase(_phase(g, "hand_sequence"), "play")
    not_broken = _phase(play, "hearts_not_broken")
    trans = next(i for i in not_broken.items if isinstance(i, n.TransitionTo))
    assert trans.target == "hearts_broken"
    assert trans.event.move_type == "play_to_trick"
    # where action.card.suit == hearts  ->  BinOp(==, Member(Member(action,card),suit), hearts)
    pred = trans.event.where
    assert isinstance(pred, n.BinOp) and pred.op == "=="
    assert isinstance(pred.left, n.Member) and pred.left.field == "suit"
    assert isinstance(pred.left.obj, n.Member) and pred.left.obj.field == "card"
    assert isinstance(pred.left.obj.obj, n.NameRef) and pred.left.obj.obj.name == "action"


def test_demands_two_forms() -> None:
    # MustFollowSuit is a library rule, present only after resolve splices it.
    from cardlang.resolve import resolve

    g = resolve(_game())
    rules = {r.name: r for r in g.rules}

    pass_three = rules["PassExactlyThreeCards"]
    assert pass_three.constrains == "transfer_between_hands"
    assert pass_three.demands is not None and pass_three.demands.kind == "actions"

    follow = rules["MustFollowSuit"]
    assert follow.demands is not None and follow.demands.kind == "cards"
    assert follow.applies_when is not None and not follow.applies_when.always


def test_scoring_comprehension_and_movement() -> None:
    g = _game()
    scoring = _phase(_phase(g, "hand_sequence"), "scoring")
    lets = [i for i in scoring.items if isinstance(i, n.LetStmt)]
    base = next(l for l in lets if l.name == "base")
    assert isinstance(base.value, n.Comprehension)
    assert base.value.agg == "sum" and base.value.binder == "card"

    # setup statements now live in the before_each lifecycle hook.
    hand_seq = _phase(g, "hand_sequence")
    before = next(i for i in hand_seq.items if isinstance(i, n.BeforeEach))
    movements = [s for s in before.body if isinstance(s, n.Movement)]
    gather = next(m for m in movements if m.source is None)
    assert gather.verb == "move" and gather.amount == "all"  # `move all cards to deck`
    deal = next(m for m in movements if m.verb == "deal")
    assert deal.item == "cards" and deal.dest_each
    shuffle = next(s for s in before.body if isinstance(s, n.EpistemicOp))
    assert shuffle.op == "shuffle"
