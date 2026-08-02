"""Static deck-capacity check.

A conservative compile-time pass: for each per-hand window it bounds the worst-case
deck *usage* — the most cards drawn from the deck between refills — and errors if
that exceeds the deck's capacity. So a too-large player count (an 8-player
Seven-Card Stud needing 60 cards from a 52-card deck, a 5-player Bridge needing 65)
is a compile error, not a runtime `ValueError` on an exhausted deck.

It tracks usage as a running count that **resets when the deck is refilled** — a
movement whose destination is the deck (`move all cards to deck`) puts cards back,
so deals before and after it draw from separate fills and must not be summed. The
window's bound is the peak usage at any single deal.

It never rejects a valid game: where a deal count can't be bounded statically it
adds nothing. Specifically it SKIPS

- `deal all …` (takes only what remains — can't overflow by construction),
- a non-literal amount (`deal hand_size …`, a state var or any expression),
- deals inside a `repeat until` (the iteration count is a runtime value),
- draws inside a MOVE effect (`offer`/rounds run moves, and a move can fire
  arbitrarily many times per hand — not statically boundable; the gate's
  domain is the scripted deals in phase bodies, recorded in issue #135),

and counts the bounded forms at their worst case: an `if` contributes the larger
of its branches (a guarded deal is *taken*), and a `for each player` /
`to each <family>` deals once per player (the high end of a range). One window =
one iteration of a `repeats` phase: its `before_each` (which refills then deals)
plus the deals in its (non-repeating) sub-phases.

Contract (decisions.md "Closed-domain completeness", write-time triage)
-----------------------------------------------------------------------
Assumes:      a resolved, typechecked, procedure-free AST.
Establishes:  deck-capacity soundness over its stated domain (the scripted
              deals in phase bodies — the SKIPS list above). A pure
              validator: the (unchanged) :class:`Game` flows on.
Now illegal:  a statically-boundable deal plan exceeding deck capacity.
Verified by:  tests/test_deckcheck.py.
"""

from __future__ import annotations

from typing import assert_never

from cardlang.ast import nodes as n
from cardlang.diagnostics import DiagnosticBag, DiagnosticError
from cardlang.domains import ITERABLE_ROLES, DomainSources, role_static_members
from cardlang.stdlib.enums import deck_size, rank_names, suit_names

# (peak usage reached, deck usage carried out) for a walked fragment, given the
# usage carried in. "Usage" is cards drawn from the deck since its last refill.
_Usage = tuple[int, int]


def check_capacity(game: n.Game) -> n.Game:
    """Raise a `DiagnosticError` if any per-hand window can draw more cards than the
    deck holds. A no-op for an unknown deck or a game with no deck zone."""
    capacity = deck_size(game.deck)
    if capacity is None:
        return game
    deck_zones = {z.name for z in game.zones if z.type_ref.name == "Deck"}
    if not deck_zones:
        return game
    players = game.players.high if game.players.high is not None else game.players.low
    # How many times each `for each <role>` body runs, read from the quantifiable-
    # domain registry rather than assumed. A hand-written rule like "players, or
    # once" would count a loop over a VALUE domain (`for each suit s: deal 15 cards
    # …`) as one iteration: it would demand four times what this gate checked, pass,
    # and fail mid-deal, where the executor requires a source to hold at least the
    # cards a deal asks for — the exact failure currency the gate exists to replace.
    # A new domain row arrives here already counted.
    sources = DomainSources(
        suits=sorted(suit_names(game.deck)),
        ranks=list(game.ranking) or sorted(rank_names(game.deck)),
        players=range(players),
        teams=game.partnerships,
    )
    counts = {
        role.value: len(role_static_members(role.value, sources))
        for role in ITERABLE_ROLES
    }

    bag = DiagnosticBag()
    for phase in game.phases:
        _check_windows(phase, players, counts, deck_zones, capacity, game, bag)
    if bag.has_errors:
        error = DiagnosticError(bag.items[0])
        if len(bag.items) > 1:
            error.add_note(bag.format())
        raise error
    return game


def _check_windows(
    phase: n.Phase,
    players: int,
    counts: dict[str, int],
    deck_zones: set[str],
    capacity: int,
    game: n.Game,
    bag: DiagnosticBag,
) -> None:
    """Check `phase` as one window (deck full at entry), then recurse into nested
    `repeats` phases (each its own reset boundary, hence its own window)."""
    peak, _ = _window_usage(phase, 0, players, counts, deck_zones)
    if peak > capacity:
        span = phase.span if phase.span is not None else game.players.span
        bag.error(
            f"deck '{game.deck}' holds {capacity} cards but phase '{phase.name}' "
            f"deals up to {peak} from it in one hand with {players} players",
            span,
        )
    for sub in _nested_repeating_phases(phase):
        _check_windows(sub, players, counts, deck_zones, capacity, game, bag)


