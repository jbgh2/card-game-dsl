# LLM player seats: a second runtime target sharing the kernel

*Exploratory design analysis — a proposal, not settled spec. Motivated by
open-communication games (Codenames, Spyfall, Concept, Noobs in Space,
Werewolf-family) that the OpenSpiel target rightly excludes, but that become
playable if an LLM (or a human) occupies a seat. Related survey material:
`../research/topology-and-query-requirements.md`, "collection spot-checks".*

## The claim

The work this project already treats as load-bearing — deriving each
player's information set from zone visibility plus observation events —
produces, as a side effect, exactly the interface an LLM player needs. An
agent in a seat requires two things: its legal actions, and everything it
has observed so far. The kernel already derives both, per observer, and the
OpenSpiel adapter already serializes the observation stream into an
information-state string. That same string, rendered as prose instead of a
tensor, is an LLM's prompt context. Nothing about info-set derivation is
speculative here; the LLM seat is a second *consumer* of the same stream.

This means one game description can serve three consumers without
modification: a classical solver (via OpenSpiel — CFR, IS-MCTS,
determinization), an LLM agent (via the projected observation history +
legal-action list), and a human UI (the same projected history, rendered).
Mixed tables fall out for free: a human, an LLM, and a search bot can occupy
three seats of the same game because every seat consumes the identical
derived interface. In the kernel's decision-interpreter direction
(`kernel-extensibility.md`), a seat is just a chooser; which intelligence
answers the choice is a runtime binding, not a language question. A fourth
binding falls out for free: the automa — modern solo modes drive a
pseudo-player from a rules-defined policy (flip a card, follow its
flowchart), i.e. a chooser bound to a policy function that is itself part
of the game description.

## The one new primitive: the opaque utterance

The games that motivate this need exactly one construct the language lacks:
an utterance action — `say`-shaped — whose payload is designer-opaque text
and whose audience is a declared observer set. It routes through the
existing projection machinery like any observation event, and the full
projection lattice transfers to the channel unchanged, so communication
*regimes* become declarations: `identity` to all is public table talk;
`identity` to the audience with `existence_only` to others is Diplomacy —
everyone sees "France and Russia spoke", no one else hears content (the
physical game's leave-the-room reality, made formal); `count_only` to
others is traffic analysis — how much they spoke, which a long physical
negotiation already leaks; `trivial` is a genuinely secret channel; and
per-observer maps admit asymmetries the physical table cannot host, such
as a wiretap (`identity` to one eavesdropper, `existence_only` to the
rest). Once utterances are projected events, the who-talks-to-whom graph
is first-class game state — scorable, restrictable, deducible-over — and
communication metadata joins the certified information set (a Diplomacy
seat can legitimately reason from "France spent a long time with Russia"
without that being a harness leak). The engine's guarantees are unchanged: indistinguishability and
soundness are claims about what the *engine* emits, and the engine emits
nothing hidden. Players voluntarily leaking their private information
through the channel is not a leak — it is the game (Codenames is nothing
else). Perfect recall holds trivially: utterances are ordinary events in
the per-observer history.

Two properties make this cheap rather than corrosive:

- **It does not touch OpenSpiel compilation.** An unbounded text payload
  cannot be an OpenSpiel action space, so games using the utterance simply
  do not compile to the OpenSpiel target — a static, per-game fact the
  compiler can state plainly. Everything else about the game (hidden zones,
  probes, scoring, win conditions) still checks under the same kernel.
- **Digital runtime inverts communication enforcement.** At a physical
  table, "no talking" (Sky Team) and constrained hint grammars (Hanabi) are
  honor-system rules. When the engine owns the only channel, an absent or
  grammar-constrained channel is enforced by construction. The utterance
  primitive's *restrictions* are as expressible as its presence.

## The channel ladder

Witnesses, ordered by how formal the communication channel is — which is
also the implementation ladder:

1. **Sky Team** — empty channel (communication banned). Fully formal today;
   OpenSpiel-classical. The ban itself becomes enforceable by construction.
2. **Hanabi** — constrained formal channel (hint grammar over declared
   projections — the existing axis-2 gate in `generalization-path.md`).
   OpenSpiel-classical once axis 2 lands.
3. **Concept** — the sleeper: clues are marker placements on a fixed board
   of icons — a finite, enumerable action space, mechanically hostable under
   the existing model with no utterance primitive at all. Only the
   *semantics* are open; a classical solver would flail, an LLM plays it
   directly. The cheapest full LLM-seat witness.
4. **Codenames** — one open-text word plus a number. Needs the utterance;
   clue legality splits into a mechanical part (not a word on the board)
   and a judged part (no derivatives/rhymes) — a judge seat, which may
   itself be an LLM or a human.
5. **Spyfall, Noobs in Space, Werewolf-family** — unbounded dialogue. Pure
   utterance; roles, location, voting, and accusation mechanics are all
   ordinary hidden-zone machinery (Spyfall's location card is a zone
   visible to all observers except one — an already-legal projection map).

## The evaluation angle

The same architecture makes the corpus a testing ground for LLMs, with an
edge no hand-rolled game harness has. Existing LLM game benchmarks
(Diplomacy, Werewolf/Avalon, Hanabi) assemble each model's prompt by hand,
and hand-assembled prompts are exactly where such evals fail — leaking
hidden state into a model's context invalidates the result silently. Here
the prompt *is* the derived per-observer stream, and the indistinguishability
proofs the harness already runs are a machine-checked guarantee that the
eval leaks nothing: certified-fair hidden information. Three further
properties follow. Every game added to the corpus is automatically an eval
— the seat interface falls out of the description, so the suite grows at
the cost of writing rules, not harnesses. Because the solver target shares
the kernel, IS-MCTS/CFR can occupy the adjacent seat, giving LLMs a
calibrated skill baseline (and humans a third point of comparison) inside
the same game instance, rather than LLM-vs-LLM round-robins. And the
deception games measure something no static benchmark touches: whether a
model can sustain a false persona under adversarial probing — Spyfall is
structurally a Turing test, run inside the game, in both directions at
once (the spy passing as located; the model passing as human).

One load-bearing caveat: **perfect recall is a confound.** An artificial
seat receives its full projected transcript by default — the equivalent of
the Clue player who writes down every suggestion and refutation and
usually wins, because they are the only one at the table playing the game
as formally defined. Deduction games split into an *inference gap*
(Cryptid: hard even with perfect notes) and a *memory gap* (Clue largely,
Memory/Concentration entirely — near-trivial under perfect recall, games
only because humans forget). An LLM beating humans at a memory-gap game
demonstrates recall, not reasoning. Because the engine knows precisely
what each seat's full information set is, degraded recall (truncated or
summarized transcripts) is a controlled experimental variable — and the
same lever expresses, in a digital runtime, the note-taking rules that
physical tables leave to convention (Clue ships a notepad; Hanabi tacitly
forbids one).

## What this note does not settle

Whether the utterance is a kernel verb or a runtime-level action outside
the language; how a judge seat is declared (it resembles a chooser with a
restricted decision domain); how real-time pressure (Noobs' timer) maps to
turn budgets, if at all; how utterance events should render into the
information-state string (verbatim transcript is the obvious start); and
evaluation — "see what happens" wants game logs and replays, which
determinism already gives, but says nothing about measuring play quality.
None of these blocks the observation that the architecture is already
pointed the right way: derived info sets were built for solvers, and they
turn out to be the LLM seat's entire interface.
