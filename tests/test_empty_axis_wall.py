"""A parametrization axis that derives to nothing fails the build.

`empty_parameter_set_mark` defaults to `skip`, so a parametrized test whose
axis comes back empty is not a failure — it silently stops existing, and the
suite reports success. An adversarial audit of `tests/test_role_comparison_pin.py`
met it directly: pointing `_PACKAGE` at a directory that does not exist retired
that module's entire per-module sweep and the run was `2 passed, 1 skipped`,
exit 0 — GREEN. That is the "vacuously green" class (`docs/decisions.md`,
"Closed-domain completeness") defeating the mechanism this repo leans on most,
an axis derived in code from a registry or a filesystem glob.

The wall is pytest's own: `empty_parameter_set_mark = "fail_at_collect"` in
`pyproject.toml`. It is preferred to a scrape or a collect-the-suite test for a
reason that is derived, not assumed — every parameter set in pytest is born at
one choke point, `ParameterSet._for_parametrize`, so the flag covers
`@pytest.mark.parametrize`, `metafunc.parametrize` and `@pytest.fixture(params=)`
alike, where a scrape over one spelling would cover strictly less
(`test_the_birth_sites_are_the_ones_pytest_has` derives that claim from pytest's
source rather than restating it here). Building the guard out of a derived axis
of our own — the shape the issue sketched — would have built it from the same
material that broke.

What the flag cannot know is that an axis is empty *on purpose*. Three are:
the live docs hold zero `cardlang`, zero `cardlang-bad` and zero
`cardlang-bad-fragment` blocks, and `tests/test_doc_snippets.py` proves those
code paths with synthetic fixtures instead. So the flag is the deny-everything
wall and `tests/empty_axis.py`'s `may_be_empty` is the only door through it:
the reason rides at the call site, the set of call sites is pinned below, and
an authorized axis that STOPS being empty fails loud — the `xfail_strict`
bargain, so closing the gap forces the record of it to be updated in the same
change.

Contract (decisions.md "Closed-domain completeness", write-time triage)
-----------------------------------------------------------------------
Assumes:      pytest creates every parameter set through
              `ParameterSet._for_parametrize`, and honours
              `empty_parameter_set_mark` there.
Establishes:  an empty axis is a collection ERROR at every birth site unless
              routed through `may_be_empty`; every `may_be_empty` call site is
              pinned here; an authorized axis that is no longer empty is loud.
Now illegal:  a derived axis that quietly evaporates to nothing; an
              authorization that outlives the emptiness it describes; a
              `may_be_empty` call that is not attached to a test function's
              decorators (so the pin below cannot see it).

Completeness ledger
--------------------
property:   a parametrization axis that derives to nothing stops the build, in
            every way pytest can create one, unless it is authorized at its
            call site with a stated reason and pinned in this module.
domain:     the birth sites of a pytest parameter set — DERIVED from pytest's
            own source rather than listed here: the single choke point
            (`ParameterSet._for_parametrize`), its one caller
            (`Metafunc.parametrize`), and that method's internal callers (the
            `@pytest.mark.parametrize` path in `python.py`, the
            `@pytest.fixture(params=)` path in `fixtures.py`) plus its public
            use from a `pytest_generate_tests` hook. Crossed with
            {unauthorized, authorized} and with the argname arities each site
            admits (a fixture yields one value, so arity is 1 there by
            construction).
registry:   `_birth_sites()` derives the site axis from `_pytest/**/*.py` by
            AST — a pytest release that grows a fourth site reddens it by name.
            `_authorized_empty_axes()` derives the authorization table from
            `tests/**/*.py` by AST. `pyproject.toml`'s
            `empty_parameter_set_mark` is the wall itself.
covered:    the grid — `test_the_wall_holds_at_every_birth_site`, ten cells
            (`_GRID`), each a generated module run under a real sub-pytest
            against this repo's own ini file, asserting the collection error or
            the authorized placeholder by name. Plus, one per claim this ledger
            makes: the site axis pin
            (`test_the_birth_sites_are_the_ones_pytest_has`), whose scrape is
            proven to fire against a synthetic tree
            (`test_the_birth_site_scrape_can_see_a_call`); the wall's
            installation (`test_the_wall_is_installed`); the authorization
            table (`test_every_authorized_empty_axis_is_pinned`) and the
            attribution wall that makes it total
            (`test_every_helper_call_is_attributed_to_a_test`), whose scrapes
            are likewise proven to fire
            (`test_the_authorization_scrape_can_see_a_call`); the door's two
            refusals — staleness
            (`test_an_authorization_that_is_no_longer_empty_is_loud`) and a
            placeholder reason (`test_a_blank_reason_is_not_a_reason`) — each
            proven to stop the BUILD at the decorator site where it really
            fires, not merely to raise when called
            (`test_a_refused_authorization_stops_collection`, two cells); the
            arity backstop pytest owns (`test_an_argcount_mismatch_is_loud`);
            and the core-install config
            (`test_the_suite_collects_clean_without_pyspiel`), which is the only
            gate that ever collects this suite without the `openspiel` extra —
            CI always installs it. Every pin above that was born green carries
            its reddening mutation in its own docstring, run and reverted.
sampled:    none. Every cell of the crossed domain is an executed row.
residual:   FIVE, each with its wall or its owner:
            (1) an axis that NARROWS without reaching zero (a glob matching 3
            of 60 modules) is the same defect and no count-based check sees it.
            Deliberately not machinery: issue #143's scope note for #150 rules
            it a recorded residual, and this ledger owns that record. R4 —
            narrowing a derived axis means editing the machinery that derives
            it; no game and no designer sentence can reach it.
            (2) a nonempty axis every row of which skips at RUN time
            (`tests/test_family_libraries.py`, `tests/fuzz/test_fuzz.py` call
            `pytest.skip()` from inside the test body) evaporates the same
            guarantee one stage later, where a collection-time wall cannot
            reach. No wall; recorded as issue #162 — R4, and filed anyway
            because the guarantee it guards (a check that claims coverage
            actually runs) is rigor-critical.
            (3) a module that skips itself at COLLECTION takes every test in it
            away. Today that is only `pytest.importorskip("pyspiel")`, walled
            by `tests/test_optional_pyspiel.py::test_every_test_module_imports_without_pyspiel`
            plus CI installing the extra — a wall that exists, in another
            module, so it is named rather than rebuilt. R4 — reaching it
            takes a test author adding an `importorskip`, or an install
            without the extra.
            (4) a `reason` is prose. It is required to be nonempty and to sit
            at the call site, but nothing checks that it stays true; the
            staleness pin covers the case that actually bites (the axis becomes
            nonempty). R4, this ledger owns the record.
            (5) the wall is ini configuration, so `-o
            empty_parameter_set_mark=skip` on a command line disables it for
            that run, and a hand-written `pytest.param(..., marks=skip)`
            bypasses the door without touching the pin. Both are deliberate
            acts by an author already editing the mechanism, reachable by
            nobody else. R4, this ledger owns the record.
"""

