#!/usr/bin/env bash
# Checks every proof. Needs coqc (Ubuntu: apt-get install coq).
set -euo pipefail
cd "$(dirname "$0")"
coqc -Q . Infoset Kernel.v
coqc -Q . Infoset Witnesses.v
coqc -Q . Infoset Delta.v
coqc -Q . Infoset DeltaWitnesses.v
coqc -Q . Infoset Audit.v
