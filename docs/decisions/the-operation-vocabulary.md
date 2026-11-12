## The operation vocabulary

Games relocate cards and resources, reveal and hide them, shuffle and
rotate. These operations are a small, closed vocabulary in three families,
not an open-ended set of verbs. The surface reads like a rulebook, but each
verb lowers to one of a few semantic primitives — the same
small-core/rich-library split that makes the trick a `round` configuration
rather than syntax ([principles.md](../principles.md)).

**Transfer** — relocating items between two places. One primitive underlies
every transfer verb: `deal`, `move` and `draw` are sugar that differ only in
defaults, not in kind — one word per meaning, so a second word for the same
node (a `burn`, a `muck`, a `transfer`) does not exist. A transfer carries a
selection (`all`, a count, or a `chosen`/`random` amount), an item noun, a
source place, and a destination (a single zone or `to each` recipient). A
count is an Integer, never a comparison or a flag: a count that does not
type exactly Integer — the permissive top included — is refused at check
time, as is a negative literal count; a Boolean hidden inside arithmetic over
the top is refused at play time. The
item noun is `cards`/`card` today; the noun stays open in the grammar so a
resource transfer (coins, chips) can one day be the *same* construct as a
card deal rather than separate syntax — but resource transfers and the
grammar's per-transfer `visibility =` override are deferred surface, rejected
by the checker ([roadmap.md](../roadmap.md), "Grammar surface deferred by the checker")
rather than left for the runtime to silently ignore.

A `to each` deal distributes the stated amount to every recipient. When the
amount is `all` and the deck does not divide evenly, `as-equally-as-possible`
deals it round-robin so the remainder is spread across the first recipients —
Getaway deals the whole deck across 3–8 hands this way (`deal all cards from
deck as-equally-as-possible to each hand`).

The checker enforces the production's valid combinations ("Surface totality"
below): `as-equally-as-possible` requires an `all` deal `to each` with no
selection mode (it distributes the whole source — or the whole `where` pool —
round-robin); `deal all … to each` *without* it is rejected as a trap (the
first recipient would drain the source); a gather (`move all cards to
<zone>`, no `from`) collects everything into a single zone — counted,
selected, or `to each` gathers are rejected; and the `in <zone>` form is
deferred ([roadmap.md](../roadmap.md), "Grammar surface deferred by the checker").

**Transfer `where` filter.** The `from` form of a transfer (any destination
shape) takes an optional `where <lambda>` clause, narrowing the *source pool*
to the cards matching the predicate — in source order — before the selection
draws from it: `move chosen 6 cards from hand[p] where is_pref_discard(card)
to discard[p]`. The four selection modes read the narrowed pool exactly as
they would read the whole source: `chosen`/`random` draw `count` from the pool
via the chooser/RNG; the default (dealt) form takes the pool's first `count` —
first *match* in source order, not top-of-source, since non-matching cards
were already skipped; `all` takes every matching card and leaves the rest
untouched in the source. Requesting more than the pool holds fails loudly,
identically to the unfiltered form. The destination forms compose: a filtered
`to each` deal narrows each recipient's pool in turn, and a filtered
`as-equally-as-possible` deal distributes the whole matching pool round-robin,
leaving non-matching cards in the source. An unfiltered transfer is
unaffected — the filter is a genuinely separate code path
(`execute.py::_select_filtered`), not a generalization of the unfiltered one,
so no existing game's card-selection behaviour changed when this clause was
added.

French Tarot's chien discard is the corpus's first use: the discard is six
chosen plain non-Kings (`cards in hand where is_pref_discard(card)`), and
when fewer than six exist the forced top-up draws from the non-bout atouts
alone (`where card.suit is atouts and not is_bout(card)`) — a per-card
predicate over which cards a decision may even draw from, distinct from the
*count* a plain `chosen N cards` transfer already expressed.

**Epistemic** — changing knowledge or order without relocating anything:
`reveal`, `peek`, `hide`, `announce`, `expose_top`, `forget`, `shuffle`. A
closed family; each is a prose statement (`shuffle deck`, `reveal proof to
all`) normalized to one IR node and resolved against a signature table
([library.md](../library.md) "Operations"). Their effect is defined in the
projection vocabulary of "Knowledge, visibility, and the projection model"
below.

**State-cycle** — advancing a state variable through a list of values, e.g.
`rotate pass_direction through [left, right, across, hold]`. Orthogonal to
the other two (it touches no zone): a single small construct.

**Surface: actions are prose, queries are calls.** Every operation above is a
prose statement — the built-in vocabulary reads as rulebook commands, one
surface for "what the game does." Call syntax (`player_holding(2 of clubs)`,
`rank_value(card)`) is reserved for value-returning functions and named
user-defined operations, which appear in expression position. The dividing
line is *do* versus *answer*: an operation acts (a statement with effects), a
function answers (a value in an expression). The families above are a
*semantic* classification — each lowers to a small set of IR nodes — and are
independent of this surface choice; the bounded cost of the prose surface is
one production per operation, added as the corpus needs it.

A new rulebook verb is presumed an instance of an existing family — transfer
sugar or an epistemic op — until a game proves it is genuinely none of them.
Adding a fourth family is a deliberate act, not the default response to a new
word.
