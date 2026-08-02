"""Every assert-currency site in the runtime packages is write-time-triaged.

decisions.md "Closed-domain completeness" (write-time triage): a check lands
only after naming its owner — a **wall** (moved to the owning layer, in that
layer's currency), a **backstop** (it stays, and its comment names the wall it
shadows), or a **missing wall** (the wall is built upstream and the site
becomes a backstop citing it). The runtime's failure currency for anything a
game description can cause is the typed ``RuntimeError``; an ``assert`` /
``raise AssertionError`` is compiler-bug currency only. The runtime-assert
census (tests/test_movement_endpoints.py's origin story) applied that triage
once, by hand; this module makes it mechanical, so an untriaged assert cannot
land silently between censuses.

The mechanism (the ``inspect.getsource``-scrape idiom of
tests/test_operator_walls.py, widened to whole packages): every ``assert``
statement and ``raise AssertionError`` in the runtime packages must carry, in
its *attached text* — the statement's own source lines (message strings and
trailing comments included), the contiguous ``#`` block immediately above it,
or, when the site is the first statement of an ``if`` body, the block above
that ``if`` header — one of:

* a **fallthrough marker** — ``unknown …`` / ``no declared …`` — the message
  convention of an exhaustive-dispatch default arm (``_apply``'s "unknown
  assignment operator", the native dispatch's "unknown …" fallthroughs);
  ``assert_never`` sites need no marker: mypy owns their unreachability and
  they are not assert statements, so they are outside the scraped domain; or
* a **guarantor word** naming the upstream wall the site backstops —
  ``backstop`` itself, or the owning pass/registry: ``grammar``, ``parse``,
  ``resolve``, ``typecheck``, ``expand``, ``deckcheck``, ``registry`` (the
  existing style: "(resolve should have rejected this)", "resolve() must
  reject a missing max_length", "grammar makes `or <default>` mandatory").

The classifier checks that a site *names* its owner; whether the named wall
truly guards it is the reviewer's judgment, exactly as for any comment. A
site with neither tag fails the build with the triage instructions.

Completeness ledger (decisions.md "Closed-domain completeness"):

property:  every assert-currency site in the runtime packages names its triage
           class (dispatch fallthrough, or backstop naming its wall) in
           machine-checkable form.
domain:    ``ast.Assert`` nodes and ``ast.Raise`` nodes whose exception is
           ``AssertionError`` (call or bare name), in every module of the
           ``cardlang.runtime`` and ``cardlang.stdlib`` packages, times the
           attachment shapes Python's comment grammar allows (message string /
           statement-span trailing comment / contiguous block above the
           statement / block above the enclosing ``if`` header).
registry:  the source scrape itself — modules enumerated by globbing the two
           packages' directories (a new module is in-domain the day it
           exists), sites enumerated by ``ast.walk`` (a string containing the
           word "assert" is not a site; a multi-line or f-string message is).
covered:   all modules of both packages; all site shapes (bare assert, assert
           with message, raise AssertionError call / bare name); all four
           attachment shapes — each pinned by a synthetic-source probe below,
           so the classifier itself cannot rot vacuously green.
sampled:   the guarantor vocabulary is a closed word list (this module's
           ``GUARANTOR_WORDS``); a future pass must be added to it when it
           becomes a wall owner. Substring matching means an unrelated comment
           containing e.g. "parse" would satisfy the classifier — accepted:
           the gate enforces that triage is *stated*, review enforces that it
           is *true*.
residual:  compile-pass modules (cardlang/parse.py … ir.py, openspiel/) are
           outside the domain — their failure currency for internal
           invariants is the assert, walled per-pass by the ``Contract``
           blocks in their module docstrings and the assert_never dispatch
           pins, so a blanket scrape would mis-rank their sites. Extending the
           gate there needs its own convention (which comment tags mark a pass
           invariant) before it can be mechanical; this ledger is its record.
           ``assert_never`` sites are excluded by construction (mypy owns
           them; pinned by a probe below).
"""

