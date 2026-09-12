"""The game loop: drives a registered OpenSpiel game and logs a transcript.

The referee holds the state; the agents never do. It reads three things off the
state for the acting player — `information_state_string`, `legal_actions`,
`action_to_string` — and hands them over as a `DecisionView`. It also has full
ground truth, which it uses only for the transcript and the metrics facts, never
for anything an agent sees.

Contract
--------
Assumes: `cardlang.openspiel.game` imports (which requires the `openspiel`
extra) and the corpus directory is present.
Establishes: a `GameRecord` from which the whole game is replayable — `(seed,
history)` is a pure function of the engine, so the transcript needs no state
snapshots to be auditable — and its `game_digest` field, which pins the
`.cardlang` source the recorded action ids were assigned against;
`replay_views` refuses a replay whose `expected_digest` names a different
source rather than silently decoding ids the loaded game may not have.
Illegal after: passing a `pyspiel.State` into anything in `agents.py`.
"""

from __future__ import annotations

import hashlib
import time
from dataclasses import asdict, dataclass, field
from typing import Any

from .agents import Agent, DecisionView
from .metrics import decision_facts, game_key

# The adapter samples the deal space at the root chance node; see
# `cardlang/openspiel/game.py`. Seeds outside the range are not addressable, so
# a matchup with N > NUM_SEEDS would silently reuse deals — `run_eval` refuses.
NUM_SEEDS = 4096


def load_game(short_name: str) -> Any:
    """The registered OpenSpiel game. Importing `cardlang.openspiel.game` is
    what registers every corpus game, so it must precede the load."""
    import pyspiel

    from cardlang.openspiel import game as _adapter  # noqa: F401  (registration)

    return pyspiel.load_game(short_name)


class ProvenanceError(ValueError):
    """A transcript names a digest the loaded game's source does not match."""


def game_digest(short_name: str) -> str:
    """SHA-256 hex digest of the `.cardlang` source bytes registered under
    `short_name`.

    The path comes from `cardlang.openspiel.registry.GAMES` — the same map
    `cardlang/openspiel/game.py`'s own corpus registration loop reads short
    names and files from — joined with that module's games directory, rather
    than a path hard-coded here, so a corpus rename cannot silently point this
    at a stale file. Covers the game SOURCE only: the OpenSpiel action
    encoding a transcript's ids are recorded against also depends on the
    checker and `cardlang.openspiel.encoding.ActionSpace`, and a change there
    with the source untouched is not visible to this digest.
    """
    from cardlang.openspiel.registry import GAMES, _GAMES_DIR

    if short_name not in GAMES:
        raise KeyError(
            f"{short_name!r} is not a corpus game; "
            f"cardlang.openspiel.registry.GAMES names {sorted(GAMES)}"
        )
    return hashlib.sha256((_GAMES_DIR / GAMES[short_name]).read_bytes()).hexdigest()


@dataclass
class Decision:
    """One decision, as recorded."""

    step: int
    player: int
    agent: str
    action_id: int
    action: str
    legal: list[str]
    facts: dict[str, Any]
    llm: dict[str, Any] = field(default_factory=dict)
    infostate: str = ""


@dataclass
class GameRecord:
    """One completed (or truncated) game."""

    matchup: str
    game_index: int
    seed: int
    # The registered OpenSpiel short name. Recorded per RECORD, not only in the
    # run summary and the treatment sidecar beside it, because a transcript that
    # travels alone otherwise loses its identity — which is what let `verify.py`
    # fold a poker archive with Cheat's rate table and exit 0.
    game: str
    # SHA-256 of the `.cardlang` source `game` names (`referee.game_digest`).
    # A record without this key still loads: every reader here treats a
    # record as a dict of the specific keys it uses, never a required set, and
    # only a caller that asks `replay_views` for provenance needs this one.
    game_digest: str
    seats: dict[int, str]
    history: list[int]
    decisions: list[Decision]
    returns: list[float]
    terminal: bool
    truncated: bool
    num_decisions: int
    wall_seconds: float
    # Per-agent token spend for THIS game (spec §5 asks for tokens per game, not
    # only per run). Summed from the attempts actually made, so a retry counts
    # twice — which is the honest figure, since both calls were billed.
    usage: dict[str, dict[str, int]] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        out = asdict(self)
        out["seats"] = {str(k): v for k, v in self.seats.items()}
        return out


