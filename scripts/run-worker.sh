#!/usr/bin/env bash
# Runs the worker. Defaults to fully mocked adapters (PPDM_*_MODE=mock) — see
# worker/config.py and docs/WORKER_SETUP.md for how to point this at real
# services once corporate access exists.
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."

if [ -f .venv/bin/activate ]; then
  # shellcheck disable=SC1091
  source .venv/bin/activate
fi

export PPDM_POWERPLATFORM_MODE="${PPDM_POWERPLATFORM_MODE:-mock}"
export PPDM_SHAREPOINT_MODE="${PPDM_SHAREPOINT_MODE:-mock}"
export PPDM_COPILOT_MODE="${PPDM_COPILOT_MODE:-mock}"

python3 -m worker.main "$@"
