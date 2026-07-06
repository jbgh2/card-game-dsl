"""The OpenSpiel-readiness proof, per fully-kernel game (SP1 spec, "The proof"):

1. pyspiel API conformance (random_sim_test, or a bounded random API walk for
   games whose full sim is prohibitively long — see CONFORMANCE_STEPS).
2. INDISTINGUISHABILITY: two worlds differing only in cards hidden from P
   yield byte-identical information states for P (the leak-closure proof).
3. Soundness converse: perturbing what P CAN see changes P's state.
4. Perfect recall: each player's observation log is append-only along a game.
"""

from __future__ import annotations

import random
from pathlib import Path
from typing import Any

import pytest

pyspiel = pytest.importorskip("pyspiel")

import cardlang.openspiel.game as ogame  # noqa: E402  (registers on import)
from cardlang.openspiel.infostate import information_state  # noqa: E402
from cardlang.openspiel.replay import Pause, load, run  # noqa: E402

GAMES_DIR = Path(__file__).resolve().parent.parent / "docs" / "games"
KERNEL_GAMES = sorted(ogame.GAMES.items())  # (short_name, filename), deterministic order

# The zone family hiding each player's cards — what the swap tests perturb.
# Stud's hidden cards live in `hole` (its `upcards` are public); everyone else
# hides a `hand`.
HIDDEN_ZONE = {"cardlang_seven_card_stud": "hole"}


def _hidden(short_name: str) -> str:
    return HIDDEN_ZONE.get(short_name, "hand")

# Steps to replay before the indistinguishability check. Deep enough that real
# decisions and movements happened; shallow enough that opponents still hold
# swappable cards. Getaway/Big Two shed cards fast, hence the smaller L.
# Bridge redeals the hand outright on a 4-pass "passed out" auction (real
# rule), and this harness's greedy `_advance` (always `legal[0]`) always picks
# "pass" first, so any depth >= 4 crosses into a *second* deal — a fresh
# shuffle unrelated to the hands `on_first_decision` mutates (that hook always
# fires at the game's very first-ever decision, i.e. deal #1). At depth >= 4
# the swap was confirmed (field-by-field diff, see task-10 report) to change
# ONLY P0's own re-shuffled `hand[0]` — hidden hands stayed `#13` in both
# worlds and no opponent card identity appeared in the obs log — i.e. an
# ill-posed experiment (mutated hands != examined hands), not a leak. Depth 3
# stays inside deal #1, where the mutated hands and the examined hands
# coincide, so the property is checked in the pre-play auction phase (this
# seed's greedy policy never reaches trick play for bridge).
#
# French Tarot hits the exact same case, deterministically rather than just
# under this seed's policy: `pass` (action id 78) sorts below every bid
# (79-82), so greedy `legal[0]` always passes, and its four-seat auction
# ALWAYS throws the hand in at exactly 4 actions (re-dealing before-each next
# hand) — confirmed directly (a field-by-field info-state diff at depth 12
# showed the SAME shape as Bridge's: only the later re-dealt hands moved, via
# the gather-then-shuffle the thrown-in hand's `before_each` runs). Depth 3
# stays inside the still-open first auction, before that reshuffle.
DEPTH = {
    "cardlang_getaway": 8,
    "cardlang_big_two": 6,
    "cardlang_bridge": 3,
    "cardlang_french_tarot": 3,
    # Cribbage (2 players): the deepest pause <= DEFAULT_DEPTH whose pauser is
    # player 0 (probed at seed 5) — player 0 discards first (seat-order
    # for-each) and always leads pegging as the non-dealer (`dealer: Player =
    # 0` flips to 1 in the first before_each), so depth 4 (both players' two
    # discard picks each, decomposed to 4 sequential actions) is exactly
    # player 0's first pegging draw. With only 2 players, the swappable
    # opponent is necessarily the same seat throughout, so the pause must
    # coincide with the first decider (`p == d0`, seat 0 discards first too) —
    # true here, and true at every deeper p0 pause this seed reaches.
    "cardlang_cribbage": 4,
    # Schnapsen (2 players): greedy `legal[0]` always leads the lowest card id,
    # and at seed 5 the even depths pause on player 0 — the first decider, as
    # the 2-player branch requires (p == d0). Depth 6 is three completed tricks
    # (real leads, follows, and talon draws happened) while the talon still
    # holds 3 hidden cards to pair the swap against; by depth 10 it is empty.
    "cardlang_schnapsen": 6,
}
DEFAULT_DEPTH = 12

# 2-player games only: the hidden un-dealt stock the swap pairs the opponent's
# hand against. The default is the `deck`; Schnapsen empties its deck into the
# `talon` before the first decision (the stock it draws from), so its hidden
# pool lives there — the deck itself is empty at every pause.
STOCK_ZONE = {"cardlang_schnapsen": "talon"}

# 2-player games only (see the indistinguishability test's `else` branch): how
# many leading stock cards to exclude from the swap pool. For Cribbage this is
# defensive/redundant at the current DEPTH=4 pause: the pool is sourced from the
# paused (post-cut) deck, where the starter already sits in the `starter` zone and
# `deck[0]` is an ordinary card, so the swap cannot touch the starter regardless.
# (The starter stays identical across both swap worlds structurally — the cut deals
# off the deck head while a swapped card is appended to the tail.) Kept at 1 so a
# shallower, pre-cut pause could not swap the imminent public starter.
DECK_SWAP_SKIP = {"cardlang_cribbage": 1}

