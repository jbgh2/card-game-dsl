"""The merge gate's review clause: is a review on record at the merging head?

`tools/merge-gate.sh` pipes a pull request's issue comments here (the
`gh api --paginate --slurp` listing) with the head it read and the lane
`tools/lane-of.sh` printed:

    python3 tools/review_record.py --head SHA --lane C|D < comments.json

It prints its evidence lines and exits 0 only when the review the lane
requires is on record at that head (docs/harness.md, "Arming is merging";
the lane requirements are "The Merge Lanes").

Two records are read, each bound to a head:

* **The Review Record** -- the comment the `cardlang-code-review` skill
  posts (its "Output" section), whose first line is
  `<!-- cardlang-review-record:v1 {...} -->`. Only an author with write
  access (`author_association` OWNER, MEMBER or COLLABORATOR) writes one;
  anyone else's marker is not a record. The newest record naming the head
  governs. Lane D passes on any tier with zero CONFIRMED findings; Lane C
  passes on Standard or Thorough with every CONFIRMED finding filed; both
  require a Phase-0 artifact gate other than `absent`.
* **The Codex review state** -- the `codex-review-state:v1` marker the
  Codex bot keeps in its summary comment. Codex at the head with its review
  incomplete or findings unresolved refuses; a clean Codex review is
  printed as evidence and never stands in for the Review Record, because
  the lanes require a `cardlang-code-review` pass.

Fails closed: no record at the head is `absent`, a record only at older
heads is `stale` (`reviewed head X, merging head Y`), and a record or
marker it cannot read, or one outside the closed vocabulary below, is
`refused` -- never read as satisfied.

Held by: Derived and Pinned (tests/test_review_record.py) for the
predicate, bound to the head the gate reads. Which of Standard or Thorough
a Lane C change selects is Review-Enforced Prose: the tier is the review
skill's judgment of the delta, recorded by the reviewer.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from typing import Any, Literal, get_args

Tier = Literal["Quick", "Standard", "Thorough"]
ArtifactGate = Literal["present", "absent", "not-triggered"]
Lane = Literal["C", "D"]
Outcome = Literal["pass", "absent", "stale", "refused"]
TIERS: tuple[str, ...] = get_args(Tier)
ARTIFACT_GATES: tuple[str, ...] = get_args(ArtifactGate)
LANES: tuple[str, ...] = get_args(Lane)
OUTCOMES: tuple[str, ...] = get_args(Outcome)

MARKER = "cardlang-review-record:v1"
CODEX_MARKER = "codex-review-state:v1"
CODEX_LOGIN = "chatgpt-codex-connector[bot]"
TRUSTED_ASSOCIATIONS = frozenset({"OWNER", "MEMBER", "COLLABORATOR"})
RECORD_FIELDS = frozenset({"head_sha", "tier", "confirmed", "filed", "artifact_gate"})

_RECORD_RE = re.compile(r"\A\s*<!--\s*" + re.escape(MARKER) + r"\s+(\{.*?\})\s*-->", re.DOTALL)
_CODEX_RE = re.compile(r"<!--\s*" + re.escape(CODEX_MARKER) + r"\s+(\{.*?\})\s*-->", re.DOTALL)
_SHA_RE = re.compile(r"\A[0-9a-f]{40}\Z")


@dataclass(frozen=True)
class Record:
    head: str
    tier: str
    confirmed: int
    filed: tuple[int, ...]
    artifact_gate: str
    comment_id: int


@dataclass(frozen=True)
class Verdict:
    outcome: str
    lines: tuple[str, ...]


class Unreadable(Exception):
    """A marker is present and cannot be read as its vocabulary states."""


def _count(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def parse_record(payload_text: str, comment_id: int) -> Record:
    try:
        payload = json.loads(payload_text)
    except json.JSONDecodeError as err:
        raise Unreadable(f"not JSON ({err.msg})") from None
    if not isinstance(payload, dict):
        raise Unreadable("not a JSON object")
    keys = set(payload)
    if keys != RECORD_FIELDS:
        raise Unreadable(
            f"fields {sorted(keys)} are not {sorted(RECORD_FIELDS)}"
        )
    head, tier = payload["head_sha"], payload["tier"]
    confirmed, filed, gate = payload["confirmed"], payload["filed"], payload["artifact_gate"]
    if not isinstance(head, str) or not _SHA_RE.match(head):
        raise Unreadable(f"head_sha {head!r} is not a full lower-case commit sha")
    if tier not in TIERS:
        raise Unreadable(f"tier {tier!r} is not one of {', '.join(TIERS)}")
    if gate not in ARTIFACT_GATES:
        raise Unreadable(f"artifact_gate {gate!r} is not one of {', '.join(ARTIFACT_GATES)}")
    if not _count(confirmed) or confirmed < 0:
        raise Unreadable(f"confirmed {confirmed!r} is not a count")
    if not isinstance(filed, list) or not all(_count(n) and n > 0 for n in filed):
        raise Unreadable(f"filed {filed!r} is not a list of issue numbers")
    if len(set(filed)) != len(filed):
        raise Unreadable(f"filed {filed!r} names an issue twice")
    if len(filed) > confirmed:
        raise Unreadable(f"filed names {len(filed)} issues for {confirmed} CONFIRMED findings")
    return Record(head, tier, confirmed, tuple(filed), gate, comment_id)


def _flatten(comments: object) -> list[dict[str, Any]]:
    if not isinstance(comments, list):
        raise ValueError("comments must be a JSON list (pages of comments, or comments)")
    flat: list[object] = []
    for item in comments:
        flat.extend(item if isinstance(item, list) else [item])
    if not all(isinstance(c, dict) for c in flat):
        raise ValueError("every comment must be a JSON object")
    return [c for c in flat if isinstance(c, dict)]


def _order(c: dict[str, Any]) -> tuple[str, int]:
    return (str(c.get("updated_at") or c.get("created_at") or ""), int(c.get("id") or 0))


def _codex_lines(comments: list[dict[str, Any]], head: str) -> tuple[list[str], bool]:
    """Evidence lines for the Codex arm, and whether it refuses."""
    bot = [
        c for c in comments
        if (c.get("user") or {}).get("login") == CODEX_LOGIN
        and (c.get("user") or {}).get("type") == "Bot"
        and CODEX_MARKER in str(c.get("body") or "")
    ]
    if not bot:
        return ["codex: no review state on record -- not required"], False
    latest = max(bot, key=_order)
    match = _CODEX_RE.search(str(latest.get("body") or ""))
    try:
        if not match:
            raise Unreadable("marker not closed")
        state = json.loads(match.group(1))
        review = state["code_review"] if isinstance(state, dict) else None
        if not isinstance(review, dict):
            raise Unreadable("no code_review object")
        sha, status = review.get("commit_sha"), review.get("status")
        unresolved = review.get("has_unresolved_findings")
    except (Unreadable, json.JSONDecodeError, KeyError) as err:
        return [f"codex: review state in comment {latest.get('id')} unreadable ({err}) -- FAIL"], True
    if sha != head:
        return [f"codex: last reviewed {str(sha)[:12]}, not the merging head -- not read"], False
    if status != "completed":
        return [f"codex: review at head {head[:12]} is {status!r}, not completed -- FAIL"], True
    if unresolved is not False:
        return [f"codex: unresolved findings at head {head[:12]} -- FAIL"], True
    return [
        f"codex: completed at head {head[:12]}, no unresolved findings "
        "(evidence only; the lane requires the cardlang-code-review Review Record)"
    ], False


def _satisfies(record: Record, lane: str) -> str | None:
    """None when the record meets the lane, else the reason it does not."""
    if record.artifact_gate == "absent":
        return "the Phase-0 artifact gate reports the surface-totality artifacts absent"
    if lane == "D":
        if record.confirmed:
            return f"{record.confirmed} CONFIRMED finding(s); Lane D requires none"
        return None
    if record.tier == "Quick":
        return "tier Quick; Lane C requires the full review (Standard or Thorough)"
    open_findings = record.confirmed - len(record.filed)
    if open_findings:
        return f"{open_findings} CONFIRMED finding(s) neither fixed nor filed"
    return None


def judge(comments: object, head: str, lane: str) -> Verdict:
    if lane not in LANES:
        raise ValueError(f"lane {lane!r}: the gate judges a review only for lanes {', '.join(LANES)}")
    if not _SHA_RE.match(head):
        raise ValueError(f"head {head!r} is not a full lower-case commit sha")
    flat = _flatten(comments)
    lines, refused = _codex_lines(flat, head)

    records: list[tuple[tuple[str, int], Record]] = []
    for c in flat:
        if c.get("author_association") not in TRUSTED_ASSOCIATIONS:
            continue
        body = str(c.get("body") or "")
        if not body.lstrip().startswith("<!--") or MARKER not in body.split("\n", 1)[0]:
            continue
        cid = int(c.get("id") or 0)
        match = _RECORD_RE.match(body)
        try:
            if not match:
                raise Unreadable("marker not closed on a JSON object")
            records.append((_order(c), parse_record(match.group(1), cid)))
        except Unreadable as err:
            lines.append(f"review: Review Record in comment {cid} unreadable: {err} -- FAIL")
            refused = True

    at_head = [r for key, r in sorted(records, key=lambda kr: kr[0]) if r.head == head]
    if at_head:
        record = at_head[-1]
        reason = _satisfies(record, lane)
        summary = (
            f"Review Record (comment {record.comment_id}) at head {head[:12]}: tier {record.tier}, "
            f"{record.confirmed} CONFIRMED, filed {list(record.filed) or 'none'}, "
            f"artifact gate {record.artifact_gate}"
        )
        if reason is None:
            lines.append(f"review: {summary} -- ok for Lane {lane}")
        else:
            lines.append(f"review: {summary} -- FAIL ({reason})")
            refused = True
        outcome = "refused" if refused else "pass"
    elif records:
        latest = max(records, key=lambda kr: kr[0])[1]
        lines.append(
            f"review: reviewed head {latest.head[:12]}, merging head {head[:12]} -- FAIL "
            f"(the newest Review Record is comment {latest.comment_id}; review the merging head)"
        )
        outcome = "refused" if refused else "stale"
    else:
        lines.append(
            f"review: no {MARKER} comment at head {head[:12]} -- FAIL "
            "(looked for the cardlang-code-review Review Record from an author with write access)"
        )
        outcome = "refused" if refused else "absent"
    return Verdict(outcome, tuple(lines))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    parser.add_argument("--head", required=True)
    parser.add_argument("--lane", required=True)
    args = parser.parse_args(argv)
    try:
        verdict = judge(json.load(sys.stdin), args.head, args.lane)
    except (ValueError, json.JSONDecodeError) as err:
        print(f"review: cannot judge -- FAIL ({err})")
        return 2
    for line in verdict.lines:
        print(line)
    return 0 if verdict.outcome == "pass" else 1


if __name__ == "__main__":
    sys.exit(main())
