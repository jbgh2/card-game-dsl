"""English re-rendering of the information state — the Q2 arm.

This is the experimental arm against the raw-string arm. Both are pure functions
of the engine's information-state string, so BOTH inherit the
indistinguishability guarantee: two states the acting player cannot distinguish
produce the same info-state string, hence the same rendering, hence the same
prompt. Rawness was never what made the argument sound (BUILDLOG,
"Leak-freeness"); it was purity.

What keeps a *rendering* from becoming an *interpretation* is three pins, in
`tests/test_render.py`:

- **round-trip** — `recover()` parses the English back out, and the test asserts
  it reproduces exactly what `infostate.parse` reads from the raw string. That
  is what proves no fact was added or lost.
- **no strategy** — a vocabulary scrape: the output may not contain evaluative
  language ("safe", "risky", "should"). Formatting help is in scope; advice is
  not, and would silently become part of the measured policy.
- **purity/determinism** — same bytes in, same bytes out.

Scope is deliberate: zones and state variables only. The observation log passes
through UNCHANGED. Every verified comprehension failure so far sits in the two
small sections (Haiku misreading its hand; Opus misreading `claim_rank`), while
the log — 80% of the tokens — has produced none. Rendering it would inflate the
prompt, and summarising it would lose information and break the round-trip.

Contract
--------
Assumes: an information state for `docs/games/cheat.cardlang` specifically. The
state vocabulary is Cheat's, and an unexpected zone or variable RAISES rather
than passing through unrendered — a silently-dropped field would be information
loss disguised as formatting. The three fields the prose states by ASSUMPTION
rather than by reading — `challenged`, `challenger`, and `responder` while the
window is closed — are held to the same bar by a refusal: no decision point
exhibits them set, so there is no faithful sentence for a state that does.
Establishes: English carrying exactly the facts `infostate.parse` reads.
Illegal after: adding a sentence to this module that is not recoverable by
`recover()`.
"""

from __future__ import annotations

import re

from . import infostate as istate

# Plural rank names, as the rules text says them ("call them as Aces").
RANK_PLURAL: dict[str, str] = {
    "A": "Aces", "2": "Twos", "3": "Threes", "4": "Fours", "5": "Fives",
    "6": "Sixes", "7": "Sevens", "8": "Eights", "9": "Nines", "10": "Tens",
    "J": "Jacks", "Q": "Queens", "K": "Kings",
}
PLURAL_TO_RANK: dict[str, str] = {v: k for k, v in RANK_PLURAL.items()}

COUNT_WORD: dict[int, str] = {1: "one", 2: "two", 3: "three", 4: "four"}

# The exact vocabulary this game's information state can contain. Declared, not
# discovered: an unknown key means the game changed under the renderer, and the
# right response is to fail rather than quietly omit a fact from the prompt.
EXPECTED_STATE_VARS = frozenset({
    "challenged", "challenger", "claim_count", "claim_rank", "claimant",
    "responder", "window_open", "won",
})
EXPECTED_SINGLE_ZONES = frozenset({"deck", "flipped", "pile", "played"})


def _cards(view: list[str] | int | None, label: str) -> list[str]:
    if not isinstance(view, list):
        raise ValueError(f"{label} did not render as identities: {view!r}")
    return view


