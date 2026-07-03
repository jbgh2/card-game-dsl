# OpenSpiel Projection Substrate Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Derive per-player information sets from declared zone visibility + emitted observation events, and prove the six fully-kernel games (Hearts, Getaway, Spades, Bridge, Oh Hell, Big Two) OpenSpiel-ready via a general adapter — replacing the three Hearts-specific hardcodings.

**Architecture:** Two pillars over the kept `(seed, history)` re-simulation engine. Pillar 1: the library-type → projection table becomes data; a new `Ctx.observer` channel (default `None`, zero cost) emits per-observer events from the kernel decision/movement sites; one general `information_state(player, rs, obs_log)` replaces the Hearts one. Pillar 2: a per-game global action universe (cards ∪ move-vocabulary ∪ integer-choose ∪ combinations) derived from the AST plus a new game-local `universe()` engine query, replacing the hardcoded 52-card space. Spec: `docs/superpowers/specs/2026-07-01-openspiel-projection-substrate-design.md`.

**Tech Stack:** Python 3.11, mypy `--strict` (bare `mypy` covers `tests/` too), pytest, `pyspiel` (installed in `.venv`).

## Global Constraints

- **Byte-identical playouts.** Observation emission adds no chooser draws and no RNG. After EVERY task: bare `mypy` clean AND full `PYTHONHASHSEED=0 pytest -q` green (321+ tests). Never push on a partial run.
- **Runtime + adapter only.** No grammar / AST / parser / IR / resolve / typecheck changes. No IR golden regeneration.
- **The `("decision", (actor, choice))` trace event is safe** because every tracer-using test filters by event name (recorded invariant, design note §9 step 2).
- **The eight `instantiate` games are out of scope**; the adapter rejects them loudly.
- **Fail loudly**: no silent fallbacks; unknown zone type / projection / action = raise.
- Commits end with: `Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`
- Working branch: `feat/openspiel-projection-substrate` (already created, stacked on `refactor/unify-decision-round`).

**Key existing facts (verified):**
- `Ctx` is a frozen dataclass in `cardlang/runtime/state.py:205` with `trace()`/`with_local()` etc.; `Chooser = Callable[[Player, list[Any], int], list[Any]]`; `Player = int`.
- `ZoneStore.__init__` (`state.py:~97`) drops `decl.type_ref.name` today.
- The six games' zone types: `Deck`, `Hand<player>`, `TrickPile`, `PlayerPile<player>`, `TeamPile<team>`, `Discard`. Winners: hearts `lowest cumulative_score`, spades `highest score`, oh-hell `highest score`, big-two `lowest score`, bridge `highest total_score` (team-keyed!), getaway is a **loser** game (`loser:` clause, `GameResult.scores` empty).
- Decision sites reaching the six games: `run_decision_round` (mechanics.py:126), `_choose` (evaluate.py:78), `_select` chosen movements (execute.py:156), `_offer` (execute.py:251), `_pass_selection` (execute.py:325).
- Big Two `Play` = frozen dataclass `(kind, size, key, cards)` in `cardlang/runtime/bigtwo.py`; `_combos(hand)` enumerates representatives; `_STRAIGHTS` is the ten rank windows; `_RANK`/`_NAT`/`_SUIT` are the key tables. Universe size = 52+78+52+10200+5108+3744+624+40 = **19,898**.
- `pyspiel.random_sim_test(game, num_sims, serialize, verbose, ...)` exists in the venv.
- `play_game(game, rng, tracer=None, chooser=None)` in `driver.py`; `GameResult(scores, winner, loser, hands_played)`; `ChooserAbort` carries `player`, `legal`, and gets `rs` attached.
- `SUITS = ("clubs","diamonds","hearts","spades")`, `RANKS = ("2",...,"A")` in `values.py`; card id = `SUITS.index(suit)*13 + RANKS.index(rank)` (keep).

---

### Task 1: Projection table as data

**Files:**
- Modify: `cardlang/stdlib/zones.py`
- Test: `tests/test_zone_projections.py` (create)

**Interfaces:**
- Produces: `ZoneVisibility(owner: str, others: str)` frozen dataclass; `ZONE_PROJECTIONS: dict[str, ZoneVisibility]`; `zone_projection(zone_type: str, is_owner: bool) -> str`. Projections used: `"identity" | "count_only" | "trivial"`.

- [ ] **Step 1: Write the failing test**

```python
"""The library-type -> per-observer projection table (decisions.md "Knowledge,
visibility, and the projection model"; library.md "Library zone types")."""

from __future__ import annotations

import pytest

from cardlang.stdlib.zones import (
    LIBRARY_ZONE_TYPES,
    ZONE_PROJECTIONS,
    zone_projection,
)


def test_every_library_type_has_a_projection() -> None:
    assert set(ZONE_PROJECTIONS) == set(LIBRARY_ZONE_TYPES)


def test_hand_is_identity_to_owner_count_to_others() -> None:
    assert zone_projection("Hand", is_owner=True) == "identity"
    assert zone_projection("Hand", is_owner=False) == "count_only"


def test_public_zones_are_identity_to_all() -> None:
    for t in ("PublicHand", "TrickPile", "Discard", "PlayerPile", "TeamPile"):
        assert zone_projection(t, is_owner=False) == "identity"


def test_hidden_and_dead_zones() -> None:
    for t in ("Deck", "FaceDownPile", "ChipStack"):
        assert zone_projection(t, is_owner=False) == "count_only"
    for t in ("Muck", "Burn"):
        assert zone_projection(t, is_owner=True) == "trivial"


def test_unknown_type_fails_loudly() -> None:
    with pytest.raises(KeyError):
        zone_projection("NoSuchZoneType", is_owner=False)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_zone_projections.py -q`
Expected: FAIL — `ImportError: cannot import name 'ZONE_PROJECTIONS'`

- [ ] **Step 3: Implement — append to `cardlang/stdlib/zones.py`**

```python
from dataclasses import dataclass


@dataclass(frozen=True)
class ZoneVisibility:
    """Per-observer projection of a zone's contents (decisions.md "Knowledge,
    visibility, and the projection model"). `owner` applies to the observer the
    zone's index names (the owning player, or a member of the owning team);
    `others` to everyone else. Unowned zones use the same projection for both."""

    owner: str
    others: str


# library type name -> per-observer composition, from library.md "Library zone
# types". The corpus exercises identity / count_only / trivial; the remaining
# lattice levels gain emission rules when a game first uses them.
ZONE_PROJECTIONS: dict[str, ZoneVisibility] = {
    "Deck": ZoneVisibility("count_only", "count_only"),
    "Hand": ZoneVisibility("identity", "count_only"),
    "PublicHand": ZoneVisibility("identity", "identity"),
    "TrickPile": ZoneVisibility("identity", "identity"),
    "Discard": ZoneVisibility("identity", "identity"),
    "Muck": ZoneVisibility("trivial", "trivial"),
    "ChipStack": ZoneVisibility("count_only", "count_only"),
    "PlayerPile": ZoneVisibility("identity", "identity"),
    "TeamPile": ZoneVisibility("identity", "identity"),
    "FaceDownPile": ZoneVisibility("count_only", "count_only"),
    "Burn": ZoneVisibility("trivial", "trivial"),
}


def zone_projection(zone_type: str, is_owner: bool) -> str:
    """The projection an observer gets of a zone of this library type. Raises
    KeyError for an unknown type — a zone with no declared visibility cannot be
    projected, and silently guessing would leak information."""
    vis = ZONE_PROJECTIONS[zone_type]
    return vis.owner if is_owner else vis.others
```

- [ ] **Step 4: Run tests + full gate**

Run: `pytest tests/test_zone_projections.py -q` → PASS (5 passed)
Run: `mypy` → clean; `PYTHONHASHSEED=0 pytest -q` → all green

- [ ] **Step 5: Commit**

```bash
git add cardlang/stdlib/zones.py tests/test_zone_projections.py
git commit -m "feat(stdlib): record the library-type projection table as data"
```

---

### Task 2: ZoneStore retains zone types; Ctx gains the observer channel

**Files:**
- Modify: `cardlang/runtime/state.py` (ZoneStore `__init__`; Ctx dataclass)
- Test: `tests/test_observe.py` (create)

**Interfaces:**
- Produces: `ZoneStore.zone_type: dict[str, str]` (zone name → library type name); `ZoneStore.zone_index: dict[str, str | None]` (zone name → `"player" | "team" | None`); `ZoneStore.locate(zone: Zone) -> tuple[str, Player | None]`; `Ctx.observer: Callable[[Player, tuple[Any, ...]], None] | None = None` (a NEW LAST field of the frozen dataclass) and `Ctx.observe(player, event)` (no-op when observer is None).

- [ ] **Step 1: Write the failing test**

```python
"""The observer channel and zone-type retention (SP1 spec, Pillar 1)."""

from __future__ import annotations

import random
from typing import Any

from cardlang.ast import nodes as n
from cardlang.runtime.state import Ctx, RuntimeState, ZoneStore
from cardlang.runtime.values import Seating


def _store() -> ZoneStore:
    decls = (
        n.ZoneDecl(name="deck", index=None, type_ref=n.TypeRef(name="Deck")),
        n.ZoneDecl(name="hand", index="player", type_ref=n.TypeRef(name="Hand")),
        n.ZoneDecl(name="captured", index="team", type_ref=n.TypeRef(name="TeamPile")),
    )
    return ZoneStore(decls, players=(0, 1, 2, 3), teams=(0, 1))


def test_zone_store_retains_declared_types_and_index() -> None:
    zs = _store()
    assert zs.zone_type == {"deck": "Deck", "hand": "Hand", "captured": "TeamPile"}
    assert zs.zone_index == {"deck": None, "hand": "player", "captured": "team"}


def test_locate_finds_singles_and_family_instances() -> None:
    zs = _store()
    assert zs.locate(zs.single("deck")) == ("deck", None)
    assert zs.locate(zs.instance("hand", 2)) == ("hand", 2)
    assert zs.locate(zs.instance("captured", 1)) == ("captured", 1)


def test_ctx_observer_defaults_to_none_and_observe_is_noop() -> None:
    rs = RuntimeState(Seating(4), _store(), random.Random(0))
    ctx = Ctx(rs=rs, chooser=lambda p, c, k: list(c)[:k])
    ctx.observe(0, ("announce", 1, "pass"))  # must not raise


def test_ctx_observe_delivers_to_installed_observer() -> None:
    rs = RuntimeState(Seating(4), _store(), random.Random(0))
    seen: list[tuple[int, tuple[Any, ...]]] = []
    ctx = Ctx(
        rs=rs,
        chooser=lambda p, c, k: list(c)[:k],
        observer=lambda pl, ev: seen.append((pl, ev)),
    )
    ctx.observe(2, ("chose", "Q spades"))
    assert seen == [(2, ("chose", "Q spades"))]
```

(`Seating` is a dataclass `(count: int, clockwise: bool = True)` — `Seating(4)` and `Seating(2)` are valid.)

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_observe.py -q`
Expected: FAIL — `AttributeError: 'ZoneStore' object has no attribute 'zone_type'`

- [ ] **Step 3: Implement in `cardlang/runtime/state.py`**

In `ZoneStore.__init__`, after the existing loop body, retain the declaration:

```python
        self.singles: dict[str, Zone] = {}
        self.families: dict[str, dict[int, Zone]] = {}
        # The declared library type and index kind per zone, so the observation
        # emitter and info-state builder can look up any zone's projection.
        self.zone_type: dict[str, str] = {}
        self.zone_index: dict[str, str | None] = {}
        for decl in decls:
            self.zone_type[decl.name] = decl.type_ref.name
            self.zone_index[decl.name] = decl.index
            if decl.index is None:
                self.singles[decl.name] = Zone()
            else:
                keys = teams if decl.index == "team" else players
                self.families[decl.name] = {k: Zone() for k in keys}
