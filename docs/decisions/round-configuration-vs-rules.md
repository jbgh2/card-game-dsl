## Round configuration vs rules

Some phase-level configuration is *not* a rule even though it looks like one. A
trick `round` carries a `winner` function and optional `trump` / `early`
clauses, and the surrounding body does the routing. These shape *what happens
after a play* (who is selected, when the pass ends early, where the cards go);
rules shape *which plays are legal*.

The categories don't unify:

- **Rules** are filters on the candidate-move set. They attach to phases via
  `active_rules:` and are consulted before each move.
- **Round configuration** (`winner`, `early`, `trump`) and the post-round body
  routing run once per trick (or per play) and produce the trick's effect.

Getaway's first-trick-to-waste behaviour is the canonical mistake: written as a
rule (`rule FirstTrickAlwaysGoesToWaste`) it has nothing to constrain — its
effect is *where the cards go*, an ordinary body transfer after the round:

```cardlang-fragment first_trick_phase
phase first_trick {
  active_rules: [MustLeadAceOfSpadesOnFirstPlay]
  round play_to_trick from leader over all players source hand into trick_pile
        winner highest_of_led_suit
  move all cards from trick_pile to waste
}
```

Hearts' `highest_of_led_suit` is the round's `winner` function, not a rule. The
clean test: if the configuration's effect is "filter legal moves before play,"
it is a rule; if its effect is "shape the trick's resolution after play," it is
round configuration or body routing.

**Routing has two surface forms, both ordinary body statements.** When the
routing is a single unconditional transfer, it is one statement after the round
(Hearts; Getaway's first trick: `move all cards from trick_pile to waste`). When
it branches — Getaway routes the pile to the trick winner on a tochoo (pickup)
but to the waste otherwise — it is an `if` over the round's terminal state:

```cardlang-fragment play_phase
phase play {
  round play_to_trick from leader over players where not eliminated[player]
        source hand into trick_pile winner highest_of_led_suit early on_play_off_led_suit
  if state.trick_terminated_early { move all cards from trick_pile to hand[winner] }
  else { move all cards from trick_pile to waste }
}
```

The body reads the round's `winner` (the selected player) and its terminal
`state` (e.g. `state.trick_terminated_early`). Routing is just body
statements — there is no separate routing construct.

**A finished round's `state.` is read until its window closes.** The window
closes when a decision other than a round's is asked — an `offer`, a `choose`,
a chosen movement, a `turns` ring, a poll — or when the phase that ran the
round ends. A read past it is refused at play, never served the old frame, so a
poll after the tricks, or the next hand's bid, cannot read the last trick. A
value a later decision needs is copied into a declared state variable directly
after the round, where every seat's information state renders it. A decision
inside a round reads that round's live frame, which no window closes.

**Contextual card properties are the game's Trick Order.** Some games
interpret card properties contextually rather than from the card's intrinsic
fields: Skat's jacks are trumps regardless of printed suit, and in Doppelkopf
the queens and jacks are too. Those games declare a Trick Order ("Trick Order"
below): three functions, `is_trump`, `follow_class` and `card_strength`, that
say what a trump is, what class a card follows as, and how strong it is; the
kernel's winner and follow test read them. A game that declares none keeps the default —
printed-suit equality, and the trump suit its round names — and the presence
partition refuses any mixture of the two vocabularies.
