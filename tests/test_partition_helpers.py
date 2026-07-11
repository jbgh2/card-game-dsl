"""The information-partition proof machinery (tests/openspiel_ready/partition.py):
fact enumeration from the declared projections, the perturbation matrix, the
witness renderer, and the coverage registry."""

from __future__ import annotations

import json
import random
from typing import Any

from cardlang.ast import nodes as n
from cardlang.runtime.state import RuntimeState, ZoneStore
from cardlang.runtime.values import Card, Seating

from tests.openspiel_ready.partition import (
    RECORDS,
    SYNTHETIC,
    all_hidden,
    check_visible_facts,
    dump_json,
    first_divergence,
    projection_for,
    record,
    summary_lines,
    zone_instances,
)


def _rs() -> RuntimeState:
    decls = (
        n.ZoneDecl(name="deck", index=None, type_ref=n.TypeRef(name="Deck")),
        n.ZoneDecl(name="hand", index="player", type_ref=n.TypeRef(name="Hand")),
        n.ZoneDecl(name="trick_pile", index=None, type_ref=n.TypeRef(name="TrickPile")),
        n.ZoneDecl(name="muck", index=None, type_ref=n.TypeRef(name="Muck")),
    )
    rs = RuntimeState(Seating(2), ZoneStore(decls, players=(0, 1)), random.Random(0))
    rs.zones.instance("hand", 0).add(Card("Q", "spades"))
    rs.zones.instance("hand", 1).add(Card("2", "clubs"))
    rs.zones.single("trick_pile").add(Card("7", "hearts"))
    rs.zones.single("deck").add(Card("9", "diamonds"))
    rs.zones.single("muck").add(Card("4", "clubs"))
    rs.push_frame()
    rs.declare("score", indexed=False, value={0: 10, 1: 20})
    return rs


def test_first_divergence_locates_the_difference() -> None:
    a = "x" * 100 + "AAA" + "y" * 100
    b = "x" * 100 + "BBB" + "y" * 100
    w = first_divergence(a, b)
    assert "AAA" in w and "BBB" in w and "@100" in w
    assert first_divergence("same", "same") == "(identical)"


def test_projection_for_reflects_declared_visibility() -> None:
    rs = _rs()
    assert projection_for(rs, "hand", 0, 0) == "identity"      # own hand
    assert projection_for(rs, "hand", 1, 0) == "count_only"    # opponent's
    assert projection_for(rs, "trick_pile", None, 0) == "identity"
    assert projection_for(rs, "deck", None, 0) == "count_only"
    assert projection_for(rs, "muck", None, 0) == "trivial"


def test_zone_instances_deterministic_order() -> None:
    rs = _rs()
    labels = [(name, key) for name, key, _ in zone_instances(rs)]
    assert labels == [
        ("deck", None), ("muck", None), ("trick_pile", None),
        ("hand", 0), ("hand", 1),
    ]


def test_all_hidden_is_a_projection_table_fact() -> None:
    rs = _rs()
    assert all_hidden(rs, "deck")            # count_only / count_only
    assert all_hidden(rs, "muck")            # trivial / trivial
    assert not all_hidden(rs, "hand")        # identity to its owner
    assert not all_hidden(rs, "trick_pile")  # identity to everyone


def test_visible_fact_matrix_passes_on_a_correct_state() -> None:
    rs = _rs()
    log: list[tuple[Any, ...]] = [("announce", 1, "bid(3)")]
    failures, counts = check_visible_facts(rs, log, observer=0)
    assert failures == []
    # every zone got at least one perturbation; the state var and log too
    assert counts["zone_identity"] >= 2      # own hand + trick_pile
    assert counts["zone_count_only"] >= 2    # opp hand + deck
    assert counts["zone_trivial"] >= 1       # muck
    assert counts["state_vars"] == 1         # score
    assert counts["obs_events"] == 1


def test_visible_fact_matrix_restores_the_world() -> None:
    rs = _rs()
    before = {
        (name, key): list(zone.cards) for name, key, zone in zone_instances(rs)
    }
    frames_before = [dict(f) for f in rs.frames]
    log: list[tuple[Any, ...]] = [("chose", "7♥")]
    check_visible_facts(rs, log, observer=1)
    assert {
        (name, key): list(zone.cards) for name, key, zone in zone_instances(rs)
    } == before
    assert rs.frames == frames_before
    assert log == [("chose", "7♥")]


def test_visible_fact_matrix_catches_a_dropped_zone() -> None:
    # A renderer that ignores zones entirely must fail the identity facts.
    rs = _rs()
    failures, _ = check_visible_facts(
        rs, [], observer=0,
        info_fn=lambda player, rs_, log: "constant",
    )
    assert failures, "a constant info state must fail the matrix"
    assert any("hand[0]" in f.fact for f in failures)


def test_visible_fact_matrix_catches_a_leaking_renderer() -> None:
    # A renderer that shows raw hidden content must fail the no-change facts.
    rs = _rs()

    def leaky(player: int, rs_: RuntimeState, log: list[tuple[Any, ...]]) -> str:
        return ",".join(
            str(c) for _, _, z in zone_instances(rs_) for c in z.cards
        )

    failures, _ = check_visible_facts(rs, [], observer=0, info_fn=leaky)
    assert any(f.expected == "no-change" for f in failures)


def test_coverage_registry_records_and_dumps(tmp_path: Any) -> None:
    # Snapshot-and-restore: the registry is a session-global that the
    # openspiel_ready proofs may already have populated in this run, and the
    # terminal summary renders it AFTER all tests — never clear it outright.
    saved = RECORDS[:]
    RECORDS.clear()
    try:
        record("cardlang_demo", "swap", seed=5, pairs_tried=3)
        record("cardlang_demo", "facts", observers=2)
        lines = summary_lines()
        assert any("cardlang_demo" in line for line in lines)
        out = tmp_path / "report.json"
        dump_json(str(out))
        data = json.loads(out.read_text())
        assert data[0]["game"] == "cardlang_demo" and data[0]["proof"] == "swap"
        assert data[0]["detail"]["seed"] == 5
    finally:
        RECORDS[:] = saved


def test_synthetic_card_is_not_a_real_card() -> None:
    assert SYNTHETIC.suit == "synthetic"
    assert str(SYNTHETIC) == "‡:synthetic"
