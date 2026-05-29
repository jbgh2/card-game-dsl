# Out-of-turn moves

**Tier 4 — low impact, defer until forced.**

Tichu bombs (four-of-a-kind or straight-flush of length ≥ 5) may be
played by any player at almost any moment — not just on their turn.
A bomb beats any combination on the table; it ends the current play
and the bomber leads the next trick.

The provisional surface:

```
phase play {
  legal_moves:       [play_combination, pass]
  out_of_turn_legal: bombs
}

move_type play_combination {
  ...
  out_of_turn_legal: when combination.is_bomb
}
```

The framing question: every other rule in the corpus is *restrictive*
("constrains: X; demands: a subset"). Out-of-turn-legality is the
inverse — it *permits* a normally-illegal action. The current
model.md framing ("rules constrain candidate moves") doesn't cover
this shape. Options:

- **Move-type property** `out_of_turn_legal: <predicate>` — the
  property lives on the move type, not on the phase. Phases that
  want to allow it list it; phases that don't, don't.
- **Permitting rules** — a new rule shape with `permits:` instead of
  `demands:`. Generalizes beyond out-of-turn play but adds a new rule
  category.
- **Phase-level `out_of_turn_legal:` list** — phases declare which
  move types are legal out-of-turn. Currently the provisional Tichu
  draft uses both this and the move-type property; one of the two is
  redundant.

A second game with out-of-turn moves (Egyptian Ratscrew's slapping,
some real-time variants) would force the framing decision. Until
then a Tichu-specific encoding is fine.

Related: decisions.md "Trick mechanic parameters vs rules"
catalogs the distinction between rules (filter legal moves) and
mechanic parameters (shape resolution). "Permit"-style out-of-turn
legality doesn't fit either category cleanly — it's about *who's
on the move*, not what the on-move actor can do.
