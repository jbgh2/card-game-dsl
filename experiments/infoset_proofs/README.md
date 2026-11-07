# Spike: machine-checked information-set properties — 2026-11-07

**This is a dated spike report. Its counts and measurements describe what we
found on 2026-11-07 and do not update. The living spec is in `docs/`.**

## The question

Can a proof assistant prove the information-set properties the OpenSpiel
target rests on (`docs/open-questions/structural-infoset-proofs.md`)? If it
can, what does such a proof teach us that the sampled harness in
`tests/openspiel_ready/` does not? The method follows the shape of Anthropic's
FlashProve work (anthropic.com/research/provable-inference, 2026-11-02):

- A formal model states the properties.
- The proofs are checked mechanically.
- The production code is held to the model by execution, not by proof.
- The gap between model and code is stated rather than hidden.

## What was built

| Artifact | What it is |
|---|---|
| `coq/Kernel.v` | A core calculus of the kernel's information model, and three theorems over it. It models zones with per-observer projections (trivial / count / identity, the levels `ZONE_PROJECTIONS` declares), public state variables, newest-first per-seat logs of the five `EVENT_PAYLOADS` kinds, a chosen movement with a guarded menu, a deal, a reveal, an assignment and a branch. |
| `coq/Witnesses.v` | The issue #755 fixture and a new state-recall witness, transcribed into the calculus, with computed counterexamples and a non-vacuity corollary. |
| `coq/Audit.v`, `coq/build.sh` | `Print Assumptions` for every theorem. On 2026-11-07 every theorem printed "Closed under the global context", meaning no axioms and no admitted lemmas. A clean build took 4 s. |
| `witnesses/state_recall.cardlang` | An engine witness. The checker accepts it, and it breaks perfect recall. |
| `probe_state_recall.py` | Runs that witness in the real engine. |
| `probe_recall_corpus.py` | A perfect-recall oracle over every registered game. It uses Constructed Worlds (`resample`): worlds a seat cannot tell from the true one at the pause. |
| `probe_ask_sites.py` | Lists, for each registered game, the ask payloads that more than one decision site emits. |

The prover is Coq 8.18 from Ubuntu's apt archive. We tried Lean 4 first, but
its toolchain ships from GitHub releases, and this environment's proxy refuses
github.com. Nothing here relies on a Coq-specific feature: the development
would port to Lean almost line for line.

## Theorems

Let `s` be a program the checker accepts (`checked`). That means:

- every chosen movement's pool is identity-visible to its decider;
- every read in its menu passes the Hidden Read judgement for that decider
  (`x_ok`, the model's `stdlib.zones.reveals`);
- no condition is placed on any branch.

1. **`guard_view`: the Hidden Read judgement is sound for menus.** A menu that
   passes it evaluates the same on any two worlds the decider sees alike.
2. **`legal_agreement`: OpenSpiel's legal-action requirement holds.** Take any
   two runs, from any starts and with any pick sequences. If two decisions of
   seat `p` fall in one information set, they offer the same menu. The premise
   is that the `asked` event tells the program's decision sites apart. No
   analysis of branches is needed. The proof factors into Theorem 1 plus one
   fact: the newest event in the decider's log names the site.
3. **`pub_from_log`: assignments cannot cause forgetting once they are logged.**
   If an assignment emits an observation event, the public state at any
   decision is a function of the decider's log. Two decisions with equal logs
   see equal public state.

Counterexamples, computed:

- **`control_branch_breaks_agreement`.** With the engine's coarse ask (phase,
  construct, count, destination), issue #755's fixture passes `checked`, yet
  seat 0 has one information set that offers two different menus.
- **`sited_ask_reveals_branch`.** Under a site-naming ask, the same two worlds
  are told apart, so seat 0 learns which branch ran: a fact about seat 1's
  hidden card.
- **`control_branch_agrees_when_sited`.** Theorem 2 instantiated on the
  fixture. Its premises are satisfiable, so the theorem is not vacuous.
- **`state_recall_forgets`.** Both runs make the same picks. Seat 0 can tell
  the worlds apart at its first decision but not at its second, which is
  imperfect recall. A site-naming ask does not prevent it.
