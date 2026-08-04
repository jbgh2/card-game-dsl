"""Cheat's half of the per-game seam.

Deliberately a THIN module. Cheat's rules text, decision facts and baseline
policy stay exactly where they were written — `prompts.py`, `metrics.py`,
`agents.py` — and this module only names them as one game's pack. Moving them
here would have been tidier and would have rewritten the code behind every
number in `REVIEWER.md`, which is a cost with no reader.

So the split to read in the diff is: Cheat's behaviour did not change, and the
seam is what is new.
"""

from __future__ import annotations

from typing import Any

from .agents import Agent, DecisionView, RuleAgent
from .metrics import decision_facts as decision_facts
from .prompts import RULES_RAW as RULES_RAW, RULES_RENDERED as RULES_RENDERED


def build_rule_agent(spec: dict[str, Any], seed: int) -> Agent:
    """Cheat's competent non-learning baseline: truthful when it can be,
    challenging what it can prove plus a fixed random share."""
    return RuleAgent(
        seed=seed,
        challenge_prob=float(spec.get("challenge_prob", 0.1)),
        bluff_prob=float(spec.get("bluff_prob", 0.0)),
        name=spec.get("name", "rule"),
    )


__all__ = [
    "RULES_RAW",
    "RULES_RENDERED",
    "DecisionView",
    "build_rule_agent",
    "decision_facts",
]
