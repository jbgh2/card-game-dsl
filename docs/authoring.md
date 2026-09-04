# Writing a game

The path from an empty file to a game you can play and hand to OpenSpiel.

This is for someone describing a card game. Adding a game to the corpus is a
further step with its own obligations —
[maintaining.md](maintaining.md), "When the corpus changes" — and the tool
itself is [implementation.md](implementation.md) and
[building.md](building.md). Nothing below requires either.

## What a game file is

A game file is one `game { }` declaration plus the definitions that support it
— Move Types, functions, rules — in plain text. It needs no particular
directory: the front end takes a path, so a file you keep anywhere is a game
the checker and the playout driver both read.

Inside the braces a game names its seats, the bound on its length, the
Component Set it deals from, the zones its cards live in, the state variables
it keeps, the phases it runs, and how it is won. That is a complete game:

```cardlang
game HighCard {

  players: 2
  max_length: 20

  cards: standard52
  ranking: aces high

  zones {
    deck          : Deck
    hand[player]  : Hand<player>
    shown[player] : PublicHand<player>
  }

  state {
    score[player] : Integer = 0
  }

  phase deal {
    shuffle deck
    for each player p: deal 2 cards from deck to hand[p]
  }

  phase showdown {
    each player simultaneously:
      move chosen 1 card from hand[player] to shown[player]

    let a = sum of rank_value(card) over cards in shown[0]
    let b = sum of rank_value(card) over cards in shown[1]
    if a > b { score[0] += 1 } else { score[1] += 1 }
  }

  winner: highest score
}
```

Every construct in it is spelled the same way somewhere in `docs/games/`: the
sealed simultaneous commit is Goofspiel's, the per-seat deal is Kuhn Poker's.
Reading two or three corpus games beside your own is the quickest way to find
the spelling of something you can picture but cannot name — those files are
worked examples for exactly that, and each is complete enough to play from
cold.

Each clause is owned elsewhere:

- `players:`, `direction:` — the seats and the turn direction
  ([model.md](model.md)).
- `max_length:` — a declared contract on how long a game may run, not a hint
  ([decisions.md](decisions.md), "Game length as a declared contract").
- `cards:` — the Component Set
  ([library.md](library.md), "Built-in component sets").
- `ranking:` — the deck's context-free rank order ([decisions.md](decisions.md),
  "The `ranking:` declaration: enumeration or convention").
- `zones { }` — the clause that decides what each seat sees; see below.
- `state { }` — the state variables, lexically scoped
  ([decisions.md](decisions.md), "State scoping (lexical)").
- `phase` — the sequential program, phases running in declaration order
  ([model.md](model.md)).
- `winner:` / `loser:` — the game result ([decisions.md](decisions.md),
  "Game result: `winner:` and `loser:`").

## The loop: check, play, read the information state

Check the file. The checker is silent on success and exits non-zero on
failure:

```console
$ cardlang check high-card.cardlang
```

Then play one uniform-random self-play, asking for a seat's view at the end:

```console
$ cardlang play high-card.cardlang --seed 3 --info-state 1
HighCard — 2 seats, uniform-random self-play
  returns      P0 0, P1 1
  best return  P1
  decisions    2
  seed         3

information state, seat 1, at the terminal position:
P1|deck=#48;hand[0]=#1;hand[1]=[5♣];shown[0]=[4♥];shown[1]=[8♦]|state:score={0:0,1:1}|obs:('move', 'deck', 2, 'hand[0]', 2);('move', 'deck', 2, 'hand[1]', ('5♣', '8♦'));('chose', ('8♦',));('move', 'hand[0]', 1, 'shown[0]', ('4♥',));('move', 'hand[1]', ('8♦',), 'shown[1]', ('8♦',))
```

Omitting `--seed` draws one and reports it, so any run repeats. `cardlang
<file>` with no command named reads as `check`, and `python -m cardlang` runs
the same front end straight from a source tree.

`--info-state` needs the game to have asked someone to choose: a game that
reaches its end with no decision in it prints the summary, then refuses the
seat's view because the engine exposes no world to project from (issue #555).
An early skeleton often has no decision yet, and that refusal is what it looks
like.

The last line is the point of the language. It is the seat's **information
state** — the per-seat artifact OpenSpiel consumes; the information set is the
equivalence class it induces, and the two are not interchangeable. It has
three segments:

