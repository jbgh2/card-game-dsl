"""Coup's game-local runtime primitives.

The game runs fully on the kernel (coup.cardlang): setup, the turn loop, and
the seven actions are plain statements — the turn's action pick is an `offer`
over coin-guarded move types, and every influence loss is a chosen movement
by the loser (the single-actor `for each player q: if q == <loser>` idiom).
What stays game-local: the response windows' randomness. At the migrated
random-play scope, challenging and blocking are probability gates and the
blocker's claimed character is a random pick — NOT player decisions — so they
are rng primitives at the reference's exact draw sites (`tichu_call_roll` /
`tichu_dragon_recipient` precedent), as are the action targets
(`coup_random_target`: the reference drives targets with `rng.choice`; a real
target choice is a scope upgrade, gated on the Player move-parameter domain).
The in-game/seat scans and character lookups are pure reads, and two trace
primitives keep the `coup_reveal` / `coup_game` events the characterization
golden and the playout invariants consume.

The windows' *results* are public phase state (`challenge_stands` /
`block_stands`), as challenges and blocks are in real Coup. One documented
under-inform at this scope: a proven challenge returns the claimed card to
the deck as hidden movements (counts to observers), where real Coup shows the
proven card publicly — the fidelity upgrade (a `reveal` epistemic op plus
challenge decisions as moves) belongs to the interactive-windows scope
upgrade, not this migration.
"""

from __future__ import annotations

from cardlang.runtime.state import Ctx
from cardlang.runtime.values import Player

CHALLENGE_PROB = 0.18
BLOCK_PROB = 0.30


def _in_game(ctx: Ctx, p: Player) -> bool:
    return bool(
        ctx.rs.get("alive")[p] == 1 and ctx.rs.zones.families["influence"][p].cards
    )


def coup_players_in(ctx: Ctx) -> int:
    """How many players still hold influence (the game ends at 1)."""
    return sum(1 for p in ctx.rs.seating.players if _in_game(ctx, p))


def coup_next_in_game(ctx: Ctx, p: Player) -> Player:
    """The next in-game player clockwise after `p` (p itself when alone)."""
    npl = len(ctx.rs.seating.players)
    return next(
        (q % npl for q in (p + 1 + i for i in range(npl)) if _in_game(ctx, q % npl)),
        p,
    )


def coup_random_target(ctx: Ctx, actor: Player) -> Player:
    """The action's target: a random in-game opponent (the migrated scope
    plays randomly; a chooser-driven target is a scope upgrade)."""
    opps = [q for q in ctx.rs.seating.players if q != actor and _in_game(ctx, q)]
    return ctx.rs.rng.choice(opps)


def coup_challenger(ctx: Ctx, claimant: Player) -> Player | None:
    """The challenge window's gate: scan the in-game opponents clockwise from
    the claimant, each challenging with probability 0.18; the first hit
    challenges (or nobody does). Consumes one roll per live opponent scanned —
    the reference's exact sequence."""
    npl = len(ctx.rs.seating.players)
    for c in ((claimant + i) % npl for i in range(npl)):
        if c == claimant or not _in_game(ctx, c):
            continue
        if ctx.rs.rng.random() < CHALLENGE_PROB:
            return c
    return None


def coup_fa_blocker(ctx: Ctx, actor: Player) -> Player | None:
    """Foreign aid's block gate: any in-game opponent may claim the Duke, in
    seat order, each blocking with probability 0.30."""
    for b in ctx.rs.seating.players:
        if b == actor or not _in_game(ctx, b):
            continue
        if ctx.rs.rng.random() < BLOCK_PROB:
            return b
    return None


def coup_block_roll(ctx: Ctx) -> bool:
    """A single-blocker window's gate (the assassination/steal target)."""
    return bool(ctx.rs.rng.random() < BLOCK_PROB)


def coup_duke_claim(ctx: Ctx) -> str:
    """The foreign-aid blocker's claimed character. A one-element pick, but it
    consumes the reference's `rng.choice` draw, so it stays a primitive."""
    return str(ctx.rs.rng.choice(["Duke"]))


def coup_contessa_claim(ctx: Ctx) -> str:
    """The assassination blocker's claimed character (same one-element-pick
    rng consumption as the Duke claim)."""
    return str(ctx.rs.rng.choice(["Contessa"]))


def coup_steal_block_claim(ctx: Ctx) -> str:
    """The steal blocker's claimed character: Captain or Ambassador, at
    random (the one multi-way claim pick in the game)."""
    return str(ctx.rs.rng.choice(["Captain", "Ambassador"]))


def coup_has_char(ctx: Ctx, p: Player, rank: str) -> bool:
    """Does `p` hold the claimed character face-down (a challenge's proof)?"""
    return any(c.rank == rank for c in ctx.rs.zones.families["influence"][p].cards)


def coup_note_reveal(ctx: Ctx, p: Player) -> int:
    """Trace the influence flip that just happened (the last card into
    `revealed[p]`) — the per-seed reveal-sequence golden's anchor."""
    card = ctx.rs.zones.families["revealed"][p].cards[-1]
    ctx.trace("coup_reveal", (p, card.rank))
    return 0


def coup_game_summary(ctx: Ctx) -> int:
    """Emit the end-of-game `coup_game` trace: the two conservation totals
    (50 coins, 15 cards — the playout invariants) plus final coins and the
    alive vector (the characterization golden)."""
    players = list(ctx.rs.seating.players)
    coins = ctx.rs.get("coins")
    alive = ctx.rs.get("alive")
    treasury = ctx.rs.get("treasury")
    total_coins = int(treasury) + sum(int(coins[p]) for p in players)
    deck = ctx.rs.zones.single("court_deck")
    influence = ctx.rs.zones.families["influence"]
    revealed = ctx.rs.zones.families["revealed"]
    total_cards = len(deck.cards) + sum(
        len(influence[p].cards) + len(revealed[p].cards) for p in players
    )
    ctx.trace(
        "coup_game",
        {
            "total_coins": total_coins,
            "total_cards": total_cards,
            "coins": {p: coins[p] for p in players},
            "alive": {p: alive[p] for p in players},
        },
    )
    return total_coins
