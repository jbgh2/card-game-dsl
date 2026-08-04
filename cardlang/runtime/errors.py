"""The runtime's typed failure channel, keyed on a guard's ROLE.

The compile passes fail as diagnostics and the proofs fail with a witness; the
runtime fails as a typed exception (decisions.md "Closed-domain completeness").
This module is that third currency's definition site, and its types carry the
Owner Guard / Shadow Guard distinction (glossary section 5) rather than merely
reporting it: the type IS the classification, so a guard that changes role
changes its type. That is deliberate — a guard moving from authoritative to
redundant, or one layer to another, is a design change, and the type is what
makes it visible instead of silent (decisions.md, "A check's comment names the
downstream contract...", the role-bearing-currency case).

Contract
--------
Assumes: the caller has already decided the guard's ROLE and its AUTHOR — this
module encodes a decision, it does not make one. Establishes: every runtime
refusal of a game description is catchable as `GameDescriptionError`, and a
refusal that means an ENGINE gap is separately catchable as `ShadowGuardError`.
Illegal after this: catching `OwnerGuardError` or `ShadowGuardError` outside
tests. Harnesses catch the base — the base names what is wrong (this game is
illegal), the subtypes name which role caught it, and a harness that discovers
an engine gap must not silently treat it as a bad game.

What is deliberately NOT in this tree
-------------------------------------
`PrimitiveReadError` (runtime/reads.py) addresses the primitive-module author,
not the game author, so it stays outside and roots at `RuntimeError`. That
disjointness is exactly why `GameDescriptionError` roots at `Exception` rather
than `RuntimeError`: rooting at `RuntimeError` would silently make every
`PrimitiveReadError` a `GameDescriptionError`, which is false about its Author.

`IllegalMove` (runtime/state.py) is not a defect at all — the game author wrote
`error(...)` deliberately and the move being refused IS the rule working. It
stays a plain `Exception`.

The corpus/checkout layout failures (`openspiel/registry.py`, `libraries.py`)
fire at import with no game running, so the faulty artifact is the checkout or
the wheel. They stay outside: a harness catching `GameDescriptionError` must
never swallow a missing corpus directory.
"""

from __future__ import annotations


class GameDescriptionError(Exception):
    """This game description is illegal, discovered at play time.

    The base a harness catches. It says only that the game is at fault; which
    ROLE of guard caught it is the subtype's job, and a harness has no business
    discriminating on that — see `ShadowGuardError`.
    """


class OwnerGuardError(GameDescriptionError):
    """Refused by the authoritative guard for a defect class.

    Business as usual: the game description is wrong, the guard that owns the
    class said so, and the message addresses the game author in their language.
    """


class ShadowGuardError(GameDescriptionError):
    """Refused BEHIND a leaked Owner Guard, which this names.

    Firing is always an engine gap, never merely a bad game: the Owner Guard
    for this class should have refused it earlier, so the message leads with
    the guard that leaked and carries the game context second.

    It stays under `GameDescriptionError` because the game description really is
    illegal — a harness should still stop. The subtype is what lets the SUITE
    hold a stronger line than a harness can: any `ShadowGuardError` raised
    during the tests is a failure, because "unreachable if the Owner Guard is
    correct" is only a guarantee while something enforces it.
    """

    def __init__(self, leaked: str, message: str) -> None:
        """`leaked` names the Owner Guard that should have caught this first —
        a pass, a registry, or a function. It leads the rendered message because
        the reader who must act is the engine maintainer, not the game author.
        """
        super().__init__(f"{leaked} should have refused this earlier — {message}")
        self.leaked = leaked
