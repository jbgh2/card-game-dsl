"""The runner's budget and reporting guarantees, exercised.

A token cap that has never actually stopped a run is exactly the
implemented-but-never-executed code the next silent defect hides in, so these
drive `run_matchup` end to end against the fake provider rather than inspecting
`Budget` in isolation.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from .. import run_eval as run_eval_mod
from ..metrics import iter_jsonl
from ..run_eval import (
    Budget,
    ensure_provider,
    main,
    run_matchup,
    validate_model_refs,
)
from ..spend import Billed, Spend, SpendLog, Window, registry_spend

pytest.importorskip("pyspiel", reason="the OpenSpiel adapter needs the `openspiel` extra")

FAKE_MODEL: dict[str, Any] = {
    "kind": "fake",
    "model": "fake",
    "replies": ['{"action": 0, "reasoning": "first legal"}'],
}


def _log(tmp_path: Path) -> SpendLog:
    """A spend log under `tmp_path`, so no test writes into the committed
    results tree — which a config-derived default path would.

    A fresh object per call: two calls on one `tmp_path` share the FILE and
    not the session, which is what two invocations against one results tree
    do. A test that needs one invocation across several `run_matchup` calls
    binds the result once and passes it to each.
    """
    return SpendLog(tmp_path / "spend" / "log.jsonl")


def _config(**overrides: Any) -> dict[str, Any]:
    config: dict[str, Any] = {
        "game": "cardlang_cheat",
        "max_decisions": 400,
        "models": {"m": FAKE_MODEL},
        "matchups": [],
    }
    config.update(overrides)
    return config


def _run_dir(results_dir: Path) -> Path:
    """The single run directory `main()` just created under `results_dir`.

    Asserts there is exactly one: a test that silently read the newest of several
    would pass while the runner leaked extra directories.
    """
    from .. import layout

    runs = layout.list_runs(results_dir)
    assert len(runs) == 1, f"expected one run directory, found {[p.name for p in runs]}"
    return runs[0]


def _matchup(n: int, llm: bool) -> dict[str, Any]:
    focus = {"kind": "llm", "name": "fake_llm", "model": "m"} if llm else {"kind": "rule"}
    return {
        "name": "t",
        "n": n,
        "rotate": True,
        "agents": [focus, {"kind": "random"}, {"kind": "random"}, {"kind": "random"}],
    }


def test_offline_matchup_needs_no_provider(tmp_path: Path) -> None:
    """The acceptance-criterion-1 path: a roster naming no model builds no
    provider, so the run needs no API key and no SDK."""
    config = _config()
    matchup = _matchup(2, llm=False)
    registry: dict[str, Any] = {}
    summary = run_matchup(config, matchup, tmp_path, registry, log=_log(tmp_path))
    assert registry == {}, "an offline roster must construct no provider"
    assert summary["n_completed"] == 2
    assert summary["stopped_early"] is None
    assert summary["usage"] == {}


def test_budget_stops_the_run_and_reports_partial_n(tmp_path: Path) -> None:
    """A cap crossed mid-matchup stops cleanly BETWEEN games, and the summary
    records the completed N and the cap that stopped it — never the intended N."""
    config = _config(token_budget={"max_output_tokens": 50})
    matchup = _matchup(10, llm=True)
    summary = run_matchup(config, matchup, tmp_path, {}, log=_log(tmp_path))

    assert 0 < summary["n_completed"] < 10, "the cap neither fired nor blocked everything"
    assert summary["n_requested"] == 10
    assert summary["stopped_early"] is not None
    assert "max_output_tokens" in summary["stopped_early"]
    # The transcript on disk agrees with the reported count — a summary that
    # claimed more games than were written would be the worse failure.
    assert len(list(iter_jsonl(str(tmp_path / "transcripts" / "t.jsonl")))) == summary[
        "n_completed"
    ]


def test_budget_is_shared_across_matchups(tmp_path: Path) -> None:
    """One provider registry for the whole run, so a `max_*` ceiling is a
    ceiling for the RUN. Per-matchup providers would let a four-matchup config
    spend four times what its author wrote down."""
    config = _config(token_budget={"max_output_tokens": 10_000_000})
    first, second = _matchup(1, llm=True), _matchup(1, llm=True)
    second["name"] = "t2"
    registry: dict[str, Any] = {}
    log = _log(tmp_path)

    run_matchup(config, first, tmp_path, registry, log=log)
    assert set(registry) == {"m"}, "the first matchup builds the shared provider"
    after_first = registry["m"].usage.output_tokens
    summary = run_matchup(config, second, tmp_path, registry, log=log)
    after_second = registry["m"].usage.output_tokens

    assert after_second > after_first > 0
    # The matchup block reports its own delta; `run_total` carries the running sum.
    assert summary["usage"]["m"]["output_tokens"] == after_second - after_first
    assert summary["usage"]["m"]["run_total"]["output_tokens"] == after_second
    # And the durable record partitions the same spend exactly once: two
    # matchups, one log, no line counted twice and none missed.
    assert log.total(Window("invocation")).output_tokens == after_second
    assert registry_spend(registry) == log.appended, "billed and never written"


def _session_config(tmp_path: Path, **budget: Any) -> Path:
    """A one-LLM-matchup config on its own results tree, written to disk.

    `main()` rather than `run_matchup`, because the defect is what happens
    BETWEEN invocations and only `main` starts one.
    """
    config = _config(
        results_dir=str(tmp_path),
        max_decisions=40,
        token_budget=budget,
        matchups=[_matchup(2, llm=True)],
    )
    tmp_path.mkdir(parents=True, exist_ok=True)
    path = tmp_path / "config.yaml"
    path.write_text(json.dumps(config), encoding="utf-8")
    return path


def _completed(run: Path) -> int:
    summary = json.loads((run / "summary.json").read_text(encoding="utf-8"))
    completed: int = summary["matchups"][0]["n_completed"]
    return completed


def _stops(run: Path) -> str | None:
    summary = json.loads((run / "summary.json").read_text(encoding="utf-8"))
    stopped: str | None = summary["matchups"][0]["stopped_early"]
    return stopped


def test_a_second_invocation_stops_where_the_first_left_off(tmp_path: Path) -> None:
    """THE defect. A session is many invocations, and a windowed cap counts
    them all.

    The ceiling is exactly what one invocation of this matchup spends, so it
    is never reached WITHIN an invocation and is reached the moment a second
    one starts. Under `window: all` the first runs to completion and the
    second stops before its first game, naming the cap.

    Its twin, `test_the_default_window_still_bounds_one_invocation`, is this
    fixture with the window left out. The two differ in one config key.

    Verified against the accepted-but-ignored form of the fix — `window`
    parsed and stored but `Budget.exceeded` reading only the live registry —
    where the second invocation plays both games and reports
    `stopped_early: None`, which is the behaviour issue #219 describes.
    """
    probe = _session_config(tmp_path / "probe")
    assert main(["--config", str(probe)]) == 0
    one = json.loads(
        (_run_dir(tmp_path / "probe") / "summary.json").read_text(encoding="utf-8")
    )["run_totals"]["m"]["output_tokens"]

    config = _session_config(tmp_path, max_output_tokens=one, window="all")
    assert main(["--config", str(config)]) == 0
    assert main(["--config", str(config)]) == 0

    from .. import layout

    first, second = layout.list_runs(tmp_path)
    assert _completed(first) == 2, "the first invocation was capped, not the second"
    assert _stops(first) is None
    assert _completed(second) == 0
    assert _stops(second) is not None
    assert "max_output_tokens" in str(_stops(second))
    assert "all" in str(_stops(second)), "the stop does not say which window"


def test_the_default_window_still_bounds_one_invocation(tmp_path: Path) -> None:
    """Every shipped config names no window, so the default must not change
    what they mean: a ceiling over this process, spent again on the next."""
    probe = _session_config(tmp_path / "probe")
    assert main(["--config", str(probe)]) == 0
    one = json.loads(
        (_run_dir(tmp_path / "probe") / "summary.json").read_text(encoding="utf-8")
    )["run_totals"]["m"]["output_tokens"]

    config = _session_config(tmp_path, max_output_tokens=one)
    assert main(["--config", str(config)]) == 0
    assert main(["--config", str(config)]) == 0

    from .. import layout

    for run in layout.list_runs(tmp_path):
        assert _completed(run) == 2, "the default window reached across invocations"
        assert _stops(run) is None
    # The record was written anyway, so turning a window on later has history
    # to read rather than starting from a log nothing filled.
    log = SpendLog(layout.spend_log_path(tmp_path))
    assert log.total(Window("all")).output_tokens >= 2 * one


def test_estimate_spend_is_recorded_and_counts_toward_a_later_run(
    tmp_path: Path,
) -> None:
    """`--estimate` plays real games on a real account, so it is spend.

    Its output is scratch — a gitignored `estimate/` directory it overwrites
    in place — and that is the whole of what makes it disposable. The money is
    not.
    """
    from .. import layout

    config = _session_config(tmp_path, max_output_tokens=10**9, window="all")
    assert main(["--config", str(config), "--estimate", "2"]) == 0

    log = SpendLog(layout.spend_log_path(tmp_path))
    spent = log.total(Window("all"))
    assert spent.output_tokens > 0, "cost recon wrote nothing to the record"
    assert not (tmp_path / "runs").exists(), "an estimate is not a run"

    capped = _session_config(tmp_path, max_output_tokens=1, window="all")
    assert main(["--config", str(capped)]) == 0
    stopped = _stops(_run_dir(tmp_path))
    assert stopped is not None and "max_output_tokens" in stopped


def test_an_offline_matchup_runs_under_a_crossed_window(tmp_path: Path) -> None:
    """The no-API-key acceptance path survives a ceiling that has been reached.

    A cap gates spending, and a roster naming no model cannot spend. Without
    the exemption, `rule_vs_random` — the run that needs no credential and
    costs nothing — would refuse to play the moment a window wide enough to
    have been crossed was configured.

    red under: dropping the `if providers` guard from `run_matchup`'s cap
    check.
    """
    from .. import layout

    log = SpendLog(layout.spend_log_path(tmp_path))
    log.record(
        "earlier", "t", [Billed("m", "claude-haiku-4-5", 1, Spend(output_tokens=10**6))]
    )

    config = _config(
        results_dir=str(tmp_path),
        token_budget={"max_output_tokens": 10, "window": "all"},
        matchups=[{**_matchup(2, llm=False), "name": "offline"}],
    )
    path = tmp_path / "config.yaml"
    path.write_text(json.dumps(config), encoding="utf-8")

    assert main(["--config", str(path)]) == 0
    run = _run_dir(tmp_path)
    assert _completed(run) == 2
    assert _stops(run) is None
    assert len(list(iter_jsonl(str(run / "transcripts" / "offline.jsonl")))) == 2


def test_a_matchup_that_dies_mid_game_still_records_what_it_spent(
    tmp_path: Path,
) -> None:
    """The case a log derived from `summary.json` gets wrong.

    A provider that dies partway leaves its usage counted in memory and its
    game unwritten; the record has to carry that spend anyway, or the next
    invocation's ceiling is short by exactly the run that failed.

    red under: deleting the `flush_spend()` that follows `run_matchup`'s game
    loop. (Not the abort branch — every exit from the loop reaches the one
    after it, which is why the abort branch has no flush of its own.)
    """
    config = _config(max_decisions=400)
    matchup = _matchup(5, llm=True)
    ok = _calls_in_first_game(tmp_path) + 20
    registry: dict[str, Any] = {"m": ExplodingProvider(ok_calls=ok)}
    log = _log(tmp_path)

    summary = run_matchup(config, matchup, tmp_path, registry, log=log)

    assert summary["aborted"] is not None
    assert registry_spend(registry) == log.appended, "the dying game's spend went unwritten"
    assert log.total(Window("all")).output_tokens == registry["m"].usage.output_tokens


def test_summary_records_the_full_request_params(tmp_path: Path) -> None:
    """`params` is the reproduction recipe, so it keeps every knob the provider
    consumed — reporting the post-`pop` remainder would omit `max_tokens` from
    the record of a run it shaped."""
    model = {**FAKE_MODEL, "params": {"max_tokens": 256, "temperature": 0}}
    config = _config(models={"m": model})
    matchup = _matchup(1, llm=True)
    summary = run_matchup(config, matchup, tmp_path, {}, log=_log(tmp_path))
    # The fake provider ignores params, but the plumbing that reports them is
    # shared; the Anthropic provider's own copy is asserted below.
    assert "params" in summary["usage"]["m"]


def test_anthropic_provider_keeps_max_tokens_in_reported_params() -> None:
    """Constructed without a network call; only `__init__` runs."""
    pytest.importorskip("anthropic")
    from ..providers import AnthropicProvider

    provider = AnthropicProvider(
        "claude-haiku-4-5", {"max_tokens": 256, "temperature": 0, "max_retries": 3}
    )
    assert provider.params == {"max_tokens": 256, "temperature": 0, "max_retries": 3}


def test_unpriced_model_is_refused() -> None:
    """A typo would otherwise be costed at $0.00 in the summary."""
    pytest.importorskip("anthropic")
    from ..providers import AnthropicProvider

    with pytest.raises(ValueError, match="no published price"):
        AnthropicProvider("claude-opus-9000")


def test_roster_size_must_match_the_seats(tmp_path: Path) -> None:
    config = _config()
    matchup = _matchup(1, llm=False)
    matchup["agents"] = matchup["agents"][:3]
    with pytest.raises(ValueError, match="roster has 3 agents"):
        run_matchup(config, matchup, tmp_path, {}, log=_log(tmp_path))


def test_unknown_model_reference_is_loud() -> None:
    """Pre-flight, before any provider is constructed."""
    config = _config()
    matchup = _matchup(1, llm=True)
    matchup["agents"][0]["model"] = "nope"
    with pytest.raises(ValueError, match="not defined"):
        validate_model_refs(config, [matchup])


def test_unpriced_model_reference_dies_in_preflight() -> None:
    """A typo in a real model id is caught without constructing anything, so it
    fails the same way with or without a credential."""
    config = _config(models={"m": {"kind": "anthropic", "model": "claude-opus-9000"}})
    with pytest.raises(ValueError, match="no published price"):
        validate_model_refs(config, [_matchup(1, llm=True)])


def test_ensure_provider_memoizes_into_the_shared_registry() -> None:
    config = _config()
    registry: dict[str, Any] = {}
    first = ensure_provider(config, "m", registry)
    assert ensure_provider(config, "m", registry) is first
    assert set(registry) == {"m"}


def test_seed_range_is_checked_against_the_adapter(tmp_path: Path) -> None:
    """The adapter addresses 4096 deals; beyond that, seeds would silently wrap
    and games would replay identical hands under different indices."""
    config = _config(seeds={"start": 4090})
    matchup = _matchup(20, llm=False)
    with pytest.raises(ValueError, match="only addresses"):
        run_matchup(config, matchup, tmp_path, {}, log=_log(tmp_path))


def test_seat_rotation_moves_the_focus_agent(tmp_path: Path) -> None:
    """Position effects wash out only if the focus seat actually rotates."""
    config = _config()
    matchup = _matchup(4, llm=False)
    run_matchup(config, matchup, tmp_path, {}, log=_log(tmp_path))
    records = list(iter_jsonl(str(tmp_path / "transcripts" / "t.jsonl")))
    seats = [
        next(int(k) for k, v in r["seats"].items() if v == "rule") for r in records
    ]
    assert seats == [0, 1, 2, 3]


def test_rotation_can_be_disabled(tmp_path: Path) -> None:
    config = _config()
    matchup = _matchup(3, llm=False)
    matchup["rotate"] = False
    run_matchup(config, matchup, tmp_path, {}, log=_log(tmp_path))
    records = list(iter_jsonl(str(tmp_path / "transcripts" / "t.jsonl")))
    assert all(r["seats"]["0"] == "rule" for r in records)


@pytest.mark.parametrize(
    ("cap", "usage_kwargs", "expected"),
    [
        ({}, {"input_tokens": 10**9}, None),  # no cap configured
        ({"max_input_tokens": 100}, {"input_tokens": 99}, None),
        ({"max_input_tokens": 100}, {"input_tokens": 100}, "max_input_tokens"),
        ({"max_output_tokens": 10}, {"output_tokens": 11}, "max_output_tokens"),
        ({"max_cost_usd": 1.0}, {"input_tokens": 10**6}, "max_cost_usd"),
        ({"max_cost_usd": 10.0}, {"input_tokens": 10**6}, None),
    ],
)
def test_budget_boundaries(
    tmp_path: Path, cap: dict[str, Any], usage_kwargs: dict[str, int], expected: str | None
) -> None:
    """Each cap fires at its own boundary and not before. `claude-haiku-4-5` is
    $1/MTok in, so 10**6 input tokens is exactly $1.00.

    An empty log, so this is the in-flight spend alone — the same reading the
    default `invocation` window gives. Which spend a window ADMITS is
    test_spend.py's grid; this is the boundary of each cap over one total.
    """
    registry = _registry({"claude-haiku-4-5": usage_kwargs})
    assert Budget(**cap).exceeded(_log(tmp_path), registry_spend(registry)) == expected


def _registry(spend: dict[str, dict[str, int]]) -> dict[str, Any]:
    """A provider registry carrying the given usage, keyed by model id."""
    from ..providers import FakeProvider, Usage

    registry: dict[str, Any] = {}
    for model, usage_kwargs in spend.items():
        provider = FakeProvider(replies=["{}"])
        provider.model = model
        provider.usage = Usage(**usage_kwargs)
        registry[model] = provider
    return registry


def test_budget_sums_across_every_model_in_the_registry(tmp_path: Path) -> None:
    """The cap is a ceiling for the RUN, so it cannot be evaluated one provider at
    a time.

    Per model, a config naming three models had an effective ceiling of three
    times what its author wrote down: the frontier provider could reach the cap
    and the run would carry on into a matchup using the cheap provider, whose own
    counter started at zero. Here NEITHER model is over $1 alone; together they
    are $1.20.
    """
    registry = _registry(
        {"claude-haiku-4-5": {"input_tokens": 600_000},   # $0.60
         "claude-sonnet-5": {"input_tokens": 200_000}}    # $0.60
    )
    log = _log(tmp_path)
    assert Budget(max_cost_usd=1.0).exceeded(log, registry_spend(registry)) == "max_cost_usd"
    # Non-vacuity: the same registry is under a ceiling that genuinely clears it.
    assert Budget(max_cost_usd=2.0).exceeded(log, registry_spend(registry)) is None


def test_budget_sums_token_caps_across_models_too(tmp_path: Path) -> None:
    """Tokens are counts and add the same way dollars do."""
    registry = _registry(
        {"claude-haiku-4-5": {"input_tokens": 60, "output_tokens": 6},
         "claude-sonnet-5": {"input_tokens": 60, "output_tokens": 6}}
    )
    log = _log(tmp_path)
    assert Budget(max_input_tokens=100).exceeded(log, registry_spend(registry)) == "max_input_tokens"
    assert Budget(max_output_tokens=10).exceeded(log, registry_spend(registry)) == "max_output_tokens"
    assert (
        Budget(max_input_tokens=200, max_output_tokens=20).exceeded(
            log, registry_spend(registry)
        )
        is None
    )


def test_budget_on_an_empty_registry_and_log_is_unlimited(tmp_path: Path) -> None:
    """Nothing spent is nothing counted, however wide the window.

    An offline matchup builds no provider, and a tree nothing has run in has
    no log — the two zeros a cap must not fire on.
    """
    log = _log(tmp_path)
    assert Budget(max_cost_usd=0.01).exceeded(log, Spend()) is None
    assert Budget(max_cost_usd=0.01, window="all").exceeded(log, Spend()) is None


def _two_matchup_config(tmp_path: Path) -> tuple[dict[str, Any], Path]:
    """A config the BARE command would run: an offline matchup and an LLM one."""
    config = _config(
        results_dir=str(tmp_path),
        models={"live": {"kind": "anthropic", "model": "claude-haiku-4-5"}},
        matchups=[
            {**_matchup(2, llm=False), "name": "offline"},
            {
                "name": "online",
                "n": 2,
                "rotate": True,
                "agents": [
                    {"kind": "llm", "name": "live_llm", "model": "live"},
                    {"kind": "random"},
                    {"kind": "random"},
                    {"kind": "random"},
                ],
            },
        ],
    )
    path = tmp_path / "config.yaml"
    path.write_text(json.dumps(config), encoding="utf-8")  # YAML is a JSON superset
    return config, path


def test_bare_command_does_not_construct_providers_before_running(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Acceptance criterion 1, at the granularity the criterion states it.

    The BARE command selects EVERY matchup. The property that keeps the offline
    matchup runnable without an SDK or a credential is that a provider is
    constructed only when the matchup that names it actually starts — so the
    offline matchup completes even if provider construction is impossible.

    The discriminator is a `make_provider` that raises. Under lazy
    construction the offline transcript is written in full and only the LLM
    matchup dies; under an eager registry built across all selected matchups,
    the run dies before a single game and no transcript exists.

    Note the narrower `test_offline_matchup_needs_no_provider` cannot see this,
    and neither can a bare command passed `--matchup offline`: both narrow the
    selection so an eager registry has nothing to build. Verified against a
    reintroduced eager registry, which fails this test on the missing
    transcript.
    """
    for var in ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN", "ANTHROPIC_PROFILE"):
        monkeypatch.delenv(var, raising=False)

    def refuse(spec: dict[str, Any]) -> Any:
        raise RuntimeError("provider constructed")

    # Patched on the MODULE OBJECT, not by dotted string. A string target is
    # re-imported by name, and this package is reachable as both `llm_eval.*`
    # and `experiments.llm_eval.*`; the two resolve to distinct module objects,
    # so a string could patch one while the run under test used the other — and
    # the test would pass by never patching anything.
    monkeypatch.setattr(run_eval_mod, "make_provider", refuse)
    _, config_path = _two_matchup_config(tmp_path)

    with pytest.raises(RuntimeError, match="provider constructed"):
        main(["--config", str(config_path)])

    run = _run_dir(tmp_path)
    transcript = run / "transcripts" / "offline.jsonl"
    assert transcript.exists(), (
        "the offline matchup did not run — provider construction happened "
        "before it, so acceptance criterion 1 depends on LLM credentials"
    )
    assert len(list(iter_jsonl(str(transcript)))) == 2

    # And its DERIVED numbers survived too: the summary is written after every
    # matchup, so a later matchup dying does not discard the completed ones.
    summary = json.loads((run / "summary.json").read_text(encoding="utf-8"))
    assert [m["matchup"] for m in summary["matchups"]] == ["offline"]
    assert summary["matchups"][0]["n_completed"] == 2


