"""The gate's `check` job goes to the laptop when the laptop will finish it first.

`tools/ci-route.sh` picks the runner for the merge gate's `check` job: the
self-hosted pool (the operator's laptop) or a GitHub-hosted runner
(docs/harness.md, "The physical layer"; ADR-0022). A wrong pick has no
error to show for itself. Sent to a sleeping laptop, a head waits for a lid
to open; sent to a hosted runner past a free laptop, it takes the slow lane
for nothing. So the pick is a pure function of stated facts, and this module
crosses those facts.

Contract (decisions.md "Closed-domain completeness", write-time triage)
-----------------------------------------------------------------------
Assumes:      `ci-route.sh --decide` runs the same jq program the route job
              runs live; the live path only gathers the facts and sends the
              probe.
Establishes:  one of three answers for every fact set -- `laptop`, `hosted`,
              or `probe` (ask the laptop, then decide again) -- with the
              reason beside it.
Now illegal:  a forced lane the script does not name passing as `auto`; a
              job status the script has not classified counting as nothing.

Completeness ledger
-------------------
property:   the pick is `laptop` exactly when the laptop is known alive and
            its load plus one gate job fits inside the hosted lane's time;
            `probe` exactly when nothing yet shows the laptop alive or
            silent; `hosted` otherwise.
domain:     the forced lane {auto, laptop, hosted, anything else} x the
            probe {not sent, answered, silent} x what each other run of the
            workflow contributes {nothing, a pool job running, a pool job
            waiting, an older run still routing}. The job-status axis is
            GitHub's own six values, enumerated in `_JOB_STATUSES`.
registry:   `_JOB_STATUSES` is GitHub's documented job status set; the
            script classifies by exclusion (running, finished, everything
            else waits), so a seventh value lands as a waiting job, the
            direction that errs toward the hosted lane.
held by:    a Pin (this grid). The decision is one jq program with one
            caller; no type can hold a shell pipeline.
does not prove:  that the facts are true. The live gather reads GitHub's
            run and job lists, and a run whose route has just finished can
            show its `check` job for a moment with no labels, which counts
            as nothing. Nor that a laptop which answered the probe stays
            awake for the job it is then given.
red under:  `test_one_job_ahead_fits_and_two_do_not` fails if the load sum
            drops the waiting jobs; `test_a_silent_laptop_is_never_picked`
            fails if a silent probe falls through to the load comparison;
            `test_every_job_status_is_classified` fails if a status is
            dropped from the waiting side.
"""

from __future__ import annotations

import json
import pathlib
import subprocess
from typing import NamedTuple

import pytest

_REPO = pathlib.Path(__file__).resolve().parent.parent
_SCRIPT = _REPO / "tools" / "ci-route.sh"

_POOL = ["self-hosted", "cardlang"]
_HOSTED = ["macos-latest"]
_NOW = 1_800_000_000
_ME = 500

# GitHub's job `status` values (REST: "List jobs for a workflow run").
_JOB_STATUSES = ("queued", "in_progress", "completed", "waiting", "requested", "pending")

Job = dict[str, object]
Run = dict[str, object]


class _Pick(NamedTuple):
    returncode: int
    lane: str
    reason: str
    stderr: str


def _iso(minutes_ago: float) -> str:
    import datetime as dt

    when = dt.datetime.fromtimestamp(_NOW - int(minutes_ago * 60), tz=dt.timezone.utc)
    return when.strftime("%Y-%m-%dT%H:%M:%SZ")


def _job(name: str, status: str, labels: list[str], minutes_ago: float | None = None) -> Job:
    return {
        "name": name,
        "status": status,
        "labels": labels,
        "started_at": None if minutes_ago is None else _iso(minutes_ago),
    }


def _decided(run_id: int, check: Job) -> Run:
    return {"id": run_id, "jobs": [_job("route", "completed", ["ubuntu-latest"], 30), check]}


def _running(run_id: int, minutes_in: float) -> Run:
    return _decided(run_id, _job("check", "in_progress", _POOL, minutes_in))


def _waiting(run_id: int, status: str = "queued") -> Run:
    return _decided(run_id, _job("check", status, _POOL))


def _routing(run_id: int, status: str = "in_progress") -> Run:
    return {
        "id": run_id,
        "jobs": [_job("route", status, ["ubuntu-latest"]), _job("check", "waiting", [])],
    }


def _pick(runs: list[Run], probe: str | None = None, force: str = "auto") -> _Pick:
    facts = {
        "force": force,
        "me": _ME,
        "now": _NOW,
        "laptop_minutes": 20,
        "hosted_minutes": 55,
        "stale_minutes": 45,
        "probe": probe,
        "runs": runs,
    }
    proc = subprocess.run(
        [str(_SCRIPT), "--decide"],
        input=json.dumps(facts),
        capture_output=True,
        text=True,
        check=False,
        cwd=str(_REPO),
    )
    lane, _, reason = proc.stdout.rstrip("\n").partition("\t")
    return _Pick(proc.returncode, lane, reason, proc.stderr)