from __future__ import annotations

import ast
import pathlib
import subprocess
import sys
import tempfile
from typing import NamedTuple

import pytest

_REPO = pathlib.Path(__file__).resolve().parent.parent
_TESTS = _REPO / "tests"
_INI = _REPO / "pyproject.toml"


# ---------------------------------------------------------------------------
# Axis 1: where a parameter set can be born. Derived from pytest's source.
# ---------------------------------------------------------------------------


_PYTEST = pathlib.Path(pytest.__file__).resolve().parent.parent / "_pytest"


def _birth_sites(root: pathlib.Path = _PYTEST) -> dict[str, list[str]]:
    """Every internal call to the parameter-set choke point, by callee.

    Keyed by the callee's name (`_for_parametrize`, `parametrize`), valued by
    `<module>::<enclosing function>` — enough to say WHICH code path creates
    parameter sets, which is the grid's first axis. Derived by AST so a comment
    or a docstring mentioning `parametrize` is not a hit (pytest's own source
    carries several, in `mark/__init__.py` and `mark/structures.py`).

    `root` is a parameter so the derivation can be called with a tree that is
    not pytest's — the pin below reads the real one, and reading it twice is
    not evidence that anything was read at all."""
    out: dict[str, list[str]] = {}
    for path in sorted(root.rglob("*.py")):
        tree = ast.parse(path.read_text())
        for fn in ast.walk(tree):
            if not isinstance(fn, ast.FunctionDef | ast.AsyncFunctionDef):
                continue
            for node in ast.walk(fn):
                if not isinstance(node, ast.Call):
                    continue
                func = node.func
                if not isinstance(func, ast.Attribute):
                    continue
                if func.attr not in ("_for_parametrize", "parametrize"):
                    continue
                out.setdefault(func.attr, []).append(
                    f"{path.relative_to(root)}::{fn.name}"
                )
    return {k: sorted(set(v)) for k, v in sorted(out.items())}


