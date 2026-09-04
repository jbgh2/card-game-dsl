"""Every fully-kernel game as a registered ``pyspiel.Game``.

One general adapter (SP1 spec): the state is ``(seed, history)`` over the
re-simulation engine — that seed being the [[shuffle-seed]] the root chance node
draws, fixed and unexposed for a Chance-Free Game, whose tree carries no such
node — the action space and information states are DERIVED, and
registration is a loop over the game table — adding a fully-kernel game to the
table is the whole per-game cost. Importing this module registers every corpus
game, and every file ``CARDLANG_GAMES`` names; load with e.g.
``pyspiel.load_game("cardlang_hearts")``.

A game file anywhere on disk reaches the same tree through
:func:`register_game_file`. Three sources — the corpus glob, that call, and
that environment variable — and one ``_register``, so a path-registered game
is checked, classified and named exactly as a corpus game is. What it does NOT
get is the readiness proof battery, which runs per corpus game from a
hand-authored module and has no way in by path (issue #25): a game registered
by path has the adapter's derived information states and no proof they are
sound.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import pyspiel

from cardlang.openspiel import replay
from cardlang.openspiel.infostate import information_state
from cardlang.runtime.errors import GameRegistrationError, ShadowGuardError

_NUM_SEEDS = 4096  # sampled deal space at the root chance node (known limitation)
# The seed a Chance-Free Game runs under. Any value does: its generator refuses
# every draw (`cardlang.runtime.chance`), so no branch of the collapsed node
# could have differed from any other.
_CHANCE_FREE_SEED = 0

from cardlang.openspiel.registry import GAMES as GAMES
from cardlang.openspiel.registry import SHORT_NAME_CHARS, _GAMES_DIR, _short_name

# The environment variable naming extra game files, `os.pathsep`-separated,
# each a file or a directory globbed as the corpus is.
GAMES_ENV_VAR = "CARDLANG_GAMES"

# What one of that variable's entries can be. The dispatch in
# `_register_env_entry` reads this vocabulary, so a kind added here without an
# arm is a name with no behavior rather than a silent skip.
ENTRY_KINDS: tuple[str, ...] = ("file", "directory", "missing", "empty")

# short name -> the resolved file it was registered from. Seeded by the corpus
# loop at the bottom of this module, which is what lets a later collision name
# the corpus file it would otherwise have replaced: `pyspiel.register_game`
# accepts a duplicate short name and the LAST registration wins, silently, so
# without this map a designer's own `hearts.cardlang` would answer
# `pyspiel.load_game("cardlang_hearts")` for the rest of the process.
_REGISTERED: dict[str, str] = {}


class _Observer:
    """Minimal observer providing the information-state string (no tensors)."""

    def __init__(self) -> None:
        self.tensor = None
        self.dict: dict[str, Any] = {}

    def set_from(self, state: CardlangState, player: int) -> None:
        pass  # no tensor representation

    def string_from(self, state: CardlangState, player: int) -> str:
        return state.information_state_string(player)


class CardlangState(pyspiel.State):
    """``_seed is None`` exactly while a root chance node is pending.

    A Chance-Free Game has no such node, so its seed is fixed at construction
    and the predicate stays true by definition rather than carrying a second
    meaning: `current_player` never reports CHANCE for it, and the root is its
    first decision.
    """

    def __init__(
        self, game: pyspiel.Game, path: str, num_players: int, chance_free: bool
    ) -> None:
        super().__init__(game)
        self._path = path
        self._num_players = num_players
        self._chance_free = chance_free
        self._seed: int | None = _CHANCE_FREE_SEED if chance_free else None
        self._history_ids: list[int] = []
        self._cache_key: Any = object()
        self._cache: replay.DecisionNode | replay.TerminalNode | None = None

    def _run(self) -> replay.DecisionNode | replay.TerminalNode:
        assert self._seed is not None
        key = (self._seed, tuple(self._history_ids))
        if self._cache_key != key:
            self._cache = replay.run(self._path, self._seed, tuple(self._history_ids))
            self._cache_key = key
        assert self._cache is not None
        return self._cache

    def current_player(self) -> int:
        if self._seed is None:
            return pyspiel.PlayerId.CHANCE
        r = self._run()
        return pyspiel.PlayerId.TERMINAL if isinstance(r, replay.TerminalNode) else r.player

    def _legal_actions(self, player: int) -> list[int]:
        r = self._run()
        assert isinstance(r, replay.DecisionNode)
        return r.legal

    def chance_outcomes(self) -> list[tuple[int, float]]:
        if self._chance_free:
            # Unreachable while the classification is right — pyspiel asks only
            # at a chance node, and this game declares none. Saying so beats the
            # bare assert it replaces: a wrong classification surfaces as the
            # sentence that names it, not as a traceback the reader must decode.
            raise ShadowGuardError(
                "cardlang.runtime.chance.chance_sites",
                f"pyspiel asked {self._path} for chance outcomes, but it is "
                f"registered DETERMINISTIC because nothing in it draws",
            )
        assert self._seed is None
        p = 1.0 / _NUM_SEEDS
        return [(i, p) for i in range(_NUM_SEEDS)]

    def _apply_action(self, action: int) -> None:
        if self._seed is None:
            self._seed = int(action)
        else:
            self._history_ids.append(int(action))

    def _action_to_string(self, player: int, action: int) -> str:
        if player == pyspiel.PlayerId.CHANCE:
            return f"Chance(seed={action})"
        _, space = replay.load(self._path)
        return space.to_string(action)

    def is_terminal(self) -> bool:
        return self._seed is not None and isinstance(self._run(), replay.TerminalNode)

    def returns(self) -> list[float]:
        if self._seed is None:
            return [0.0] * self._num_players
        r = self._run()
        return r.returns if isinstance(r, replay.TerminalNode) else [0.0] * self._num_players

    def information_state_string(self, player: int | None = None) -> str:
        if self._seed is None:
            return ""  # chance root
        if player is None:
            player = self.current_player()
        r = self._run()
        if not isinstance(r, replay.DecisionNode):
            return ""
        return information_state(player, r.rs, r.obs_logs[player])

    def clone(self) -> CardlangState:
        copy = CardlangState(
            self.get_game(), self._path, self._num_players, self._chance_free
        )
        copy._seed = self._seed
        copy._history_ids = list(self._history_ids)
        return copy

    def __str__(self) -> str:
        if self._chance_free:
            return f"history={self._history_ids}"
        return f"seed={self._seed} history={self._history_ids}"


def _register(short_name: str, path: str) -> None:
    """Register the game at `path` under `short_name`, or refuse.

    The one call to `pyspiel.register_game` in the package — every source goes
    through here, so the collision rule and the classification read cannot come
    to differ between them. The path is used as given rather than normalized:
    it becomes `replay.load`'s cache key and the state's own `_path`, and the
    corpus's spelling is the one every other consumer of `GAMES` builds. What
    IS normalized is the identity `_REGISTERED` records, so two spellings of a
    file are one registration rather than a collision.

    A repeat of the same file is a no-op. Re-reading it is not: `replay.load`
    memoizes on the path, so a file edited between two registrations in one
    process keeps the tree it was first checked with. Designed — the alternative
    is an mtime key that makes one file two games in one process, and the
    registry has no way to retract the first.
    """
    key = str(Path(path).resolve())
    prior = _REGISTERED.get(short_name)
    if prior is not None:
        if prior == key:
            return
        raise GameRegistrationError(
            f"two files claim the OpenSpiel short name {short_name!r}: "
            f"{prior} is registered and {key} would replace it. Rename one — "
            f"the short name is the file's stem, so two files with one stem "
            f"are one game to pyspiel."
        )
    game_ast, space = replay.load(path)
    # The one read of the classification per registered game. The GameType's
    # chance mode, the declared outcome count and the state's opening node all
    # come off this single answer, so they cannot describe different games.
    chance_free = replay.chance_free(path)
    num_players = game_ast.players.low
    assert game_ast.max_length is not None, "resolve() must reject a missing max_length"
    game_type = pyspiel.GameType(
        short_name=short_name,
        long_name=f"Cardlang {game_ast.name}",
        dynamics=pyspiel.GameType.Dynamics.SEQUENTIAL,
        chance_mode=(
            pyspiel.GameType.ChanceMode.DETERMINISTIC
            if chance_free
            else pyspiel.GameType.ChanceMode.EXPLICIT_STOCHASTIC
        ),
        # Asserted, not derived, and designed so: the obvious derivation is a
        # wall rather than an oversight. "Perfect iff every declared zone
        # type projects identity to all" (`stdlib.zones.identity_to_all`)
        # answers IMPERFECT for every game in `GAMES`, a constant wearing a
        # function; IMPERFECT_INFORMATION is meanwhile the conservative
        # over-approximation and stays sound for every consumer. What makes
        # the perfect-information games here perfect-information is that their
        # one count-projected zone is EMPTY at every decision node, a fact
        # about the run that no zone type states. `trivial` does not state it
        # either, being the most hidden projection rather than an inert one
        # (`observe.view_of` renders it None), which is why Hold'em's muck
        # carries it. Hence the asymmetry with `chance_mode` above — that
        # field has a cheap sound static answer (`runtime.chance.chance_sites`)
        # and this one has none. Making this one true takes either a static
        # reachability analysis over every card-adding construct or a declared
        # clause the checker enforces; both are real surface for a field no
        # consumer reads, so the conservative constant stands until one does.
        # `tests/test_zone_projections.py` reddens if the vacuity ever ends.
        information=pyspiel.GameType.Information.IMPERFECT_INFORMATION,
        utility=pyspiel.GameType.Utility.GENERAL_SUM,
        reward_model=pyspiel.GameType.RewardModel.TERMINAL,
        max_num_players=num_players,
        min_num_players=num_players,
        provides_information_state_string=True,
        provides_information_state_tensor=False,
        provides_observation_string=False,
        provides_observation_tensor=False,
        provides_factored_observation_string=False,
    )
    game_info = pyspiel.GameInfo(
        num_distinct_actions=space.num_distinct_actions,
        max_chance_outcomes=0 if chance_free else _NUM_SEEDS,
        num_players=num_players,
        min_utility=-100000.0,  # loose static bounds; true scores are far inside
        max_utility=100000.0,
        utility_sum=None,
        max_game_length=game_ast.max_length,
    )

    class _Game(pyspiel.Game):
        def __init__(self, params: Any = None) -> None:
            super().__init__(game_type, game_info, params or {})

        def new_initial_state(self) -> CardlangState:
            return CardlangState(self, path, num_players, chance_free)

        def make_py_observer(self, iig_obs_type: Any = None, params: Any = None) -> _Observer:
            return _Observer()

    pyspiel.register_game(game_type, _Game)
    _REGISTERED[short_name] = key


def register_game_file(path: str | Path) -> str:
    """Register the game file at `path` with pyspiel; return its short name.

    The way in for a game that does not live in `docs/games/`. The file gets
    the same static check a corpus game gets (`cardlang.pipeline.check_source`,
    so a `.cardlang` file is raw DSL and any other suffix is read as Markdown
    holding one fenced block), the same naming rule
    (`cardlang.openspiel.registry`), and the same tree. A check failure raises
    the checker's own `DiagnosticError`, addressed to the game's author with a
    span; nothing about the file's provenance reaches that channel.

    Registering the same file twice is a no-op returning the same name, so a
    caller may offer a directory's worth of games without tracking which it has
    already done. A short name another file holds is refused naming both, since
    pyspiel would otherwise take the second and answer with it.

    What this does not do is prove the game ready: the readiness battery runs
    per corpus game from a hand-authored module under `tests/openspiel_ready/`,
    and issue #25 is the way in by path. A game registered here has derived
    information states, and no proof they hold.
    """
    p = Path(path)
    if not p.is_file():
        reason = "no such file" if not p.exists() else "not a file"
        raise GameRegistrationError(f"cannot register {p}: {reason}")
    short_name = _short_name(p.name)
    if not SHORT_NAME_CHARS.fullmatch(short_name):
        raise GameRegistrationError(
            f"{p.name!r} derives the OpenSpiel short name {short_name!r}, "
            f"which pyspiel cannot load — a stem may hold only letters, "
            f"digits, hyphens and underscores. Rename the file."
        )
    _register(short_name, str(p.resolve()))
    return short_name


def _entry_kind(entry: str) -> str:
    """Which of `ENTRY_KINDS` a `CARDLANG_GAMES` entry is."""
    if not entry.strip():
        return "empty"
    p = Path(entry)
    if p.is_file():
        return "file"
    if p.is_dir():
        return "directory"
    return "missing"


def _register_env_entry(entry: str) -> None:
    """Register what one `CARDLANG_GAMES` entry names.

    A directory is globbed as the corpus directory is — `*.cardlang`, one level
    — and an empty one is refused rather than registering nothing: the entry
    was written to load games, so finding none is a typo and not an answer.
    """
    kind = _entry_kind(entry)
    if kind == "file":
        register_game_file(entry)
        return
    if kind == "directory":
        found = sorted(Path(entry).glob("*.cardlang"))
        if not found:
            raise GameRegistrationError(
                f"{GAMES_ENV_VAR} names the directory {entry}, which holds no "
                f".cardlang games."
            )
        for game_file in found:
            register_game_file(game_file)
        return
    if kind == "empty":
        raise GameRegistrationError(
            f"{GAMES_ENV_VAR} holds an empty entry — two {os.pathsep!r} "
            f"separators with nothing between them, or a trailing one. Remove "
            f"it; an empty entry names no file."
        )
    raise GameRegistrationError(
        f"{GAMES_ENV_VAR} names {entry}, which is neither a file nor a "
        f"directory."
    )


def _register_env_var() -> None:
    """Register everything `CARDLANG_GAMES` names, refusing loudly.

    A malformed entry stops this import, corpus registration included, and that
    is the decision rather than an oversight: the variable is set by whoever
    runs this process, this run, for no purpose but to load those games, so
    skipping a bad entry would hand back the `Unknown game` it was set to
    escape — with a configuration that looks applied. An unset variable and one
    set to nothing mean the same thing and register nothing.
    """
    value = os.environ.get(GAMES_ENV_VAR, "")
    if not value.strip():
        return
    for entry in value.split(os.pathsep):
        _register_env_entry(entry)


for _short_name_key, _filename in GAMES.items():
    _register(_short_name_key, str(_GAMES_DIR / _filename))

_register_env_var()
