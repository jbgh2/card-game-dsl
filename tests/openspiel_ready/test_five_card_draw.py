"""Heads-up fixed-limit Five-Card Draw — OpenSpiel readiness.

Hidden zone `hole`: the five private cards, as in both Hold'em variants and
Stud. `discards` is hidden too and holds nothing to perturb at the depth
below — the greedy line stands pat, which is also why the exchange gets the
dedicated test at the foot of this module.

`swap_axis="any"`: the line this proof replays contains no card-naming
action. That is a claim about the LINE, not about the action space — `toss`
is a `move chosen one card`, so a tossed card's own action id names it, and a
swapped world would not replay a recorded toss. The greedy `legal[0]` line
never tosses: at the exchange it is offered `[stand, toss]` and `stand` sorts
first, so the whole line is `check, check, stand, stand, check, check` on
every manifest seed. Two-card-suit filtering would starve a five-card hole
pool as it does the siblings', which is the other half of why the axis is
`any` rather than the default.

`depth=4`. The 2-player swap branch pauses on the FIRST decider, so the depth
must land on a P0 decision; P0 decides at 0, 2 and 4 on the greedy line. 4 is
the deepest and the strongest: the exchange is complete, so the swap is
checked at a pause where the draw phase has run and 42 cards still sit
undealt in the deck to pair the opponent's five hole cards against. Both
seats stood pat to reach it — greedy takes `stand` — so the swap says nothing
about a hole that was exchanged, which `test_the_draw_count_is_public_and_the
_discards_are_not` covers instead.

`adapter_terminal_steps=12`: the greedy line reaches TerminalNode in 6 steps
on every seed of the manifest (measured; the line is seed-independent because
neither `check` nor `stand` consults a card), so 12 carries a 6-step margin.

`conformance_steps` is deliberately UNSET, so this game plays a full
`pyspiel.random_sim_test`. The sim re-simulates the whole (seed, history)
state after every action, which is O(n^2) in game length (issue #139) — but
this is ONE hand of at most a few dozen decisions, so the same sim that Stud
and three-handed Hold'em must bound is affordable here and the game gets the
stronger check rather than a budget with a coverage claim attached. No
`conformance_verbs_unreached` follows from that: the complement pin is only
meaningful with a bound.
"""

from typing import Any

from cardlang.openspiel.infostate import information_state
from cardlang.openspiel.replay import DecisionNode, load, run

from .harness import GAMES_DIR, GameSpec, ReadinessProofs

PATH = str(GAMES_DIR / "five-card-draw.cardlang")


class TestReadiness(ReadinessProofs):
    spec = GameSpec(
        "cardlang_five_card_draw",
        "five-card-draw.cardlang",
        hidden_zone="hole",
        depth=4,
        swap_axis="any",
        adapter_terminal_steps=12,
    )


def _drive(seed: int, script: list[str]) -> DecisionNode:
    """Replay a named line, `*` taking the lowest-encoded card of a card
    decision. A `toss` is two decisions — the move type, then the card it
    names — so a script that tosses interleaves the two."""
    _, space = load(PATH)
    history: list[int] = []
    for want in script:
        r = run(PATH, seed, tuple(history))
        assert isinstance(r, DecisionNode), f"the hand ended before `{want}`"
        names = [space.to_string(a) for a in r.legal]
        history.append(r.legal[0] if want == "*" else r.legal[names.index(want)])
    r = run(PATH, seed, tuple(history))
    assert isinstance(r, DecisionNode), "the hand ended before the post-draw pause"
    return r


def test_the_draw_count_is_public_and_the_discards_are_not() -> None:
    """The game's whole strategic content, and the one thing no harness proof
    reaches: greedy stands pat, so every proof above runs at a pause where no
    card was exchanged.

    What an opponent learns from an exchange is exactly one number. Each
    `toss` reaches a non-owner as a count-only movement into a
    `HiddenPile<player>` — no card name on either side of it — and the
    replacements come off the `Deck`, count-only to all, as a single movement
    of that many unnamed cards. The owner's own log carries every identity,
    which is not a leak. Nobody wrote an observation rule for any of it; it
    falls out of the two zone types.
    """
    r = _drive(3, ["check", "check", "toss", "*", "toss", "*", "toss", "*", "stand", "stand"])

    owner, opponent = 0, 1
    assert len(r.rs.zones.instance("discards", owner).cards) == 3
    assert not r.rs.zones.instance("discards", opponent).cards

    def moves(log: list[tuple[Any, ...]], src: str, dst: str) -> list[tuple[Any, ...]]:
        return [e for e in log if e[0] == "move" and e[1] == src and e[3] == dst]

    tosses = moves(r.obs_logs[opponent], f"hole[{owner}]", f"discards[{owner}]")
    assert len(tosses) == 3, f"the opponent must see three cards leave: {tosses}"
    for e in tosses:
        assert e[2] == 1 and e[4] == 1, (
            f"a tossed card's identity leaked to the opponent on either side "
            f"of the movement: {e}"
        )

    draws = [e for e in moves(r.obs_logs[opponent], "deck", f"hole[{owner}]") if e[2] == 3]
    assert draws == [("move", "deck", 3, f"hole[{owner}]", 3)], (
        f"the opponent must see three unnamed cards replace them: {draws}"
    )

    # The owner's own view of the same three events carries every identity on
    # both sides, and the cards it names are exactly the ones now in the pile.
    own = moves(r.obs_logs[owner], f"hole[{owner}]", f"discards[{owner}]")
    assert len(own) == 3, own
    for e in own:
        assert e[2] == e[4] and isinstance(e[4], tuple) and len(e[4]) == 1, e
    assert {e[4][0] for e in own} == {
        str(c) for c in r.rs.zones.instance("discards", owner).cards
    }

    # And the count, not the cards, is what the opponent's information state
    # renders: the `HiddenPile<player>` projection stated as a string.
    assert f"discards[{owner}]=#3" in information_state(
        opponent, r.rs, r.obs_logs[opponent]
    )
    assert f"discards[{owner}]=[" in information_state(owner, r.rs, r.obs_logs[owner])


def test_a_standing_pat_seat_is_indistinguishable_from_one_that_drew_nothing() -> None:
    """The converse of the count being public: zero is a count too. A seat
    that stands pat moves no card, so the opponent's log carries no exchange
    event at all for it and its `discards` render empty rather than hidden —
    which is what makes "he stood pat" readable at the table.
    """
    r = _drive(3, ["check", "check", "stand", "stand"])
    for observer in (0, 1):
        log = r.obs_logs[observer]
        assert not [
            e for e in log if e[0] == "move" and str(e[3]).startswith("discards[")
        ], f"P{observer} observed an exchange on a line where nobody tossed"
        state = information_state(observer, r.rs, log)
        assert "discards[0]=[]" in state or "discards[0]=#0" in state, state