```

Add to `ZoneStore`:

```python
    def locate(self, zone: Zone) -> "tuple[str, Player | None]":
        """The (name, instance-key) of a zone object — the reverse lookup the
        observation emitter needs when a movement holds only the Zone value."""
        for name, z in self.singles.items():
            if z is zone:
                return name, None
        for name, family in self.families.items():
            for key, z in family.items():
                if z is zone:
                    return name, key
        raise KeyError("zone object is not in this store")
```

Add to `Ctx` (as the LAST field, keeping all existing construction sites valid), plus the method:

```python
    observer: Callable[[Player, tuple[Any, ...]], None] | None = None

    def observe(self, player: Player, event: tuple[Any, ...]) -> None:
        """Deliver a per-observer observation event (the projection substrate).
        No observer installed (normal playouts) means no cost and no effect."""
        if self.observer is not None:
            self.observer(player, event)
```

- [ ] **Step 4: Run tests + full gate**

Run: `pytest tests/test_observe.py -q` → PASS
Run: `mypy` → clean; `PYTHONHASHSEED=0 pytest -q` → all green

- [ ] **Step 5: Commit**

```bash
git add cardlang/runtime/state.py tests/test_observe.py
git commit -m "feat(runtime): ZoneStore retains declared zone types; Ctx.observer channel"
```

---

### Task 3: The observation emitter (`observe.py`)

**Files:**
- Create: `cardlang/runtime/observe.py`
- Test: `tests/test_observe.py` (extend)

**Interfaces:**
- Consumes: `ZONE_PROJECTIONS`/`zone_projection` (Task 1); `Ctx.observe`, `ZoneStore.zone_type/zone_index` (Task 2).
- Produces:
  - `render(value: Any) -> Any` — Card→`str(card)`; `(name, value)` tuple→`"name"`/`"name(value)"`; play-like (has `.cards`)→`"kind[c1,c2,...]"` (cards sorted); `list`/selection→sorted tuple of card strings; int/str pass through.
  - `choice(ctx, actor, value)` — actor-only `("chose", render(value))`.
  - `announce(ctx, actor, value)` — to every player `("announce", actor, render(value))`.
  - `movement(ctx, src: tuple[str, Player | None], dst: tuple[str, Player | None], cards)` — to every player `("move", src_label, src_view, dst_label, dst_view)`; label `"name"`/`"name[key]"`; each view is `tuple[str,...]` (identity), `int` (count_only), or `None` (trivial); event skipped for an observer when both views are `None`.
  - `view_of(rs, zone_name, key, observer, cards) -> tuple[str, ...] | int | None` — shared by the info-state builder (Task 7).

- [ ] **Step 1: Append failing tests to `tests/test_observe.py`**

```python
from cardlang.runtime import observe
from cardlang.runtime.values import Card


def _ctx_with_log() -> tuple[Ctx, dict[int, list[tuple[Any, ...]]]]:
    rs = RuntimeState(Seating(4), _store(), random.Random(0))
    rs.team_of = {0: 0, 1: 1, 2: 0, 3: 1}
    logs: dict[int, list[tuple[Any, ...]]] = {p: [] for p in range(4)}
    ctx = Ctx(
        rs=rs,
        chooser=lambda p, c, k: list(c)[:k],
        observer=lambda pl, ev: logs[pl].append(ev),
    )
    return ctx, logs


def test_render_shapes() -> None:
    assert observe.render(Card("Q", "spades")) == str(Card("Q", "spades"))
    assert observe.render(("bid", None)) == "bid"
    assert observe.render(("bid", "hearts")) == "bid(hearts)"
    assert observe.render(7) == 7
    assert observe.render("pass") == "pass"
    two = [Card("2", "clubs"), Card("A", "spades")]
    assert observe.render(two) == tuple(sorted(str(c) for c in two))


def test_choice_reaches_only_the_actor() -> None:
    ctx, logs = _ctx_with_log()
    observe.choice(ctx, 2, Card("Q", "spades"))
    assert logs[2] == [("chose", str(Card("Q", "spades")))]
    assert logs[0] == logs[1] == logs[3] == []


def test_announce_reaches_everyone() -> None:
    ctx, logs = _ctx_with_log()
    observe.announce(ctx, 1, ("bid", 3))
    for p in range(4):
        assert logs[p] == [("announce", 1, "bid(3)")]


def test_movement_projects_per_observer() -> None:
    ctx, logs = _ctx_with_log()
    cards = [Card("2", "clubs"), Card("9", "hearts")]
    # deck (count_only to all) -> hand[1] (identity to owner, count to others)
    observe.movement(ctx, ("deck", None), ("hand", 1), cards)
    ident = tuple(sorted(str(c) for c in cards))
    assert logs[1] == [("move", "deck", 2, "hand[1]", ident)]
    for p in (0, 2, 3):
        assert logs[p] == [("move", "deck", 2, "hand[1]", 2)]


def test_movement_identity_zone_is_public() -> None:
    ctx, logs = _ctx_with_log()
    card = [Card("Q", "spades")]
    # hand[0] -> captured[1] (TeamPile: identity to all)
    observe.movement(ctx, ("hand", 0), ("captured", 1), card)
    ident = (str(Card("Q", "spades")),)
    assert logs[0] == [("move", "hand[0]", ident, "captured[1]", ident)]
    for p in (1, 2, 3):
        assert logs[p] == [("move", "hand[0]", 1, "captured[1]", ident)]


def test_team_owner_resolution() -> None:
    ctx, _ = _ctx_with_log()
    # captured is team-indexed; player 2 is on team 0.
    assert observe.view_of(ctx.rs, "captured", 0, 2, [Card("2", "clubs")]) == (
        str(Card("2", "clubs")),
    )
```

- [ ] **Step 2: Run to verify failure**

Run: `pytest tests/test_observe.py -q`
Expected: FAIL — `ImportError` / `AttributeError` on `observe`

- [ ] **Step 3: Create `cardlang/runtime/observe.py`**

```python
"""Per-observer observation emission — the projection substrate.

Every event is a plain, deterministic, human-readable tuple. The vocabulary:

  ("chose", <rendered value>)             delivered to the actor only, at the
                                          moment of the chooser draw (perfect
                                          recall of one's own decisions)
  ("announce", actor, <rendered value>)   a public vocabulary decision — a bid,
                                          bet, pass, offer pick, or `choose`
                                          result (state variables are public,
                                          so their decisions are announcements)
  ("move", src_label, src_view, dst_label, dst_view)
                                          what THIS observer learned of a card
                                          transfer through each side's declared
                                          projection: a sorted tuple of card
                                          strings (identity), a count
                                          (count_only), or None (trivial)

Emission is driven by the zone declarations alone (decisions.md "Knowledge,
visibility, and the projection model") — no game names its observers.
"""

from __future__ import annotations

from typing import Any

from cardlang.runtime.state import Ctx, RuntimeState
from cardlang.runtime.values import Card, Player
from cardlang.stdlib.zones import zone_projection


def render(value: Any) -> Any:
    """A deterministic, readable rendering of a decision value."""
    if isinstance(value, Card):
        return str(value)
    if isinstance(value, (list,)):  # a multi-card selection (simultaneous pass)
        return tuple(sorted(str(c) for c in value))
    if isinstance(value, tuple) and len(value) == 2 and isinstance(value[0], str):
        name, param = value  # a (move_type, param) auction/betting candidate
        return name if param is None else f"{name}({param})"
    cards = getattr(value, "cards", None)
    if cards is not None:  # a combination play (climb engines)
        kind = getattr(value, "kind", "combo")
        return f"{kind}[" + ",".join(sorted(str(c) for c in cards)) + "]"
    return value  # int (a choose), str (a move name / "pass")


def choice(ctx: Ctx, actor: Player, value: Any) -> None:
    """The actor observes their own decision at the draw."""
    ctx.observe(actor, ("chose", render(value)))


def announce(ctx: Ctx, actor: Player, value: Any) -> None:
    """A public decision: every player hears (actor, what)."""
    if ctx.observer is None:
        return
    for p in ctx.rs.seating.players:
        ctx.observe(p, ("announce", actor, render(value)))


def _is_owner(rs: RuntimeState, zone_name: str, key: Player | None, observer: Player) -> bool:
    index = rs.zones.zone_index[zone_name]
    if key is None or index is None:
        return False
    if index == "team":
        return rs.team_of.get(observer) == key
    return observer == key


def view_of(
    rs: RuntimeState,
    zone_name: str,
    key: Player | None,
    observer: Player,
    cards: Any,
) -> tuple[str, ...] | int | None:
    """What `observer` sees of `cards` at this zone, per its declared projection."""
    proj = zone_projection(
        rs.zones.zone_type[zone_name], _is_owner(rs, zone_name, key, observer)
    )
    if proj == "identity":
        return tuple(sorted(str(c) for c in cards))
    if proj == "count_only":
        return len(cards)
    if proj == "trivial":
        return None
    raise AssertionError(f"projection '{proj}' has no emission rule yet")


def _label(zone_name: str, key: Player | None) -> str:
    return zone_name if key is None else f"{zone_name}[{key}]"


def movement(
    ctx: Ctx,
    src: tuple[str, Player | None],
    dst: tuple[str, Player | None],
    cards: Any,
) -> None:
    """Emit a card transfer to every observer through both sides' projections
    (decisions.md "Observation events"). Observers for whom both sides are
    trivial learn nothing and get no event."""
    if ctx.observer is None or not cards:
        return
    for p in ctx.rs.seating.players:
        src_view = view_of(ctx.rs, src[0], src[1], p, cards)
        dst_view = view_of(ctx.rs, dst[0], dst[1], p, cards)
        if src_view is None and dst_view is None:
            continue
        ctx.observe(p, ("move", _label(*src), src_view, _label(*dst), dst_view))
```

- [ ] **Step 4: Run tests + full gate**

Run: `pytest tests/test_observe.py -q` → PASS
Run: `mypy` → clean; `PYTHONHASHSEED=0 pytest -q` → all green

- [ ] **Step 5: Commit**

```bash
git add cardlang/runtime/observe.py tests/test_observe.py
git commit -m "feat(runtime): per-observer observation emitter over the projection table"
```

---

### Task 4: Wire emission into the kernel decision/movement sites

**Files:**
- Modify: `cardlang/runtime/mechanics.py` (interpreter + the three forms)
- Modify: `cardlang/runtime/execute.py` (`_movement`, `_deal_round_robin`, `_gather`, `_offer`, `_pass_selection`, `_apply_pass`)
- Modify: `cardlang/runtime/evaluate.py` (`_choose`)
- Test: `tests/test_observe_integration.py` (create)

**Interfaces:**
- Consumes: `observe.choice/announce/movement` (Task 3).
- Produces: with an observer installed, a full Hearts playout yields per-player logs with the event shapes of Task 3; with `observer=None`, byte-identical behavior (full suite green). Also the canonical `ctx.trace("decision", (actor, choice))` now fires in `run_decision_round`.

- [ ] **Step 1: Write the failing integration test**

```python
"""Observation emission across a real playout: per-player logs derived from
zone declarations alone, and no behavior change without an observer."""

from __future__ import annotations

import random
from pathlib import Path
from typing import Any

from cardlang.pipeline import check_source
from cardlang.runtime.driver import play_game

GAMES = Path(__file__).resolve().parent.parent / "docs" / "games"


def _play_with_logs(path: str, seed: int) -> dict[int, list[tuple[Any, ...]]]:
    game = check_source(GAMES / path)
    logs: dict[int, list[tuple[Any, ...]]] = {p: [] for p in range(game.players.low)}
    play_game(
        game,
        random.Random(seed),
        observer=lambda pl, ev: logs[pl].append(ev),
    )
    return logs


def test_hearts_deal_is_private_per_recipient() -> None:
    logs = _play_with_logs("hearts.cardlang", 0)
    for p in range(4):
        deals = [e for e in logs[p] if e[0] == "move" and e[3] == f"hand[{p}]"]
        assert deals, f"player {p} saw no deal into their own hand"
        first = deals[0]
        assert isinstance(first[4], tuple) and len(first[4]) == 13  # own: identity
        other = [
            e for e in logs[p] if e[0] == "move" and e[3] == f"hand[{(p + 1) % 4}]"
        ]
        assert other and other[0][4] == 13  # someone else's deal: a count