# Full `pyspiel.random_sim_test` re-simulates the whole (seed, history) state
# after every action — O(n^2) in game length — and a Stud game runs until one
# player holds all 400 chips: ~486 hands x ~21 decisions ~ 10k actions, which
# extrapolates to a ~15-minute median full sim. Games in this map instead get
# a bounded random API walk (the sanctioned SP1 bridge-fallback precedent):
# CONFORMANCE_STEPS random legal actions checking current_player/legal-actions
# consistency, info-state string non-crash, chance-node handling, and terminal
# handling if reached. The other games keep the full random_sim_test.
# French Tarot's 36 hands x ~76 decision-picks/hand (~2,740 total) measured at
# 436s for the full sim (O(n^2) re-simulation) — far past the ~60s keep-it
# threshold, so it gets the same bounded-walk treatment as Stud.
# Tichu runs to 1000 points (~15-25 hands x ~100-200 climb decisions plus the
# 12-pick push), thousands of actions — the same O(n^2) wall as Stud/Tarot.
CONFORMANCE_STEPS = {
    "cardlang_seven_card_stud": 120,
    "cardlang_french_tarot": 120,
    "cardlang_tichu": 120,
}


@pytest.mark.parametrize(("short_name", "filename"), KERNEL_GAMES)
def test_pyspiel_conformance(short_name: str, filename: str) -> None:
    game = pyspiel.load_game(short_name)
    steps = CONFORMANCE_STEPS.get(short_name)
    if steps is None:
        pyspiel.random_sim_test(game, num_sims=1, serialize=False, verbose=False)
        return
    rng = random.Random(7)
    state = game.new_initial_state()
    for _ in range(steps):
        if state.is_terminal():
            assert len(state.returns()) == game.num_players()
            break
        if state.is_chance_node():
            outcomes = state.chance_outcomes()
            assert abs(sum(p for _, p in outcomes) - 1.0) < 1e-9
            action = rng.choice([a for a, _ in outcomes])
        else:
            player = state.current_player()
            assert 0 <= player < game.num_players()
            legal = state.legal_actions(player)
            assert legal, "a decision node must offer at least one action"
            assert legal == sorted(set(legal)), "legal actions must be sorted, unique"
            assert all(0 <= a < game.num_distinct_actions() for a in legal)
            assert state.information_state_string(player)  # derives, non-crash
            action = rng.choice(legal)
        state.apply_action(action)


def _advance(path: str, seed: int, depth: int) -> tuple[list[int], Pause]:
    history: list[int] = []
    r = run(path, seed, ())
    assert isinstance(r, Pause)
    while len(history) < depth:
        history.append(r.legal[0])
        nxt = run(path, seed, tuple(history))
        if not isinstance(nxt, Pause):  # short game: back off one step
            history.pop()
            break
        r = nxt
    return history, r


def _side_zone(rs: Any, side: tuple[str, "int | None"]) -> Any:
    """A swap side: a (family, key) pair (a per-player zone) or (name, None)
    (a single zone, e.g. Cribbage's `deck` — the other side of a 2-player
    swap when there is no second opponent hand to pair against)."""
    name, key = side
    return rs.zones.single(name) if key is None else rs.zones.instance(name, key)


def _swap_fn(side1: tuple[str, "int | None"], side2: tuple[str, "int | None"], x: Any, y: Any) -> Any:
    def swap(rs: Any) -> None:
        h1, h2 = _side_zone(rs, side1), _side_zone(rs, side2)
        h1.remove(x)
        h2.remove(y)
        h1.add(y)
        h2.add(x)

    return swap


def _swap_pairs(short_name: str, hand1: list[Any], hand2: list[Any]) -> list[Any]:
    """Swappable hidden-card pairs. Games whose recorded actions are cards (or
    card combos) need same-suit swaps so every recorded action stays legal in
    the swapped world; Stud's recorded actions are betting vocabulary — none
    names a card — so ANY hole swap replays legally (and its two-card holes
    rarely share a suit, so a same-suit filter would starve the pool)."""
    if short_name == "cardlang_seven_card_stud":
        return [(x, y) for x in hand1 for y in hand2 if x != y]
    three_d = ("3", "diamonds")
    return [
        (x, y)
        for x in hand1
        for y in hand2
        if x.suit == y.suit
        and x != y
        # keep the 3♦ fixed: Big Two's opening filter keys on that exact card
        and (x.rank, x.suit) != three_d
        and (y.rank, y.suit) != three_d
    ]


@pytest.mark.parametrize(("short_name", "filename"), KERNEL_GAMES)
def test_indistinguishability_under_hidden_swap(short_name: str, filename: str) -> None:
    path = str(GAMES_DIR / filename)
    seed = 5
    depth = DEPTH.get(short_name, DEFAULT_DEPTH)
    hz = _hidden(short_name)
    history, pause_a = _advance(path, seed, depth)
    p = pause_a.player
    first = run(path, seed, ())
    assert isinstance(first, Pause)
    d0 = first.player  # the swap must not touch the first decider (stale candidates)

    others = [q for q in range(len(pause_a.obs_logs)) if q not in (p, d0)]
    if len(others) >= 2:
        opp1, opp2 = others[0], others[1]
        # Skip pairs the replay rejects (a rule keyed on the specific card).
        hand1 = pause_a.rs.zones.instance(hz, opp1).cards
        hand2 = pause_a.rs.zones.instance(hz, opp2).cards
        candidates = _swap_pairs(short_name, hand1, hand2)
        side1: tuple[str, "int | None"] = (hz, opp1)
        side2: tuple[str, "int | None"] = (hz, opp2)
        who = f"players {opp1},{opp2}"
    else:
        # 2-player games: there is only ever one opponent, so the harness
        # swaps between that opponent's hand and the un-dealt deck instead —
        # both hidden from P throughout the replayed prefix. This only works
        # when the pause coincides with the first decider (`p == d0`), so the
        # swap (fired at the very first decision) never mutates a decider
        # whose candidates were already computed from the un-swapped world.
        assert p == d0, (
            f"{short_name}: with 2 players the harness needs the DEPTH pause "
            f"to coincide with the first decider (p == d0) — adjust DEPTH"
        )
        assert len(others) == 1, f"{short_name}: expected exactly one other player"
        opp = others[0]
        hand = pause_a.rs.zones.instance(hz, opp).cards
        stock = STOCK_ZONE.get(short_name, "deck")
        skip = DECK_SWAP_SKIP.get(short_name, 0)
        deck = pause_a.rs.zones.single(stock).cards[skip:]
        candidates = _swap_pairs(short_name, hand, deck)
        side1 = (hz, opp)
        side2 = (stock, None)
        who = f"player {opp}'s hand <-> the undealt {stock}"

    assert candidates, "no swap pair available; lower DEPTH for this game"

    info_a = information_state(p, pause_a.rs, pause_a.obs_logs[p])
    last_err: ValueError | None = None
    for x, y in candidates:
        try:
            pause_b = run(path, seed, tuple(history), on_first_decision=_swap_fn(side1, side2, x, y))
        except ValueError as e:
            # this pair made a recorded action illegal (ActionSpace.match's
            # "not among the live candidates", or a zone .remove failure);
            # try the next pair, but remember why in case none work.
            last_err = e
            continue
        assert isinstance(pause_b, Pause)
        info_b = information_state(p, pause_b.rs, pause_b.obs_logs[p])
        assert info_a == info_b, (
            f"{short_name}: swapping hidden {x}<->{y} ({who}) "
            f"CHANGED P{p}'s information state — the info-set leaks"
        )
        return  # one successful controlled swap proves the property
    pytest.fail(f"{short_name}: no swap pair produced a legal replay; last replay error: {last_err!r}")