def test_offline_only_selection_writes_a_clean_summary(tmp_path: Path) -> None:
    """The command the README gives for the no-API run, end to end."""
    _, config_path = _two_matchup_config(tmp_path)
    assert main(["--config", str(config_path), "--matchup", "offline"]) == 0
    run = _run_dir(tmp_path)
    assert len(list(iter_jsonl(str(run / "transcripts" / "offline.jsonl")))) == 2
    summary = json.loads((run / "summary.json").read_text(encoding="utf-8"))
    assert summary["run_totals"] == {}, "an offline run must construct no provider"
    assert summary["matchups"][0]["agents"]["rule"]["games_scored"] == 2


def test_preflight_validates_matchups_it_will_not_construct(tmp_path: Path) -> None:
    """A bad model reference in an LLM matchup is caught before any game runs,
    even though nothing is constructed for it."""
    config, _ = _two_matchup_config(tmp_path)
    validate_model_refs(config, config["matchups"])  # the good config passes
    config["matchups"][1]["agents"][0]["model"] = "nope"
    with pytest.raises(ValueError, match="not defined"):
        validate_model_refs(config, config["matchups"])


def test_per_game_token_usage_is_recorded_and_aggregated(tmp_path: Path) -> None:
    """Spec §5 asks for tokens per game, not only per run. The transcript
    carries each game's own tally and `aggregate` divides by games played."""
    from ..metrics import aggregate

    config = _config()
    matchup = _matchup(2, llm=True)
    run_matchup(config, matchup, tmp_path, {}, log=_log(tmp_path))
    records = list(iter_jsonl(str(tmp_path / "transcripts" / "t.jsonl")))

    assert len(records) == 2
    for record in records:
        tally = record["usage"]["fake_llm"]
        assert tally["llm_calls"] > 0
        assert tally["input_tokens"] > 0
        # One call per decision when nothing needs retrying.
        llm_decisions = sum(1 for d in record["decisions"] if d["agent"] == "fake_llm")
        assert tally["llm_calls"] == llm_decisions

    stats = aggregate(records)["agents"]["fake_llm"]
    assert stats["llm_calls"] == sum(r["usage"]["fake_llm"]["llm_calls"] for r in records)
    assert stats["llm_calls_per_game"] == stats["llm_calls"] / 2
    assert stats["input_tokens_per_game"] == stats["input_tokens"] / 2
    # A non-model agent contributes no tally, and 0.0 is the CORRECT reading
    # here — it played games and spent nothing, so the denominator is real.
    # (Contrast the challenge rates, where an empty denominator gives None.)
    assert aggregate(records)["agents"]["random"]["games"] == 6
    assert aggregate(records)["agents"]["random"]["input_tokens_per_game"] == 0.0


