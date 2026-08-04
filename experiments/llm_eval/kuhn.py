"""Kuhn poker — the game-specific half of the harness, and the solver.

Kuhn is the reason this game is worth evaluating on at all: it is *solved*. The
whole tree is six deals and five lines, so a best response can be computed
exactly, and "how well did the model play" stops being a behavioural proxy and
becomes a number in chips per hand.

That gives two measurement families the Cheat harness could not have:

1. **Dominated actions.** Folding a King to a bet, or calling a bet with a Jack,
   loses chips against *every* opponent strategy — no belief, no read, no
   equilibrium reasoning required. Nash assigns both probability zero. A non-zero
   rate is a straight error, and it is the Kuhn analogue of Cheat's
   "provable lie" (logical certainty) as against its "improbable lie"
   (a judgement call).
2. **Exploitability.** Fix the measured policy at its seat, let the opponent
   best-respond, and report how many chips per hand that costs relative to what
   equilibrium play would have guaranteed. Zero for a Nash policy, by
   construction — and asserted, not assumed (`tests/test_kuhn.py`).

Contract
--------
Assumes: information-state strings produced by `cardlang_kuhn_poker` through the
OpenSpiel adapter.
Establishes: a parsed `Info` (own card + public announcement history), and
exact game-theoretic quantities over Kuhn's six-deal tree.
Illegal after: deriving a Kuhn quantity by sampling when the tree admits an
exact answer — it has 30 leaves.

This module imports nothing else from the package and nothing from the engine:
it is on the decision path (`agents.py` imports it), so `tests/
test_prompt_purity.py`'s import scrape covers it, and it must stay clean.
"""

from __future__ import annotations

import ast
import itertools
import re
from collections.abc import Iterable, Iterator, Mapping, Sequence
from dataclasses import asdict, dataclass, field
from typing import Any

# --- the game ---------------------------------------------------------------

CARDS: tuple[str, ...] = ("J", "Q", "K")
RANK: dict[str, int] = {c: i for i, c in enumerate(CARDS)}

#: Every deal, each equally likely. Kuhn deals one of three cards to each of two
#: players, so there are 3 x 2 = 6 — small enough that everything below is an
#: enumeration rather than an estimate.
DEALS: tuple[tuple[str, str], ...] = tuple(
    (a, b) for a in CARDS for b in CARDS if a != b
)

#: Which seat acts after a given announcement history, or `None` at a terminal.
#: This IS Kuhn's tree; the five terminal histories are exactly the five lines
#: the adapter walks (verified against the engine in `tests/test_kuhn.py`).
_TO_ACT: dict[tuple[str, ...], int | None] = {
    (): 0,
    ("check",): 1,
    ("bet",): 1,
    ("check", "bet"): 0,
    ("check", "check"): None,
    ("check", "bet", "call"): None,
    ("check", "bet", "fold"): None,
    ("bet", "call"): None,
    ("bet", "fold"): None,
}

#: The actions offered at each decision history. Two shapes: an opening
#: check-or-bet, and a fold-or-call facing a bet.
_OFFERED: dict[tuple[str, ...], tuple[str, str]] = {
    (): ("check", "bet"),
    ("check",): ("check", "bet"),
    ("bet",): ("fold", "call"),
    ("check", "bet"): ("fold", "call"),
}

#: The equilibrium value of the game to seat 0, in chips per hand. Kuhn's
#: first player is at a structural disadvantage: -1/18. Asserted against the
#: solver rather than trusted (`tests/test_kuhn.py`).
NASH_VALUE: tuple[float, float] = (-1.0 / 18.0, 1.0 / 18.0)


def payoff(deal: tuple[str, str], history: tuple[str, ...]) -> float:
    """Chips to seat 0 at a terminal history. Antes are 1 each, the bet is 1.

    Byte-checked against the engine's own `returns()` on all five lines of all
    six deals in `tests/test_kuhn.py`, so this table cannot drift from the DSL
    description without a test going red.
    """
    if _TO_ACT[history] is not None:
        raise ValueError(f"{history!r} is not terminal")
    high = 1.0 if RANK[deal[0]] > RANK[deal[1]] else -1.0
    if history == ("check", "check"):
        return high
    if history == ("bet", "fold"):
        return 1.0
    if history == ("check", "bet", "fold"):
        return -1.0
    return 2.0 * high  # both lines that reach a called bet


