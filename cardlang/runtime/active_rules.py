"""Active-[[rule]] computation for a [[phase]], including its [[mode]]s.

The rules a trick round asks are built down the chain of phases enclosing it
(decisions.md "Sub-phase rule and legal-move deltas"). Each phase starts from its
parent's set, or from nothing when its own `active_rules:` entries hold a plain
entry, applies those entries, then layers on the deltas of whichever of its
modes currently hold; a mode's plain entry adds, since a mode is a condition on
its phase and never replaces the phase's set. Hearts' `hearts_not_broken` /
`hearts_broken` are one condition's two sides: the mode declaring the
`transition_to` is the "before" side (it holds until a target has fired), its
target the "after" side. A fired transition is recorded in
`RuntimeState.fired_transitions`, and the phase declaring the mode discards it
when it is entered (`driver.run_phase`).

Modes are INDEPENDENT conditions, not an exclusive state machine. A phase may
hold several and any number may be active at once, their deltas stacking in
declaration order — which is what lets two unrelated conditions ("hearts have
been broken", "the queen has gone") be written as two mode pairs instead of as
the four modes of their product.

Contract
--------
Assumes: resolve has guarded the mode-role invariant — every mode is exactly one
of a transition SOURCE or a transition TARGET (`_check_modes`). Both functions
here rely on it: a mode that were both would be read as a source and its
target-ness ignored, and a mode that were neither could never be active at all.
Establishes: the active rule set for one chain of phases at one moment, and the
exits live at that moment in every phase of the chain.
"""

from __future__ import annotations

from cardlang.ast import nodes as n
from cardlang.runtime.state import RuntimeState


def compute_active_rules(
    chain: tuple[n.Phase, ...], rs: RuntimeState
) -> tuple[n.RuleDef, ...]:
    names: list[str] = []
    for phase in chain:
        own = [
            ref for item in phase.items if isinstance(item, n.ActiveRules) for ref in item.refs
        ]
        if any(ref.delta == "plain" for ref in own):
            names = []
        for ref in own:
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
    if ref.delta in ("plain", "add"):
        names.append(ref.name)
    elif ref.delta == "remove":
        names[:] = [name for name in names if name != ref.name]


def _mode_active(mode: n.Mode, rs: RuntimeState) -> bool:
    """Whether one mode currently holds.

    A SOURCE mode holds until ANY of its targets has fired — `any`, not the
    first transition alone, because a condition may have several triggers
    ("hearts are broken by a heart or by the queen") and ending only on the one
    that happens to be written first is a silently wrong answer, not a
    restriction anybody chose.

    A TARGET mode holds once its own name has fired. The two branches are
    exhaustive because resolve guards the roles: a mode with no transition is one
    some sibling names.
    """
    if mode.transitions:
        return not any(t.mode in rs.fired_transitions for t in mode.transitions)
    return mode.name in rs.fired_transitions


def active_mode_exits(
    chain: tuple[n.Phase, ...], rs: RuntimeState
) -> list[tuple[n.Mode, tuple[n.TransitionTo, ...]]]:
    """Each currently-holding mode of every phase in the chain, paired with its
    own exits: a trick in a nested phase ends an enclosing phase's mode.

    A transition is an EXIT FROM a condition, so it exists only while that
    condition does — and the pairing is what carries that. A flat list of
    transitions loses which mode owns each one, and then a source mode with two
    targets reaches BOTH: two mutually alternative "after" modes hold at once
    with their rule deltas stacked. The caller needs the grouping, not just the
    filter, because one play can satisfy two of a single mode's exits — mode
    activity is re-checked here per play, but not between two exits of the same
    mode inside one play (`_fire_transitions` owns that, by stopping at the
    first exit that fires).

    Evaluated per play rather than cached per pass, because a mode goes
    inactive mid-pass: the transition that deactivates it is fired by a play
    inside the very trick this list is consulted for.
    """
    return [
        (item, item.transitions)
        for phase in chain
        for item in phase.items
        if isinstance(item, n.Mode) and _mode_active(item, rs)
    ]