- **`state_recall_logged_remembers`.** Logging the assignment separates the
  second decisions.

## Findings

### 1. Public state variables can break perfect recall (new)

`docs/decisions.md` states that "`forget` is the only operation that breaks
perfect recall." That is false of the engine. Consider this sequence:

1. An assignment reads something a seat cannot see. `AssignStmt.value` is
   `READ_POSITION_OUTSIDE`, on the reasoning that "state is public, so an
   assignment is an announcement".
2. The seat decides while it can see the variable.
3. The variable is overwritten before the seat's next decision.

At the second decision, nothing in the seat's information state records what
it saw at the first. An assignment emits no observation event, and the
information state renders only the current value. The model predicted this
before any engine run (`state_recall_forgets`), and `probe_state_recall.py`
reproduces it in the real engine:

```
seed 0 first : ...|state:flag=0;...|obs:('move', 'deck', 1, 'hand[1]', 1);('asked', 'peek', 'choose', 1, None)
seed 1 first : ...|state:flag=1;...|obs:('move', 'deck', 1, 'hand[1]', 1);('asked', 'peek', 'choose', 1, None)
seed 0 second: ...|state:flag=0;...|obs:...;('chose', 0);('announce', 0, 0);('asked', 'peek', 'choose', 1, None)
seed 1 second: ...|state:flag=0;...|obs:...;('chose', 0);('announce', 0, 0);('asked', 'peek', 'choose', 1, None)
```

The current guards miss it:

- `test_perfect_recall_logs_are_append_only` checks that each log only grows,
  which this witness satisfies.
- The swap proof compares worlds at the pause, which this witness passes.
- The Constructed World sampler accepts on the pause's information state and
  the log, so it constructs exactly these worlds.

Corpus measurement, 2026-11-07 (`probe_recall_corpus.py`):

- **Method.** Six seeded uniform lines per game. At picks 1, 2, 3, 5, 8, 12,
  20 and 30 the oracle constructed a world, then compared the seat's
  information state at each of its earlier decisions.
- **The oracle works.** It reported "RECALL FAILS" on the witness in all 37
  runs.
- **No corpus game failed.** Every game the sampler builds worlds for passed.
  That is 28 games, with up to 48 constructed worlds compared per game.
- **Not measured.** Nine games run 0 comparisons because the sampler refuses
  them ("repeated cards": breakthrough, canasta, coup, doppelkopf,
  english_draughts, hex, nine_mens_morris, pinochle, tic_tac_toe).

So the gap is reachable but, as far as these samples show, not exercised by
the corpus. Two fixes the model supports:

- **Log assignments.** `pub_from_log` shows this is enough for the
  public-state half. It changes every information-state string, so the
  goldens would need regenerating; it should change no corpus partition
  except where a game actually forgets.
- **Refuse unlogged declassification.** Judge `AssignStmt.value` the way a
  `READ_POSITION_NO_SEAT` read is judged. This would refuse games that
  publish a hidden fact on purpose. #471 is the Primitive-shaped sibling of
  that choice.

Searched before reporting: #471 (a Primitive's result published into state),
#755 (a branch chooses the menu), #999 (the observation epic). None covers
assignments and recall.

### 2. Issue #755 is two questions, and only one needs a static analysis

Theorem 2 shows that OpenSpiel's legal-action requirement follows from:

- the menu-position Hidden Read judgement the checker already has; plus
- an ask that names its decision site.

So "the engine records the fact the branch read", one of the two fixes #755
lists, can be done by putting a site identity in the `asked` event. That makes
the partition well-formed for every program by construction.

What it does not settle is Honest Play. Under a site-naming ask, a branch on
hidden cards shows up as a leak in the seat's information state
(`sited_ask_reveals_branch`) rather than as an inconsistency. Whether such a
game is mis-modelled is still the checker's call. The checker's call is now a
lint question, not a soundness question.

What the corpus relies on today, 2026-11-07 (`probe_ask_sites.py`, eight
uniform lines per game, no line errored). Fourteen of the 37 registered games
have at least one ask payload that more than one site emits. The
`control_branch` fixture is the control case; the probe flags it.

