"""No raise in the engine leaves its Author to be guessed from the message.

`tests/test_failure_taxonomy.py` pins where each exception class SITS. This
module pins that the classes are actually USED: every `raise` in `cardlang/`
either carries a class whose Author the taxonomy records, or appears in the
residual table below with a reason. A typed hierarchy nothing raises is
decoration, and this repo has the precedent in tree — `diagnostics.Severity.
WARNING` has been a member of a two-member enum with zero producers for its
whole life.

The residual table is a RATCHET, not a permanent allow-list. Rows shrink as
sites convert and the shrink is visible in the diff; a row that GROWS, or a new
(module, class) pair appearing anywhere in `cardlang/`, fails the suite. That
is the property worth having after the migration is done: the next bare
`raise ValueError` added to the runtime cannot land silently.

Why (module, class) and not file:line — line numbers churn on every edit above
them, so a positional table would go stale weekly and be "fixed" by
regenerating it, which is the same as having no table. A module-and-class row
survives ordinary editing and still localises the work.

Contract
--------
Assumes: `tests/test_failure_taxonomy.py` holds (each class's position is
pinned). Establishes: every raise site's Author is recorded somewhere a reader
can find. Illegal after this: adding a bare untyped `raise` to `cardlang/`
without either giving it a role type or recording it here with a reason.

Completeness ledger (decisions.md "Closed-domain completeness"):

property:   every `raise <exc>` statement in `cardlang/` either names a class
            whose Author `runtime/errors.py` records, or is a recorded residual
            with a stated reason.
domain:     every `ast.Raise` node with an exception, in every module of the
            `cardlang` package — crossed with the exception class named at the
            raise. Both axes derive; neither is listed.
registry:   the source scrape itself (`_raise_sites`): modules by globbing the
            package directory, so a new module is in domain the day it exists;
            sites by `ast.walk`, so a string containing the word "raise" is not
            a site and a re-raise (`raise` with no exception) is correctly not
            one either. The class axis is whatever the raise names — including
            helper factories (`_env_miss`, `_undeclared`), which are recorded
            by their helper name because that is what the site says.
covered:    `test_no_unrecorded_raise_class` — the full derived site set
            against `_ACCOUNTED` and `_RESIDUAL`.
sampled:    none. The scrape is total over the package.
residual:   three, each a limit of what a SCRAPE can see rather than a cell
            nobody looked at:

            1. Exceptions raised with no `raise` token — `list.remove`, bare
               `next()`, raw dict subscripts. ~50 sites, derived and recorded
               on issue #231. Structurally invisible here: this module walks
               `ast.Raise`, and those are not raises. Guarded by that issue,
               not by this test, and the distinction is worth keeping — closing
               them is authoring guards, not classifying existing ones.
            2. Counting, not identity. A change that converts one site and adds
               another in the SAME module and class leaves the count unmoved
               and passes. Accepted deliberately: keying by identity means
               keying by line, which churns (see above). The exposure is one
               change touching one module in one class in both directions at
               once.
            3. Bare `assert` statements are outside the domain — they raise no
               `ast.Raise` node. `tests/test_assert_triage.py` owns them and is
               total over the same two runtime packages, so the pair covers
               the assert-channel sites this module cannot see. Note those
               vanish under `python -O`, including three import-time registry
               reconciliations (`domains.py:400`, `resolve.py:139`,
               `runtime/reads.py:366`); nothing in this repo runs `-O`, and
               R4 — recorded here rather than filed, per decisions.md
               "Reachability ranks the work".

red under: add `raise ValueError("x")` to any module of `cardlang/` —
`test_no_unrecorded_raise_class` fails naming that module and class, and says
whether the fix is a role type or a residual row. Verified by doing so.
"""

from __future__ import annotations

import ast
import collections
import pathlib
from functools import cache

import cardlang

# Classes whose Author `cardlang/runtime/errors.py` records, plus the engine's
# own control-flow signals. A raise naming one of these is accounted for: the
# reader can find out who must act by looking the class up.
_ACCOUNTED = frozenset(
    {
        # role-bearing: the game author, and the engine when a guard leaked
        "OwnerGuardError",
        "ShadowGuardError",
        # other Authors, each with its position pinned in the taxonomy
        "InstallationError",
        "PrimitiveReadError",
        "DiagnosticError",
        # not a defect: the game author wrote `error(...)` and the refusal is
        # the rule working
        "IllegalMove",
        # control flow, not failure
        "_ProduceSignal",
        "_ContinueTo",
        "_SkipHand",
        "ChooserAbort",
        # compile-pass diagnostic factories — `error` is the bag's first
        # diagnostic, the others build an AssertionError with a class-level
        # explanation attached
        "error",
        "_env_miss",
        "_untyped_operator",
        "_undeclared",
        "_missing",
        # the engine maintainer's channel, owned by tests/test_assert_triage.py
        "AssertionError",
        # `raise exc.orig_exc` — re-raising an already-classified exception
        "exc.orig_exc",
        # the CLI's exit path
        "SystemExit",
    }
)

