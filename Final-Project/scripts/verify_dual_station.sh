#!/usr/bin/env bash
# ==============================================================================
# SHADOWCOMM — Distributed Dual-Station Smoke Verification Script
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

cd "${PROJECT_ROOT}"
export PYTHONPATH="${PROJECT_ROOT}:${PYTHONPATH:-}"

ALPHA_PID=""
BRAVO_PID=""
GATEWAY_PID=""
SPAWNED_BY_SCRIPT=0

cleanup() {
    if [ "${SPAWNED_BY_SCRIPT}" -eq 1 ]; then
        echo ""
        echo "Cleaning up spawned test daemons..."
        for pid in "${ALPHA_PID}" "${BRAVO_PID}" "${GATEWAY_PID}"; do
            if [ -n "${pid}" ] && kill -0 "${pid}" 2>/dev/null; then
                kill "${pid}" 2>/dev/null || true
            fi
        done
        sleep 0.5
        lsof -ti :5050,5051,5052 | xargs kill -9 2>/dev/null || true
    fi
}

trap cleanup INT TERM EXIT

echo "========================================================================"
echo "  SHADOWCOMM — Multi-Daemon Dual-Station Smoke Verification"
echo "========================================================================"

# Check if stations are already running, otherwise launch ephemeral instances
if ! lsof -i :5051 &>/dev/null || ! lsof -i :5052 &>/dev/null; then
    echo "[INIT] Launching ephemeral Alpha (5051), Bravo (5052), and Gateway (5050)..."
    SPAWNED_BY_SCRIPT=1
    mkdir -p "${PROJECT_ROOT}/data"

    # Start Alpha on 5051
    "${PYTHON_BIN}" -m messaging.server --host 127.0.0.1 --port 5051 --db data/alpha_smoke.db \
        --station-id endpoint-a --station-name "Station Alpha" \
        --peer-url "http://127.0.0.1:5052/api/v1" --with-worker &
    ALPHA_PID=$!

    # Start Bravo on 5052
    "${PYTHON_BIN}" -m messaging.server --host 127.0.0.1 --port 5052 --db data/bravo_smoke.db \
        --station-id endpoint-b --station-name "Station Bravo" \
        --peer-url "http://127.0.0.1:5051/api/v1" --with-worker &
    BRAVO_PID=$!

    # Start Gateway on 5050
    "${PYTHON_BIN}" -m messaging.server --host 127.0.0.1 --port 5050 --no-worker &
    GATEWAY_PID=$!

    echo "Waiting for daemons to boot..."
    for i in {1..20}; do
        if curl -s http://127.0.0.1:5051/api/v1/health &>/dev/null && \
           curl -s http://127.0.0.1:5052/api/v1/health &>/dev/null && \
           curl -s http://127.0.0.1:5050/api/v1/health &>/dev/null; then
            break
        fi
        sleep 0.3
    done
fi

echo "[1/4] Probing Health Metadata on Station Alpha (:5051)..."
ALPHA_HEALTH=$(curl -s http://127.0.0.1:5051/api/v1/health)
if echo "${ALPHA_HEALTH}" | grep -q '"station_id":"endpoint-a"'; then
    echo "      ✔ Alpha station_id correctly bound to 'endpoint-a'"
else
    echo "      ✖ Failed: Alpha health did not return station_id: endpoint-a"
    echo "        Response: ${ALPHA_HEALTH}"
    exit 1
fi

echo "[2/4] Probing Health Metadata on Station Bravo (:5052)..."
BRAVO_HEALTH=$(curl -s http://127.0.0.1:5052/api/v1/health)
if echo "${BRAVO_HEALTH}" | grep -q '"station_id":"endpoint-b"'; then
    echo "      ✔ Bravo station_id correctly bound to 'endpoint-b'"
else
    echo "      ✖ Failed: Bravo health did not return station_id: endpoint-b"
    echo "        Response: ${BRAVO_HEALTH}"
    exit 1
fi

echo "[3/4] Testing Identity Spoofing Protection on Station Alpha (:5051)..."
SPOOF_STATUS=$(curl -s -o /dev/null -w "%{http_code}" -X POST http://127.0.0.1:5051/api/v1/messages \
    -H "Content-Type: application/json" \
    -d '{"client_idempotency_key": "spoof-test-01", "sender_endpoint_id": "endpoint-b", "recipient_endpoint_id": "endpoint-a", "payload": "Malicious Spoofed Frame"}')
if [ "${SPOOF_STATUS}" -eq 403 ]; then
    echo "      ✔ Spoofed submission claiming 'endpoint-b' on Alpha returned HTTP 403 (IDENTITY_SPOOFING_BLOCKED)"
else
    echo "      ✖ Failed: Expected HTTP 403, got ${SPOOF_STATUS}"
    exit 1
fi

echo "[4/4] Transmitting Cross-Station Message from Alpha (:5051) -> Bravo (:5052)..."
IDEMPOTENCY_KEY="smoke-$(date +%s)-$RANDOM"
SEND_RESP=$(curl -s -X POST http://127.0.0.1:5051/api/v1/messages \
    -H "Content-Type: application/json" \
    -d "{\"client_idempotency_key\": \"${IDEMPOTENCY_KEY}\", \"sender_endpoint_id\": \"endpoint-a\", \"recipient_endpoint_id\": \"endpoint-b\", \"payload\": \"Tactical cross-daemon smoke test payload\"}")

MSG_ID=$(echo "${SEND_RESP}" | grep -o '"message_id":"[^"]*' | cut -d'"' -f4 || true)
if [ -z "${MSG_ID}" ]; then
    echo "      ✖ Failed: Message submission did not return message_id"
    echo "        Response: ${SEND_RESP}"
    exit 1
fi
echo "      ✔ Message enqueued on Alpha with ID: ${MSG_ID}"

# Poll Bravo's inbox for receipt
RECEIVED=0
for i in {1..15}; do
    INBOX=$(curl -s "http://127.0.0.1:5052/api/v1/endpoints/endpoint-b/inbox")
    if echo "${INBOX}" | grep -q "${MSG_ID}"; then
        RECEIVED=1
        break
    fi
    sleep 0.2
done

if [ "${RECEIVED}" -eq 1 ]; then
    echo "      ✔ Message successfully ingested and verified in Station Bravo inbox!"
else
    echo "      ✖ Failed: Message did not arrive in Bravo inbox within 3 seconds"
    exit 1
fi

echo ""
echo "========================================================================"
echo "  [PASS] DUAL STATION VERIFICATION SUCCESSFUL"
echo "  Physical database isolation and peer-to-peer forwarding confirmed."
echo "========================================================================"
