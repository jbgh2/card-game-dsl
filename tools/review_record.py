"""The Review Record: written by the review, read by the merge gate.

The review posts through `post`, the one writer (the `cardlang-code-review`
skill's "Output"):

    python3 tools/review_record.py post --pr N --head SHA --tier T \
        --artifact-gate G findings.json [--dry-run] [--record-only]

`findings.json` is the review's findings list (`file`, `line`, `summary`,
`failure_scenario`, `verdict`, `category`, `reaches`). Each finding
becomes one review thread at the head the review read -- on its line when
the diff carries a comment there, on its file when the file is in the
diff, and otherwise on the diff's first file naming where it is -- so a
finding's disposition is its thread's, exactly as for Codex (ADR-0019;
docs/harness.md, "Review threads"). The Review Record follows, its
CONFIRMED count derived from the same list. Nothing is posted when the
pull request is not at the head the review read, both before and after
the diff is read, and nothing further once a post fails.

`tools/merge-gate.sh` pipes a pull request's issue comments to `judge`
(the `gh api --paginate --slurp` listing) with the head it read and the
lane `tools/lane-of.sh` printed:

    python3 tools/review_record.py judge --head SHA --lane C|D < comments.json

It prints its evidence lines and exits 0 only when the review the lane
requires is on record at that head (docs/harness.md, "Arming is merging";
the lane requirements are "The Merge Lanes"). Either record below is a
review on record; every record at the head must also allow the lane.

Two records are read, each bound to a head:

* **The Review Record** -- the comment `post` writes, whose first line is
  `<!-- cardlang-review-record:v2 {...} -->`. Only an author with write
  access (`author_association` OWNER, MEMBER or COLLABORATOR) writes one;
  anyone else's marker is not a record. Every record naming the head is
  read, and a later one never clears an earlier one's findings, because a
  CONFIRMED finding is fixed only by a new head. Lane D refuses any
  record at the head that carries a CONFIRMED finding; Lane C needs a
  record at Standard or Thorough unless Codex reviewed the head, and
  leaves the findings to their threads; both refuse a record whose
  Phase-0 artifact gate is `absent`. A record is read as it stands, edits
  included.
* **The Codex review state** -- the `codex-review-state:v1` marker the
  Codex bot keeps in its summary comment, newest comment only. A review
  it completed at the head is a review on record for either lane
  (ADR-0018). A marker it cannot read refuses, at any head; Codex still
  running at the head refuses. Its findings are review threads, which the
  gate's thread clause owns (the marker's `has_unresolved_findings` does
  not clear when the threads resolve), so they are printed as evidence
  here, and a Codex review never clears a Review Record's findings.

Fails closed: no record at the head is `absent`, records only at older
heads are `stale` (`reviewed head X, merging head Y`), and a record or
marker it cannot read, or one outside the closed vocabulary below, is
`refused` -- never read as satisfied.

Held by: Derived and Pinned (tests/test_review_record.py) for the
predicate, bound to the head the gate reads, and for the writer, whose
record count and threads derive from one findings list
(tests/test_review_post.py). Review-Enforced Prose holds two residuals
the record cannot carry: which of Standard or Thorough a Lane C change
selects (the review skill's judgment of the delta), and that a record was
written by `post` rather than by hand. The gate runs this module under
the system `python3`, so it stays stdlib-only and parses at Python 3.9
(pinned in the same module).
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from dataclasses import dataclass
from typing import Any, Callable, Literal, Mapping, Optional, Sequence, get_args

Tier = Literal["Quick", "Standard", "Thorough"]
ArtifactGate = Literal["present", "absent", "not-triggered"]
Lane = Literal["C", "D"]
Outcome = Literal["pass", "absent", "stale", "refused"]
FindingVerdict = Literal["CONFIRMED", "PLAUSIBLE"]
Reach = Literal["R1", "R2", "R3", "R4"]
Anchor = Literal["line", "file", "outside"]
TIERS: tuple[str, ...] = get_args(Tier)
ARTIFACT_GATES: tuple[str, ...] = get_args(ArtifactGate)
LANES: tuple[str, ...] = get_args(Lane)
OUTCOMES: tuple[str, ...] = get_args(Outcome)
FINDING_VERDICTS: tuple[str, ...] = get_args(FindingVerdict)
REACHES: tuple[str, ...] = get_args(Reach)
ANCHORS: tuple[str, ...] = get_args(Anchor)

MARKER = "cardlang-review-record:v2"
CODEX_MARKER = "codex-review-state:v1"
CODEX_LOGIN = "chatgpt-codex-connector[bot]"
TRUSTED_ASSOCIATIONS = frozenset({"OWNER", "MEMBER", "COLLABORATOR"})
RECORD_FIELDS = frozenset({"head_sha", "tier", "confirmed", "artifact_gate"})
FINDING_FIELDS = frozenset({"file", "line", "summary", "failure_scenario", "verdict", "category", "reaches"})
FINDING_OPTIONAL = frozenset({"short_summary"})

_RECORD_RE = re.compile(r"\A\s*<!--\s*" + re.escape(MARKER) + r"\s+(\{.*?\})\s*-->", re.DOTALL)
_CODEX_RE = re.compile(r"<!--\s*" + re.escape(CODEX_MARKER) + r"\s+(\{.*?\})\s*-->", re.DOTALL)
_SHA_RE = re.compile(r"\A[0-9a-f]{40}\Z")


@dataclass(frozen=True)
class Record:
    head: str
    tier: str
    confirmed: int
    artifact_gate: str
    comment_id: int


@dataclass(frozen=True)
class Finding:
    file: str
    line: Optional[int]
    summary: str
    failure_scenario: str
    verdict: str
    category: str
    reaches: str


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
    confirmed, gate = payload["confirmed"], payload["artifact_gate"]
    if not isinstance(head, str) or not _SHA_RE.match(head):
        raise Unreadable(f"head_sha {head!r} is not a full lower-case commit sha")
    if tier not in TIERS:
        raise Unreadable(f"tier {tier!r} is not one of {', '.join(TIERS)}")
    if gate not in ARTIFACT_GATES:
        raise Unreadable(f"artifact_gate {gate!r} is not one of {', '.join(ARTIFACT_GATES)}")
    if not _count(confirmed) or confirmed < 0:
        raise Unreadable(f"confirmed {confirmed!r} is not a count")
    return Record(head, tier, confirmed, gate, comment_id)


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


def _codex_lines(comments: list[dict[str, Any]], head: str) -> tuple[list[str], bool, str | None]:
    """Evidence lines for the Codex arm, whether it refuses, and the head it reviewed."""
    bot = [
        c for c in comments
        if (c.get("user") or {}).get("login") == CODEX_LOGIN
        and (c.get("user") or {}).get("type") == "Bot"
        and CODEX_MARKER in str(c.get("body") or "")
    ]
    if not bot:
        return ["codex: no review state on record"], False, None
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
        return [f"codex: review state in comment {latest.get('id')} unreadable ({err}) -- FAIL"], True, None
    if not isinstance(sha, str) or not _SHA_RE.match(sha):
        return [f"codex: no reviewed commit in comment {latest.get('id')} ({sha!r}) -- not read"], False, None
    if sha != head:
        return [f"codex: last reviewed {sha[:12]}, not the merging head -- not read"], False, sha
    if status != "completed":
        return [f"codex: review at head {head[:12]} is {status!r}, not completed -- FAIL"], True, None
    found = "reports findings (the thread clause owns them)" if unresolved is not False else "no findings"
    return [f"codex: completed at head {head[:12]}, {found} -- review on record"], False, sha


def _refusal(record: Record, lane: str) -> str | None:
    """None when the record's findings and artifact gate allow the lane."""
    if record.artifact_gate == "absent":
        return "the Phase-0 artifact gate reports the surface-totality artifacts absent"
    if lane == "D" and record.confirmed:
        return f"{record.confirmed} CONFIRMED finding(s); Lane D requires none"
    return None


