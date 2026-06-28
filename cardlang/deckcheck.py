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

and counts the bounded forms at their worst case: an `if` contributes the larger
of its branches (a guarded deal is *taken*), and a `for each player` /
`to each <family>` deals once per player (the high end of a range). One window =
one iteration of a `repeats` phase: its `before_each` (which refills then deals)
plus the deals in its (non-repeating) sub-phases.
"""

from __future__ import annotations

from cardlang.ast import nodes as n
from cardlang.diagnostics import DiagnosticBag, DiagnosticError
from cardlang.stdlib.values import deck_size

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

    bag = DiagnosticBag()
    for phase in game.phases:
        _check_windows(phase, players, deck_zones, capacity, game, bag)
    if bag.has_errors:
        error = DiagnosticError(bag.items[0])
        if len(bag.items) > 1:
            error.add_note(bag.format())
        raise error
    return game


def _check_windows(
    phase: n.Phase,
    players: int,
    deck_zones: set[str],
    capacity: int,
    game: n.Game,
    bag: DiagnosticBag,
) -> None:
    """Check `phase` as one window (deck full at entry), then recurse into nested
    `repeats` phases (each its own reset boundary, hence its own window)."""
    peak, _ = _window_usage(phase, 0, players, deck_zones)
    if peak > capacity:
        span = phase.span if phase.span is not None else game.players.span
        bag.error(
            f"deck '{game.deck}' holds {capacity} cards but phase '{phase.name}' "
            f"deals up to {peak} from it in one hand with {players} players",
            span,
        )
    for sub in _nested_repeating_phases(phase):
        _check_windows(sub, players, deck_zones, capacity, game, bag)


def _window_usage(phase: n.Phase, carry: int, players: int, deck_zones: set[str]) -> _Usage:
    """Peak deck usage over one iteration of `phase`: its lifecycle hooks plus its
    statements and folded non-repeating sub-phases, threaded left to right. Nested
    `repeats` phases are excluded — they are their own windows."""
    peak = carry
    for item in phase.items:
        if isinstance(item, (n.BeforeEach, n.AfterEach)):
            p, carry = _seq_usage(item.body, carry, players, deck_zones)
        elif isinstance(item, n.Phase):
            if _repeats(item):
                continue  # separate window
            p, carry = _window_usage(item, carry, players, deck_zones)
        elif isinstance(item, n.Stmt):
            p, carry = _stmt_usage(item, carry, players, deck_zones)
        else:
            continue  # StateBlock, ActiveRules, LegalMoves, TransitionTo, …
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
    stmts: tuple[n.Stmt, ...] | list[n.Stmt], carry: int, players: int, deck_zones: set[str]
) -> _Usage:
    peak = carry
    for s in stmts:
        p, carry = _stmt_usage(s, carry, players, deck_zones)
        peak = max(peak, p)
    return peak, carry


def _stmt_usage(stmt: n.Stmt, carry: int, players: int, deck_zones: set[str]) -> _Usage:
    if isinstance(stmt, n.Movement):
        return _movement_usage(stmt, carry, players, deck_zones)
    if isinstance(stmt, (n.ForEach, n.EachSimultaneous)):
        # The body runs once per player (or once for a non-player ring); thread the
        # carry across iterations so a refilling body resets each pass.
        iters = players if stmt.role == "player" else 1
        peak = carry
        for _ in range(iters):
            p, carry = _stmt_usage(stmt.body, carry, players, deck_zones)
            peak = max(peak, p)
        return peak, carry
    if isinstance(stmt, n.IfStmt):
        then_peak, then_carry = _seq_usage(stmt.then_body, carry, players, deck_zones)
        else_peak, else_carry = (
            _seq_usage(stmt.else_body, carry, players, deck_zones)
            if stmt.else_body
            else (carry, carry)
        )
        return max(then_peak, else_peak), max(then_carry, else_carry)
    # RepeatUntil (runtime iteration count) and everything else draw nothing
    # statically boundable from the deck; usage is unchanged.
    return carry, carry


def _movement_usage(m: n.Movement, carry: int, players: int, deck_zones: set[str]) -> _Usage:
    """Deck usage after a single movement. A move *into* the deck refills it (usage
    resets to 0); a deal *from* the deck adds to usage; anything else is inert."""
    if m.dest is not None and _base_name(m.dest) in deck_zones:
        return carry, 0  # refill: cards go back to the deck
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