# The choke point has ONE caller, and that caller has two internal ones. This is
# the whole reason the ini flag is the wall rather than a scrape of our own: all
# three surface spellings funnel through a single gate, so covering the gate
# covers spellings nobody has written yet.
_BIRTH_SITES = {
    "_for_parametrize": ["python.py::parametrize"],
    "parametrize": [
        "fixtures.py::pytest_generate_tests",
        "python.py::pytest_generate_tests",
    ],
}


def test_the_birth_sites_are_the_ones_pytest_has() -> None:
    """The grid's site axis is READ from pytest, not asserted about it.

    red under: point `_PYTEST` at a directory that does not exist — the derived
    side comes back empty and no longer matches. It reddens for real on a pytest
    release that grows a new way to create a parameter set, which is the point:
    that is a grid cell nobody has written."""
    assert _birth_sites() == _BIRTH_SITES, (
        "pytest's parameter-set birth sites moved (pytest "
        f"{pytest.__version__}). Each site is a way an axis can evaporate; a "
        "new one needs a row in _GRID and a line in this module's ledger "
        "before the pin is updated."
    )


def test_the_birth_site_scrape_can_see_a_call(tmp_path: pathlib.Path) -> None:
    """The scrape is load-bearing, so prove it FIRES rather than trusting a
    green run over pytest's tree — a scrape that matched nothing would be green
    there too, and the axis would be `_BIRTH_SITES` describing itself.

    Three shapes, one that must be found and two that must not: a call inside a
    function, the same text inside a STRING (a constant, not a call), and a
    same-named call on nothing (`parametrize(...)` bare, which is not a call
    through the choke point's owner)."""
    (tmp_path / "probe.py").write_text(
        "def outer():\n"
        "    metafunc.parametrize('x', [])\n"
        "    src = 'thing.parametrize(\"y\", [])'\n"
        "    parametrize('z', [])\n"
    )
    assert _birth_sites(tmp_path) == {"parametrize": ["probe.py::outer"]}


# ---------------------------------------------------------------------------
# The grid: birth site x authorization x arity.
# ---------------------------------------------------------------------------

_REASON = "nothing to cross today"


def _probe_source(site: str, authorized: bool, argcount: int) -> str:
    """A module whose axis is empty, born at `site`, with `argcount` names."""
    names = ",".join(f"a{i}" for i in range(argcount))
    args = ", ".join(f"a{i}" for i in range(argcount))
    values = (
        f"may_be_empty([], reason={_REASON!r}, argcount={argcount})"
        if authorized
        else "[]"
    )
    head = (
        "import sys\n"
        f"sys.path.insert(0, {str(_REPO)!r})\n"
        "import pytest\n"
        "from tests.empty_axis import may_be_empty\n\n"
    )
    if site == "parametrize_mark":
        return head + (
            f"@pytest.mark.parametrize({names!r}, {values})\n"
            f"def test_cell({args}):\n"
            "    assert False\n"
        )
    if site == "metafunc_parametrize":
        return head + (
            "def pytest_generate_tests(metafunc):\n"
            f"    if 'a0' in metafunc.fixturenames:\n"
            f"        metafunc.parametrize({names!r}, {values})\n\n"
            f"def test_cell({args}):\n"
            "    assert False\n"
        )
    if site == "fixture_params":
        return head + (
            f"@pytest.fixture(params={values})\n"
            "def a0(request):\n"
            "    return request.param\n\n"
            "def test_cell(a0):\n"
            "    assert False\n"
        )
    raise AssertionError(f"unknown birth site {site!r}")  # backstop: _GRID owns the axis


