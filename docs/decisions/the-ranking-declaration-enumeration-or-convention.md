## The `ranking:` declaration: enumeration or convention

`ranking:` declares the game's rank strength order, strongest first. It is
optional (Coup and French Tarot declare none — the rank *namespace* always
comes from the deck; `ranking:` only orders it), and an enumeration may be
a partial permutation of the deck's ranks, which narrows the `Rank`
move-parameter domain (see "Declared parameter domains").

The clause takes one of two forms:

- **An explicit enumeration** — `ranking: A K Q J 10 9 8 7 6 5 4 3 2` —
  each entry a rank of the declared deck, no repeats.
- **A convention keyword** — one of the closed set `aces high`, `aces low`,
  `ace-ten`, `twos high`. A convention means *this deck's ranks in the
  standard French order, with the named adjustment*: `aces high` is
  A K Q … 2, `aces low` moves the ace to the bottom, `ace-ten` promotes the
  10 between ace and king (the Ace-Ten family: Skat, Schnapsen, Pinochle,
  Doppelkopf, Belote's non-trump order), and `twos high` moves the 2 to the
  top (the climbing-game order). The template is **filtered to the declared
  deck**, so one convention serves every French-ranked deck: `aces high`
  means A K Q J 10 9 8 7 on skat32. A convention is always a *complete*
  ranking of its deck. A deck with any rank outside the standard A..2 set
  (tarot78's atouts, tichu56's specials, coup15's characters) admits no
  convention — the resolver rejects it, naming the offending ranks, and the
  game enumerates explicitly instead.

The convention spellings are **reserved in ranking position**: an
enumeration whose entries spell exactly a convention name is read as the
convention (no deck names ranks `aces`/`high`, so nothing real is
shadowed). The resolver expands the convention into the operative tuple;
everything downstream — the Rank enum, the move-parameter domain, the
runtime's `rank_index`, the OpenSpiel action space — consumes the expanded
order and never sees the keyword. The registry is
`cardlang/runtime/values.py::RANKING_CONVENTIONS`, derived from the one
canonical `RANKS` tuple and reconciled against the grammar in both
directions by `tests/test_ranking_conventions.py`; suit-contextual orders
(trump promotions, Euchre's bowers) are out of this declaration's scope: a
game whose strength depends on the trick's context declares a Trick Order
with a `card_strength` function instead ("Trick Order"), and `ranking:` stays
the deck's one context-free order. What a Trick Order does not answer — a card whose IDENTITY changes with context, Tichu's Phoenix — stays
open ([open-questions/special-cards-declaration.md](../open-questions/special-cards-declaration.md)).