- **Zones, as seat 1 sees them.** `hand[1]=[5♣]` is that seat's own remaining
  card by identity. `hand[0]=#1` is the opponent's, a bare count. `deck=#48`
  likewise. `shown[0]` and `shown[1]` are public to everyone.
- **State variables**, which are public in full to every seat.
- **The observation log**: what this seat saw happen. Its own deal arrives as
  identities, `('move', 'deck', 2, 'hand[1]', ('5♣', '8♦'))`; the opponent's
  arrives as a count, `('move', 'deck', 2, 'hand[0]', 2)`.

No observation rule produced any of that. The `zones { }` block did — the
declared zone types carry the per-observer Projections, and the information
state is derived from them plus the events the moves emit. That derivation is
the reason the language exists rather than hand-writing each game against
OpenSpiel (`CLAUDE.md`, "OpenSpiel is the target, and deriving information
sets is the hard part"), and it is what the next section is really about.

One asymmetry to hold onto, because nothing warns about it: **hidden
information lives only in zones.** A state variable is public by construction,
so a concealed bid modelled as a state variable leaks, and the checker says
nothing — model it as zone contents instead
([decisions.md](decisions.md), "Hidden information lives only in zones; state is public").

## Zones and visibility

Each entry in `zones { }` gives a zone a **zone type**, and the zone type
carries the per-observer Projection. That single choice is what the paragraph
above derives everything from. Indexing a zone by `[player]` makes it a zone
family, one instance per seat, and the index is the observer the owner-keyed
types project to.

The closed set of zone types, each shown with the Projection it encodes, is
the table in [library.md](library.md), "Library zone types". Read it before
writing the block; picking from it is usually a ten-second decision once you
can say who is meant to see what. `Hand<player>` is identity to its owner and a
count to everyone else; `PublicHand<player>` is owned but visible to all;
`HiddenPile<player>` is a resting pile its owner conceals; `Muck` is trivial to
everyone, its contents invisible going forward while whatever was already
observed of those cards still stands.

A wrong choice here is not a crash and not a diagnostic — it is a different
game, one that runs and proves things about the wrong information sets. This
is the clause to check twice. The model beneath it, and what the projection
vocabulary means, is [decisions.md](decisions.md),
"Knowledge, visibility, and the projection model"; the declaration side alone
is [decisions.md](decisions.md), "Per-observer visibility on zones".

## Decisions and moves

A game elicits a decision in one of a few ways, and which one you want follows
from what is being decided:

- **Which move** — `offer to <player> one of [move_a, move_b]`, a declared
  Offering of Move Types, each with its own `when:` guard and effect.
- **A structured interaction** — trick play, an auction, a betting street, a
  poll: the `round` forms, which are the kernel construct these all configure
  ([decisions.md](decisions.md),
  "Interactive decisions: a kernel and an in-DSL standard library"). The turn
  loop beneath them is [decisions.md](decisions.md), "The `turns` form".
- **An integer** — `choose integer in 0 .. 13`, optionally capped or excluding
  one value ([decisions.md](decisions.md), "`choose` as expression"). Integer
  decisions only; the section is explicit that the others are not `choose`.
- **Which cards** — a transfer with a `chosen` selection, the vocabulary and
  its `where` filter being [decisions.md](decisions.md),
  "The operation vocabulary".

A single-actor stretch runs inside `as <player> { }`
([decisions.md](decisions.md), "Single-actor decisions: the `as` block").

Two facts about card selection are worth knowing before you write a discard,
because both shape the game tree you get:

**`move chosen N cards` is N sequential single-card decisions**, not one
decision over N-card subsets. Each draws a bare card from the source. The
observation log shows the movement as one event, but the tree branches N
times.

**One decision over subsets is `where jointly`, and it has a hard
prerequisite.** The joint form binds the candidate *set*, so the predicate can
test the cards together — the load-bearing test of any meld game. But the
subset universe is not derivable from the predicate's text: it comes from a
**registered per-predicate codec keyed on the predicate's root call**, and
that codec is engine Python. A predicate with no registered codec — or no root
call at all — is refused at action-space construction, loudly. If you are not
editing the engine, the joint form is closed to you, and the alternative the
spec prescribes is the announce-then-stage decomposition: one move announces,
another stages a card at a time. Both the requirement and the decomposition
are [decisions.md](decisions.md), "Joint-predicate selection", with the
staging shape at [decisions.md](decisions.md),
"Meld groups: flattened zone families".

## Libraries

`uses <name>` imports one whole family library — the tier between game-local
definitions and the stdlib, holding definition forms plus state. It is a whole
library at a time, never a named-definitions manifest, and it does not
inherit: a game-local definition under an imported name is an error, not an
override. The tier and its rules are [decisions.md](decisions.md),
"Family libraries".

The library's `requires { }` block is its **contract**: what the including game
must declare for the import to resolve. State variables, and also zones — each
named with the zone type the library's definitions were written against, since
that type is what fixes the per-observer Projection they assume. The contract
is checked at the `uses` line, so an unmet one is reported to you rather than
as an undeclared name somewhere inside the library. The libraries live in
`docs/libraries/`, and reading the one you are importing is the fastest way to
write the `zones { }` and `state { }` entries it demands — each `requires` row
is annotated with what it holds and why the library cannot own it.

For poker, `uses poker_betting` brings check, bet, call, raise and the ring
predicates; `fold` stays game-local, because where a folded card goes is a
fact about your zones. The showdown is a Primitive your game *declares*
rather than implements, and which one follows from where the holding sits —
`pot_share` ranks each entrant's own cards and so reads the zone families
`hole` and `upcards` **by name**, while the shared-board form reads `hole`,
`shown` and `board`. Naming your zones to match is what lets a new variant
reuse the family's showdown arithmetic without engine work. The whole
arrangement is the betting bullet under [library.md](library.md), "Mechanics".

## When the checker refuses

A diagnostic carries a span and a message, and the message names the fix
wherever the guard knows it:

```console
$ cardlang check bad.cardlang
bad.cardlang:7:16: error: `deal all ... to each` would give the whole source to the first player; use `as-equally-as-possible` to distribute it
```

Exit codes separate the two kinds of failure: `1` when the game file is at
fault, whether a compile stage or the playout says so, and `2` when the
invocation cannot be carried out at all — an unreadable path, a seat the game
does not seat, a broken checkout.

One class is the exception, and it is the one a first file is likeliest to hit:
a **syntax** error is still reported in the parser generator's vocabulary,
describing a terminal that fails to match in a parser context, and pointing at
where the grammar gave up rather than where the file went wrong. A missing `}`
is the usual cause; look above the reported line for an unclosed block. This
is a known defect, tracked as issue #551 — every diagnostic past the parser
speaks the language's own terms.

## Reaching OpenSpiel with your own game

The corpus registers itself from `docs/games/`, but a file of your own reaches
the adapter directly:

```python
import pyspiel
from cardlang.openspiel.game import register_game_file

short_name = register_game_file("high-card.cardlang")
game = pyspiel.load_game(short_name)
```

`register_game_file(path)` checks the file, registers it under the same naming
rule the corpus uses — `cardlang_` plus the file stem with hyphens turned to
underscores, so `high-card.cardlang` becomes `cardlang_high_card` — and
returns that short name. A name already taken is refused, naming both files.

`CARDLANG_GAMES` does the same without code: an `os.pathsep`-separated list of
files or directories, registered when `cardlang.openspiel.game` is imported.

Such a game gets the adapter and its derived information states, on the terms
[decisions.md](decisions.md), "OpenSpiel compilation" sets out. What it does
not get is the readiness proof battery — the per-game proofs under
`tests/openspiel_ready/` are corpus-bound, keyed to files in `docs/games/`, so
no proof module covers a game outside it (issue #25). The adapter's derivation
is the same either way; the standing evidence that it holds for *your* game is
what is absent.

## Where the language cannot go yet

You will meet a rule the language cannot express. The rule for what to do is
`CLAUDE.md`, "The game does not bend to the harness", and it is worth stating
plainly here because the tempting move is the wrong one: **do not trim the
game to fit.** A trimmed game reads as the real one and quietly measures
something else, and every proof taken against it is then a proof about a game
nobody plays.

Keep the game whole, and let the gap be a gap. If the language should grow to
meet it, the gap wants a witness — the game file that needs it — and an issue
on the [tracker](https://github.com/jbgh2/card-game-dsl/issues). That is how
the language grows: corpus-first, one forcing game at a time.

## Contributing the game to the corpus

If the game should join `docs/games/`, that is a further step, and it has
obligations a private file does not:
[maintaining.md](maintaining.md), "When the corpus changes" holds all of them
— what the rulebook twin carries against its `.cardlang`, and the
hand-authored tables a new game joins beyond the glob, each of which classifies
a game in a way no glob can derive and reddens until you fill it in.