# --- policies ---------------------------------------------------------------
#
# A policy is a flat map from an information set to a distribution over the
# actions offered there. The key carries the seat, so one map can describe a
# whole table, and a seat's half can be lifted out of a transcript.

Policy = dict[str, dict[str, float]]


def infoset(seat: int, card: str, history: tuple[str, ...]) -> str:
    """The information-set key: everything the acting seat knows.

    Its own card and the public announcement history — which is exactly what the
    engine's information-state string carries, and the reason a policy read off
    the transcript is a policy over the same partition the proofs cover.
    """
    return f"P{seat}|{card}|{'-'.join(history) or 'open'}"


def infoset_keys(seat: int) -> list[str]:
    """A seat's six information sets, in a stable order."""
    return [
        infoset(seat, card, history)
        for history, actor in sorted(_TO_ACT.items())
        if actor == seat
        for card in CARDS
    ]


def offered(key: str) -> tuple[str, str]:
    """The two actions offered at an information set, from its key alone."""
    _, _, tail = key.split("|")
    history = () if tail == "open" else tuple(tail.split("-"))
    return _OFFERED[history]


def nash_policy(alpha: float = 1.0 / 6.0) -> Policy:
    """Kuhn's equilibrium family, parameterised by `alpha` in [0, 1/3].

    Seat 0's whole family is a one-parameter line: bluff a Jack at `alpha`, bet a
    King at `3*alpha`, never bet a Queen, and call a bet with a Queen at
    `alpha + 1/3`. Seat 1's equilibrium is unique.

    The constants are stated here and **checked**, not trusted: `tests/
    test_kuhn.py` computes the exploitability of this policy with the
    best-response code below and asserts it is zero across the family. A
    misremembered frequency would move every comparison in this file silently,
    so it is pinned by the one piece of machinery that does not share its
    assumptions.
    """
    if not 0.0 <= alpha <= 1.0 / 3.0:
        raise ValueError(f"alpha must lie in [0, 1/3]; got {alpha}")
    bet = {"J": alpha, "Q": 0.0, "K": 3.0 * alpha}
    call0 = {"J": 0.0, "Q": alpha + 1.0 / 3.0, "K": 1.0}
    bet1 = {"J": 1.0 / 3.0, "Q": 0.0, "K": 1.0}
    call1 = {"J": 0.0, "Q": 1.0 / 3.0, "K": 1.0}
    policy: Policy = {}
    for card in CARDS:
        policy[infoset(0, card, ())] = {"bet": bet[card], "check": 1.0 - bet[card]}
        policy[infoset(0, card, ("check", "bet"))] = {
            "call": call0[card],
            "fold": 1.0 - call0[card],
        }
        policy[infoset(1, card, ("check",))] = {
            "bet": bet1[card],
            "check": 1.0 - bet1[card],
        }
        policy[infoset(1, card, ("bet",))] = {
            "call": call1[card],
            "fold": 1.0 - call1[card],
        }
    return policy


def uniform_policy(seat: int) -> Policy:
    """A seat's maximally uncommitted policy — the fill for information sets a
    measured run never reached. Named rather than inlined because which fill is
    used materially moves an exploitability number, so it has to be a stated
    choice (see `aggregate`, which reports both this and the Nash fill)."""
    return {key: {a: 0.5 for a in offered(key)} for key in infoset_keys(seat)}


def _expected(deal: tuple[str, str], policy: Policy, history: tuple[str, ...]) -> float:
    """Chips to seat 0 from one deal, under a complete two-seat policy."""
    seat = _TO_ACT[history]
    if seat is None:
        return payoff(deal, history)
    dist = policy[infoset(seat, deal[seat], history)]
    return sum(
        p * _expected(deal, policy, history + (action,))
        for action, p in dist.items()
        if p > 0.0
    )