# Every cell of the crossed domain, and the outcome each one is DESIGNED to
# have. `collect_error`: the wall fires and collection stops. `authorized_skip`:
# the door opens and exactly one placeholder is skipped, carrying its reason.
# Arity 2 exists only where the site admits several names; a fixture yields one
# value, so `fixture_params` has no arity-2 cell to write.
_GRID = [
    ("parametrize_mark", False, 1, "collect_error"),
    ("parametrize_mark", False, 2, "collect_error"),
    ("parametrize_mark", True, 1, "authorized_skip"),
    ("parametrize_mark", True, 2, "authorized_skip"),
    ("metafunc_parametrize", False, 1, "collect_error"),
    ("metafunc_parametrize", False, 2, "collect_error"),
    ("metafunc_parametrize", True, 1, "authorized_skip"),
    ("metafunc_parametrize", True, 2, "authorized_skip"),
    ("fixture_params", False, 1, "collect_error"),
    ("fixture_params", True, 1, "authorized_skip"),
]


class _ProbeRun(NamedTuple):
    returncode: int
    text: str


def _run_probe(source: str) -> _ProbeRun:
    """Collect and run `source` as a module, under this repo's OWN ini file.

    `-c` rather than a bare `-o`: the claim is about the configuration this repo
    ships, so a cell must read the same `pyproject.toml` CI does. A cell that
    passed its own flag in would stay green the day the line is deleted."""
    with tempfile.TemporaryDirectory() as tmp:
        probe = pathlib.Path(tmp) / "test_cell_probe.py"
        probe.write_text(source)
        proc = subprocess.run(  # noqa: PLW1510 -- returncode is the assertion, not an exception
            [
                sys.executable,
                "-m",
                "pytest",
                "-q",
                "-rs",
                "-p",
                "no:cacheprovider",
                "-c",
                str(_INI),
                str(probe),
            ],
            cwd=_REPO,
            capture_output=True,
            text=True,
        )
    return _ProbeRun(proc.returncode, proc.stdout + proc.stderr)


@pytest.mark.parametrize(
    ("site", "authorized", "argcount", "expected"),
    _GRID,
    ids=[f"{s}-{'auth' if a else 'bare'}-{n}" for s, a, n, _ in _GRID],
)
def test_the_wall_holds_at_every_birth_site(
    site: str, authorized: bool, argcount: int, expected: str
) -> None:
    """Every way pytest can create a parameter set, crossed with the door."""
    proc = _run_probe(_probe_source(site, authorized, argcount))
    out = proc.text
    if expected == "collect_error":
        assert proc.returncode != 0, (
            f"{site}/arity {argcount}: an empty axis collected cleanly — the "
            f"wall does not reach this birth site.\n{out}"
        )
        assert "Empty parameter set" in out, (
            f"{site}/arity {argcount}: the run failed, but not for the empty "
            f"axis — red for the wrong reason.\n{out}"
        )
    else:
        assert proc.returncode == 0, (
            f"{site}/arity {argcount}: an AUTHORIZED empty axis was refused.\n{out}"
        )
        assert "1 skipped" in out, f"{site}: expected one placeholder.\n{out}"
        assert _REASON in out, (
            f"{site}/arity {argcount}: the placeholder skipped without carrying "
            f"its authorization reason — the door is open but says nothing.\n{out}"
        )


def test_the_wall_is_installed(request: pytest.FixtureRequest) -> None:
    """The grid proves what the wall DOES; this proves this repo has it.

    red under: delete `empty_parameter_set_mark` from `[tool.pytest.ini_options]`
    in pyproject.toml."""
    assert request.config.getini("empty_parameter_set_mark") == "fail_at_collect", (
        "pyproject.toml must set empty_parameter_set_mark = 'fail_at_collect'; "
        "without it an axis that derives to nothing retires itself as a skip "
        "and the suite reports success."
    )