def test_hearts_trick_plays_are_public() -> None:
    logs = _play_with_logs("hearts.cardlang", 0)
    for p in range(4):
        to_trick = [e for e in logs[p] if e[0] == "move" and e[3] == "trick_pile"]
        assert to_trick
        # every observer sees each played card at identity (TrickPile: identity to all)
        assert all(isinstance(e[4], tuple) and len(e[4]) == 1 for e in to_trick)


def test_hearts_pass_hides_other_players_picks() -> None:
    logs = _play_with_logs("hearts.cardlang", 0)
    for p in range(4):
        # "chose" events are actor-only by construction; every one in p's log is p's own.
        chose = [e for e in logs[p] if e[0] == "chose"]
        assert chose  # p chose pass cards and trick plays
        # p sees others' hand->hand pass transfers only as counts
        pass_moves = [
            e
            for e in logs[p]
            if e[0] == "move"
            and e[1].startswith("hand[")
            and e[3].startswith("hand[")
            and e[1] != f"hand[{p}]"
            and e[3] != f"hand[{p}]"
        ]
        assert pass_moves and all(
            isinstance(e[2], int) and isinstance(e[4], int) for e in pass_moves
        )


def test_no_observer_changes_nothing() -> None:
    game = check_source(GAMES / "hearts.cardlang")
    a = play_game(game, random.Random(7))
    b_logs: dict[int, list[Any]] = {p: [] for p in range(4)}
    b = play_game(game, random.Random(7), observer=lambda pl, ev: b_logs[pl].append(ev))
    assert a.scores == b.scores and a.winner == b.winner
```

Note: `play_game` does not accept `observer` yet — that parameter is added in Step 3 (it threads into the root `Ctx`). The bigtwo/bridge announce paths get asserted in Task 10's harness; this file pins Hearts's derivations.

- [ ] **Step 2: Run to verify failure**

Run: `pytest tests/test_observe_integration.py -q`
Expected: FAIL — `TypeError: play_game() got an unexpected keyword argument 'observer'`

- [ ] **Step 3: Implement the wiring**

**(a) `driver.py`** — `play_game` gains `observer` (threaded into the root Ctx):

```python
def play_game(
    game: n.Game,
    rng: random.Random,
    tracer: Callable[[str, Any], None] | None = None,
    chooser: Chooser | None = None,
    observer: Callable[[Player, tuple[Any, ...]], None] | None = None,
) -> GameResult:
```

and the Ctx construction becomes:

```python
    ctx = Ctx(rs=rs, chooser=chooser or random_chooser(rng), tracer=tracer, observer=observer)
```

**(b) `mechanics.py`** — add `observe` to the runtime imports (`from cardlang.runtime import observe, phases, rules`), then:

In `run_decision_round`, after the draw:

```python
        choice = ctx.chooser(actor, candidates, 1)[0]  # the single per-step draw
        ctx.trace("decision", (actor, choice))  # the canonical decision event (§4)
        observe.choice(ctx, actor, choice)
        state = form.apply(actor, choice, state, ctx)
```

In `TrickForm.apply`, after the two zone mutations:

```python
        ctx.rs.zones.instance(self.source_family, actor).remove(choice)
        ctx.rs.zones.single(self.play_zone).add(choice)
        observe.movement(ctx, (self.source_family, actor), (self.play_zone, None), [choice])
```

In `AuctionForm.apply`, first line (the announcement precedes the effect's own movements):

```python
    def apply(self, actor: Player, choice: Any, state: State, ctx: Ctx) -> State:
        from cardlang.runtime.execute import run_body

        observe.announce(ctx, actor, choice)
        name, value = choice
```

In `ClimbForm.__init__`, retain the zone names next to the existing lookups:

```python
        self.source_name: str = stmt.source_zone
        self.pile_name: str = stmt.play_zone
```

In `ClimbForm.apply`:

```python
    def apply(self, actor: Player, choice: Any, state: State, ctx: Ctx) -> State:
        if choice == "pass":
            observe.announce(ctx, actor, "pass")
            state["idx"] += 1
            return state
        play = choice
        for c in play.cards:
            self.hands[actor].remove(c)
        self.pile.add_all(play.cards)
        observe.movement(ctx, (self.source_name, actor), (self.pile_name, None), play.cards)
```

**(c) `execute.py`** — import `observe` (`from cardlang.runtime import mechanics, observe`), then:

`_movement`, `dest_each` per-player branch:

```python
            for player in ctx.rs.seating.players:
                cards = _select(source, stmt, ctx, player)
                ctx.rs.zones.instance(stmt.dest.name, player).add_all(cards)
                if ctx.observer is not None:
                    observe.movement(
                        ctx, ctx.rs.zones.locate(source), (stmt.dest.name, player), cards
                    )
```

`_movement`, plain branch:

```python
        selected = _select(source, stmt, ctx, player)
        dest.add_all(selected)
        if ctx.observer is not None:
            observe.movement(
                ctx, ctx.rs.zones.locate(source), ctx.rs.zones.locate(dest), selected
            )
```

`_deal_round_robin` (collect per recipient, then emit):

```python
def _deal_round_robin(source: Zone, dest_family: str, ctx: Ctx) -> None:
    """Deal the source one card at a time around the players, so an indivisible
    deck is spread as equally as possible (the first players get the remainder)."""
    players = list(ctx.rs.seating.players)
    dealt: dict[Player, list[Card]] = {p: [] for p in players}
    i = 0
    while source.cards:
        card = source.cards.pop(0)
        ctx.rs.zones.instance(dest_family, players[i % len(players)]).add(card)
        dealt[players[i % len(players)]].append(card)
        i += 1
    if ctx.observer is not None:
        src = ctx.rs.zones.locate(source)
        for p in players:
            observe.movement(ctx, src, (dest_family, p), dealt[p])
```

`_gather` (one event per non-empty source zone):

```python
    for name, zone in zones.singles.items():
        if zone is not dest:
            taken = zone.take_all()
            if ctx.observer is not None:
                observe.movement(ctx, (name, None), zones.locate(dest), taken)
            dest.add_all(taken)
    for fname, family in zones.families.items():
        for key, zone in family.items():
            taken = zone.take_all()
            if ctx.observer is not None:
                observe.movement(ctx, (fname, key), zones.locate(dest), taken)
            dest.add_all(taken)
```

(`observe.movement` already skips empty card lists.)

`_offer`, after the draw:

```python
    chosen = ctx.chooser(player, legal, 1)[0]
    observe.choice(ctx, player, chosen)
    observe.announce(ctx, player, chosen)
    run_body(ctx.rs.move_type_index[chosen].effect, pctx)
```

`_pass_selection`, capture and emit before returning:

```python
    actor = ctx.require_actor("a simultaneous-pass selection")
    chosen = ctx.chooser(actor, list(source.cards), count)
    observe.choice(ctx, actor, chosen)
    return chosen
```

`_apply_pass`, after the transfer loop:

```python
    for card in selections[player]:
        source.remove(card)
        dest.add(card)
    if ctx.observer is not None:
        observe.movement(
            ctx, ctx.rs.zones.locate(source), ctx.rs.zones.locate(dest), selections[player]
        )
```

**(d) `evaluate.py`** — `_choose`, after the draw (import observe lazily inside the function to avoid a module cycle if one appears; try the top-level import first):

```python
    value = ctx.chooser(ctx.require_actor("a `choose`"), candidates, 1)[0]
    from cardlang.runtime import observe

    actor = ctx.require_actor("a `choose`")
    observe.choice(ctx, actor, value)
    observe.announce(ctx, actor, value)
    return value
```

(Refactor so `require_actor` is called once and reused.)

- [ ] **Step 4: Run tests + full gate**

Run: `pytest tests/test_observe_integration.py -q` → PASS
Run: `mypy` → clean; `PYTHONHASHSEED=0 pytest -q` → **all green — this is the byte-identity gate for the whole wiring.**

- [ ] **Step 5: Commit**

```bash
git add cardlang/runtime/mechanics.py cardlang/runtime/execute.py cardlang/runtime/evaluate.py cardlang/runtime/driver.py tests/test_observe_integration.py
git commit -m "feat(runtime): emit derived per-observer observations from every kernel decision site"
```

---

### Task 5: The Big Two combination universe

**Files:**
- Modify: `cardlang/runtime/bigtwo.py` (add `bigtwo_universe`)
- Modify: `cardlang/runtime/stdlib.py` (add `climb_universe_function`)
- Test: `tests/test_bigtwo_universe.py` (create)
- Create: `tests/golden/bigtwo_universe_count.json` (pinned in Step 4)

**Interfaces:**
- Produces: `bigtwo_universe() -> list[Play]` — every play the engine can ever emit, unique by card-set, deterministic order; `stdlib.climb_universe_function(name: str) -> Callable[[], list[Any]]` keyed by the SAME name as the `combinations` query (`"bigtwo_lead_options"`).

- [ ] **Step 1: Write the failing test**

```python
"""The Big Two play universe: a superset of every reachable representative,
unique by card-set — the combination action space (SP1 spec, Pillar 2)."""

from __future__ import annotations

import json
import random
from pathlib import Path

from cardlang.runtime.bigtwo import _combos, bigtwo_universe
from cardlang.runtime.stdlib import climb_universe_function
from cardlang.runtime.values import RANKS, SUITS, Card

GOLDEN = Path(__file__).resolve().parent / "golden" / "bigtwo_universe_count.json"


def test_universe_size_is_pinned_and_card_sets_unique() -> None:
    plays = bigtwo_universe()
    sets = {frozenset(p.cards) for p in plays}
    assert len(sets) == len(plays)  # card-set decodes to exactly one play
    expected = json.loads(GOLDEN.read_text())["count"]
    assert len(plays) == expected


def test_universe_composition_by_kind() -> None:
    plays = bigtwo_universe()
    by_kind: dict[str, int] = {}
    for p in plays:
        by_kind[p.kind] = by_kind.get(p.kind, 0) + 1
    assert by_kind["single"] == 52
    assert by_kind["pair"] == 13 * 6
    assert by_kind["triple"] == 13 * 4
    assert by_kind["straightflush"] == 10 * 4
    assert by_kind["straight"] == 10 * (4**5 - 4)
    assert by_kind["flush"] == 4 * (1287 - 10)
    assert by_kind["fullhouse"] == 13 * 12 * 4 * 6
    assert by_kind["quads"] == 13 * 48


def test_universe_covers_every_reachable_representative() -> None:
    universe = {frozenset(p.cards): p.kind for p in bigtwo_universe()}
    deck = [Card(r, s) for s in SUITS for r in RANKS]
    rng = random.Random(0)
    for _ in range(300):
        hand = rng.sample(deck, 13)
        for play in _combos(hand):
            key = frozenset(play.cards)
            assert key in universe, f"unreachable in universe: {play}"
            assert universe[key] == play.kind


def test_stdlib_registry_resolves_by_combos_query_name() -> None:
    fn = climb_universe_function("bigtwo_lead_options")
    assert len(fn()) == len(bigtwo_universe())
