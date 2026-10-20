#!/usr/bin/env bash
# SHADOWLINK FIELD - Stop Field Stack
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
RUN_DIR="${PROJECT_ROOT}/run"

SERVER_PID_FILE="${RUN_DIR}/server.pid"
WORKER_PID_FILE="${RUN_DIR}/worker.pid"

if [ -f "${SERVER_PID_FILE}" ]; then
    PID=$(cat "${SERVER_PID_FILE}")
    echo "[*] Stopping Server (PID: ${PID})..."
    kill "${PID}" 2>/dev/null || true
    rm -f "${SERVER_PID_FILE}"
fi

if [ -f "${WORKER_PID_FILE}" ]; then
    PID=$(cat "${WORKER_PID_FILE}")
    echo "[*] Stopping Worker (PID: ${PID})..."
    kill "${PID}" 2>/dev/null || true
    rm -f "${WORKER_PID_FILE}"
fi

echo "[+] SHADOWLINK FIELD services stopped."
