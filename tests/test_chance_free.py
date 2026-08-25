"""A Chance-Free Game consumes no randomness, and its OpenSpiel tree says so.

The grid crosses two independent halves against each other. The **classifier**
(`cardlang.runtime.chance.chance_sites`) reads the game's text and names every
construct that would draw. The **oracle** plays the game with a counting
generator installed as `rs.rng` and reports what it actually drew. Neither
calls the other, so their agreement is evidence rather than restatement: a
missing arm in the classifier's enumeration makes a drawing game read
Chance-Free and the counter contradicts it.

The third half is the adapter: a Chance-Free Game registers as
`DETERMINISTIC` with no chance outcomes and opens on a decision node, and
every other game keeps its root [[shuffle-seed]] draw.

Completeness ledger (decisions.md "Closed-domain completeness"):

property:        a game the classifier calls Chance-Free draws nothing when it
                 runs and compiles to a tree whose root is a decision node; a
                 game that draws is never called Chance-Free, and a construct
                 the classifier cannot recognize is refused rather than read as
                 drawing nothing.
domain:          the construct axis is every alternative of the grammar's two
                 randomness-bearing positions -- `epistemic_op` (the `shuffle`
                 and `reveal` arms) crossed with `selection`'s optional
                 `select_mode` (the `chosen` and `random` arms, plus the absent
                 mode the bracket admits) -- each cell a minimal game the
                 oracle plays. The corpus axis is every entry of the adapter's
                 own registry, so a game is in-domain the day its file lands.
                 The classifier reads the checked tree, in which `_apply_uses`
                 has spliced every library definition and `expand` has spliced
                 every procedure body at its call site, so library and
                 procedure text are inside the domain and no import edge is
                 walked separately. Randomness a chooser draws is outside it
                 and stays there: a policy is not the game's chance, so every
                 cell supplies its own chooser with a generator of its own and
                 `rs.rng` sees game draws alone.
registry:        construct axis: `cardlang/grammar/cardlang.lark`, the
                 `epistemic_op` and `select_mode` productions, scraped by
                 `test_construct_axis_is_pinned_by_grammar`. Corpus axis:
                 `cardlang.openspiel.registry.GAMES`. Consumer of the
                 classification: `cardlang.openspiel.replay.chance_free`.
                 One proof module per registry entry:
                 tests/openspiel_ready/test_coverage.py.
does not prove:  the oracle half walks ONE line per game -- a single policy
                 seed -- so a draw site on a branch that line never takes is
                 seen by the classifier alone. The two halves are independent,
                 not jointly exhaustive: what a green rules out is a
                 classifier arm missing for a construct the played line
                 reaches, never one missing for a construct no line reaches.
"""

from __future__ import annotations

import dataclasses
import random
from importlib import resources
from pathlib import Path
from typing import Any

import pytest

from cardlang.ast import nodes as n
from cardlang.openspiel.registry import GAMES
from cardlang.openspiel.replay import DecisionNode, TerminalNode, run
from cardlang.pipeline import check_dsl, check_source
from cardlang.runtime.chance import RefusingRandom, chance_sites, is_chance_free
from cardlang.runtime.chooser import random_chooser
from cardlang.runtime.driver import play_game
from cardlang.runtime.errors import OwnerGuardError, ShadowGuardError

GAMES_DIR = Path(__file__).resolve().parent.parent / "docs" / "games"


class _Counting(random.Random):
    """A generator that answers every draw and counts it. The oracle half: it
    reads what a run consumed, and knows nothing of the classifier."""

    def __init__(self, seed: int) -> None:
        super().__init__(seed)
        self.draws = 0

    def random(self) -> float:
        self.draws += 1
        return super().random()

    def getrandbits(self, k: int) -> int:
        self.draws += 1
        return super().getrandbits(k)


def _play_counting(game: n.Game, policy_seed: int = 1) -> tuple[int, bool]:
    """Play `game` with a counting generator as `rs.rng` and a chooser drawing
    from a generator of its own. Returns (draws, completed).

    The chooser is supplied rather than defaulted precisely because
    `driver.play_game` would otherwise build `random_chooser(rng)` over the
    same generator, and the policy's draws would count as the game's.

    A playout may exhaust its declared `max_length` on a long random line; the
    draws taken before that are still what the run consumed, so the count is
    returned either way and the completion flag carries the difference."""
    rng = _Counting(0)
    try:
        play_game(game, rng, chooser=random_chooser(random.Random(policy_seed)))
    except OwnerGuardError:
        return rng.draws, False
    return rng.draws, True


# =============================================================================
# The construct axis -- pinned against the grammar productions that define it
# =============================================================================


