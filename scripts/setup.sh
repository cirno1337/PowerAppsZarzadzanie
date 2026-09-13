#!/usr/bin/env bash
# Sets up a local Python environment for offline development. No network
# access, corporate VPN, or Microsoft account is required.
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."

PYTHON_BIN="${PYTHON_BIN:-python3}"
VENV_DIR=".venv"

if [ ! -d "$VENV_DIR" ]; then
  echo "Creating virtual environment in $VENV_DIR (with access to system site-packages, in case pytest is already installed system-wide and there's no network access to fetch it again)..."
  "$PYTHON_BIN" -m venv --system-site-packages "$VENV_DIR"
fi

# shellcheck disable=SC1091
source "$VENV_DIR/bin/activate"

echo "Installing dev dependencies (pytest)..."
if ! python -c "import pytest" 2>/dev/null; then
  pip install --quiet -e ".[dev]" || echo "Warning: could not install pytest (no network?). If it's already available system-wide, tests will still run."
fi

echo ""
echo "Setup complete. Next steps:"
echo "  source $VENV_DIR/bin/activate"
echo "  ./scripts/run-tests.sh   # run the test suite"
echo "  ./scripts/demo.sh         # run the full mock pipeline"
