"""The review's writer (`tools/review_record.py post`) can fail.

Completeness ledger (decisions.md "Closed-domain completeness")
-----------------------------------------------------------------
property:   `post` turns one review's findings into one review thread
            each on the pull request, at the head the review read, and
            then the Review Record the gate reads, whose CONFIRMED count
            is derived from the same findings list (ADR-0019). It posts
            nothing when the pull request's head is not the head the
            review read, and nothing further once a post fails. Every
            finding lands on a thread: on its line when the diff can
            carry a comment there, on its file when the file is in the
            diff, and otherwise on the diff's first file, naming where it
            is. A findings list outside the closed vocabulary is refused
            before anything is posted.
domain:     every finding verdict crossed with every anchor a finding can
            take (a line the diff added, a context line, a changed file's
            line no hunk shows, a changed file with no line, a file
            outside the diff with and without a line), and the patch line
            kinds a hunk holds (added, context, removed, the no-newline
            marker, a second hunk, a header with its count omitted, a
            file with no patch); beside the grid, the misuse probes: each
            closed field given a word outside its vocabulary, a field
            missing, a field unknown, and the post sequence under a moved
            head, a failed review post, a dry run, zero findings, and a
            record posted alone.
registry:   finding verdicts: `tools.review_record.FINDING_VERDICTS`;
            reachability: `tools.review_record.REACHES`; anchors:
            `tools.review_record.ANCHORS`; the record vocabulary the
            writer and the gate share:
            tests/test_review_post.py::test_the_record_written_is_the_record_the_gate_reads
held by:    Derived and Pinned -- the record's count and the thread set
            derive from one findings list in one function, and this grid
            pins the derivation; the writer and the reader share one
            vocabulary module, pinned by the round trip. That a review
            posts through the writer at all is Review-Enforced Prose (the
            review skill's "Output"), since a hand can still write a
            record.
does not prove:  that the findings list is the review's whole output, or
            that GitHub renders a thread where the payload asks -- the
            fake `gh` here records the request, and the live post on a
            pull request is the witness for the response; nor that a
            thread's disposition reply is true.
"""

from __future__ import annotations

import json
import subprocess
from typing import Any

import pytest

from tools import review_record as rr

HEAD = "a" * 40
OLD = "b" * 40

PATCH = "\n".join(
    [
        "@@ -1,4 +1,5 @@",
        " kept one",
        "-gone",
        "+added two",
        "+added three",
        " kept four",
        "\\ No newline at end of file",
        "@@ -40 +41,2 @@",
        "+added forty-one",
        " kept forty-two",
    ]
)
CHANGED = {"tools/a.py": PATCH, "docs/b.md": None}


def finding(**fields: object) -> dict[str, object]:
    base: dict[str, object] = {
        "file": "tools/a.py",
        "line": 2,
        "summary": "the summary",
        "failure_scenario": "the scenario",
        "verdict": "CONFIRMED",
        "category": "correctness",
        "reaches": "R4",
    }
    base.update(fields)
    return base


def test_commentable_lines_follow_the_new_side_of_every_hunk() -> None:
    assert rr.commentable_lines(PATCH) == frozenset({1, 2, 3, 4, 41, 42})
    assert rr.commentable_lines(None) == frozenset()
    assert rr.commentable_lines("") == frozenset()


# The anchor each finding takes, authored by hand: (file, line) -> anchor.
ANCHOR_CELLS: dict[tuple[str, int | None], str] = {
    ("tools/a.py", 2): "line",  # added
    ("tools/a.py", 4): "line",  # context
    ("tools/a.py", 42): "line",  # context in the second hunk
    ("tools/a.py", 20): "file",  # a line no hunk shows
    ("tools/a.py", None): "file",
    ("docs/b.md", 3): "file",  # a file with no patch
    ("cardlang/elsewhere.py", 7): "outside",
    ("cardlang/elsewhere.py", None): "outside",
}