def test_construct_axis_is_pinned_by_grammar() -> None:
    """The randomness-bearing positions are two grammar productions, and the
    cells below cross every alternative of both. Scraped rather than listed so
    a new `epistemic_op` arm or `select_mode` arm surfaces here as an
    uncovered member instead of silently reading as non-drawing."""
    grammar = resources.files("cardlang.grammar").joinpath("cardlang.lark").read_text()

    epistemic = _production(grammar, "epistemic_op")
    ops = {alias[: -len("_op")] for alias in _aliases(epistemic) if alias.endswith("_op")}
    assert ops == {"shuffle", "reveal"}, (
        f"the epistemic-op alternatives are {sorted(ops)}; the construct grid "
        f"covers {sorted(EPISTEMIC_CELLS)} -- add the new arm to both the grid "
        f"and cardlang.runtime.chance's enumeration"
    )

    modes = _production(grammar, "select_mode")
    named = {alias[len("sel_"):] for alias in _aliases(modes) if alias.startswith("sel_")}
    assert named == {"chosen", "random"}, (
        f"the select-mode alternatives are {sorted(named)}; the construct grid "
        f"covers {sorted(m for m in SELECTION_CELLS if m is not None)}"
    )
    # The bracket on `select_mode` is the third member of the selection axis:
    # a movement may state no mode at all, and that cell is covered below.
    assert "selection: [select_mode]" in grammar, (
        "the selection mode is no longer optional -- the absent-mode cell of "
        "the grid describes surface that no longer exists"
    )


def _production(grammar: str, name: str) -> str:
    """The text of one lark production, from its `name:` line through its
    continuation lines (those beginning with the alternation bar)."""
    lines = grammar.splitlines()
    start = next(i for i, line in enumerate(lines) if line.startswith(f"{name}:"))
    out = [lines[start]]
    for line in lines[start + 1 :]:
        if line.strip().startswith("|"):
            out.append(line)
        elif line.strip() and not line.strip().startswith("//"):
            break
    return "\n".join(out)


def _aliases(production: str) -> set[str]:
    """The `-> alias` names of a production's alternatives."""
    return {
        part.split("->", 1)[1].strip().split()[0]
        for part in production.splitlines()
        if "->" in part
    }


_PRELUDE = """
game G {
  players: 2
  max_length: 200
  cards: standard52
  ranking: A K Q J 10 9 8 7 6 5 4 3 2
  zones { deck : Deck  hand[player] : Hand<player>  pile : Discard }
  state { score[player] : Integer = 0 }
  phase p { BODY }
  winner: highest score
}
"""


def _minimal(body: str) -> n.Game:
    return check_dsl(_PRELUDE.replace("BODY", body), "chance_cell.cardlang")


# construct -> (statement exercising it, whether it draws from the game's rng).
# The expected column is a design decision, authored from what each construct
# MEANS: `shuffle` permutes by chance and `random` selection picks by chance;
# `reveal` names a card the predicate already fixes, `chosen` defers to the
# chooser seam, and an absent mode deals off the top. Nothing here is captured
# from the implementation.
EPISTEMIC_CELLS: dict[str, tuple[str, bool]] = {
    "shuffle": ("shuffle deck", True),
    "reveal": ("reveal one card from deck", False),
}

# Every selection cell runs inside `for each player p:` so the mode is the only
# thing varying across the axis -- `chosen` needs an acting player for the
# chooser to address, and giving the other modes a different frame would put a
# second difference into a one-axis grid.
SELECTION_CELLS: dict[str | None, tuple[str, bool]] = {
    "random": ("for each player p: move random one card from deck to pile", True),
    "chosen": ("for each player p: move chosen one card from deck to pile", False),
    None: ("for each player p: move one card from deck to pile", False),
}


@pytest.mark.parametrize("op", sorted(EPISTEMIC_CELLS))
def test_epistemic_op_cell(op: str) -> None:
    """Each epistemic op: the classifier names it as a chance site exactly when
    playing it draws."""
    body, draws_expected = EPISTEMIC_CELLS[op]
    game = _minimal(body)
    drawn, completed = _play_counting(game)
    assert completed, f"the {op} cell's minimal game did not finish"
    assert (drawn > 0) is draws_expected, (
        f"`{body}` drew {drawn} times; the cell expects "
        f"{'a draw' if draws_expected else 'no draw'}"
    )
    assert is_chance_free(game) is not draws_expected, (
        f"the classifier calls `{body}` "
        f"{'Chance-Free' if is_chance_free(game) else 'chance-bearing'}, "
        f"and the run drew {drawn} times"
    )
    if draws_expected:
        assert any(op in site for site in chance_sites(game)), (
            f"the classifier names {chance_sites(game)} as this game's chance "
            f"sites, none of which mentions `{op}`"
        )