def game_value(policy: Policy) -> float:
    """Chips per hand to seat 0, averaged over all six deals."""
    return sum(_expected(deal, policy, ()) for deal in DEALS) / len(DEALS)


def _pure(keys: Sequence[str], choices: Sequence[str]) -> Policy:
    return {
        key: {a: 1.0 if a == choice else 0.0 for a in offered(key)}
        for key, choice in zip(keys, choices, strict=True)
    }


def best_response(policy: Policy, seat: int) -> tuple[float, Policy]:
    """The best response to `policy` at `seat`, and its value TO `seat`.

    Brute force over the responder's 2^6 pure strategies rather than a
    counterfactual-value recursion. A pure best response always exists, sixty-four
    evaluations of a thirty-leaf tree is nothing, and the belief arithmetic a
    recursive best response needs is precisely where such code goes subtly wrong.
    The point of this function is to be obviously right.
    """
    responder = 1 - seat
    keys = infoset_keys(responder)
    sign = 1.0 if responder == 0 else -1.0
    fixed = {k: v for k, v in policy.items() if k.startswith(f"P{seat}|")}
    missing = [k for k in infoset_keys(seat) if k not in fixed]
    if missing:
        raise ValueError(
            f"policy for seat {seat} is incomplete: {missing} — a best response "
            f"needs a complete policy, so the fill has to be a stated choice"
        )
    best_value = float("-inf")
    best_policy: Policy = {}
    for choices in itertools.product(*(offered(k) for k in keys)):
        candidate = {**fixed, **_pure(keys, choices)}
        value = sign * game_value(candidate)
        if value > best_value:
            best_value, best_policy = value, candidate
    return best_value, best_policy


def noise_floor(
    visits: Mapping[str, Mapping[str, int]],
    seat: int,
    trials: int = 200,
    seed: int = 20260803,
) -> tuple[float, float]:
    """The exploitability a player who is EXACTLY at equilibrium would measure,
    given these visit counts. Returns `(mean, 95th percentile)`.

    This is the null, and without it an exploitability number is not evidence.
    Exploitability is a non-negative functional of an estimated policy, so
    sampling noise can only push it UP: a perfect player measured over finitely
    many hands scores strictly worse than zero-exploitable, and the smaller the
    sample the worse it looks. At the visit counts a few hundred Kuhn hands
    produce, that floor is a substantial fraction of the numbers being reported.

    Resampling uses the OBSERVED per-information-set visit counts rather than an
    even split, because the counts are wildly uneven — an information set the
    opponent's policy rarely puts you in carries most of the noise, and an
    even-split null would understate the floor exactly where it matters.
    """
    import random as _random

    rng = _random.Random(seed)
    nash = nash_policy()
    keys = infoset_keys(seat)
    counts = {k: sum(visits.get(k, {}).values()) for k in keys}
    values: list[float] = []
    for _ in range(trials):
        drawn: Policy = {}
        for key in keys:
            actions = offered(key)
            n = counts[key]
            if not n:
                # Never visited: the fill is the caller's stated choice, and a
                # resample cannot invent one. Uniform matches `policy`'s default.
                drawn[key] = {a: 0.5 for a in actions}
                continue
            tally = {a: 0 for a in actions}
            probability = nash[key]
            for _ in range(n):
                roll = rng.random()
                cumulative = 0.0
                for action in actions:
                    cumulative += probability[action]
                    if roll < cumulative:
                        tally[action] += 1
                        break
                else:
                    tally[actions[-1]] += 1
            drawn[key] = {a: tally[a] / n for a in actions}
        values.append(exploitability(drawn, seat))
    values.sort()
    return sum(values) / len(values), values[int(0.95 * (len(values) - 1))]