def _meets_tier(record: Record, lane: str) -> bool:
    return lane == "D" or record.tier != "Quick"


def judge(comments: object, head: str, lane: str) -> Verdict:
    if lane not in LANES:
        raise ValueError(f"lane {lane!r}: the gate judges a review only for lanes {', '.join(LANES)}")
    if not _SHA_RE.match(head):
        raise ValueError(f"head {head!r} is not a full lower-case commit sha")
    flat = _flatten(comments)
    lines, refused, codex_head = _codex_lines(flat, head)
    codex_at_head = codex_head == head

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

    at_head = [r for _, r in sorted(records, key=lambda kr: kr[0]) if r.head == head]
    if at_head or codex_at_head:
        for record in at_head:
            reason = _refusal(record, lane)
            summary = (
                f"Review Record (comment {record.comment_id}) at head {head[:12]}: tier {record.tier}, "
                f"{record.confirmed} CONFIRMED (their threads carry the dispositions), "
                f"artifact gate {record.artifact_gate}"
            )
            lines.append(f"review: {summary} -- {'ok' if reason is None else f'FAIL ({reason})'}")
            refused = refused or reason is not None
        if not codex_at_head and not any(_meets_tier(r, lane) for r in at_head):
            lines.append(
                f"review: no record at head {head[:12]} ran Standard or Thorough -- FAIL "
                "(Lane C requires the full review, or Codex's)"
            )
            refused = True
        outcome = "refused" if refused else "pass"
    elif records or codex_head:
        reviewed: list[tuple[str, str]] = []
        if records:
            latest = max(records, key=lambda kr: kr[0])[1]
            reviewed.append((latest.head, f"the newest Review Record is comment {latest.comment_id}"))
        if codex_head:
            reviewed.append((codex_head, "the Codex review state"))
        for old, source in reviewed:
            lines.append(
                f"review: reviewed head {old[:12]}, merging head {head[:12]} -- FAIL "
                f"({source}; review the merging head)"
            )
        outcome = "refused" if refused else "stale"
    else:
        lines.append(
            f"review: no {MARKER} comment and no completed Codex review at head {head[:12]} -- FAIL "
            "(looked for the cardlang-code-review Review Record from an author with write access, "
            "and the Codex bot's review state)"
        )
        outcome = "refused" if refused else "absent"
    return Verdict(outcome, tuple(lines))