def _window_usage(
    phase: n.Phase, carry: int, players: int, counts: dict[str, int], deck_zones: set[str]
) -> _Usage:
    """Peak deck usage over one iteration of `phase`: its lifecycle hooks plus its
    statements and folded non-repeating sub-phases, threaded left to right. Nested
    `repeats` phases are excluded — they are their own windows."""
    peak = carry
    for item in phase.items:
        match item:
            case n.BeforeEach() | n.AfterEach():
                p, carry = _seq_usage(item.body, carry, players, counts, deck_zones)
            case n.Phase():
                if _repeats(item):
                    continue  # separate window
                p, carry = _window_usage(item, carry, players, counts, deck_zones)
            case n.StateBlock() | n.ActiveRules() | n.LegalMoves() | n.TransitionTo():
                continue  # configuration blocks move no cards
            case _:
                # The residue of PhaseItem is exactly Stmt — mypy checks that on
                # this call, so a new phase-item block kind fails here loudly
                # instead of being silently skipped as a catch-all
                # `else: continue` would.
                p, carry = _stmt_usage(item, carry, players, counts, deck_zones)
        peak = max(peak, p)
    return peak, carry


def _nested_repeating_phases(phase: n.Phase) -> list[n.Phase]:
    """The `repeats` phases reachable below `phase` without crossing another
    `repeats` boundary — each is a separate window."""
    out: list[n.Phase] = []
    for item in phase.items:
        if isinstance(item, n.Phase):
            if _repeats(item):
                out.append(item)
            else:
                out.extend(_nested_repeating_phases(item))
    return out


def _repeats(phase: n.Phase) -> bool:
    return phase.qualifier is not None and phase.qualifier.kind == "repeats"


def _seq_usage(
    stmts: tuple[n.Stmt, ...] | list[n.Stmt],
    carry: int,
    players: int,
    counts: dict[str, int],
    deck_zones: set[str],
) -> _Usage:
    peak = carry
    for s in stmts:
        p, carry = _stmt_usage(s, carry, players, counts, deck_zones)
        peak = max(peak, p)
    return peak, carry


def _stmt_usage(
    stmt: n.Stmt, carry: int, players: int, counts: dict[str, int], deck_zones: set[str]
) -> _Usage:
    """Exhaustive over `Stmt`. This function had the silent default that bit:
    a `Block` fell through it and the gate went blind to every deal inside a
    procedure body. Now each statement kind states its deck behaviour by name,
    and a new kind is a mypy error here until it does."""
    match stmt:
        case n.Movement():
            return _movement_usage(stmt, carry, players, deck_zones)
        case n.ForEach() | n.EachSimultaneous():
            # The body runs once per member of the role's domain, read from the
            # registry (`counts`) — never assumed. Thread the carry across
            # iterations so a refilling body resets each pass.
            iters = counts.get(stmt.role, 1)
            peak = carry
            for _ in range(iters):
                p, carry = _stmt_usage(stmt.body, carry, players, counts, deck_zones)
                peak = max(peak, p)
            return peak, carry
        case n.IfStmt():
            then_peak, then_carry = _seq_usage(
                stmt.then_body, carry, players, counts, deck_zones
            )
            else_peak, else_carry = (
                _seq_usage(stmt.else_body, carry, players, counts, deck_zones)
                if stmt.else_body
                else (carry, carry)
            )
            return max(then_peak, else_peak), max(then_carry, else_carry)
        case n.AsBlock():
            # `as <p> { … }` rebinds only the acting player; for deck usage it is
            # an UNCONDITIONAL sequence — its body runs once, threaded exactly as
            # if written here (a deal inside it counts inline, like the Block arm).
            return _seq_usage(stmt.body, carry, players, counts, deck_zones)
        case n.Block():
            # A block (what `expand` turns a `run` into) is an UNCONDITIONAL
            # sequence: thread it exactly as if its statements were written
            # here, which is the whole point of the construct. A silent default
            # would be wrong in BOTH directions here: falling through would
            # return `carry, carry`, blinding the gate to every deal inside a
            # procedure body (undercount), while encoding the block as
            # `if true { … }` would route it through the IfStmt arm, whose
            # max-of-branches carry treats the body as skippable — a refill
            # inside a procedure would not reset the running total, and the same
            # program would be accepted written inline but rejected written as a
            # `run` (overcount).
            return _seq_usage(stmt.body, carry, players, counts, deck_zones)
        case n.Produces():
            # Exactly one arm runs (typecheck enforces arm exhaustiveness over
            # the variant's cases), so this is an if with one branch per arm:
            # worst case over arms, for both peak and carry. The arm is
            # mandatory rather than optional: `_stmt_usage` ends in
            # `assert_never`, so omitting it is a mypy error before it is
            # anything else — the gate cannot go quietly blind to deals
            # written inside a `produces:` arm.
            if not stmt.arms:
                return carry, carry
            usages = [
                _seq_usage(arm.body, carry, players, counts, deck_zones)
                for arm in stmt.arms
            ]
            return max(p for p, _ in usages), max(c for _, c in usages)
        case n.RepeatUntil():
            # The iteration count is a runtime value, so deals inside are not
            # statically boundable — skipped by design (module docstring). And
            # carrying `carry` straight across is SOUND, not lazy: `repeat
            # until` checks its condition first (runtime `_repeat_until`), so
            # the zero-iteration execution is always statically possible, and
            # "usage unchanged" is exactly that execution. A refill inside the
            # body helps only the executions that enter the body; the gate must
            # still account for the one that never does.
            return carry, carry
        case n.Turns():
            # A turn loop's iteration count is runtime data — the same
            # currency as `repeat until`, with the same soundness argument:
            # `until` is checked before the first turn (runtime `_turns`),
            # so the zero-iteration execution always exists.
            return carry, carry
        case n.Round():
            # A round moves cards between hands and the play zone — never a
            # draw from the deck — so it is inert to deck usage.
            return carry, carry
        case n.Offer():
            # An offered move's EFFECT can draw from the deck, but move effects
            # are outside this gate's domain entirely (it walks phase bodies,
            # and a move can be offered arbitrarily many times, so its draws
            # are not statically boundable — same currency as repeat-until).
            # Recorded as a domain limit in the module docstring and issue #135.
            return carry, carry
        case (
            n.EpistemicOp() | n.RotateStmt() | n.LetStmt() | n.AssignStmt()
            | n.Produce() | n.ContinueTo() | n.SkipToNextHand() | n.RunStmt()
        ):
            return carry, carry  # no card movement at all
        case _:
            assert_never(stmt)


