"""`python -m cardlang` — the console script's entry point, reached without it.

The package installs `cardlang` on PATH (`pyproject.toml`, `[project.scripts]`),
which a source checkout that was never installed does not have. Both forms run
the same `main`, so neither can grow behavior the other lacks.
"""

from __future__ import annotations

from cardlang.cli import main

if __name__ == "__main__":
    raise SystemExit(main())