```

- [ ] **Step 2: Create the golden with the analytic count, run to verify the right failure**

```bash
mkdir -p tests/golden && echo '{"count": 19898}' > tests/golden/bigtwo_universe_count.json
pytest tests/test_bigtwo_universe.py -q
```

Expected: FAIL — `ImportError: cannot import name 'bigtwo_universe'`
(19,898 = 52 singles + 78 pairs + 52 triples + 10,200 straights + 5,108 flushes + 3,744 full houses + 624 quads + 40 straight flushes. If the enumerator below disagrees, STOP and reconcile the arithmetic against `_five_card_combos` — do not adjust the golden to match blindly.)

- [ ] **Step 3: Implement**

Append to `cardlang/runtime/bigtwo.py` (after `first_leader_seat`):

```python
def bigtwo_universe() -> list[Play]:
    """Every play this engine can ever produce over any hand — the combination
    action universe for the OpenSpiel adapter (a stable superset of the
    reachable representatives; supersets are safe, collisions are not, so the
    one invariant is that each card-set appears at most once).

    Enumerates by shape, mirroring `_combos` / `_five_card_combos` exactly:
    representatives take the top suits *present in the hand*, so over all hands
    every suit subset is reachable — pairs are all C(4,2) per rank, triples all
    C(4,3), a straight is any non-monochrome suit assignment over its window
    (monochrome is a straight flush), a flush any 5-of-a-suit whose ranks are
    not a straight window, a quad takes any of the 48 spare cards as kicker.
    """
    import itertools

    suits_desc = sorted(_SUIT, key=lambda s: _SUIT[s], reverse=True)
    out: list[Play] = []

    for r in _RANK:
        for s in suits_desc:
            out.append(Play("single", 1, (_RANK[r], _SUIT[s]), (Card(r, s),)))
    for r in _RANK:
        for s1, s2 in itertools.combinations(suits_desc, 2):
            out.append(Play("pair", 2, (_RANK[r], _SUIT[s1]), (Card(r, s1), Card(r, s2))))
        for suits3 in itertools.combinations(suits_desc, 3):
            out.append(Play("triple", 3, (_RANK[r],), tuple(Card(r, s) for s in suits3)))

    for seq in _STRAIGHTS:
        top_nat = _NAT[seq[-1]]
        for suit in suits_desc:  # monochrome: the straight flushes
            cards = tuple(Card(r, suit) for r in seq)
            out.append(Play("straightflush", 5, (_STRAIGHTFLUSH, top_nat, _SUIT[suit]), cards))
        for assignment in itertools.product(suits_desc, repeat=5):
            if len(set(assignment)) == 1:
                continue  # monochrome emitted above as a straight flush
            cards = tuple(Card(r, s) for r, s in zip(seq, assignment))
            out.append(Play("straight", 5, (_STRAIGHT, top_nat, _SUIT[assignment[-1]]), cards))

    for suit in suits_desc:
        for ranks in itertools.combinations(_RANK, 5):
            if _is_straight_ranks(frozenset(ranks)):
                continue  # that card-set is a straight flush
            ordered = sorted(ranks, key=lambda r: _RANK[r], reverse=True)
            cards = tuple(Card(r, suit) for r in ordered)
            out.append(Play("flush", 5, (_FLUSH, _SUIT[suit], _RANK[ordered[0]]), cards))

    for tr in _RANK:
        for pr in _RANK:
            if pr == tr:
                continue
            for ts in itertools.combinations(suits_desc, 3):
                for ps in itertools.combinations(suits_desc, 2):
                    cards = tuple(
                        [Card(tr, s) for s in ts] + [Card(pr, s) for s in ps]
                    )
                    out.append(Play("fullhouse", 5, (_FULLHOUSE, _RANK[tr]), cards))

    for r in _RANK:
        four = tuple(Card(r, s) for s in suits_desc)
        for kr in _RANK:
            if kr == r:
                continue
            for ks in suits_desc:
                out.append(Play("quads", 5, (_QUADS, _RANK[r]), four + (Card(kr, ks),)))
    return out
```

Append to `cardlang/runtime/stdlib.py` (beside `climb_follow_function`):

```python
def climb_universe_function(name: str) -> Callable[[], list[Any]]:
    """The engine's full play universe — every combination it can ever emit —
    keyed by the SAME name as its `combinations` lead query. The OpenSpiel
    adapter derives the climb action space from this; the lead query itself
    cannot serve (its representatives depend on the live hand and game state)."""
    match name:
        case "bigtwo_lead_options":
            from cardlang.runtime.bigtwo import bigtwo_universe

            return bigtwo_universe
        case _:
            raise AssertionError(f"no combination universe for climb engine '{name}'")
```

- [ ] **Step 4: Run tests + full gate**

Run: `pytest tests/test_bigtwo_universe.py -q` → PASS (4 passed; the coverage test is the load-bearing one)
Run: `mypy` → clean; `PYTHONHASHSEED=0 pytest -q` → all green

- [ ] **Step 5: Commit**

```bash
git add cardlang/runtime/bigtwo.py cardlang/runtime/stdlib.py tests/test_bigtwo_universe.py tests/golden/bigtwo_universe_count.json
git commit -m "feat(bigtwo): enumerate the full play universe for the combination action space"
```

---

### Task 6: The derived per-game ActionSpace

**Files:**
- Rewrite: `cardlang/openspiel/encoding.py` (keep `card_to_action` / `action_to_card` / `NUM_DISTINCT_ACTIONS` — `tests/test_openspiel_encoding.py` pins them)
- Modify: `cardlang/runtime/mechanics.py` (rename `_enumerate_domain(type_name, ctx)` → `enumerate_domain(type_name)`; drop the unused `ctx` param; update its two call sites in `AuctionForm.candidates`)
- Test: `tests/test_openspiel_encoding.py` (extend)

**Interfaces:**
- Consumes: `climb_universe_function` (Task 5); `n.Game` ASTs via `check_source`.
- Produces:
  ```python
  @dataclass(frozen=True)
  class ComboAction:
      cards: frozenset[Card]

  class ActionSpace:
      num_distinct_actions: int
      @staticmethod
      def for_game(game: n.Game) -> "ActionSpace"
      def encode(self, value: Any) -> int          # Card | int | str | (name, param) | play-like
      def decode(self, aid: int) -> Any            # Card | int | str | tuple | ComboAction
      def match(self, aid: int, pool: list[Any]) -> Any   # the candidate `decode(aid)` denotes
      def to_string(self, aid: int) -> str
  ```
  Layout: `[0,52)` cards (always); then names (offer move-types + `"pass"` if any climb round, sorted); then integers `0..52` if any `Choose` node; then auction vocabulary in declared round order (`(name, None)` or `(name, value)` over `enumerate_domain`); then the combination universe sorted by `(size, kind, sorted card ids)`.

- [ ] **Step 1: Append failing tests to `tests/test_openspiel_encoding.py`**

```python
from pathlib import Path

from cardlang.openspiel.encoding import ActionSpace, ComboAction
from cardlang.pipeline import check_source

GAMES = Path(__file__).resolve().parent.parent / "docs" / "games"


def _space(path: str) -> ActionSpace:
    return ActionSpace.for_game(check_source(GAMES / path))


def test_hearts_space_is_cards_only() -> None:
    assert _space("hearts.cardlang").num_distinct_actions == 52


def test_spades_space_adds_the_integer_block() -> None:
    space = _space("spades.cardlang")
    assert space.num_distinct_actions == 52 + 53
    assert space.decode(space.encode(7)) == 7
    assert space.to_string(space.encode(7)) == "7"


def test_bridge_space_adds_the_auction_vocabulary() -> None:
    space = _space("bridge.cardlang")
    # pass, submit_bid over Suit? (clubs, diamonds, hearts, spades, none), double, redouble
    assert space.num_distinct_actions == 52 + 8
    aid = space.encode(("submit_bid", "hearts"))
    assert space.decode(aid) == ("submit_bid", "hearts")
    assert space.to_string(aid) == "submit_bid(hearts)"
    assert space.decode(space.encode(("pass", None))) == ("pass", None)


def test_bigtwo_space_adds_pass_and_the_combo_universe() -> None:
    space = _space("big-two.cardlang")
    assert space.num_distinct_actions == 52 + 1 + 19898
    aid = space.encode("pass")
    assert space.decode(aid) == "pass"


def test_combo_round_trip_and_match() -> None:
    from cardlang.runtime.bigtwo import bigtwo_universe

    space = _space("big-two.cardlang")
    play = next(p for p in bigtwo_universe() if p.kind == "fullhouse")
    aid = space.encode(play)
    decoded = space.decode(aid)
    assert isinstance(decoded, ComboAction)
    assert decoded.cards == frozenset(play.cards)
    assert space.match(aid, [play, "pass"]) is play
    assert space.to_string(aid).startswith("fullhouse[")


def test_encode_rejects_out_of_space_values() -> None:
    import pytest

    space = _space("hearts.cardlang")
    with pytest.raises((KeyError, AssertionError, ValueError)):
        space.encode(("submit_bid", "hearts"))  # hearts has no vocabulary
```

- [ ] **Step 2: Run to verify failure**

Run: `pytest tests/test_openspiel_encoding.py -q`
Expected: the two old tests PASS; the new ones FAIL with `ImportError: cannot import name 'ActionSpace'`

- [ ] **Step 3: Implement**

In `mechanics.py`, rename and simplify (the `ctx` param was never used):

```python
def enumerate_domain(type_name: str) -> list[Any]:
    """The value-domain a parameterized move ranges over, in a fixed order so the
    flattened candidate list is deterministic. `Suit` is the deck's suits;
    `Suit?` appends `none` (the no-trump strain), which ranks last."""
    base = type_name.rstrip("?")
    if base == "Suit":
        values: list[Any] = list(SUITS)
        if type_name.endswith("?"):
            values.append(None)
        return values
    raise NotImplementedError(f"move parameter domain '{type_name}' not supported yet")
```

and in `AuctionForm.candidates` replace both `_enumerate_domain(mt.param.type_name, ctx)` with `enumerate_domain(mt.param.type_name)`.

Rewrite `cardlang/openspiel/encoding.py` (keeping the three existing card primitives verbatim at the top):

```python
"""Derived per-game action encoding.

Every decision a kernel game can pose maps to a stable global action id — the
same id means the same action in every world, which is what makes determinized
replay sound (SP1 spec, Pillar 2). The space is the disjoint union, in a fixed
layout, of: the 52 cards (always); bare-name actions (offer move-types, the
climb "pass"); the integer block 0..52 (games with `choose`); the auction
vocabulary (moves flattened over their parameter domains, declared order); and
the combination universe (the climb engine's `universe()` query, canonically
ordered and golden-pinned).
"""

from __future__ import annotations

import dataclasses
from dataclasses import dataclass
from typing import Any, Iterator

from cardlang.ast import nodes as n
from cardlang.runtime.mechanics import enumerate_domain
from cardlang.runtime.values import RANKS, SUITS, Card

NUM_DISTINCT_ACTIONS = len(SUITS) * len(RANKS)  # 52 — the card block


def card_to_action(card: Card) -> int:
    return SUITS.index(card.suit) * len(RANKS) + RANKS.index(card.rank)