def _text(value: object, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} {value!r} is not a non-empty string")
    return value


def parse_findings(data: object) -> tuple[Finding, ...]:
    """The review's findings list, refused outside its closed vocabulary."""
    if not isinstance(data, list) or not all(isinstance(f, dict) for f in data):
        raise ValueError("findings must be a JSON list of objects")
    findings = []
    for n, raw in enumerate(data, 1):
        keys = set(raw)
        if not FINDING_FIELDS <= keys or not keys <= FINDING_FIELDS | FINDING_OPTIONAL:
            raise ValueError(f"finding {n}: fields {sorted(keys)} are not {sorted(FINDING_FIELDS)}")
        line = raw["line"]
        if line is not None and (not _count(line) or line < 1):
            raise ValueError(f"finding {n}: line {line!r} is not a line number or null")
        if raw["verdict"] not in FINDING_VERDICTS:
            raise ValueError(f"finding {n}: verdict {raw['verdict']!r} is not one of {', '.join(FINDING_VERDICTS)}")
        if raw["reaches"] not in REACHES:
            raise ValueError(f"finding {n}: reaches {raw['reaches']!r} is not one of {', '.join(REACHES)}")
        findings.append(
            Finding(
                file=_text(raw["file"], f"finding {n}: file"),
                line=line,
                summary=_text(raw["summary"], f"finding {n}: summary"),
                failure_scenario=_text(raw["failure_scenario"], f"finding {n}: failure_scenario"),
                verdict=raw["verdict"],
                category=_text(raw["category"], f"finding {n}: category"),
                reaches=raw["reaches"],
            )
        )
    return tuple(findings)


_HUNK_RE = re.compile(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,\d+)? @@")


def commentable_lines(patch: Optional[str]) -> frozenset[int]:
    """The new-side lines of a file's patch a review comment can sit on."""
    lines: set[int] = set()
    new = 0
    for text in (patch or "").split("\n"):
        hunk = _HUNK_RE.match(text)
        if hunk:
            new = int(hunk.group(1))
        elif new and text[:1] in ("+", " "):
            lines.add(new)
            new += 1
    return frozenset(lines)


def _where(finding: Finding) -> str:
    return f"{finding.file}:{finding.line}" if finding.line is not None else finding.file


def _thread_body(finding: Finding) -> str:
    return (
        f"**{finding.verdict}** -- {finding.reaches}, {finding.category} -- `{_where(finding)}`\n\n"
        f"{finding.summary}\n\n**Failure scenario:** {finding.failure_scenario}\n\n"
        "Reply with its disposition -- fixed (the commit), filed (the issue), refuted (the executed "
        'evidence) or escalated -- then resolve the thread (docs/harness.md, "Review threads").'
    )


