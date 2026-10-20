#!/usr/bin/env bash
# SHADOWLINK FIELD - Start Field Stack (FastAPI + Queue Worker)
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
LOG_DIR="${PROJECT_ROOT}/logs"
RUN_DIR="${PROJECT_ROOT}/run"

mkdir -p "${LOG_DIR}" "${RUN_DIR}"

export PYTHONPATH="${PROJECT_ROOT}/backend:${PROJECT_ROOT}"

PYTHON_BIN="/Users/sabhay/radioconda/bin/python3"
if [ ! -f "${PYTHON_BIN}" ]; then
    PYTHON_BIN="python3"
fi

SERVER_PID_FILE="${RUN_DIR}/server.pid"
WORKER_PID_FILE="${RUN_DIR}/worker.pid"

# Stop existing processes if running
if [ -f "${SERVER_PID_FILE}" ]; then
    OLD_PID=$(cat "${SERVER_PID_FILE}")
    if kill -0 "${OLD_PID}" 2>/dev/null; then
        echo "[!] Server already running (PID: ${OLD_PID})."
    else
        rm -f "${SERVER_PID_FILE}"
    fi
fi

if [ -f "${WORKER_PID_FILE}" ]; then
    OLD_PID=$(cat "${WORKER_PID_FILE}")
    if kill -0 "${OLD_PID}" 2>/dev/null; then
        echo "[!] Worker already running (PID: ${OLD_PID})."
    else
        rm -f "${WORKER_PID_FILE}"
    fi
fi

echo "[*] Launching SHADOWLINK FIELD FastAPI Core..."
nohup "${PYTHON_BIN}" -m uvicorn app.main:app --host 0.0.0.0 --port 8000 > "${LOG_DIR}/server.log" 2>&1 &
SERVER_PID=$!
echo "${SERVER_PID}" > "${SERVER_PID_FILE}"
echo "    -> Server started (PID: ${SERVER_PID}) on http://127.0.0.1:8000"

echo "[*] Launching SHADOWLINK FIELD Background Queue Worker..."
nohup "${PYTHON_BIN}" -m app.services.worker > "${LOG_DIR}/worker.log" 2>&1 &
WORKER_PID=$!
echo "${WORKER_PID}" > "${WORKER_PID_FILE}"
echo "    -> Worker started (PID: ${WORKER_PID})"

echo ""
echo "================================================================="
echo "  SHADOWLINK FIELD IS RUNNING"
echo "  Web UI & API:  http://127.0.0.1:8000"
echo "  API Docs:      http://127.0.0.1:8000/docs"
echo "  Logs:          ${LOG_DIR}/"
echo "  To Stop:       ./scripts/stop_field_stack.sh"
echo "================================================================="
