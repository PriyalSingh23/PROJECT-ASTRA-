#!/usr/bin/env bash
# ==============================================================================
# SHADOWCOMM — Stop Distributed Development Daemons & Processes
# ==============================================================================
set -euo pipefail

echo "Stopping all running SHADOWCOMM processes across cluster ports..."

# Stop ports 5050, 5051, 5052, 5173
echo "  - Terminating listeners on ports :5050, :5051, :5052, :5173..."
lsof -ti :5050,5051,5052,5173 | xargs kill -9 2>/dev/null || true

# Stop python background delivery workers and servers
echo "  - Cleaning up messaging.worker and messaging.server processes..."
pkill -f "messaging.server" 2>/dev/null || true
pkill -f "messaging.worker" 2>/dev/null || true

# Stop legacy processes on port 5001 if any
if lsof -i :5001 &>/dev/null; then
    echo "  - Terminating legacy process on port 5001..."
    lsof -ti :5001 | xargs kill -9 2>/dev/null || true
fi

echo "All SHADOWCOMM daemons and services stopped cleanly."