def render_state(info_state: str) -> str:
    """The information state as English. Pure; raises on anything unexpected."""
    info = istate.parse(info_state)

    missing = EXPECTED_STATE_VARS - set(info.state)
    unknown = set(info.state) - EXPECTED_STATE_VARS
    if missing or unknown:
        raise ValueError(
            f"state vocabulary does not match Cheat's: missing={sorted(missing)} "
            f"unknown={sorted(unknown)} — the renderer would drop a fact"
        )
    seats = sorted(int(k[5:-1]) for k in info.zones if k.startswith("hand["))
    zone_names = {k for k in info.zones if not k.startswith("hand[")}
    if zone_names != EXPECTED_SINGLE_ZONES:
        raise ValueError(f"unexpected table zones: {sorted(zone_names)}")

    lines: list[str] = [f"You are seat {info.player}, of {len(seats)} players.", ""]

    hand = info.hand
    lines.append(f"Your hand holds {len(hand)} cards: {' '.join(hand)}")
    for seat in seats:
        if seat != info.player:
            lines.append(f"Seat {seat} holds {info.hand_size(seat)} cards, which you cannot see.")

    pile = info.zones["pile"]
    played = info.zones["played"]
    flipped = _cards(info.zones["flipped"], "flipped")
    lines.append("")
    lines.append(f"The pile holds {pile} cards, face down; nobody can see them.")
    lines.append(
        f"{played} cards are face down in front of the current claimant, awaiting "
        f"the challenge window."
    )
    lines.append(
        f"Face up for everyone: {' '.join(flipped)}" if flipped
        else "No cards are face up right now."
    )
    lines.append(f"The deck holds {info.zones['deck']} cards.")

    # --- the decision context ------------------------------------------------
    #
    # Three moments, and the raw string tells them apart by `claimant` and
    # `window_open` alone: no play stands (the announce), a play is being
    # assembled face down by its own claimant (the card picks), or a play
    # stands and the window is open (the challenge). Naming the moment is the
    # substance of this arm — the same facts, framed as the question being
    # asked rather than as a record to be decoded.
    rank = info.claim_rank
    if rank not in RANK_PLURAL:
        raise ValueError(f"claim_rank {rank!r} is not a rank this renderer knows")
    open_window = info.state["window_open"] == "True"
    claimant = info.claimant
    # Three fields the sentences below ASSUME idle rather than state, so
    # `recover` reports them from the shape of the prose. `challenged` and
    # `challenger` are idle at every decision — no one is asked anything
    # between a call and its adjudication, and `resolve_play` clears the
    # verdict before the next offer — and `responder` is a cursor only an open
    # window has. Assuming is safe exactly while it is checked: an assumption
    # violated here would be a fact dropped from the prompt, so it refuses.
    assumed_idle = [
        name
        for name, idle in (
            ("challenged", "False"),
            ("challenger", "None"),
            *((("responder", "None"),) if not open_window else ()),
        )
        if info.state[name] != idle
    ]
    if assumed_idle:
        raise ValueError(
            f"render_state: {sorted(assumed_idle)} carry window bookkeeping that "
            f"no decision point in Cheat exhibits — this renderer states them by "
            f"assumption, so it has no faithful sentence for such a state"
        )
    lines.append("")
    if open_window:
        lines.append(
            f"RIGHT NOW: seat {claimant} has played {info.claim_count} cards "
            f"face down, claiming they are {RANK_PLURAL[rank]}. You are deciding "
            f"whether to call \"Cheat!\" on that claim."
        )
        lines.append(f"Seat {info.state['responder']} is the window's rotation cursor.")
    elif claimant is None:
        lines.append(
            f"RIGHT NOW: it is your play. You must call your cards as "
            f"{RANK_PLURAL[rank]}."
        )
        lines.append("No play stands: nothing is waiting to be challenged.")
    else:
        lines.append(
            f"RIGHT NOW: seat {claimant} has announced {info.claim_count} cards "
            f"as {RANK_PLURAL[rank]} and is choosing which cards to put down."
        )
    lines.append(f"The challenge window is {'open' if open_window else 'closed'}.")

    won = re.findall(r"(\d+):(True|False)", info.state["won"])
    out = [s for s, w in won if w == "True"]
    lines.append(
        f"Seats that have gone out: {', '.join(out)}." if out
        else "No seat has gone out yet."
    )

    lines.append("")
    lines.append("Your complete event log, oldest first:")
    lines.append(info.obs)
    return "\n".join(lines)


def recover(rendered: str) -> dict[str, object]:
    """Parse the rendering back into facts — the round-trip half of the pin.

    Exists so `test_render.py` can assert the English carries exactly what
    `infostate.parse` reads from the raw string. If a future sentence states
    something this cannot recover, the round-trip test fails, which is the
    intended tripwire: an unrecoverable sentence is an unaudited claim in the
    prompt.
    """
    def need(pattern: str) -> re.Match[str]:
        m = re.search(pattern, rendered)
        if m is None:
            raise ValueError(f"rendering does not state: {pattern}")
        return m

    player = int(need(r"You are seat (\d+),").group(1))
    hand = need(r"Your hand holds \d+ cards: (.*)").group(1).split()
    sizes = {
        int(s): int(n) for s, n in re.findall(r"Seat (\d+) holds (\d+) cards", rendered)
    }
    sizes[player] = len(hand)  # the observer's own hand is stated by identity
    facts: dict[str, object] = {"player": player, "hand": hand, "hand_sizes": sizes}
    facts["pile"] = int(need(r"The pile holds (\d+) cards").group(1))
    facts["played"] = int(need(r"(\d+) cards are face down in front").group(1))
    m = re.search(r"Face up for everyone: (.*)", rendered)
    facts["flipped"] = m.group(1).split() if m else []
    facts["deck"] = int(need(r"The deck holds (\d+) cards").group(1))

    if "whether to call" in rendered:
        m = need(r"seat (\d+) has played (\d+) cards face down, claiming they are (\w+)")
        facts["claimant"], facts["claim_count"] = int(m.group(1)), int(m.group(2))
        facts["claim_rank"] = PLURAL_TO_RANK[m.group(3)]
        facts["responder"] = int(
            need(r"Seat (\d+) is the window's rotation cursor").group(1)
        )
    elif "No play stands" in rendered:
        facts["claim_rank"] = PLURAL_TO_RANK[
            need(r"You must call your cards as (\w+)\.").group(1)
        ]
        facts["claimant"], facts["claim_count"] = None, 0
        facts["responder"] = None
    else:
        m = need(r"seat (\d+) has announced (\d+) cards as (\w+) and is choosing")
        facts["claimant"], facts["claim_count"] = int(m.group(1)), int(m.group(2))
        facts["claim_rank"] = PLURAL_TO_RANK[m.group(3)]
        facts["responder"] = None
    facts["window_open"] = "The challenge window is open." in rendered
    m = re.search(r"Seats that have gone out: ([\d, ]+)\.", rendered)
    facts["won"] = sorted(int(x) for x in m.group(1).split(",")) if m else []
    facts["obs"] = rendered.split("Your complete event log, oldest first:\n", 1)[1]
    return facts