@pytest.mark.parametrize(("short_name", "filename"), KERNEL_GAMES)
def test_soundness_own_view_changes_the_state(short_name: str, filename: str) -> None:
    path = str(GAMES_DIR / filename)
    hz = _hidden(short_name)
    r0 = run(path, 5, ())
    assert isinstance(r0, Pause)
    p = r0.player
    opp = next(q for q in range(len(r0.obs_logs)) if q != p)
    own = r0.rs.zones.instance(hz, p).cards
    theirs = r0.rs.zones.instance(hz, opp).cards
    x, y = next(iter(_swap_pairs(short_name, own, theirs)))
    info_a = information_state(p, r0.rs, r0.obs_logs[p])
    r1 = run(path, 5, (), on_first_decision=_swap_fn((hz, p), (hz, opp), x, y))
    assert isinstance(r1, Pause)
    info_b = information_state(r1.player, r1.rs, r1.obs_logs[r1.player])
    # The pause player is the same (no actions replayed); their own hand changed.
    assert r1.player == p and info_a != info_b, (
        f"{short_name}: the info-state is insensitive to the player's own hand"
    )


@pytest.mark.parametrize(("short_name", "filename"), KERNEL_GAMES)
def test_perfect_recall_logs_are_append_only(short_name: str, filename: str) -> None:
    path = str(GAMES_DIR / filename)
    seed = 9
    history: list[int] = []
    r = run(path, seed, ())
    prev: dict[int, list[tuple[Any, ...]]] = {}
    steps = 0
    while isinstance(r, Pause) and steps < 40:
        for q, log in r.obs_logs.items():
            if q in prev:
                assert log[: len(prev[q])] == prev[q], (
                    f"{short_name}: P{q}'s observation log rewrote history"
                )
            prev[q] = list(log)
        history.append(r.legal[0])
        r = run(path, seed, tuple(history))
        steps += 1


def _is_stud_reveal_event(e: tuple[Any, ...]) -> bool:
    """A Stud showdown reveal (the park-then-flip `hole[p] -> upcards[p]`
    movement in seven-card-stud.cardlang's showdown block) as any NON-owner
    sees it: `hole[p]` collapses to a count (the owner's own view of the same
    event is a 7-card identity tuple, filtered out here) while `upcards[p]` —
    a PublicHand — stays identity for every observer, all seven merged cards
    landing in the clear at once."""
    return bool(
        e[0] == "move"
        and isinstance(e[1], str) and e[1].startswith("hole[")
        and isinstance(e[2], int)
        and isinstance(e[3], str) and e[3].startswith("upcards[")
        and isinstance(e[4], tuple) and len(e[4]) == 7
    )


