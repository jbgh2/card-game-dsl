"""Heads-up fixed-limit Hold'em's half of the per-game seam.

Everything here reads the acting seat's own information-state STRING and
nothing else — the same constraint the model plays under. That is not a
convention: this module imports no engine code, and
`tests/test_prompt_purity.py` walks the transitive import closure of the
decision path, so a `cardlang.*` import one edge away would fail the leak
pins rather than sitting under them.

The cost of that is the small poker evaluator below, which is NOT a second copy
of `cardlang/runtime/poker.py`'s: it ranks a holding into a coarse CATEGORY for
a betting heuristic and does not compute kickers, so it could not settle a pot
and is never asked to. The engine settles pots; this decides whether a baseline
raises.

WHAT IS NOT MEASURED HERE, deliberately: nothing hand-strength-conditioned. A
"was that a bluff" number for poker needs a ground truth for deception that this
harness does not have and this game was not added to provide — Cheat's
`provably_false` works because a claim is checkable against the observer's own
cards, and no such check exists for a raise. The facts below are the chosen verb
and the verbs that were on offer, which is what supports an action rate and
nothing more.

Contract
--------
Assumes: `view.infostate` is the adapter's information-state string for
`cardlang_holdem_heads_up`, in the format `_parse` documents.
Establishes: an action id drawn from `view.legal_actions`, and per-decision
facts derived only from entitled information plus the action taken.
Illegal after: reading a card this seat is not entitled to see.
"""

from __future__ import annotations

import random
import re
from collections import Counter
from collections.abc import Iterable
from dataclasses import asdict, dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:  # below the agent layer, as `kuhn` is: agents.py imports US
    from .agents import Agent, DecisionView

# --- static rules text ----------------------------------------------------
#
# Hand-trimmed from `docs/games/holdem-heads-up.md`, whose own acceptance test
# is that a non-player can read it cold and play a hand. Public information,
# held as a module constant rather than generated: a dynamically-built rules
# string would be one more thing that could vary with hidden state.

RULES_TEXT = """\
You are playing HEADS-UP FIXED-LIMIT TEXAS HOLD'EM — two players, one hand, on
a standard 52-card deck. You are one of the two players. Seats are numbered 0
and 1.

POSITIONS AND BLINDS. Seat 0 holds the button. Heads-up the blinds are
REVERSED: the button posts the SMALL BLIND (1 chip) and seat 1 posts the BIG
BLIND (2 chips). These are forced bets, not decisions. Both players start with
100 chips.

THE DEAL. Each player is dealt two private HOLE CARDS, face down. You see your
own two and never your opponent's.

THE STREETS. There are four betting rounds.
  1. PRE-FLOP, before any community cards. The button acts first.
  2. THE FLOP — three face-up COMMUNITY CARDS are dealt. The big blind (seat 1)
     acts first, and does on every street from here on.
  3. THE TURN — a fourth community card. Bets DOUBLE from here (2 becomes 4).
  4. THE RIVER — a fifth and last community card.
The community cards belong to nobody and are used by BOTH players' hands.

THE ACTIONS. On your turn you may:
  - CHECK — pass, only when nothing is owed.
  - BET — put in the street's bet size when nobody has bet yet.
  - CALL — match what is owed.
  - RAISE — match what is owed and increase by the street's bet size.
  - FOLD — give up the hand and lose what you have already put in.
Only the legal ones are offered to you.

THE BET SIZES ARE FIXED. 2 chips pre-flop and on the flop, 4 on the turn and
river. You do not choose how much to bet — only whether to.

THE RAISE CAP. Each street allows at most FOUR aggressive actions in total.
Pre-flop the big blind is the first of the four, so three raises may follow it;
on later streets it is a bet plus three raises. Once the cap is reached, raising
is no longer offered and the only replies are call and fold.

SHOWDOWN. If neither player folded, both hands are revealed after the river.
Each player makes their best five-card poker hand from the SEVEN available —
their two hole cards plus the five community cards — and the best hand wins the
pot. You may use both hole cards, one, or none ("playing the board"). Equal
hands split the pot.

Standard poker hand ranking, strongest first: straight flush, four of a kind,
full house, flush, straight, three of a kind, two pair, one pair, high card.

WINNING. The hand is the whole game. Your score is the chips you won or lost
against your 100-chip starting stack, so folding early loses little and winning
a raised pot wins a lot.
"""

