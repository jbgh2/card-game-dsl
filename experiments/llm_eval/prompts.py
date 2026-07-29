"""Prompt construction and response parsing — the leak-freeness boundary.

`build_prompt` takes STRINGS, never a game state. That is the enforcement
mechanism, not a convention: there is no state object in scope to leak from, so
two states the acting player cannot distinguish necessarily produce
byte-identical prompts. Combined with the indistinguishability proofs in
`tests/openspiel_ready/test_cheat.py`, that is what lets a result measured here
be attributed to the information the player is entitled to.

Contract
--------
Assumes: `info_state` is the engine's raw information-state string for the
acting player, and `legal_actions` its `action_to_string` renderings, in the
engine's own order.
Establishes: a deterministic prompt that is a pure function of its arguments.
Illegal after: any prompt-side access to `pyspiel.State`, `RuntimeState`, the
seed, or another player's view.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass

# --- static rules text ----------------------------------------------------
#
# Hand-trimmed from `docs/games/cheat.md`, whose own acceptance test is that a
# non-player can read it cold and play a hand. Public information, held as a
# module constant rather than generated: a dynamically-built rules string would
# be one more thing that could vary with hidden state.

RULES_TEXT = """\
You are playing CHEAT (also called I Doubt It, Bullshit, or Bluff) — a
four-player shedding game on a standard 52-card deck. You are one of the four
players. Seats are numbered 0-3 and play passes clockwise 0 -> 1 -> 2 -> 3 -> 0.

THE DEAL. The whole deck is dealt out: 13 cards to each of the four hands.
There is no stock; every card starts in someone's hand.

THE CLAIM CYCLE. Plays are called as ranks in a fixed ascending cycle that
belongs to the table, not to any player. The first play is called "Aces", the
second "Twos", the third "Threes", ... then Jacks, Queens, Kings, and back to
Aces. The cycle advances by exactly one step per play and never resets — a
challenge does not restart it. You do not choose the rank you claim; the cycle
does.

A TURN. On your turn you discard one to four cards FACE DOWN onto the pile and
call them as the cycle's current rank ("two Sevens"). The count you announce is
the count you actually played — miscounting is not part of this game. The RANKS
are your own business: you do not need to hold the called rank at all. With the
wrong hand at the wrong point in the cycle, lying is not merely allowed, it is
forced.

THE CHALLENGE WINDOW. After each play, every other player — clockwise from the
player's left — may call "Cheat!" or let it go. The first call closes the
window.
  - A CALL. The cards just played (only this play, not the pile beneath) are
    turned face up for the whole table. If EVERY one is the called rank, the
    claim was honest and the embarrassed challenger picks up those cards AND
    the entire pile into their hand. If ANY card is not the called rank, the
    liar is caught and picks it all up instead.
  - NO CALL. The cards join the pile face down, unseen, and stay unseen. A lie
    that draws no call is never found out.

AFTER A PLAY. Challenged or not, the cycle advances one rank and the turn
passes to the next player clockwise.

WINNING. The first player to empty their hand AND survive the challenge window
on that final play wins immediately. A caught lie on the final play refills the
liar's hand from the pile.
"""

# How to read the raw information-state string. The state string itself is
# passed through verbatim (never paraphrased or re-rendered) because it is the
# artifact the indistinguishability proofs cover; the cost of that fidelity is
# that its format has to be explained here instead.
FORMAT_TEXT = """\
HOW TO READ YOUR KNOWLEDGE STATE

You will be shown the engine's raw knowledge state for your seat. It is
machine-generated and terse. Its layout is:

    P<seat>|<zone>=<view>;...|state:<var>=<value>;...|obs:<event>;...

  - P<seat> is you.
  - Each zone renders as one of three views. `[10♣,2♠,A♥]` means you can see
    those exact cards. `#13` means you can see only that the zone holds 13
    cards, not which. `?` means you can see nothing at all.
      * `hand[n]` is seat n's hand. Your own shows identities; everyone else's
        shows a count.
      * `played` holds the face-down cards of the play currently standing in
        the challenge window — a count to everyone, including whoever played
        them.
      * `pile` is the accumulated face-down discards nobody challenged.
      * `flipped` briefly holds cards a challenge has exposed; it is visible to
        everyone and is empty except at that moment.
      * `deck` is empty after the deal.
  - The `state:` section is public information every player can see:
      * `claim_rank` — the rank in play RIGHT NOW. It is already correct for
        whatever you are being asked to do: when you are choosing what to
        play, it is the rank YOUR OWN play must be called as, so do not
        advance it yourself; when you are deciding whether to challenge, it is
        the rank the standing play was called as. The cycle steps forward only
        after a play has been fully resolved.
      * `claim_count` — how many cards the standing play claims to be.
      * `claimant` — the seat whose play stands in the window.
      * `challenged`, `challenger`, `responder`, `window_open` — the state of
        the current challenge window.
      * `won` — which seats have gone out.
  - The `obs:` section is your complete personal event log, oldest first. It is
    the record of everything you have observed, including the cards you chose
    to play (which nobody else saw) and every challenge flip (which everyone
    saw). Events look like:
      * ('move', <from>, <n>, <to>, <what>) — n cards moved. `<what>` is a
        tuple of card names if you were entitled to see them, or a bare number
        if you only saw the count.
      * ('announce', <seat>, <move>) — a public announcement.
      * ('chose', <card>) — a card YOU selected.