def test_retries_are_billed_twice_in_the_per_game_tally(tmp_path: Path) -> None:
    """A retry is two billed calls, and the tally says so — an undercount here
    would make the cost estimate optimistic exactly when the prompt is failing."""
    model = {**FAKE_MODEL, "replies": ["nonsense", '{"action": 0, "reasoning": ""}']}
    config = _config(models={"m": model}, max_decisions=20)
    matchup = _matchup(1, llm=True)
    run_matchup(config, matchup, tmp_path, {}, log=_log(tmp_path))
    record = next(iter(iter_jsonl(str(tmp_path / "transcripts" / "t.jsonl"))))
    llm_decisions = sum(1 for d in record["decisions"] if d["agent"] == "fake_llm")
    assert record["usage"]["fake_llm"]["llm_calls"] > llm_decisions


def test_transcript_lines_are_valid_json_records(tmp_path: Path) -> None:
    config = _config()
    matchup = _matchup(2, llm=False)
    run_matchup(config, matchup, tmp_path, {}, log=_log(tmp_path))
    text = (tmp_path / "transcripts" / "t.jsonl").read_text(encoding="utf-8")
    lines = [line for line in text.splitlines() if line.strip()]
    assert len(lines) == 2
    for line in lines:
        record = json.loads(line)
        assert set(record) >= {"seed", "seats", "history", "decisions", "returns"}
        assert len(record["history"]) == record["num_decisions"]