# How to read the raw information-state string. The state string itself is
# passed through verbatim (never paraphrased or re-rendered) because it is the
# artifact the indistinguishability proofs cover; the cost of that fidelity is
# that its format has to be explained here instead.
FORMAT_TEXT = """\
HOW TO READ YOUR KNOWLEDGE STATE

You are given one line in three sections separated by "|".

  P<seat>|<zones>|state:<variables>|obs:<observation log>

ZONES, separated by ";".
  hole[0]=[4H,8D]   a hand you can see: those exact cards.
  hole[1]=#2        a hand you CANNOT see: only that it holds 2 cards.
  board=[AS,JD,QH]  the community cards, face up to both players.
  deck=#43          cards left undealt.
  burn=?, muck=?    piles whose contents nobody is entitled to.
  shown[0]=[]       the showdown reveal, empty until the hand is shown down.
Suits are the symbols for spades, hearts, diamonds and clubs; ranks are
2-10, J, Q, K, A.

STATE VARIABLES, separated by ";". The ones worth reading:
  stack={0:99,1:98}       chips each player still holds.
  committed={0:1,1:2}     chips each has put in THIS HAND — the pot is their sum.
  bet_by={0:1,1:2}        chips each has put in on THIS STREET.
  bet_to_match=2          the street's standing bet. You owe
                          bet_to_match - bet_by[you]; zero means you may check.
  limit=2                 this street's bet size (2 pre-flop and flop, 4 after).
  raises=1                aggressive actions so far this street.
  raise_cap=4             the cap. No raise is offered once raises reaches it.
  button=0, big_blind=1   who holds which position.
  folded={0:False,1:False}
Others (net, in_hand, acted) are bookkeeping and can be ignored.

OBSERVATION LOG, ";"-separated, oldest first. Each entry is what YOU were
entitled to observe:
  ('move','deck',1,'hole[0]',('4H',))  a card moved and you saw WHICH.
  ('move','deck',1,'hole[1]',1)        a card moved and you saw only HOW MANY.
  ('announce',0,'call')                seat 0 played `call`, publicly.
The log is how you know the betting so far. A card that reached a hidden zone
appears as a count, never an identity — the state simply does not contain what
you are not entitled to.
"""

RULES_RAW = RULES_TEXT + "\n" + FORMAT_TEXT

# --- information-state parsing --------------------------------------------

_RANKS = ("2", "3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K", "A")
_RANK_VALUE = {r: i + 2 for i, r in enumerate(_RANKS)}
_SUITS = "♠♥♦♣"  # spades, hearts, diamonds, clubs
_CARD = re.compile(rf"(10|[2-9JQKA])([{_SUITS}])")


@dataclass(frozen=True)
class Info:
    """What one seat is entitled to know at one decision."""

    seat: int
    hole: tuple[tuple[str, str], ...]  # (rank, suit)
    board: tuple[tuple[str, str], ...]
    bet_to_match: int
    bet_by: dict[int, int]
    committed: dict[int, int]
    limit: int
    raises: int
    raise_cap: int

    @property
    def owed(self) -> int:
        return max(0, self.bet_to_match - self.bet_by.get(self.seat, 0))

    @property
    def pot(self) -> int:
        return sum(self.committed.values())

    @property
    def street(self) -> str:
        return {0: "preflop", 3: "flop", 4: "turn", 5: "river"}.get(
            len(self.board), "unknown"
        )


def _cards(text: str) -> tuple[tuple[str, str], ...]:
    return tuple((m.group(1), m.group(2)) for m in _CARD.finditer(text))


def _int_map(text: str) -> dict[int, int]:
    return {int(k): int(v) for k, v in re.findall(r"(\d+):(-?\d+)", text)}


