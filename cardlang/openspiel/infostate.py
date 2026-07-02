"""The general information state (perfect recall, per player) — derived, not
hand-authored.

A player's information state is a pure function of (a) their projected view of
every zone through its declared library-type visibility, (b) the declared
state variables — public by convention: hidden information lives only in
zones (SP1 spec, "State variables are public"), and (c) their accumulated
per-observer observation log (perfect recall; a `Muck`'s contents are trivial
going forward while prior observations persist in the log). The string is
deterministic and human-readable — it doubles as the designer/LLM feed.
"""

from __future__ import annotations

from typing import Any

from cardlang.runtime.observe import view_of
from cardlang.runtime.state import RuntimeState


def _render(value: Any) -> str:
    if isinstance(value, dict):
        items = sorted(value.items(), key=lambda kv: repr(kv[0]))
        return "{" + ",".join(f"{k}:{_render(v)}" for k, v in items) + "}"
    if isinstance(value, (list, tuple, set, frozenset)):
        return "[" + ",".join(sorted(_render(v) for v in value)) + "]"
    return str(value)


def _zone_line(rs: RuntimeState, name: str, key: Any, player: int) -> str:
    zone = rs.zones.single(name) if key is None else rs.zones.instance(name, key)
    view = view_of(rs, name, key, player, zone.cards)
    label = name if key is None else f"{name}[{key}]"
    if view is None:
        return f"{label}=?"
    if isinstance(view, int):
        return f"{label}=#{view}"
    return f"{label}=[" + ",".join(view) + "]"


def information_state(
    player: int, rs: RuntimeState, obs_log: list[tuple[Any, ...]]
) -> str:
    zones = [
        _zone_line(rs, name, None, player) for name in sorted(rs.zones.singles)
    ] + [
        _zone_line(rs, name, key, player)
        for name in sorted(rs.zones.families)
        for key in sorted(rs.zones.families[name])
    ]
    merged: dict[str, Any] = {}
    for frame in rs.frames:  # later frames shadow earlier (phase-local over game)
        merged.update(frame)
    state_vars = ";".join(f"{k}={_render(v)}" for k, v in sorted(merged.items()))
    obs = ";".join(repr(e) for e in obs_log)
    return f"P{player}|" + ";".join(zones) + f"|state:{state_vars}|obs:{obs}"


# ============================================================================
# Legacy: Hearts-specific encoding (kept for backward compatibility; to be
# removed in Task 9 when game.py and tests no longer import it)
# ============================================================================


def hearts_information_state(
    player: int, rs: Any, observed_log: list[tuple[int, int, str]]
) -> str:
    hand = sorted(str(c) for c in rs.zones.instance("hand", player).cards)
    # Public plays (visible to all) + this player's own pass picks.
    observable = [
        (pl, aid) for (pl, aid, kind) in observed_log if kind == "play" or pl == player
    ]
    scores = rs.get(rs.score_var) if rs.score_var else {}
    score_str = ",".join(f"{p}:{scores[p]}" for p in sorted(scores))
    return f"P{player}|hand={hand}|obs={observable}|scores={score_str}"
