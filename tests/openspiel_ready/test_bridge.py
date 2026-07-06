"""Bridge — OpenSpiel readiness.

Depth 3: Bridge redeals the hand outright on a 4-pass "passed out" auction
(real rule), and the harness's greedy `_advance` (always `legal[0]`) always
picks "pass" first, so any depth >= 4 crosses into a *second* deal — a fresh
shuffle unrelated to the hands `on_first_decision` mutates (that hook always
fires at the game's very first-ever decision, i.e. deal #1). At depth >= 4
the swap was confirmed (field-by-field diff, see task-10 report) to change
ONLY P0's own re-shuffled `hand[0]` — hidden hands stayed `#13` in both
worlds and no opponent card identity appeared in the obs log — i.e. an
ill-posed experiment (mutated hands != examined hands), not a leak. Depth 3
stays inside deal #1, where the mutated hands and the examined hands
coincide, so the property is checked in the pre-play auction phase (this
seed's greedy policy never reaches trick play for bridge).
"""

from .harness import GameSpec, ReadinessProofs


class TestReadiness(ReadinessProofs):
    spec = GameSpec("cardlang_bridge", "bridge.cardlang", depth=3)
