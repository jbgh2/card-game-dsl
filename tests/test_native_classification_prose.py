"""Prose that CLASSIFIES a named native function names its actual registry.

property:   wherever prose labels a backticked function name a Builtin or a
            Primitive, the label matches the registry that name is declared in.
            `player_holding` is a Builtin; calling it a Primitive in the
            library catalogue teaches a designer the wrong half of the split
            `runtime/builtins.py` and `runtime/primitives.py` open by drawing.
domain:     every (label, name) pair in tracked `.py`/`.md`/`.cardlang`/`.lark`
            prose where the label is ADJACENT to the name in one of the forms
            in `_ADJACENCY` -- crossed against every name in the native
            registries.
registry:   the names come from `cardlang.builtins.functions` --
            `BUILTIN_CALL_FUNCS` against the union of the five `PRIMITIVE_*`
            sets -- so a name added to, moved between, or retired from a
            registry arrives here without anyone editing a fixture. The file
            walk is `git ls-files`; the adjacency forms are `_ADJACENCY`.
covered:    `test_no_prose_mislabels_a_native_function` over the full walk,
            plus `test_each_adjacency_form_is_matched` -- one row per form,
            each proving the matcher sees that form at all, so a form cannot
            silently stop matching and leave the sweep looking clean.
sampled:    none.
residual:   A label at a DISTANCE from the name it governs is out of the
            domain and stays review judgment: `kernel-migration.md` once read
            "Stud-local Primitives ... (like `team_of`)", where the apposition
            makes `team_of` an example of how they are called rather than a
            member of the set. No matcher resolves that without resolving the
            English, and a matcher that guessed would fire on correct prose --
            the same ruling #214 D4 makes for glossary usage. R3, recorded
            here rather than filed: the mechanism is the reviewer.
            Also out of domain: prose that classifies an unnamed thing ("a
            native registry", "the Primitive slot"), which has no backticked
            name to bind to. Both defects were real -- see the PR #332 review
            rounds -- and both are why this module claims the adjacent case
            only rather than a reach it does not have.

red under: relabel a known name -- e.g. in `docs/library.md` change
    "the Primitive `tarot_led_suit()`" to "the Builtin `tarot_led_suit()`"
    (its real home is `PRIMITIVE_CALL_FUNCS`), or in `docs/building.md`
    change "(Builtin query)" after `player_holding` to "(Primitive query)".
    Either was a shipped defect Codex caught on PR #332; both fail here.
"""

from __future__ import annotations

import ast
import io
import pathlib
import re
import subprocess
import tokenize

import pytest

from cardlang.builtins import functions as F

ROOT = pathlib.Path(__file__).resolve().parent.parent

BUILTIN_NAMES: frozenset[str] = F.BUILTIN_CALL_FUNCS
PRIMITIVE_NAMES: frozenset[str] = frozenset().union(
    F.PRIMITIVE_CALL_FUNCS,
    F.PRIMITIVE_TRICK_WINNERS,
    F.PRIMITIVE_AUCTION_OUTCOMES,
    F.PRIMITIVE_EARLY_PREDICATES,
    F.PRIMITIVE_CLIMB_LEADS,
    F.PRIMITIVE_CLIMB_FOLLOWS,
)

# The adjacency forms. Each binds ONE label to ONE immediately-neighbouring
# backticked name; a name reached across a comma, a list, or another
# backticked name is out of the domain (see `residual`).
#
# The name is the LEADING identifier of the backticked span, and the span may
# carry anything after it: the catalogue writes call spellings and whole
# signatures inside one span (`player_holding(Card) -> Player`), and the
# `name-then-parenthetical` probe below is exactly that shape -- it is what
# caught this pattern being too narrow when it required the span to end at the
# identifier.
_NAME = r"`(?P<name>[a-z_][a-z0-9_]*)[^`\n]*`"
_LABEL = r"(?P<label>Builtin|Primitive)s?"
_ADJACENCY: tuple[tuple[str, str], ...] = (
    # "the Builtin `tarot_led_suit()`" / "a Primitive query `f`"
    ("label-then-name", rf"{_LABEL}\s+(?:\w+\s+)?{_NAME}"),
    # "`player_holding(Card) -> Player` (Builtin query)"
    ("name-then-parenthetical", rf"{_NAME}[^`\n]{{0,40}}\(\s*{_LABEL}\b[^)\n]*\)"),
    # "`pot_share` is a Primitive" / "`lines`, a Builtin"
    ("name-then-copula", rf"{_NAME}[,]?\s+(?:is\s+)?(?:an?\s+)?{_LABEL}\b"),
)


def _tracked() -> list[pathlib.Path]:
    listing = subprocess.run(
        ["git", "ls-files", "-z", "*.py", "*.md", "*.cardlang", "*.lark"],
        cwd=ROOT, capture_output=True, text=True, check=True,
    ).stdout
    out = [ROOT / n for n in listing.split("\0") if n]
    assert out, "the file walk found nothing -- this check would pass vacuously"
    return out