# ---------------------------------------------------------------------------
# Axis 2: who is authorized. Derived from the suite by AST.
# ---------------------------------------------------------------------------

_HELPER = "may_be_empty"


def _helper_calls(tree: ast.AST) -> list[ast.Call]:
    """Every call to the helper, under either spelling.

    `ast.Attribute` counts: `ea.may_be_empty(...)` after `import
    tests.empty_axis as ea` is the same call, and matching only the bare name
    would hide it from BOTH the attribution table and the stray wall — an
    authorized axis with no row anywhere, which is a hole rather than an
    under-report. Enumerating one spelling is the deny-list this repo forbids,
    and `tests/test_role_comparison_pin.py` records it missing four shapes that
    way before review caught it."""
    return [
        n
        for n in ast.walk(tree)
        if isinstance(n, ast.Call)
        and (
            (isinstance(n.func, ast.Name) and n.func.id == _HELPER)
            or (isinstance(n.func, ast.Attribute) and n.func.attr == _HELPER)
        )
    ]


def _authorized_empty_axes(root: pathlib.Path = _TESTS) -> dict[str, list[str]]:
    """Every test whose axis is authorized to be empty, per module.

    Attribution is by DECORATOR: a `may_be_empty` call inside a test function's
    decorator list names that function. A call anywhere else is not attributed,
    which would leave it outside the pin — so it is walled instead, by
    `test_every_helper_call_is_attributed_to_a_test`.

    The helper's name appears in this module only inside generated source
    STRINGS, which `ast` sees as constants, not calls — so the grid's probes do
    not authorize themselves."""
    out: dict[str, list[str]] = {}
    for path in sorted(root.rglob("*.py")):
        tree = ast.parse(path.read_text())
        for fn in ast.walk(tree):
            if not isinstance(fn, ast.FunctionDef | ast.AsyncFunctionDef):
                continue
            if any(_helper_calls(dec) for dec in fn.decorator_list):
                out.setdefault(str(path.relative_to(root)), []).append(fn.name)
    return {k: sorted(v) for k, v in sorted(out.items())}


def _unattributed_helper_calls(root: pathlib.Path = _TESTS) -> list[str]:
    """Every `may_be_empty` call the attribution above cannot see.

    This module is exempt: it is where the helper's own refusal is proven, so
    calling it outside a decorator is the point rather than an escape. Matched
    by FULL PATH — a basename match would exempt any future `tests/**/` file
    that happened to share the name, and would drop it from the sweep while
    this ledger still claimed every module."""
    exempt = pathlib.Path(__file__).resolve()
    found: list[str] = []
    for path in sorted(root.rglob("*.py")):
        if path.resolve() == exempt:
            continue
        tree = ast.parse(path.read_text())
        attributed = {
            id(call)
            for fn in ast.walk(tree)
            if isinstance(fn, ast.FunctionDef | ast.AsyncFunctionDef)
            for dec in fn.decorator_list
            for call in _helper_calls(dec)
        }
        found += [
            f"{path.relative_to(root)}:{call.lineno}"
            for call in _helper_calls(tree)
            if id(call) not in attributed
        ]
    return found


# The whole allow-list. Each entry's REASON lives at its call site; this table
# is the central record that one exists, so a new authorization cannot land
# without a line in a diff someone reads.
_AUTHORIZED_EMPTY_AXES: dict[str, list[str]] = {
    "test_doc_snippets.py": [
        "test_bad_fragment_blocks_are_rejected_when_wrapped",
        "test_cardlang_bad_blocks_are_rejected",
        "test_cardlang_blocks_are_full_valid_games",
    ],
}


