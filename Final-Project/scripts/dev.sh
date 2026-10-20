#!/usr/bin/env bash
# ==============================================================================
# SHADOWCOMM — Distributed Multi-Daemon Development Environment Launcher
# ==============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

PYTHON_BIN=""
if [ -x "/Users/sabhay/radioconda/bin/python3" ]; then
    PYTHON_BIN="/Users/sabhay/radioconda/bin/python3"
elif command -v python3 &>/dev/null; then
    PYTHON_BIN="$(command -v python3)"
else
    echo "[ERROR] Python 3 not found."
    exit 1
fi

MODE="dual"
if [ $# -gt 0 ]; then
    case "$1" in
        --dual-station|dual)
            MODE="dual"
            ;;
        --station)
            if [ $# -ge 2 ] && [ "$2" = "alpha" ]; then
                MODE="alpha"
            elif [ $# -ge 2 ] && [ "$2" = "bravo" ]; then
                MODE="bravo"
            else
                echo "Usage: $0 --station [alpha|bravo]"
                exit 1
            fi
            ;;
        --single)
            MODE="single"
            ;;
        *)
            MODE="dual"
            ;;
    esac
fi

# Track background processes for clean shutdown
ALPHA_PID=""
BRAVO_PID=""
GATEWAY_PID=""
VITE_PID=""

cleanup() {
    echo ""
    echo "========================================================================"
    echo "  Shutting down SHADOWCOMM services cleanly..."
    echo "========================================================================"
    PIDS=("${ALPHA_PID}" "${BRAVO_PID}" "${GATEWAY_PID}" "${VITE_PID}")
    for pid in "${PIDS[@]}"; do
        if [ -n "${pid}" ] && kill -0 "${pid}" 2>/dev/null; then
            echo "  - Terminating process (PID ${pid})..."
            kill "${pid}" 2>/dev/null || true
        fi
    done
    sleep 0.5
    for pid in "${PIDS[@]}"; do
        if [ -n "${pid}" ] && kill -0 "${pid}" 2>/dev/null; then
            kill -9 "${pid}" 2>/dev/null || true
        fi
    done
    echo "  Freeing ports (5050, 5051, 5052, 5173)..."
    lsof -ti :5050,5051,5052,5173 | xargs kill -9 2>/dev/null || true
    echo "  All services stopped."
    exit 0
}

trap cleanup INT TERM EXIT

cd "${PROJECT_ROOT}"
export PYTHONPATH="${PROJECT_ROOT}:${PYTHONPATH:-}"
mkdir -p "${PROJECT_ROOT}/data"

# Build frontend if dist missing
if [ ! -d "${PROJECT_ROOT}/frontend/dist" ]; then
    echo "[BUILD] Building frontend distribution assets..."
    (cd "${PROJECT_ROOT}/frontend" && npm run build)
fi

echo "========================================================================"
echo "  SHADOWCOMM — Launching Distributed Multi-Daemon Environment"
echo "  Project Root: ${PROJECT_ROOT}"
echo "  Mode:         ${MODE}"
echo "========================================================================"

# Clear any lingering listeners
lsof -ti :5050,5051,5052,5173 | xargs kill -9 2>/dev/null || true
sleep 0.5

if [ "${MODE}" = "dual" ]; then
    # 1. Start Station Alpha (Port 5051, data/alpha.db)
    echo "[1/3] Starting Station Alpha Daemon on http://127.0.0.1:5051 (data/alpha.db)..."
    "${PYTHON_BIN}" -m messaging.server --host 127.0.0.1 --port 5051 --db data/alpha.db \
        --station-id endpoint-a --station-name "Station Alpha" \
        --peer-url "http://127.0.0.1:5052/api/v1" --with-worker &
    ALPHA_PID=$!

    # 2. Start Station Bravo (Port 5052, data/bravo.db)
    echo "[2/3] Starting Station Bravo Daemon on http://127.0.0.1:5052 (data/bravo.db)..."
    "${PYTHON_BIN}" -m messaging.server --host 127.0.0.1 --port 5052 --db data/bravo.db \
        --station-id endpoint-b --station-name "Station Bravo" \
        --peer-url "http://127.0.0.1:5051/api/v1" --with-worker &
    BRAVO_PID=$!

    # 3. Start Gateway & Frontend Server (Port 5050)
    echo "[3/3] Starting Unified Console Gateway on http://127.0.0.1:5050..."
    "${PYTHON_BIN}" -m messaging.server --host 127.0.0.1 --port 5050 --no-worker &
    GATEWAY_PID=$!

    echo ""
    echo "========================================================================"
    echo "  SHADOWCOMM Distributed Cluster Online!"
    echo "========================================================================"
    echo "  • Station Alpha Daemon:   http://127.0.0.1:5051/ (data/alpha.db)"
    echo "  • Station Bravo Daemon:   http://127.0.0.1:5052/ (data/bravo.db)"
    echo "  • Unified Console Gateway: http://127.0.0.1:5050/"
    echo ""
    echo "  Default Logins:"
    echo "    - Operator: operator / OperatorPass@2026!"
    echo "    - Admin:    admin / AdminPass@2026!"
    echo "========================================================================"
    echo "  Press Ctrl+C to stop all daemons cleanly."
    echo ""

    wait "${ALPHA_PID}" "${BRAVO_PID}" "${GATEWAY_PID}"

elif [ "${MODE}" = "alpha" ]; then
    echo "Starting Station Alpha Daemon on http://127.0.0.1:5051..."
    "${PYTHON_BIN}" -m messaging.server --host 127.0.0.1 --port 5051 --db data/alpha.db \
        --station-id endpoint-a --station-name "Station Alpha" \
        --peer-url "http://127.0.0.1:5052/api/v1" --with-worker &
    ALPHA_PID=$!
    wait "${ALPHA_PID}"

elif [ "${MODE}" = "bravo" ]; then
    echo "Starting Station Bravo Daemon on http://127.0.0.1:5052..."
    "${PYTHON_BIN}" -m messaging.server --host 127.0.0.1 --port 5052 --db data/bravo.db \
        --station-id endpoint-b --station-name "Station Bravo" \
        --peer-url "http://127.0.0.1:5051/api/v1" --with-worker &
    BRAVO_PID=$!
    wait "${BRAVO_PID}"

else
    echo "Starting Single Canonical Node on http://127.0.0.1:5050..."
    "${PYTHON_BIN}" -m messaging.server --host 127.0.0.1 --port 5050 --with-worker &
    GATEWAY_PID=$!
    wait "${GATEWAY_PID}"
fi
