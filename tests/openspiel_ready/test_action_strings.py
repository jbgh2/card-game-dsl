"""Action RENDERINGS are a function of the action id and the game — not of the
world.

Why this is a partition obligation and not a formatting detail. The proofs in
this package certify that two worlds an observer cannot distinguish yield
byte-identical information states and identical legal-action *ids*. Nothing
downstream consumes ids: `experiments/llm_eval/referee.py` builds every prompt
from `state.action_to_string(player, a)`, so the bytes a model reads are the
RENDERINGS. An id-level guarantee plus a world-sensitive renderer is a leak
with every existing proof still green — the rendering would be an unpoliced
channel sitting between the certified partition and the measured agent.

The obligation splits in two, and this module owns the first half:

- **The renderer cannot read the world** (here). `CardlangState._action_to_string`
  is a pure function of the game path and the action id, pinned two ways: an
  `ast` scrape of what it reads off `self`, and a behavioural differential that
  renders the same ids from states at different points of the same game.
- **The renderings agree wherever the ids do** (the world-pair proofs, which
  assert `action_strings(...)` alongside every legal-action agreement). Those
  assertions are BACKSTOPS shadowing this module's wall: with the renderer pure,
  equal ids give equal strings by construction, so they cannot fail on their own.
  They are stated where the property is claimed so the composition is visible at
  the point of use, and they turn red the moment a world-sensitive renderer ships
  without this module being updated.

Completeness (decisions.md, "Closed-domain completeness")

- **Property.** An action's rendering depends on nothing but the action id and
  the game.
- **Domain.** ONE function, `CardlangState._action_to_string` — the sole
  implementation of `pyspiel.State.action_to_string` for every registered game.
  It is the whole domain because the adapter is general: no game overrides it.
  That the domain is closed is pinned below rather than argued
  (`test_no_game_overrides_the_renderer`).
- **Coverage.** The scrape is total over the function's USES of `self` — every
  occurrence must be an attribute read on the entitled list, so a delegation
  like `helper(self, action)` is rejected rather than passed. It was written
  total over attribute *reads* only, which let exactly that delegation through
  while reporting a clean wall; the distinction is the wall, not a detail of
  it. The differential runs over every registered game (derived from
  `REGISTERED_GAMES`, not listed), rendering each state's full legal set plus a
  fixed spread across the action space, at every step of a short greedy walk.
- **Residual.** The differential walks a bounded prefix, so a renderer that
  couples to the world only in a deep state would pass it — the scrape is what
  covers that case, which is why both are here and neither is sufficient alone.
  Chance-node rendering (`Deal(seed=...)`) is deliberately world-naming and is
  excluded from the differential; it is never shown to an agent, since a chance
  node has no acting player. This ledger owns that record: it is a domain fact
  about the root deal node, not deferred work.

red under (the escape): keep the entitled `self._path` read and delegate —
`return _sneak(self, space, action)` with the helper reading
`state._history_ids`. RUN result: the bare-`self` assertion fires naming the
line, and the differential fails on every registered game. A plant that drops
the attribute read instead trips the non-vacuity guard first, which is a
different assertion and does not exercise this one — worth stating, because
that was the first plant tried and it looked like a pass.

red under (the world read): make `_action_to_string` return
`space.to_string(action) + ('!' if len(self._history_ids) % 2 else '')`. RUN
result, not a prediction — the scrape reddens naming `_history_ids`, the
differential reddens on every registered game, and the adapter-agreement
assertion reddens. The DSL world-pair backstops stay GREEN under that same
mutation, which is the measurement that says they are backstops: they compare
two worlds of one implementation, and the mutation moves both worlds
identically. Their own reddening mutation is necessarily two-part — a
world-sensitive renderer AND `action_strings` threaded with the world — and
the wall above is what stops the one-part version shipping quietly.
"""

from __future__ import annotations

import ast
import inspect
import textwrap

import pytest

pyspiel = pytest.importorskip("pyspiel")

import cardlang.openspiel.game as ogame
from cardlang.openspiel.replay import load

from .harness import GAMES_DIR, REGISTERED_GAMES, action_strings

# What `_action_to_string` may read off `self`. The game it belongs to, and
# nothing that varies within a game — no seed, no history, no replayed state.
ENTITLED_SELF_READS = frozenset({"_path"})

WALK_STEPS = 4


def _renderer() -> ast.FunctionDef:
    source = textwrap.dedent(inspect.getsource(ogame.CardlangState._action_to_string))
    node = ast.parse(source).body[0]
    assert isinstance(node, ast.FunctionDef)
    return node