def parse(infostate: str) -> Info:
    """Parse the adapter's information-state string for this game.

    Raises on a string that does not carry the fields this game's decisions
    need. A parser that returned defaults would let a format change surface as
    a baseline that plays badly — a silent wrong answer — rather than as a
    crash.
    """
    head, zones, state, _, _ = _split(infostate)
    seat = int(head[1:])
    zone_fields = dict(_kv(zones))
    state_fields = dict(_kv(state.removeprefix("state:")))
    missing = {"bet_to_match", "bet_by", "committed", "limit", "raises", "raise_cap"} - set(
        state_fields
    )
    if missing or f"hole[{seat}]" not in zone_fields:
        raise ValueError(
            f"information state is missing {sorted(missing) or f'hole[{seat}]'} — "
            f"the format changed, or this is not a "
            f"cardlang_holdem_heads_up state: {infostate[:120]!r}"
        )
    return Info(
        seat=seat,
        hole=_cards(zone_fields[f"hole[{seat}]"]),
        board=_cards(zone_fields.get("board", "")),
        bet_to_match=int(state_fields["bet_to_match"]),
        bet_by=_int_map(state_fields["bet_by"]),
        committed=_int_map(state_fields["committed"]),
        limit=int(state_fields["limit"]),
        raises=int(state_fields["raises"]),
        raise_cap=int(state_fields["raise_cap"]),
    )


def _split(infostate: str) -> tuple[str, str, str, str, str]:
    """`P<seat>|<zones>|state:...|obs:...` — the observation log may itself
    contain `|`-free tuples, so the split is bounded rather than greedy."""
    parts = infostate.split("|")
    if len(parts) < 3:
        raise ValueError(f"malformed information state: {infostate[:120]!r}")
    obs = "|".join(parts[3:]) if len(parts) > 3 else ""
    return parts[0], parts[1], parts[2], obs, infostate


def _kv(section: str) -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    for field_text in section.split(";"):
        if "=" in field_text:
            key, _, value = field_text.partition("=")
            out.append((key.strip(), value.strip()))
    return out


# --- a coarse hand-strength read ------------------------------------------
#
# Categories only, no kickers: enough to decide whether a baseline raises,
# calls or folds, and deliberately not enough to settle a pot (the engine does
# that, with `cardlang/runtime/poker.py`).

HIGH_CARD, PAIR, TWO_PAIR, TRIPS, STRAIGHT, FLUSH, FULL_HOUSE, QUADS = range(8)


def category(cards: tuple[tuple[str, str], ...]) -> int:
    """The best hand category available from up to seven cards."""
    ranks = Counter(r for r, _ in cards)
    suits = Counter(s for _, s in cards)
    counts = sorted(ranks.values(), reverse=True)
    flush = max(suits.values(), default=0) >= 5
    values = {_RANK_VALUE[r] for r in ranks}
    if 14 in values:
        values.add(1)  # the wheel: A-2-3-4-5
    straight = any(all(v + i in values for i in range(5)) for v in values)
    if counts and counts[0] >= 4:
        return QUADS
    if counts[:2] == [3, 2] or counts.count(3) >= 2:
        return FULL_HOUSE
    if flush:
        return FLUSH
    if straight:
        return STRAIGHT
    if counts and counts[0] == 3:
        return TRIPS
    if counts.count(2) >= 2:
        return TWO_PAIR
    if 2 in counts:
        return PAIR
    return HIGH_CARD


def _hole_is_involved(info: Info) -> bool:
    """Whether the made hand uses a hole card at all. Playing the board is a
    guaranteed split heads-up, so it is worth no chips and the baseline must
    not read it as strength."""
    return category(info.hole + info.board) > category(info.board)


# --- the baseline ---------------------------------------------------------


