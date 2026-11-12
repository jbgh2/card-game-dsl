## The `suit ranking:` declaration

`suit ranking:` declares the game's Suit Ranking, strongest first and
space-separated, as `ranking:` declares ranks: `suit ranking: spades hearts
diamonds clubs`. It is optional; `suit_value(s : Suit) : Integer` is its one
reader, numbering the weakest listed suit 0, and a card is ranked by
`suit_value(card.suit)`. There is no convention form: the closed set of rank
conventions has no suit analogue, and a convention written here is refused
naming `ranking:`.

The list names every suit the deck declares (`Deck.suits`), each once, and may
leave out the deck's **special suits**, its card suits beyond the declared
ones (a 54-card deck's joker, Tarot's `atouts` and `excuse`, Tichu's
`special`). A declared suit left out is refused at check time, naming it; a
card of a left-out special suit reaching `suit_value` is refused when the game
runs, naming the suit and the declared list, because which cards reach the
read is a fact of zone contents (the partial-`ranking:` rule, for suits).

**The clause reorders nothing.** Unlike `ranking:`, which orders and narrows
the `Rank` move-parameter domain, `suit ranking:` leaves the `Suit` and
`Suit?` move-parameter domains and `for each suit` / `any suit where` in deck
order, so a Suit parameter's OpenSpiel action ids are the same with the clause
and without it (Bridge's `submit_bid(strain : Suit?)` is the witness). The
order is public and static, so it moves no information set.

A clause nothing reads is refused ("Surface totality", "A clause nothing reads
is refused"); `suit_value` is its reader. A `suit_value` call in a game
declaring no clause is refused at the call, or on the `uses` line when a
library makes it ("Family libraries"). A game whose strength order depends on
the trick's context, the trump suit above all, declares a Trick Order; its
functions may read `suit_value` for the part of the order that is fixed
(Skat's and Doppelkopf's jacks and queens, clubs high).
