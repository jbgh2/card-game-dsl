#!/usr/bin/env bash
# tools/verify.sh — the worktree verification invocation, named so the
# permission charter can allow a script instead of an env-prefixed
# command pattern: a prefix rule that admits `VAR=x <anything>` admits
# anything (PR #311 review). Runs mypy or pytest as a module of the
# checkout's interpreter (never a bare `mypy` or `pytest` found on PATH,
# which can belong to another install); pytest runs with the worktree on
# PYTHONPATH. `import MODULE` imports one module by its dotted name, the
# form of the CI step that proves the openspiel extra is installed, and
# prints `import MODULE: ok`.
#
# The interpreter, first found wins, named on stderr:
#   1. the .venv beside the main worktree (`git rev-parse --git-common-dir`),
#      which every linked worktree shares (the venv-and-worktrees convention);
#   2. $VIRTUAL_ENV;
#   3. python3 on PATH.
# Verify cardlang resolves into the worktree, not the main checkout, when
# it matters.
#
# Usage: verify.sh mypy [args...] | verify.sh pytest [args...] | verify.sh import MODULE
set -euo pipefail

tool=${1:?usage: verify.sh mypy|pytest [args...] | verify.sh import MODULE}
shift
case "$tool" in
  mypy|pytest) ;;
  import)
    [ $# -eq 1 ] && [[ "$1" =~ ^[A-Za-z_][A-Za-z0-9_.]*$ ]] \
      || { echo "verify.sh: import takes one dotted module name" >&2; exit 2; } ;;
  *) echo "verify.sh: only mypy, pytest and import are chartered (got: $tool)" >&2; exit 2 ;;
esac

py="" why=""
common=$(git rev-parse --path-format=absolute --git-common-dir 2>/dev/null || true)
if [ "${common##*/}" = ".git" ] && [ -x "${common%/.git}/.venv/bin/python" ]; then
  py="${common%/.git}/.venv/bin/python" why="the .venv beside the main worktree"
elif [ -n "${VIRTUAL_ENV:-}" ] && [ -x "$VIRTUAL_ENV/bin/python" ]; then
  py="$VIRTUAL_ENV/bin/python" why="\$VIRTUAL_ENV"
elif command -v python3 >/dev/null 2>&1; then
  py=$(command -v python3) why="python3 on PATH"
else
  echo "verify.sh: no interpreter: no .venv beside the main worktree, no \$VIRTUAL_ENV, no python3 on PATH" >&2
  exit 2
fi
echo "verify.sh: interpreter $py ($why)" >&2

# mypy runs with no PYTHONPATH, as CI runs it: mypy reads a PYTHONPATH
# entry as installed packages and silences every error in the modules it
# follows there, `tools/` among them.
if [ "$tool" = mypy ]; then
  exec env -u PYTHONPATH "$py" -m mypy "$@"
fi
if [ "$tool" = import ]; then
  exec "$py" -c "import $1; print('import $1: ok')"
fi
PYTHONPATH="$PWD" exec "$py" -m pytest "$@"
