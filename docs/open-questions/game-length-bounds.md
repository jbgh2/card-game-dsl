# Game length as a declared contract

**Tier 1 — high impact, enough data to commit.** The bound on a game's
length currently exists as two unrelated magic constants:

- the runtime's hardcoded 10,000-iteration `repeat until` safety cap, and
- `max_game_length=40000` in the OpenSpiel adapter
  (cardlang/openspiel/game.py).

The broad-sweep stress test (branch `stress-test/broad-sweep`,
`stress-test/FINDINGS.md`) showed the first constant is not a theoretical
backstop: Palace/Shithead — a real game whose random playouts legitimately
run thousands of turns — crashes on roughly 10–15% of seeds by *hitting the
cap*, with a bare assertion failure rather than a diagnostic. A
checker-green game that cannot complete a random playout is exactly the
"runs but isn't done" failure mode the project's acceptance criteria exist
to catch, and today the author gets no signal until the runtime dies.

Meanwhile the OpenSpiel target *requires* a max game length per game — the
adapter must report one — so the language will need a per-game answer
regardless. Two arbitrary constants, one of which crashes real games and
the other of which the adapter invents, should be one declared (or derived)
contract.

## The options

- **A per-game `max_length:` declaration.** The game names its bound (in
  decision nodes, or per-loop iterations); the runtime enforces it with a
  proper diagnostic ("game exceeded its declared bound — raise `max_length`
  or fix the non-terminating rule"), and the adapter exports it instead of
  40000. Cheap, explicit, and it makes "does this game terminate?" an
  author-visible question rather than an interpreter constant.
- **Derive bounds statically where possible, declare where not.** Card-
  conservation games (tricks consume hands) have derivable bounds;
  pickup/recycle games (Palace, War) genuinely do not — they'd still need a
  declaration. More design and analysis work; could arrive later as an
  optimization of the first option, with derived bounds *checking* declared
  ones.
- **Just raise the cap / make it configurable at the harness level.**
  Treats the symptom: the adapter still needs a per-game number, and a
  too-generous global cap turns non-terminating bugs into hangs instead of
  errors.

**Current recommendation: the declaration, now.** It is a one-clause
grammar addition, it replaces both constants with one auditable number, it
converts the Palace crash class into a legible diagnostic, and it supplies
what the OpenSpiel adapter must report anyway. Static derivation can layer
on later without changing the surface.

Related: the OpenSpiel-target section of [../../CLAUDE.md](../../CLAUDE.md)
(why the adapter's reported bound matters);
[turn-loop-form](turn-loop-form.md) (the loop construct whose iterations the
bound governs in non-trick games).
