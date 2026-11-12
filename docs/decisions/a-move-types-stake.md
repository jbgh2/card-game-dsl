## A move type's stake

A move type may say, on its own line under its name and before its
`when:`, that taking it is a **Wager** or a **Concession**
([glossary/stake.md](../glossary/stake.md)):

```text
move_type call_tichu {
  wager
  when: called[actor] is 0 and (not push_done or (number of cards in hand[actor]) is 14)
  effect { called[actor] := 100  quiet := 0 }
}

move_type throw_in {
  concession
  effect { thrown_in := true  decided := true }
}
```

A Wager stakes something the game settles later (Tichu's call, a bid);
a Concession gives up what was at stake for certain (Pinochle's
throw-in, a resignation). A move type with no row states no stake, and
a Seat Policy reads it as plain; the plain side of an offering — the
decline, the pass — is never marked: the mark is on what is staked.
Which corpus games state their stakes is issue #768's sweep, one game
per measured line. The row says what the move IS, never
what it is worth; the amount stays in the scoring that settles it
("Bidding patterns").

The row lives on the move, not at the offering site, because it holds
at every site the move is offered from (the contrast with the refused
`optional: true` property is in "Off-the-clock windows"). It is a rules
fact, not play advice: "the cautious one" depends on the hand and is
not stated in a game file, whose play-style assumptions live in the
test instruments.

**What reads it.** The row is static game text. It emits no
observation event, enters no information state, mints no action id, and
changes nothing the runtime does; the full-width per-seed goldens are
byte-identical under it, which is the pin that it is inert. Its reader
is a Seat Policy, through the checked game: the `ranked` Opponent
declines a staked move type wherever a plain one is on offer at the same
decision, and draws where none is.

**What the checker refuses.** Every row is readable or refused:

- a row on a game's own move type that no reachable `offer` presents —
  nothing reads it. An offer made inside a move
  type or procedure that nothing reaches presents nothing. A library
  move type's row is the library's statement for every game importing
  it, so a game that presents it nowhere is not refused;
- a row on a `Card`-parameterized move type — a card play is offered as
  its card, whose action id names no move type;
- `wager: true` / `wager: false` / `wager:` (the row is a fact, not a
  flag; a plain move is written by leaving the row out), and a row
  written after `when:` — as a flag or not, and a second row there
  when one already stands under the name — each refused at the word,
  naming the fix;
- `wager` and `concession` as the name of a state variable, zone or
  function — both are clause keywords, reserved as `outcome` is. A move
  type may still be named either, since a move type's name is never a
  bare value;
- in a game with a climbing round, a move type spelled like one of the
  engine's own actions (`pass`, an announcement token, the interrupt
  decline), whatever presents it: a seat would see the two alike, and a
  nullary `offer` of it would share the action's id. A Seat Policy
  reads a row by the move type an id was minted for, never by its
  spelling.

One cell is not refusable, by design: the row on the wrong side
(`wager` on `no_call`). The checker cannot read a stake off an effect —
the link from a move to the score it risks runs through the game's
phases — so the row is a declared contract the checker trusts, as
`max_length:` is, and execution is its witness: the Tichu line in
`tests/test_move_stake.py` reddens when the row moves to the decline.

Witnesses: Tichu's `call_tichu` and `call_grand_tichu`
([games/tichu.cardlang](../games/tichu.cardlang)); Pinochle's `submit_bid`
and `throw_in` ([games/pinochle.cardlang](../games/pinochle.cardlang)) —
the two games no uniform draw finishes.
