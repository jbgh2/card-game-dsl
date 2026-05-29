# Choice-embedded routing

**Tier 4 — low impact, defer until forced.**

Tichu's Dragon, when it wins a trick as a single card, *gives the
trick to an opponent of the Dragon-holder's choice* — including the
Dragon's own 25 points. The chooser is the trick winner; the
destination is one of two opposing players' team piles.

The provisional surface, inside the `TichuTrickRouting` function:

```
elif winner played Dragon as the winning single:
  all cards from trick_pile to captured[team of (winner chooses one opponent)]
```

The `winner chooses one opponent` clause embeds a player decision
inside the routing function. Existing routing functions in the
corpus are pure: deterministic on `(played_cards, trick_state,
outcome)`.

Design choices:

- **Routing function may include `choose()` calls** — the function
  becomes a `Routing → choice → routing` mini-protocol, with the
  choice surfacing as a move-type-equivalent event in the knowledge
  stream.
- **A separate `post_trick_routing_choice` phase** — fires only when
  certain conditions hold (Dragon won). Adds phase machinery for a
  small routing decision.
- **A `routing_chooser:` parameter on the Trick mechanic** — the
  mechanic accepts a chooser when one is needed, and the routing
  function reads its decision.

Each option trades simplicity at the use site against changes to
the Trick mechanic's contract.

A second game with player-chosen routing (rare; possibly some Skat
declarer-routing variants, or Spite and Malice's give-stack choices)
would force the decision. Until then a Tichu-specific extension is
fine.

Related: [routing-as-constraint](routing-as-constraint.md) on the
broader category of phase-attached configuration beyond rules.