def test_every_authorized_empty_axis_is_pinned() -> None:
    """The door is narrow, and the list of who went through it is here.

    Compared against a NONEMPTY baseline on purpose: this pin is itself a
    derived axis over a glob, so a `_TESTS` that resolves to nothing would give
    an empty derivation — the very defect this module exists to stop, one level
    down. An empty derivation fails against the table instead of matching it.

    red under: wrap any other parametrization in `may_be_empty` — that module
    appears on the derived side and the table does not carry it."""
    assert _authorized_empty_axes() == _AUTHORIZED_EMPTY_AXES


def test_every_helper_call_is_attributed_to_a_test() -> None:
    """The pin attributes by decorator, so nothing may call the helper elsewhere.

    Hoisting the call one line up (`_AXIS = may_be_empty(...)` beside the
    decorator that uses it) would authorize an empty axis that the table above
    cannot name. That band is not left silent.

    red under: assign a `may_be_empty(...)` result to a module-level name in any
    test module."""
    stray = _unattributed_helper_calls()
    assert not stray, (
        f"{_HELPER} called outside a test function's decorators at {stray} — "
        "the authorization pin attributes by decorator, so a call anywhere else "
        "opens the door without appearing in _AUTHORIZED_EMPTY_AXES. Inline it "
        "into the parametrize/fixture decorator."
    )


def test_the_authorization_scrape_can_see_a_call(tmp_path: pathlib.Path) -> None:
    """Both scrapes above are load-bearing, so prove they FIRE.

    A scrape that matched nothing would also be green against the real tree —
    `_AUTHORIZED_EMPTY_AXES` would just be `{}`, and the wall would be a check
    that cannot fail. Fed a synthetic tree carrying an attributed call under
    each of the helper's two spellings — bare name, and qualified through a
    module alias — plus one stray call and one decorated test that does not use
    the helper at all."""
    (tmp_path / "sub").mkdir()
    (tmp_path / "test_attributed.py").write_text(
        "import pytest\n"
        "@pytest.mark.parametrize('x', may_be_empty([], reason='r'))\n"
        "def test_yes(x): pass\n"
        "@pytest.mark.parametrize('x', ea.may_be_empty([], reason='r'))\n"
        "def test_yes_qualified(x): pass\n"
        "@pytest.mark.parametrize('x', [1])\n"
        "def test_no(x): pass\n"
    )
    (tmp_path / "sub" / "test_stray.py").write_text(
        "_AXIS = may_be_empty([], reason='r')\n"
        "def test_plain(): pass\n"
    )
    assert _authorized_empty_axes(tmp_path) == {
        "test_attributed.py": ["test_yes", "test_yes_qualified"]
    }
    assert _unattributed_helper_calls(tmp_path) == ["sub/test_stray.py:1"]


def test_an_authorization_that_is_no_longer_empty_is_loud() -> None:
    """The `xfail_strict` bargain: closing the gap updates the record.

    An authorization describes a fact about today — "the live docs hold zero
    `cardlang` blocks". The day one lands, the axis is nonempty, the reason is a
    lie, and nothing else in the suite would ever say so: the test would simply
    start doing its job with a stale authorization beside it. So the helper
    refuses.

    red under: `return values` at the top of `may_be_empty` — the pass-through
    reading, which is what the name suggests and what makes this silent."""
    from tests.empty_axis import may_be_empty

    with pytest.raises(BaseException) as excinfo:
        may_be_empty([1], reason="the live docs hold none")
    assert "no longer empty" in str(excinfo.value)


def test_a_blank_reason_is_not_a_reason() -> None:
    """The door's whole cost is that someone writes down why. A placeholder
    reason pays it in appearance only — the same defect
    `tests/test_role_comparison_pin.py` guards against by requiring its marker
    to carry a nonempty reason rather than merely to be present.

    red under: drop the `reason.strip()` guard from `may_be_empty`."""
    from tests.empty_axis import may_be_empty

    with pytest.raises(BaseException) as excinfo:
        may_be_empty([], reason="   ")
    assert "needs a reason" in str(excinfo.value)


