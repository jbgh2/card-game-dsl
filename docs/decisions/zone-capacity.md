## Zone capacity

Each library zone type carries a **capacity** — a column of the
zone-type registry ([library.md](../library.md), "Library zone types"),
total over every row. `Cell` (the one-card holding space) has capacity
1; every other library zone type is unbounded.

A transfer whose destination would exceed its type's finite capacity
fails loudly at runtime with a typed error naming the zone, its type,
the capacity, and the guard to write:

```text
zone 'slot[0]' is a Cell (capacity 1) and already holds 1 — the move
would overfill it; guard the move (`slot[0] is empty`)
```

The Owner Guard **stands behind** the game's own guards; the registry owns the
capacity class, so the check lives at the single transfer-executor
append rather than being re-derived per move type. An honest game guards
its placements (FreeCell's `cells[slot] is empty`, tic-tac-toe's
`square[at] is empty`), so the Owner Guard never fires on a correct game — it
converts a rules bug into a loud failure at the overfilling move, not a
silently dropped card. The `Point` row (an unbounded stack) is deferred
to its witness; see issue #118.
