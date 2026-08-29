"""The audit path, executed — and the summary/auditor contract, pinned.

`verify.py` exists to recompute the published numbers with its OWN arithmetic,
so a bug in `metrics.aggregate` cannot hide behind a checker that shares its
code. That is a real claim and it was unfalsifiable: `holdem_tally`, `AUDITS`,
`HOLDEM_RATES`, the `--game` selector and the `--deep` refusal were reached by
nothing in either suite, so any divergence between the two folds shipped green.

Two properties here, and the second is why the first could go wrong unnoticed:

1. The two folds AGREE over the committed archive. That cashes the independence
   claim: `aggregate` and `holdem_tally` are two independent implementations
   of the same arithmetic over the same transcript, so a fold bug has to
   occur identically in both to go unnoticed.
2. The auditor's rate table is DERIVED from `holdem.ACTION_VERBS`, not restated
   beside it. Restated, dropping a verb left the whole suite and mypy green
   while the published summary lost a rate the auditor kept printing.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from .. import holdem
from ..metrics import GAME_KEYS, aggregate, iter_jsonl
from ..verify import AUDITS, DEFAULT_GAME, HOLDEM_RATES, game_of, holdem_tally

ARCHIVE = Path(__file__).parent.parent / "results_holdem" / "transcripts"
MATCHUPS = (
    "rule_vs_random",
    "llm_cheap_vs_random",
    "llm_cheap_vs_rule",
    "llm_mid_vs_rule",
)


def _records(matchup: str) -> list[dict[str, object]]:
    path = ARCHIVE / f"{matchup}.jsonl.gz"
    if not path.is_file():
        pytest.skip(f"{path} is not present (the archive is committed, but a "
                    f"sparse checkout may omit it)")
    return list(iter_jsonl(str(path)))


@pytest.mark.parametrize("matchup", MATCHUPS)
def test_the_two_folds_agree_over_the_committed_archive(matchup: str) -> None:
    """The independence claim, cashed.

    Compared per agent and per verb, with the counts asserted non-zero first —
    two folds that both compute nothing agree trivially, and that is the shape
    this test would otherwise take on an empty archive.

    red under: change `holdem_tally`'s verb loop to read `d["facts"]["verb"]`
    instead of `d["action"]`. RUN, not predicted: the test still passes, because
    the two sources currently hold identical values — which is exactly why the
    NEXT test, not this one, is what protects against drift. What this one
    catches is an arithmetic divergence, and for that the reddening mutation is
    `c[f"{verb}_offered"] += 1` -> `+= 2`, which fails naming the verb.
    """
    records = _records(matchup)
    agg = aggregate(records, "holdem_hu")["agents"]
    assert agg, f"{matchup}: no agents folded"

    compared = 0
    for who, stats in agg.items():
        counts = holdem_tally(records, who)
        assert counts["terminal_games"] > 0, f"{matchup}/{who}: no scored games"
        assert stats["win_rate"] == counts["wins"] / counts["terminal_games"]
        assert stats["mean_net_chips"] == counts["net_total"] / counts["terminal_games"]
        for verb in holdem.ACTION_VERBS:
            offered = counts[f"{verb}_offered"]
            mine = stats.get(f"{verb}_rate")
            theirs = counts[f"{verb}_chosen"] / offered if offered else None
            assert mine == theirs, f"{matchup}/{who}/{verb}: {mine} vs {theirs}"
            if offered:
                compared += 1
    assert compared >= len(holdem.ACTION_VERBS), (
        f"{matchup}: only {compared} verb rates had a non-empty denominator — "
        f"the comparison is near-vacuous"
    )


def test_the_auditors_rate_table_is_derived_from_the_game_module() -> None:
    """`verify.py` must audit exactly what the summary reports.

    red under: drop "raise" from `holdem.ACTION_VERBS`. Now that BOTH the
    summary and the auditor derive from that one tuple the drift is closed by
    construction, so this test is a pin on the derivation rather than a
    detector: its reddening mutation is restating either list by hand.
    """
    audited = {name for name, _, _ in HOLDEM_RATES if name.endswith("_rate")}
    audited -= {"win_rate", "fallback_rate"}  # game-generic, not verb rates
    declared = {f"{verb}_rate" for verb in holdem.ACTION_VERBS}
    assert audited == declared, (
        f"the auditor's verb rates {sorted(audited)} do not match the game's "
        f"{sorted(declared)} — verify.py would stop being a recomputation of "
        f"what was published"
    )

    reports_chips = any(name == "mean_net_chips" for name, _, _ in HOLDEM_RATES)
    assert reports_chips, (
        "this game's returns are chip-denominated and its summary reports "
        "mean_net_chips; an auditor that does not is not a recomputation of it"
    )


def test_every_runnable_game_has_an_audit_path() -> None:
    """A game with no `AUDITS` entry is not even offered by `--game`, so its
    archive falls through to the Cheat default — the same root as the identity
    hole `game_of` closes.

    red under: delete the `cardlang_holdem_heads_up` entry from `AUDITS`. RUN,
    not predicted: fails naming `holdem_hu` as runnable-but-unauditable.
    """
    # Both collections are keyed by the OpenSpiel SHORT NAME, which is also what
    # `--game` takes — `GAME_KEYS`' *values* are the harness's own short keys and
    # comparing against those would be comparing two different vocabularies.
    #
    # No carve-outs: `verify.py` is THE entry point for every game's
    # recomputation. Kuhn's audit has a different output shape (exploitability,
    # not counts and ratios) and lives in `verify_kuhn.py`, but it is reached
    # from here like the others.
    missing = set(GAME_KEYS) - set(AUDITS)
    assert not missing, (
        f"runnable games with no recomputation: {sorted(missing)} — their "
        f"archives would be audited with another game's rate table"
    )
    assert set(AUDITS) <= set(GAME_KEYS), (
        f"AUDITS names something the harness cannot run: "
        f"{sorted(set(AUDITS) - set(GAME_KEYS))}"
    )


def test_a_transcript_declares_its_own_game() -> None:
    """Identity comes from the DATA, so `--game` cannot be a proxy.

    The Hold'em archive resolves via its `treatment.json` sidecars (it predates
    the per-record `game` field); anything written since carries the field
    directly. The Cheat archive resolves to `None`, which is the honest answer
    for it and the reason the flag's default still stands there.
    """
    for matchup in MATCHUPS:
        path = ARCHIVE / f"{matchup}.jsonl.gz"
        if not path.is_file():
            pytest.skip("archive not present")
        assert game_of(path, _records(matchup)) == "cardlang_holdem_heads_up"

    cheat = Path(__file__).parent.parent / "results" / "transcripts"
    sample = cheat / "rule_vs_random.jsonl.gz"
    if sample.is_file():
        assert game_of(sample, list(iter_jsonl(str(sample)))) is None, (
            "the Cheat archive predates the game field and has no sidecar, so "
            "it must resolve to None and fall back to the flag — if it now "
            "resolves, this test is what tells you the fallback is dead code"
        )
    assert DEFAULT_GAME == "cardlang_cheat"


@pytest.mark.parametrize(
    ("archive", "expected"),
    [
        ("results_holdem", "cardlang_holdem_heads_up"),
        ("results_kuhn", "cardlang_kuhn_poker"),
        ("results", None),
    ],
)
def test_each_archive_resolves_to_its_own_game(archive: str, expected: str | None) -> None:
    """Every committed archive identifies itself, or is the one that honestly
    cannot and falls back to the flag.

    This is what makes ONE entry point safe. Before the archive `summary.json`
    was consulted, the Kuhn archive resolved to `None`, fell through to the
    Cheat default, and printed a real Kuhn win rate beside `0 / 0 = None` for
    every deception metric — a clean-looking audit of the wrong game.

    red under: drop the `summary.json` branch from `game_of`. RUN, not
    predicted: the `results_kuhn` row fails, resolving to None.
    """
    from ..verify import _transcripts

    root = Path(__file__).parent.parent / archive / "transcripts"
    if not root.is_dir():
        pytest.skip(f"{root} is not present")
    for path in _transcripts(root):
        assert game_of(path, _load_records(path)) == expected


def _load_records(path: Path) -> list[dict[str, object]]:
    return list(iter_jsonl(str(path)))


def test_deep_refuses_the_cheat_archive_in_its_own_voice() -> None:
    """The Cheat archive cannot be deep-audited against today's game, and the
    auditor must SAY so rather than surface an encoder error four frames down.

    A history is a sequence of action ids, so it means something only against
    the action space it was recorded in; Cheat's changed when the four-card
    play cap was removed. Pinned because a refusal nothing exercises is a
    message no one has read — and because the shallow audit, which DOES still
    cover this archive, is the remedy the message has to name.
    """
    from ..verify import deep_facts

    cheat_archive = Path(__file__).parent.parent / "results" / "transcripts"
    record = next(iter(iter_jsonl(str(cheat_archive / "rule_vs_random.jsonl.gz"))))
    with pytest.raises(SystemExit) as excinfo:
        deep_facts(record)
    message = str(excinfo.value)
    assert "four-card play cap" in message, "the refusal must name the cause"
    assert "--deep" in message and "SHALLOW" in message, (
        "the refusal must name the audit that still covers this archive"
    )
