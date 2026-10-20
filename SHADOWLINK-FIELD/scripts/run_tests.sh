#!/usr/bin/env bash
# SHADOWLINK FIELD - Test Suite Runner
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

export PYTHONPATH="${PROJECT_ROOT}/backend:${PROJECT_ROOT}"

PYTHON_BIN="/Users/sabhay/radioconda/bin/python3"
if [ ! -f "${PYTHON_BIN}" ]; then
    PYTHON_BIN="python3"
fi

cd "${PROJECT_ROOT}"
echo "[*] Executing SHADOWLINK FIELD Automated Test Suite..."
"${PYTHON_BIN}" -m pytest tests/ -v "$@"