from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path

import cardlang.runtime
import cardlang.stdlib

FALLTHROUGH_MARKERS = ("unknown ", "no declared ")
GUARANTOR_WORDS = (
    "backstop",
    "grammar",
    "parse",
    "resolve",
    "typecheck",
    "expand",
    "deckcheck",
    "registry",
)


@dataclass(frozen=True)
class Site:
    module: str
    line: int
    source: str  # first line of the statement, for the failure listing
    attached_text: str

    @property
    def triaged(self) -> bool:
        text = self.attached_text.lower()
        return any(m in text for m in FALLTHROUGH_MARKERS) or any(
            w in text for w in GUARANTOR_WORDS
        )


def _package_modules() -> list[Path]:
    """Every module of the two runtime packages, from the filesystem — the
    module axis derives from the package directories, not a hand list."""
    packages = (
        Path(str(cardlang.runtime.__file__)).parent,
        Path(str(cardlang.stdlib.__file__)).parent,
    )
    return sorted(p for pkg in packages for p in pkg.glob("*.py"))


def _is_assertion_raise(node: ast.Raise) -> bool:
    exc = node.exc
    if isinstance(exc, ast.Call):
        exc = exc.func
    return isinstance(exc, ast.Name) and exc.id == "AssertionError"


def _comment_block_above(lines: list[str], lineno: int) -> str:
    """The contiguous ``#`` block ending on the line just above ``lineno``
    (1-based). A blank line or a code line breaks attachment."""
    block: list[str] = []
    i = lineno - 2  # 0-based index of the line above
    while i >= 0 and lines[i].strip().startswith("#"):
        block.append(lines[i])
        i -= 1
    return "\n".join(reversed(block))


def _sites_in_source(source: str, module: str) -> list[Site]:
    lines = source.splitlines()
    tree = ast.parse(source)

    # Parent links, so a raise that is the first statement of an `if` body can
    # claim the comment block above the `if` header (state.py's zone-index
    # wall-bypass raise is the motivating shape).
    first_stmt_of_if: dict[int, ast.If] = {}  # id(child) -> enclosing If
    for parent in ast.walk(tree):
        if isinstance(parent, ast.If) and parent.body:
            first_stmt_of_if[id(parent.body[0])] = parent

    sites: list[Site] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Assert) or isinstance(node, ast.Raise) and _is_assertion_raise(node):
            pass
        else:
            continue
        end = node.end_lineno if node.end_lineno is not None else node.lineno
        parts = [
            "\n".join(lines[node.lineno - 1 : end]),
            _comment_block_above(lines, node.lineno),
        ]
        header: ast.stmt | None = first_stmt_of_if.get(id(node))
        while header is not None:  # nested ifs: climb while still first-in-body
            parts.append(_comment_block_above(lines, header.lineno))
            header = first_stmt_of_if.get(id(header))
        sites.append(
            Site(
                module=module,
                line=node.lineno,
                source=lines[node.lineno - 1].strip(),
                attached_text="\n".join(p for p in parts if p),
            )
        )
    return sites


def _runtime_sites() -> list[Site]:
    sites: list[Site] = []
    for path in _package_modules():
        sites.extend(_sites_in_source(path.read_text(), path.name))
    return sites


# --- the gate -----------------------------------------------------------