@pytest.mark.parametrize(
    "mode", sorted(SELECTION_CELLS, key=lambda m: "" if m is None else str(m))
)
def test_selection_mode_cell(mode: str | None) -> None:
    """Each selection mode, including the absent one the grammar's bracket
    admits: the classifier names it as a chance site exactly when playing it
    draws."""
    body, draws_expected = SELECTION_CELLS[mode]
    game = _minimal(body)
    drawn, completed = _play_counting(game)
    assert completed, f"the {mode} selection cell's minimal game did not finish"
    assert (drawn > 0) is draws_expected, (
        f"`{body}` drew {drawn} times; the cell expects "
        f"{'a draw' if draws_expected else 'no draw'}"
    )
    assert is_chance_free(game) is not draws_expected, (
        f"the classifier calls `{body}` "
        f"{'Chance-Free' if is_chance_free(game) else 'chance-bearing'}, "
        f"and the run drew {drawn} times"
    )


# =============================================================================
# The refusal -- a construct the enumeration does not recognize
# =============================================================================


def test_unknown_epistemic_op_is_refused_not_read_as_chance_free() -> None:
    """An epistemic op outside the enumeration is refused, and the message names
    the two sites that disagree. An internal invariant rather than a typed
    runtime channel, the same shape `replay.returns_for` uses for an unhandled
    RANK_DIR: no game description is at fault, the engine's table is out of sync
    with the grammar. Reading the op as non-drawing instead is the silent half
    of this defect class -- a future `roll` arm would then collapse the chance
    node of a game that rolls dice."""
    game = _minimal("shuffle deck")
    hijacked = _retag(game, n.EpistemicOp, op="peek")
    with pytest.raises(AssertionError, match="unhandled epistemic op 'peek'"):
        chance_sites(hijacked)


def test_unknown_selection_mode_is_refused_not_read_as_chance_free() -> None:
    """A selection mode outside the enumeration is refused, for the same
    reason: an unrecognized mode must not read as dealing off the top."""
    game = _minimal("move random one card from deck to pile")
    hijacked = _retag(game, n.Transfer, selection_mode="telepathic")
    with pytest.raises(AssertionError, match="unhandled selection mode 'telepathic'"):
        chance_sites(hijacked)


def _retag(game: n.Game, node_type: type, **changes: Any) -> n.Game:
    """`game` with every node of `node_type` rebuilt with `changes` applied.

    A generic rewrite rather than an indexed one: the probe's construct sits
    wherever its cell's minimal game puts it, and reaching for `phases[0]` would
    tie the probe to one body shape.
    """

    def rec(node: Any) -> Any:
        if dataclasses.is_dataclass(node) and not isinstance(node, type):
            rebuilt = {
                f.name: rec(getattr(node, f.name)) for f in dataclasses.fields(node)
            }
            if isinstance(node, node_type):
                rebuilt.update(changes)
            return dataclasses.replace(node, **rebuilt)
        if isinstance(node, tuple):
            return tuple(rec(item) for item in node)
        return node

    rewritten = rec(game)
    assert isinstance(rewritten, n.Game)
    return rewritten


@pytest.mark.expects_shadow_guard
def test_refusing_generator_refuses_every_draw() -> None:
    """The generator installed for a Chance-Free Game refuses at the two
    primitives every other `random.Random` method is built on, so a draw the
    classifier missed stops the run at its site rather than returning a value
    nothing checks. `ShadowGuardError` is the channel because a firing means the
    engine's enumeration leaked, never that the game is bad -- and the suite
    already fails on any `ShadowGuardError` raised during a run."""
    r = RefusingRandom(0)
    for label, call in (
        ("sample", lambda: r.sample([1, 2, 3], 2)),
        ("shuffle", lambda: r.shuffle([1, 2, 3])),
        ("choice", lambda: r.choice([1, 2, 3])),
        ("randint", lambda: r.randint(0, 5)),
        ("randrange", lambda: r.randrange(5)),
        ("uniform", lambda: r.uniform(0.0, 1.0)),
        ("choices", lambda: r.choices([1, 2], k=2)),
        ("gauss", lambda: r.gauss(0.0, 1.0)),
    ):
        try:
            call()
        except ShadowGuardError:
            continue
        pytest.fail(f"{label} answered a draw instead of refusing it")


# =============================================================================
# The corpus axis -- classifier against oracle, over the adapter's own registry
# =============================================================================

# The corpus games that consume no randomness. A pin, not a derivation: the
# equality below would also hold if both halves went blind together, and this
# says which games the corpus actually contains. A new board game reddens it,
# and the author confirms rather than discovers.
CHANCE_FREE_CORPUS: frozenset[str] = frozenset(
    {"cardlang_breakthrough", "cardlang_tic_tac_toe"}
)


