# What produced these transcripts

One invocation: `results_holdem/runs/2026-08-04T06-09-30Z/`, whose `summary.json`
records what it spent and how far it got.

```
python -m experiments.llm_eval.run_eval --config experiments/llm_eval/config_holdem.yaml
```

Wall clock **2026-08-04T06:09:30Z to 07:11:50Z**, 62m20s. Cost $6.3340 —
**tokens times the list-price table in `providers.py`**, not a billing figure.

## The code, because the fingerprint cannot carry it

Each matchup's `*.treatment.json` records the config that produced it — the
game, the agent blocks, `rotate`, `max_decisions`, the seed start, the models.
It does **not** record the code, and for this run that distinction is load-bearing:

> **These transcripts were produced under commit `9c06d41`** ("Heads-up
> Hold'em's harness pack"), which carries the WIDENED pre-flop range in
> `HoldemRuleAgent`. An earlier policy in the same session — same
> `aggression: 0.25`, therefore the same fingerprint byte for byte — folded 57%
> of the decisions where folding was legal and finished +43 chips over 400 hands
> against random, against +539 for the policy here. Two runs of that pair are
> indistinguishable from their `treatment.json` alone.

The runs made under the earlier policy were deleted rather than archived, so
nothing here is ambiguous; this note exists so the *reason* they were deleted
survives, and so a future run under a changed baseline cannot quietly join this
directory. Issue #220 owns the general case (a resume can mix two treatments
because the fingerprint checks config and not the code that builds the prompt).

## The game tree, which the transcripts also cannot carry

These transcripts record decisions made against the corpus game as it stood at
that commit, and two betting corrections have landed since. The first, issue
#198, retires the `order priority` value so every betting round takes the ring:
it moves the decision order of every poker game with three or
more seats and, for a two-seat game, moves nothing — at a street's first decision
both seats are pending and the pointer is at the leader, so a re-scan from the
leader picks the seat the pointer already names, and after either seat acts it
stops being pending. The two traversals agree at every decision. The second,
issue #237, gives an un-acted seat that owes nothing its `raise` option, which
DOES move this game: the big blind facing a limped pot decides at a node these
files do not contain, so a transcript here shows it offered `check` alone.

So a rate recomputed from these files is a rate against the tree of that run,
and that tree is no longer the corpus game's. That is what a record of real
model responses is for — the transcripts are not regenerable (below), so they
are read as evidence about the models under a stated tree, never as a current
benchmark of the corpus game. Re-running under the current tree would draw a
fresh sample rather than replicate this one, which is why the divergence is
recorded here instead.

## Recompute every published rate

```bash
python -m experiments.llm_eval.verify --game cardlang_holdem_heads_up \
  --dir experiments/llm_eval/results_holdem/transcripts
```

`verify.py` deliberately does not call `metrics.aggregate`: for this game it
re-derives every rate from the referee's own `legal`/`action` record rather than
from the pack's `facts`, so a bug in the pack shows up as a disagreement instead
of being reproduced by an auditor sharing its input.

Transcripts are **not regenerable** — they hold real model responses, which are
not deterministic — so these files are the record, not a cache. Re-running draws
a fresh sample; it is not replication.