def exploitability(policy: Policy, seat: int) -> float:
    """Chips per hand a best-responding opponent takes from `seat` over and above
    what equilibrium play would have conceded.

    Zero for any Nash policy and strictly positive otherwise, in the units the
    game is actually scored in. This is the headline: it converts "does the model
    play well" into a quantity with a floor everyone can check.
    """
    value_to_responder, _ = best_response(policy, seat)
    # `value_to_responder` is chips to the OPPONENT; the seat gets its negation.
    return NASH_VALUE[seat] - (-value_to_responder)


# --- reading the engine's information state ---------------------------------

_HAND = re.compile(r"hand\[(\d)\]=\[([JQK])")
_SEAT = re.compile(r"^P(\d)\|")


@dataclass(frozen=True)
class Info:
    """What the acting seat knows: its own card, and what has been announced."""

    player: int
    card: str
    history: tuple[str, ...]

    @property
    def key(self) -> str:
        return infoset(self.player, self.card, self.history)

    @property
    def facing_bet(self) -> bool:
        return self.history[-1:] == ("bet",)


def parse(infostate: str) -> Info:
    """Parse one information-state string into `Info`.

    Reads only what the seat is entitled to: its own `hand[n]`, which the
    adapter renders as card identities exactly when the seat owns it, and the
    public `('announce', seat, move)` events. The opponent's hand renders as
    `#1` and does not match `_HAND`, so a leak here would be a parse failure
    rather than a silently richer view — asserted in `tests/test_kuhn.py`.
    """
    seat_match = _SEAT.match(infostate)
    if seat_match is None:
        raise ValueError(f"no seat marker in information state: {infostate[:60]!r}")
    player = int(seat_match.group(1))

    zones, _, tail = infostate.partition("|state:")
    own = [card for n, card in _HAND.findall(zones) if int(n) == player]
    if len(own) != 1:
        raise ValueError(
            f"seat {player} sees {len(own)} identified card(s) in the zone "
            f"section; Kuhn deals exactly one and hides the other"
        )

    _, _, log = tail.partition("|obs:")
    history: list[str] = []
    for event in _events(log):
        if event and event[0] == "announce":
            history.append(str(event[2]))
    return Info(player=player, card=own[0], history=tuple(history))


def _events(log: str) -> Iterator[tuple[Any, ...]]:
    """The observation log's events. `ast.literal_eval` rather than a regex: the
    entries are Python tuple literals and a card name can contain a comma-free
    but bracket-bearing suit glyph."""
    for chunk in log.split(");"):
        chunk = chunk.strip()
        if not chunk:
            continue
        if not chunk.endswith(")"):
            chunk += ")"
        try:
            value = ast.literal_eval(chunk)
        except (ValueError, SyntaxError):
            continue
        if isinstance(value, tuple):
            yield value


# --- the prompt's static text -----------------------------------------------
#
# Trimmed from `docs/games/kuhn-poker.md`, whose own acceptance test is that a
# non-player can read it cold and play a hand. Public information, held as a
# module constant rather than generated: a dynamically-built rules string would
# be one more thing that could vary with hidden state.

RULES_TEXT = """\
You are playing KUHN POKER — a two-player poker game on a three-card deck. You
are one of the two players. Seats are numbered 0 and 1.

THE DECK. Three cards: Jack, Queen, King. King beats Queen beats Jack. There are
no suits that matter and no ties.

THE DEAL. Each player antes 1 chip into the pot, then is dealt one card face
down. The third card is not used and nobody sees it. You see your own card only.

THE BETTING. There is exactly one betting round, and the bet size is 1 chip.
Seat 0 acts first.

  - Seat 0 may CHECK or BET 1.
  - If seat 0 checks, seat 1 may CHECK (both check: showdown) or BET 1.
      - If seat 1 bets, seat 0 may FOLD or CALL.
  - If seat 0 bets, seat 1 may FOLD or CALL.

There are no raises. The hand ends the moment somebody folds, somebody calls, or
both players check.

THE SHOWDOWN. If nobody folded, both cards are turned face up and the higher card
takes the whole pot. A fold gives the pot to the other player without any card
being shown — a folded card is never revealed.

WHAT A HAND IS WORTH. Counting from your starting stack:
  - Both check, you have the higher card: you win 1.  Lower card: you lose 1.
  - A bet is called and you have the higher card: you win 2.  Lower: you lose 2.
  - You fold: you lose 1 (your ante).
  - Your opponent folds: you win 1.

THE POINT. A Jack never wins a showdown and a King never loses one, so betting a
Jack can only ever win by making the other player fold, and folding a King throws
away a hand that was going to win. A Queen is the interesting card: it wins some
showdowns and loses others, so what to do with it depends on what you think the
other player is doing.
"""

