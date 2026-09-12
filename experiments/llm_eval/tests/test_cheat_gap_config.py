"""Structural tests for the `cheat_gap` study's config and its archive.

Checks the config parses and validates, and pins the invariants the study's
design depends on rather than any number a run happens to produce: seed
pairing across cells, the null control's four identical seats, and the three
one-LLM-seat cells differing from each other only in the LLM seat. The
promotable claim — that a committed archive still identifies its own game and
replays — is checked against whatever the archive holds, so this test is
meaningful before a byte of it exists and after.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
import yaml

from ..metrics import iter_jsonl
from ..referee import ProvenanceError, game_digest, load_game, replay_views
from ..run_eval import validate_model_refs

pytest.importorskip("pyspiel", reason="the OpenSpiel adapter needs the `openspiel` extra")

CONFIG_PATH = Path("experiments/llm_eval/config_cheat_gap.yaml")
ARCHIVE = Path("experiments/llm_eval/results_cheat_gap/transcripts")

# The three cells this study preregisters before running: identical to each
# other except for the LLM seat's `model` and `name` and the registered `n`.
LLM_TABLE_CELLS = ("llm_cheap_table", "llm_mid_table", "llm_frontier_table")

# `n` per registered cell, as `PREREGISTRATION_CHEAT_GAP.md` registers it. The
# frontier model is ~5x the per-game cost of the cheap one, so the cheaper
# cells buy the extra within-cell resolution and the frontier cell is sized to
# the 10 seeds all three share. A registered parameter is exactly what a test
# may pin: an `n` that drifts from this table makes the preregistration
# describe a study nobody ran.
REGISTERED_N = {"llm_cheap_table": 20, "llm_mid_table": 20, "llm_frontier_table": 10}


def _config() -> dict[str, Any]:
    loaded: dict[str, Any] = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))
    return loaded


def _by_name(config: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {m["name"]: m for m in config["matchups"]}


def test_config_parses() -> None:
    config = _config()
    assert config["game"] == "cardlang_cheat"
    assert config["results_dir"] == "experiments/llm_eval/results_cheat_gap"
    assert config["matchups"], "no matchups"
    names = [m["name"] for m in config["matchups"]]
    assert len(names) == len(set(names)), f"duplicate matchup name in {names}"


def test_every_matchup_validates_its_agent_specs() -> None:
    """`run_eval`'s pre-flight — a typo'd model reference or an unpriced model
    must die here, before any credential is needed."""
    config = _config()
    validate_model_refs(config, config["matchups"])  # must not raise


def test_no_matchup_overrides_seeds() -> None:
    """Every matchup draws its seed from the ONE config-level `seeds.start`,
    which is what lets a gap pair by seed across cells. A per-matchup `seeds`
    key is not read by `run_eval` at all — silently ignored rather than
    honoured — so a matchup that set one would break the pairing while
    looking configured."""
    config = _config()
    assert "start" in config["seeds"]
    overriding = [m["name"] for m in config["matchups"] if "seeds" in m]
    assert not overriding, f"matchup(s) {overriding} set their own `seeds`"


def test_rule_table_is_four_identical_seats() -> None:
    """The null control: a rule agent's challenge decision conditions on
    nothing but `provably_false` and a fixed independent draw, so making the
    four seats identical is what makes its reader's gap zero by construction
    on non-provable windows."""
    rule_table = _by_name(_config())["rule_table"]
    agents = rule_table["agents"]
    assert len(agents) == 4
    assert all(a["kind"] == "rule" for a in agents)
    shapes = {tuple(sorted(a.items())) for a in agents}
    assert len(shapes) == 1, f"rule_table's seats are not identical: {agents}"


def test_registered_cells_carry_their_registered_n() -> None:
    by_name = _by_name(_config())
    got = {cell: by_name[cell]["n"] for cell in LLM_TABLE_CELLS}
    assert got == REGISTERED_N, (
        f"{got} is not the N registered in PREREGISTRATION_CHEAT_GAP.md "
        f"({REGISTERED_N}) — change the preregistration first"
    )


def test_llm_table_cells_differ_only_in_the_llm_seat() -> None:
    """`n` is excluded from the compared shape and pinned by name above: it
    differs between these cells BY REGISTRATION, where a difference in any
    other key would make a model comparison unattributable."""
    by_name = _by_name(_config())
    shared = None
    seen_models = set()
    seen_names = set()
    for cell in LLM_TABLE_CELLS:
        matchup = by_name[cell]
        agents = matchup["agents"]
        llm_seat, rule_seats = agents[0], agents[1:]
        assert llm_seat["kind"] == "llm", f"{cell}'s first seat is not the LLM seat"
        seen_models.add(llm_seat.get("model"))
        seen_names.add(llm_seat.get("name"))
        shape = {
            "rotate": matchup.get("rotate", True),
            "llm_seat_minus_model_and_name": {
                k: v for k, v in llm_seat.items() if k not in ("model", "name")
            },
            "rule_seats": rule_seats,
        }
        if shared is None:
            shared = shape
        else:
            assert shape == shared, (
                f"{cell} differs from the other llm_*_table cells beyond "
                f"model/name: {shape} vs {shared}"
            )
    # And they really do differ where they are supposed to — three distinct
    # models and three distinct seat names, not one shape copy-pasted three
    # times with nothing changed.
    assert len(seen_models) == 3, f"llm_*_table cells do not name 3 distinct models: {seen_models}"
    assert len(seen_names) == 3, f"llm_*_table cells do not name 3 distinct seat names: {seen_names}"


def _archived_transcripts() -> list[Path]:
    if not ARCHIVE.is_dir():
        return []
    return sorted(ARCHIVE.glob("*.jsonl.gz")) + sorted(ARCHIVE.glob("*.jsonl"))


def test_archived_transcripts_carry_the_expected_game_digest_and_replay() -> None:
    """Every promoted free-cell transcript carries `game_digest ==
    referee.game_digest("cardlang_cheat")`, and its first record replays
    without `ProvenanceError` — the check `promote.py`'s own docstring wants
    ("promote, delete the run directory, and the archive still identifies its
    own game") applied to provenance rather than only to game name.

    Skips rather than fails with no archive promoted: the config and its
    structural invariants above are the part of this test that holds before
    any game has been played, and a fresh checkout with the archive not yet
    promoted is not a broken one.
    """
    transcripts = _archived_transcripts()
    if not transcripts:
        pytest.skip("no matchup has been promoted into results_cheat_gap/transcripts yet")
    expected = game_digest("cardlang_cheat")
    game = load_game("cardlang_cheat")
    for path in transcripts:
        records = list(iter_jsonl(str(path)))
        assert records, f"{path} has no records"
        first = records[0]
        assert first.get("game_digest"), f"{path}'s first record has no game_digest"
        assert first["game_digest"] == expected, (
            f"{path}'s first record digests as {first['game_digest']!r}, not "
            f"the currently-loaded game's {expected!r}"
        )
        try:
            replay_views(
                game, first["seed"], first["history"], expected_digest=first["game_digest"]
            )
        except ProvenanceError as exc:  # pragma: no cover - the assertion below fails first
            pytest.fail(f"{path}'s first record does not replay: {exc}")
