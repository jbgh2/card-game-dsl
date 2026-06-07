"""The Coup game mechanic (3-6 players; concrete).

The corpus's furthest-from-cards game: hidden *influence* cards, a coin economy,
and actions resolved through challenge and block windows with bluffing. Built as
one concrete mechanic that runs the whole game to a sole survivor, updating the
influence/revealed zones and the coin/alive state directly.

Two conservation invariants make the engine falsifiable: total coins are always
50 (treasury + all players), and total influence cards are always 15 (deck +
hands + revealed). The random chooser/`rng` drives action, target, challenge, and
block decisions; challenges and blocks fire at a modest probability so games stay
lively but always terminate (forced Coup at 10 coins guarantees eliminations).
"""

from __future__ import annotations

from typing import Any

from cardlang.ast import nodes as n
from cardlang.runtime.evaluate import evaluate
from cardlang.runtime.state import Ctx
from cardlang.runtime.values import Card, Player

CHALLENGE_PROB = 0.18
BLOCK_PROB = 0.30


def run_coup_game(stmt: n.Instantiate, ctx: Ctx) -> Player:
    rs = ctx.rs
    rng = rs.rng
    choose = ctx.chooser
    players = list(rs.seating.players)
    npl = len(players)
    influence = rs.zones.families["influence"]
    revealed = rs.zones.families["revealed"]
    deck = rs.zones.single("court_deck")
    coins = rs.get("coins")
    alive = rs.get("alive")
    treasury = [rs.get("treasury")]  # boxed so nested helpers can mutate it

    def gain(p: Player, amt: int) -> None:
        amt = min(amt, treasury[0])
        treasury[0] -= amt
        coins[p] += amt

    def pay(p: Player, amt: int) -> None:
        amt = min(amt, coins[p])
        coins[p] -= amt
        treasury[0] += amt

    def in_game(p: Player) -> bool:
        return alive[p] == 1 and bool(influence[p].cards)

    def has_char(p: Player, ch: str) -> bool:
        return any(c.rank == ch for c in influence[p].cards)

    def opponents(p: Player) -> list[Player]:
        return [q for q in players if q != p and in_game(q)]

    def lose_influence(p: Player) -> None:
        if not in_game(p):
            return
        card = choose(p, list(influence[p].cards), 1)[0]
        influence[p].remove(card)
        revealed[p].add(card)
        ctx.trace("coup_reveal", (p, card.rank))
        if not influence[p].cards:
            alive[p] = 0
            treasury[0] += coins[p]  # exiled: coins return to the bank
            coins[p] = 0

    def order_from(start: Player, exclude: Player) -> list[Player]:
        return [(start + i) % npl for i in range(npl) if (start + i) % npl != exclude]

    def challenge_window(claimant: Player, claimed: str) -> str:
        """Returns 'stands' or 'refuted'."""
        for c in order_from(claimant, claimant):
            if not in_game(c):
                continue
            if rng.random() < CHALLENGE_PROB:
                if has_char(claimant, claimed):  # claim proven
                    proof = next(x for x in influence[claimant].cards if x.rank == claimed)
                    influence[claimant].remove(proof)
                    deck.cards.append(proof)
                    rng.shuffle(deck.cards)
                    influence[claimant].add(deck.cards.pop())  # private replacement
                    lose_influence(c)
                    return "stands"
                lose_influence(claimant)  # bluff caught
                return "refuted"
        return "stands"

    def block_window(blockers: list[Player], blocking: list[str]) -> str:
        """Returns 'blocked' or 'not_blocked'."""
        for b in blockers:
            if not in_game(b):
                continue
            if rng.random() < BLOCK_PROB:
                claimed = rng.choice(blocking)
                return "blocked" if challenge_window(b, claimed) == "stands" else "not_blocked"
        return "not_blocked"

    # --- setup ---
    rng.shuffle(deck.cards)
    for p in players:
        influence[p].add(deck.cards.pop())
        influence[p].add(deck.cards.pop())
        gain(p, 2)

    # --- turn loop ---
    turn_p = players[0]
    guard = 0
    while sum(1 for p in players if in_game(p)) > 1:
        guard += 1
        if guard > 10000:
            raise RuntimeError(
                "coup game exceeded 10000 turns without a sole survivor (non-termination?)"
            )
        if in_game(turn_p):
            _take_turn(turn_p, coins, opponents, choose, rng, gain, pay,
                       lose_influence, challenge_window, block_window,
                       influence, deck, in_game)
        nxt = next((q for q in (turn_p + 1 + i for i in range(npl)) if in_game(q % npl)), None)
        if nxt is None:
            break
        turn_p = nxt % npl

    rs.set("treasury", treasury[0])
    total_coins = treasury[0] + sum(coins[p] for p in players)
    total_cards = len(deck.cards) + sum(
        len(influence[p].cards) + len(revealed[p].cards) for p in players
    )
    ctx.trace("coup_game", {"total_coins": total_coins, "total_cards": total_cards})
    return next((p for p in players if in_game(p)), turn_p)


def _take_turn(  # type: ignore[no-untyped-def]
    actor, coins, opponents, choose, rng, gain, pay, lose_influence,
    challenge_window, block_window, influence, deck, in_game,
) -> None:
    c = coins[actor]
    opps = opponents(actor)
    if c >= 10:
        legal = ["coup"]  # forced
    else:
        legal = ["income", "foreign_aid", "tax", "steal", "exchange"]
        if c >= 7:
            legal.append("coup")
        if c >= 3:
            legal.append("assassinate")
    action = choose(actor, legal, 1)[0]

    if action == "income":
        gain(actor, 1)
    elif action == "foreign_aid":
        if block_window(opps, ["Duke"]) == "not_blocked":
            gain(actor, 2)
    elif action == "coup":
        target = rng.choice(opps)
        pay(actor, 7)
        lose_influence(target)
    elif action == "tax":
        if challenge_window(actor, "Duke") == "stands":
            gain(actor, 3)
    elif action == "assassinate":
        target = rng.choice(opps)
        pay(actor, 3)  # fee paid up front, and stays spent either way
        # A refuted (caught) bluff: the actor already lost an influence in the
        # challenge and the assassination fails. Otherwise the target may block.
        if challenge_window(actor, "Assassin") == "stands":
            if block_window([target], ["Contessa"]) == "not_blocked":
                lose_influence(target)
    elif action == "steal":
        target = rng.choice(opps)
        if challenge_window(actor, "Captain") == "stands":
            if block_window([target], ["Captain", "Ambassador"]) == "not_blocked":
                amount = min(2, coins[target])
                coins[target] -= amount
                coins[actor] += amount
    elif action == "exchange":
        if challenge_window(actor, "Ambassador") == "stands":
            drawn = [deck.cards.pop() for _ in range(min(2, len(deck.cards)))]
            for card in drawn:
                influence[actor].add(card)
            for card in choose(actor, list(influence[actor].cards), len(drawn)):
                influence[actor].remove(card)
                deck.cards.append(card)
            rng.shuffle(deck.cards)