# (module, exception class) -> (count, why it has not been given a role type).
# A ratchet: shrink rows as sites convert, delete a row at zero. Growth fails.
#
# Every row here has an Author OTHER than the game author. That is the line:
# the migration's claim is that no game-author-facing raise is left untyped,
# not that every raise in the engine is typed.
_RESIDUAL: dict[tuple[str, str], tuple[int, str]] = {
    # --- engine maintainer: invariants over the engine's own registry data ---
    ("cardlang/stdlib/boards.py", "ValueError"): (
        20,
        ("BoardEntry.__post_init__ pins the family BUILDER's output; the "
        "messages say 'registry bug' and mean it. Deliberately NOT role-typed: "
        "resolve's catch narrows to OwnerGuardError precisely so these "
        "propagate as engine failures instead of becoming a diagnostic on the "
        "designer's `board:` line. Giving them an engine-bug TYPE is the "
        "assert-channel question, which tests/test_assert_triage.py owns."),
    ),
    ("cardlang/runtime/values.py", "ValueError"): (
        4,
        ("Deck / ComponentSet __post_init__ invariants over the COMPONENT_SETS "
        "registry literal. The grammar's only deck surface is a registry "
        "LOOKUP (`cards: NAME`), so no game file can construct one of these "
        "and reach them; they fire at module import if the table is wrong."),
    ),
    ("cardlang/diagnostics.py", "ValueError"): (
        1,
        ("Span.__post_init__ (end precedes start). A malformed span is a "
        "compile-pass bug; no game description can express one."),
    ),
    # --- primitive-module maintainer -----------------------------------------
    ("cardlang/runtime/reads.py", "TypeError"): (
        3,
        ("deep_freeze's immutability refusals. Author is whoever declared the "
        "Python type (`frozen=True, slots=True` is the fix), which is a "
        "different class from PrimitiveReadError's name/declaration coupling — "
        "same audience, different artifact, so not that type either."),
    ),
    ("cardlang/runtime/tichu.py", "ValueError"): (
        1,
        ("The combo codec's play-universe refusal. Firing means the codec and "
        "the combination engine drifted — both Python in cardlang/runtime/, "
        "neither reachable from a .cardlang file."),
    ),
    # --- deliberate signals, caught by type ----------------------------------
    ("cardlang/runtime/state.py", "KeyError"): (
        2,
        ("_frame_of's miss is a SIGNAL: runtime/reads.py:409 catches KeyError "
        "by type and converts it to PrimitiveReadError, so retyping it breaks "
        "that conversion silently. ZoneStore.locate's is unreachable by "
        "construction (Zone is instantiated only inside ZoneStore.__init__)."),
    ),
    ("cardlang/libraries.py", "KeyError"): (
        1,
        ("load_library on an unregistered name. Its own comment says resolve "
        "diagnoses the author-facing case with a span this module cannot see, "
        "so reaching here is a caller bug, not a game-description one."),
    ),
    ("cardlang/libraries.py", "ValueError"): (
        1,
        ("A library file whose declared `library <name>` disagrees with its "
        "filename. Author is the library author, not the game author."),
    ),
    # --- the Interop boundary -------------------------------------------------
    ("cardlang/openspiel/encoding.py", "ValueError"): (
        5,
        ("Action-id and card-encoding misses at the OpenSpiel adapter seam. "
        "Author is the adapter maintainer; OpenSpiel's own contract is what "
        "these enforce, and Interop is an anti-corruption layer whose "
        "vocabulary is deliberately separate (the glossary's OpenSpiel boundary)."),
    ),
    # --- not defects: deferred surface ---------------------------------------
    ("cardlang/openspiel/encoding.py", "NotImplementedError"): (
        5,
        ("Encoder cases not yet built. NotImplementedError is self-describing "
        "about both Author and remedy, which is why it is not being retyped: "
        "'nobody implemented this yet' is not a guard refusing anything."),
    ),
    ("cardlang/domains.py", "NotImplementedError"): (1, "Deferred domain surface — see the encoding row."),
    ("cardlang/runtime/evaluate.py", "NotImplementedError"): (1, "Deferred evaluator surface — see the encoding row."),
    ("cardlang/runtime/values.py", "NotImplementedError"): (
        1,
        ("component_set's registry miss. Its docstring names "
        "resolve._resolve_component_set as the Owner Guard, so this is really "
        "a Shadow Guard wearing the wrong channel — the one row here that is "
        "a genuine mis-typing rather than a different Author. Left because its "
        "test pins NotImplementedError by name and the fix is a separate, "
        "provable change; recorded rather than swept so it is not mistaken "
        "for a decision."),
    ),
}


