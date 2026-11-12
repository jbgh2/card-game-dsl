## Rule demand forms

A rule's `demands:` clause names **a candidate-card set** — an expression
returning the cards a legal move may use, filtering a zone. `MustFollowSuit`'s
`demands: cards in hand where card.suit is state.led_suit` and Hearts'
`demands: cards in hand where card.suit is not hearts` are this form. The legal
move set is the intersection of every active rule's candidate set. Because that
intersection can empty — a void player cannot follow suit — a card-set
`demands` **must** declare an `if_impossible:` fallback: `hand` to play any
card, or `error(...)` to reject the move. There is no silent default (see "No
implicit actions"); a card-set rule without `if_impossible` is rejected at
resolve time.

**A rule binds at exactly one decision site: the trick round's card
decision.** Rules are consulted where card legality is computed
(`rules.legal_cards`) and nowhere else, so a rule is accepted only if it can
fire there — it must `constrains: play_to_trick`, and it must carry a
card-set `demands:` or an `exempts:`. The checker rejects the rest rather
than accepting surface it would silently drop ("Surface totality"):

- a `constrains:` naming any other move type, or omitted entirely;
- a rule with neither `demands:` nor `exempts:`, which cannot change what is
  legal however its `applies_when:` reads.

The one site is permanent: ADR-0011 records the ruling and the wide form
that lost.

**Inside a rule, `hand` is the cards the player on turn plays from.** A
rule is asked only at the trick round's card decision, so a bare `hand` in
any of its clauses (`applies_when:`, `demands:`, `if_impossible:`,
`exempts:`) names that decision's **Play Source**: the acting seat's instance
of the round's `source` family, or, under Delegated Play, the zone
`play_source_for` routes it to ("Delegated play"). It names that whatever
the game calls its zones — a game whose round says `source hands` plays
`MustFollowSuit` unchanged — and a rule needs nothing from a game to read
it, which is what lets the standard library's rules carry an empty contract
("Family libraries"). The reading is the rule's own and nobody else's:

- a binder a clause introduces outranks it, and a subscripted `hand[p]`
  names the game's declared `hand` zone, which a rule wanting that zone
  writes (a `hand[p]` with no `hand` declared is refused, naming the bare
  form);
- a function a rule's clauses call, directly or through another, may not
  read bare `hand` or a trick round's source family by name — a function
  body cannot see the Play Source. Keep the filter in the rule and have the
  function take a card: `cards in hand where follows(card, state.led_suit)`;
- a game whose rules read `hand` may not also declare a state variable named
  `hand`, or a zone named `hand` that is not kept per player — the rule
  could never read it by that name — and a rule parameter may not be named
  `hand`;
- a rule reading `hand` in a game that runs no trick round is refused: it
  would never be asked. A climbing round binds no rule.

The checker types the Play Source as the contents of the trick rounds'
`source` families, and judges what it reveals through those families'
projections, which a trick round already must show their owner — so a
rule's reads derive the same information sets as the round's own offer.

**State the constraint where the move is made instead.** A transfer's
`chosen N` binds a count (Hearts' pass is `move chosen 3 cards` -- the
`3` *is* the "pass exactly three" law); a move type's When Clause binds
its parameters (Stud's bring-in amount), which is why no corpus game
loses a constraint to the guards above.

**The one site is the design, not a deferral.** Every other decision is
legal or not by the construct that makes it: a move type's When Clause
(`when:`) admits or refuses each candidate, and a condition that reads the
whole position -- "every enemy man stands in a mill", `in_mill(at)` -- is
a named function the clause calls; a chosen transfer's `where` filter and
`chosen N` bind a card choice; a number a player names is bound by its
`choose integer in ...` range and `excluding`; a climb round's play is
legal by the round's `follows` function, which a game declaring it states
the condition in, while a Registered Engine's `follows` fixes the legality
and takes no addition; a decision that exists only under a condition is an
`offer` behind an `if`. These are the enforcing forms, and a constraint a
family shares is a function a family library carries, never a rule. The
refusals above are therefore permanent: a rule naming any move type but
`play_to_trick`, or activated where no trick round runs, is refused naming
the enforcing form its condition belongs in -- for a kernel move type, the
form `KERNEL_MOVE_FORMS` (`cardlang/stdlib/moves.py`) records as making it;
for a Registered Engine's play, that none admits it; for a rule naming no
move type, `play_to_trick` itself. The in-mill removal restriction is
`remove`'s When Clause over that function; mandatory capture is the
rulebook's own branch, an `offer` behind an `if` over `can_jump(t)`. What
would reopen this is a legality over the offered list as a whole -- a
maximum over the offer -- which neither a When Clause nor a card-shaped
rule states; it arrives as its own construct, and no corpus game or ladder
candidate has one.

**The move under inspection is bound as `action`.** A predicate over a
player's move — the `when <move-type> where …` trigger of a sub-phase
transition (see "Sub-phase entry and exit") — binds that move as
`action`, and its
fields expose the move's data: `action.card` (the card played),
`action.cards`, `action.card_count`, `action.actor`, `action.amount`. The
subject is always reached through `action`; there are no bare field names,
and it is never spelled `move` — `move` is the zone-transfer verb (see "The
operation vocabulary"). `action` is the same player-move object the `offer
action` syntax names. (The *concept* is still a move type; `action` is an
instance of one, as taken.)