@pytest.mark.parametrize("verdict", rr.FINDING_VERDICTS)
@pytest.mark.parametrize(("where", "anchor"), sorted(ANCHOR_CELLS.items(), key=str))
def test_every_finding_lands_on_a_thread(verdict: str, where: tuple[str, int | None], anchor: str) -> None:
    path, line = where
    findings = rr.parse_findings([finding(file=path, line=line, verdict=verdict)])
    payload = rr.review_payload(findings, CHANGED, HEAD, "Standard")
    assert payload is not None
    assert payload["commit_id"] == HEAD and payload["event"] == "COMMENT"
    (comment,) = payload["comments"]
    assert verdict in comment["body"] and "the scenario" in comment["body"]
    if anchor == "line":
        assert comment == {**comment, "path": path, "line": line, "side": "RIGHT"}
        assert "subject_type" not in comment
    elif anchor == "file":
        assert comment["path"] == path and comment["subject_type"] == "file"
        assert "line" not in comment
    else:
        assert comment["path"] == "tools/a.py" and comment["subject_type"] == "file"
        assert f"Outside this diff: `{path}" in comment["body"]


def test_anchor_cells_span_the_anchors() -> None:
    assert set(ANCHOR_CELLS.values()) == set(rr.ANCHORS)
    assert set(rr.FINDING_VERDICTS) == {"CONFIRMED", "PLAUSIBLE"}
    assert set(rr.REACHES) == {"R1", "R2", "R3", "R4"}


def test_no_findings_is_no_review() -> None:
    assert rr.review_payload((), CHANGED, HEAD, "Quick") is None


def test_an_empty_diff_is_refused() -> None:
    with pytest.raises(ValueError):
        rr.review_payload(rr.parse_findings([finding()]), {}, HEAD, "Quick")


@pytest.mark.parametrize(
    "fields",
    [
        {"verdict": "REFUTED"},
        {"verdict": "confirmed"},
        {"reaches": "R5"},
        {"reaches": "r4"},
        {"line": 0},
        {"line": "12"},
        {"line": True},
        {"file": ""},
        {"summary": ""},
        {"failure_scenario": 3},
        {"extra": 1},
    ],
    ids=lambda f: json.dumps(f),
)
def test_a_finding_outside_the_vocabulary_is_refused(fields: dict[str, object]) -> None:
    with pytest.raises(ValueError):
        rr.parse_findings([finding(), finding(**fields)])


@pytest.mark.parametrize("missing", sorted(finding()))
def test_a_finding_missing_a_field_is_refused(missing: str) -> None:
    bad = finding()
    del bad[missing]
    with pytest.raises(ValueError):
        rr.parse_findings([bad])


@pytest.mark.parametrize("data", [{}, "[]", None, [3]])
def test_a_findings_list_that_is_not_a_list_of_objects_is_refused(data: object) -> None:
    with pytest.raises(ValueError):
        rr.parse_findings(data)


def test_a_short_summary_rides_along() -> None:
    (parsed,) = rr.parse_findings([finding(short_summary="short")])
    assert parsed.summary == "the summary"


@pytest.mark.parametrize("lane", rr.LANES)
@pytest.mark.parametrize("tier", rr.TIERS)
@pytest.mark.parametrize("gate", rr.ARTIFACT_GATES)
@pytest.mark.parametrize("verdicts", [(), ("PLAUSIBLE",), ("CONFIRMED", "PLAUSIBLE", "CONFIRMED")])
def test_the_record_written_is_the_record_the_gate_reads(
    lane: str, tier: str, gate: str, verdicts: tuple[str, ...]
) -> None:
    findings = rr.parse_findings([finding(verdict=v) for v in verdicts])
    body = rr.record_text(HEAD, tier, gate, findings)
    comment = {"id": 1, "author_association": "OWNER", "body": body, "user": {"login": "jbgh2", "type": "User"}}
    verdict = rr.judge([comment], HEAD, lane)
    confirmed = verdicts.count("CONFIRMED")
    expected = rr._refusal(rr.Record(HEAD, tier, confirmed, gate, 1), lane) is None and rr._meets_tier(
        rr.Record(HEAD, tier, confirmed, gate, 1), lane
    )
    assert verdict.outcome == ("pass" if expected else "refused"), verdict.lines
    assert any(f"{confirmed} CONFIRMED" in line for line in verdict.lines)