def review_payload(
    findings: Sequence[Finding], patches: Mapping[str, Optional[str]], head: str, tier: str
) -> Optional[dict[str, Any]]:
    """The pull-request review holding one thread per finding; None for no findings."""
    if not findings:
        return None
    if not patches:
        raise ValueError("the pull request changes no file, so no thread can be anchored")
    first = next(iter(patches))
    threads: list[dict[str, Any]] = []
    for finding in findings:
        body = _thread_body(finding)
        if finding.file in patches:
            if finding.line is not None and finding.line in commentable_lines(patches[finding.file]):
                threads.append({"path": finding.file, "subject": "LINE", "line": finding.line, "side": "RIGHT",
                                "body": body})
            else:
                threads.append({"path": finding.file, "subject": "FILE", "body": body})
        else:
            threads.append({"path": first, "subject": "FILE",
                            "body": f"Outside this diff: `{_where(finding)}`.\n\n{body}"})
    confirmed = sum(f.verdict == "CONFIRMED" for f in findings)
    return {
        "commit_id": head,
        "event": "COMMENT",
        "body": (
            f"`cardlang-code-review` at tier {tier} read head `{head[:12]}`: {len(findings)} finding(s), "
            f"{confirmed} CONFIRMED, one thread each. The Review Record follows as a comment."
        ),
        "threads": threads,
    }


def record_text(head: str, tier: str, artifact_gate: str, findings: Sequence[Finding]) -> str:
    """The Review Record comment, its count derived from the findings it posts."""
    if tier not in TIERS:
        raise ValueError(f"tier {tier!r} is not one of {', '.join(TIERS)}")
    if artifact_gate not in ARTIFACT_GATES:
        raise ValueError(f"artifact gate {artifact_gate!r} is not one of {', '.join(ARTIFACT_GATES)}")
    if not _SHA_RE.match(head):
        raise ValueError(f"head {head!r} is not a full lower-case commit sha")
    confirmed = sum(f.verdict == "CONFIRMED" for f in findings)
    payload = {"head_sha": head, "tier": tier, "confirmed": confirmed, "artifact_gate": artifact_gate}
    listed = "".join(f"\n- **{f.verdict}** ({f.reaches}) `{_where(f)}` -- {f.summary}" for f in findings)
    return (
        f"<!-- {MARKER} {json.dumps(payload)} -->\n\n## Review Record\n\n"
        f"`cardlang-code-review` at tier **{tier}** read head `{head}`: {len(findings)} finding(s), "
        f"{confirmed} CONFIRMED; artifact gate `{artifact_gate}`. Each finding is a review thread on "
        f"this pull request, and its disposition is the thread's.\n{listed}\n"
    )


Gh = Callable[[list[str], Optional[str]], str]

# The REST review endpoint takes no file-level comment, so every thread is
# added to a pending review through GraphQL, and the review is submitted
# only once all of them are in.
_ADD_THREAD = (
    "mutation($review: ID!, $path: String!, $body: String!, $line: Int, $side: DiffSide, "
    "$subject: PullRequestReviewThreadSubjectType) { addPullRequestReviewThread(input: "
    "{pullRequestReviewId: $review, path: $path, body: $body, line: $line, side: $side, "
    "subjectType: $subject}) { thread { id } } }"
)


def _gh(args: list[str], stdin: Optional[str] = None) -> str:
    done = subprocess.run(["gh", *args], input=stdin, capture_output=True, text=True, check=True)
    return done.stdout


def _response(out: str) -> dict[str, Any]:
    try:
        data = json.loads(out)
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


def _failure(err: subprocess.CalledProcessError) -> str:
    return f"gh {' '.join(str(a) for a in err.cmd[1:5])} failed ({(err.stderr or '').strip()})"