# --- a game that dies mid-matchup ------------------------------------------


class ExplodingProvider:
    """A provider that works for `ok_calls` and then raises, standing in for the
    real failure this guards: a terminal `400 — you have reached your specified
    API usage limits` partway through a multi-hour run."""

    def __init__(self, ok_calls: int, message: str = "usage limit reached") -> None:
        from ..providers import Usage

        self.model = "fake"
        self.params: dict[str, Any] = {}
        self.usage = Usage()
        self._ok = ok_calls
        self._message = message

    def complete(self, prompt: str) -> Any:
        from ..providers import Reply

        if self.usage.calls >= self._ok:
            raise RuntimeError(self._message)
        reply = Reply(text='{"action": 0, "reasoning": "x"}', input_tokens=10, output_tokens=5)
        self.usage.add(reply)
        return reply


def _calls_in_first_game(tmp_path: Path) -> int:
    """How many model calls one game of this fixture takes.

    Derived rather than hard-coded: the exploder has to die during a LATER game
    for these tests to mean anything, and a magic constant would silently start
    dying in game one the moment episode lengths shifted — turning the tests
    green-but-vacuous.
    """
    probe = tmp_path / "probe"
    # Its own log, or the probe's spend would sit in the record the calling
    # test then reads and every count would be one game too high.
    run_matchup(
        _config(max_decisions=400), _matchup(1, llm=True), probe, {}, log=_log(probe)
    )
    rec = next(iter(iter_jsonl(str(probe / "transcripts" / "t.jsonl"))))
    return int(rec["usage"]["fake_llm"]["llm_calls"])