This log is the reason you know what you played even though `played` and `pile`
show you only counts: your own choices are in your log, and nobody else's are
in theirs.
"""

RESPONSE_TEXT = """\
HOW TO ANSWER

Reply with a single JSON object and nothing else:

    {"action": <index>, "reasoning": "<one or two sentences>"}

`action` is the integer index of your chosen action from the numbered list
above. Do not include internal or system XML tags in your response. Do not wrap
the JSON in prose.
"""


def build_prompt(rules: str, infostate: str, legal_actions: list[str]) -> str:
    """The complete prompt for one decision.

    Pure by signature: three strings in, one string out. There is no state
    object here to read, so nothing outside the acting player's entitled view
    can reach the model — which is the whole point of the harness.
    """
    numbered = "\n".join(f"  {i}: {a}" for i, a in enumerate(legal_actions))
    return (
        f"{rules}\n"
        f"Your current knowledge:\n\n{infostate}\n\n"
        f"Your legal actions right now:\n\n{numbered}\n\n"
        f"{RESPONSE_TEXT}"
    )


# --- response parsing -----------------------------------------------------

_JSON_OBJECT = re.compile(r"\{.*\}", re.DOTALL)


@dataclass(frozen=True)
class ParseResult:
    """Either a valid action index, or the reason it could not be read."""

    index: int | None
    reasoning: str
    error: str | None

    @property
    def ok(self) -> bool:
        return self.index is not None


def parse_response(text: str, num_actions: int) -> ParseResult:
    """Extract `{"action": i, "reasoning": s}` from a model reply.

    Tolerant about surroundings (code fences, a stray sentence, a leaked
    `<thinking>` block) and strict about the payload: the index must be an
    integer in `0..num_actions-1`. Anything else returns a named error rather
    than a guess — the harness reports its fallback rate, and a silently
    coerced index would understate it.
    """
    match = _JSON_OBJECT.search(text)
    if match is None:
        return ParseResult(None, "", "no JSON object in response")
    try:
        payload = json.loads(match.group(0))
    except json.JSONDecodeError as exc:
        return ParseResult(None, "", f"malformed JSON: {exc.msg}")
    if not isinstance(payload, dict):
        return ParseResult(None, "", "JSON payload is not an object")

    reasoning = payload.get("reasoning", "")
    reasoning = reasoning if isinstance(reasoning, str) else repr(reasoning)

    raw = payload.get("action")
    if isinstance(raw, bool) or not isinstance(raw, int):
        # `bool` is an `int` subclass; `True` is not an action index.
        if isinstance(raw, str) and raw.strip().lstrip("-").isdigit():
            raw = int(raw.strip())
        else:
            return ParseResult(None, reasoning, f"action is not an integer: {raw!r}")
    if not 0 <= raw < num_actions:
        return ParseResult(
            None, reasoning, f"action {raw} out of range 0..{num_actions - 1}"
        )
    return ParseResult(raw, reasoning, None)


RETRY_NOTE = """\

Your previous reply could not be used: {error}

Reply with ONLY a JSON object of the form {{"action": <index>, "reasoning": "<brief>"}},
where <index> is one of the integers listed above.
"""


# The format guide for the RAW arm: the state arrives machine-formatted, so its
# layout has to be explained. `RULES_RAW` is what `LLMAgent.rules` defaults to,
# which keeps every measurement taken before the rendered arm existed valid.
RULES_RAW = RULES_TEXT + "\n" + FORMAT_TEXT

# The format guide for the RENDERED arm. Most of FORMAT_TEXT existed only to
# explain the machine format; once the zones and state variables arrive as
# English, only the event log still needs describing. That is why this arm's
# prompt is SHORTER despite the state section itself being more verbose.
FORMAT_TEXT_RENDERED = """\
HOW TO READ YOUR SITUATION

You will be shown your own view of the table in plain English, followed by your
complete personal event log. The log is machine-generated and terse; it is the
record of everything you have observed, including the cards you chose to play
(which nobody else saw) and every challenge flip (which everyone saw). Its
entries look like:

  * ('move', <from>, <n>, <to>, <what>) — n cards moved between zones. `<what>`
    is a tuple of card names if you were entitled to see them, or a bare number
    if you only saw the count.
  * ('announce', <seat>, <move>) — a public announcement.
  * ('chose', <card>) — a card YOU selected.

The log is the reason you know what you played even though the pile and the
face-down cards show you only counts: your own choices are in your log, and
nobody else's are in theirs.
"""

RULES_RENDERED = RULES_TEXT + "\n" + FORMAT_TEXT_RENDERED