def _post_review(pr: int, review: dict[str, Any], repo: str, run: Gh) -> Optional[str]:
    """Post the review's threads; the review's URL, or None with nothing left posted."""
    reviews = f"repos/{repo}/pulls/{pr}/reviews"
    try:
        pending = _response(run(["api", "-X", "POST", reviews, "--input", "-"],
                                json.dumps({"commit_id": review["commit_id"], "comments": []})))
    except subprocess.CalledProcessError as err:
        print(f"post: {_failure(err)} -- nothing posted (a pending review of yours on the pull request "
              "blocks a new one: submit or delete it first)")
        return None
    review_id, node = pending.get("id"), pending.get("node_id")
    if not isinstance(review_id, int) or not isinstance(node, str):
        print("post: the pending review's id is unreadable -- nothing submitted; delete your pending review "
              "on the pull request, then post again")
        return None
    try:
        for thread in review["threads"]:
            variables = {"review": node, "path": thread["path"], "body": thread["body"],
                         "subject": thread["subject"], "line": thread.get("line"), "side": thread.get("side")}
            run(["api", "graphql", "--input", "-"], json.dumps({"query": _ADD_THREAD, "variables": variables}))
        submitted = _response(run(["api", "-X", "POST", f"{reviews}/{review_id}/events", "--input", "-"],
                                  json.dumps({"event": review["event"], "body": review["body"]})))
    except subprocess.CalledProcessError as err:
        try:
            run(["api", "-X", "DELETE", f"{reviews}/{review_id}"], None)
            left = "the pending review is deleted"
        except subprocess.CalledProcessError:
            left = f"delete pending review {review_id} by hand"
        print(f"post: {_failure(err)} -- nothing posted; {left}; post again")
        return None
    url = str(submitted.get("html_url") or f"review {review_id}")
    print(f"post: {len(review['threads'])} thread(s) in {url}")
    return url


def post(
    pr: int,
    head: str,
    tier: str,
    artifact_gate: str,
    findings: Sequence[Finding],
    *,
    repo: str,
    run: Gh = _gh,
    dry_run: bool = False,
    record_only: bool = False,
) -> int:
    """Post the review's threads, then its record; 0 posted, 1 not posted, 2 a post failed."""
    record = record_text(head, tier, artifact_gate, findings)
    view = ["pr", "view", str(pr), "--repo", repo, "--json", "headRefOid", "--jq", ".headRefOid"]
    try:
        heads = [run(view, None).strip()]
        review = None
        if not record_only:
            pages = json.loads(run(["api", "--paginate", "--slurp", f"repos/{repo}/pulls/{pr}/files"], None))
            heads.append(run(view, None).strip())
            patches = {f["filename"]: f.get("patch") for f in _flatten(pages)}
            review = review_payload(findings, patches, head, tier)
    except subprocess.CalledProcessError as err:
        print(f"post: {_failure(err)} -- nothing posted")
        return 2
    moved = next((h for h in heads if h != head), None)
    if moved is not None:
        print(f"post: the review read {head[:12]}, the pull request is at {moved[:12]} -- "
              "nothing posted; review the current head")
        return 1
    if dry_run:
        print(json.dumps({"review": review, "record": record}, indent=2))
        return 0
    if review is not None and _post_review(pr, review, repo, run) is None:
        return 2
    try:
        posted = _response(run(["api", "-X", "POST", f"repos/{repo}/issues/{pr}/comments", "--input", "-"],
                               json.dumps({"body": record})))
    except subprocess.CalledProcessError as err:
        again = "rerun with --record-only, since the threads are posted" if review is not None else "post again"
        print(f"post: {_failure(err)} -- the Review Record is not posted; {again}")
        return 2
    print(f"post: Review Record {posted.get('html_url') or 'posted'}")
    return 0


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    commands = parser.add_subparsers(dest="command", required=True)
    judging = commands.add_parser("judge", help="the merge gate's review clause")
    judging.add_argument("--head", required=True)
    judging.add_argument("--lane", required=True)
    posting = commands.add_parser("post", help="post a review's threads and its Review Record")
    posting.add_argument("--pr", type=int, required=True)
    posting.add_argument("--head", required=True)
    posting.add_argument("--tier", required=True)
    posting.add_argument("--artifact-gate", required=True)
    posting.add_argument("--repo", default="jbgh2/card-game-dsl")
    posting.add_argument("--dry-run", action="store_true")
    posting.add_argument("--record-only", action="store_true")
    posting.add_argument("findings", help="the review's findings list, a JSON file")
    args = parser.parse_args(argv)
    if args.command == "post":
        try:
            with open(args.findings) as handle:
                findings = parse_findings(json.load(handle))
            return post(args.pr, args.head, args.tier, args.artifact_gate, findings, repo=args.repo,
                        dry_run=args.dry_run, record_only=args.record_only)
        except (OSError, ValueError) as err:
            print(f"post: nothing posted -- {err}")
            return 2
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