@pytest.mark.parametrize("short_name", sorted(GAMES))
def test_corpus_classification_agrees_with_what_the_game_draws(short_name: str) -> None:
    """Every corpus game: the classifier's verdict and the run's draw count
    agree. The two are computed by different mechanisms -- a walk over the
    checked tree, and a counter on the live generator -- so this cell fails
    whenever an arm of the enumeration is missing for a construct the played
    line reaches."""
    game = check_source(GAMES_DIR / GAMES[short_name])
    free = is_chance_free(game)
    drawn, completed = _play_counting(game)
    assert free == (drawn == 0), (
        f"{short_name}: the classifier calls it "
        f"{'Chance-Free' if free else 'chance-bearing'} and its playout drew "
        f"{drawn} times; sites named: {chance_sites(game)}"
    )
    if free:
        assert completed, (
            f"{short_name}: classified Chance-Free but its playout did not "
            f"finish -- a game that cannot complete is not evidence it draws "
            f"nothing"
        )


def test_the_chance_free_corpus_is_exactly_the_two_board_games() -> None:
    """Which corpus games are Chance-Free is a fact about the corpus, pinned so
    a game gaining or losing its randomness is a decision someone makes rather
    than a set that quietly moves.

    red under: set `EPISTEMIC_OP_DRAWS["shuffle"] = False` in
    `cardlang/runtime/chance.py`. Every shuffling game then classifies
    Chance-Free and this set grows to the whole registry (verified).
    """
    free = {
        short for short in GAMES if is_chance_free(check_source(GAMES_DIR / GAMES[short]))
    }
    assert free == CHANCE_FREE_CORPUS, (
        f"the Chance-Free corpus games are {sorted(free)}, and this pin names "
        f"{sorted(CHANCE_FREE_CORPUS)}"
    )


# =============================================================================
# The adapter axis -- the tree shape follows the classification
# =============================================================================


@pytest.mark.parametrize("short_name", sorted(GAMES))
def test_adapter_root_follows_the_classification(short_name: str) -> None:
    """A Chance-Free Game opens on a decision node and declares no chance
    outcomes; every other game opens on its root [[shuffle-seed]] draw. The
    expected side is read from the classifier, and the cell asserts the
    adapter's four declared facts move together -- a game whose GameType says
    DETERMINISTIC while its root is a chance node is the shape this catches."""
    pyspiel = pytest.importorskip("pyspiel")
    import cardlang.openspiel.game  # noqa: F401  (registers every corpus game)

    free = is_chance_free(check_source(GAMES_DIR / GAMES[short_name]))
    game = pyspiel.load_game(short_name)
    state = game.new_initial_state()

    expected_mode = (
        pyspiel.GameType.ChanceMode.DETERMINISTIC
        if free
        else pyspiel.GameType.ChanceMode.EXPLICIT_STOCHASTIC
    )
    assert game.get_type().chance_mode == expected_mode
    assert (game.max_chance_outcomes() == 0) is free
    assert state.is_chance_node() is not free
    assert (state.current_player() == pyspiel.PlayerId.CHANCE) is not free


@pytest.mark.parametrize("short_name", sorted(CHANCE_FREE_CORPUS))
def test_chance_free_root_carries_a_real_information_state(short_name: str) -> None:
    """Collapsing the chance node moves the game's first information state to
    the root, where the chance node used to render the empty string. Every seat
    sees a populated state before any action is applied."""
    pyspiel = pytest.importorskip("pyspiel")
    import cardlang.openspiel.game  # noqa: F401

    game = pyspiel.load_game(short_name)
    state = game.new_initial_state()
    for player in range(game.num_players()):
        assert state.information_state_string(player), (
            f"{short_name}: P{player} has no information state at the root"
        )


@pytest.mark.parametrize("short_name", sorted(CHANCE_FREE_CORPUS))
def test_chance_free_game_plays_to_terminal_under_a_refusing_generator(
    short_name: str,
) -> None:
    """The executed half of the collapse's licence, stated per game: a full
    greedy line reaches a terminal node while the generator refuses every draw.
    This is what replaces a cross-seed comparison -- once the seed cannot reach
    a draw, comparing seeds asserts nothing, while a line that completes under
    refusal can fail.

    red under: add `shuffle box` to a phase of `docs/games/tic-tac-toe.cardlang`
    and set `EPISTEMIC_OP_DRAWS["shuffle"] = False` -- one fault, that the
    enumeration does not know `shuffle` draws. The game then classifies
    Chance-Free, `run` gives it the refusing generator, and the line dies at the
    shuffle with `ShadowGuardError` naming the leaked classifier (verified)."""
    path = str(GAMES_DIR / GAMES[short_name])
    history: list[int] = []
    r: Any = run(path, 0, ())
    steps = 0
    while isinstance(r, DecisionNode) and steps < 500:
        history.append(r.legal[0])
        r = run(path, 0, tuple(history))
        steps += 1
    assert isinstance(r, TerminalNode), (
        f"{short_name}: the greedy line did not reach a terminal node in "
        f"{steps} steps"
    )
