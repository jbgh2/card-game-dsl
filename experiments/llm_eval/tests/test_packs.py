"""The per-game seam: the registry is total over the corpus, and refuses.

Two properties, both of the kind that go quietly wrong. A harness that DEFAULTED
an unknown game to Cheat's pack would run Cheat's rules text against another
game's information state and produce a transcript that parses, aggregates and
means nothing. And a coverage list that only grows would let "not packed" drift
from a decision into an oversight.
"""

from __future__ import annotations

import pytest

from ..packs import CHEAT, HOLDEM_HEADS_UP, PACKS, UNPACKED, pack_for


def _corpus_short_names() -> set[str]:
    """Every registered corpus game, from the adapter's own derived registry —
    never a hand-list here, or this test would check a copy of the answer."""
    from cardlang.openspiel.registry import GAMES

    return set(GAMES)


def test_every_corpus_game_is_packed_or_named_unpacked() -> None:
    """Tight in BOTH directions.

    A new corpus game with no pack fails here rather than surfacing as a
    `SystemExit` mid-run; a game that gains a pack and stays in `UNPACKED`
    fails just as loudly, so the list cannot outlive its reason. And a name in
    either collection that is not a corpus game at all fails too — that is how
    a rename gets caught.

    red under: delete `"cardlang_holdem"` from `UNPACKED`. RUN, not predicted:
    fails naming cardlang_holdem as covered by neither collection.
    """
    corpus = _corpus_short_names()
    packed = set(PACKS)

    both = packed & UNPACKED
    assert not both, f"packed AND listed unpacked: {sorted(both)}"

    neither = corpus - packed - UNPACKED
    assert not neither, (
        f"corpus games covered by neither collection: {sorted(neither)} — add a "
        f"pack in packs.py, or name them in UNPACKED with the reason that file "
        f"gives"
    )

    unknown = (packed | UNPACKED) - corpus
    assert not unknown, (
        f"named in packs.py but not a registered corpus game: {sorted(unknown)}"
    )


def test_an_unpacked_game_is_refused_rather_than_defaulted() -> None:
    """The refusal, and that it names the way out. `SystemExit` rather than a
    silent Cheat pack is the whole point of the registry."""
    for short_name in sorted(UNPACKED)[:3]:
        with pytest.raises(SystemExit) as caught:
            pack_for(short_name)
        assert "no harness pack" in str(caught.value)
        assert short_name in str(caught.value)


def test_pack_for_returns_the_named_pack() -> None:
    assert pack_for("cardlang_cheat") is CHEAT
    assert pack_for("cardlang_holdem_heads_up") is HOLDEM_HEADS_UP


def test_every_packs_short_name_matches_its_registry_key() -> None:
    """A pack whose `short_name` disagreed with its key would be reachable
    under one name and load the game under another."""
    for key, pack in PACKS.items():
        assert key == pack.short_name


def test_a_pack_declaring_action_verbs_offers_them_in_the_game() -> None:
    """`action_verbs` names the move types whose rates get reported. A verb the
    game never offers would report a rate over an empty denominator forever —
    a metric that cannot fail, dressed as one that can.

    Checked against the game's real action space rather than a list: every
    declared verb must be renderable by the adapter for that game. The
    renderings are read off a STATE, not off the game — `Game.action_to_string`
    is pyspiel's own `Action(id=N)` default and would make this pass on any
    list at all.
    """
    pyspiel = pytest.importorskip("pyspiel")
    from cardlang.openspiel import game as _adapter  # noqa: F401  (registration)

    for pack in PACKS.values():
        if not pack.action_verbs:
            continue
        game = pyspiel.load_game(pack.short_name)
        state = game.new_initial_state()
        state.apply_action(0)  # the root chance node: the deal
        space = {
            state.action_to_string(0, a) for a in range(game.num_distinct_actions())
        }
        missing = set(pack.action_verbs) - space
        assert not missing, (
            f"{pack.short_name} declares action verbs it cannot offer: "
            f"{sorted(missing)}"
        )
