## The expression register

The expression layer speaks the same English register as the statement layer:
queries and predicates are rulebook sentences, and their binders are
implicit. There is no method register (`zone.method(…)`) and no lambda
syntax; a query names its domain noun and binds the corresponding pronoun per
candidate — `player` in the player queries, `card` in the card queries,
`team`/`suit`/`rank` in the quantifiers. One spelling per concept governs
every form here ([principles.md](../principles.md)).

**The word/symbol line.** Words spell logic, equality, membership, and
quantification: `is`, `is not`, `in`, `not`, `and`, `or`, `any`, `all`,
`number of … where`. Symbols spell arithmetic, ordering, and state change:
`+` `-` `*`, `<` `<=` `>` `>=`, `:=` `+=` `-=`. This is one sentence a
designer can internalize — and it is Python's line, so the surface stays
familiar. English forms for assignment were considered and rejected: the
symbols carry no confusion cost, there is no compact English word for `>=`,
and the per-line verbosity cost would be the largest in the language. One
carve-out, the `offset_by` precedent: domain arithmetic goes word-spelled
when the symbol would mislead — rounded division is `divided by … rounded
up|down` (below), because no symbol spells a division that must name its
rounding. `is`,
`not`, and `number` are reserved words — no state variable, zone, function,
or binder may take one of these names.

**Every keyword is a whole word.** A keyword never matches inside a longer
run of word characters, in either direction: `letx = 3` is a syntax error
rather than a declaration of `x`, and `1and`, `up to10` and `moveall` are
refused for the same reason. Names that merely begin with a keyword stay
ordinary names — `letter`, `is_re`, `assets`, `some_var`. The rule exists
because the alternative is not an ambiguity a parser could report but a
*misreading*: the fused spelling has exactly one parse, and it is not the
one a reader takes from the page. A dropped space is therefore a diagnostic,
never a silently different sentence. This is separate from, and larger than,
the reserved-word question above: reservation says a word may not name a
value, whole-word matching says no word may be cut in half.

**Equality is `is` / `is not`** — plain equality, with no identity/equality
split to trip over. `a is not b` is a single operator, never `a is (not b)`.
The right-hand keywords `none` and `empty` are a closed set dispatching to
the absence and emptiness checks (`led_suit is none`, `hand[p] is not
empty`); every other operand is ordinary equality. `==`/`!=` are not part of
the language; the checker rejects them with the replacement spelling.

**Rounded division is `divided by … rounded up|down`** — a `term`-level
operator (the `offset_by` shape: `working_bid divided by base rounded up`),
Integer operands and result, with the rounding direction mandatory: there is
no bare quotient to misread as exact. `rounded down` floors toward negative
infinity and `rounded up` ceilings toward positive infinity — the English
words' own directions, whatever the operands' signs — and a zero divisor is
a typed runtime error. `*` binds tighter on both sides (`2 * bid divided by
base rounded up` divides the product); multiplying a quotient takes parens
(`(bid divided by base rounded up) * 2`). `/` and `%` are not part of the
language; the checker rejects them with the replacement spelling. `//`
cannot even be rejected: it introduces a comment, so a floor-division habit
written `a // b` reads as `a` with the rest of the line commented out —
write the word form.

**Card queries** mirror the player queries ("Player-collection queries"
below), binding `card` per candidate over a named zone:

