"""Hearts information-state encoding (perfect recall, per player).

A player observes: their own hand, every card played to a trick (public), their
own pass selections, and the scores. They do NOT observe other players'
un-played cards or other players' pass selections. The encoding reads only
``hand[player]`` and the player-observable slice of the action log, so it cannot
leak hidden information. These observation rules are Hearts-specific.
"""

from __future__ import annotations

from typing import Any


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
