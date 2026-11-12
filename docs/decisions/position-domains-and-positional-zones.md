## Position domains and positional zones

Solitaire layouts (and any game whose rules address *places* — columns,
cells, piles-by-location) are described with **declared position
domains**: per-game, finite, integer-keyed value domains, declared in a
game-level `positions { }` block:

```text
positions {
  column : 1..7      // Klondike's seven tableau columns
}
```

Each entry mints a domain usable in exactly two surface slots:

- **Zone-family index**: `tableau_up[column] : Cascade<column>` — one
  zone instance per member, subscripted by any integer-valued expression
  (`tableau_up[c]`, `tableau_up[3]`). The declaration's type argument
  names the same domain as the index, like `Hand<player>`.
- **Move-parameter domain**: `move_type build(src : column, dst :
  column)` — enumerated into the guard-filtered cross-product like
  `Suit`/`Rank`/`Player` ("Declared parameter domains"), with one
  OpenSpiel vocabulary action id per combination. The runtime and the
  static action space enumerate the same declared `lo..hi` members by
  construction.

The bounds are non-negative integer literals with `lo <= hi`, and a
domain holds at most 256 members (a layout wider than that is a
declaration error, not an action-space explosion). A declared name may
not collide with a built-in domain id or type name (`player`, `suit`,
`Rank`, `Card`, `Integer`, …) — the built-in registry and the declared
block are reconciled by rejection, so the two sources can never disagree
about a name. A `board:` clause mints a **named-member** domain (`cell`,
string members) on this same substrate — same collision guard, same cap,
same two surface slots — detailed in "Boards and cells" below.

**Positions are unowned.** No observer *is* a column, so a
position-indexed family has no owner: every observer receives the zone
type's `others` projection. Consequently a zone type whose owner and
others projections differ (`Hand`, `HiddenPile` — any row with two
distinct projections) cannot be indexed by a position; the checker
rejects it, because its owner projection would be silently unreachable.
Uniform-projection types (`Cascade`, `HiddenStack`, `Foundation`,
`Cell`, `PlayerPile`, …) may.

**Iteration and state-indexing reject loudly; quantification is admitted.**
A position domain is not a seat and not an iteration role: `for each
column c`, `each column simultaneously` and a position-indexed `state`
variable are all rejected with diagnostics (deferred, recorded in issue
#111). A `state` variable may be typed by a board's named-member domain
(`last_at : cell? = none`), read and written as a `Player?` variable is,
and a per-seat or per-team store of one (`lastp[player] : cell? = none`)
is declared and read the same way; a `none` it holds is refused at play
wherever a square must be named;
an integer position domain is no `state` type, the refusal naming
`Integer` as the type that remembers its member
(tests/test_typed_position_state.py). Quantifiers
range over a position domain's members like any other quantifiable
domain — `any column where …`, `all columns where …`, `number of columns
where …`, and the set of the members satisfying a predicate, `columns
where …`, each also over a collection of the domain's members (`columns
in [1, 2] where …`); for a board the register adds the lines a collection
form ranges over, detailed with `lines(k)` in "Boards and cells" below
(tests/test_cell_queries.py, tests/test_cell_set_form.py). A position-indexed family
is always subscripted: no seat owns one of its instances, so a bare name
has nothing to mean ("Per-observer visibility on zones", "A family named
bare is the acting player's own").

**Mixed-facing piles are two zones.** Per-position visibility inside one
physical pile (Klondike's columns: face-down below, face-up above) is
represented by *zone decomposition*, never by per-card facing state: a
`HiddenStack<column>` family under a `Cascade<column>` family, with the
flip written as an ordinary transfer between them. The flip's observation
event derives from the two declared projections (count from the hidden
side, identity from the open side) exactly like every other transfer —
per-position visibility adds **nothing** to the projection model. The
analysis and the rejected alternatives are in
[design-notes/positional-zones.md](../design-notes/positional-zones.md).

**Sequence orientation.** A zone's contents are a sequence: arrivals
append at the end (placing on top of a face-up pile — `top_of` reads the
end, `bottom_of` the front), and the dealt take (`draw`/`deal` with no
`where`) removes from the front (FIFO). For a shuffled stock the ends are
indistinguishable; where order is observable the FIFO contract is the
physical one — Klondike's unshuffled redeal (`move all cards from waste
to deck`) cycles the stock in exactly the order the last pass drew.
Filtered transfer selects in source order and appends in source order,
which is what moves a cascade's run as an intact unit ("stack movement"
is a usage pattern of the existing transfer verb — a rank filter denotes
the suffix — not new surface). Sequence *knowledge* is derived, not
declared: an identity-entitled observer saw every arrival event, so order
falls out of the observation log under perfect recall.

`top_of(z)` / `bottom_of(z)` are native functions over any card
collection; on an empty collection they fail loudly at runtime (guard
first — `Z is not empty`). Their use in a move *guard* is subject to the
same discipline as every guard expression: legality must not read
information the decider is not entitled to, which the per-game
legal-action-agreement proofs police (`tests/openspiel_ready/`).
