#!/usr/bin/env bash
# ==============================================================================
# SHADOWCOMM — macOS Environment Setup Script
# ==============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

echo "========================================================================"
echo "  SHADOWCOMM — Setting up development environment on macOS"
echo "  Project Root: ${PROJECT_ROOT}"
echo "========================================================================"

# 1. Detect Python 3
PYTHON_BIN=""
if [ -x "/Users/sabhay/radioconda/bin/python3" ]; then
    PYTHON_BIN="/Users/sabhay/radioconda/bin/python3"
elif command -v python3 &>/dev/null; then
    PYTHON_BIN="$(command -v python3)"
else
    echo "[ERROR] Python 3 not found. Please install Python 3.10+ or radioconda."
    exit 1
fi

echo "[1/4] Using Python: $("${PYTHON_BIN}" --version) at ${PYTHON_BIN}"

# 2. Verify Python dependencies
echo "[2/4] Verifying Python dependencies..."
"${PYTHON_BIN}" -c "
import flask, sqlalchemy, Crypto, reedsolo
try:
    import torch
    print('  - PyTorch available (Apple Silicon MPS:', hasattr(torch.backends, 'mps') and torch.backends.mps.is_available(), ')')
except ImportError:
    print('  - [WARNING] PyTorch not found. Neural research features will use analytical fallbacks.')
print('  - Core messaging, crypto, and database modules ready.')
"

# 3. Detect Node & npm for frontend
echo "[3/4] Verifying Node.js and npm..."
if ! command -v node &>/dev/null || ! command -v npm &>/dev/null; then
    echo "[ERROR] Node.js and npm are required to build the frontend. Please install Node 18+."
    exit 1
fi
echo "  - Node: $(node -v), npm: $(npm -v)"

# 4. Install frontend packages and build
echo "[4/4] Building React 19 + TypeScript + Vite frontend..."
cd "${PROJECT_ROOT}/frontend"
npm install --silent
npm run build

echo "========================================================================"
echo "  Setup complete! Built assets verified in frontend/dist/"
echo "  To launch the application, run: ./scripts/dev.sh"
echo "========================================================================"
