## Meld groups: flattened zone families

There is no first-class meld-group object. A game's persistent card groups
— shared, growing, keyed, typed, scored as objects — flatten onto existing
machinery, and two rummy-family games prove the two halves:

- **The key flattens into zone-family names.** A group keyed by a small
  static domain declares one zone family per key value: Canasta's
  per-team per-rank melds are eleven team-indexed `TeamPile`
  families (`meldA[team] … meld4[team]`), plus the black-three going-out
  group and the red-three row; Gin's three arrangement slots are
  `meldA/B/C[player]`. The one index a zone family carries is the *owner*
  (a `zone_key_of` domain — a seat or a team); every other key is spelled
  in the name. Statement-level routing on a runtime key value is an
  if-dispatch over the key domain in the move's effect
  ([games/canasta.cardlang](../games/canasta.cardlang), `close_meld`), closed
  by construction because the key domain is the declared (possibly
  partial) `ranking:`.
- **Growth is ordinary transfer.** Either partner extends a standing meld
  with a plain guarded transfer on any of their turns; nothing about the
  group persists outside its zone.
- **Typed state is derived from composition, never stored.** Natural vs
  mixed, canasta-completion, wild-count legality are pure functions of the
  pile's contents, evaluated at every read by the game's own functions and
  game-local primitives (the guards at extension time, the scorers at hand
  end). Storing group state beside the cards would create a second source
  of truth.
- **Per-group scoring reads each zone as an object.** Canasta's hand
  settlement scores every meld pile by its own composition
  (`canasta_canasta_bonus`); the group *is* the zone.
- **Joint formation legality** is either a joint selection ("Joint-predicate
  selection" above — Gin's one-shot arrangements) or, where the action
  space cannot carry subset ids (a duplicate-card deck's multisets —
  [roadmap.md](../roadmap.md), "Grammar surface deferred by the checker"),
  an announce-then-stage decomposition whose
  per-card guards keep a legal completion reachable from every offered
  state (Canasta's `stage_card`/`close_meld`, the arrange-guard totality
  trick per card).

The forcing function this decision waited for was Canasta's shared growing
pile, and the flattening carried it without new surface. A first-class
group object becomes worth designing only if a game arrives whose group
key domain is *not* statically declarable (unboundedly many groups, or
keys outside any declared enumeration) — Cassino's builds are the nearest
candidate ([games/_candidates.md](../games/_candidates.md)).