FORMAT_TEXT = """\
HOW TO READ YOUR KNOWLEDGE STATE

You will be shown the engine's raw knowledge state for your seat. It is
machine-generated and terse. Its layout is:

    P<seat>|<zone>=<view>;...|state:<var>=<value>;...|obs:<event>;...

  - P<seat> is you.
  - Each zone renders as one of three views. `[K♠]` means you can see that exact
    card. `#1` means you can see only that the zone holds one card, not which.
    `?` means you can see nothing at all.
      * `hand[n]` is seat n's hand. Your own shows its card; the other seat's
        shows a bare count, because you are not entitled to see it.
      * `deck` is the one undealt card, which nobody sees.
      * `muck` holds a folded card. It is never shown to anybody, including the
        player who folded it.
      * `shown[n]` is seat n's card at a showdown, and is empty until then.
  - The `state:` section is public information both players can see:
      * `committed` — chips each seat has put in, antes included.
      * `bet_to_match`, `bet_by` — the current bet and who has matched it.
      * `folded` — which seats have folded.
      * `stack`, `net` — chips remaining, and the running result.
      * `first_actor`, `acted`, `raises`, `raise_cap`, `limit` — betting
        bookkeeping; `raise_cap` is 1 because Kuhn allows no raises.
  - The `obs:` section is your complete personal event log, oldest first. Events
    look like:
      * ('move', <from>, <n>, <to>, <what>) — n cards moved. `<what>` is a tuple
        of card names if you were entitled to see them, or a bare number if you
        only saw the count. The deal shows you your own card and a count for
        the other seat.
      * ('announce', <seat>, <move>) — a public announcement: this is the
        betting history, and it is how you know what has been done to you.
"""

FORMAT_TEXT_RENDERED = """\
HOW TO READ YOUR SITUATION

You will be shown your own view of the hand in plain English: the card you hold,
what each player has put in, and the betting so far in the order it happened.
Everything not stated is something you are not entitled to know — in particular
the other player's card, which you never see before a showdown.
"""

RULES_RAW = RULES_TEXT + "\n" + FORMAT_TEXT
RULES_RENDERED = RULES_TEXT + "\n" + FORMAT_TEXT_RENDERED


def render_state(infostate: str) -> str:
    """The information state as English.

    A pure function of the same string the raw arm passes through verbatim, so
    the leak-freeness argument is unchanged: it can only ever say less than its
    input, never more. `tests/test_kuhn.py` pins the direction — every fact it
    prints is derived from `parse`, which reads only entitled fields.
    """
    info = parse(infostate)
    lines = [
        f"You are seat {info.player}.",
        f"Your card: {info.card}.",
        "You have not seen the other player's card.",
    ]
    if not info.history:
        lines.append("Nothing has been announced yet; you are first to act.")
    else:
        # Kuhn's announcements strictly alternate from seat 0, so who said what
        # follows from the history's position alone.
        seq = []
        seat = 0
        for action in info.history:
            seq.append(f"seat {seat} checked" if action == "check" else f"seat {seat} bet 1")
            seat = 1 - seat
        lines.append("Betting so far: " + "; ".join(seq) + ".")
    pot = 2 + (1 if "bet" in info.history else 0)
    lines.append(f"There are {pot} chips in the pot.")
    if info.facing_bet:
        lines.append("You are facing a bet of 1: you must fold or call.")
    else:
        lines.append("No bet stands against you: you may check or bet 1.")
    return "\n".join(lines)


# --- per-decision facts -----------------------------------------------------


