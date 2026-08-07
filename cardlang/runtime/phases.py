"""Active-rule computation for a phase, including its modes.

A phase's active rules are its plain `active_rules` entries plus the deltas
contributed by whichever of its modes currently hold. Hearts' `hearts_not_broken`
/ `hearts_broken` are one condition's two sides: the mode declaring the
`transition_to` is the "before" side (it holds until a target has fired), its
target the "after" side. A fired transition is recorded in
`RuntimeState.fired_transitions`, which resets each loop iteration.

Modes are INDEPENDENT conditions, not an exclusive state machine. A phase may
hold several and any number may be active at once, their deltas stacking in
declaration order — which is what lets two unrelated conditions ("hearts have
been broken", "the queen has gone") be written as two mode pairs instead of as
the four modes of their product.

Contract
--------
Assumes: resolve has walled the mode-role invariant — every mode is exactly one
of a transition SOURCE or a transition TARGET (`_check_modes`). Both functions
here rely on it: a mode that were both would be read as a source and its
target-ness ignored, and a mode that were neither could never be active at all.
Establishes: the active rule set for one phase at one moment.
"""

from __future__ import annotations

from cardlang.ast import nodes as n
from cardlang.runtime.state import RuntimeState


def compute_active_rules(phase: n.Phase | None, rs: RuntimeState) -> tuple[n.RuleDef, ...]:
    if phase is None:
        return ()
    names: list[str] = []

    for item in phase.items:
        if isinstance(item, n.ActiveRules):
            for ref in item.refs:
                _apply_ref(names, ref)

    for item in phase.items:
        if isinstance(item, n.Mode) and _mode_active(item, rs):
            for block in item.active_rules:
                for ref in block.refs:
                    _apply_ref(names, ref)

    seen: dict[str, None] = {}
    for name in names:
        seen.setdefault(name, None)
    return tuple(rs.rule_index[name] for name in seen)


def _apply_ref(names: list[str], ref: n.RuleRef) -> None:
    if ref.op in ("plain", "add"):
        names.append(ref.name)
    elif ref.op == "remove" and ref.name in names:
        names.remove(ref.name)


def _mode_active(mode: n.Mode, rs: RuntimeState) -> bool:
    """Whether one mode currently holds.

    A SOURCE mode holds until ANY of its targets has fired — `any`, not the
    first transition alone, because a condition may have several triggers
    ("hearts are broken by a heart or by the queen") and ending only on the one
    that happens to be written first is a silently wrong answer, not a
    restriction anybody chose.

    A TARGET mode holds once its own name has fired. The two branches are
    exhaustive because resolve walls the roles: a mode with no transition is one
    some sibling names.
    """
    if mode.transitions:
        return not any(t.target in rs.fired_transitions for t in mode.transitions)
    return mode.name in rs.fired_transitions


def active_transitions(phase: n.Phase | None, rs: RuntimeState) -> list[n.TransitionTo]:
    """The transitions that can still fire: those of modes that currently hold.

    A transition is an EXIT FROM a condition, so it exists only while that
    condition does. Returning every mode's transitions unconditionally loses
    which mode owns each one, and a source mode with two different targets then
    keeps its second exit live after its first has fired — both targets end up
    reached, and two mutually alternative "after" modes hold at once with their
    rule deltas stacked.

    Evaluated per play rather than cached per pass, because a mode goes
    inactive mid-pass: the transition that deactivates it is fired by a play
    inside the very trick this list is consulted for.
    """
    if phase is None:
        return []
    return [
        transition
        for item in phase.items
        if isinstance(item, n.Mode) and _mode_active(item, rs)
        for transition in item.transitions
    ]
