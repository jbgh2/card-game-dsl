## Sub-phase rule and legal-move deltas

A sub-phase inherits its parent's `active_rules` — the set in force in the
parent at that moment, the parent's holding modes included. A trick round
asks the set built down the chain of phases enclosing it: each starts from
its parent's, applies its own slot, then layers on its holding modes' deltas
(a mode's plain entry adds; a mode never replaces its phase's set). To modify
the inherited set, the sub-phase uses three operators inside the slot:

```text
phase parent { active_rules: [A, B, C] }

phase child_extend   { active_rules: [+ D] }            // adds D       → A, B, C, D
phase child_remove   { active_rules: [- B] }            // removes B    → A, C
phase child_override { active_rules: [override A2] }    // replaces A   → A2, B, C
```

`override X` matches by name: the parent rule with the same identifier
as `X` is replaced by `X`. If no parent rule matches the override
target, it's a compile error — there's nothing to override.

The delta operators are `active_rules`-only. `legal_moves` takes a
plain list of move-type names, stated directly in each phase that
sets it:

```text
phase parent { legal_moves: [play_to_trick] }
```

A `legal_moves:` is set only by a phase that actually runs. A mode holds
rules, never the move menu, so its body admits no `legal_moves:` at all —
the grammar rejects one, since nothing would consult it and the move menu
must never blink from a condition rather than from the step you are in.

A slot may mix operators and plain entries — a sub-phase that lists
a bare rule is shadowing inheritance with its own complete set:

```cardlang-fragment active_rules_shadowing
phase parent { active_rules: [A, B, C] }
phase child  { active_rules: [X, Y] }                   // X, Y only — parent set discarded
```

**Corpus usage.** Every corpus delta is a `+ X` inside a mode: Hearts and
Spades add the lead restriction while their suit is unbroken. Every
rule-bearing corpus phase runs its own trick round, so none inherits a set
from a parent. `- X` and `override X` are reserved for cases where the
rulebook itself describes a rule being struck out or replaced. The
rulebook-natural reading of every game in the current corpus uses `+ X` even
when the mechanical effect could be expressed as a removal.

**Rules are asked only where a trick round runs.** A rule binds at a trick
round's card decision and nowhere else ("Rule demand forms"), and a mode's
condition changes only on a trick play, so a phase whose `active_rules:` or
modes no trick round in its subtree can ask — its own body, a phase inside
it, or the effect of a move type it offers — is refused, naming the phase. A
climbing round asks no rule. A trick played with chosen moves holds itself to
a rule with a `where` filter on the move (`where follows_lead(card, <pile>)`).

The criterion for which operator to use: write the slot the way the
game's rulebook introduces the change. Rulebooks describe what
*kicks in*, not what *goes away*; the syntax follows.