def test_the_renderer_reads_nothing_of_the_world() -> None:
    """The wall. Every use of `self` in `_action_to_string` must be an entitled
    attribute read — the game, and nothing that varies within one.

    An `ast` scrape rather than a behavioural check, for the reason the purity
    scrapes in the LLM harness give: a run only proves the branches it took,
    while the scrape proves no branch exists that could read the world.

    Stated over USES of `self`, not over attribute reads. Those are different
    checks and the difference is the whole wall: `helper(self, action)` performs
    no attribute read at all, so an attribute-only scrape passes it while the
    helper receives the entire world — seed, history, replayed state. A rendering
    that reaches the world through a callee is exactly as much of a leak channel
    as one that reaches it directly.
    """
    fn = _renderer()
    entitled_reads = {
        id(node.value)
        for node in ast.walk(fn)
        if isinstance(node, ast.Attribute)
        and isinstance(node.value, ast.Name)
        and node.value.id == "self"
        and node.attr in ENTITLED_SELF_READS
    }
    reads = {
        node.attr
        for node in ast.walk(fn)
        if isinstance(node, ast.Attribute)
        and isinstance(node.value, ast.Name)
        and node.value.id == "self"
    }
    escapes = [
        node
        for node in ast.walk(fn)
        if isinstance(node, ast.Name) and node.id == "self" and id(node) not in entitled_reads
    ]
    assert reads, "the scrape found no `self.*` reads — it has stopped checking anything"
    assert reads <= ENTITLED_SELF_READS, (
        f"CardlangState._action_to_string reads {sorted(reads - ENTITLED_SELF_READS)} "
        f"off the state. An action rendering that varies with the world is a leak "
        f"channel the id-level indistinguishability proofs cannot see, because "
        f"they compare ids and the prompt shows strings."
    )
    assert not escapes, (
        f"CardlangState._action_to_string uses bare `self` at line(s) "
        f"{sorted({n.lineno for n in escapes})} — passing the state to a callee "
        f"hands over seed, history and replayed state whatever this scrape says "
        f"about attribute reads. Read the entitled attribute and pass that."
    )


def test_no_game_overrides_the_renderer() -> None:
    """The domain is closed: one adapter, one renderer, every game. If a game
    ever ships its own state class, the scrape above stops being total over the
    corpus and this fails rather than silently under-covering."""
    for short_name, _ in REGISTERED_GAMES:
        state = pyspiel.load_game(short_name).new_initial_state()
        assert type(state)._action_to_string is ogame.CardlangState._action_to_string, (
            f"{short_name} renders actions through its own state class — the "
            f"purity scrape covers only CardlangState"
        )


@pytest.mark.parametrize("short_name,filename", REGISTERED_GAMES)
def test_action_strings_do_not_move_with_the_state(short_name: str, filename: str) -> None:
    """The behavioural half: render a FIXED set of action ids at every step of a
    short greedy walk, and require the rendering never to change.

    Complements the scrape rather than repeating it. The scrape sees direct
    `self` reads; this sees any coupling to the world, however it is reached —
    a module-level cache keyed on the line, a lookup through `load()`, a
    rendering that consults the runtime state.

    The probe ids are the game's own legal sets plus a fixed spread across the
    action space, so the check covers ids the walk never offers as well as the
    ones it does.
    """
    game = pyspiel.load_game(short_name)
    _, space = load(str(GAMES_DIR / filename))
    state = game.new_initial_state()
    assert state.is_chance_node()
    state.apply_action(5)

    n = game.num_distinct_actions()
    probes = sorted({(i * n) // 8 for i in range(8)} | {0, n - 1})
    rendered: dict[int, str] = {}
    steps = 0
    while not state.is_terminal() and steps < WALK_STEPS:
        legal = state.legal_actions()
        player = state.current_player()
        for aid in sorted(set(legal) | set(probes)):
            got = state.action_to_string(player, aid)
            assert rendered.setdefault(aid, got) == got, (
                f"{short_name}: action {aid} rendered {rendered[aid]!r} earlier in "
                f"this game and {got!r} at step {steps} — the rendering moves with "
                f"the state, so two indistinguishable worlds could show an "
                f"observer different action text"
            )
            # And the adapter renders what the DSL-level action space does, so
            # the DSL-level proofs' string backstops speak about the same bytes.
            assert got == action_strings(space, [aid])[0]
        state.apply_action(legal[0])
        steps += 1
    assert rendered, f"{short_name}: the walk rendered nothing"