| Game | Ask payload `(phase, construct, count, destination)` | Sites |
|---|---|---|
| Belote | `play, offer, 1, None` | 4 |
| Canasta | `play, offer, 1, None` | 3 |
| Cheat | `play, offer, 1, None` | 2 |
| Coup | `play, offer, 1, None` | 5 |
| Doppelkopf | `play, offer, 1, None` | 4 |
| Doppelkopf | `play, transfer, 1, trick_pile` | 4 |
| English Draughts | `play, offer, 1, None` | 2 |
| Five Hundred | `play, offer, 1, None` | 2 |
| Five Hundred | `play, transfer, 1, trick_pile` | 8 |
| Gin Rummy | seven payloads across `turn_one`, `play`, `showdown` | 2–3 each |
| Nine Men's Morris | `play, offer, 1, None` | 4 |
| Oh Hell | `bidding, choose, 1, None` | 2 |
| Pinochle | `play, offer, 1, None` | 4 |
| Schnapsen | `play, transfer, 1, trick_pile` | 2 |
| Skat | `play, offer, 1, None` | 7 |
| Skat | `play, transfer, 1, trick_pile` | 6 |
| Tichu | `play, climb, 1, None`: the climb's turn and its hosted bomb-window poll | 2 |
| Tichu | `play, offer, 1, None` | 4 |

The Tichu row deserves the closest look. A seat asked in the climb and a seat
asked in the bomb window receive the same ask. The shared proofs cover the
bomb window only on its declining line (issue #765). Whether the log alone
always tells the seat which of the two it is answering is not shown here.

At each of these, the partition is sound only because the branch or sequence
choosing between the sites is one the asked seat can follow. In Doppelkopf it
is the seat order of the trick. In Five Hundred it is the public
`is_open_misere`, `tricks_played` and declarer. A control-position wall for
#755 needs to judge exactly these places, and nowhere else. We expect a site-naming ask to leave these partitions unchanged, because the
site is already a function of what the seat can see there. This spike did not
test that; it is the next measurement, a full-width goldens run with the
site in the ask.

### 3. What a proof costs, and where it paid

- **Size.** The calculus and its theorems are about 600 lines of Coq. Every
  proof is a short structural induction.
- **Why it was cheap.** Most of the claims are true by construction. The
  information state is a pure function of the seat's view, the public state
  and the log, so the theorems reduce to facts about what each kernel step
  emits.
- **What would be expensive.**
  - Loops and the round forms.
  - The zone half of perfect recall: replaying a seat's view from its log.
  - A flow-sensitive control check that accepts a reveal before a branch (the
    GOPS pattern #755 names). This is relational, a two-run lockstep proof.
  - Connecting the model to the engine. Here we did that only by execution.
- **Where it paid.** The value came from having to write the property down
  formally. Stating perfect recall precisely, as same information set now
  implies same earlier information sets, is what surfaced Finding 1. The
  existing pin is the weaker "the log is append-only", and the witness that
  breaks the real property passes that pin. Every finding here was then
  confirmed by running the engine: the model proposes, and execution decides.

## What this does not prove

- **That the engine is the model.** The calculus is hand-written, and nothing
  mechanically ties `cardlang/runtime/` to `Kernel.v`. Agreement rests on the
  probes. The FlashProve report states the same gap for its C++ verifier.
- **Anything about constructs the calculus leaves out.** These are loops,
  rounds, `as <expr>`, simultaneous decisions, offers, zone order, the
  undeclared projection levels, and Primitives. The leak-freedom of
  Primitives rests on their `reads` declarations.
- **That a declared visibility matches the real game.** That stays a question
  for the rules source.
- **Anything beyond the sampled lines.** The corpus probes are samples. A
  green probe means no counterexample on those lines.

## Running it

```
./experiments/infoset_proofs/coq/build.sh            # needs coqc (apt-get install coq)
python experiments/infoset_proofs/probe_state_recall.py
python experiments/infoset_proofs/probe_recall_corpus.py [game ...]
python experiments/infoset_proofs/probe_ask_sites.py [game ...]
```
