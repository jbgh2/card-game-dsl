# ADR-0022: The merge gate runs on the laptop when the laptop will finish first, and on a hosted runner otherwise

- **Status:** Accepted
- **Date:** 2026-11-10
- **Ruled by:** the operator, on the harness desk's measurement of the gate's queue waits
- **Record:** issue #278 (the options, the measurements and the ruling); the PR that lands this record
- **Governs:** harness.md, "The physical layer" ("a GitHub-hosted macOS runner when the pool is asleep or full")

## Context

The gate's `check` job ran only on a self-hosted runner on the operator's
laptop. Over the 178 `check` jobs that reached a verdict between 2026-10-16
and 2026-11-09, queue wait came to 77.7 hours: 64% behind another gate job,
and 36% with no gate job running, the runner asleep or offline. The median
wait was 1.5 minutes and the longest 783; fifteen runs waited over an hour.
A green job took a median of 19 minutes. The repo is public, so standard
hosted runners carry no minute charge. The operator, on what hurt: "It
doesn't happen often but it's a pain when I travel or when I have lots of
builds going".

The whole gate was then measured on both hosted platforms, each at every
core it offers (workflow run 42964833213, 2026-11-11), against the pool's
green run on main of 2026-11-09:

| Runner | Passed | Skipped | Test step |
| --- | --- | --- | --- |
| the pool, 8 workers | 38911 | 44 | 26 min |
| hosted macOS, 3 cores | 38911 | 44 | 52 min |
| hosted Linux, 4 cores | 38877 | 78 | 64 min |

## Decision

"I prefer C so I can use the Github hosted runners as well as the machine"
(the operator, 2026-11-10). Both lanes stand, and a route job picks one per
run: the pool when it is awake and will finish the job first, a hosted
macOS runner when it is asleep or full.

## Alternatives

- **Hosted only.** Lost: it gives up the fast lane, 26 minutes of tests
  against 52.
- **A second always-on machine.** Lost: hardware and its upkeep, and a
  second runner only halves a burst.
- **Hosted Linux as the second lane.** Lost on the measurement: it skips
  34 tests the pool runs (`tests/test_war_room_progress.py` is
  Darwin-only), so a head judged there is judged on less, and it was 12
  minutes slower. The weekly canary keeps Linux honest.
- **The runners API as the routing signal.** Not taken: only a token with
  repository administration read can list runners, which is a secret in
  the operator's hand. A one-step probe job on the pool answers the same
  question with the workflow's own token.
- **A manual switch alone.** Lost: an unplanned closed lid is the case
  where nobody is there to flip it. The switch stays as the override.

## Consequences

- `tools/ci-route.sh` owns the pick and `tests/test_ci_route.py` crosses
  its facts. Branch protection still requires one check, `check`,
  whichever lane ran it.
- A `route` job that fails fails `check`. A required check skipped behind
  a failed job reads as passing to branch protection, so `check` runs and
  fails instead.
- The probe runs at the `ci-probe-anchor` tag, so its check lands on a
  commit that is no pull request's head. Without the tag every run takes
  the hosted lane, with a warning on the run.
- The repository variable `CI_ROUTE` forces a lane, and setting it is the
  operator's.
- A lid closed mid-job leaves a job record that still reads as running.
  A run routed to the pool in those minutes waits for the lid; once the
  record ends, the route asks the pool directly and gets no answer.
- Deliberately not decided: whether a fork's pull request gets a hosted
  run, and whether the Standing Roles move off the laptop.