def _lane(runs: list[Run], probe: str | None = None, force: str = "auto") -> str:
    pick = _pick(runs, probe, force)
    assert pick.returncode == 0, pick.stderr
    assert pick.reason, "every pick states its reason"
    return pick.lane


def test_an_idle_pool_is_asked_before_it_is_trusted() -> None:
    assert _lane([]) == "probe"


def test_a_laptop_that_answers_takes_the_job() -> None:
    assert _lane([], probe="answered") == "laptop"


def test_a_silent_laptop_is_never_picked() -> None:
    assert _lane([], probe="silent") == "hosted"
    assert _lane([_waiting(400)], probe="silent") == "hosted"
    assert _lane([_running(400, minutes_in=50)], probe="silent") == "hosted"


def test_a_running_gate_job_shows_the_laptop_alive_without_a_probe() -> None:
    assert _lane([_running(400, minutes_in=2)]) == "laptop"


def test_one_job_ahead_fits_and_two_do_not() -> None:
    # 20 for the job itself, against 55 on the hosted lane.
    assert _lane([_running(400, minutes_in=2)]) == "laptop"  # 18 + 20
    assert _lane([_running(400, minutes_in=2), _waiting(401)]) == "hosted"  # 18 + 20 + 20
    assert _lane([_running(400, minutes_in=18), _waiting(401)]) == "laptop"  # 2 + 20 + 20
    assert _lane([_waiting(400)], probe="answered") == "laptop"  # 20 + 20
    assert _lane([_waiting(400), _waiting(401)], probe="answered") == "hosted"  # 40 + 20


def test_the_boundary_goes_to_the_laptop() -> None:
    assert _lane([_running(400, minutes_in=5), _waiting(401)]) == "laptop"  # 15 + 20 + 20 == 55
    assert _lane([_running(400, minutes_in=4), _waiting(401)]) == "hosted"  # 16 + 20 + 20 == 56


def test_a_job_running_past_the_stale_bound_proves_nothing() -> None:
    assert _lane([_running(400, minutes_in=50)]) == "probe"
    # An answer while that record still says running means the record is dead.
    assert _lane([_running(400, minutes_in=50)], probe="answered") == "laptop"


def test_an_older_run_still_routing_counts_as_a_job_ahead() -> None:
    assert _lane([_routing(400)], probe="answered") == "laptop"
    assert _lane([_routing(400), _routing(401, status="queued")], probe="answered") == "hosted"
    assert _lane([_routing(400), _running(401, minutes_in=2)]) == "hosted"


def test_an_older_run_with_no_jobs_yet_counts_as_a_job_ahead() -> None:
    bare: list[Run] = [{"id": 400, "jobs": []}, {"id": 401, "jobs": []}]
    assert _lane(bare, probe="answered") == "hosted"


def test_a_younger_run_still_routing_yields_to_this_one() -> None:
    assert _lane([_routing(600), _routing(601)], probe="answered") == "laptop"


def test_this_run_does_not_count_itself() -> None:
    assert _lane([_routing(_ME), _waiting(_ME)], probe="answered") == "laptop"


def test_jobs_on_the_hosted_lane_are_not_laptop_load() -> None:
    hosted = _decided(400, _job("check", "in_progress", _HOSTED, 2))
    assert _lane([hosted]) == "probe"
    assert _lane([hosted, hosted | {"id": 401}], probe="answered") == "laptop"


def test_a_run_that_skipped_the_gate_is_not_laptop_load() -> None:
    canary: Run = {
        "id": 400,
        "jobs": [
            _job("route", "completed", []),
            _job("check", "completed", []),
            _job("canary", "in_progress", ["ubuntu-latest"], 40),
        ],
    }
    assert _lane([canary, canary | {"id": 401}], probe="answered") == "laptop"


@pytest.mark.parametrize("status", _JOB_STATUSES)
def test_every_job_status_is_classified(status: str) -> None:
    pair = [
        _decided(400, _job("check", status, _POOL, 2)),
        _decided(401, _job("check", status, _POOL, 2)),
    ]
    expected = {
        # Two running jobs cannot be on one runner; the sum still holds: 18 + 18 + 20.
        "in_progress": "hosted",
        "completed": "laptop",
    }.get(status, "hosted")
    assert _lane(pair, probe="answered") == expected


@pytest.mark.parametrize(
    ("force", "probe", "expected"),
    [
        ("hosted", "answered", "hosted"),
        ("hosted", None, "hosted"),
        ("laptop", "silent", "laptop"),
        ("laptop", None, "laptop"),
        ("", None, "probe"),
    ],
)
def test_a_forced_lane_wins(force: str, probe: str | None, expected: str) -> None:
    assert _lane([], probe=probe, force=force) == expected


@pytest.mark.parametrize("force", ["Hosted", "github", "off", "auto "])
def test_an_unknown_forced_lane_is_refused_by_name(force: str) -> None:
    pick = _pick([], force=force)
    assert pick.returncode == 2
    assert "CI_ROUTE" in pick.stderr
    for valid in ("auto", "laptop", "hosted"):
        assert valid in pick.stderr
