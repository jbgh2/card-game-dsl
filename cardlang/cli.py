"""Command-line entry point: parse + check a single game file, optionally emit IR.

    cardlang docs/games/hearts.md            # check only; silent on success
    cardlang docs/games/hearts.md --emit-ir  # check, then print the IR JSON
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from cardlang.diagnostics import DiagnosticError
from cardlang.pipeline import check_source, compile_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="cardlang")
    parser.add_argument(
        "file", help="game file (.cardlang raw DSL, or .md with a fenced DSL block)"
    )
    parser.add_argument(
        "--emit-ir",
        action="store_true",
        help="print the validated IR as JSON on success",
    )
    args = parser.parse_args(argv)

    path = Path(args.file)
    if not path.exists():
        print(f"cardlang: cannot read {path}: no such file", file=sys.stderr)
        return 2

    try:
        if args.emit_ir:
            print(json.dumps(compile_path(path), indent=2))
        else:
            check_source(path)
    except DiagnosticError as exc:
        print(exc.diagnostic.format(), file=sys.stderr)
        notes = getattr(exc, "__notes__", [])
        for note in notes:
            print(note, file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
