"""Static deck-capacity check.

A conservative compile-time pass: for each per-hand window (the deals between deck
resets) it bounds the worst-case number of cards dealt *from the deck* and errors
if that exceeds the deck's capacity. So a too-large player count — an 8-player
Seven-Card Stud needing 60 cards from a 52-card deck, a 5-player Bridge needing 65
— is a compile error, not a runtime `ValueError` on an exhausted deck.

It never rejects a valid game: where a deal count can't be bounded statically it
contributes nothing rather than guessing. Specifically it SKIPS

- `deal all …` (takes only what remains — can't overflow by construction),
- a non-literal amount (`deal hand_size …`, a state var or any expression),
- deals inside a `repeat until` (the iteration count is a runtime value),

and counts the bounded forms at their worst case: an `if` contributes the larger
of its branches (a guarded deal is *taken*), and a `for each player` /
`to each <family>` multiplies by the player count (the high end of a range). The
per-hand reset (`move all cards to deck` is a gather, not a deck-source deal) means
one window = one iteration of a `repeats` phase: its `before_each` deals counted
once plus the deals in its (non-repeating) sub-phases.
"""

from __future__ import annotations

from cardlang.ast import nodes as n
from cardlang.diagnostics import DiagnosticBag, DiagnosticError
from cardlang.stdlib.values import deck_size


def check_capacity(game: n.Game) -> n.Game:
    """Raise a `DiagnosticError` if any per-hand window can deal more cards than the
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
    """Check `phase` as one window, then recurse into any nested `repeats` phases
    (each its own reset boundary, hence its own window)."""
    dealt = _window_deals(phase, 1, deck_zones, players)
    if dealt > capacity:
        span = phase.span if phase.span is not None else game.players.span
        bag.error(
            f"deck '{game.deck}' holds {capacity} cards but phase '{phase.name}' "
            f"deals up to {dealt} from it in one hand with {players} players",
            span,
        )
    for sub in _nested_repeating_phases(phase):
        _check_windows(sub, players, deck_zones, capacity, game, bag)


def _window_deals(phase: n.Phase, factor: int, deck_zones: set[str], players: int) -> int:
    """Worst-case cards dealt from the deck in one iteration of `phase`: its
    lifecycle hooks (run once) plus its statements and folded non-repeating
    sub-phases. Nested `repeats` phases are excluded — they are their own windows."""
    total = 0
    for item in phase.items:
        if isinstance(item, (n.BeforeEach, n.AfterEach)):
            total += _stmts(item.body, factor, deck_zones, players)
        elif isinstance(item, n.Phase):
            if not _repeats(item):
                total += _window_deals(item, factor, deck_zones, players)
        elif isinstance(item, n.Stmt):
            total += _stmt(item, factor, deck_zones, players)
    return total


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


def _stmts(stmts: tuple[n.Stmt, ...] | list[n.Stmt], factor: int, deck_zones: set[str], players: int) -> int:
    return sum(_stmt(s, factor, deck_zones, players) for s in stmts)


def _stmt(stmt: n.Stmt, factor: int, deck_zones: set[str], players: int) -> int:
    if isinstance(stmt, n.Movement):
        return _movement_deals(stmt, factor, deck_zones, players)
    if isinstance(stmt, n.ForEach):
        sub = factor * players if stmt.role == "player" else factor
        return _stmt(stmt.body, sub, deck_zones, players)
    if isinstance(stmt, n.EachSimultaneous):
        sub = factor * players if stmt.role == "player" else factor
        return _stmt(stmt.body, sub, deck_zones, players)
    if isinstance(stmt, n.IfStmt):
        then_dealt = _stmts(stmt.then_body, factor, deck_zones, players)
        else_dealt = _stmts(stmt.else_body, factor, deck_zones, players) if stmt.else_body else 0
        return max(then_dealt, else_dealt)  # worst case: the branch that deals more
    # RepeatUntil and everything else (assignments, offers, rounds, …) deal nothing
    # statically boundable from the deck.
    return 0


def _movement_deals(m: n.Movement, factor: int, deck_zones: set[str], players: int) -> int:
    """Cards a single movement draws from the deck, or 0 if it is not a deck-source
    deal or its count cannot be bounded."""
    if m.source is None:  # a gather (`move all cards to deck`) — not a deck draw
        return 0
    if _base_name(m.source) not in deck_zones:
        return 0
    if m.amount == "all":
        return 0  # takes only what remains; cannot overflow
    if m.amount == "one":
        per_dest = 1
    elif isinstance(m.amount, n.IntLit):
        per_dest = m.amount.value
    else:
        return 0  # a non-literal amount (state var / expression) — cannot bound
    if m.dest_each:
        per_dest *= players  # `to each <family>` deals to every player
    return per_dest * factor


def _base_name(expr: n.Expr) -> str | None:
    """The root zone name of a movement source (`deck`, `deck[i]`, …)."""
    while isinstance(expr, (n.Subscript, n.Member)):
        expr = expr.obj
    return expr.name if isinstance(expr, n.NameRef) else None