def test_every_runtime_assert_site_is_triaged() -> None:
    untagged = [s for s in _runtime_sites() if not s.triaged]
    listing = "\n".join(f"  {s.module}:{s.line}: {s.source}" for s in untagged)
    assert not untagged, (
        f"{len(untagged)} untriaged assert-currency site(s) in the runtime "
        f"packages:\n{listing}\n"
        "Write-time triage (decisions.md 'Closed-domain completeness'): a "
        "check lands as a wall at the owning layer, in that layer's currency, "
        "or as a backstop whose comment/message names the wall it shadows. "
        "Tag each site above — in its message, a comment directly above it, "
        "or a trailing comment — with the guarantor it backstops "
        f"({', '.join(GUARANTOR_WORDS)}), or mark an exhaustive-dispatch "
        "fallthrough with an 'unknown …' / 'no declared …' message. If the "
        "condition is reachable from a game description, it is a MISSING "
        "wall: raise a typed RuntimeError (the runtime's failure currency) "
        "or build the wall upstream — do not tag it."
    )


def test_the_scrape_sees_the_census_modules() -> None:
    """Anti-vacuity floor: the census modules each still contribute at least
    one site, so an empty scrape (wrong path, wrong node match) cannot pass
    as universal compliance. If a refactor genuinely removes every assert
    from one of these, updating this pin is the intended friction."""
    by_module: set[str] = {s.module for s in _runtime_sites()}
    # `builtins.py` is deliberately absent: the Builtins half of the dispatch
    # (issue #201) states its backstops as typed `RuntimeError`s, which are
    # outside this scrape's domain, so it contributes no site to floor.
    for module in ("execute.py", "evaluate.py", "mechanics.py", "primitives.py"):
        assert module in by_module, f"scrape found no sites in {module}"


# --- classifier probes (synthetic sources; the misuse-probe artifact) ----


def _classify(source: str) -> list[bool]:
    return [s.triaged for s in _sites_in_source(source, "probe.py")]


def test_probe_bare_assert_is_flagged() -> None:
    assert _classify("def f(x):\n    assert x is not None\n") == [False]


def test_probe_unrelated_comment_is_flagged() -> None:
    src = "def f(x):\n    # hot path, keep allocation-free\n    assert x >= 0\n"
    assert _classify(src) == [False]


def test_probe_untagged_raise_is_flagged() -> None:
    src = 'def f(x):\n    raise AssertionError(f"unexpected value {x}")\n'
    assert _classify(src) == [False]


def test_probe_blank_line_breaks_comment_attachment() -> None:
    src = "def f(x):\n    # resolve rejects this upstream\n\n    assert x\n"
    assert _classify(src) == [False]


def test_probe_message_tag_is_accepted() -> None:
    src = 'def f(x):\n    assert x, "resolve() must reject a missing x"\n'
    assert _classify(src) == [True]


def test_probe_comment_above_is_accepted() -> None:
    src = "def f(x):\n    # Backstop of the endpoint wall.\n    assert x\n"
    assert _classify(src) == [True]


def test_probe_trailing_comment_is_accepted() -> None:
    src = "def f(x):\n    assert x  # narrowing; parse guarantees a dest\n"
    assert _classify(src) == [True]


def test_probe_multiline_message_tag_is_accepted() -> None:
    src = (
        "def f(op):\n"
        "    raise AssertionError(\n"
        '        f"unknown operator {op!r}"\n'
        "    )\n"
    )
    assert _classify(src) == [True]


def test_probe_comment_above_enclosing_if_is_accepted() -> None:
    src = (
        "def f(x):\n"
        "    # Resolve walls these declarations; reaching this raise means a\n"
        "    # construction path bypassed it.\n"
        "    if x not in ROLES:\n"
        '        raise AssertionError("bypassed the wall")\n'
    )
    assert _classify(src) == [True]


def test_probe_typed_errors_are_outside_the_domain() -> None:
    src = (
        "def f(x):\n"
        '    raise RuntimeError("wrong currency lives elsewhere")\n'
        "def g(x):\n"
        '    raise ValueError("also not scraped")\n'
    )
    assert _classify(src) == []


def test_probe_assert_never_is_outside_the_domain() -> None:
    src = (
        "def f(x):\n"
        "    match x:\n"
        "        case _ as unreachable:\n"
        "            assert_never(unreachable)\n"
    )
    assert _classify(src) == []
