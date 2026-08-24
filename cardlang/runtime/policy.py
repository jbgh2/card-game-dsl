"""The [[playout-policy]]: a [[chooser]] that ranks where it can and says so.

`random_chooser` draws uniformly, which exercises invariants but never
reaches a branch a competent player would steer toward — Spades' +500 win
sits behind bidding that a uniform draw over 0..13 systematically overbids
past. This resolves the [[candidate]] kinds it declares a ranking for and
delegates the rest to a uniform draw, so the reach it buys is legible: what
is ranked, what is not, and a refusal for anything in neither.

The registry below is the whole claim. A policy that ranked one Candidate
kind and quietly drew uniformly for the others would look identical from
outside — same playouts, same green suite — so an unregistered Candidate
shape is refused at the seam rather than delegated, and
`tests/test_playout_policy.py` is where that registry is held to it.

It reads only the deciding seat's own [[projection]] — the zone types whose
`ZONE_PROJECTIONS` entry shows card identity to their owner and not to
anyone else. A policy that consulted another seat's hand would still produce
playouts, but they would be evidence about a game nobody is playing.
"""

from __future__ import annotations

import random
from typing import Any

from cardlang.runtime.chooser import random_chooser
from cardlang.runtime.errors import OwnerGuardError
from cardlang.runtime.state import RuntimeState
from cardlang.runtime.values import Card
from cardlang.stdlib.zones import ZONE_PROJECTIONS

# The Candidate kinds this policy classifies. A shape outside them is refused,
# never delegated — see the module docstring.
CANDIDATE_KINDS: tuple[str, ...] = ("integer", "card", "card_group", "move", "token")

# The subset carrying a declared ranking. Everything else delegates to the
# injected uniform draw. Ranking applies at a single draw only: a multi-card
# selection is a pass or a discard, and which cards those want is game-specific
# in a direction a state-free ranking cannot pick (Hearts passes its highest
# cards, a discard sheds its lowest).
RANKED_KINDS: frozenset[str] = frozenset({"integer"})


def candidate_kind(value: Any) -> str:
    """The registered kind of one Candidate, or a refusal.

    `bool` is refused ahead of `int` deliberately. It is an `int` subclass, so
    an `isinstance(value, int)` arm would rank `True` as the integer 1 — and
    the runtime's two existing statements of the decision-value domain
    disagree about it: `observe.render` accepts a bool through its `int | str`
    arm while `ActionSpace.encode` rejects one outright. No call site produces
    one. This sides with the encoder: a Candidate with no OpenSpiel action id
    is not one this policy will pick.
    """
    if isinstance(value, bool):
        raise OwnerGuardError(
            "a boolean candidate has no declared Playout Policy disposition — "
            "`ActionSpace.encode` refuses it as an action value, so ranking or "
            "drawing one would pick a Candidate with no action id"
        )
    if isinstance(value, Card):
        return "card"
    if isinstance(value, int):
        return "integer"
    if isinstance(value, str):
        return "token"
    if isinstance(value, tuple) and len(value) == 2 and isinstance(value[0], str):
        return "move"
    if getattr(value, "cards", None) is not None:
        return "card_group"
    raise OwnerGuardError(
        f"a candidate of type {type(value).__name__} has no declared Playout "
        f"Policy disposition — add it to CANDIDATE_KINDS with a ranking or an "
        f"explicit delegation, rather than letting it draw uniformly unrecorded"
    )


def _own_private_cards(rs: RuntimeState, player: int) -> list[Card]:
    """Every card the deciding seat can see and nobody else can.

    Derived from the declared projections rather than a zone name: a family
    qualifies when its library type shows identity to its owner and something
    less to everyone else, which is what `Hand` and `HiddenPile` are and what
    a shared pile is not.
    """
    out: list[Card] = []
    for name, zone_type in rs.zones.zone_type.items():
        vis = ZONE_PROJECTIONS.get(zone_type)
        if vis is None or vis.owner != "identity" or vis.others == "identity":
            continue
        family = rs.zones.families.get(name)
        if family is not None and player in family:
            out.extend(family[player].cards)
    return out


def _likely_winners(rs: RuntimeState, player: int) -> int:
    """How many tricks the seat's own cards look like taking.

    The standard bidding heuristic, stated deck-agnostically: cards in the top
    two ranks of the declared ranking, plus trump length beyond a fair share of
    the hand. Both terms read the declared `ranking:` and `trump:`, which are
    public, and the seat's own cards, which are its own.

    It is a heuristic and nothing more — it does not model partners, position,
    voids, or what has already been played. What it buys is a declaration in
    the neighbourhood of the hand instead of one uniform over the whole range.
    """
    cards = _own_private_cards(rs, player)
    if not cards or not rs.rank_index:
        return 0
    top = max(rs.rank_index.values())
    winners = sum(1 for c in cards if rs.rank_index.get(c.rank, -1) >= top - 1)
    if rs.trump:
        fair_share = len(cards) // max(1, len(rs.suits))
        winners += max(0, sum(1 for c in cards if c.suit == rs.trump) - fair_share)
    return winners


class PlayoutPolicy:
    """A Playout Policy over the Chooser seam.

    Wire both halves — the seam and the live world:

        policy = PlayoutPolicy(rng)
        play_game(game, rng, chooser=policy, on_first_decision=policy.attach)

    Forgetting the second is refused rather than tolerated: a policy with no
    world silently draws uniformly, which is the one failure this class exists
    to make impossible to ship by accident.
    """

    def __init__(self, rng: random.Random) -> None:
        # The delegate is `random_chooser` itself, not a private re-draw: it
        # owns the `n > len(candidates)` refusal, samples by position (so decks
        # declared with `copies` keep their equal cards distinguishable), and
        # draws from the same stream the uniform chooser would. One RNG source,
        # so a seeded run stays reproducible.
        self._draw = random_chooser(rng)
        self._rs: RuntimeState | None = None

    def attach(self, rs: RuntimeState) -> None:
        """Take the live world, via `play_game`'s `on_first_decision` seam.

        Reads only; `on_first_decision`'s caveat about mutating the first
        decider's zones does not bite.
        """
        self._rs = rs

    def __call__(self, player: int, candidates: list[Any], n: int) -> list[Any]:
        rs = self._rs
        if rs is None:
            raise OwnerGuardError(
                "PlayoutPolicy was asked to decide before attach() gave it the "
                "live world — pass `on_first_decision=policy.attach` to "
                "play_game alongside `chooser=policy`. Refusing rather than "
                "drawing uniformly, which would look like a policy and not be one"
            )
        kinds = {candidate_kind(c) for c in candidates}
        # One ranked kind, one draw. A mixed list delegates entire: ranking the
        # members of the ranked kind and drawing among the rest would be a
        # ranking nobody declared, and mixed lists are real (a climbing round
        # offers combination plays beside a bare "pass").
        if n == 1 and len(kinds) == 1 and kinds <= RANKED_KINDS:
            return [self._rank_integer(rs, player, candidates)]
        return self._draw(player, candidates, n)

    def _rank_integer(
        self, rs: RuntimeState, player: int, candidates: list[Any]
    ) -> Any:
        """Declare the number of tricks the hand looks like taking, clamped to
        what is on offer. Returns an element of `candidates` rather than a
        freshly computed equal value, so the seam's return-what-you-were-handed
        contract holds for every kind alike."""
        target = _likely_winners(rs, player)
        return min(candidates, key=lambda c: (abs(int(c) - target), int(c)))