@pytest.mark.parametrize(
    ("values", "reason", "expected"),
    [
        ("[1]", "stale", "no longer empty"),
        ("[]", "   ", "needs a reason"),
    ],
    ids=["stale-authorization", "blank-reason"],
)
def test_a_refused_authorization_stops_collection(
    values: str, reason: str, expected: str
) -> None:
    """The refusals must fail the BUILD, at the site they actually fire.

    Both live in a decorator argument, so they raise during module import —
    collection, not a test run. `pytest.fail` raises `Failed`, whose base class
    `OutcomeException` pytest deliberately special-cases at import time: that is
    how `importorskip` retires a whole module quietly. Asserting the function
    raises when called from a test body (the two tests below) proves the
    function raises; it does not prove the channel survives the trip. If it did
    not, this whole mechanism would be the vacuously-green class it exists to
    stop.

    red under: swap either refusal in `tests/empty_axis.py` for
    `pytest.skip(reason=..., allow_module_level=True)`, the channel
    `importorskip` uses — the module retires itself, the reason never reaches
    the output, and the run reports no tests collected instead of the refusal.
    Note which assertion catches that: the returncode one does NOT, because
    "no tests ran" is itself a nonzero exit. The message assertion is what
    makes this pin discriminate, which is why both are here."""
    proc = _run_probe(
        "import sys\n"
        f"sys.path.insert(0, {str(_REPO)!r})\n"
        "import pytest\n"
        "from tests.empty_axis import may_be_empty\n\n"
        f"@pytest.mark.parametrize('a0', may_be_empty({values}, reason={reason!r}))\n"
        "def test_cell(a0):\n"
        "    assert True\n"
    )
    assert proc.returncode != 0, (
        f"a refused authorization collected cleanly — {expected!r} never "
        f"reached the build.\n{proc.text}"
    )
    assert expected in proc.text, (
        f"the run failed, but without saying {expected!r} — red for the wrong "
        f"reason, and the author is told nothing.\n{proc.text}"
    )


def test_an_argcount_mismatch_is_loud() -> None:
    """A placeholder of the wrong arity is refused by pytest itself, at
    collection, naming both counts — so `may_be_empty` does not re-check it.

    This is a backstop's docstring, not a wall: the wall is pytest's own
    `ParameterSet._for_parametrize` length check. Pinned because "the layer
    below catches it" is exactly the claim that goes stale unnoticed."""
    probe = _probe_source("parametrize_mark", authorized=True, argcount=1).replace(
        "'a0'", "'a0,a1'"
    )
    out = _run_probe(probe)
    assert "must be equal to the number of values" in out.text, out.text
    assert out.returncode != 0, out.text


def test_the_suite_collects_clean_without_pyspiel() -> None:
    """The wall must hold on a core install, which no other gate collects under.

    The flag converts a skip into a hard collection ERROR, so an axis that is
    nonempty only because the `openspiel` extra is present would take its whole
    module down on an install without it. CI always installs the extra
    (pyproject.toml), so that failure would be invisible everywhere else —
    `tests/test_optional_pyspiel.py` proves every module IMPORTS without
    pyspiel, which is a weaker claim than collecting without it.

    red under: derive any axis from something pyspiel-only (e.g. parametrize a
    test over `[]` when `pyspiel` is absent)."""
    script = (
        "import sys\n"
        "class _BlockPyspiel:\n"
        "    def find_spec(self, name, path=None, target=None):\n"
        "        if name == 'pyspiel' or name.startswith('pyspiel.'):\n"
        "            raise ModuleNotFoundError('pyspiel is blocked on the core path')\n"
        "        return None\n"
        "sys.meta_path.insert(0, _BlockPyspiel())\n"
        "import pytest\n"
        "sys.exit(pytest.main(['--collect-only', '-q', '-p', 'no:cacheprovider', 'tests']))\n"
    )
    proc = subprocess.run(  # noqa: PLW1510 -- returncode is the assertion, not an exception
        [sys.executable, "-c", script],
        cwd=_REPO,
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, (
        "collecting the suite without the openspiel extra is not clean — an "
        "empty or failing axis that only CI's install hides:\n"
        + (proc.stdout + proc.stderr)[-4000:]
    )