@dataclass
class HoldemRuleAgent:
    """A tight-aggressive non-learning baseline, decided entirely from the
    information state.

    The policy, and its honest limits. Strength is the coarse `category` of the
    seven (or two, or five) cards this seat may see, plus a pre-flop read of the
    two hole cards alone. It is CRUDE by construction — no pot odds, no position
    play, no draw counting, no opponent model, and no kicker — because its job
    is to be a non-random opponent worth measuring against, not to play well.
    Anything it loses to, it loses to on strength alone.

    - STRONG (two pair or better after the flop; a pocket pair or two high
      cards before it): raise while the cap allows, else bet, else call.
    - FAIR (one pair using a hole card, or an ace): call what is owed, check
      when nothing is; never opens the betting.
    - WEAK: check when free, fold when it costs anything.

    `aggression` is the one tunable: the probability of betting a FAIR holding
    that is checked to it. At 0 the baseline never bluffs and is trivially
    readable; the default 0.25 keeps it from being a pure calling station.
    """

    seed: int
    aggression: float = 0.25
    name: str = "rule"
    _rng: random.Random = field(init=False)

    def __post_init__(self) -> None:
        self._rng = random.Random(self.seed)

    def choose(self, view: "DecisionView") -> int:
        info = parse(view.infostate)
        strength = self._strength(info)
        offered = view.legal_strings
        if strength == "strong":
            want = ["raise", "bet", "call", "check"]
        elif strength == "fair":
            want = (
                ["bet", "check", "call"]
                if self._rng.random() < self.aggression
                else ["check", "call"]
            )
        else:
            want = ["check", "fold"]
        for verb in want:
            if verb in offered:
                return view.legal_actions[offered.index(verb)]
        # Nothing preferred is legal. `call` and `fold` are the only pair that
        # can remain (facing a bet at the cap), so this is the conservative
        # tail rather than a fallback that could pick anything.
        for verb in ("call", "check", "fold"):
            if verb in offered:
                return view.legal_actions[offered.index(verb)]
        return view.legal_actions[0]

    def _strength(self, info: Info) -> str:
        return self._preflop(info) if not info.board else self._postflop(info)

    def _preflop(self, info: Info) -> str:
        """Heads-up pre-flop ranges are WIDE, and the first version of this
        policy got that badly wrong. It played only pairs, two broadway cards
        and aces, folding roughly 57% of the decisions where folding was legal
        — and measured against 400 random hands it won 33.8% of them. A player
        that folds the small blind is laying 1 chip to win 3, so the fold has to
        beat 25% equity, which almost no two cards fail to have heads-up.

        The bands below are a coarse Sklansky-style read, not a solved range:
        a pair or two high cards is strong; one high card, a suited holding or a
        connected one is fair; and only genuinely disconnected low cards are
        weak. Measured, not asserted — `test_holdem_pack.py` pins that this
        baseline beats random on BOTH chips and hands won, which the first
        version did not.
        """
        ranks = sorted(_RANK_VALUE[r] for r, _ in info.hole)
        if len(ranks) < 2:
            return "fair"
        low, high = ranks
        suited = len({s for _, s in info.hole}) == 1
        if low == high:
            return "strong"  # a pocket pair
        if low >= _RANK_VALUE["10"]:
            return "strong"  # two broadway cards
        if high >= _RANK_VALUE["J"] or suited or (high - low) <= 2:
            return "fair"
        return "weak"

    def _postflop(self, info: Info) -> str:
        made = category(info.hole + info.board)
        if made >= TWO_PAIR and _hole_is_involved(info):
            return "strong"
        if made >= PAIR and _hole_is_involved(info):
            return "fair"
        # An overcard to the whole board still wins unimproved often enough to
        # call one bet heads-up; below that there is nothing to continue with.
        board_high = max((_RANK_VALUE[r] for r, _ in info.board), default=0)
        if any(_RANK_VALUE[r] > board_high for r, _ in info.hole):
            return "fair"
        return "weak"

    def pop_trace(self) -> dict[str, Any]:
        return {}


def build_rule_agent(spec: dict[str, Any], seed: int) -> "Agent":
    return HoldemRuleAgent(
        seed=seed,
        aggression=float(spec.get("aggression", 0.25)),
        name=spec.get("name", "rule"),
    )


# --- metric facts ---------------------------------------------------------


def decision_facts(view: "DecisionView", action: str) -> dict[str, Any]:
    """The metric-relevant facts of one decision: the verb chosen and the verbs
    that were on offer.

    `offered` is what makes an action rate honest. A raw fold count over all
    decisions conflates "declined to fold" with "could not fold" — checking is
    free and folding is not offered then — so every rate this game reports is
    denominated in the decisions where the verb was actually available.
    """
    info = parse(view.infostate)
    return {
        "kind": "bet",
        "verb": action,
        "offered": list(view.legal_strings),
        "street": info.street,
        "owed": info.owed,
        "pot": info.pot,
    }


