## Family libraries

A **family library** is the import tier between game-local definitions and the
standard library. It holds exactly the definition forms a game already holds — move_types, rules,
functions, procedures — plus the two state clauses `state` and
`requires`, and it lives in
`docs/libraries/<name>.cardlang`, beside the corpus and maintained with it. The
stdlib is the part maintained with the *language*; that boundary is the one
[design-notes/primitive-sidecars.md](../design-notes/primitive-sidecars.md) exists
to defend, and the tier exists so a family of related games need neither paste
shared machinery per game nor promote domain knowledge into the stdlib.

A game names one whole library at a time:

```text
game SevenCardStud {
  uses poker_betting
  ...
}
```

Whole-library, never a named-definitions manifest: the line stands in for the
rulebook sentence it replaces ("betting proceeds as in standard poker" is
Pagat's own practice), and that is what keeps the read-cold acceptance test
intact — the readable unit becomes the game file plus its *named* libraries. A
game may `uses` several libraries; repeating one is an error, because the
repeat imports nothing further.

Resolution is flat and two-level: game, then the named libraries, then the
stdlib. There is no library-imports-library. Imports are pure name resolution —
`resolve` splices each named library's move types, functions, procedures and
provided state into the game before any other name check runs, so what flows on
is one flat game. No later pass knows imports exist, with three recorded facts
as the exceptions. Where a Definition Contract crosses the splice (below), the
answering definition and the library's calls of it carry the row, so `typecheck`
can check the row's result type and report it on the game's `uses` line. Every
piece of library text the splice brings in carries its origin -- the library,
the definition holding it and the game's `uses` line (`n.LibraryOrigin`) -- so
a type-layer verdict that reads a game clause is told to the author who owns
its fact. And a library's Library Witnesses -- the corpus and family games that `uses`
it -- are read by the one step that decides which file a refusal of library
text is told in (below), and by nothing else. A
library's rules splice
where a game's `active_rules:` names them instead, after the game's own rules —
one splice, driven by activation, for every tier's rules alike. A rule template
no game instantiates is therefore not an error, and a rule no game activates is
checked against its library alone; the collision guards below still sweep every
rule a library declares, activated or not. That is what makes an import carry no runtime and no
information-set implication, and the splice is the whole of the reason: nothing
is added, and the game's own declarations are what run. In particular it is NOT
because a library cannot name a zone. A contract can name one, and a zone type
fixes the per-observer projection, so a library CAN say what its definitions
were written against — `HiddenPile` rather than `PublicHand`. That constrains
which games may import it; it changes nothing about the game that does.

**The standard library is a library with an empty contract.**
`cardlang/stdlib/rules.cardlang` is `library stdlib`: parsed by the same entry
point and held to the same library-alone law as a family library. Two things
set it apart. It ships with the language rather than the corpus, and no `uses`
line names it — a game switches its rules on by name in `active_rules:`, and
`uses stdlib` is refused with exactly that said. So its declared name is pinned
at load, and its `requires` must be empty, since a contract row would have no
`uses` line to be reported at. It needs no contract: its rules read the Play
Source a rule's bare `hand` names and the suit a trick round publishes as
`state.led_suit`, which every game that asks a rule has ("Rule demand forms").
Every stdlib rule is activated by some corpus game, because a rule no game
activates is checked by name alone.

**`uses` imports; it does not inherit.** A game-local definition under an
imported name is an error, not an override, and so is the same name from two
libraries. Import-with-override would make the tier inheritance, and would put a
game's meaning at the mercy of a silent redefinition — the accepted-but-ignored
defect class at file granularity. Nor is there a second, override-shaped
mechanism waiting behind it: there is no variant-delta construct and will not be
one ([principles.md](../principles.md), "Composition over inheritance"). Variants
are sibling games over a shared core, which is this tier — so `uses` is not one
of two ways to relate games, it is the way, and the no-override rule is
unconditional rather than provisional.

That decision sets the open question for this tier: **what may a library
contain?** Siblings can only share what a library can hold, so anything two
variants have in common and a library cannot express comes back as duplication.
Today a library holds definitions (move types, rules, functions, procedures)
and state, and no other game structure. Poker forced state; a
pair of variants sharing a phase tree would force phases. Grow it corpus-first,
one forcing game at a time — but do not describe a library as "a vocabulary, not
a game", because that framing assumed a delta mechanism would cover the rest, and
none is coming.

**State reaches a library two ways, and the difference is ownership.** A library
`requires` state the including GAME owns, and `state`s the state the LIBRARY
owns. Both are checked at the `uses` line, so an unmet contract or a collision
is reported to the game's author rather than as an undeclared name inside
spliced library text they never typed. So is every game clause the library's
definitions need: a library writing what a game clause gates, in a game whose
clauses refuse it, is refused on the game's `uses` line, naming the library,
what it writes and the clause. That covers a Builtin call (`ranking:` for
`rank_value`), and a construct: a `Rank` move parameter, `for each team`, state
keyed by team, `for each cell`, a card form in a piece game, a round's winner.
The gates are `resolve._CLAUSE_GATES`, and each row's test is the one its gate
asks of the game's own text. The rules judged are the ones the game activates.
A gate that needs an operand's type speaks after the splice and reads the
origin stamp instead: a card field the game's component set lacks (`c.suit` in
a game played with pieces) is refused on the `uses` line the same way, by the
type layer (`typecheck.CLAUSE_READS` names every type-layer read of a game
clause, and what each tells library text).

