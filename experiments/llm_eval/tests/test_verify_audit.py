"""The audit path, executed — and the pack/auditor contract, pinned.

`verify.py` exists to recompute the published numbers with its OWN arithmetic,
so a bug in `metrics.aggregate` cannot hide behind a checker that shares its
code. That is a real claim and it was unfalsifiable: `holdem_tally`, `AUDITS`,
`HOLDEM_RATES`, the `--game` selector and the `--deep` refusal were reached by
nothing in either suite, so any divergence between the two folds shipped green.

Two properties here, and the second is why the first could go wrong unnoticed:

1. The two folds AGREE over the committed archive. That cashes the independence
   claim: they read different sources — `aggregate` takes the pack's `facts`,
   `holdem_tally` the referee's own `legal`/`action` record — so agreement is
   evidence, not a tautology.
2. The auditor's rate table is DERIVED from the pack, not restated beside it.
   `packs.py` declares what a game reports and `verify.py` restated it in three
   places; dropping a verb from the pack left 233 tests and mypy green while the
   published summary lost a rate the auditor kept printing.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from ..metrics import aggregate, iter_jsonl
from ..packs import PACKS
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
    pack = PACKS["cardlang_holdem_heads_up"]
    records = _records(matchup)
    agg = aggregate(records, pack.action_verbs, pack.reports_chip_delta)["agents"]
    assert agg, f"{matchup}: no agents folded"

    compared = 0
    for who, stats in agg.items():
        counts = holdem_tally(records, who)
        assert counts["terminal_games"] > 0, f"{matchup}/{who}: no scored games"
        assert stats["win_rate"] == counts["wins"] / counts["terminal_games"]
        assert stats["mean_net_chips"] == counts["net_total"] / counts["terminal_games"]
        for verb in pack.action_verbs:
            offered = counts[f"{verb}_offered"]
            mine = stats.get(f"{verb}_rate")
            theirs = counts[f"{verb}_chosen"] / offered if offered else None
            assert mine == theirs, f"{matchup}/{who}/{verb}: {mine} vs {theirs}"
            if offered:
                compared += 1
    assert compared >= len(pack.action_verbs), (
        f"{matchup}: only {compared} verb rates had a non-empty denominator — "
        f"the comparison is near-vacuous"
    )


def test_the_auditors_rate_table_is_derived_from_the_pack() -> None:
    """`verify.py` must audit exactly what `packs.py` says is reported.

    red under: drop "raise" from `HOLDEM_HEADS_UP.action_verbs`. RUN, not
    predicted: this fails naming `raise_rate` as audited-but-not-reported, where
    before the whole experiments suite stayed green and only the published
    summary quietly lost the rate.
    """
    pack = PACKS["cardlang_holdem_heads_up"]
    audited = {name for name, _, _ in HOLDEM_RATES if name.endswith("_rate")}
    audited -= {"win_rate", "fallback_rate"}  # game-generic, not verb rates
    declared = {f"{verb}_rate" for verb in pack.action_verbs}
    assert audited == declared, (
        f"the auditor's verb rates {sorted(audited)} do not match the pack's "
        f"{sorted(declared)} — verify.py would stop being a recomputation of "
        f"what was published"
    )

    reports_chips = any(name == "mean_net_chips" for name, _, _ in HOLDEM_RATES)
    assert reports_chips == pack.reports_chip_delta, (
        "the auditor and the pack disagree on whether this game's returns are "
        "chip-denominated"
    )


def test_every_pack_has_an_audit_path() -> None:
    """A pack with no `AUDITS` entry is not even offered by `--game`, so its
    archive falls through to the Cheat default — the same root as the identity
    hole `game_of` closes.

    red under: delete the `cardlang_holdem_heads_up` entry from `AUDITS`. RUN,
    not predicted: fails naming it as packed-but-unauditable.
    """
    missing = set(PACKS) - set(AUDITS)
    assert not missing, (
        f"packed games with no recomputation: {sorted(missing)} — their "
        f"archives would be audited with another game's rate table"
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