def test_stud_showdown_reveals_contenders_holes_to_others() -> None:
    """The showdown block is the one place a Stud hand's hidden hole cards
    become public — and it is exactly what the score goldens can't see (the
    scores are provably insensitive to the reveal) and what this file's own
    proofs above never reach (their swaps pause pre-showdown, `DEFAULT_DEPTH`
    / stud's own comment above). This drives an actual hand past it and
    inspects the emitted events directly: a non-owner learns all seven of a
    contender's cards at once (count-only source, full-identity dest); a
    folded entrant's still-hidden hole cards muck count-only, with no
    identity leak to anyone else.

    The policy is `legal[0]` (check/call, the betting vocabulary's id order
    52..56) throughout, which alone reaches a contested 4-entrant showdown —
    nobody ever folds under it, since call and fold share a guard
    (`bet_to_match > bet_by[actor]`) and call's id sorts lower — except the
    first time `fold` itself is offered, where it is taken once, on purpose,
    to also exercise the folded-entrant guard in the same hand.
    """
    path = str(GAMES_DIR / "seven-card-stud.cardlang")
    game, space = load(path)
    seed = 3

    history: list[int] = []
    r = run(path, seed, ())
    assert isinstance(r, Pause)
    folded_player: int | None = None
    reveal: dict[int, tuple[Any, ...]] = {}  # contender -> a non-owner's view of their reveal
    for _ in range(40):
        names = [space.to_string(a) for a in r.legal]
        if folded_player is None and "fold" in names:
            folded_player = r.player
            aid = r.legal[names.index("fold")]
        else:
            aid = r.legal[0]
        history.append(aid)
        nxt = run(path, seed, tuple(history))
        assert isinstance(nxt, Pause), "the hand ended before a showdown reveal was observed"
        r = nxt
        for log in r.obs_logs.values():
            for e in log:
                if _is_stud_reveal_event(e):
                    reveal[int(e[3][len("upcards["):-1])] = e
        if reveal:
            break
    else:
        pytest.fail("no contested stud showdown reveal within 40 steps")
    assert folded_player is not None, "the drive never saw a legal fold to take"

    contenders = set(reveal)
    assert len(contenders) > 1, "need a CONTESTED showdown (more than one contender)"
    assert contenders == set(range(game.players.low)) - {folded_player}

    # Every contender's reveal is visible to a NON-contender observer (the
    # folded entrant): source count-only over the merged 7-card hand, dest
    # identity with all seven card names.
    folded_log = r.obs_logs[folded_player]
    for p in contenders:
        src, dst = f"hole[{p}]", f"upcards[{p}]"
        matches = [
            e for e in folded_log if _is_stud_reveal_event(e) and e[1] == src and e[3] == dst
        ]
        assert matches, f"P{folded_player} never observed contender {p}'s reveal"
        event = matches[0]
        assert event[2] == 7, "the source view must be count-only over all seven cards"
        assert len(event[4]) == 7 and all(isinstance(c, str) for c in event[4])

    # Converse guard: the folded entrant's own hole cards were never
    # revealed. Their eventual hole -> muck event must stay count-only
    # (trivial dest) in every OTHER player's log — only the owner's own log
    # may show identity, and that isn't a leak.
    saw_fold_muck = False
    for q, log in r.obs_logs.items():
        if q == folded_player:
            continue
        for e in log:
            if e[0] == "move" and e[1] == f"hole[{folded_player}]" and e[3] == "muck":
                saw_fold_muck = True
                assert isinstance(e[2], int), (
                    f"P{q} saw the folded entrant's hole-card identity leak into the muck"
                )
                assert e[4] is None
    assert saw_fold_muck, "the folded entrant's hole cards were never observed mucking"


def test_pinochle_declaration_and_lead_derive_observations() -> None:
    """Pinochle's trump declaration and its twelve strict tricks are the first
    time this game's decisions run through the kernel's decision/movement sites
    (docs/kernel-migration.md) rather than a Python mechanic that called
    `ctx.trace` only — a total info-set leak (no observer calls at all), not
    just an incomplete one. This drives a hand past the declaration and its
    opening lead and inspects the actual observation tuples, rather than
    relying only on the swap-based leak-closure proof above (which shows
    hidden cards don't change the information state, but never positively
    confirms an event's *shape*).

    Policy: `legal[0]` throughout. `submit_bid` sorts before `pass` (ids
    52 < 53), so the auction always runs the full 16 bids to the cap and
    settles deterministically on seat 1 (docs/games/pinochle.cardlang;
    tests/test_pinochle_auction.py pins the same ring-rotation fact); seed 5
    gives seat 1 a marriage, so `declare_trump_suit` is offered and its
    lowest-id enumerated Suit candidate (clubs) is taken.
    """
    path = str(GAMES_DIR / "pinochle.cardlang")
    game, space = load(path)
    seed = 5

    history: list[int] = []
    r = run(path, seed, ())
    assert isinstance(r, Pause)
    declarer: int | None = None
    declared: str | None = None
    while declared is None:
        names = [space.to_string(a) for a in r.legal]
        if declarer is None and any(n.startswith("declare_trump_suit") for n in names):
            declarer = r.player
        aid = r.legal[0]
        chosen = space.to_string(aid)
        if declarer is not None and chosen.startswith("declare_trump_suit"):
            declared = chosen
        history.append(aid)
        assert len(history) < 30, "trump was never declared within 30 steps"
        nxt = run(path, seed, tuple(history))
        assert isinstance(nxt, Pause), "the hand ended before trump was declared"
        r = nxt
    assert declarer is not None

    # The declaration is a public announcement: every player's log hears it
    # (state variables are public — `trump_suit` is no exception).
    for p, log in r.obs_logs.items():
        assert ("announce", declarer, declared) in log, (
            f"P{p} never observed the trump declaration"
        )

    # The declarer leads the first trick; one more action plays their card.
    assert r.player == declarer, "the declarer leads the first trick"
    history.append(r.legal[0])
    r2 = run(path, seed, tuple(history))
    assert isinstance(r2, Pause), "the hand ended on the opening lead"

    # A non-owner sees the leader's hand shrink count-only (never which card
    # left), while the public `trick_pile` destination is identity to
    # everyone — a follower sees WHAT was led, never what remains unplayed.
    non_owner = next(p for p in r2.obs_logs if p != declarer)
    plays = [
        e for e in r2.obs_logs[non_owner] if e[0] == "move" and e[1] == f"hand[{declarer}]"
    ]
    assert plays, f"P{non_owner} never observed P{declarer}'s card leaving their hand"
    event = plays[0]
    assert isinstance(event[2], int), "a non-owner must see the source hand count-only"
    assert event[3] == "trick_pile"
    assert isinstance(event[4], tuple) and len(event[4]) == 1

    # The converse: the owner's own log shows identity leaving their own hand.
    own_plays = [
        e for e in r2.obs_logs[declarer] if e[0] == "move" and e[1] == f"hand[{declarer}]"
    ]
    assert own_plays and isinstance(own_plays[0][2], tuple), (
        f"P{declarer} should see their own card's identity leaving their hand"
    )

    # And the non-owner's full information state renders every OTHER hand
    # (including the ones that haven't played yet) as counts, never identity.
    info = information_state(non_owner, r2.rs, r2.obs_logs[non_owner])
    for q in r2.obs_logs:
        if q == non_owner:
            continue
        n = len(r2.rs.zones.instance("hand", q).cards)
        assert f"hand[{q}]=#{n}" in info, f"P{non_owner} sees P{q}'s hand as more than a count"