def classify(card: str, history: tuple[str, ...], action: str) -> dict[str, bool]:
    """The metric classification of one decision, from primitives alone.

    Factored out and called from BOTH `decision_facts` (at run time, so the
    transcript is readable) and `KuhnStats.observe` (at aggregation time, from
    `card`/`history`/`action`), so a transcript written before a definition
    changed still aggregates under the current one. The flags in an old
    transcript are then a record of what was thought at the time and never an
    input to a published rate.

    A BLUFF is betting the card that cannot win a showdown, and only where
    betting is what is on offer. Calling a bet with a Jack is NOT a bluff — it
    is a dominated action, and `dominated` already owns it. Pooling the two
    made the rate opponent-dependent: the identical `NashAgent` scored 0.187
    against itself and 0.144 against a random opponent, purely because the
    two matchups put it in front of a bet at different rates.

    The denominator still mixes the opening bluff (equilibrium frequency
    `alpha`) with the bluff after a check (equilibrium frequency 1/3), which is
    why `rates` also reports each separately, straight off the per-information-
    set visit counts where neither the opponent nor the seat share can move it.
    """
    facing_bet = history[-1:] == ("bet",)
    return {
        "dominated_offered": facing_bet and card in ("J", "K"),
        "dominated": facing_bet
        and ((card == "K" and action == "fold") or (card == "J" and action == "call")),
        "bluff_offered": card == "J" and not facing_bet,
        "bluff": card == "J" and not facing_bet and action == "bet",
    }


def decision_facts(player: int, infostate: str, action: str) -> dict[str, Any]:
    """The metric-relevant facts of one decision, from the acting seat's own
    information state plus the action it chose.

    `dominated` is the load-bearing one. Folding a King to a bet returns -1 where
    calling returns +2, and calling a bet with a Jack returns -2 where folding
    returns -1 — against *every* opponent strategy, since a King wins every
    showdown and a Jack loses every showdown. No equilibrium reasoning is needed
    to call those errors, which is what makes the rate quotable on its own.
    """
    info = parse(infostate)
    return {
        "kind": "response" if info.facing_bet else "open",
        "seat": player,
        "card": info.card,
        "history": "-".join(info.history) or "open",
        "infoset": info.key,
        "action": action,
        **classify(info.card, info.history, action),
    }


# --- aggregation ------------------------------------------------------------


def _rate(numerator: int, denominator: int) -> float | None:
    """A rate, or `None` when there were no opportunities — never 0.0 for an
    empty denominator, which reads as "never did it" when the truth is "was
    never asked"."""
    return numerator / denominator if denominator else None


