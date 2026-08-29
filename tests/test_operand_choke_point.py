"""The operand-check choke point is closed by construction.

The class this guards: "an integer literal in a Player/Team position must name a
real seat/team." It is closed not by enumerating the positions (that list rots
the day a new position is added -- exactly how PR #92's per-site guard failed
three review rounds) but by routing EVERY operand coercion through one function,
`typecheck._check_operand`, which runs the seat/team range check. This module is
the pin that keeps it closed: it fails the day a new coercion site calls
`coercible(...)` directly instead of routing through the choke point.

Domain: the operand-coercion checks in `cardlang/typecheck.py`. Registry: the
set of `coercible(...)` CALL sites (found via `ast`, so docstring/comment
mentions do not count). Property: every such call is inside `_check_operand`, OR
carries a `# choke-point-exempt` marker at its site naming why it is not an
operand coercion (there are exactly two such reasons, three calls).

Born green (all routing is already in place). red under: at any residual site,
restore the bare form the choke point replaced -- e.g. in
`_check_state_default_type`, put back `if not coercible(got, declared):
bag.error(...)` in place of the `_check_operand(...)` call. An unmarked
`coercible(` call then appears outside `_check_operand`, and
`test_no_coercible_escapes_the_choke_point` reddens (naming that line). The
edit plants the fault in the production code under guard, not in this test.
"""
from __future__ import annotations

import ast
import pathlib

import cardlang.typecheck

_SRC_PATH = pathlib.Path(cardlang.typecheck.__file__)
_SOURCE = _SRC_PATH.read_text()
_TREE = ast.parse(_SOURCE)
_LINES = _SOURCE.splitlines()
_MARKER = "choke-point-exempt"


def _func(name: str) -> ast.FunctionDef:
    for node in ast.walk(_TREE):
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return node
    raise AssertionError(f"{name} not found in typecheck.py")


def _coercible_calls() -> list[ast.Call]:
    return [
        node
        for node in ast.walk(_TREE)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "coercible"
    ]


def _in_choke_point(call: ast.Call) -> bool:
    choke = _func("_check_operand")
    end = choke.end_lineno or choke.lineno
    return choke.lineno <= call.lineno <= end


def _marked(call: ast.Call) -> bool:
    end = call.end_lineno or call.lineno
    return any(_MARKER in _LINES[ln - 1] for ln in range(call.lineno, end + 1))


def test_no_coercible_escapes_the_choke_point() -> None:
    """Every `coercible(...)` call routes through `_check_operand` (so the
    seat/team range check applies) or is marked exempt with a reason. A new
    coercion site that calls `coercible` directly reddens this until it routes
    through the choke point or is marked."""
    escapes = [
        c for c in _coercible_calls()
        if not _in_choke_point(c) and not _marked(c)
    ]
    assert not escapes, (
        f"coercible() is called outside _check_operand, unmarked, at line(s) "
        f"{[c.lineno for c in escapes]}: route the operand through _check_operand "
        f"so the seat/team range check applies, or mark the line "
        f"'# {_MARKER}: <reason it is not an operand coercion>'."
    )


def test_choke_point_holds_exactly_one_coercible() -> None:
    """`_check_operand` IS the single `coercible` call every operand routes
    through. Inlining the check back at a site would leave the escape pin green
    while defeating it, so the count is pinned here too."""
    inside = [c for c in _coercible_calls() if _in_choke_point(c)]
    assert len(inside) == 1


def test_exemptions_are_only_the_documented_ones() -> None:
    """The whitelist is exactly three reasons: the symmetric equality check (two
    operands, no single `expected` -- two calls), the `again` Boolean check (a
    state-var NAME resolved to a type, not an operand expression -- one call),
    and the `primitives { }` index-binder check (a parameter's declared
    annotation against an index domain's member type -- two DECLARED types, so
    there is no operand expression to range-check -- one call).
    Pinning the count means a FOURTH exemption cannot be slipped in without a
    test noticing and a reviewer having to bless it."""
    marked = [c for c in _coercible_calls() if _marked(c)]
    assert len(marked) == 4, (
        f"expected 4 marked-exempt coercible() calls (equality x2, again x1, "
        f"primitive index binder x1), "
        f"found {len(marked)} at line(s) {sorted(c.lineno for c in marked)}"
    )