def test_french_tarot_discard_derives_hidden_observations() -> None:
    """French Tarot's chien discard is the fidelity stage's payoff: a
    genuinely HIDDEN reroute (`discard[player]`, not the public captured
    pile the byte-identical migration used). Drives a hand to a Petite
    contract — seat 2 (the opener) takes the ONLY bid (`bid_petite`, forced
    at the very first decision, since greedy `legal[0]` always picks `pass`
    first — the same reason `test_french_tarot_auction.py` and the Bridge
    harness comment above both note); every later seat then passes under
    `legal[0]`, confirmed by direct probe — and inspects the chien merge and
    the discard directly, rather than relying only on the swap-based
    leak-closure proof above (which never positively confirms an event's
    *shape*, per the Pinochle/Stud precedent).
    """
    path = str(GAMES_DIR / "french-tarot.cardlang")
    game, space = load(path)
    seed = 0

    history: list[int] = []
    r = run(path, seed, ())
    assert isinstance(r, Pause)
    taker = r.player  # the opener; the only bidder under this driving policy
    bid_petite_aid = space.encode(("bid_petite", None))
    assert bid_petite_aid in r.legal, "bid_petite must be legal at the first turn"
    history.append(bid_petite_aid)
    r = run(path, seed, tuple(history))
    assert isinstance(r, Pause)

    # Three remaining auction passes, then the six discard picks — nine more
    # `legal[0]` steps (verified by direct probe: `pass` has no guard and
    # always sorts first among the candidates, so every later seat passes).
    for _ in range(9):
        history.append(r.legal[0])
        nxt = run(path, seed, tuple(history))
        assert isinstance(nxt, Pause), "the hand ended before the discard completed"
        r = nxt
    assert r.player == taker, "the taker leads the first trick next"

    taker_log = r.obs_logs[taker]
    defender = next(p for p in r.obs_logs if p != taker)
    defender_log = r.obs_logs[defender]

    # The auction is public: every log hears the bid and every pass.
    for p, log in r.obs_logs.items():
        assert ("announce", taker, "bid_petite") in log, f"P{p} never heard the bid"
        for other in range(4):
            if other != taker:
                assert ("announce", other, "pass") in log, f"P{p} never heard P{other} pass"

    # The chien merge (`chien` -> `hand[taker]`): count-only to a defender on
    # BOTH sides (the chien's own projection is count-only to everyone), but
    # identity into the taker's own hand.
    chien_to_defender = next(e for e in defender_log if e[0] == "move" and e[1] == "chien")
    assert chien_to_defender[2] == 6 and chien_to_defender[4] == 6

    chien_to_taker = next(e for e in taker_log if e[0] == "move" and e[1] == "chien")
    assert isinstance(chien_to_taker[4], tuple) and len(chien_to_taker[4]) == 6

    # The six discard picks surface as six "chose" events in the taker's log
    # only (the choice values themselves must never appear as another
    # player's "chose" — perfect recall of one's own decisions only).
    discarded = {e[1] for e in taker_log if e[0] == "chose"} - {"bid_petite"}
    assert len(discarded) == 6, discarded
    for p, log in r.obs_logs.items():
        if p == taker:
            continue
        leaked = [e for e in log if e[0] == "chose" and e[1] in discarded]
        assert not leaked, f"P{p} observed the taker's private discard choice: {leaked}"

    # The discard movement itself (`hand[taker]` -> `discard[taker]`) — the
    # fidelity payoff — is count-only to a defender on BOTH sides, never the
    # old public-captured-pile leak.
    discard_to_defender = next(
        e for e in defender_log if e[0] == "move" and e[3] == f"discard[{taker}]"
    )
    assert discard_to_defender[1] == f"hand[{taker}]"
    assert discard_to_defender[2] == 6, "source (hand) must be count-only to a defender"
    assert discard_to_defender[4] == 6, "dest (discard) must be count-only to a defender"

    # The taker sees identity on both sides of their own discard, the same
    # six cards leaving one zone and landing in the other.
    discard_to_taker = next(
        e for e in taker_log if e[0] == "move" and e[3] == f"discard[{taker}]"
    )
    assert isinstance(discard_to_taker[2], tuple) and len(discard_to_taker[2]) == 6
    assert isinstance(discard_to_taker[4], tuple) and len(discard_to_taker[4]) == 6
    assert set(discard_to_taker[2]) == set(discard_to_taker[4]) == discarded

    # Info state: a defender's rendering is a bare count; the taker's shows
    # the six actual identities.
    defender_info = information_state(defender, r.rs, r.obs_logs[defender])
    assert f"discard[{taker}]=#6" in defender_info

    taker_info = information_state(taker, r.rs, r.obs_logs[taker])
    assert f"discard[{taker}]=#6" not in taker_info
    assert f"discard[{taker}]=[" in taker_info


