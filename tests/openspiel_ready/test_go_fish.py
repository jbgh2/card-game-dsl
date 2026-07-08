"""Go Fish — OpenSpiel readiness.

Four players, hidden `hand`. A public ask's transfer COUNT is observed
(`Hand` -> count_only to non-owners), so an indistinguishable world requires a
same-RANK swap (K♠↔K♥): it preserves every per-rank count and every ask's
legality, hence every public observation. Same-suit (the trick-game default)
would change a rank count the observer saw.

Depth 6: the greedy `legal[0]` policy always names the SMALLEST legal
(target, rank) pair, and Go Fish's `ask(target, rank)` guard never consults
the target's hand — only `target != actor` and "actor holds the rank" — so
the smallest legal target is always player 0 (for any actor != 0) or player 1
(for actor 0, since 0 can't target itself). Concretely: every non-zero actor
always asks player 0, and player 0 always asks player 1. Players 2 and 3 are
therefore NEVER named as an ask target under this policy, so their hands
never lose a card to a targeted transfer. At depth 6 the pause lands on
player 1 (p=1), so the harness swaps between hands {2, 3} — exactly the two
hands the greedy policy structurally never touches. This isn't a lucky
artifact of this seed's deal: it holds for any deal, since it follows from the
guard and the target-ordering alone, which is what makes a same-rank swap
between those two hands genuinely invisible to P1 (own hand untouched, and
the swapped hands are never observed as anything but counts, unaffected by a
same-rank swap, all the way through the replayed prefix).
"""

from .harness import GameSpec, ReadinessProofs


class TestReadiness(ReadinessProofs):
    spec = GameSpec(
        "cardlang_go_fish",
        "go-fish.cardlang",
        hidden_zone="hand",
        depth=6,
        swap_axis="rank",
    )