```text
requires {
  stack[player] : Integer   // the game declares it, sets it, writes it
  raise_cap     : Integer
}

state {
  acted[player] : Boolean = false   // the library's own; the game may read it
  limit         : Integer = 0
}
```

`requires` is deliberately a `state_decl` minus the `= <default>`: the initial
value is the game's to choose, and a library that could set one would be
configuring the game rather than contracting with it. Provided `state` carries
its default for the mirror-image reason — the library owns the variable, so it
owns the value the variable starts at.

**Provided state is read-only to the game.** It splices into the game's own
`state { }` and the game may read it, but an assignment from game text is an
error, reported in the GAME (the game's author wrote the assignment) and naming
both the variable and the library that owns it. The rule is what makes
"provided" mean anything: a variable the library maintains and the game may also
write is not owned by either, and the library's invariants over it would hold
only by the game's good manners. It is enforced across every write form the
language has — `:=`/`+=`/`-=`, `rotate`, and a `turns … again <flag>`, whose flag
the runtime clears at each turn boundary — because a rule that covered only the
obvious one would be two thirds of a guarantee.

**Nor may the game shadow provided state with a name of its own.** Read-only
governs writing; this governs reading. A binder or a declaration parameter the
game introduces — `for each player limit:`, `function f(limit : Integer)`, a
`let`, a `produces:` payload — may not be spelled like a
provided variable, because wherever that name is in scope the bare word is the
binder and the provided variable cannot be read there at all. It is the same visibility
asymmetry the injection rule below turns on, arriving from the other side: the
base language lets a binder shadow a same-named declaration precisely because
the author wrote both and can see both, and that reasoning does not survive a
declaration in a file they never open. A name the library merely `requires`
stays shadowable — the game declared it, so the author did write both. So does a
spelling the game already binds at declaration level, which the injection rule
refuses first: one clash draws one refusal.

Which fix the refusal prescribes follows the binder, and turns on one question:
is the spelling the author's to choose? Where they picked it, renaming the binder
is the fix. Where they did not — `any player where` always binds `player`, an
aggregation always binds `card`, a transfer filter binds the game's content noun
— there is nothing at the refusal site to rename, so the library's variable is
what must change instead. Both are reported in the GAME, which is where the
shadow is written and the file the author has open.

A Primitive's parameters are the one declaration parameters the rule does not
reach, and not by exemption: they label the Python signature and key the entry's
`reads` binders, so no DSL text sits inside their scope and there is nothing for
them to shadow.

**A provided default may not read the contract.** Provided state splices in
front of the game's own, so a `requires` name — which only the game can declare
— is never in scope where a provided default runs. This is the declare-order
rule of "State scoping (lexical)" landing on the tier, and the general guard
would catch it after the splice; it is refused before the splice as well,
against the library alone, because the splice destroys the distinction the
author needs. Post-splice a required name is just a variable declared later,
and "declare it earlier" is advice a library author cannot take. Give the
provided variable a literal default and set it from the contract in a phase.

**A contract names state, a zone, or a definition the game defines, and the
row's shape says which.** A row with a parameter list is a Definition Contract
for a definition the library CALLS: a function, typed by its result, or a
procedure, typed `Procedure`. A row without one is keyed, and its type is read
against two registries — the state types, and the stdlib zone types — plus the
one word `Move`, for a move type the library OFFERS by name and never passes
arguments. The three are disjoint, so which of the game's declaring blocks
answers a row is derived rather than declared:

```text
requires {
  hand[player]      : Hand<player>        // answered from the game's `zones { }`
  shipment[player]  : HiddenPile<player>
  merchant          : Player              // answered from its `state { }`
  raise_cap         : Integer
  fold              : Move                // answered by its `move_type fold { }`
  is_contraband(card : Card) : Boolean    // by its `function is_contraband(…) = …`
  settle_false_alarm() : Procedure        // by its `procedure settle_false_alarm() { … }`
}
```

A Definition Contract is how a library holds a move whose parts the family
leaves to the game. `poker_betting`'s street offers the game's `fold` beside
the four betting moves it defines, because which cards a fold disposes of is
the game's; `smuggling`'s `inspect` calls the game's `is_contraband` and runs
its `settle_false_alarm`, because which goods are contraband and what a false
alarm costs are the game's. The kinds a row can name are derived
(`resolve.CONTRACT_KINDS`): every definition kind some library text can name.
A rule is the kind it excludes, since only a game's `active_rules:` names a
rule, and `x : Rule` is refused saying so.

The game's own definition is the one answer — a library may not both define
and require one, and one library's definition does not answer another's
contract, exactly as for state. A Builtin needs no row (the library calls it
directly), and a row may not take a Primitive's or a round callback's spelling,
so a game's `primitives { }` entry never answers a function row. The game's
definition matches the row by parameter POSITION and by the exact spelling of
each parameter's type, `?` included; the row's parameter names are its own
reading, since the library never names the game's binders. A function's result
is inferred from its body, never declared, so it is checked against the row's
result by the ordinary coercion rule in `typecheck`, which reads it off the
stamp the splice leaves (above). Every one of these mismatches is reported once,
on the game's `uses` line: the library's own calls are typed against the row,
not against the game's answer, so a wrong answer earns no second report inside
library text the game's author never wrote. One definition may answer rows of
several libraries, and each row is checked on its own library's `uses` line; a
name one library's row makes the game define, and another library brings in,
is refused on that second `uses` line, since the two libraries do not combine
and the game cannot rename its answer. The rest follows from the language
around the row. A procedure may not run another, so a procedure row is run
from a library move type's effect. A definition the library calls cannot be
handed a new argument from the game's side, so the refusal of a call-site
pronoun inside one sends the game's author to the parameter the row passes. A
call cycle that crosses the splice is the game's to break, since its
definition closed the cycle, and it is reported there. A library is sound
when some answer meets its row, so a failure only some answers produce is the
answer's, and it is reported there too. A read the deciding seat cannot make,
reached through the game's answer from a library's decision, is refused in
the game's file, at the last text the game wrote on the way to the read,
naming the library, the row and the library's decision; that holds where the
library's argument names the instance the answer reads, and the sentence then
names the argument. So is a `choose` the answer makes where the library reads
it with no player acting, and a bare `hand` the answer reads under a library's
rule, each told a fix the game's text can take.

The same holds from the game's side. A library definition is sound when some
calling position meets it, so a failure that only the game's choice of where
to call it produces is the game's. Some positions call a library function
that reads what they may not hold: a Trick Order row, a rule clause, or a
place where no player is acting. Others are a Hosted Poll that calls, runs
or offers such library text. Each is refused in the game's file, at the last
text the game wrote on the way. The refusal names the library and its
definition, and tells the fix the game's text can take. A fault in the
library's own text stays the library's in every game, whatever calls it. A
function reading `actor` is one such fault, and a statement a procedure or
a move type's effect may never hold is another; each is told once, to the
library's author.

A library's text can also depend on a game declaration its contract does
not name: the `hand` a `Card` parameter takes its card from, the zone
`player_holding` searches, the actions of the game's climb engine, and the
phase a scoped Primitive reached through the game's answer reads. A refusal
such a declaration decides is the game's, told on its `uses` line, naming
the library and its definition, with the fix the game can take. Where the
contract names the zone, every game meeting it is refused alike, so the
refusal is the library's own, told where the library wrote it.

**One step decides which file a refusal of library text is told in.** No
check chooses; each refusal stands where the text it refuses stands, and
`cardlang.attribution` tells it, at every raise after the splice. A check
that follows the game's text into library text attaches the crossing it
left by -- a Trick Order row's call, a Hosted Poll's reach, a `run`, a
decision position's call -- to every refusal that
crossing causes, and such a refusal is told at the game's text on that
crossing, with the crossing kind's fix. A refusal with no crossing, in a
library definition that some Library Witness reaches and checks clean with, is the
game's by the law above: some game meets the definition, so this game's
choice is what refuses it. It is told on the game's `uses` line, naming the
library, the definition and the Library Witness. A Library Witness reaches what its own text
names, followed through the definitions it names in turn, the rules it
activates, the Delegated Play helpers where it plays a trick round, and the
library's provided state; a definition no Library Witness reaches is not certified,
so a fault that shows only where the definition runs stays its author's. Any other refusal
stays in the library's file; where no Library Witness checks clean,
one warning on the game's `uses` line says that no game yet checks clean
with the library, and where one does but none reaches the refused
definition, one warning there names the definition. A check that knows the sentence a game's author should
read supplies it beside its own, and the step tells whichever its verdict
picks. Every refusal told in the game's file keeps each library line it
stands on as a note under it, naming the definition that holds the line:
the library text a moved refusal stood in, or the library text a check
refusing the game's own text names or reached. Game text naming a library
definition -- a call, a `run`, an offer, an activation -- and a template
argument the game passes into a library rule stand on that definition, so a
refusal there keeps the definition's line beside every other line it stands
on. A
sentence names library text, and every function, procedure, move type,
rule, template or provided state variable, the game's own included, only
through a citation carrying the definition's line: the step words a
library's, and the game's own renders as written and makes no note, its
line being in the file told. A refusal standing in a library
procedure's body is told the same way once the `run` is expanded, through
the definition the expanded body keeps. Who is told never changes what is
refused: a warning and a note refuse nothing, and the step only moves spans.

The spellings do not cross. A zone type carries the `<owner>` argument; a
state type and `Move` carry none. A `?` is a type's nullability, never a
row's optionality — no row is optional — so it appears only on a signature
row's parameter or result type, where a function's own parameter could carry
it. A keyed row's grammar has no spelling for one. An argument on a state or
move row, a kind spelled where a type belongs (`fold : move_type`,
`respond : Procedure`, `x : Function`), a signature on a move row
(`fold() : Move`), a parameter type no definition of the row's kind could
declare, and a function result that is not a value type are all refused
against the LIBRARY ALONE, before any game is consulted, naming the row to
write — as are an owner argument disagreeing with the index, an owned zone
type with no index, and an index that is a position domain rather than a seat
or team. So is a move row the library never offers, or a procedure row it
never runs, because the game's answer would be refused as never offered or
never run and no game could meet the row. The declaration keyword at the
head of a row (`function is_contraband(card : Card) : Boolean`) is refused at
parse, with the row it should be. A library declares no `positions { }` and
cannot name one, so a position-indexed zone family cannot be contracted at
all.

That the derivation IS a derivation rests on a guard: a declared `type` and a
per-game `positions { }` name may not take a kernel zone type's spelling. Without
it `type Hand = { … }` would make `requires { x : Hand }` mean two things, and
the classification would silently pick one.

A contracted zone is the game's zone. The game declares it, writes it, and owns
its projection; the contract only says which shape the library's definitions were
written against. That is the reverse of provided state, and deliberately so —
there are no library-owned zones, because every zone a family shares is written
by game text somewhere (a deal, a settlement, a game-local move), and a variable
the library owns and the game may also write is owned by neither.

**There is no visibility system beyond this, and that is a decision, not a
gap.** No `private`/`public` marker on a definition, no export list, no scoped
namespace. Two surveys over the two multi-member families in hand measured what
sharing actually needs (recorded under "The evidence" below), and read-only
provided state plus ordinary procedures covered every case: the variables no
game reads become the library's, the boundary writes that remain become a
procedure the game runs. Nothing in either family wanted a definition hidden
from its importer. Adding a marker system now would be designing against
imagined pressure, and this paragraph exists so the question is not silently
reopened — reopen it when a family produces a case these two mechanisms cannot
express, and name that case. One case is named: a family move type whose
meaning holds only inside the library's own procedure, as `poker_betting`'s
`bet` posts a street size that only `betting_street` sets, can still be
offered by the importing game (issue #938).

A requirement's own index is checked first, and reported to the LIBRARY's author:
`requires { seen[rank] : Integer }` is refused where the library wrote it,
because an index must be a role a state variable can be keyed by
(player/team) and no game could answer such a requirement. That is the
library Shadow Guard of the state-index guard, and the difference is
who can fix it — an unmet contract is a fact about the importing game, a
malformed index is wrong in the library's own text. A mismatch between a
well-formed requirement and the game's declaration names both roles
(`per-team` against `per-player`), never the presence or absence of an
index.

What the `requires` contract checks is that **exactly one**
declaration of the name exists somewhere in the game, at the library's arity and
type. Which `state { }` block holds it is not checked: a phase's block is the
natural home for state that resets on phase re-entry, which is what per-hand
betting state is, and Seven-Card Stud declares all seven of `poker_betting`'s
requirements inside `phase play`. That is weaker than "the library's definitions
can read it where they run" — a declaration in a phase the library never runs in
satisfies the contract and then fails at play time — and the shortfall is not the
import tier's to close: a plain game with no library reproduces it, one phase
declaring what another reads. It is recorded in issue #138.

Cross-block shadowing is legal for game-private state and refused for a
`requires`d name: the two shadowed declarations answer different questions, and
no fixed tie-break picks correctly, since a shadow in the phase where the
library's definitions run and a shadow in some other phase want opposite winners.
Because the spelling is the interface, a `requires`d name is not game-private:
the metamorphic rename transform excludes it for the same reason.

**The contract is meant to be sufficient, not advisory.** A library's
definitions may reach only its `requires` contract, its own definitions, the
stdlib, the pronouns and binders any body has anyway, the Play Source a rule
clause's bare `hand` names, and the fields a round publishes to `state.` —
checked against the library alone, before any game is consulted. Without that the contract would be
a suggestion: a body reading past it resolves against a game that happens to
declare the extra name and fails against a game meeting the contract in full,
reporting an unresolved-name error inside library text the game's author never
wrote. That is the misaddressed failure `requires` exists to prevent, arriving by
the back door, and it is why the check reports to the LIBRARY's author — the
library author is the only one who can fix it. The same rule makes a library
deck-agnostic: it names no rank, no suit and no card, because those exist only
once an including game names a deck, and a family's members do not share one
(Kuhn's holds three cards). A rank or suit written as a string (`c.rank is
"10"`) is named all the same, and is refused to the library's author in every
game, with the fix of taking it as a parameter (`r : Rank`) the game passes.
And the same rule makes a library seat-agnostic: it names no seat and no team,
seat 0 included, because those exist only once an including game says
`players:` and `teams:`, and a family's members do not seat one table
(`poker_betting` is played heads-up and at a full table). A definition that
needs a particular player reads it from state its contract requires (`dealer :
Player`); a provided variable that needs a first seat moves into `requires {
}`, so the game declares it and picks it. The refusal reaches every position
the seat and team range check does; a number compared by `is` (issue #803) or
reaching a seat through another expression's value (issue #805) is held there
for library and game alike.

The check enforces this for every name the resolver classifies **and** for every
name a construct holds as a bare string instead — a `turns … again <var>`, a
`round`'s source and play zones. (`state.<field>` names a field a round
publishes, a set closed by `ROUND_STATE_FIELDS` and the same for a library as
for a game.) The second
half runs off the **reference-slot registry**: one table classifying every
string-typed field of every AST node as a declaration, a binder, a reference
into a named namespace, a keyword, opaque text, a classified name, or pass
metadata. The table's key set is derived from the AST and pinned to it, so a
field added to a node is classified or the build fails; what each slot MEANS is
authored, because no annotation carries it.

The registry is what makes the boundary statable. A namespace a library can
reach is either swept against what the library itself has, or carries a written
reason why reaching it is not a channel — a closed kernel table or domain registry
identical either side, a name owned by a declaration that IS swept, a name
another named pass refuses to the library's author, or a name nothing checks by
a recorded decision. There is no third state, and no consumer keeps a list of the
slots it remembered.

A library names no [[primitive]], in a call or in a `round`'s query slots: a
Primitive belongs to the one game that declares it, so library text naming one
couples every importer to that game. Both are refused to the library's author.
A call's value can be computed by the game and passed in as an argument; a round
slot takes a bare name, so a round naming a Primitive is written in the game.

**Name collisions on state are guarded the same way collisions on definitions
are.** A library may not both provide and require one name — the two clauses
point opposite ways, so no reading satisfies both. Two libraries may not provide
one name, because resolution is flat and picking by `uses` order would make a
game's meaning depend on the order of its import lines. A game may not declare
what a library provides: that is the state face of "`uses` imports, it does not
inherit". And a requirement is answered by the game's own declaration, never by
another library's provision, which would couple two libraries through a name
neither mentions the other in. Two libraries requiring the same name is fine —
one game declaration answers both contracts.

**A library may not inject a name the game already uses for anything — in any
namespace, not just the same kind.** The collision guards above catch a library
definition landing on a game definition of the SAME kind (function over
function) and a provided name landing on the game's own state. The remaining
cases are the silent ones: a provided name, or a library definition, coinciding
with the game's zone, a suit or rank or direction value of its deck, a position
domain, or a definition of a DIFFERENT kind. Each is a trap because a `uses`
import adds names without overriding and the game's author never opens the
library file — so a bare `hearts` the author writes meaning the suit resolves to
the library's variable instead, or a `pile` they declared as a zone is shadowed
by a provided one they cannot see. This is where the tier parts company with the
base language, which lets a GAME reuse one name across its own namespaces: there
the author wrote and can see both declarations, and the precedence that resolves
the reference is theirs to know. The refusal is deliberately conservative — a
coincidence is refused even where precedence would make it harmless — because the
rule a designer must hold is "a library may not bring in a name you already use",
not a table of safe pairs. It is reported naming the library, since that is the
half the author cannot see. The game-level face of the same clash is left to
the author deliberately, and is not deferred work: `state { pile }` beside
`zones { pile }`, a state variable spelled like a suit, or a function named
after a rank all resolve by `_classify`'s precedence (state variable over
zone over deck value over function), which makes the loser unreachable by
that spelling with no diagnostic. That is the ordinary block shadowing every
language allows, and a game-level uniqueness rule would be a far larger,
higher-risk change than the corpus has forced. The library guard turns on
INVISIBILITY — a name the author cannot see — so it would be wrong to apply
to names they wrote; if a designer is ever surprised by their own
cross-namespace shadow, the fix is to lift the same sweep to the game's own
declarations and measure the corpus cost.

**What a library holds, and what stays game-local.** A library holds definitions
and the state its definitions own — but no zones and no phases — because that is
as far as the corpus has forced it, not because a library is a lesser kind of
thing than a game. The boundary moves as sibling games need to share more.
Within today's boundary the corpus forced a sharper line, and the line is about
VARIATION rather than about zones: **what differs across the family stays
game-local; the library holds what every member holds identically, and
contracts for the game's part of it.**

`poker_betting` holds check, bet, call, raise and the `can_act`/`owes`/`pending`
ring predicates — all of which move chips and nothing else, over the reading of
`acted` in "Named functions" above — and omits `fold`,
the one betting move that touches cards. Which cards a fold disposes of, and
where they go, is a property of the game: Stud sends the folder's upcards to the
muck the instant they fold, and opponents' information sets carry that
observation. Each game defines its own `fold`, and the library contracts
for it (`requires { fold : Move }`) so its street can offer it beside the
imported moves.

`smuggling` draws the same line one family over, at a finer grain. Its members'
inspections differ in three orthogonal ways — the fine (a per-game constant),
the contraband test (a card predicate), and what a false alarm costs (a
statement block, carrying a bounty in some members) — and each is a part a
contract row can name: the fine is required state, the test a function row,
the false alarm a procedure row. So the whole round is in the library,
`inspect` included, and each member supplies the three parts. "Touches a zone"
was never the criterion: a move touching a CONTRACTED zone belongs in the
library, and what varies stays the game's, however small the part.

**Parameterization rides on state and on procedure arguments, not on the
import.** Family members differ by constants, and where the constant lives
follows what it is a property of. A per-GAME constant is required state the game
declares: Stud allows three raises per street and Leduc two, so `raise_cap` is
`requires`d. A per-OCCASION constant belongs to the occasion, so it is a
procedure argument: a poker bet size is a property of a street, not of a game
(Stud runs 5/5/10/10/10), so `limit` is provided state that the library's
`betting_street(first, bet_size, big_size)` sets, and each street names its own sizes
where the street is written — the second being the street's other legal wager,
or 0 where its rules give only one. Neither difference reaches the import surface, which stays a bare
name.

The test for which of the two a constant is: could one declaration in the game
carry it? `raise_cap` yes, `limit` no. A value that varies within a game was
never a declaration's to hold, and making it one is how `limit := 5` came to be
repeated at five sites that were otherwise identical.

**A second family was measured against this rule and did not break it, but it
did narrow what the rule is about.** The smuggling family's members differ in
three ways, and only one is parameterization at all: a fine (a per-game
constant, which required state carries), a contraband predicate, and a
false-alarm cost that is statements. The last two are not constants of any
kind, so no clause on the import would carry them either — a `with` clause is
not what that family wants. What it wants is a contract over DEFINITIONS: the
function and procedure rows above, which let the varying predicate and
statements be the game's while the move stays shared. That is a different
question from #178's — a definition is a NAME the game declares, where #178 asks
whether a contract can express a capability at all. Recorded here so the next
reader does not re-derive a `with` clause from the same evidence.

**A member offers a subset of the family vocabulary, at no cost.** Importing a
library is not a commitment to use all of it: Kuhn's `offering` list is
`[check, bet, call, fold]`, so the imported `raise` is never offered — standard
Kuhn has no raise. That costs nothing at the OpenSpiel target, because the
action space is derived from the `offering` / `offer` lists, never from the
game's move-type table, so an imported-but-unoffered move type mints no action
id and cannot widen `num_distinct_actions`. This is what makes whole-library
import affordable for a small family member, and it is pinned rather than
assumed (`tests/openspiel_ready/test_kuhn_poker.py`). It is not a licence to
leave a move type dead by accident: a game's own definitions are still subject
to the ordinary totality rule above — the exemption is for *imported* text the
author did not write, whose unused parts are the price of naming a family
rather than a manifest.

**The evidence.** Two surveys sized what a library must hold, and they are
recorded here because the shape of this tier is an empirical claim rather than a
deduction.

*Survey 1, over the three poker games.* Every game write to `poker_betting`'s
state is at a street boundary, with one exception: `folded`, written mid-street
by each game's own `fold`. Four of the nine required variables — `acted`,
`raises`, `limit`, `raise_cap` — were never READ by any of the three games. (Nine is what the
contract held then; it holds seven now, which is what the survey bought.) And
all five street-reset sites (one in Leduc, four in Stud) were one shape differing
in a single integer. That is what forced provided state and a street procedure that sets it: writes
that cluster at boundaries are absorbable by a procedure, and a variable no game
reads or writes has no business in a contract. Only two of the four moved,
though, and the two that did not are as informative as the two that did —
`raise_cap` is a per-game constant so no single provided default fits it, and
Stud's bring-in genuinely writes `raises`, a boundary write no *shared* procedure
absorbs because only one game in the family has a bring-in.

*Survey 2, over the smuggling family* (`experiments/green-lane/`, an experiment
rather than corpus). Run as a survey first and then EXECUTED, and the two
answers differ, which is why the executed one is what stands.

The survey said the shared material a library could not hold was irreducibly
zones plus state declarations. Building the library found the first half was a
missing mechanism rather than a boundary — hence zone contracts — and the second
half stands: state declarations are shared by being contracted, never by being
held, so each member still writes its own.

What the build measured, over all twelve files: `zones { }`, `commit_shipment`,
`respond` and `wave` are byte-identical everywhere; `state { }` varies in one
default and one added variable; `phase play` varies in two lines; `phase
scoring` in four; and `inspect` has ten bodies that differ only in the three
parts above. The library holds the whole round — the commit, the respond step,
the wave and the inspection — and the contract they reach. Even so, **much of
what these siblings have in common is material this tier does not hold**: zones
(contracted, not shared), state declarations (likewise), and the phase tree.

Phases were NOT forced, and for a reason worth keeping: the shared phase material
reduced to statements a procedure covers. A separate constraint capped how far
that goes — a procedure may not invoke another (expansion is a single splice,
not a call graph) — so shared material reachable only from inside a game's own
procedure has to be lifted to a phase to be shareable at all.

The second survey carries a caveat that bounds how far it generalizes. Green
Lane's variants are a **delta lattice** — v4 is v1 composed with v3, and each
delta edits disjoint rule text — so the family shares a great deal by
construction. A family whose members are siblings rather than deltas may share a
different *shape* of material. Read Survey 2 as "phases were not forced by this
family", not as "phases are settled".

The tier's completeness gate is `tests/test_family_libraries.py`, whose ledger
records the one deliberate non-cell: kernel move types and a game's `move_type`
definitions are disjoint consult paths that never share a namespace, so there is
no collision there to guard against.