def test_cribbage_discard_and_pegging_derive_observations() -> None:
    """Cribbage's crib discard and pegging are the first time this game's
    decisions run through the kernel's decision/movement sites rather than a
    Python mechanic that traced only `cribbage_show` (dropped, no consumer) —
    a total info-set leak, not just an incomplete one (the Pinochle/Tarot
    precedent). Seed 5, greedy `legal[0]` throughout (the same seed and policy
    DEPTH=4 is probed against, docs comment above): player 0 discards first
    (seat-order for-each) and always leads pegging as the non-dealer.

    The crib's contents are never revealed even at the show (only the score
    delta signals it, matching the deleted monolith, which never moved the
    crib either) — a faithful table reveal is deferred fidelity work, not
    this migration (docs/roadmap.md).
    """
    path = str(GAMES_DIR / "cribbage.cardlang")
    game, space = load(path)
    seed = 5

    history: list[int] = []
    r = run(path, seed, ())
    assert isinstance(r, Pause)
    assert r.player == 0, "player 0 discards first"

    # Player 0's two discard picks (k=2 decomposes to 2 sequential actions).
    for _ in range(2):
        history.append(r.legal[0])
        nxt = run(path, seed, tuple(history))
        assert isinstance(nxt, Pause)
        r = nxt
    assert r.player == 1, "player 1 discards next"

    # P0's own discard: identity on the source (their own hand), COUNT-ONLY
    # into the crib even for the discarder's own view (FaceDownPile is
    # count-only to EVERYONE, not just opponents — the crib stays hidden from
    # the dealer too), plus the two per-pick "chose" events in P0's log only.
    own_log = r.obs_logs[0]
    own_discard = next(
        e for e in own_log if e[0] == "move" and e[1] == "hand[0]" and e[3] == "crib"
    )
    assert isinstance(own_discard[2], tuple) and len(own_discard[2]) == 2
    assert own_discard[4] == 2
    assert len([e for e in own_log if e[0] == "chose"]) == 2

    # P1's view of the same event: count-only on BOTH sides, no "chose"
    # leakage (P1 hasn't acted yet, so their log has none at all).
    opp_log = r.obs_logs[1]
    opp_view = next(
        e for e in opp_log if e[0] == "move" and e[1] == "hand[0]" and e[3] == "crib"
    )
    assert opp_view[2] == 2 and opp_view[4] == 2
    assert not any(e[0] == "chose" for e in opp_log)

    # Player 1's two discard picks.
    for _ in range(2):
        history.append(r.legal[0])
        nxt = run(path, seed, tuple(history))
        assert isinstance(nxt, Pause)
        r = nxt
    assert r.player == 0, "player 0 (the non-dealer) leads pegging"

    # The starter cut: identity to all (a genuinely public reveal).
    for p, log in r.obs_logs.items():
        starter_cut = next(
            e for e in log if e[0] == "move" and e[1] == "deck" and e[3] == "starter"
        )
        assert isinstance(starter_cut[4], tuple) and len(starter_cut[4]) == 1

    # Player 0's first pegging play.
    history.append(r.legal[0])
    r2 = run(path, seed, tuple(history))
    assert isinstance(r2, Pause)
    assert r2.player == 1, "pegging alternates to player 1 next"

    # The non-actor (P1) sees the play count-only on the source, identity on
    # the public play_pile destination — WHAT was led, never what remains.
    non_actor_play = next(
        e for e in r2.obs_logs[1] if e[0] == "move" and e[1] == "hand[0]" and e[3] == "play_pile"
    )
    assert non_actor_play[2] == 1
    assert isinstance(non_actor_play[4], tuple) and len(non_actor_play[4]) == 1

    # The actor (P0) sees identity on both sides of their own play.
    actor_play = next(
        e for e in r2.obs_logs[0] if e[0] == "move" and e[1] == "hand[0]" and e[3] == "play_pile"
    )
    assert isinstance(actor_play[2], tuple) and len(actor_play[2]) == 1
    assert actor_play[2] == actor_play[4]

    # Belt-and-braces: P1's rendered info state shows P0's hand and the crib
    # as bare counts, never identity; P0's own hand renders as identity.
    info1 = information_state(1, r2.rs, r2.obs_logs[1])
    assert "crib=#4" in info1
    n0 = len(r2.rs.zones.instance("hand", 0).cards)
    assert f"hand[0]=#{n0}" in info1
    info0 = information_state(0, r2.rs, r2.obs_logs[0])
    assert "crib=#4" in info0  # count-only to everyone — `crib` has no owner index
    assert f"hand[0]=#{n0}" not in info0
    assert "hand[0]=[" in info0


