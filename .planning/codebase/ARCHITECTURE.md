<!-- refreshed: 2026-10-16 -->
# Architecture

**Analysis Date:** 2026-10-16  
**System:** SHADOWCOMM — Reliable Communications & Research Platform  
**Repository:** `https://github.com/PriyalSingh23/Final-Project`  

---

## 1. System Overview

```text
┌─────────────────────────────────────────────────────────────────────────────────────────────┐
│                       Presentation Tier: SHADOWCOMM Modern Web UI                           │
│  React 19.2.8 + TypeScript 6.0 + Vite 8.3.4 + Tailwind CSS v4 (`frontend/src/`)             │
│  Compiled to `frontend/dist/` and served at root `/` on Port 5050 by `messaging/server.py`  │
├─────────────────┬───────────────────┬────────────────────┬─────────────────┬────────────────┤
│  Messages View  │  Research Lab     │  Connectivity      │  Devices View   │  Security View │
│  - 3-Panel UX   │  - Model Verif.   │  - Multi-tier ping │  - DMR Adapter  │  - PBKDF2 Auth │
│  - Signed ACKs  │  - Loss / BER viz │  - Fault Injection │  - STAR-V Lock  │  - RBAC Admin  │
│  - Event Audit  │  - IQ Scatter     │  - Outage Sim.     │  - LPI Transcvr │  - Audit Logs  │
│  - IndexedDB    │  - MPS Detect     │  - Auto-reconnect  │  - Relay Telemetry│ - GCM Envelope │
└────────┬────────┴─────────┬─────────┴──────────┬─────────┴────────┬────────┴────────┬───────┘
         │                  │                    │                  │                 │
         └──────────────────┴────────────────────┼──────────────────┴─────────────────┘
                                                 ▼
┌─────────────────────────────────────────────────────────────────────────────────────────────┐
│                          API Routing & Unified Server Tier                                  │
│  Flask 3.x REST API Blueprint `api_v1` on Port 5050 (`messaging/server.py`, `api.py`)       │
│  Routes: `/api/v1/health`, `/api/v1/auth/*`, `/api/v1/security/*`,                         │
│          `/api/v1/messages/*`, `/api/v1/endpoints/*`, `/api/v1/research/*`                  │
└────────────────────────────────────────┬────────────────────────────────────────────────────┘
                                         │
                 ┌───────────────────────┴───────────────────────┐
                 ▼                                               ▼
┌───────────────────────────────────────────────┐ ┌───────────────────────────────────────────┐
│     Security & Authenticated Encryption       │ │         Messaging Engine & States         │
│  `messaging/crypto_v2.py`, `auth_service.py`  │ │  `messaging/service.py`, `state_machine`  │
├───────────────────────────────────────────────┤ ├───────────────────────────────────────────┤
│  • AES-256-GCM v2 Envelope (0x02 prefix,      │ │  • Deterministic State Machine transitions│
│    96-bit random nonce, 128-bit MAC tag)      │ │    (SUBMITTED -> QUEUED -> IN_TRANSIT     │
│  • PBKDF2-HMAC-SHA256 (100k iters + salt)     │ │     -> DELIVERED / EXPIRED / FAILED)      │
│  • RBAC (ADMINISTRATOR, OPERATOR, VIEWER)     │ │  • Deduplication via Client Idempotency   │
│  • 60-min session TTL & 5-strike lockout      │ │  • Durable Signed ACK Reconciliation      │
└───────────────────────┬───────────────────────┘ └─────────────────────┬─────────────────────┘
                        │                                               │
                        └───────────────────────┬───────────────────────┘
                                                ▼
┌─────────────────────────────────────────────────────────────────────────────────────────────┐
│                     Delivery Queue Worker & Persistence Tier                                │
│  `messaging/worker.py`, `messaging/db.py`, `messaging/models.py`                            │
├───────────────────────────────────────────────┬─────────────────────────────────────────────┤
│  • Atomic leasing with `worker_lease_id`      │  • SQLite 3 WAL Mode (`PRAGMA busy_timeout= │
│  • Exponential backoff retry policy           │    5000`, `synchronous=NORMAL`)             │
│  • Chronological `message_events` audit trail │  • Schema auto-migrations for v2 columns    │
│  • Terminal state timeout reconciliation      │  • Browser client IndexedDB fallback cache  │
└───────────────────────────────────────┬─────────────────────────────────────────────────────┘
                                        │
                                        ▼
┌─────────────────────────────────────────────────────────────────────────────────────────────┐
│                    Interoperability & Multi-Transport Broker Layer                          │
│  `integration/manager.py` (BaseTransportAdapter, Capability Matrix, Priority Routing)       │
├──────────────────────┬──────────────────────┬──────────────────────┬────────────────────────┤
│ LPI-CGAN Transceiver │ Motorola MOTOTRBO TMS│ STAR-V Tactical SDR  │ Decoupled Ground /     │
│ `integration/lpi_cgan`│ `integration/motorola`│ `integration/starv`  │ Mobile Relay Manager   │
│ • RS(42,34) + CRC8   │ • 280-byte DMR limit │ • Hard safety lockout│ • Battery/Temp/Buffer  │
│ • Keyed Zadoff-Chu   │ • Simulation mode    │ • ICD verification   │ • Store-and-forward    │
│ • State: READY       │ • State: SIMULATION  │ • State: LOCKED_OUT  │ • Failsafe decoupled   │
└──────────┬───────────┴──────────────────────┴──────────────────────┴────────────────────────┘
           │
           ▼
┌─────────────────────────────────────────────────────────────────────────────────────────────┐
│                   Physical SDR & Neural Signal Processing Layer                             │
│  `lpi_v4/` (`lpi_core.py`, `lpi_crypto.py`, `lpi_stats.py`, `uhd_io.py`)                    │
├───────────────────────────────────────────────┬─────────────────────────────────────────────┤
│  • PyTorch `LPIGenerator`, `LPIDecoder`       │  • Ettus Research USRP B200/B210 UHD driver │
│  • 8-domain EW Statistics (KS, Kurtosis, C42) │  • Baseband complex IQ streaming            │
│  • Apple Silicon Metal (MPS) + CPU fallback   │  • Deterministic BER vs SNR evaluation      │
└───────────────────────────────────────────────┴─────────────────────────────────────────────┘
```

---

## 2. Component Responsibilities

| Component | Responsibility | File Path |
|---|---|---|
| **SHADOWCOMM Frontend** | Production 5-view tactical console (Messages, Research Lab, Connectivity, Devices, Security) with IndexedDB outbox. | `frontend/src/` |
| **Unified Server** | Serves compiled React SPA assets, configures CORS, initializes SQLite DB, registers API routes. | `messaging/server.py` |
| **REST API Gateway** | Versioned `/api/v1` endpoints for auth, messages, endpoints, audit logs, and research telemetry. | `messaging/api.py` |
| **Auth & RBAC Service** | PBKDF2 password hashing, session issuance/revocation, brute-force protection, RBAC permission checks. | `messaging/auth_service.py` |
| **Crypto Envelope v2** | Authenticated AES-256-GCM encryption with fresh 96-bit nonces, AAD header binding, and tampering defense. | `messaging/crypto_v2.py` |
| **Messaging Service** | Core message lifecycle orchestration: deduplication, queue ingestion, inbox delivery, audit logging. | `messaging/service.py` |
| **State Machine** | Strict, deterministic transitions (`SUBMITTED` → `QUEUED` → `IN_TRANSIT` → `DELIVERED` / `EXPIRED` / `FAILED`). | `messaging/state_machine.py` |
| **Queue Delivery Worker**| Background daemon process with atomic conditional leasing, exponential backoff, and ACK validation. | `messaging/worker.py` |
| **Ack Manager** | Cryptographically signed receipt generation, signature tracking, and bidirectional ACK reconciliation. | `messaging/ack_manager.py` |
| **Transport Manager** | Unified broker managing radio adapters, capability declarations, readiness filtering, and link routing. | `integration/manager.py` |
| **LPI-CGAN Adapter** | Neural transceiver bridge applying RS(42,34) FEC, CRC-8, and neural spreading modulation to payloads. | `integration/lpi_cgan/adapter.py` |
| **Motorola Adapter** | DMR TMS adapter enforcing 280-byte packet ceilings and XCMP protocol simulation. | `integration/motorola/adapter.py` |
| **STAR-V Adapter** | Tactical SDR simulation adapter with mandatory software safety lockout until physical ICD verified. | `integration/starv/adapter.py` |
| **Relay Nodes Manager**| Autonomous ground/aerial relay telemetry, queue buffering, and payload decoupling failsafes. | `integration/relay_nodes/manager.py` |
| **SDR Research Service**| Serves model checkpoints, manifest verification, training curves, BER sweeps, and baseband IQ telemetry. | `integration/sdr_research/service.py` |
| **LPI v4 Physical Core**| PyTorch `LPIGenerator` / `LPIDecoder`, Zadoff-Chu synchronization preambles, and matched filter demodulation. | `lpi_v4/lpi_core.py` |

---

## 3. Core Architectural Patterns

### Pattern 1: Asynchronous Store-and-Forward Decoupling
- **No Physical RF Blocking on Application Tier:** The REST API and UI client never wait synchronously on radio transmitters, buffer flushes, or physical propagation. 
- **Persist-Before-Emit:** Ingestion writes messages to SQLite in `SUBMITTED` state immediately within an atomic transaction. Only after persistence does the background worker lease and dispatch the frame.
- **Client Outbox Resilience:** If the server is unreachable or offline, the client frontend caches pending messages in browser `IndexedDB` (`shadowcomm_outbox_db`) and synchronizes upon reconnect using preserved idempotency keys.

### Pattern 2: Multi-Transport Interoperability Abstraction
- All radio and network links inherit from `BaseTransportAdapter` with uniform method signatures: `send_payload()`, `check_readiness()`, `get_capabilities()`.
- Transports explicitly declare readiness: `READY`, `SIMULATION_ONLY`, `LOCKED_OUT`, `OFFLINE`.
- Tactical safety lockouts are enforced in code—never allowing unverified simulation code to drive physical RF hardware.

### Pattern 3: Atomic Distributed Lease Scheduling
- Delivery workers claim queued messages using conditional SQL updates:
  ```sql
  UPDATE messages 
  SET status = 'IN_TRANSIT', worker_lease_id = :worker_id, lease_expires_at = :expires_at 
  WHERE message_id = :id AND status = 'QUEUED';
  ```
- Protects against duplicate transmissions across concurrent worker threads or restarted processes.
- Expired leases are automatically reclaimed and rescheduled with exponential backoff.

### Pattern 4: Authenticated Cryptographic Envelope (v2)
- Plaintext payloads are encapsulated into a versioned binary envelope:
  `[0x02] (1 byte) || Nonce (12 bytes) || Ciphertext (N bytes) || Tag (16 bytes)`.
- Eliminates the Gen 1 fixed-counter vulnerability and guarantees authenticated integrity.

---

## 4. Primary Data Flows

### Flow A: Offline Message Delivery with Durable ACK
1. **Client Submission:** User clicks send in React console. UI checks network connectivity. If offline, writes to IndexedDB outbox; if online, sends `POST /api/v1/messages` with `client_idempotency_key`.
2. **Ingestion & Persistence:** `MessagingService.submit_message()` validates payload, authenticates session, deduplicates against existing key, and persists message with state `SUBMITTED`.
3. **Queue Promotion:** Message status transitions immediately to `QUEUED` with an audit record written to `message_events`.
4. **Worker Lease:** `QueueWorker` polls SQLite, acquires message via `lease_expires_at`, sets state to `IN_TRANSIT`, and increments `delivery_attempts`.
5. **Transport Dispatch:** `QueueWorker` routes payload through `TransportManager` to the selected adapter (LPI-CGAN, Motorola DMR, or Simulated Link).
6. **Recipient Processing:** Recipient endpoint decodes payload, verifies integrity, stores message in `inbox`, and generates a signed receipt.
7. **ACK Reconciliation:** Recipient posts ACK back to sender. `AckManager` validates receipt signature, updates message to `DELIVERED`, records event, and clears worker lease.

### Flow B: Research Model Verification & Telemetry
1. **Frontend Request:** `ResearchLabView` mounts and requests `/api/v1/research/checkpoints` and `/api/v1/research/training-history`.
2. **Manifest Verification:** Backend calculates SHA-256 hash of `lpi_v4/run/lpi_v4.best.pt` and compares against `export_manifest.json` digest.
3. **Hardware Probe:** Backend checks `torch.backends.mps.is_available()` on Apple Silicon and queries system memory.
4. **Data Delivery:** Frontend receives verified model metadata, 75-epoch training loss curves, BER vs SNR curves, and baseband IQ constellation points.
5. **Interactive Evaluation:** User triggers on-demand evaluation sweep; backend runs validation without blocking messaging queues.

---

## 5. Architectural Constraints & Platform Considerations

1. **macOS Port Allocation Strategy:**
   - **Port 5050:** Canonical backend, REST API, and static distribution of React SPA.
   - **Port 5173:** Dedicated to Vite HMR during active frontend development only.
   - **Avoid Port 5000:** Occupied natively on macOS Monterey+ by Apple AirPlay Receiver (`ControlCenter`).
   - **Avoid Port 5001:** Legacy prototype port permanently decommissioned.

2. **Apple Silicon PyTorch / OpenBLAS Safety:**
   - `import torch` must precede all `numpy` and `scipy` imports across all entry points to prevent dynamic linker symbol collision and segfaults (`SIGSEGV 139`).
   - Metal Performance Shaders (MPS) is utilized for neural tensor inference, with deterministic CPU fallback for numerical unit tests.

3. **SQLite WAL Concurrency:**
   - Write-Ahead Logging (`PRAGMA journal_mode=WAL`) allows simultaneous readers without blocking writers.
   - 5000ms busy timeout ensures zero `database is locked` exceptions under concurrent worker and API threads.

---

*Refreshed: 2026-10-16*