def test_completed_games_keep_their_summary_when_a_later_game_dies(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """THE fix. A game that raises must not take the COMPLETED games' derived
    numbers with it.

    Verified against the reverted behaviour: without the try/except in
    `run_matchup`, the exception propagates out and this test fails on the raise
    itself, with no summary to inspect.
    """
    config = _config(max_decisions=400)
    matchup = _matchup(5, llm=True)
    ok = _calls_in_first_game(tmp_path) + 20  # dies partway through game 2
    registry: dict[str, Any] = {"m": ExplodingProvider(ok_calls=ok)}

    summary = run_matchup(config, matchup, tmp_path, registry, log=_log(tmp_path))

    assert summary["aborted"] is not None
    assert "usage limit reached" in summary["aborted"]
    assert 0 < summary["n_completed"] < 5, "the provider died at the wrong point to test this"
    # The completed games are both on disk AND aggregated.
    assert len(list(iter_jsonl(str(tmp_path / "transcripts" / "t.jsonl")))) == summary["n_completed"]
    assert summary["agents"]["fake_llm"]["games"] == summary["n_completed"]
    assert summary["agents"]["fake_llm"]["plays"] > 0
    # The traceback is re-printed, so nothing is hidden by the catch.
    assert "RuntimeError" in capsys.readouterr().err


def test_the_aborted_game_leaves_no_record(tmp_path: Path) -> None:
    """The game that raised produced NO record, so it is not counted at all — a
    half-played game must never appear as a loss.

    Note this is distinct from TRUNCATION: a game that hits `max_decisions` is a
    legitimate recorded outcome with `terminal=False`, and the fixture produces
    those. What must be absent is the seed the exploder killed.
    """
    config = _config(max_decisions=400)
    matchup = _matchup(5, llm=True)
    ok = _calls_in_first_game(tmp_path) + 20
    registry: dict[str, Any] = {"m": ExplodingProvider(ok_calls=ok)}
    summary = run_matchup(config, matchup, tmp_path, registry, log=_log(tmp_path))
    recs = list(iter_jsonl(str(tmp_path / "transcripts" / "t.jsonl")))
    assert len(recs) == summary["n_completed"]
    # Seeds run 0..n_completed-1; the seed that died is absent entirely.
    assert [r["seed"] for r in recs] == list(range(len(recs)))
    assert summary["agents"]["fake_llm"]["games"] == len(recs)
    # Truncated games ARE recorded (and excluded from win rates elsewhere);
    # only the aborted one is missing.
    assert summary["agents"]["fake_llm"]["games_scored"] == sum(r["terminal"] for r in recs)


def test_abort_writes_the_summary_and_skips_later_matchups(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Whole-run behaviour: `summary.json` lands with the partial block, the
    later matchups are skipped (a dead credential would fail them identically,
    just slower), and the exit code is non-zero."""
    config = _config(
        results_dir=str(tmp_path),
        max_decisions=400,
        matchups=[
            {**_matchup(5, llm=True), "name": "first"},
            {**_matchup(5, llm=True), "name": "second"},
        ],
    )
    config_path = tmp_path / "config.yaml"
    config_path.write_text(json.dumps(config), encoding="utf-8")
    ok = _calls_in_first_game(tmp_path) + 20
    monkeypatch.setattr(
        run_eval_mod, "make_provider", lambda spec: ExplodingProvider(ok_calls=ok)
    )

    assert main(["--config", str(config_path)]) == 1, "an aborted run must exit non-zero"

    run = _run_dir(tmp_path)
    summary = json.loads((run / "summary.json").read_text(encoding="utf-8"))
    assert [m["matchup"] for m in summary["matchups"]] == ["first"], (
        "the second matchup ran anyway — a dead credential would fail it too"
    )
    assert summary["matchups"][0]["aborted"] is not None
    assert summary["matchups"][0]["n_completed"] > 0
    assert not (run / "transcripts" / "second.jsonl").exists()


def test_clean_run_reports_no_abort(tmp_path: Path) -> None:
    """The field is present and None on a healthy run, so a consumer can read it
    unconditionally rather than probing for its existence."""
    summary = run_matchup(_config(), _matchup(2, llm=False), tmp_path, {}, log=_log(tmp_path))
    assert summary["aborted"] is None


def test_resume_appends_only_the_missing_games(tmp_path: Path) -> None:
    """Finishing a matchup that died partway must not re-play what succeeded."""
    config = _config()
    first = {**_matchup(3, llm=False), "n": 5, "resume_from": 0}
    run_matchup(config, {**first, "n": 3}, tmp_path, {}, log=_log(tmp_path))
    before = list(iter_jsonl(str(tmp_path / "transcripts" / "t.jsonl")))
    assert [r["seed"] for r in before] == [0, 1, 2]

    summary = run_matchup(config, {**first, "n": 5, "resume_from": 3}, tmp_path, {}, log=_log(tmp_path))
    after = list(iter_jsonl(str(tmp_path / "transcripts" / "t.jsonl")))
    assert [r["seed"] for r in after] == [0, 1, 2, 3, 4]
    # The three original records are untouched, byte for byte.
    assert after[:3] == before
    assert summary["games_this_invocation"] == 2
    assert summary["n_completed"] == 5, "the summary covers the WHOLE matchup"
    assert summary["agents"]["rule"]["games"] == 5


def test_resume_reproduces_what_a_full_run_would_have_done(tmp_path: Path) -> None:
    """The resumed games are bit-identical to the ones a single full run would
    have produced — same seed AND same seat rotation, which is a function of the
    game index, not of position within the invocation."""
    full = run_matchup(
        _config(),
        {**_matchup(5, llm=False), "n": 5},
        tmp_path / "full",
        {},
        # Its own record: the two runs below are an independent reproduction
        # of this one, and one shared log would fold both into a single tree's
        # spend the moment either roster named a model.
        log=_log(tmp_path / "full"),
    )
    a = list(iter_jsonl(str(tmp_path / "full" / "transcripts" / "t.jsonl")))

    part = tmp_path / "part"
    part_log = _log(part)
    run_matchup(_config(), {**_matchup(3, llm=False), "n": 3}, part, {}, log=part_log)
    run_matchup(
        _config(),
        {**_matchup(5, llm=False), "n": 5, "resume_from": 3},
        part,
        {},
        log=part_log,
    )
    b = list(iter_jsonl(str(part / "transcripts" / "t.jsonl")))

    assert len(a) == len(b) == 5
    for x, y in zip(a, b, strict=True):
        assert x["seed"] == y["seed"]
        assert x["seats"] == y["seats"], "seat rotation diverged on resume"
        assert x["history"] == y["history"], "the resumed game played differently"
    assert full["n_completed"] == 5


def test_resume_refuses_a_mismatched_transcript(tmp_path: Path) -> None:
    """Appending onto the wrong prefix would silently duplicate games and the
    result would still look like a valid transcript."""
    run_matchup(_config(), {**_matchup(2, llm=False), "n": 2}, tmp_path, {}, log=_log(tmp_path))
    with pytest.raises(ValueError, match="cannot resume"):
        run_matchup(_config(), {**_matchup(5, llm=False), "n": 5, "resume_from": 4}, tmp_path, {}, log=_log(tmp_path))


def test_resume_without_a_transcript_is_refused(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="nothing to resume"):
        run_matchup(_config(), {**_matchup(5, llm=False), "n": 5, "resume_from": 3}, tmp_path, {}, log=_log(tmp_path))


def test_transcripts_read_identically_from_gzip(tmp_path: Path) -> None:
    """Committed transcripts are gzipped (12-21x); the audit path must read them
    directly, or a reviewer has to unzip before checking anything."""
    import gzip
    import shutil

    from ..verify import _load, _transcripts, _stem

    run_matchup(_config(), _matchup(2, llm=False), tmp_path, {}, log=_log(tmp_path))
    plain = tmp_path / "transcripts" / "t.jsonl"
    gz = plain.with_suffix(".jsonl.gz")
    with plain.open("rb") as src, gzip.open(gz, "wb") as dst:
        shutil.copyfileobj(src, dst)

    assert list(iter_jsonl(str(plain))) == list(iter_jsonl(str(gz)))
    assert _load(plain) == _load(gz)
    assert _stem(gz) == _stem(plain) == "t"
    # Both present: the matchup is listed ONCE, preferring the fresher plain file.
    assert _transcripts(tmp_path / "transcripts") == [plain]
    plain.unlink()
    assert _transcripts(tmp_path / "transcripts") == [gz]


def test_verify_agrees_with_aggregate_for_multi_seat_agents(tmp_path: Path) -> None:
    """The audit must reach the SAME denominators as the thing it audits.

    Three seats share the `random` label in every shipped matchup. A tally that
    counted one of them would report a third of the baseline's plays, windows and
    wins — quietly, and only for the multi-seat agents, which is exactly where
    nobody would look.
    """
    from ..metrics import aggregate
    from ..verify import tally

    run_matchup(_config(), _matchup(3, llm=False), tmp_path, {}, log=_log(tmp_path))
    records = list(iter_jsonl(str(tmp_path / "transcripts" / "t.jsonl")))
    agg = aggregate(records)["agents"]

    for who in ("rule", "random"):
        c = tally(records, who)
        a = agg[who]
        assert c["games"] == a["games"], f"{who}: seat-games disagree"
        assert c["wins"] == a["wins"], f"{who}: wins disagree"
        assert c["decisions"] == a["decisions"], f"{who}: decisions disagree"
        assert c["plays"] == a["plays"], f"{who}: plays disagree"
        assert c["windows"] == a["challenge_opportunities"], f"{who}: windows disagree"
        assert c["provable_faced"] == a["provable_opportunities"]
        assert c["provable_caught"] == a["provable_caught"]
    # And the fixture really is multi-seat, or the test proves nothing.
    assert agg["random"]["games"] == 3 * len(records)


def test_shipped_config_carries_no_resume_marker() -> None:
    """`resume_from` is an operational marker for ONE invocation, not config.

    Committed, it fails on every fresh checkout — the uncompressed prefix it
    resumes from is gitignored — and in an all-matchup run it fails only after
    the expensive matchups have already been paid for.
    """
    import yaml

    config = yaml.safe_load(
        Path("experiments/llm_eval/config.yaml").read_text(encoding="utf-8")
    )
    carried = [m["name"] for m in config["matchups"] if m.get("resume_from")]
    assert not carried, f"matchups ship a stale resume marker: {carried}"


def test_shipped_config_names_only_registered_arms() -> None:
    """A typo in `arm:` must not silently run the control.

    `build_agent` passes the string straight through to `LLMAgent`, which refuses
    an unregistered name — but only once it is constructed, which for the
    committed config is a fact about the file, not about a run. An arm that
    resolved to the default would produce a complete, plausible, multi-hour run
    of the control reported under the arm's name.
    """
    import yaml

    from ..prompts import RESPONSE_ARMS

    config = yaml.safe_load(
        Path("experiments/llm_eval/config.yaml").read_text(encoding="utf-8")
    )
    named = {
        spec["arm"]
        for matchup in config["matchups"]
        for spec in matchup["agents"]
        if "arm" in spec
    }
    assert named, "no matchup names an arm — this check has stopped checking"
    assert named <= set(RESPONSE_ARMS), (
        f"config names unregistered arms: {sorted(named - set(RESPONSE_ARMS))}"
    )
    # The retired flag must not linger: `build_agent` ignores it silently now.
    stale = [
        matchup["name"]
        for matchup in config["matchups"]
        for spec in matchup["agents"]
        if "neutral" in spec
    ]
    assert not stale, f"matchups still carry the retired `neutral:` flag: {stale}"