def test_schnapsen_lead_actions_derive_hidden_observations() -> None:
    """Schnapsen's information structure, positively confirmed (the
    Tarot/Cribbage precedent: the swap-based leak-closure proof above never
    confirms an event's *shape*): the talon is a count to everyone, the turned
    trump indicator identity to everyone, the free lead actions (exchange the
    trump jack, declare a marriage) public announcements whose card movements
    reveal exactly what the table sees, and a marriage never reveals the king.

    Seed 10, confirmed by direct probe: at the very first pause player 0 (the
    leader) may declare the hearts marriage, exchange the trump jack, or close
    the talon — one seed drives the whole scenario. The exchange does not lead
    (the ring re-offers the leader); the marriage leads its queen and ends the
    leader round.
    """
    path = str(GAMES_DIR / "schnapsen.cardlang")
    game, space = load(path)
    seed = 10

    r = run(path, seed, ())
    assert isinstance(r, Pause)
    leader, opp = r.player, 1 - r.player
    exchange_aid = space.encode(("exchange_trump_jack", None))
    marriage_aid = space.encode(("declare_marriage", "hearts"))
    assert exchange_aid in r.legal and marriage_aid in r.legal

    # The deal: each player sees their own five cards, the other's as counts,
    # and the turned trump indicator at identity (it is face up on the table).
    for p, log in r.obs_logs.items():
        own = [e for e in log if e[0] == "move" and e[3] == f"hand[{p}]"]
        assert own and all(isinstance(e[4], tuple) for e in own)
        other = [e for e in log if e[0] == "move" and e[3] == f"hand[{1 - p}]"]
        assert other and all(isinstance(e[4], int) for e in other)
        indicator = next(e for e in log if e[0] == "move" and e[3] == "trump_indicator")
        assert isinstance(indicator[4], tuple) and len(indicator[4]) == 1
        # The stock: nine cards into the talon, a count to everyone.
        talon = next(e for e in log if e[0] == "move" and e[3] == "talon")
        assert talon[4] == 9

    turned = r.rs.zones.single("trump_indicator").cards[0]

    # Exchange the trump jack — a free action: the round re-offers the leader.
    r = run(path, seed, (exchange_aid,))
    assert isinstance(r, Pause)
    assert r.player == leader, "the exchange must not end the leader's turn"
    assert exchange_aid not in r.legal, "the jack is in the indicator now"
    assert marriage_aid in r.legal, "the marriage is untouched by the exchange"
    for p, log in r.obs_logs.items():
        assert ("announce", leader, "exchange_trump_jack") in log
        # The turned card leaves the indicator at identity (everyone knows
        # which card the leader took)...
        out = next(e for e in log if e[0] == "move" and e[1] == "trump_indicator")
        assert out[2] == (str(turned),)
        # ...and the jack arrives face up at identity (the deal's turn-up is
        # also a dst=trump_indicator event, hence the src filter).
        into = next(
            e
            for e in log
            if e[0] == "move" and e[1] == f"hand[{leader}]" and e[3] == "trump_indicator"
        )
        assert isinstance(into[4], tuple) and into[4][0].startswith("J")

    # Declare the hearts marriage: a public announcement; the queen leads at
    # identity; the king is never revealed.
    r = run(path, seed, (exchange_aid, marriage_aid))
    assert isinstance(r, Pause)
    assert r.player == opp, "the marriage leads its queen, ending the leader round"
    from cardlang.runtime.values import Card

    for p, log in r.obs_logs.items():
        assert ("announce", leader, "declare_marriage(hearts)") in log
        queen = next(e for e in log if e[0] == "move" and e[3] == "trick_pile")
        assert queen[4] == (str(Card("Q", "hearts")),)
    assert not any(
        str(Card("K", "hearts")) in str(e) for e in r.obs_logs[opp]
    ), "the marriage revealed the king; only the suit is public"

    # The follower answers (greedy lowest card id), the trick resolves, and
    # the winner and loser each draw from the talon: a count to the other
    # player, identity to the drawer.
    r2 = run(path, seed, (exchange_aid, marriage_aid, r.legal[0]))
    assert isinstance(r2, Pause)
    for drawer in (0, 1):
        other_log = r2.obs_logs[1 - drawer]
        draw_seen = next(
            e
            for e in other_log
            if e[0] == "move" and e[1] == "talon" and e[3] == f"hand[{drawer}]"
        )
        assert draw_seen[2] == 1 and draw_seen[4] == 1, (
            f"P{1 - drawer} saw more than a count of P{drawer}'s talon draw"
        )
        own_draw = next(
            e
            for e in r2.obs_logs[drawer]
            if e[0] == "move" and e[1] == "talon" and e[3] == f"hand[{drawer}]"
        )
        assert isinstance(own_draw[4], tuple) and len(own_draw[4]) == 1

    # Belt-and-braces: the opponent's rendered info state shows the leader's
    # hand and the talon as bare counts, never identity.
    info_opp = information_state(opp, r2.rs, r2.obs_logs[opp])
    n_leader = len(r2.rs.zones.instance("hand", leader).cards)
    n_talon = len(r2.rs.zones.single("talon").cards)
    assert f"hand[{leader}]=#{n_leader}" in info_opp
    assert f"talon=#{n_talon}" in info_opp


def test_skat_pickup_and_discard_derive_hidden_observations() -> None:
    """Skat's information structure, positively confirmed (the Tarot/Cribbage/
    Schnapsen precedent): the Reizen and every declaration are public
    announcements, the skat pickup is identity only into the declarer's own
    hand (a count to the defenders on both sides), the two-card discard's
    picks are the declarer's alone, and a defender's rendered info state shows
    the declarer's hand and the skat as bare counts.

    The auction roles are seating-derived, so the driven line is
    seed-independent: dealer rotates 0->1 before hand 1, forehand = 2 answers,
    middlehand = 0 speaks, rearhand = 1 speaks second. Both speakers pass, so
    forehand becomes declarer at 18 (play_at_eighteen), picks up the skat,
    discards two, and declares grand — no cards influence any legal set until
    the discard, whose picks we take from the live legal actions.
    """
    path = str(GAMES_DIR / "skat.cardlang")
    game, space = load(path)
    seed = 3
    declarer, defenders = 2, (0, 1)

    aid = {name: space.encode(name) for name in
           ("play_at_eighteen", "pick_up_skat", "declare_grand")}
    vpass = space.encode(("pass", None))

    history: list[int] = [vpass, vpass, aid["play_at_eighteen"], aid["pick_up_skat"]]
    r = run(path, seed, tuple(history))
    assert isinstance(r, Pause)
    assert r.player == declarer and all(a < 52 for a in r.legal), "the discard pause"
    history.append(r.legal[0])  # first discard pick
    r = run(path, seed, tuple(history))
    assert isinstance(r, Pause)
    history.append(r.legal[0])  # second discard pick
    history.append(aid["declare_grand"])
    r = run(path, seed, tuple(history))
    assert isinstance(r, Pause)
    assert r.player == 2, "forehand leads the first trick"

    # The auction and declarations are public: every log heard both passes and
    # each of the declarer's choices.
    for p, log in r.obs_logs.items():
        assert ("announce", 0, "pass") in log and ("announce", 1, "pass") in log
        for name in ("play_at_eighteen", "pick_up_skat", "declare_grand"):
            assert ("announce", declarer, name) in log, f"P{p} missed {name}"

    # The pickup (skat -> hand[declarer]): identity into the declarer's own
    # hand; the skat side is a count to everyone (FaceDownPile), and a
    # defender sees the hand side as a count too.
    own_pickup = next(
        e for e in r.obs_logs[declarer]
        if e[0] == "move" and e[1] == "skat" and e[3] == f"hand[{declarer}]"
    )
    assert own_pickup[2] == 2 and isinstance(own_pickup[4], tuple) and len(own_pickup[4]) == 2
    picked_up = set(own_pickup[4])
    for d in defenders:
        seen = next(
            e for e in r.obs_logs[d]
            if e[0] == "move" and e[1] == "skat" and e[3] == f"hand[{declarer}]"
        )
        assert seen[2] == 2 and seen[4] == 2, f"P{d} saw more than counts of the pickup"

    # The discard (hand[declarer] -> skat): the declarer sees the two cards
    # leave; a defender sees counts on both sides; the two "chose" picks are
    # the declarer's alone.
    own_discard = next(
        e for e in r.obs_logs[declarer]
        if e[0] == "move" and e[1] == f"hand[{declarer}]" and e[3] == "skat"
    )
    assert isinstance(own_discard[2], tuple) and len(own_discard[2]) == 2
    discarded = set(own_discard[2])
    for d in defenders:
        seen = next(
            e for e in r.obs_logs[d]
            if e[0] == "move" and e[1] == f"hand[{declarer}]" and e[3] == "skat"
        )
        assert seen[2] == 2 and seen[4] == 2, f"P{d} saw the discard identities"
        leaked = [e for e in r.obs_logs[d] if e[0] == "chose" and e[1] in discarded]
        assert not leaked, f"P{d} observed the declarer's discard picks: {leaked}"

    # A defender's rendered info state: the declarer's hand and the skat are
    # bare counts; the declarer's own rendering shows the hand identities.
    # And no hidden-derived value reaches the public state rendering: the
    # matador count (a function of the declarer's hidden hand + the face-down
    # skat, computed at this point of the hand for the grand contract) must be
    # a local, never a state variable — state renders public to everyone.
    for d in defenders:
        info = information_state(d, r.rs, r.obs_logs[d])
        assert f"hand[{declarer}]=#10" in info
        assert "skat=#2" in info
        assert "matadors" not in info, "the matador count leaked into public state"
    own_info = information_state(declarer, r.rs, r.obs_logs[declarer])
    assert f"hand[{declarer}]=#10" not in own_info
    assert f"hand[{declarer}]=[" in own_info