def play_game(
    game: Any,
    agents: dict[int, Agent],
    seed: int,
    matchup: str,
    game_index: int,
    max_decisions: int = 0,
    store_prompts: bool = False,
    store_infostates: bool = False,
) -> GameRecord:
    """Play one game to termination (or to `max_decisions`, if positive).

    A truncated game has `terminal=False` and is excluded from win rates, which
    are reported alongside the truncation count — a game silently scored as a
    loss for whoever happened to be behind would be a fabricated result.
    """
    started = time.monotonic()
    # Which game's facts to record, DERIVED from the loaded game rather than
    # passed beside it. A mismatch between the two would compute one game's
    # metrics over another's transcript and report them without complaint.
    short_name = game.get_type().short_name
    key = game_key(short_name)
    state = game.new_initial_state()
    state.apply_action(seed % NUM_SEEDS)  # the root chance node: the deal

    history: list[int] = []
    decisions: list[Decision] = []
    usage: dict[str, dict[str, int]] = {}
    truncated = False

    while not state.is_terminal():
        if max_decisions and len(decisions) >= max_decisions:
            truncated = True
            break
        player = state.current_player()
        legal = list(state.legal_actions())
        strings = [state.action_to_string(player, a) for a in legal]
        info = state.information_state_string(player)
        view = DecisionView(
            player=player, infostate=info, legal_actions=legal, legal_strings=strings
        )

        agent = agents[player]
        action = agent.choose(view)
        if action not in legal:
            raise AssertionError(
                f"agent {agent.name!r} returned action {action}, which is not "
                f"legal at this decision ({legal}) — a bug in the agent, not a "
                f"game outcome"
            )
        chosen = strings[legal.index(action)]
        trace = agent.pop_trace()
        if trace:
            tally = usage.setdefault(
                agent.name, {"llm_calls": 0, "input_tokens": 0, "output_tokens": 0}
            )
            for attempt in trace.get("attempts", []):
                tally["llm_calls"] += 1
                tally["input_tokens"] += int(attempt.get("input_tokens", 0))
                tally["output_tokens"] += int(attempt.get("output_tokens", 0))
            if not store_prompts:
                trace = {k: v for k, v in trace.items() if k != "prompt"}

        decisions.append(
            Decision(
                step=len(decisions),
                player=player,
                agent=agent.name,
                action_id=action,
                action=chosen,
                legal=strings,
                facts=decision_facts(view, chosen, key),
                llm=trace,
                infostate=info if store_infostates else "",
            )
        )
        history.append(action)
        state.apply_action(action)

    returns = (
        [float(r) for r in state.returns()]
        if state.is_terminal()
        else [0.0] * game.num_players()
    )
    return GameRecord(
        matchup=matchup,
        game_index=game_index,
        seed=seed,
        game=short_name,
        game_digest=game_digest(short_name),
        seats={p: a.name for p, a in agents.items()},
        history=history,
        decisions=decisions,
        returns=returns,
        terminal=not truncated,
        truncated=truncated,
        num_decisions=len(decisions),
        wall_seconds=round(time.monotonic() - started, 3),
        usage=usage,
    )


def replay_views(
    game: Any, seed: int, history: list[int], *, expected_digest: str | None = None
) -> list[DecisionView]:
    """Reconstruct every `DecisionView` of a recorded game from `(seed,
    history)` alone.

    This is what makes a transcript auditable without storing megabytes of
    information-state strings per game: the engine is a pure function of those
    two, so the views — and therefore the prompts — are recoverable exactly.
    Used by the audit path and by tests; the metrics pass does not need it.

    `expected_digest`, when given, must equal `game_digest` of the LOADED
    game's short name or this raises `ProvenanceError` before touching
    `history`: a history is a sequence of action ids, meaningful only against
    the action space it was assigned under, and a different game source can
    renumber that space silently. Omitted, this replays the transcript's own
    recorded ids against whatever `game` decodes them as — which is what an
    archive with no `game_digest` field gets.
    """
    if expected_digest is not None:
        short_name = game.get_type().short_name
        actual_digest = game_digest(short_name)
        if actual_digest != expected_digest:
            raise ProvenanceError(
                f"the transcript for {short_name!r} was recorded against a "
                f"game source digesting to {expected_digest}, but the loaded "
                f"game's source now digests to {actual_digest} — its action "
                f"ids name moves the loaded game may not have, so replaying "
                f"them through it is not a valid audit."
            )
    state = game.new_initial_state()
    state.apply_action(seed % NUM_SEEDS)
    views: list[DecisionView] = []
    for action in history:
        player = state.current_player()
        legal = list(state.legal_actions())
        views.append(
            DecisionView(
                player=player,
                infostate=state.information_state_string(player),
                legal_actions=legal,
                legal_strings=[state.action_to_string(player, a) for a in legal],
            )
        )
        state.apply_action(action)
    return views