@cache
def _raise_sites() -> collections.Counter[tuple[str, str]]:
    """Every `raise <exc>` in the package, counted by (module, class name).

    A bare `raise` (re-raise) has `node.exc is None` and is correctly not a
    site: it propagates something already classified at its origin.
    """
    root = pathlib.Path(str(cardlang.__file__)).parent
    found: collections.Counter[tuple[str, str]] = collections.Counter()
    for path in sorted(root.rglob("*.py")):
        tree = ast.parse(path.read_text(), str(path))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Raise) or node.exc is None:
                continue
            exc = node.exc
            named = exc.func if isinstance(exc, ast.Call) else exc
            module = str(path.relative_to(root.parent))
            found[(module, ast.unparse(named))] += 1
    return found


def test_the_scrape_finds_sites() -> None:
    """Anti-vacuity floor. A scrape pointed at the wrong directory finds
    nothing and reports universal compliance — this repo has watched exactly
    that happen (see `empty_parameter_set_mark` in pyproject.toml). The engine
    raises hundreds of times; if this drops near zero the scrape is broken, not
    the engine.
    """
    sites = _raise_sites()
    assert sum(sites.values()) > 100, f"scrape found only {sum(sites.values())} raise sites"
    assert ("cardlang/runtime/execute.py", "OwnerGuardError") in sites


def test_no_unrecorded_raise_class() -> None:
    """Every raise names an accounted class or sits in the residual table."""
    unrecorded: list[str] = []
    grew: list[str] = []
    for (module, cls), count in sorted(_raise_sites().items()):
        if cls in _ACCOUNTED:
            continue
        recorded = _RESIDUAL.get((module, cls))
        if recorded is None:
            unrecorded.append(f"{module}: {count}x raise {cls}")
        elif count > recorded[0]:
            grew.append(f"{module}: raise {cls} went {recorded[0]} -> {count}")

    assert not unrecorded, (
        f"{len(unrecorded)} (module, class) pair(s) raise an exception whose "
        f"Author nothing records:\n  " + "\n  ".join(unrecorded) + "\n\n"
        "Decide WHO must act. If it is the game author, raise OwnerGuardError "
        "(or ShadowGuardError naming the Owner Guard that leaked). If it is "
        "someone else and the class is deliberate, add a _RESIDUAL row saying "
        "why — a row with no reason is the same as no row."
    )
    assert not grew, (
        f"{len(grew)} residual row(s) GREW:\n  " + "\n  ".join(grew) + "\n\n"
        "The residual table is a ratchet. A new bare raise in a module that "
        "already has some is exactly what it exists to catch — give the new "
        "site a role type rather than raising the count."
    )


def test_residual_rows_are_live() -> None:
    """A row that no longer matches its module is stale.

    Without this, converting a site leaves its row behind claiming work that is
    done, and the table slowly becomes a record of the past rather than of the
    remaining. Shrinking is as much a reason to edit the table as growing.
    """
    sites = _raise_sites()
    stale = [
        f"{module}: raise {cls} recorded {count}x, actually {sites.get((module, cls), 0)}x"
        for (module, cls), (count, _why) in sorted(_RESIDUAL.items())
        if sites.get((module, cls), 0) != count
    ]
    assert not stale, (
        f"{len(stale)} residual row(s) no longer match the tree:\n  "
        + "\n  ".join(stale)
        + "\n\nLower the count, or delete the row if it reached zero."
    )


def test_every_residual_row_states_a_reason() -> None:
    """The reason is the row's whole value — it is what a later reader needs to
    know whether the residual is a decision or an omission."""
    thin = [f"{m}/{c}" for (m, c), (_n, why) in sorted(_RESIDUAL.items()) if len(why.strip()) < 30]
    assert not thin, f"residual row(s) with no real reason: {thin}"
