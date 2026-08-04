"""The per-game seam: everything in this harness that is about ONE game.

The harness was built for Cheat, with the game's rules text, decision shapes,
metric facts and baseline policy spread across `prompts.py`, `agents.py` and
`metrics.py`. A `GamePack` gathers those four things behind one value, so a
second game is a new pack rather than an edit to the game loop. What stayed
game-generic and did NOT move: the referee, the provider layer, the transcript
format, the budget accounting, and the win-rate/fallback/token statistics.

The registry REFUSES an unknown game rather than defaulting. A harness that
silently ran Cheat's rules text against another game's information state would
produce numbers that look fine and mean nothing — the accepted-but-ignored
failure in its measurement form.

Not every corpus game has a pack, and that is the honest state: a pack needs
rules text a model can read and a baseline worth losing to, which is per-game
work. `UNPACKED` names the corpus games without one, and
`tests/test_packs.py::test_every_corpus_game_is_packed_or_named_unpacked` keeps
that list tight in BOTH directions — a game that gains a pack and stays listed
fails as loudly as one that appears with neither. Absence stays a named gap
rather than an unexamined one (the `PROSE_ONLY_TWINS` idiom in
`tests/test_typecheck_corpus.py`).

Contract
--------
Assumes: a pack's `rules_*` texts are static constants, and its `facts` a pure
function of a `DecisionView` plus the chosen action string.
Establishes: exactly one game's worth of game-specific behaviour per pack, and
a loud refusal for any game without one.
Illegal after: reading a rules text, a baseline, or a facts function from
anywhere but the pack for the game being played.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from . import cheat_pack, holdem_pack
from .agents import Agent, DecisionView


@dataclass(frozen=True)
class GamePack:
    """One game's worth of harness configuration."""

    # The registered OpenSpiel short name (`cardlang_cheat`), which is also the
    # `game:` key in a run config.
    short_name: str

    # The static rules text for the raw-information-state arm, and for the
    # rendered arm. `rules_rendered = None` means this game has no rendered
    # arm; `render: true` on one of its agents is then refused at construction
    # rather than silently falling back to the raw text, which would put two
    # incomparable arms under one name.
    #
    # The pair travels together deliberately. The two arms' texts differ only
    # in their format guide, so a caller-supplied third text would make the
    # arms' numbers incomparable — the invariant `LLMAgent.rules` used to keep
    # by deriving from a module constant, kept here by owning both.
    rules_raw: str
    rules_rendered: str | None

    # The metric-relevant facts of one decision, from the acting player's own
    # information state plus the action they chose.
    facts: Callable[[DecisionView, str], dict[str, Any]]

    # This game's non-learning baseline, from a config block and a seed.
    build_rule_agent: Callable[[dict[str, Any], int], Agent]

    # The move-type names whose offer-conditioned rates `metrics.aggregate`
    # reports for this game (chosen / times legal). Empty for a game whose
    # interesting behaviour is not a verb choice — Cheat's is the lie and the
    # challenge, which have their own metrics.
    action_verbs: tuple[str, ...] = ()

    # Whether this game's OpenSpiel returns are chip-denominated, so their mean
    # is worth reporting. On for a betting game, where win rate and chip delta
    # can point in opposite directions; off for a game scored +/-1, where the
    # mean return is just `2 * win_rate - 1`.
    reports_chip_delta: bool = False


CHEAT = GamePack(
    short_name="cardlang_cheat",
    rules_raw=cheat_pack.RULES_RAW,
    rules_rendered=cheat_pack.RULES_RENDERED,
    facts=cheat_pack.decision_facts,
    build_rule_agent=cheat_pack.build_rule_agent,
)

HOLDEM_HEADS_UP = GamePack(
    short_name="cardlang_holdem_heads_up",
    rules_raw=holdem_pack.RULES_RAW,
    # No rendered arm. The rendered arm exists to answer "does English help
    # comprehension"; that question was answered on Cheat and is not re-asked
    # here (this game's brief is win rate and action rates). A `render: true`
    # agent on this game is refused rather than quietly served the raw text.
    rules_rendered=None,
    facts=holdem_pack.decision_facts,
    build_rule_agent=holdem_pack.build_rule_agent,
    action_verbs=("check", "bet", "call", "raise", "fold"),
    reports_chip_delta=True,
)


PACKS: dict[str, GamePack] = {p.short_name: p for p in (CHEAT, HOLDEM_HEADS_UP)}

# Corpus games with no pack, by OpenSpiel short name. Not a backlog and not an
# oversight: a pack is per-game work (rules text a model can read, a baseline
# worth measuring against), and this harness exists to answer questions about
# deception and about what a second game costs — not to cover the corpus.
UNPACKED: frozenset[str] = frozenset(
    {
        "cardlang_belote",
        "cardlang_big_two",
        "cardlang_breakthrough",
        "cardlang_bridge",
        "cardlang_canasta",
        "cardlang_coup",
        "cardlang_cribbage",
        "cardlang_doppelkopf",
        "cardlang_five_hundred",
        "cardlang_freecell",
        "cardlang_french_tarot",
        "cardlang_getaway",
        "cardlang_gin_rummy",
        "cardlang_go_fish",
        "cardlang_gops",
        "cardlang_hearts",
        "cardlang_holdem",
        "cardlang_klondike",
        "cardlang_kuhn_poker",
        "cardlang_leduc_poker",
        "cardlang_oh_hell",
        "cardlang_pinochle",
        "cardlang_president",
        "cardlang_schnapsen",
        "cardlang_seven_card_stud",
        "cardlang_skat",
        "cardlang_spades",
        "cardlang_tic_tac_toe",
        "cardlang_tichu",
    }
)


def pack_for(short_name: str) -> GamePack:
    """The pack for a registered game, or a loud refusal.

    Defaulting to Cheat's pack is the failure this refusal exists to prevent:
    Cheat's rules text against another game's information state produces a
    transcript that parses, aggregates, and means nothing.
    """
    try:
        return PACKS[short_name]
    except KeyError:
        raise SystemExit(
            f"no harness pack for game {short_name!r}. Packed: "
            f"{sorted(PACKS)}. A game needs its rules text, decision facts and "
            f"a baseline policy before it can be evaluated — add a pack in "
            f"experiments/llm_eval/packs.py, and drop the game from UNPACKED "
            f"there in the same change."
        ) from None
