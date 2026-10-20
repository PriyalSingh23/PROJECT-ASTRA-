# SHADOWCOMM — macOS Operator & Developer Run Guide

**System:** SHADOWCOMM  
**Subtitle:** Reliable Communications & Research Platform  
**Target OS:** macOS (Apple Silicon M1/M2/M3/M4 & Intel x86_64)  
**Supported Execution:** Python 3.10+ (radioconda / Homebrew / venv) & Node.js 18+  

---

## 1. Quick Start (One Command)

From the project root (`/Users/sabhay/Downloads/PROJECT 13OCT/Final-Project`):

```bash
# Step 1: Install frontend dependencies and build production React assets
./scripts/setup_macos.sh

# Step 2: Start the complete development environment (Backend + Delivery Worker + Web UI)
./scripts/dev.sh
```

Open your browser to:
- **Primary Web Interface:** [http://127.0.0.1:5050/](http://127.0.0.1:5050/)
- **REST API Health Check:** [http://127.0.0.1:5050/api/v1/health](http://127.0.0.1:5050/api/v1/health)
- **Research Telemetry:** [http://127.0.0.1:5050/api/v1/research/status](http://127.0.0.1:5050/api/v1/research/status)

---

## 2. Port Allocation & macOS Network Architecture

| Port | Service | Status | Role |
|---|---|---|---|
| **5050** | `messaging.server` | **ACTIVE (Canonical)** | Unified Flask REST API, SQLite WAL persistence, and built React 19 UI. |
| **5173** | `vite` | **OPTIONAL (Dev)** | Live hot-reloading development server for UI engineers (`npm run dev` in `frontend/`). |
| **5000** | Apple `ControlCenter` | **RESERVED BY MACOS** | Used by Apple AirPlay Receiver on macOS 12+. Never used by SHADOWCOMM. |
| **5001** | Legacy `app.py` | **DEPRECATED & REMOVED** | Prototype script with fake metrics. Completely shut down; redirects to 5050. |

---

## 3. Seed Accounts & Role-Based Access Control (RBAC)

| Username | Passphrase | Role | Permissions |
|---|---|---|---|
| `operator` | `OperatorPassword123!` | `OPERATOR` | Send messages, inspect delivery receipts, trigger simulation tests, view Research Lab. |
| `admin` | `FieldAdmin2026!` | `ADMINISTRATOR` | Full system access, view confidential security audit logs, manage users, execute benchmarks. |
| `viewer` | `ViewerPassword123!` | `VIEWER` | Read-only inspection of telemetry and public queues. |

---

## 4. Subsystems & Navigation

### 4.1. Messages (Primary Console)
- **3-Panel WhatsApp/Spotify-Style Layout**:
  - **Left**: Station selector (`endpoint-a`, `endpoint-b`), search, contact cards with unread badges and transport pills.
  - **Center**: Chronological conversation history, message status icons, signed receipt verification, and tactical composer with quick presets (`Status Report`, `Check-In`, `Assistance Request`, `Resource Alert`).
  - **Right (Collapsible)**: Complete diagnostic timeline showing every state transition (`CREATED` &rarr; `QUEUED` &rarr; `LEASED` &rarr; `AWAITING_ACK` &rarr; `DELIVERED`).

### 4.2. Research Lab
- **Model Inventory**: Checkpoint digests verified against `lpi_v4/run/export_manifest.json`.
- **Empirical Benchmarks**: KS Gaussianity test $p=0.865$, kurtosis $2.991$, Energy Warden 8/8 pass ($S_c=0.140$), adversary detection accuracy $50.0\%$.
- **Training Curves**: 75-epoch convergence chart of Generator Loss, BER, and Warden score.
- **Constellation & PSD**: Baseband IQ scatter plot and Power Spectral Density plot.
- **macOS Execution**: Automatically detects Apple Silicon Metal Performance Shaders (MPS) and CPU fallback. Never assumes NVIDIA CUDA.

### 4.3. Connectivity & Impairment Simulator
- Independent indicators for Public Internet, Local Backend, Delivery Worker Daemon, and Virtual RF Link.
- Real-time simulation controls: Severed link toggle, latency slider (0-1500 ms), packet drop rate (0-100%), and ACK drop rate (0-100%).
- Ground relay telemetry: battery %, temperature, and storage %.

### 4.4. Devices & Radio Adapters
- Registered station endpoints with pre-shared token authentication.
- **Motorola MOTOTRBO Adapter**: TMS over XCMP simulation enforcing the 280-byte DMR packet limit.
- **STAR-V Tactical Adapter**: Permanent software safety lockout enforced.
- **LPI-CGAN Transceiver Adapter**: 9.03 dB spreading gain, Reed-Solomon RS(42,34) framing, and keyed Zadoff-Chu synchronization.

---

## 5. Stopping Services

To stop all background processes gracefully:

```bash
# Either press Ctrl+C in the terminal running ./scripts/dev.sh, or execute:
./scripts/stop_dev.sh
```
