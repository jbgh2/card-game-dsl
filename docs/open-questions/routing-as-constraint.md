# Routing as constraint

**Tier 3 — medium impact, narrow scope.**

Getaway's `FirstTrickAlwaysGoesToWaste` is structured as a
phase-level routing override, not a rule. This suggests a distinct
category of phase-level configuration beyond rules:

- Rules (constrain candidate moves)
- Routing overrides (modify where moves' cards go)
- Outcome overrides (modify which player is the outcome)
- Event observers (side effects on events)

Open question: are these all rules in some generalized sense, or
distinct kinds of phase-attached configuration?
