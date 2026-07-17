"""Active-rule computation for a phase, including conditional rule-delta
sub-phases.

A phase's active rules are its plain `active_rules` entries plus the deltas
contributed by any *rule-delta sub-phase* that is currently active. Hearts'
`hearts_not_broken` / `hearts_broken` are rule-delta sub-phases: the one holding
the `transition_to` is the "before" state (active until its target has fired);
its target is the "after" state. A fired transition is recorded in
`RuntimeState.fired_transitions`, which resets each loop iteration.
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
        if isinstance(item, n.Phase) and _is_rule_delta(item):
            if _delta_active(item, rs):
                # Only `active_rules` is folded. A `legal_moves` here would have
                # no effect, which is exactly why resolve rejects one
                # (`_check_rule_delta_subphases`); none reaches this loop.
                for sub in item.items:
                    if isinstance(sub, n.ActiveRules):
                        for ref in sub.refs:
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


def _is_rule_delta(phase: n.Phase) -> bool:
    """A sub-phase that only configures rules (no statements / nested phases).

    `LegalMoves` is admitted so a config-only sub-phase that carries one still
    classifies as a rule-delta phase — which lets resolve identify and reject
    it (`_check_rule_delta_subphases`), since a `legal_moves` here is honored
    by no consumer. It is never folded; a rule-delta phase reaching runtime has
    only `active_rules`/`transition_to` in force.
    """
    return all(
        isinstance(item, (n.ActiveRules, n.LegalMoves, n.TransitionTo))
        for item in phase.items
    )


def _delta_active(phase: n.Phase, rs: RuntimeState) -> bool:
    transition = next((i for i in phase.items if isinstance(i, n.TransitionTo)), None)
    if transition is not None:
        # "before" sub-phase: active until its transition has fired.
        return transition.target not in rs.fired_transitions
    # "after" sub-phase: active once it has been transitioned to.
    return phase.name in rs.fired_transitions


def phase_transitions(phase: n.Phase | None) -> list[n.TransitionTo]:
    """The transitions declared by a phase's rule-delta sub-phases."""
    if phase is None:
        return []
    out: list[n.TransitionTo] = []
    for item in phase.items:
        if isinstance(item, n.Phase) and _is_rule_delta(item):
            out.extend(i for i in item.items if isinstance(i, n.TransitionTo))
    return out
