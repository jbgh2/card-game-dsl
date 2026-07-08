# Bounded-Integer parameter domains and the `choose` reconciliation

**Tier 1 — high impact, enough data to commit.** `Suit`, `Suit?`, `Rank`,
`Player`, and `Card` are settled, closed, enumerable move-parameter domains,
enumerable by both a plain `offer` and the auction `round offering`
([decisions.md](../decisions.md) "Declared parameter domains"). The one
domain still missing is a genuinely numeric one: a parameter (or a `choose`
expression) ranging over a bounded integer interval, where the bound itself
can vary by game state.

Two data points want this:

- **Ninety-Nine** (stress-sweep branch `stress-test/broad-sweep`,
  `stress-test/FINDINGS.md`) needed `play_card(delta: Integer)` — a play
  parameterized by a small signed integer — and was forced into declaring 14
  separate nullary move types instead, one per delta value: the
  nullary-move-type explosion, hand-compiling exactly the enumeration a
  declared domain should own.
- **Oh Hell** ([games/oh-hell.md](../games/oh-hell.md)) bids `choose integer
  in 0 .. hand_size`, where `hand_size` is itself per-hand state (10 down to
  1, back up to 10 across the match). This already runs today — `choose` is
  a working expression form, not blocked on this question — but its
  OpenSpiel action space is reconciled by one global constant, `_MAX_CHOOSE
  = 52` (`cardlang/openspiel/encoding.py`): every game with an integer
  `choose` anywhere reserves a fixed 53-id block (`0..52`), sized to "the
  deck," not to any declared or checked per-choose bound. The interpreter
  itself already narrows correctly at runtime — `_choose` computes
  `candidates = range(lo, hi + 1)` from the live bound and offers exactly
  those — so the gap is entirely on the **static** side: nothing declares
  what `_MAX_CHOOSE` should be, or checks that a game's bounds stay under it.

## Why this is more than ergonomics

The OpenSpiel target requires a **fixed, enumerable action space**
(`num_distinct_actions`) declared up front, with per-state legality as a mask
over it — the same contract `Suit`/`Rank`/`Player`/`Card` already satisfy
([decisions.md](../decisions.md) "Declared parameter domains"). A
runtime-computed bound is hostile to that contract by construction: the
static universe size can't be read off the declared domain the way it can
for a closed set. `_MAX_CHOOSE`'s fixed 52 papers over this for every card
game built so far (no corpus game's bound exceeds it), but it is a magic
number, not a checked contract — a future game whose natural bound is larger
would silently violate it, and nothing at resolve time would catch a
declared bound that could overflow it.

## The options

- **Reject a runtime-computed bound outright.** Only a `choose`/parameter
  whose `hi` is a static literal (or resolves to one at compile time) is
  legal; anything state-dependent is a resolve-time error. Simplest, but
  rules out exactly Oh Hell's shape, which is a common pattern (bid up to
  however many cards you hold).
- **Require a declared static outer bound, masked at runtime.** A parameter
  or `choose` states its maximum statically (a literal ceiling, or a bound
  tied to a zone's declared capacity); the OpenSpiel action space reserves
  exactly that many ids, and runtime legality — already correct today —
  narrows within it, the same way a move's guard masks a fixed cross-product
  down to what's legal in one state. This retires `_MAX_CHOOSE` as a global
  magic constant and replaces it with a per-declaration, checked one.
- **Infer the bound from context.** Derive the static ceiling automatically
  (e.g., from a hand zone's maximum size) rather than requiring the author
  to state it. Less surface, but needs a rule for where the inference comes
  from in a game with no obviously-bounding zone.

No option is committed. Whichever is chosen should retire `_MAX_CHOOSE` as a
global magic constant and put a bounded-`Integer` domain on the same footing
as `Suit`/`Rank`/`Player`/`Card`: a declared, checked, closed contract the
OpenSpiel adapter reads directly, not one inferred from runtime behavior or
papered over with a number sized to "the deck."

Related: [decisions.md](../decisions.md) "Declared parameter domains" (the
settled sibling case, whose closed-set-plus-mask contract a bounded-Integer
domain would extend to a numeric range) and "No implicit actions" (a
`choose` over an empty domain
is already an error — any bounded-Integer resolution must preserve that);
[phase-legal-moves](phase-legal-moves.md) (what a declared move vocabulary is
for — the same static-contract instinct at phase level).

## Adjacent cleanups to fold in

One small gap surfaced during the declared-parameter-domains final review,
narrow enough to ride along with whichever option above is picked rather than
warrant its own question:

- `ActionSpace.encode`'s `(name, None)`-equivalence branch (`encoding.py`
  ~263) would shadow a move name that appeared in BOTH a plain `offer` and a
  round vocabulary in the same game — dormant today (no corpus game shares a
  name across both surfaces), and even if it fired it would only waste one
  action id, not misroute an existing one.
