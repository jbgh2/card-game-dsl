# Bounded-Integer *move-parameter* domains

**Tier 2 — high impact, blocked on a corpus game.** `Suit`, `Suit?`, `Rank`,
`Player`, and `Card` are settled, closed, enumerable **move-parameter** domains
([decisions.md](../decisions.md) "Declared parameter domains"), and the integer
**`choose`** domain (a bid over a bounded interval, with a declared static
ceiling) is settled too (same section, "The integer `choose` domain"). The one
domain still missing is a genuinely numeric **move parameter**: a `move_type`
parameter ranging over a bounded integer interval, so a single move type can
carry a small integer argument instead of the author hand-compiling one nullary
move type per value.

## The data point

- **Ninety-Nine** (stress-sweep branch `stress-test/broad-sweep`,
  `stress-test/FINDINGS.md`) needed `play_card(delta : Integer)` — a play
  parameterized by a small **signed** integer — and was forced into declaring 14
  separate nullary move types instead, one per delta value: the
  nullary-move-type explosion, hand-compiling exactly the enumeration a declared
  domain should own.

Ninety-Nine is not in the corpus, so per corpus-first this stays deferred until
a corpus game forces it (or Ninety-Nine itself is promoted).

## Why it is not just the `choose` domain again

The settled integer `choose` domain reserves an OpenSpiel id block `0 .. ceiling`
and maps a value `v` to `int_base + v` — an **unsigned, origin-at-zero** scheme.
Ninety-Nine's `delta` is *signed* (a card can raise or lower the running total),
so it fits neither that id arithmetic (a negative value has no id) nor the
runtime range guard (`lo >= 0`) the `choose` domain relies on. A move-parameter
integer domain therefore needs its own design — an offset/signed interval
`[lo, hi]` minting `hi - lo + 1` ids, plus the enumeration wiring in
`enumerate_domain` / `param_domain` that `Suit`/`Rank`/`Player` already have and
that a bounded-Integer parameter is currently rejected before reaching
(`resolve.py`, `_check_move_params`).

## The options

- **Declared literal interval on the parameter.** `play_card(delta : Integer in
  -1 .. 1)` — a refinement-typed parameter whose static interval both bounds the
  enumeration and mints the ids. Mirrors how `Suit`/`Rank` are fixed-from-type,
  and how the `choose` domain declares its ceiling; connects to the deferred
  refinement-typed struct fields ([decisions.md](../decisions.md) sibling in
  roadmap's typed-outcomes entry).
- **A named integer-domain declaration.** A game-level `domain Delta = -1 .. 1`
  referenced by the parameter type, if several moves share one interval.
- **Reject outright** and keep hand-compiled nullary move types. The status quo;
  rejected as the whole point of the nullary-explosion complaint.

No option is committed — the design waits on a corpus game to size it against.

Related: [decisions.md](../decisions.md) "Declared parameter domains" (the
settled move-parameter and `choose` domains this would extend to a signed
numeric range) and "No implicit actions" (an empty domain is already an error —
any resolution must preserve that);
[phase-legal-moves](phase-legal-moves.md) (what a declared move vocabulary is
for — the same static-contract instinct at phase level).

## A larger sibling: no-limit bet sizing

A bounded-integer move parameter (above) is a small, fully-enumerable
interval. **No-limit betting is the same shape at a scale that cannot be
enumerated outright** — a bet size ranging up to a player's whole stack has
no small fixed ceiling, so it cannot mint one OpenSpiel action id per value
the way `Suit`/`Rank`/`Player`/bounded-`Integer` do; it needs bet-size
**action abstraction** (bucketing into a handful of representative sizes) to
stay within "Anchored to a finite action space"
([decisions.md](../decisions.md)). No corpus game forces this yet — Stud and
the candidate Hold'em variants ([games/_candidates.md](../games/_candidates.md),
"holdem") are fixed-limit, where the bet size is already one of a small
enumerated set, so the ordinary bounded-integer domain above would suffice.
No-limit variants stay unbuilt until a corpus game needs them.

## Adjacent cleanup to fold in

One small gap surfaced during the declared-parameter-domains review, narrow
enough to ride along with whichever option above is picked:

- `ActionSpace.encode`'s `(name, None)`-equivalence branch (`encoding.py`)
  would shadow a move name that appeared in BOTH a plain `offer` and a round
  vocabulary in the same game — dormant today (no corpus game shares a name
  across both surfaces), and even if it fired it would only waste one action id,
  not misroute an existing one.
