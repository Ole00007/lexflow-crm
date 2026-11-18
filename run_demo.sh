#!/usr/bin/env bash
# Local demo server for the LexFlow Mindmap build (dev only).
# Only the port-5057 lock holder may run/restart this.
set -euo pipefail
cd "$(dirname "$0")"

SCRATCH="$HOME/.hermes/profiles/smoothy_op_dir/cache/scratch"
export DATABASE_URL="sqlite:///$SCRATCH/mindmap_demo.db"
export LEXFLOW_VAULT_DIR="$SCRATCH/demo_vault"
export SECRET_KEY="local-demo-secret-key-for-dev-only-32b"
export JWT_SECRET_KEY="local-demo-jwt-secret-key-for-dev-only-32b"
export AGENT_ENABLED=1
export LEXFLOW_AGENT_LLM_ROUTING="${LEXFLOW_AGENT_LLM_ROUTING:-0}"

PY="$HOME/projects/lexflow/lexflow-crm-wt-hmerge/local_venv/bin/python"
exec "$PY" "$SCRATCH/mindmap_boot_5057.py"
