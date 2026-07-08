"""Go Fish — OpenSpiel readiness.

Four players, hidden `hand`. A public ask's transfer COUNT is observed
(`Hand` -> count_only to non-owners), so an indistinguishable world requires a
same-RANK swap (K♠↔K♥): it preserves every per-rank count and every ask's
legality, hence every public observation. Same-suit (the trick-game default)
is wrong in general: on any line where an observed transfer count depends on
a rank's composition, a same-suit swap changes that count. That's why "rank",
not "suit", is the correct axis for this game as a general property of the
mechanic — independent of whether any one test run happens to probe that
channel (see the caveat below: this particular run doesn't).

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

HONESTY CAVEAT — what this test does and doesn't prove: because hands 2/3
are structurally never ask targets at this depth, P1 observes no
transfer-count event that mentions either hand — so this instance shows a
same-rank swap is SUFFICIENT for a valid indistinguishable world, not that it
is NECESSARY here. Checked directly: `swap_axis="suit"` and `"any"` ALSO pass
at this exact (seed=5, depth=6) configuration, because the one channel this
test exists to guard — the public transfer count — is never exercised on
this particular line. So this test does not itself exercise the
transfer-count derivation; it demonstrates a correct instance, not a
discriminating one. The direct semantic Go Fish was chosen to prove — that an
observer derives "the asker holds the named rank" from a public ask — is
instead proven by the dedicated observational test
`test_public_ask_derives_asker_holds_rank` (Task 9), not by this swap test.
The general limitation this reveals — a greedy swap-and-replay harness can
produce a legally-replayed swap that never exercises the adversarial channel
it's meant to probe — is documented in
`docs/open-questions/structural-infoset-proofs.md` ("World-generator gap
(Go Fish)").
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