def action_to_card(action: int) -> Card:
    if not 0 <= action < NUM_DISTINCT_ACTIONS:
        raise ValueError(f"action {action} out of range 0..{NUM_DISTINCT_ACTIONS - 1}")
    return Card(RANKS[action % len(RANKS)], SUITS[action // len(RANKS)])


_MAX_CHOOSE = 52  # integer chooses are bounded by the deck size in a card game


@dataclass(frozen=True)
class ComboAction:
    """A decoded combination action: the card-set it moves. Matched against
    engine plays by card-set (each set denotes exactly one play — a pinned
    invariant of the universe)."""

    cards: frozenset[Card]


def _walk(node: Any) -> Iterator[Any]:
    """Every dataclass node reachable from `node` (AST nodes hold only
    dataclasses, tuples, and leaves)."""
    if dataclasses.is_dataclass(node) and not isinstance(node, type):
        yield node
        for f in dataclasses.fields(node):
            yield from _walk(getattr(node, f.name))
    elif isinstance(node, tuple):
        for item in node:
            yield from _walk(item)


class ActionSpace:
    """The derived global action universe of one game."""

    def __init__(
        self,
        names: list[str],
        vocab: list[tuple[str, Any]],
        has_integers: bool,
        combos: list[Any],
    ) -> None:
        self._names = names
        self._vocab = vocab
        self._has_integers = has_integers
        self._combos = combos
        self._name_base = NUM_DISTINCT_ACTIONS
        self._int_base = self._name_base + len(names)
        self._vocab_base = self._int_base + (_MAX_CHOOSE + 1 if has_integers else 0)
        self._combo_base = self._vocab_base + len(vocab)
        self.num_distinct_actions = self._combo_base + len(combos)
        self._name_ids = {v: i for i, v in enumerate(names)}
        self._vocab_ids = {v: i for i, v in enumerate(vocab)}
        self._combo_ids = {frozenset(p.cards): i for i, p in enumerate(combos)}
        assert len(self._combo_ids) == len(combos), "combo card-sets must be unique"

    @staticmethod
    def for_game(game: n.Game) -> "ActionSpace":
        from cardlang.runtime import stdlib

        names: list[str] = []
        vocab: list[tuple[str, Any]] = []
        has_integers = False
        combos: list[Any] = []
        mt_index = {m.name: m for m in game.move_types}
        climb_engines: list[str] = []
        for node in _walk(game):
            if isinstance(node, n.Choose):
                has_integers = True
            elif isinstance(node, n.Offer):
                names.extend(m for m in node.move_types if m not in names)
            elif isinstance(node, n.Round) and node.combos_fn is not None:
                if node.combos_fn not in climb_engines:
                    climb_engines.append(node.combos_fn)
            elif isinstance(node, n.Round) and node.move_types is not None:
                for mt_name in node.move_types:
                    mt = mt_index[mt_name]
                    entries = (
                        [(mt.name, None)]
                        if mt.param is None
                        else [(mt.name, v) for v in enumerate_domain(mt.param.type_name)]
                    )
                    vocab.extend(e for e in entries if e not in vocab)
        if climb_engines:
            assert len(climb_engines) == 1, "one climb engine per game for now"
            if "pass" not in names:
                names.append("pass")
            universe = stdlib.climb_universe_function(climb_engines[0])()
            combos = sorted(
                universe,
                key=lambda p: (p.size, p.kind, sorted(card_to_action(c) for c in p.cards)),
            )
        return ActionSpace(sorted(names), vocab, has_integers, combos)

    def encode(self, value: Any) -> int:
        if isinstance(value, Card):
            return card_to_action(value)
        if isinstance(value, bool):
            raise ValueError("boolean is not an action value")
        if isinstance(value, int):
            assert self._has_integers, "this game has no integer decisions"
            assert 0 <= value <= _MAX_CHOOSE, f"choose value {value} out of 0..{_MAX_CHOOSE}"
            return self._int_base + value
        if isinstance(value, str):
            return self._name_base + self._name_ids[value]
        if isinstance(value, tuple):
            return self._vocab_base + self._vocab_ids[value]
        cards = getattr(value, "cards", None)
        if cards is not None:
            return self._combo_base + self._combo_ids[frozenset(cards)]
        raise ValueError(f"cannot encode action value {value!r}")

    def decode(self, aid: int) -> Any:
        if 0 <= aid < NUM_DISTINCT_ACTIONS:
            return action_to_card(aid)
        if self._name_base <= aid < self._int_base:
            return self._names[aid - self._name_base]
        if self._int_base <= aid < self._vocab_base:
            return aid - self._int_base
        if self._vocab_base <= aid < self._combo_base:
            return self._vocab[aid - self._vocab_base]
        if self._combo_base <= aid < self.num_distinct_actions:
            return ComboAction(frozenset(self._combos[aid - self._combo_base].cards))
        raise ValueError(f"action {aid} out of range 0..{self.num_distinct_actions - 1}")

    def match(self, aid: int, pool: list[Any]) -> Any:
        """The candidate in `pool` that `aid` denotes (a recorded action must be
        among the live candidates — anything else is a corrupted history)."""
        value = self.decode(aid)
        if isinstance(value, ComboAction):
            return next(
                c
                for c in pool
                if getattr(c, "cards", None) is not None
                and frozenset(c.cards) == value.cards
            )
        return next(c for c in pool if c == value)

    def to_string(self, aid: int) -> str:
        value = self.decode(aid)
        if isinstance(value, Card):
            return str(value)
        if isinstance(value, ComboAction):
            play = self._combos[aid - self._combo_base]
            return f"{play.kind}[" + ",".join(sorted(str(c) for c in play.cards)) + "]"
        if isinstance(value, tuple):
            name, param = value
            return name if param is None else f"{name}({param})"
        return str(value)
```

- [ ] **Step 4: Run tests + full gate**

Run: `pytest tests/test_openspiel_encoding.py tests/test_bigtwo_universe.py -q` → PASS
Run: `mypy` → clean; `PYTHONHASHSEED=0 pytest -q` → all green (the `enumerate_domain` rename is exercised by every auction playout test)

- [ ] **Step 5: Commit**

```bash
git add cardlang/openspiel/encoding.py cardlang/runtime/mechanics.py tests/test_openspiel_encoding.py
git commit -m "feat(openspiel): derive the per-game global action space from the AST"
```

---

### Task 7: The general information state

**Files:**
- Rewrite: `cardlang/openspiel/infostate.py`
- Test: `tests/test_openspiel_infostate.py` (create)

**Interfaces:**
- Consumes: `observe.view_of` (Task 3), `ZoneStore.zone_type` (Task 2).
- Produces: `information_state(player: int, rs: RuntimeState, obs_log: list[tuple[Any, ...]]) -> str` — the player's projected zones + all public state variables + their observation log. Deterministic; human/LLM-readable.

- [ ] **Step 1: Write the failing test**

```python
"""The general info-state: projected zones + public state + the observation log
(derived; game-agnostic). Replaces the Hearts-specific encoding."""

from __future__ import annotations

import random
from typing import Any

from cardlang.ast import nodes as n
from cardlang.openspiel.infostate import information_state
from cardlang.runtime.state import RuntimeState, ZoneStore
from cardlang.runtime.values import Card, Seating


def _rs() -> RuntimeState:
    decls = (
        n.ZoneDecl(name="deck", index=None, type_ref=n.TypeRef(name="Deck")),
        n.ZoneDecl(name="hand", index="player", type_ref=n.TypeRef(name="Hand")),
        n.ZoneDecl(name="trick_pile", index=None, type_ref=n.TypeRef(name="TrickPile")),
    )
    rs = RuntimeState(Seating(2), ZoneStore(decls, players=(0, 1)), random.Random(0))
    rs.zones.instance("hand", 0).add(Card("Q", "spades"))
    rs.zones.instance("hand", 1).add(Card("2", "clubs"))
    rs.zones.single("trick_pile").add(Card("7", "hearts"))
    rs.push_frame()
    rs.declare("score", indexed=False, value={0: 10, 1: 20})
    return rs


def test_own_hand_at_identity_other_hand_as_count() -> None:
    s = information_state(0, _rs(), [])
    assert str(Card("Q", "spades")) in s        # own hand: identity
    assert str(Card("2", "clubs")) not in s     # opponent's hand: hidden
    assert str(Card("7", "hearts")) in s        # public pile: identity


def test_state_variables_are_public() -> None:
    s0 = information_state(0, _rs(), [])
    s1 = information_state(1, _rs(), [])
    assert "score" in s0 and "10" in s0 and "20" in s0
    assert "score" in s1 and "10" in s1 and "20" in s1


def test_observation_log_is_included_and_ordered() -> None:
    log: list[tuple[Any, ...]] = [("announce", 1, "bid(3)"), ("chose", "7 of hearts")]
    s = information_state(0, _rs(), log)
    assert "bid(3)" in s
    assert s.index("bid(3)") < s.index("chose")  # log order preserved


def test_deterministic_across_dict_insertion_orders() -> None:
    a, b = _rs(), _rs()
    b.set("score", {1: 20, 0: 10})  # same mapping, different insertion order
    assert information_state(0, a, []) == information_state(0, b, [])
```

- [ ] **Step 2: Run to verify failure**

Run: `pytest tests/test_openspiel_infostate.py -q`
Expected: FAIL — `ImportError: cannot import name 'information_state'`

- [ ] **Step 3: Rewrite `cardlang/openspiel/infostate.py`**

```python
"""The general information state (perfect recall, per player) — derived, not
hand-authored.

A player's information state is a pure function of (a) their projected view of
every zone through its declared library-type visibility, (b) the declared
state variables — public by convention: hidden information lives only in
zones (SP1 spec, "State variables are public"), and (c) their accumulated
per-observer observation log (perfect recall; a `Muck`'s contents are trivial
going forward while prior observations persist in the log). The string is
deterministic and human-readable — it doubles as the designer/LLM feed.
"""

from __future__ import annotations

from typing import Any

from cardlang.runtime.observe import view_of
from cardlang.runtime.state import RuntimeState


def _render(value: Any) -> str:
    if isinstance(value, dict):
        items = sorted(value.items(), key=lambda kv: repr(kv[0]))
        return "{" + ",".join(f"{k}:{_render(v)}" for k, v in items) + "}"
    if isinstance(value, (list, tuple, set, frozenset)):
        return "[" + ",".join(sorted(_render(v) for v in value)) + "]"
    return str(value)


def _zone_line(rs: RuntimeState, name: str, key: Any, player: int) -> str:
    zone = rs.zones.single(name) if key is None else rs.zones.instance(name, key)
    view = view_of(rs, name, key, player, zone.cards)
    label = name if key is None else f"{name}[{key}]"
    if view is None:
        return f"{label}=?"
    if isinstance(view, int):
        return f"{label}=#{view}"
    return f"{label}=[" + ",".join(view) + "]"


def information_state(
    player: int, rs: RuntimeState, obs_log: list[tuple[Any, ...]]
) -> str:
    zones = [
        _zone_line(rs, name, None, player) for name in sorted(rs.zones.singles)
    ] + [
        _zone_line(rs, name, key, player)
        for name in sorted(rs.zones.families)
        for key in sorted(rs.zones.families[name])
    ]
    merged: dict[str, Any] = {}
    for frame in rs.frames:  # later frames shadow earlier (phase-local over game)
        merged.update(frame)
    state_vars = ";".join(f"{k}={_render(v)}" for k, v in sorted(merged.items()))
    obs = ";".join(repr(e) for e in obs_log)
    return f"P{player}|" + ";".join(zones) + f"|state:{state_vars}|obs:{obs}"
```

- [ ] **Step 4: Run tests + full gate**

Run: `pytest tests/test_openspiel_infostate.py -q` → PASS
(The old `hearts_information_state` is still imported by `game.py`/tests — keep it in place until Task 9 removes the last consumer, then delete it there.)
Run: `mypy` → clean; `PYTHONHASHSEED=0 pytest -q` → all green

- [ ] **Step 5: Commit**

```bash
git add cardlang/openspiel/infostate.py tests/test_openspiel_infostate.py
git commit -m "feat(openspiel): general derived information state"
```

---

### Task 8: Generalize the replay engine

**Files:**
- Rewrite: `cardlang/openspiel/replay.py`
- Modify: `cardlang/runtime/driver.py` (add `on_first_decision` hook)
- Rewrite test: `tests/test_openspiel_replay.py`

**Interfaces:**
- Consumes: `ActionSpace` (Task 6), `observer` param on `play_game` (Task 4).
- Produces:
  ```python
  def load(path_str: str) -> tuple[n.Game, ActionSpace]        # lru_cached per path
  @dataclass class Pause:   player: int; legal: list[int]; rs: RuntimeState; obs_logs: dict[int, list[tuple[Any, ...]]]
  @dataclass class Terminal: returns: list[float]
  def run(path_str: str, seed: int, history: tuple[int, ...],
          on_first_decision: Callable[[RuntimeState], None] | None = None) -> Pause | Terminal
  def returns_for(game: n.Game, result: GameResult) -> list[float]
  ```
  `play_game` gains `on_first_decision: Callable[[RuntimeState], None] | None = None` — fired once, inside the first chooser call, before delegating (the deal-injection seam; a test fixture hook, not a language feature).
  Returns rule: winner games → `sign * score_per_player` (sign −1 for `lowest`), team-keyed scores mapped through `game.partnerships`; loser games → loser `-(n-1)`, everyone else `+1`.

- [ ] **Step 1: Rewrite `tests/test_openspiel_replay.py` as the failing spec**

```python
"""The generalized re-sim engine: replaying recorded actions reproduces a
reference game exactly, for every fully-kernel game; an exhausted history
surfaces the next decision as a Pause with per-player observation logs."""

from __future__ import annotations

import random
from pathlib import Path
from typing import Any

import pytest

from cardlang.openspiel.replay import Pause, Terminal, load, returns_for, run
from cardlang.runtime.driver import play_game

GAMES = Path(__file__).resolve().parent.parent / "docs" / "games"
HEARTS = str(GAMES / "hearts.cardlang")
BIGTWO = str(GAMES / "big-two.cardlang")
SIX = [
    "hearts.cardlang",
    "getaway.cardlang",
    "spades.cardlang",
    "bridge.cardlang",
    "oh-hell.cardlang",
    "big-two.cardlang",
]


def _record(path: str, seed: int, policy_seed: int) -> tuple[list[int], list[float]]:
    game, space = load(path)
    policy = random.Random(policy_seed)
    recorded: list[int] = []

    def recording(player: int, candidates: list[Any], n: int) -> list[Any]:
        chosen = policy.sample(list(candidates), n)
        recorded.extend(space.encode(c) for c in chosen)
        return chosen

    result = play_game(game, random.Random(seed), chooser=recording)
    return recorded, returns_for(game, result)


@pytest.mark.parametrize("name", SIX)
def test_replay_reproduces_a_reference_game(name: str) -> None:
    path = str(GAMES / name)
    recorded, native = _record(path, seed=1, policy_seed=101)
    result = run(path, 1, tuple(recorded))
    assert isinstance(result, Terminal)
    assert result.returns == native


def test_empty_history_pauses_with_encoded_legal_and_logs() -> None:
    r = run(HEARTS, 0, ())
    assert isinstance(r, Pause)
    assert r.player in range(4)
    assert len(r.legal) == 13 and r.legal == sorted(r.legal)
    assert all(0 <= a < 52 for a in r.legal)
    assert set(r.obs_logs) == {0, 1, 2, 3}
    assert all(any(e[0] == "move" for e in log) for log in r.obs_logs.values())  # the deal


def test_bigtwo_first_decision_offers_combos() -> None:
    _, space = load(BIGTWO)
    r = run(BIGTWO, 0, ())
    assert isinstance(r, Pause)
    assert all(space._combo_base <= a or a >= 52 for a in r.legal)  # no bare cards
    # stepping one combo action advances
    nxt = run(BIGTWO, 0, (r.legal[0],))
    assert isinstance(nxt, (Pause, Terminal))


def test_on_first_decision_mutates_the_replayed_world() -> None:
    r0 = run(HEARTS, 0, ())
    assert isinstance(r0, Pause)
    baseline = len(r0.rs.zones.instance("hand", 0).cards)

    def strip_one(rs: Any) -> None:
        hand = rs.zones.instance("hand", 0)
        hand.remove(hand.cards[0])

    r1 = run(HEARTS, 0, (), on_first_decision=strip_one)
    assert isinstance(r1, Pause)
    assert len(r1.rs.zones.instance("hand", 0).cards) == baseline - 1


def test_returns_for_team_scored_game_maps_players_through_teams() -> None:
    game, _ = load(str(GAMES / "bridge.cardlang"))
    from cardlang.runtime.driver import GameResult

    result = GameResult(scores={0: 120, 1: 90}, winner=0, loser=None, hands_played=1)
    rets = returns_for(game, result)
    assert len(rets) == 4
    team_of = {p: ti for ti, members in enumerate(game.partnerships) for p in members}
    assert rets == [float(result.scores[team_of[p]]) for p in range(4)]


def test_returns_for_loser_game() -> None:
    game, _ = load(str(GAMES / "getaway.cardlang"))
    from cardlang.runtime.driver import GameResult

    result = GameResult(scores={}, winner=None, loser=2, hands_played=1)
    n = game.players.low
    rets = returns_for(game, result)
    assert rets[2] == float(-(n - 1))
    assert all(rets[p] == 1.0 for p in range(n) if p != 2)
    assert abs(sum(rets)) < 1e-9


def test_instantiate_games_are_rejected_as_infoset_debt() -> None:
    # (lru_cache does not cache exceptions, so no cache management is needed.)
    with pytest.raises(ValueError, match="info-set debt"):
        load(str(GAMES / "skat.cardlang"))
```

- [ ] **Step 2: Run to verify failure**

Run: `pytest tests/test_openspiel_replay.py -q`
Expected: FAIL — `ImportError: cannot import name 'load'`

- [ ] **Step 3: Implement**

**(a) `driver.py`** — add the hook parameter and wrap the chooser:

```python
def play_game(
    game: n.Game,
    rng: random.Random,
    tracer: Callable[[str, Any], None] | None = None,
    chooser: Chooser | None = None,
    observer: Callable[[Player, tuple[Any, ...]], None] | None = None,
    on_first_decision: Callable[[RuntimeState], None] | None = None,
) -> GameResult:
```

after `rs` is fully constructed (right before `ctx = Ctx(...)`):

```python
    base_chooser = chooser or random_chooser(rng)
    if on_first_decision is not None:
        # The deal-injection seam (SP1 proof harness): fire once, inside the
        # first chooser call, before delegating. NOTE: the first decider's
        # candidates were computed before this fires — a mutation must not
        # touch the first decider's own zones (the harness guarantees it).
        inner = base_chooser
        hook = on_first_decision
        fired = False

        def hooked(player: Player, candidates: list[Any], n: int) -> list[Any]:
            nonlocal fired
            if not fired:
                fired = True
                hook(rs)
            return inner(player, candidates, n)

        base_chooser = hooked
    ctx = Ctx(rs=rs, chooser=base_chooser, tracer=tracer, observer=observer)
```

**(b) Rewrite `cardlang/openspiel/replay.py`:**

```python
"""Generalized re-simulation engine: drive ANY fully-kernel game
action-by-action by replaying a recorded action history through ``play_game``.

The OpenSpiel ``State`` is just ``(seed, history)``. Every query re-runs the
game with a :class:`ReplayChooser` that decodes and returns the recorded
actions in order and raises ``ChooserAbort`` at the first decision beyond the
history — surfacing the current decision point with the live world and the
per-player observation logs attached. The chooser makes no RNG calls, so a run
is a pure function of ``seed``. Games with `instantiate` mechanics are
rejected: their Python phases emit no observations (info-set debt,
docs/kernel-migration.md)."""

from __future__ import annotations

import random
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any, Callable, cast

from cardlang.ast import nodes as n
from cardlang.openspiel.encoding import ActionSpace
from cardlang.pipeline import check_source
from cardlang.runtime.driver import GameResult, play_game
from cardlang.runtime.state import ChooserAbort, RuntimeState


def _has_instantiate(game: n.Game) -> bool:
    from cardlang.openspiel.encoding import _walk

    return any(isinstance(node, n.Instantiate) for node in _walk(game))


@lru_cache(maxsize=None)
def load(path_str: str) -> tuple[n.Game, ActionSpace]:
    """Parse + check a game and derive its action space (cached per path)."""
    game = check_source(Path(path_str))
    if _has_instantiate(game):
        raise ValueError(
            f"game '{game.name}' uses a Python `instantiate` mechanic: its hidden "
            f"state emits no observations, so information sets cannot be derived "
            f"(info-set debt — see docs/kernel-migration.md)"
        )
    return game, ActionSpace.for_game(game)


@dataclass
class Pause:
    """A suspended player decision."""

    player: int
    legal: list[int]  # global action ids, sorted ascending
    rs: RuntimeState  # the live world at the pause
    obs_logs: dict[int, list[tuple[Any, ...]]]  # per-player observation logs


@dataclass
class Terminal:
    """A completed game."""

    returns: list[float]


class ReplayChooser:
    """Returns recorded actions in order; aborts at the first un-recorded one.
    A chooser call requesting ``k`` picks decomposes into ``k`` sequential
    actions, so multi-card selections stay in the same global action space."""

    def __init__(self, space: ActionSpace, history: tuple[int, ...]) -> None:
        self.space = space
        self.history = history
        self.cursor = 0

    def __call__(self, player: int, candidates: list[Any], k: int) -> list[Any]:
        pool = list(candidates)
        picked: list[Any] = []
        for _ in range(k):
            if self.cursor >= len(self.history):
                legal = sorted({self.space.encode(c) for c in pool})
                raise ChooserAbort(player, legal)
            aid = self.history[self.cursor]
            self.cursor += 1
            choice = self.space.match(aid, pool)  # must be among the candidates
            pool.remove(choice)
            picked.append(choice)
        return picked


def returns_for(game: n.Game, result: GameResult) -> list[float]:
    """General-sum returns from the game's own result (SP1 spec, component 6):
    true scores, sign-adjusted so higher is better (negated for `lowest`
    winners); team-keyed scores map each player to their team's score. An
    elimination (`loser:`) game returns +1 per survivor and -(n-1) for the
    loser, which sums to zero."""
    n_players = game.players.low
    if game.winner is None:
        assert result.loser is not None
        return [
            float(-(n_players - 1)) if p == result.loser else 1.0
            for p in range(n_players)
        ]
    sign = -1.0 if game.winner.rank_dir == "lowest" else 1.0
    scores = result.scores
    if set(scores) == set(range(n_players)):
        return [sign * scores[p] for p in range(n_players)]
    # Team-keyed scores (Bridge, Spades). All six games have 4 players, so the
    # player-key and team-key sets can never coincide ambiguously here.
    team_of = {p: ti for ti, members in enumerate(game.partnerships) for p in members}
    return [sign * scores[team_of[p]] for p in range(n_players)]


def run(
    path_str: str,
    seed: int,
    history: tuple[int, ...],
    on_first_decision: Callable[[RuntimeState], None] | None = None,
) -> Pause | Terminal:
    """Replay ``history`` under ``seed``; return the next decision or the result."""
    game, space = load(path_str)
    chooser = ReplayChooser(space, history)
    logs: dict[int, list[tuple[Any, ...]]] = {
        p: [] for p in range(game.players.low)
    }
    try:
        result = play_game(
            game,
            random.Random(seed),
            chooser=chooser,
            observer=lambda pl, ev: logs[pl].append(ev),
            on_first_decision=on_first_decision,
        )
    except ChooserAbort as abort:
        assert abort.rs is not None
        return Pause(abort.player, list(cast("list[int]", abort.legal)), abort.rs, logs)
    return Terminal(returns_for(game, result))
```

(This deletes `hearts_game`, `_returns_from`, `_HEARTS_PATH`, and the count-based `kind` classification — the first Hearts-specific convention falls here. `game.py` still imports the old names until Task 9; run `pytest tests/test_openspiel_replay.py -q` now, and expect `tests/test_openspiel_hearts.py` to ERROR on import — that is the known intermediate state, fixed in Task 9. Do NOT run the full gate mid-task; proceed.)

- [ ] **Step 4: Run the task tests**

Run: `pytest tests/test_openspiel_replay.py -q` → PASS
Note: `test_replay_reproduces_a_reference_game[bridge.cardlang]` replays a full rubber — if it exceeds ~120s, change its parameterization to `SIX` minus bridge plus a comment, and rely on Task 10's bounded-step bridge coverage. State clearly in the commit if you do.

- [ ] **Step 5: Commit**

```bash
git add cardlang/openspiel/replay.py cardlang/runtime/driver.py tests/test_openspiel_replay.py
git commit -m "feat(openspiel): generalize the re-sim engine to any fully-kernel game"
```

---

### Task 9: The general game adapter — six games registered

**Files:**
- Rewrite: `cardlang/openspiel/game.py`
- Rewrite: `tests/test_openspiel_hearts.py` (port to the general API)
- Delete: `hearts_information_state` from `cardlang/openspiel/infostate.py` (its last consumers go here)

**Interfaces:**
- Consumes: `load`/`run`/`Pause`/`Terminal` (Task 8), `information_state` (Task 7).
- Produces: `GAMES: dict[str, str]` (short_name → filename) and six registered pyspiel games: `cardlang_hearts`, `cardlang_getaway`, `cardlang_spades`, `cardlang_bridge`, `cardlang_oh_hell`, `cardlang_big_two`. Importing `cardlang.openspiel.game` registers all six.

- [ ] **Step 1: Port `tests/test_openspiel_hearts.py` (the failing spec)**

Rewrite the file, preserving each old test's *semantic* under the new API. The mapping: `hearts_information_state(p, rs, observed_log)` → `information_state(p, rs, pause.obs_logs[p])`; `run(seed, h)` → `run(HEARTS, seed, h)`; the zero-sum assertion becomes the general-sum contract (Hearts returns = negated raw scores).

```python
"""Hearts on the GENERAL OpenSpiel adapter: API conformance, a full rollout,
and the ported info-state regression tests (leakage, mid-pass hiding, perfect
recall, own-action distinction) — now against DERIVED observations."""

from __future__ import annotations

import random
from pathlib import Path

import pytest

pyspiel = pytest.importorskip("pyspiel")

import cardlang.openspiel.game  # noqa: E402  (registers all six games on import)
from cardlang.openspiel.infostate import information_state  # noqa: E402
from cardlang.openspiel.replay import Pause, run  # noqa: E402

HEARTS = str(Path(__file__).resolve().parent.parent / "docs" / "games" / "hearts.cardlang")


def test_random_sim_conformance() -> None:
    game = pyspiel.load_game("cardlang_hearts")
    assert game.num_distinct_actions() == 52
    pyspiel.random_sim_test(game, num_sims=2, serialize=False, verbose=False)


def test_full_rollout_returns_negated_scores() -> None:
    game = pyspiel.load_game("cardlang_hearts")
    state = game.new_initial_state()
    rng = random.Random(2)
    steps = 0
    while not state.is_terminal():
        if state.is_chance_node():
            action = rng.choice([o for o, _ in state.chance_outcomes()])
        else:
            action = rng.choice(state.legal_actions())
        state.apply_action(action)
        steps += 1
        assert steps < 10000
    ret = state.returns()
    assert len(ret) == 4
    assert all(r <= 0 for r in ret)  # lowest-wins: returns are negated penalties
    assert min(ret) < 0  # 26 penalty points exist per hand; someone took some


def test_infostate_does_not_leak_hidden_hands() -> None:
    r = run(HEARTS, 0, ())
    assert isinstance(r, Pause)
    p = r.player
    info_p = information_state(p, r.rs, r.obs_logs[p])
    for q in range(4):
        if q == p:
            continue
        for card in r.rs.zones.instance("hand", q).cards:
            assert str(card) not in info_p, f"leak: {card} (player {q}) in P{p}"


def test_infostate_hides_other_players_pass_mid_simultaneous_pass() -> None:
    seed = 0
    history: list[int] = []
    r = run(HEARTS, seed, ())
    assert isinstance(r, Pause)
    first = r.player
    while isinstance(r, Pause) and r.player == first:
        history.append(r.legal[0])
        r = run(HEARTS, seed, tuple(history))
    assert isinstance(r, Pause) and r.player != first
    p2 = r.player
    info_p2 = information_state(p2, r.rs, r.obs_logs[p2])
    # Mid-pass, transfers have not applied: the first passer's picks are still
    # in their hand, so the hidden-hand check covers the picks themselves.
    for card in r.rs.zones.instance("hand", first).cards:
        assert str(card) not in info_p2
    # And p2 must have received zero "chose" events during the pass beyond
    # their own single selection ("chose" is actor-only by construction).
    assert sum(1 for e in r.obs_logs[p2] if e[0] == "chose") == 1


def test_perfect_recall_no_duplicate_infostates_in_a_game() -> None:
    seed = 3
    history: list[int] = []
    seen: dict[int, set[str]] = {p: set() for p in range(4)}
    r = run(HEARTS, seed, ())
    steps = 0
    while isinstance(r, Pause):
        s = information_state(r.player, r.rs, r.obs_logs[r.player])
        assert s not in seen[r.player], "duplicate info-state (perfect recall violated)"
        seen[r.player].add(s)
        history.append(r.legal[0])
        r = run(HEARTS, seed, tuple(history))
        steps += 1
        assert steps < 5000


def test_perfect_recall_distinguishes_own_actions() -> None:
    r0 = run(HEARTS, 0, ())
    assert isinstance(r0, Pause)
    a, b = r0.legal[0], r0.legal[1]
    ra = run(HEARTS, 0, (a,))
    rb = run(HEARTS, 0, (b,))
    assert isinstance(ra, Pause) and isinstance(rb, Pause)
    ia = information_state(ra.player, ra.rs, ra.obs_logs[ra.player])
    ib = information_state(rb.player, rb.rs, rb.obs_logs[rb.player])
    assert ia != ib
```

- [ ] **Step 2: Run to verify failure**

Run: `pytest tests/test_openspiel_hearts.py -q`
Expected: FAIL/ERROR — `game.py` still imports the deleted `hearts_game`/old names

- [ ] **Step 3: Rewrite `cardlang/openspiel/game.py`**

First verify the `GameInfo` signature: run
`python -c "import pyspiel; help(pyspiel.GameInfo.__init__)" 2>&1 | head -5` —
if `utility_sum` is a required float, pass `0.0` (GENERAL_SUM games ignore it in the consistency checks); if it accepts `None`, pass `None`.

```python
"""Every fully-kernel game as a registered ``pyspiel.Game``.

One general adapter (SP1 spec): the state is ``(seed, history)`` over the
re-simulation engine, the action space and information states are DERIVED, and
registration is a loop over the game table — adding a fully-kernel game to the
table is the whole per-game cost. Importing this module registers all six;
load with e.g. ``pyspiel.load_game("cardlang_hearts")``.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pyspiel

from cardlang.openspiel import replay
from cardlang.openspiel.infostate import information_state

_NUM_SEEDS = 4096  # sampled deal space at the root chance node (known limitation)
_GAMES_DIR = Path(__file__).resolve().parent.parent.parent / "docs" / "games"

# short_name -> game file. The six fully-kernel games (no `instantiate`).
GAMES: dict[str, str] = {
    "cardlang_hearts": "hearts.cardlang",
    "cardlang_getaway": "getaway.cardlang",
    "cardlang_spades": "spades.cardlang",
    "cardlang_bridge": "bridge.cardlang",
    "cardlang_oh_hell": "oh-hell.cardlang",
    "cardlang_big_two": "big-two.cardlang",
}


class _Observer:
    """Minimal observer providing the information-state string (no tensors)."""

    def __init__(self) -> None:
        self.tensor = None
        self.dict: dict[str, Any] = {}

    def set_from(self, state: "CardlangState", player: int) -> None:
        pass  # no tensor representation

    def string_from(self, state: "CardlangState", player: int) -> str:
        return state.information_state_string(player)


class CardlangState(pyspiel.State):
    def __init__(self, game: pyspiel.Game, path: str, num_players: int) -> None:
        super().__init__(game)
        self._path = path
        self._num_players = num_players
        self._seed: int | None = None
        self._history_ids: list[int] = []
        self._cache_key: Any = object()
        self._cache: replay.Pause | replay.Terminal | None = None

    def _run(self) -> replay.Pause | replay.Terminal:
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
        return pyspiel.PlayerId.TERMINAL if isinstance(r, replay.Terminal) else r.player

    def _legal_actions(self, player: int) -> list[int]:
        r = self._run()
        assert isinstance(r, replay.Pause)
        return r.legal

    def chance_outcomes(self) -> list[tuple[int, float]]:
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
            return f"Deal(seed={action})"
        _, space = replay.load(self._path)
        return space.to_string(action)

    def is_terminal(self) -> bool:
        return self._seed is not None and isinstance(self._run(), replay.Terminal)

    def returns(self) -> list[float]:
        if self._seed is None:
            return [0.0] * self._num_players
        r = self._run()
        return r.returns if isinstance(r, replay.Terminal) else [0.0] * self._num_players

    def information_state_string(self, player: int | None = None) -> str:
        if self._seed is None:
            return ""  # chance root
        if player is None:
            player = self.current_player()
        r = self._run()
        if not isinstance(r, replay.Pause):
            return ""
        return information_state(player, r.rs, r.obs_logs[player])

    def clone(self) -> "CardlangState":
        copy = CardlangState(self.get_game(), self._path, self._num_players)
        copy._seed = self._seed
        copy._history_ids = list(self._history_ids)
        return copy

    def __str__(self) -> str:
        return f"seed={self._seed} history={self._history_ids}"


def _register(short_name: str, filename: str) -> None:
    path = str(_GAMES_DIR / filename)
    game_ast, space = replay.load(path)
    num_players = game_ast.players.low
    game_type = pyspiel.GameType(
        short_name=short_name,
        long_name=f"Cardlang {game_ast.name}",
        dynamics=pyspiel.GameType.Dynamics.SEQUENTIAL,
        chance_mode=pyspiel.GameType.ChanceMode.EXPLICIT_STOCHASTIC,
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
        max_chance_outcomes=_NUM_SEEDS,
        num_players=num_players,
        min_utility=-100000.0,  # loose static bounds; true scores are far inside
        max_utility=100000.0,
        utility_sum=0.0,
        max_game_length=10000,
    )

    class _Game(pyspiel.Game):
        def __init__(self, params: Any = None) -> None:
            super().__init__(game_type, game_info, params or dict())

        def new_initial_state(self) -> CardlangState:
            return CardlangState(self, path, num_players)

        def make_py_observer(self, iig_obs_type: Any = None, params: Any = None) -> _Observer:
            return _Observer()

    pyspiel.register_game(game_type, _Game)


for _short_name, _filename in GAMES.items():
    _register(_short_name, _filename)
```

Then delete `hearts_information_state` from `infostate.py` and grep for stragglers:
`grep -rn "hearts_information_state\|hearts_game\|observed_log" cardlang tests` → must return nothing.

- [ ] **Step 4: Run tests + full gate**

Run: `pytest tests/test_openspiel_hearts.py tests/test_openspiel_replay.py -q` → PASS
Run: `mypy` → clean; `PYTHONHASHSEED=0 pytest -q` → all green

- [ ] **Step 5: Commit**

```bash
git add cardlang/openspiel/game.py cardlang/openspiel/infostate.py tests/test_openspiel_hearts.py
git commit -m "feat(openspiel): one general adapter; six fully-kernel games registered"
```

---

### Task 10: The proof harness — OpenSpiel-ready, falsifiable, per game

**Files:**
- Create: `tests/test_openspiel_ready.py`

**Interfaces:**
- Consumes: everything above. This file IS the acceptance criterion of SP1.

- [ ] **Step 1: Write the harness (fails until green by construction — it is the proof, not scaffolding)**

```python
"""The OpenSpiel-readiness proof, per fully-kernel game (SP1 spec, "The proof"):

1. pyspiel API conformance (random_sim_test).
2. INDISTINGUISHABILITY: two worlds differing only in cards hidden from P
   yield byte-identical information states for P (the leak-closure proof).
3. Soundness converse: perturbing what P CAN see changes P's state.
4. Perfect recall: each player's observation log is append-only along a game.
"""

from __future__ import annotations

import random
from pathlib import Path
from typing import Any

import pytest

pyspiel = pytest.importorskip("pyspiel")

import cardlang.openspiel.game as ogame  # noqa: E402  (registers on import)
from cardlang.openspiel.infostate import information_state  # noqa: E402
from cardlang.openspiel.replay import Pause, run  # noqa: E402

GAMES_DIR = Path(__file__).resolve().parent.parent / "docs" / "games"
SIX = sorted(ogame.GAMES.items())  # (short_name, filename), deterministic order

# Steps to replay before the indistinguishability check. Deep enough that real
# decisions and movements happened; shallow enough that opponents still hold
# swappable cards. Getaway/Big Two shed cards fast, hence the smaller L.
DEPTH = {"cardlang_getaway": 8, "cardlang_big_two": 6}
DEFAULT_DEPTH = 12


@pytest.mark.parametrize(("short_name", "filename"), SIX)
def test_pyspiel_conformance(short_name: str, filename: str) -> None:
    game = pyspiel.load_game(short_name)
    pyspiel.random_sim_test(game, num_sims=1, serialize=False, verbose=False)


def _advance(path: str, seed: int, depth: int) -> tuple[list[int], Pause]:
    history: list[int] = []
    r = run(path, seed, ())
    assert isinstance(r, Pause)
    while len(history) < depth:
        history.append(r.legal[0])
        nxt = run(path, seed, tuple(history))
        if not isinstance(nxt, Pause):  # short game: back off one step
            history.pop()
            break
        r = nxt
    return history, r


def _swap_fn(opp1: int, opp2: int, x: Any, y: Any) -> Any:
    def swap(rs: Any) -> None:
        h1, h2 = rs.zones.instance("hand", opp1), rs.zones.instance("hand", opp2)
        h1.remove(x)
        h2.remove(y)
        h1.add(y)
        h2.add(x)

    return swap


@pytest.mark.parametrize(("short_name", "filename"), SIX)
def test_indistinguishability_under_hidden_swap(short_name: str, filename: str) -> None:
    path = str(GAMES_DIR / filename)
    seed = 5
    depth = DEPTH.get(short_name, DEFAULT_DEPTH)
    history, pause_a = _advance(path, seed, depth)
    p = pause_a.player
    first = run(path, seed, ())
    assert isinstance(first, Pause)
    d0 = first.player  # the swap must not touch the first decider (stale candidates)

    others = [q for q in range(len(pause_a.obs_logs)) if q not in (p, d0)]
    assert len(others) >= 2, "harness needs two swappable opponents"
    opp1, opp2 = others[0], others[1]

    # Same-suit swap keeps every recorded action legal in the swapped world;
    # skip pairs the replay rejects (a rule keyed on the specific card).
    hand1 = pause_a.rs.zones.instance("hand", opp1).cards
    hand2 = pause_a.rs.zones.instance("hand", opp2).cards
    three_d = ("3", "diamonds")
    candidates = [
        (x, y)
        for x in hand1
        for y in hand2
        if x.suit == y.suit
        and x != y
        # keep the 3♦ fixed: Big Two's opening filter keys on that exact card
        and (x.rank, x.suit) != three_d
        and (y.rank, y.suit) != three_d
    ]
    assert candidates, "no same-suit swap pair available; lower DEPTH for this game"

    info_a = information_state(p, pause_a.rs, pause_a.obs_logs[p])
    for x, y in candidates:
        try:
            pause_b = run(path, seed, tuple(history), on_first_decision=_swap_fn(opp1, opp2, x, y))
        except Exception:
            continue  # this pair made a recorded action illegal; try the next
        assert isinstance(pause_b, Pause)
        info_b = information_state(p, pause_b.rs, pause_b.obs_logs[p])
        assert info_a == info_b, (
            f"{short_name}: swapping hidden {x}<->{y} (players {opp1},{opp2}) "
            f"CHANGED P{p}'s information state — the info-set leaks"
        )
        return  # one successful controlled swap proves the property
    pytest.fail(f"{short_name}: no swap pair produced a legal replay")


@pytest.mark.parametrize(("short_name", "filename"), SIX)
def test_soundness_own_view_changes_the_state(short_name: str, filename: str) -> None:
    path = str(GAMES_DIR / filename)
    r0 = run(path, 5, ())
    assert isinstance(r0, Pause)
    p = r0.player
    opp = next(q for q in range(len(r0.obs_logs)) if q != p)
    own = r0.rs.zones.instance("hand", p).cards
    theirs = r0.rs.zones.instance("hand", opp).cards
    x, y = next(
        (x, y) for x in own for y in theirs if x.suit == y.suit and x != y
    )
    info_a = information_state(p, r0.rs, r0.obs_logs[p])
    r1 = run(path, 5, (), on_first_decision=_swap_fn(p, opp, x, y))
    assert isinstance(r1, Pause)
    info_b = information_state(r1.player, r1.rs, r1.obs_logs[r1.player])
    # The pause player is the same (no actions replayed); their own hand changed.
    assert r1.player == p and info_a != info_b, (
        f"{short_name}: the info-state is insensitive to the player's own hand"
    )


@pytest.mark.parametrize(("short_name", "filename"), SIX)
def test_perfect_recall_logs_are_append_only(short_name: str, filename: str) -> None:
    path = str(GAMES_DIR / filename)
    seed = 9
    history: list[int] = []
    r = run(path, seed, ())
    prev: dict[int, list[tuple[Any, ...]]] = {}
    steps = 0
    while isinstance(r, Pause) and steps < 40:
        for q, log in r.obs_logs.items():
            if q in prev:
                assert log[: len(prev[q])] == prev[q], (
                    f"{short_name}: P{q}'s observation log rewrote history"
                )
            prev[q] = list(log)
        history.append(r.legal[0])
        r = run(path, seed, tuple(history))
        steps += 1
```

Note on the soundness test's first-decider caveat: here the swap DOES touch the pause player `p` — but with `history=()` no action is ever replayed and no candidate is consumed, only the paused world is inspected, so the stale-candidates hazard is moot; the hook fires before the abort. Do not extend this test to nonzero history without re-introducing the d0 exclusion.

- [ ] **Step 2: Run per game, then the full gate**

Run: `PYTHONHASHSEED=0 pytest tests/test_openspiel_ready.py -q -x`
Expected: PASS (24 tests: 4 properties × 6 games). If `test_indistinguishability_under_hidden_swap` FAILS for a game, that is a REAL info-set leak in the emission wiring — debug the leak (which event delivered identity content it shouldn't have?), do NOT weaken the test.
If bridge conformance exceeds ~120s: keep it but add `@pytest.mark.timeout` exemption comment; if it exceeds ~300s, replace bridge's `random_sim_test` with a 200-step manual rollout loop (apply random legal actions, assert legality/cloning at each step) and say so in the commit message.

Run: `mypy` → clean; `PYTHONHASHSEED=0 pytest -q` → all green

- [ ] **Step 3: Commit**

```bash
git add tests/test_openspiel_ready.py
git commit -m "test(openspiel): the OpenSpiel-readiness proof harness for the six kernel games"
```

- [ ] **Step 4: The playtest-report helper (spec component 7's second half)**

Create `cardlang/openspiel/report.py` — the seed of the design-tool CLI, shared
between tests and future tooling:

```python
"""Playtest statistics over random rollouts of a registered cardlang game —
the designer-feedback seed (SP1 spec, "Design-tool alignment"): run N games,
report length, branching, returns spread, and per-seat outcomes."""

from __future__ import annotations

import random
from typing import Any

import pyspiel


def playtest_report(short_name: str, num_games: int, seed: int = 0) -> dict[str, Any]:
    game = pyspiel.load_game(short_name)
    rng = random.Random(seed)
    lengths: list[int] = []
    branchings: list[int] = []
    all_returns: list[list[float]] = []
    for _ in range(num_games):
        state = game.new_initial_state()
        steps = 0
        while not state.is_terminal():
            if state.is_chance_node():
                state.apply_action(rng.choice([o for o, _ in state.chance_outcomes()]))
                continue
            legal = state.legal_actions()
            branchings.append(len(legal))
            state.apply_action(rng.choice(legal))
            steps += 1
        lengths.append(steps)
        all_returns.append(state.returns())
    n = game.num_players()
    best_seat = [0] * n
    for rets in all_returns:
        best_seat[max(range(n), key=lambda p: rets[p])] += 1
    return {
        "game": short_name,
        "num_games": num_games,
        "mean_length": sum(lengths) / len(lengths),
        "mean_branching": sum(branchings) / len(branchings),
        "mean_returns": [
            sum(r[p] for r in all_returns) / num_games for p in range(n)
        ],
        "best_seat_counts": best_seat,
    }
```

Append to `tests/test_openspiel_ready.py`:

```python
def test_playtest_report_shape() -> None:
    from cardlang.openspiel.report import playtest_report

    rep = playtest_report("cardlang_getaway", num_games=2, seed=1)
    assert rep["num_games"] == 2
    assert rep["mean_length"] > 0 and rep["mean_branching"] >= 1
    assert len(rep["mean_returns"]) == 4
    assert sum(rep["best_seat_counts"]) == 2
```

Run: `PYTHONHASHSEED=0 pytest tests/test_openspiel_ready.py -q` → PASS; then commit:

```bash
git add cardlang/openspiel/report.py tests/test_openspiel_ready.py
git commit -m "feat(openspiel): playtest-report helper — the design-tool feedback seed"
```

---

### Task 11: Documentation, honest status, final gate

**Files:**
- Modify: `CLAUDE.md` (the load-bearing "honest status" paragraph)
- Modify: `docs/design-notes/kernel-extensibility.md` (§6 headline + §9 step 4 + status line)
- Modify: `docs/kernel-migration.md` (info-set-debt framing: the substrate now exists)
- Modify: `docs/superpowers/specs/2026-07-01-openspiel-projection-substrate-design.md` (already amended pre-implementation; verify consistency)

- [ ] **Step 1: Update `CLAUDE.md`** — replace the "Honest status" paragraph body with (keep the heading and surrounding structure):

```markdown
**Honest status — the substrate exists; the escape hatches are still debt.**
The six fully-kernel games (Hearts, Getaway, Spades, Bridge, Oh Hell, Big Two)
reach OpenSpiel through ONE general adapter with *derived* information sets:
per-observer observations are emitted from the kernel's decision/movement
sites through the declared zone-type projections, and
`tests/test_openspiel_ready.py` proves indistinguishability (hidden-card swaps
leave a player's information state byte-identical), soundness, and perfect
recall for each. No per-game observation rules remain. But every per-game
Python escape-hatch mechanic dispatched by `instantiate` (Schnapsen, Pinochle
rest, Coup, Skat, Tarot rest, Cribbage, Stud showdown, Tichu) still *bypasses*
this derivation — the adapter rejects those eight games loudly, and the leak
lands hardest on exactly the imperfect-information games the AI target most
exists to serve. The gap is quantified in
`docs/design-notes/kernel-extensibility.md`, §6.
```

- [ ] **Step 2: Update the design note** — in the status line at the top, change "§9 steps 1–3 are done" to "§9 steps 1–3 are done, and step 4 is delivered for the fully-kernel games (the projection substrate + general adapter; the eight `instantiate` games remain)". In §6, prefix the headline paragraph with a one-sentence status: the substrate described here now exists for kernel-form games (`cardlang/runtime/observe.py`, `cardlang/openspiel/`); the leak persists exactly where `instantiate` mechanics run. In §9 step 4, mark the kernel-game half done the same way steps 2–3 were marked.

- [ ] **Step 3: Update `docs/kernel-migration.md`** — in the intro (near the workstream list), add one sentence: each migration now has a second payoff — a game leaving its Python mechanic becomes OpenSpiel-ready automatically (register it in `cardlang/openspiel/game.py:GAMES` and add it to the proof harness), so "migrated" now means "derived info sets proven," per the SP1 spec.

- [ ] **Step 4: Final full gate + push**

```bash
mypy
PYTHONHASHSEED=0 pytest -q
git add CLAUDE.md docs/design-notes/kernel-extensibility.md docs/kernel-migration.md
git commit -m "docs: the projection substrate closes the info-set leak for kernel-form games"
git push -u origin feat/openspiel-projection-substrate
```

Both commands MUST be green before the push (CLAUDE.md discipline). PR title: `feat(openspiel): projection substrate — derived info sets + general adapter for the six kernel games`. PR body: goal, the two pillars, the proof harness's four properties, the byte-identity guarantee, the honest exclusion of the eight `instantiate` games, and the "Generated with Claude Code" footer. Note the stacking on PR #20 (merge that first or retarget).
