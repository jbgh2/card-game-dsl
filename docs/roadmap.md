# Roadmap

The deferred **work** lives in the GitHub tracker
(<https://github.com/jbgh2/card-game-dsl/issues>), not here. This file keeps
only the two things that are not work items: what is out of scope for the
current phase, and the ledger of grammar surface the checker deliberately
defers. Both are properties of the language as it stands, so they belong with
the spec.

## Where the work is tracked

- **Cross-cutting task sequence** — [issue #143](https://github.com/jbgh2/card-game-dsl/issues/143),
  the pinned ordering issue. It is the authority on what to build next and in
  what order.
- **Open design questions and their priority** —
  [open-questions/_index.md](open-questions/_index.md).
- **The game pipeline** — [games/_candidates.md](games/_candidates.md).
- **Everything else** — one issue per deferred item. An issue blocked on a
  corpus game carries `blocked:needs-witness` and names that game in its body;
  `epic` issues are checklist containers for multi-stage workstreams.

A deferred cell recorded in a completeness ledger cites its issue as
`issue #N` (decisions.md "Closed-domain completeness"). Every issue's
`## Provenance` line names the roadmap item it came from.

## Out of scope

CCG-style card effects (Magic, Yu-Gi-Oh!) are out of initial scope; the Forge
text-DSL pattern (one mini-language per card) is the reference if and when we
tackle them. Deck-builders are deferred alongside them, though the deferral is
narrower than the grouping suggests —
[design-notes/deck-builder-onramp.md](design-notes/deck-builder-onramp.md)
reframes it. Per-card mutable attributes (tapping, counters, status effects)
are not part of the surface, since the oriented- and CCG-style card state they
would serve is what is deferred here.

## Grammar surface deferred by the checker

Grammatically valid forms are statically rejected until a game needs them
(decisions.md "Surface totality": rejected loudly rather than silently
ignored). Movements: the
`in <zone>` form (the verb implying its destination — `muck one cards in
discard`), the per-movement `visibility =` override (visibility derives from
the declared zone types; the override's semantics is
[open-questions/move-level-visibility.md](open-questions/move-level-visibility.md)),
and resource movements (`move 2 chips …` — the corpus keeps chips/coins as
Integer state; moving resources through zones is undesigned). Elsewhere:
`override` rule deltas in `active_rules:`, `before_each`/`after_each` on a
phase with no iteration, transition events other than `play_to_trick`, a
trick round naming a move type its form cannot run, duplicate
`state { }` blocks, and named call arguments (`f(x = 1)` — rejected until
a game needs the surface; positional arguments are the implemented form).
Counting is the card-query form (`number of cards in … [where <pred>]`);
the retired `count over` comprehension (whose body was silently
discarded) does not parse.
Rule-template parameters (`rule X(suit: Suit)`) support the Suit domain
only, and one instantiation per rule name per game — both rejected loudly,
lifted when a game needs more. Quantifier / `for each` roles are the closed
set player/team/suit/rank; `each … simultaneously` is player-only.
Value-domain-indexed state (`state { seen[rank] : Integer = 0 }` as a
per-rank tally) is rejected: a zone or state index must be a
`zone_key_of` domain (player/team — `cardlang/domains.py`), because the
runtime keys those stores by an observer-anchored member set. A per-value
tally is expressible today as per-player state plus a query; lift the wall
when a game genuinely wants the store (the runtime's key-set plumbing
already reads the domain table, so the extension is a table row plus an
observation-encoding decision, not a rewrite).
The `turns` form has no `direction` override clause (rotation follows the
game's declared direction; not grammar until a game needs a mid-game or
per-loop override). Joint-predicate selection: `jointly` under a `random`
or dealt selection is rejected (a subset decision needs a decider; a
uniform-random satisfying subset has no corpus user), `some` without
`jointly` is rejected (nothing owns the size), `jointly` with `to each`
is rejected (each destination seat would become its own subset decider —
a real semantic no game has asked for; note the pre-existing non-joint
`chosen … to each` DOES reassign the decider per parcel the same way,
unexercised by the corpus and undocumented — the same decision awaits
whichever game first wants either shape), and the subset enumeration
refuses source pools past 16 cards at runtime rather than hanging
(`cardlang/runtime/execute.py`, `_JOINT_ENUMERATION_BOUND`). Movement
amounts: negative is a typed runtime error everywhere and a zero `chosen`
amount is refused as a vacuous decision (`_check_count`), while a zero
dealt/`random` amount stays an accepted no-op (a computed "deal what
remains" may legitimately be zero). On the
OpenSpiel side, a joint predicate must root in a call with a registered
subset codec (`cardlang/runtime/stdlib.py`, `joint_codec_function` — the
climb-codec pattern); an inline or unregistered predicate, a game mixing
climb and joint selections, or two joint predicates wanting different
codecs are each a loud `NotImplementedError` at action-space
construction, lifted when a game forces the composed-combo-block design.
Joint selections on a deck with duplicate identical cards (pinochle48,
doppelkopf48, coup15, canasta108) are refused there too: the combo block
canonicalizes subsets by frozenset, which collapses copies — {K♠, K♠}
would collide with {K♠} — so the encoding needs a multiset-safe
canonicalization no game has forced (Canasta, the first duplicate-deck
melding game, deliberately encodes melds per card through the card block
instead — copies share an id soundly there, since identical cards are
interchangeable).

## Not yet migrated

These post-date the 2026-07-25 migration of this file to the tracker and have
not been triaged into issues yet. They are work items and do not belong here
permanently; each needs an issue, and this section should empty.

Note also that [issue #95](https://github.com/jbgh2/card-game-dsl/issues/95)
was filed against the pre-PR-#93 framing of the player-literal wall. PR #93
closed that wall by construction (the `_check_operand` choke point), so #95's
stated subject is done and the `partnerships:` residual below is what actually
remains.

- **Role drift through a variable, an unread reason, or the test tree.** Every
  construct that BRANCHES on a role-id literal carries a marker saying why it is
  not registry drift, and every role literal that does NOT branch is authorized
  in a per-module multiset — both pinned by tests/test_role_comparison_pin.py.
  The position axis is the branch itself, not one spelling: any comparison
  operator, at any depth in an operand (so a role inside a set or tuple counts),
  plus `match` patterns. That axis is a PROXY for "the literal participates in a
  decision", so the band it cannot see is walled rather than trusted: 14 role
  literals branch and 54 do not, and a decision that moves OUT of a comparison —
  a role set hoisted to a module constant, a `role.startswith("team")` — changes
  the multiset and reddens. Requiring a marker on all 68 was rejected
  deliberately: a marker demanded where nothing is decided trains the marker into
  noise, which is how a pin stops being read. Three things stay outside all of
  it. A role reached through a VARIABLE rather than a literal is out of reach of
  any scrape; only a type would catch it (a `Role` enum in place of `str`), which
  is a larger change than the drift so far justifies. A marker's REASON is prose:
  `.` satisfies "nonempty", and a reason asserting a registry pin beside it stays
  green when that pin is later deleted — a tag vocabulary (`intrinsic:` /
  `not-a-role:` / `pinned:`) derived from one named constant would make the
  reason's CLASS machine-checkable, and is the next step here. And `tests/` is
  not swept at all, though it carries 37 branching sites to production's 14,
  including `openspiel_ready/harness.py` in the proof layer; that is a separate
  domain needing its own framing check and probes, and the precedent cuts toward
  doing it — mypy already holds `tests/` to the same strict bar.

- **A scalar `winner:` target crashes instead of being refused.** `winner:
  highest <var>` names the score variable a game is ranked by, and the runtime
  builds its score dict with `dict(rs.get(target))` — which requires the target
  to be an INDEXED variable (`score[player]`, `score[team]`). A scalar target
  (`state { pot : Integer = 0 }` + `winner: highest pot`) type-checks and then
  dies with a bare `TypeError: 'int' object is not iterable` inside
  `driver.play_game` — a Python error, not a diagnostic, on a game the checker
  accepted. Run and confirmed 2026-07-25. The wall is a checker rule that a
  `winner:` target names an indexed state variable (and the matching
  `loser:`-style message); deferred only because no corpus game writes one, and
  it is a distinct rule from the returns KEYING this class otherwise covers
  (tests/test_openspiel_returns_keying.py).

- **A team-scored game's `winner` is a team index.** `GameResult.winner` is
  typed `Player | None` but is picked out of `scores`
  (`driver.play_game`: `pick(scores, …)`), and `scores` is keyed by the
  `winner:` target's own index domain — so in a team-scored game (bridge,
  spades, pinochle, tichu) the field holds a TEAM index wearing a player's type.
  Nothing reads it as a seat today: the OpenSpiel returns path maps scores
  through `team_of` on the target's declared index
  (`openspiel/replay._score_key_by_seat`) and never consults
  `winner`, and the characterization goldens only record it. So this is a
  mislabelling, not a wrong answer — but it is the same team-keys-are-not-seats
  confusion that silently paid the wrong seats before that structural read
  landed. Closing it means deciding what a team-scored `winner` should BE (the
  team, a representative seat, or every member) and retyping the field to say
  so; deferred because the answer is a small design question, not a bug, and
  moving it would move the characterization goldens.

- **Unvalidated `partnerships:` list contents.** An integer literal in any
  Player or Team *operand* position -- a subscript, a call argument, a `state`
  default, a scalar `:=`, an `as`/`turns`/`round`/`offer to`/`loser:` seat, a
  struct field, a variant payload -- is range-checked by construction: every
  coercion routes through one operand check (`typecheck._check_operand`), which
  bounds the literal against the seat count (`max_players`) or team count
  (`max_teams`), two-sided (a negative literal rejects too). The wall is closed
  by construction, not by enumerating sites, and pinned: no `assignable(...)`
  coercion in typecheck.py escapes the choke point
  (tests/test_operand_choke_point.py), and every position is a grid row
  (tests/test_player_literal_range.py). The ONE place a raw seat/team integer
  still escapes is the `partnerships:` declaration itself: `partnerships:
  [[0, 5]]` in a four-player game names a non-existent seat 5 (and each bracket's
  position is a team index), but those ints are parsed straight into
  `Game.partnerships` (`tuple[tuple[int, ...], ...]`) and reach the IR and
  deckcheck without ever becoming an operand expression, so `_check_operand`
  never sees them -- and NOTHING else validates their CONTENTS either. Three
  distinct malformations are all accepted silently, the worse kind of residual:
  an OUT-OF-RANGE seat (`partnerships: [[0, 2], [1, 5]]` in a four-player game
  type-checks AND plays to completion, the phantom seat 5 simply never matching),
  a DUPLICATE seat (`[[0, 0]]`), and a seat on MULTIPLE teams (`[[0, 1], [0, 2]]`
  -- seat 0 belongs to two partnerships). Only a NEGATIVE seat is caught, and
  only because the grammar's `INT` terminal has no `-`. The wall would be a
  resolve-time check that every partnership seat is `0 <= s < player_count`,
  appears at most once, and (the game defines it) the teams partition the seats;
  it is deferred because no corpus game writes a malformed partnership, and these
  are declaration integers, not the operand coercions the choke point closes.
