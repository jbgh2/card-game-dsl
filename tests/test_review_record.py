"""The merge gate's review clause (`tools/review_record.py`) can fail.

Completeness ledger (decisions.md "Closed-domain completeness")
-----------------------------------------------------------------
property:   `judge` passes a Merge Lane C or D pull request only when the
            latest Review Record a trusted author posted names the merging
            head and satisfies the lane: Lane D, any tier with no CONFIRMED
            finding; Lane C, a tier above Quick with every CONFIRMED finding
            filed; for both, a Phase-0 artifact gate other than `absent`.
            Every other comment set lands in exactly one of the three
            failing outcomes, and a marker it cannot read is `refused`,
            never skipped.
domain:     every tier crossed with every artifact-gate verdict, every lane
            the gate judges, and the three findings shapes a record at the
            head can carry (clean, all filed, one left open), with the
            passing cells authored as a literal set; beside the grid, the
            misuse probes: each closed field given a word outside its
            vocabulary, the record forged by an author with no write access,
            the Codex marker forged by a non-bot, a record at an older head,
            a newer record at the head governing an older one, a Codex
            review at the head standing alone, and Codex reporting
            unresolved findings at the head.
registry:   tiers: `tools.review_record.TIERS`; artifact-gate verdicts:
            `tools.review_record.ARTIFACT_GATES`; lanes:
            `tools.review_record.LANES`; outcomes:
            `tools.review_record.OUTCOMES`; the review skill's written
            vocabulary:
            tests/test_review_record.py::test_the_skill_writes_the_vocabulary_the_gate_reads
held by:    Derived and Pinned -- the gate derives the predicate from the
            pull request's own comments, bound to the head it reads, and
            this grid pins the derivation; the vocabulary is a `Literal`
            the parser refuses outside of, which cannot be a rung higher
            because the record arrives as text a reviewer wrote. Which of
            Standard or Thorough a Lane C change selects is Review-Enforced
            Prose: the selection is the review skill's judgment of the
            delta, and the record carries the tier the reviewer ran.
does not prove:  that the review a record describes actually ran, or ran
            honestly -- the gate reads a trusted author's claim and binds it
            to a head, and a collaborator writing a false record passes it;
            nor that a filed issue number names an open issue about the
            finding; nor that a review left as a pull-request review body,
            rather than an issue comment, is read -- only issue comments are
            the record's channel.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from tools import review_record as rr

HEAD = "a" * 40
OLD = "b" * 40

# The passing cells, authored by hand: (tier, artifact gate, lane, findings).
PASSING = frozenset(
    {
        ("Quick", "present", "D", "clean"),
        ("Quick", "not-triggered", "D", "clean"),
        ("Standard", "present", "D", "clean"),
        ("Standard", "not-triggered", "D", "clean"),
        ("Thorough", "present", "D", "clean"),
        ("Thorough", "not-triggered", "D", "clean"),
        ("Standard", "present", "C", "clean"),
        ("Standard", "not-triggered", "C", "clean"),
        ("Standard", "present", "C", "filed"),
        ("Standard", "not-triggered", "C", "filed"),
        ("Thorough", "present", "C", "clean"),
        ("Thorough", "not-triggered", "C", "clean"),
        ("Thorough", "present", "C", "filed"),
        ("Thorough", "not-triggered", "C", "filed"),
    }
)

FINDINGS: dict[str, tuple[int, list[int]]] = {
    "clean": (0, []),
    "filed": (2, [1101, 1102]),
    "open": (2, [1101]),
}

_ids = iter(range(1, 10**6))


def comment(
    body: str,
    *,
    login: str = "jbgh2",
    user_type: str = "User",
    association: str = "OWNER",
    created_at: str = "2026-11-01T10:00:00Z",
) -> dict[str, Any]:
    return {
        "id": next(_ids),
        "user": {"login": login, "type": user_type},
        "author_association": association,
        "body": body,
        "created_at": created_at,
        "updated_at": created_at,
    }


def record_body(**fields: object) -> str:
    payload: dict[str, object] = {
        "head_sha": HEAD,
        "tier": "Standard",
        "confirmed": 0,
        "filed": [],
        "artifact_gate": "not-triggered",
    }
    payload.update(fields)
    return f"<!-- {rr.MARKER} {json.dumps(payload)} -->\n\n## Review Record\n"


def codex_body(sha: str | None, *, unresolved: bool, status: str = "completed") -> str:
    state = {
        "code_review": {
            "commit_sha": sha,
            "has_any_findings": unresolved,
            "has_unresolved_findings": unresolved,
            "status": status,
        },
        "security_review": {
            "commit_sha": None,
            "has_any_findings": None,
            "has_unresolved_findings": None,
            "status": None,
        },
    }
    return f"<!-- codex-pull-request-review-summary -->\n<!-- {rr.CODEX_MARKER} {json.dumps(state)} -->\n"


def codex(body: str, **kw: Any) -> dict[str, Any]:
    return comment(body, login=rr.CODEX_LOGIN, user_type="Bot", association="NONE", **kw)


GRID = [
    (tier, gate, lane, shape)
    for tier in rr.TIERS
    for gate in rr.ARTIFACT_GATES
    for lane in rr.LANES
    for shape in FINDINGS
]


@pytest.mark.parametrize(("tier", "gate", "lane", "shape"), GRID)
def test_grid(tier: str, gate: str, lane: str, shape: str) -> None:
    confirmed, filed = FINDINGS[shape]
    body = record_body(tier=tier, artifact_gate=gate, confirmed=confirmed, filed=filed)
    verdict = rr.judge([comment(body)], HEAD, lane)
    expected = "pass" if (tier, gate, lane, shape) in PASSING else "refused"
    assert verdict.outcome == expected, verdict.lines


def test_grid_spans_the_vocabulary() -> None:
    assert {c[0] for c in PASSING} <= set(rr.TIERS)
    assert {c[1] for c in PASSING} <= set(rr.ARTIFACT_GATES)
    assert {c[2] for c in PASSING} == set(rr.LANES)
    assert set(rr.OUTCOMES) == {"pass", "absent", "stale", "refused"}


def test_no_comments_is_absent_naming_the_arm() -> None:
    verdict = rr.judge([], HEAD, "D")
    assert verdict.outcome == "absent"
    assert any(rr.MARKER in line for line in verdict.lines)


def test_record_at_older_head_is_stale_naming_both_heads() -> None:
    verdict = rr.judge([comment(record_body(head_sha=OLD))], HEAD, "D")
    assert verdict.outcome == "stale"
    assert any(f"reviewed head {OLD[:12]}, merging head {HEAD[:12]}" in line for line in verdict.lines)


def test_newest_record_at_the_head_governs() -> None:
    older = comment(record_body(confirmed=1), created_at="2026-11-01T09:00:00Z")
    newer = comment(record_body(confirmed=0), created_at="2026-11-01T11:00:00Z")
    assert rr.judge([newer, older], HEAD, "D").outcome == "pass"
    assert rr.judge([comment(record_body(confirmed=0), created_at="2026-11-01T09:00:00Z"),
                     comment(record_body(confirmed=1), created_at="2026-11-01T11:00:00Z")],
                    HEAD, "D").outcome == "refused"


def test_record_at_head_beats_an_older_head_record() -> None:
    stale = comment(record_body(head_sha=OLD), created_at="2026-11-01T12:00:00Z")
    fresh = comment(record_body(), created_at="2026-11-01T09:00:00Z")
    assert rr.judge([stale, fresh], HEAD, "D").outcome == "pass"


@pytest.mark.parametrize("association", ["NONE", "CONTRIBUTOR", "FIRST_TIME_CONTRIBUTOR", "FIRST_TIMER"])
def test_record_from_an_author_without_write_access_is_not_read(association: str) -> None:
    verdict = rr.judge([comment(record_body(), login="drive-by", association=association)], HEAD, "D")
    assert verdict.outcome == "absent"


@pytest.mark.parametrize(
    "fields",
    [
        {"tier": "Light"},
        {"tier": "quick"},
        {"artifact_gate": "skipped"},
        {"confirmed": -1},
        {"confirmed": True},
        {"confirmed": "0"},
        {"filed": [0]},
        {"filed": ["1101"]},
        {"filed": [1101, 1101], "confirmed": 2},
        {"filed": [1101], "confirmed": 0},
        {"head_sha": "abc123"},
        {"head_sha": HEAD.upper()},
        {"extra": 1},
    ],
    ids=lambda f: json.dumps(f),
)
def test_a_record_outside_the_vocabulary_is_refused(fields: dict[str, object]) -> None:
    verdict = rr.judge([comment(record_body(**fields))], HEAD, "D")
    assert verdict.outcome == "refused", verdict.lines


@pytest.mark.parametrize("missing", ["head_sha", "tier", "confirmed", "filed", "artifact_gate"])
def test_a_record_missing_a_field_is_refused(missing: str) -> None:
    payload = json.loads(record_body().split(rr.MARKER, 1)[1].split("-->", 1)[0])
    del payload[missing]
    body = f"<!-- {rr.MARKER} {json.dumps(payload)} -->"
    assert rr.judge([comment(body)], HEAD, "D").outcome == "refused"


def test_a_marker_quoted_below_the_first_line_is_not_a_record() -> None:
    quoted = comment("The gate reads this:\n\n```\n" + record_body() + "```\n")
    assert rr.judge([quoted], HEAD, "D").outcome == "absent"


def test_an_unparseable_trusted_record_is_refused_even_beside_a_good_one() -> None:
    broken = comment(f"<!-- {rr.MARKER} {{not json -->")
    assert rr.judge([broken, comment(record_body())], HEAD, "D").outcome == "refused"


def test_a_clean_codex_review_at_the_head_does_not_stand_alone() -> None:
    verdict = rr.judge([codex(codex_body(HEAD, unresolved=False))], HEAD, "D")
    assert verdict.outcome == "absent"
    assert any("codex" in line for line in verdict.lines)


def test_codex_unresolved_findings_at_the_head_refuse() -> None:
    comments = [codex(codex_body(HEAD, unresolved=True)), comment(record_body())]
    assert rr.judge(comments, HEAD, "D").outcome == "refused"


def test_codex_unresolved_findings_at_an_older_head_are_not_read() -> None:
    comments = [codex(codex_body(OLD, unresolved=True)), comment(record_body())]
    assert rr.judge(comments, HEAD, "D").outcome == "pass"


def test_codex_review_still_running_at_the_head_refuses() -> None:
    comments = [codex(codex_body(HEAD, unresolved=False, status="in_progress")), comment(record_body())]
    assert rr.judge(comments, HEAD, "D").outcome == "refused"


def test_a_forged_codex_marker_is_not_read() -> None:
    forged = comment(codex_body(HEAD, unresolved=True), login="chatgpt-codex-connector", association="NONE")
    assert rr.judge([forged, comment(record_body())], HEAD, "D").outcome == "pass"


def test_an_unreadable_codex_marker_is_refused() -> None:
    broken = codex(f"<!-- {rr.CODEX_MARKER} {{\"code_review\": 3}} -->")
    assert rr.judge([broken, comment(record_body())], HEAD, "D").outcome == "refused"


def test_pages_from_a_slurped_listing_flatten() -> None:
    pages = [[comment("hello")], [comment(record_body())]]
    assert rr.judge(pages, HEAD, "D").outcome == "pass"


@pytest.mark.parametrize("lane", ["A", "B", "c", ""])
def test_a_lane_the_gate_does_not_judge_is_refused_loudly(lane: str) -> None:
    with pytest.raises(ValueError):
        rr.judge([comment(record_body())], HEAD, lane)


def test_the_skill_writes_the_vocabulary_the_gate_reads() -> None:
    skill = (Path(__file__).resolve().parents[1] / ".claude/skills/cardlang-code-review/SKILL.md").read_text()
    output = skill.split("## Output", 1)[1].split("\n## ", 1)[0]
    assert rr.MARKER in output
    for word in (*rr.TIERS, *rr.ARTIFACT_GATES, "head_sha", "tier", "confirmed", "filed", "artifact_gate"):
        assert f"`{word}`" in output, word