def test_tichu_push_derives_hidden_observations() -> None:
    """The push is where hidden cards change hands without ever becoming
    public: each giver picks three cards in ONE chooser draw (decomposed to
    three card actions by the replay chooser), and pick i goes to the i-th
    other player in seat order, giver-major. Per the zone projections (hand
    and gift are both owner-visible), the giver alone sees their picks, each
    receiver sees exactly the card that landed in their hand AND which giver's
    pile it came from (real Tichu: you know who passed you what), and a
    bystander sees counts on both sides. The score goldens can't witness any
    of this — the observation stream is the only proof the push derives
    per-observer."""
    path = str(GAMES_DIR / "tichu.cardlang")
    history: list[int] = []
    r = run(path, 5, ())
    assert isinstance(r, Pause)
    while len(history) < 12:  # the full push: 4 givers x 3 decomposed picks
        history.append(r.legal[0])
        nxt = run(path, 5, tuple(history))
        assert isinstance(nxt, Pause)
        r = nxt

    # The giver's three picks are the giver's alone (identity in their log).
    chose0 = [e[1] for e in r.obs_logs[0] if e[0] == "chose"]
    assert len(chose0) == 3

    def gift_moves(log: list[tuple[Any, ...]], src: str, dst: str) -> list[tuple[Any, ...]]:
        return [e for e in log if e[0] == "move" and e[1] == src and e[3] == dst]

    # The giver's outgoing pile: identity to the giver, counts to everyone else.
    (own_push,) = gift_moves(r.obs_logs[0], "hand[0]", "gift[0]")
    assert isinstance(own_push[2], tuple) and set(own_push[4]) == set(chose0)
    (other_push,) = gift_moves(r.obs_logs[2], "hand[0]", "gift[0]")
    assert other_push[2] == 3 and other_push[4] == 3, "a bystander saw the picks"

    # Giver-major routing witnessed by the receiver: p0's FIRST pick lands in
    # hand[1] (the lowest-numbered other seat), and p1 sees its identity plus
    # the source pile — but the source side collapses to a count.
    (recv,) = gift_moves(r.obs_logs[1], "gift[0]", "hand[1]")
    assert recv[4] == (chose0[0],), "the receiver must see exactly what landed"
    assert recv[2] == 1

    # A bystander sees the same transfer as counts on both sides, and never
    # observes another giver's picks.
    (bystander,) = gift_moves(r.obs_logs[3], "gift[0]", "hand[1]")
    assert bystander[2] == 1 and bystander[4] == 1, "a bystander saw a gift identity"
    leaked = [e for e in r.obs_logs[3] if e[0] == "chose" and e[1] in chose0]
    assert not leaked, f"P3 observed another giver's picks: {leaked}"

    # The pause after the push is the first climbing lead: the Mahjong holder.
    # Their rendered info state shows their own (post-push) hand as identities
    # and every other hand as a bare count.
    leader = r.player
    info = information_state(leader, r.rs, r.obs_logs[leader])
    assert f"hand[{leader}]=[" in info
    for q in range(4):
        if q != leader:
            assert f"hand[{q}]=#14" in info, "an opponent hand rendered as identities"


def test_playtest_report_shape() -> None:
    from cardlang.openspiel.report import playtest_report

    rep = playtest_report("cardlang_getaway", num_games=2, seed=1)
    assert rep["num_games"] == 2
    assert rep["mean_length"] > 0 and rep["mean_branching"] >= 1
    assert len(rep["mean_returns"]) == 4
    assert sum(rep["best_seat_counts"]) == 2