@dataclass
class KuhnStats:
    """Everything measured for one agent, counts first."""

    agent: str = ""
    games: int = 0
    games_scored: int = 0
    wins: int = 0
    chips: float = 0.0
    decisions: int = 0
    fallbacks: int = 0
    llm_calls: int = 0
    input_tokens: int = 0
    output_tokens: int = 0

    dominated_offered: int = 0
    dominated_taken: int = 0
    bluff_offered: int = 0
    bluffs: int = 0

    #: Action counts per information set, the raw material for the policy.
    visits: dict[str, dict[str, int]] = field(default_factory=dict)

    def observe(self, facts: Mapping[str, Any]) -> None:
        # Re-derived from `card`/`history`/`action` rather than read off the
        # recorded flags, so a transcript written under an older definition
        # aggregates under the current one. The flags stay in the transcript as
        # a readable record; they are never an input to a published rate.
        history_text = str(facts["history"])
        history = () if history_text == "open" else tuple(history_text.split("-"))
        flags = classify(str(facts["card"]), history, str(facts["action"]))
        if flags["dominated_offered"]:
            self.dominated_offered += 1
            if flags["dominated"]:
                self.dominated_taken += 1
        if flags["bluff_offered"]:
            self.bluff_offered += 1
            if flags["bluff"]:
                self.bluffs += 1
        key = str(facts["infoset"])
        action = str(facts["action"])
        self.visits.setdefault(key, {})[action] = (
            self.visits.setdefault(key, {}).get(action, 0) + 1
        )

    def policy(self, seat: int, fill: Policy) -> Policy:
        """The empirical policy at `seat`, with unvisited information sets taken
        from `fill`.

        The fill is a parameter and not a default because it materially moves the
        exploitability number: a uniform fill charges the seat for information
        sets it was never asked about, and a Nash fill forgives them. `rates`
        reports both, and `infoset_coverage` reports how much of the number is
        measurement rather than fill.
        """
        out: Policy = {}
        for key in infoset_keys(seat):
            counts = self.visits.get(key)
            if not counts:
                out[key] = dict(fill[key])
                continue
            total = sum(counts.values())
            out[key] = {a: counts.get(a, 0) / total for a in offered(key)}
        return out

    def _seats_played(self) -> list[int]:
        return sorted({int(k[1]) for k in self.visits})

    def exploitability(self, fill_with_nash: bool) -> float | None:
        """Chips per hand a best responder takes above the equilibrium floor,
        averaged over the seats this agent actually occupied.

        `None` when the agent never acted — a zero would read as "played
        perfectly" when the truth is "never played".
        """
        seats = self._seats_played()
        if not seats:
            return None
        nash = nash_policy()
        values = []
        for seat in seats:
            fill = (
                {k: dict(v) for k, v in nash.items() if k.startswith(f"P{seat}|")}
                if fill_with_nash
                else uniform_policy(seat)
            )
            values.append(exploitability(self.policy(seat, fill), seat))
        return sum(values) / len(values)

    def noise_floor(self) -> tuple[float, float] | None:
        """The exploitability an exactly-equilibrium player would have measured
        at THIS agent's visit counts: `(mean, p95)`. Averaged over the seats it
        occupied, like `exploitability`, so the two are directly comparable."""
        seats = self._seats_played()
        if not seats:
            return None
        pairs = [noise_floor(self.visits, seat) for seat in seats]
        return (
            sum(m for m, _ in pairs) / len(pairs),
            sum(p for _, p in pairs) / len(pairs),
        )

    def infoset_coverage(self) -> float | None:
        """The fraction of the information sets this agent could have been asked
        about that it actually visited. An exploitability number over low
        coverage is mostly a statement about the fill."""
        seats = self._seats_played()
        if not seats:
            return None
        possible = [k for seat in seats for k in infoset_keys(seat)]
        return sum(1 for k in possible if self.visits.get(k)) / len(possible)

    def rates(self) -> dict[str, float | None]:
        floor = self.noise_floor()
        measured = self.exploitability(fill_with_nash=False)
        return {
            "input_tokens_per_game": _rate(self.input_tokens, self.games),
            "output_tokens_per_game": _rate(self.output_tokens, self.games),
            "llm_calls_per_game": _rate(self.llm_calls, self.games),
            "win_rate": _rate(self.wins, self.games_scored),
            "chips_per_hand": (
                self.chips / self.games_scored if self.games_scored else None
            ),
            "fallback_rate": _rate(self.fallbacks, self.decisions),
            # The headline. Zero is equilibrium; bigger is worse — but read it
            # against `exploitability_noise_floor`, which is what a PERFECT
            # player would have scored at this sample size. The difference is
            # the claim; the raw number on its own is not.
            "exploitability": self.exploitability(fill_with_nash=False),
            "exploitability_nash_fill": self.exploitability(fill_with_nash=True),
            "exploitability_noise_floor": floor[0] if floor else None,
            "exploitability_noise_floor_p95": floor[1] if floor else None,
            "exploitability_above_floor": (
                None
                if floor is None or measured is None
                else measured - floor[0]
            ),
            "infoset_coverage": self.infoset_coverage(),
            # The error rate that needs no equilibrium to interpret.
            "dominated_action_rate": _rate(self.dominated_taken, self.dominated_offered),
            # Betting the card that cannot win a showdown. Pooled across the two
            # places a bluff is possible, so its denominator mix still moves with
            # how often the agent sat in each seat — the two rates below are the
            # per-information-set forms, which nothing outside the agent's own
            # policy can move, and are what a comparison should quote.
            "bluff_rate": _rate(self.bluffs, self.bluff_offered),
            # Equilibrium target: alpha (1/6 at the configured opponent).
            "bluff_rate_first_to_act": self._frequency(infoset(0, "J", ()), "bet"),
            # Equilibrium target: 1/3, and unique — every member of the family
            # agrees here, so a deviation is unambiguous.
            "bluff_rate_after_a_check": self._frequency(
                infoset(1, "J", ("check",)), "bet"
            ),
            # The two dominated actions, separately: Nash plays both at zero.
            "folds_the_best_hand_rate": self._frequency(
                infoset(0, "K", ("check", "bet")), "fold", infoset(1, "K", ("bet",))
            ),
            "calls_with_the_worst_hand_rate": self._frequency(
                infoset(0, "J", ("check", "bet")), "call", infoset(1, "J", ("bet",))
            ),
        }

    def _frequency(self, key: str, action: str, *also: str) -> float | None:
        """How often this agent took `action` at the named information set(s).

        Pooled over the keys given, which is how a seat-agnostic rate is formed
        when the same decision exists for both seats — `folds the best hand`
        happens at `P0|K|check-bet` and at `P1|K|bet`, and an agent that rotates
        meets both. `None` when it was never in any of them.
        """
        taken = total = 0
        for candidate in (key, *also):
            counts = self.visits.get(candidate)
            if not counts:
                continue
            taken += counts.get(action, 0)
            total += sum(counts.values())
        return _rate(taken, total)

    def as_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {**asdict(self), **self.rates()}
        # The per-infoset action frequencies, which is what a reader who
        # disbelieves the summary will want to recompute from.
        out["policy"] = {
            seat: self.policy(seat, uniform_policy(seat)) for seat in self._seats_played()
        }
        return out


