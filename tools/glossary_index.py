"""Generate `docs/glossary.md` — the index — from the entries in `docs/glossary/`.

The index is derived, never edited: one line per term, cheap to load in bulk
(issue #214, D1). An entry's own file is opened only when that term is the thing
in question. `tests/test_glossary.py` pins the index against this generator the
way the IR goldens are pinned, so an entry edited without regenerating fails.

Run: `python -m tools.glossary_index --write`
"""

from __future__ import annotations

import argparse
import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parent.parent
ENTRIES = ROOT / "docs" / "glossary"
INDEX = ROOT / "docs" / "glossary.md"

LAYERS = ("kernel", "card-family", "compiler", "interop", "check", "process")

# No `retired`: a retired spelling is a field on the canonical entry (issue #214,
# D2), so it never needs an entry of its own. A status value nothing can carry is
# a category that reads as available and is not -- the shape that let the reserved
# words fall out of their own table.
STATUSES = ("canonical", "reserved")

# The section each layer heads in the index, in order.
LAYER_SECTIONS = [
    ("kernel", "The game model and the runtime"),
    ("card-family", "The card family"),
    ("compiler", "The compiler"),
    ("interop", "The OpenSpiel boundary"),
    ("check", "Check vocabulary"),
    ("process", "The Operating Harness"),
]

PREAMBLE = ROOT / "docs" / "glossary" / "_preamble.md"


class EntryError(AssertionError):
    """An entry is malformed. `AssertionError` so the linter reddens uniformly."""


def parse_entry(path: pathlib.Path) -> dict[str, str]:
    """One entry's frontmatter. Deliberately a small hand parser rather than a
    YAML dependency: the format is fixed by `tests/test_glossary.py`, and a
    parser that accepts more than the format would let a malformed entry
    through the very check that exists to catch it."""
    text = path.read_text()
    if not text.startswith("---\n"):
        raise EntryError(f"{path.name}: no frontmatter")
    _, fm, body = text.split("---\n", 2)
    fields: dict[str, str] = {}
    for line in fm.splitlines():
        if not line.strip():
            continue
        m = re.match(r"^([a-z_]+):\s*(.*)$", line)
        if m is None:
            raise EntryError(f"{path.name}: frontmatter line is not `key: value`: {line!r}")
        fields[m.group(1)] = m.group(2).strip()
    fields["_body"] = body.strip()
    fields["_slug"] = path.stem
    return fields


def load() -> list[dict[str, str]]:
    entries = [parse_entry(p) for p in sorted(ENTRIES.glob("*.md"))
               if not p.name.startswith("_")]
    if not entries:
        raise EntryError(f"no entries in {ENTRIES} — an empty index covers nothing")
    return entries


def render(entries: list[dict[str, str]]) -> str:
    out = [PREAMBLE.read_text().rstrip(), ""]
    seen = set()
    for layer, heading in LAYER_SECTIONS:
        rows = [e for e in entries if e["layer"] == layer and e["status"] != "reserved"]
        if not rows:
            continue
        out += [f"## {heading}", "", "| Term | Definition | Home |", "|---|---|---|"]
        for e in sorted(rows, key=lambda x: x["_slug"]):
            seen.add(e["_slug"])
            home = e.get("home") or ""
            out.append(f"| [{e['term']}](glossary/{e['_slug']}.md) | {e['definition']} | {home} |")
        out.append("")
    # Keyed on the `reserved` FLAG, not on `status`: a word can be reserved and
    # still name a concept of its own (`round`, `rule`, `library`, `outcome`),
    # and those four have `status: canonical`. Selecting by status would drop
    # them from the one table that is supposed to list every word to qualify.
    reserved = [e for e in entries if e["reserved"] == "true"]
    if reserved:
        out += ["## Reserved words — never use unqualified", "",
                "These carry several meanings each; always qualify them. The ones "
                "that also name a concept of their own keep their entry in a section "
                "above as well.", "",
                "| Word | Approved compounds |", "|---|---|"]
        for e in sorted(reserved, key=lambda x: x["_slug"]):
            compounds = e["definition"]
            if e["status"] == "canonical":
                marker = "**Reserved word.** Approved compounds: "
                line = next((ln for ln in e["_body"].splitlines() if ln.startswith(marker)), None)
                if line is None:
                    raise EntryError(
                        f"{e['_slug']}.md is `reserved: true` but its body states no "
                        f"approved compounds — the reserved table would list the "
                        f"concept's definition instead of the compounds to use"
                    )
                compounds = line[len(marker):]
            out.append(f"| [{e['term']}](glossary/{e['_slug']}.md) | {compounds} |")
        out.append("")
    return "\n".join(out).rstrip() + "\n"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    args = ap.parse_args()
    text = render(load())
    if args.write:
        INDEX.write_text(text)
        print(f"wrote {INDEX.relative_to(ROOT)} ({len(load())} entries)")
    else:
        print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