def _movement_usage(m: n.Movement, carry: int, players: int, deck_zones: set[str]) -> _Usage:
    """Deck usage after a single movement. A move *into* the deck refills it (usage
    resets to 0); a deal *from* the deck adds to usage; anything else is inert."""
    if m.dest is not None and _base_name(m.dest) in deck_zones:
        # Cards go back to the deck. A full gather (`all`) or an unbounded
        # amount refills it — usage resets. A LITERAL return puts back exactly
        # k, and modeling that as a full refill made the gate blind to the
        # difference between returning one card and returning the pack:
        # deal 40, `move 1 cards from hand[0] to deck`, deal 16 was ACCEPTED
        # (carry reset to 0) and died mid-deal on the runtime's exhausted-deck
        # error — the crash this gate exists to convert into a compile error.
        # Subtracting k is exact for a valid game: the runtime errors when a
        # source holds fewer than a literal demand, so k cards genuinely
        # return.
        if m.amount == "one":
            return carry, max(0, carry - 1)
        if m.amount == "some":
            # A joint `some` return puts back AT LEAST one card (subset sizes
            # are >= 1), never the pack — crediting a full refill here
            # accepted a program that died mid-deal. One card is the sound
            # minimum credit.
            return carry, max(0, carry - 1)
        if isinstance(m.amount, n.IntLit):
            return carry, max(0, carry - m.amount.value)
        # `all` is a genuine refill. A NON-LITERAL amount also lands here and
        # is credited as one — an over-credit the gate has always made
        # (pre-existing; the sound credit for an expression that may evaluate
        # to 1 is `carry - 1`, like `some`); recorded, not silently widened,
        # since no corpus game returns an expression-counted amount to a deck.
        return carry, 0
    if m.source is None or _base_name(m.source) not in deck_zones:
        return carry, carry  # not a deck draw
    if m.amount == "all":
        return carry, carry  # takes only what remains; cannot overflow
    if m.amount == "one":
        per_dest = 1
    elif isinstance(m.amount, n.IntLit):
        per_dest = m.amount.value
    else:
        return carry, carry  # a non-literal amount (state var / expression)
    if m.dest_each:
        per_dest *= players  # `to each <family>` deals to every player
    drawn = carry + per_dest
    return drawn, drawn


def _base_name(expr: n.Expr) -> str | None:
    """The root zone name of a movement endpoint (`deck`, `deck[i]`, …)."""
    while isinstance(expr, (n.Subscript, n.Member)):
        expr = expr.obj
    return expr.name if isinstance(expr, n.NameRef) else None