def _prose(path: pathlib.Path, text: str) -> str:
    """Docstrings + comments for Python; everything outside a fence for
    Markdown; the whole file for `.lark`/`.cardlang`, which are comment-and-
    surface throughout. Mirrors `tests/test_glossary.py`'s boundary: a DSL
    fixture written as a Python string is source in another language, not
    prose making a claim."""
    if path.suffix == ".py":
        holders = (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)
        parts = [
            d
            for node in ast.walk(ast.parse(text))
            if isinstance(node, holders) and (d := ast.get_docstring(node, clean=False))
        ]
        parts += [
            t.string
            for t in tokenize.generate_tokens(io.StringIO(text).readline)
            if t.type == tokenize.COMMENT
        ]
        return "\n".join(parts)
    if path.suffix == ".md":
        kept, fenced = [], False
        for line in text.splitlines():
            if line.lstrip().startswith("```"):
                fenced = not fenced
                continue
            if not fenced:
                kept.append(line)
        return "\n".join(kept)
    return text


def _mislabels(text: str) -> list[tuple[str, str, str]]:
    """Every (form, name, label) in `text` whose label contradicts the registry."""
    out = []
    for form, pattern in _ADJACENCY:
        for m in re.finditer(pattern, text):
            name, label = m.group("name"), m.group("label").lower()
            if name in BUILTIN_NAMES and label == "primitive":
                out.append((form, name, "labelled Primitive, declared a Builtin"))
            elif name in PRIMITIVE_NAMES and label == "builtin":
                out.append((form, name, "labelled Builtin, declared a Primitive"))
    return out


# --- the gate ---------------------------------------------------------------


def test_the_two_registries_are_disjoint_and_non_empty() -> None:
    """The classification only means something if a name has ONE home. This is
    the premise every row below rests on, so it fails first and by itself.

    red under: add any `BUILTIN_CALL_FUNCS` member to `PRIMITIVE_CALL_FUNCS`.
    """
    assert BUILTIN_NAMES and PRIMITIVE_NAMES
    overlap = BUILTIN_NAMES & PRIMITIVE_NAMES
    assert not overlap, f"a name declared in both registries has no true label: {sorted(overlap)}"


def test_no_prose_mislabels_a_native_function() -> None:
    """red under: see the module docstring -- flip a real label in
    `docs/library.md` or `docs/building.md`."""
    found: list[str] = []
    scanned = 0
    for path in _tracked():
        try:
            text = _prose(path, path.read_text())
        except (SyntaxError, tokenize.TokenError) as exc:  # pragma: no cover - loud
            raise AssertionError(f"{path.relative_to(ROOT)} will not parse: {exc}") from exc
        scanned += len(text)
        for form, name, why in _mislabels(text):
            found.append(f"  {path.relative_to(ROOT)}: `{name}` {why} [{form}]")
    assert scanned, "scanned no prose -- this check would pass vacuously"
    assert not found, (
        "prose classifies a native function against its registry:\n"
        + "\n".join(sorted(found))
        + "\n\nA name's home is `cardlang/builtins/functions.py`: `BUILTIN_*` for the "
        "generic functions the language ships, `PRIMITIVE_*` for game-local Python."
    )


@pytest.mark.parametrize(
    "form,probe,name,label",
    [
        ("label-then-name", "reads the Builtin `tarot_led_suit()` first", "tarot_led_suit", "Builtin"),
        ("label-then-name", "a Primitive query `player_holding` here", "player_holding", "Primitive"),
        ("name-then-parenthetical", "`player_holding(Card) -> Player` (Primitive query)", "player_holding", "Primitive"),
        ("name-then-copula", "`tarot_led_suit` is a Builtin over the pile", "tarot_led_suit", "Builtin"),
    ],
)
def test_each_adjacency_form_is_matched(form: str, probe: str, name: str, label: str) -> None:
    """Every form in `_ADJACENCY` is proven to match, on a sentence carrying a
    KNOWN-wrong label. Without this, a form whose pattern drifted would stop
    matching and the sweep above would keep reporting clean -- the pin would be
    green because it had stopped looking, which is the failure this repo ranks
    with accepted-but-ignored.

    Every probe here is a real shipped defect from the PR #332 review rounds,
    not an invented sentence.

    red under: break the named form's pattern in `_ADJACENCY`.
    """
    hits = _mislabels(probe)
    assert hits, f"the {form!r} form matched nothing in {probe!r}"
    assert any(h[0] == form and h[1] == name for h in hits), (
        f"{probe!r} was matched, but not by {form!r} on `{name}` -- got {hits}"
    )


def test_a_correct_label_is_not_flagged() -> None:
    """The gate must be able to say yes. Otherwise it would pass the sweep only
    because it flags nothing at all.

    red under: swap the two registry lookups in `_mislabels`.
    """
    assert not _mislabels("reads the Primitive `tarot_led_suit()` first")
    assert not _mislabels("`player_holding(Card) -> Player` (Builtin query)")


def test_a_name_in_neither_registry_is_ignored() -> None:
    """Prose may classify things that are not native functions at all; only a
    name the registries KNOW is judged.

    red under: drop the registry membership tests from `_mislabels`.
    """
    assert not _mislabels("the Builtin `some_helper` and the Primitive `other_thing`")