class FakeGh:
    """Records every `gh` call; answers the reads the writer makes."""

    def __init__(self, head: str = HEAD, fail_on: str | None = None) -> None:
        self.head = head
        self.fail_on = fail_on
        self.calls: list[tuple[list[str], str | None]] = []

    def __call__(self, args: list[str], stdin: str | None = None) -> str:
        self.calls.append((args, stdin))
        joined = " ".join(args)
        if self.fail_on and self.fail_on in joined:
            raise subprocess.CalledProcessError(1, ["gh", *args], stderr="HTTP 422")
        if args[:2] == ["pr", "view"]:
            return self.head + "\n"
        if "pulls/7/files" in joined:
            return json.dumps([[{"filename": f, "patch": p} for f, p in CHANGED.items()]])
        if "pulls/7/reviews" in joined:
            return json.dumps({"id": 99, "html_url": "https://example.invalid/review/99"})
        return json.dumps({"id": 100, "html_url": "https://example.invalid/comment/100"})

    def posts(self) -> list[str]:
        return [a[a.index("-X") + 2] for a, _ in self.calls if "-X" in a]

    def payload(self, endpoint: str) -> Any:
        return next(json.loads(s or "") for a, s in self.calls if "-X" in a and a[a.index("-X") + 2].endswith(endpoint))


def post(gh: FakeGh, findings: list[dict[str, object]], **kw: Any) -> int:
    return rr.post(7, HEAD, "Standard", "not-triggered", rr.parse_findings(findings), repo="o/r", run=gh, **kw)


def test_the_review_posts_its_threads_then_its_record() -> None:
    gh = FakeGh()
    assert post(gh, [finding(), finding(verdict="PLAUSIBLE", line=41)]) == 0
    assert gh.posts() == ["repos/o/r/pulls/7/reviews", "repos/o/r/issues/7/comments"]
    assert len(gh.payload("reviews")["comments"]) == 2
    assert '"confirmed": 1' in gh.payload("comments")["body"]


def test_a_moved_head_posts_nothing() -> None:
    gh = FakeGh(head=OLD)
    assert post(gh, [finding()]) == 1
    assert gh.posts() == []


def test_a_failed_review_post_posts_no_record() -> None:
    gh = FakeGh(fail_on="pulls/7/reviews")
    assert post(gh, [finding()]) == 2
    assert gh.posts() == ["repos/o/r/pulls/7/reviews"]


def test_a_clean_review_posts_only_its_record() -> None:
    gh = FakeGh()
    assert post(gh, []) == 0
    assert gh.posts() == ["repos/o/r/issues/7/comments"]
    assert '"confirmed": 0' in gh.payload("comments")["body"]


def test_a_dry_run_posts_nothing() -> None:
    gh = FakeGh()
    assert post(gh, [finding()], dry_run=True) == 0
    assert gh.posts() == []


def test_a_record_posted_alone_posts_no_threads() -> None:
    gh = FakeGh()
    assert post(gh, [finding()], record_only=True) == 0
    assert gh.posts() == ["repos/o/r/issues/7/comments"]


@pytest.mark.parametrize(("tier", "gate"), [("Light", "present"), ("Quick", "skipped")])
def test_a_tier_or_gate_outside_the_vocabulary_posts_nothing(tier: str, gate: str) -> None:
    gh = FakeGh()
    with pytest.raises(ValueError):
        rr.post(7, HEAD, tier, gate, (), repo="o/r", run=gh)
    assert gh.calls == []
