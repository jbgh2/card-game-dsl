#!/usr/bin/env bash
# tools/verify.sh — the worktree verification invocation, named so the
# permission charter can allow a script instead of an env-prefixed
# command pattern: a prefix rule that admits `VAR=x <anything>` admits
# anything (PR #311 review). Runs mypy or pytest with the worktree on
# PYTHONPATH and the main checkout's venv python (the venv-and-worktrees
# convention; verify cardlang resolves into the worktree, not the main
# checkout, when it matters).
#
# Usage: verify.sh mypy [args...] | verify.sh pytest [args...]
set -euo pipefail

VENV_PY="/Users/benh/Projects/Card game DSL/.venv/bin/python"
[ -x "$VENV_PY" ] || { echo "verify.sh: venv python not found at $VENV_PY" >&2; exit 2; }

tool=${1:?usage: verify.sh mypy|pytest [args...]}
shift
case "$tool" in
  mypy|pytest) PYTHONPATH="$PWD" exec "$VENV_PY" -m "$tool" "$@" ;;
  *) echo "verify.sh: only mypy and pytest are chartered (got: $tool)" >&2; exit 2 ;;
esac