def aggregate(records: Iterable[dict[str, Any]]) -> dict[str, Any]:
    """Fold a run's transcripts into per-agent statistics."""
    stats: dict[str, KuhnStats] = {}
    games = 0
    truncated = 0
    total_decisions = 0
    deals: dict[str, int] = {}

    def stat(name: str) -> KuhnStats:
        if name not in stats:
            stats[name] = KuhnStats(agent=name)
        return stats[name]

    for record in records:
        games += 1
        seats = {int(k): v for k, v in record["seats"].items()}
        scored = bool(record["terminal"])
        if not scored:
            truncated += 1
        for seat, name in seats.items():
            s = stat(name)
            s.games += 1
            if scored:
                s.games_scored += 1
                s.chips += float(record["returns"][seat])
                if record["returns"][seat] > 0:
                    s.wins += 1

        for name, tally in record.get("usage", {}).items():
            s = stat(name)
            s.llm_calls += int(tally.get("llm_calls", 0))
            s.input_tokens += int(tally.get("input_tokens", 0))
            s.output_tokens += int(tally.get("output_tokens", 0))

        # Which deal this game drew, from the two seats' own facts. Reported
        # because the adapter addresses 4096 seeds over only SIX deals, so a
        # matchup's deal mix is not uniform just because its seeds are distinct.
        drawn: dict[int, str] = {}
        for d in record["decisions"]:
            s = stat(seats[d["player"]])
            s.decisions += 1
            total_decisions += 1
            if d.get("llm", {}).get("fallback"):
                s.fallbacks += 1
            facts = d["facts"]
            s.observe(facts)
            drawn.setdefault(int(facts["seat"]), str(facts["card"]))
        if len(drawn) == 2:
            label = f"{drawn[0]}{drawn[1]}"
            deals[label] = deals.get(label, 0) + 1

    return {
        "games": games,
        "games_truncated": truncated,
        "decisions": total_decisions,
        "deals": dict(sorted(deals.items())),
        "nash_value_seat0": NASH_VALUE[0],
        "agents": {name: s.as_dict() for name, s in sorted(stats.items())},
    }