- `cards in <zone> where <pred>` — the matching cards;
- `number of cards in <zone> [where <pred>]` — how many match (bare: the
  zone's size);
- `any card in <zone> where <pred>` / `all cards in <zone> where <pred>`.

**Aggregations** name their operation and bind `card` implicitly:

- `sum of <expr> over cards in <zone> [where <pred>]`;
- `highest <expr> over cards in <zone> [where <pred>] or <default>` and
  `lowest …` — the empty-set default is mandatory (the `or` clause), so an
  emptied zone yields the declared value instead of a crash; the default
  sits below `or`-precedence (parenthesize a compound default).

**Subset queries and aggregations** range over a zone's SUBSETS rather than its
cards, binding `subset` to each candidate set — the domain noun's singular, as
`card` is the card queries'. The binder is a card collection, so the predicate
asks about the set as a whole, which is the sentence no per-card form can say:

- `any subset of <k> [or more] cards in <source> where <pred>`, and the `all
  subsets …` / `number of subsets …` folds;
- `sum of <expr> over subsets of <k> [or more] cards in <source> [where <pred>]`,
  and the `highest`/`lowest` forms with the same mandatory `or <default>`.

The Subset Source is one zone, or two or more listed in brackets —
`[played[p], starter]`, the shape the language already uses for "these,
listed" (`teams:`, `one of [...]`, `x in [a, b]`), and read the same way: a
subset is drawn from any of them. The list is a phrase of the subset forms,
never a value — it cannot be bound or passed, and no other source slot takes
it, because a subset that straddles two zones cannot be built from subsets of
each, while a count or a quantifier over two zones is one over each. The
members' contents are pooled as written, so a card held by two members counts
once per member; the same zone listed twice is refused, by spelling at check
time and by identity at play time; one zone in brackets is refused as a second
spelling of the bare zone; and the enumeration bound applies to the pool.

The size clause is spelled with `of`, never `in`: `any <noun> in <expr>
where` already means "iterate the collection's members", so spelling subsets
with `in` would change the iteration domain with nothing on the page to mark
it. The size clause is mandatory in both modes — `of <k> cards` names one size
and `of <k> or more cards` every size from `k` up — because every game that
wants subsets states a floor or an exact count, and a subset domain with no
stated size has no rulebook reading. A size the source cannot supply yields no
subsets, and the fold's own empty answer applies; a size below one is refused,
since the empty set is not a subset the language enumerates. Enumeration is
deterministic (sizes ascending, combinations in source order) and bounded: a
source pool past sixteen cards is a loud runtime refusal, the same fixed engine
limit joint selection enumerates under ("Joint-predicate selection" above), from
the same home.

**Quantifiers bind their role noun implicitly**: `any player where <pred>`,
`all players where <pred>`, and the `team`/`suit`/`rank` forms (`any suit
where …` ranges over the deck's suits; `any rank where …` over the declared
`ranking:`, else the deck's ranks). The quantifier's own role set is closed at
those four; card and subset quantification are the query forms above.
`for each <role> <binder>:` keeps its explicit binder — it is a statement
loop, not a predicate, and its binder is genuinely chosen (`for each player
p:`).

The iteration-role set is closed, and its members are the four role nouns
(player/team/suit/rank), the content noun `card` — quantified through the
card-query form, not a quantifier — and `subset`. Every one of them is a
language-fixed noun: a game chooses the binder of a `for each`, a positional
domain query and a rule template, and never the binder of a query form.

**Membership is `in`**: `Q of spades in captured[p]` (zone membership),
`card.suit in [hearts, spades]` (a `[…]` list literal, never empty). The
grammar owns `in`'s three uses — range (`choose integer in 0 .. 13`), query
source (`cards in hand`), and membership — explicitly.

**Rank and suit values.** Suits and name-form ranks are bare enum values
(`card.suit is hearts`, `card.rank is K`, `card.rank is Duke`); the rank
namespace comes from the deck, not `ranking:` (Coup and Tarot declare no
ranking). Numeric ranks spell as validated strings wherever a rank is
expected -- a comparison (`card.rank is "10"`), an argument (`is_rank(card,
"10")`), a state's first value, an assignment -- and a bare `10` is an Integer
literal. One spelling rule judges every such literal: a numeric rank the deck
holds is admitted, a name-form value written as a string is refused with its
bare spelling, and a string outside the deck's values is refused. The string
spelling belongs to the literal: a String-valued name or expression is never a
rank. The checker also rejects every silently-false comparison shape: Rank vs
Integer and cross-enum comparisons.

**Transfer and reveal filters** are ordinary predicates with `card` bound
per candidate (`move chosen 6 cards from hand[p] where is_pref_discard(card)
to …`), the same `where` the card queries use.

**`repeat until` is the one iteration lexeme**, as a statement and as the
phase qualifier (`phase hand_sequence repeat until …`) — one lexeme is worth
more than the third-person `s`.

The rulings here were produced by the corpus-wide register analysis in
[design-notes/lexical-cleanup.md](../design-notes/lexical-cleanup.md), which
records the rejected alternatives (explicit binders, the `count`/`max`/`min`
comprehension spellings, noun sugar for counting) and the evidence.