# --- aggregation ----------------------------------------------------------
#
# One `aggregate` per game is this harness's shape (`metrics.aggregate`
# dispatches on the game key), because the statistics that mean something differ by
# game: Cheat reports lie and challenge rates, Kuhn exploitability, and this
# game chips and offer-conditioned action rates.

ACTION_VERBS: tuple[str, ...] = ("check", "bet", "call", "raise", "fold")


@dataclass
class HoldemStats:
    """Everything measured for one agent at heads-up Hold'em, counts first."""

    agent: str = ""
    games: int = 0
    games_scored: int = 0
    wins: int = 0
    splits: int = 0
    net_total: int = 0
    decisions: int = 0
    fallbacks: int = 0
    llm_calls: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    verb_chosen: dict[str, int] = field(default_factory=dict)
    verb_offered: dict[str, int] = field(default_factory=dict)

    def rates(self) -> dict[str, float | None]:
        return {
            # Chips first: it is the metric the blinds do not swamp. A player
            # can win a minority of hands and still finish ahead — this game's
            # first baseline did exactly that — so a win rate alone is not a
            # reading of who played better.
            "mean_net_chips": _rate(self.net_total, self.games_scored),
            "win_rate": _rate(self.wins, self.games_scored),
            "fallback_rate": _rate(self.fallbacks, self.decisions),
            "input_tokens_per_game": _rate(self.input_tokens, self.games),
            "output_tokens_per_game": _rate(self.output_tokens, self.games),
            "llm_calls_per_game": _rate(self.llm_calls, self.games),
            # OFFER-CONDITIONED: a verb's denominator is the decisions where it
            # was LEGAL. Over all decisions instead, `fold_rate` would mix
            # "declined to fold" with "could not fold" — checking is free and
            # folding is not on the table then — and every rate would drift with
            # how often the game happens to offer a free check.
            **{
                f"{verb}_rate": _rate(
                    self.verb_chosen.get(verb, 0), self.verb_offered.get(verb, 0)
                )
                for verb in ACTION_VERBS
            },
        }

    def as_dict(self) -> dict[str, Any]:
        return {**asdict(self), **self.rates()}


def _rate(numerator: float, denominator: int) -> float | None:
    """A rate, or `None` when there were no opportunities — never 0.0, which
    reads as "never did it" when the truth is "was never asked"."""
    return numerator / denominator if denominator else None


def aggregate(records: Iterable[dict[str, Any]]) -> dict[str, Any]:
    """Fold a run's transcripts into per-agent statistics."""
    stats: dict[str, HoldemStats] = {}
    games = 0
    truncated = 0
    total_decisions = 0

    def stat(name: str) -> HoldemStats:
        if name not in stats:
            stats[name] = HoldemStats(agent=name)
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
                net = int(record["returns"][seat])
                s.net_total += net
                if net > 0:
                    s.wins += 1
                elif net == 0:
                    s.splits += 1

        for name, tally in record.get("usage", {}).items():
            s = stat(name)
            s.llm_calls += int(tally.get("llm_calls", 0))
            s.input_tokens += int(tally.get("input_tokens", 0))
            s.output_tokens += int(tally.get("output_tokens", 0))

        for d in record["decisions"]:
            s = stat(seats[d["player"]])
            s.decisions += 1
            total_decisions += 1
            if d.get("llm", {}).get("fallback"):
                s.fallbacks += 1
            # The referee's OWN record of the decision, not the pack's facts.
            # `verify.py` reads the same two fields, so the two folds share an
            # input here — which is why the agreement test compares the
            # ARITHMETIC and `verify.py` keeps its own copy of it.
            for verb in ACTION_VERBS:
                if verb in d["legal"]:
                    s.verb_offered[verb] = s.verb_offered.get(verb, 0) + 1
                    if d["action"] == verb:
                        s.verb_chosen[verb] = s.verb_chosen.get(verb, 0) + 1

    return {
        "games": games,
        "games_truncated": truncated,
        "decisions": total_decisions,
        "agents": {name: s.as_dict() for name, s in sorted(stats.items())},
    }
