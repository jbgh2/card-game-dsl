"""The runtime's typed [[failure-channel]], keyed on a guard's ROLE.

The compile passes fail as diagnostics and the proofs fail with a witness; the
runtime fails as a typed exception (decisions.md "Closed-domain completeness").
This module is that third channel's definition site, and its types carry the
[[owner-guard]] / [[shadow-guard]] distinction rather than merely
reporting it: the type IS the classification, so a guard that changes role
changes its type. That is deliberate — a guard moving from authoritative to
redundant, or one layer to another, is a design change, and the type is what
makes it visible instead of silent (decisions.md, "A check's comment names the
downstream contract...", the role-bearing-channel case).

The compile stages and the runtime are the two halves of one channel, and a
channel is addressee AND span: a diagnostic names its Author and points at the
smallest span that signifies. `Located` is the runtime's half of the span,
carried on the refusal and stamped by the driver as it unwinds, so a refusal
reaching any caller — not only the one that renders today — knows the sentence
it escaped.

Contract
--------
Assumes: the caller has already decided the guard's ROLE and its AUTHOR — this
module encodes a decision, it does not make one. Establishes: every runtime
refusal of a game description is catchable as `GameDescriptionError`, and a
refusal that means an ENGINE gap is separately catchable as `ShadowGuardError`;
and a refusal that escapes a game sentence carries that sentence.
Illegal after this: catching `OwnerGuardError` or `ShadowGuardError` outside
tests. Harnesses catch the base — the base names what is wrong (this game is
illegal), the subtypes name which role caught it, and a harness that discovers
an engine gap must not silently treat it as a bad game. Illegal too: reading
`Located` as a classification. It says a failure knows WHERE, never who must
act, and the trees it spans answer different questions — a catch site asking
"whose fault" names a tree, never the carrier.

What is deliberately NOT in this tree
-------------------------------------
`PrimitiveReadError` (runtime/reads.py) addresses the primitive-module author,
not the game author, so it stays outside and roots at `RuntimeError`. That
disjointness is exactly why `GameDescriptionError` roots at `Exception` rather
than `RuntimeError`: rooting at `RuntimeError` would silently make every
`PrimitiveReadError` a `GameDescriptionError`, which is false about its
[[author]].

`IllegalMove` (runtime/state.py) is not a defect at all — the game author wrote
`error(...)` deliberately and the move being refused IS the rule working. It
stays outside this tree.

That is a statement about the RAISE SITE, and it does not settle what the same
exception means once it ESCAPES a playout, where no player was offered the move
it refuses: the rules produced no legal card and the refusal fired while the
candidates were still being counted. The Author is still the game author —
their rule refused, or their game reached a position the rule declares
impossible — so a caller reports it as theirs to look at, without calling the
file illegal. `IllegalMove` carries `Located` for the same reason a
game-description refusal does; carrying a span is not joining a tree.

`InstallationError` and `GameRegistrationError` are defined here but are
deliberately NOT under `GameDescriptionError` — see their own docstrings. They
live in this module because this is where the engine says who must act on a
failure, and "the person who installed it" and "the person who chose which
game files this process loads" are two of those people.
"""

from __future__ import annotations

from cardlang.diagnostics import Span


class Located:
    """Where a refusal happened, for a reader who must go and look.

    A mixin, and deliberately NOT an exception: it says a failure knows its
    place in the game text, which is a different question from who must act on
    it. Making it an exception would put one catchable name over
    `GameDescriptionError` and `IllegalMove`, whose separation is the point —
    and `except Located` would read as precise while catching a game fault and
    a not-a-fault together. The classes that carry it name themselves at the
    stamping sites instead, which is the enumeration a reader can check
    (decisions.md "Allow-list, never deny-list").

    Fields default at the class, so a refusal costs nothing until one is
    stamped, and every consumer reads the same three names whether or not the
    driver reached a stamping site.
    """

    span: Span | None = None
    phase: str | None = None
    zone: str | None = None

    def locate(
        self,
        *,
        span: Span | None = None,
        phase: str | None = None,
        zone: str | None = None,
    ) -> None:
        """Stamp what this frame knows. First writer of each field wins.

        The driver stamps on the way OUT, so frames offer their answers
        innermost first and the innermost is the smallest span that signifies
        — the sentence that refused, not the form around it. Last-wins would
        invert that and report the outermost frame, which is the whole-file
        diagnostic a span exists to avoid.
        """
        if span is not None and self.span is None:
            self.span = span
        if phase is not None and self.phase is None:
            self.phase = phase
        if zone is not None and self.zone is None:
            self.zone = zone


class GameDescriptionError(Located, Exception):
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


class InstallationError(Exception):
    """The engine's own data files are missing or malformed in this checkout.

    Author: whoever installed or checked out cardlang. Not the game author (no
    game is running — these fire while the engine is still loading itself), not
    the engine maintainer (the source is fine; what shipped alongside it is
    not). The corpus of games and the family libraries both load from paths
    relative to the package, so a partial wheel or a moved directory is a real
    and recurring failure with nobody else to blame.

    Deliberately NOT under `GameDescriptionError`: a harness catching that base
    to report "this game is illegal" must never swallow a missing corpus
    directory and carry on with an empty game list. Keeping it a sibling is
    what makes the two impossible to confuse.

    Having a type at all is what lets the site census key on the TYPE rather
    than on a list of file:line exclusions — an exclusion list would go stale
    the first time these modules were edited, and would silently swallow a
    genuine game-description guard added to them later.
    """


class GameRegistrationError(Exception):
    """A game file offered to the OpenSpiel adapter cannot be registered.

    Author: whoever chose which files this process registers — the caller of
    `cardlang.openspiel.game.register_game_file`, or whoever set
    `CARDLANG_GAMES`. Not the game author: the file may be legal cardlang and
    still be unregisterable, because its short name is already taken or its
    stem renders a name `pyspiel.load_game` cannot reach. A game the CHECKER
    refuses raises the checker's own `DiagnosticError`, which addresses the
    game author and reaches them with a span; that failure never arrives here.

    A sibling of `InstallationError` rather than the same type, though the two
    conditions rhyme — two files claiming one short name is the corpus's
    failure when both sit in `docs/games/` and this one when a path is
    offered. Their Authors differ, so a consumer that renders one renders it
    wrongly for the other: `cardlang/cli.py` answers an `InstallationError` by
    telling the reader their checkout is incomplete and to reinstall the
    package, which is advice a caller who passed a path cannot act on.

    Also not under `GameDescriptionError`, for the reason that keeps
    `InstallationError` out: a harness catching that base to report an illegal
    game must not swallow a registration that never happened.
    """
