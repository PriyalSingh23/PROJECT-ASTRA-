# External Integrations & Adapters

**Analysis Date:** 2026-10-16  
**System:** SHADOWCOMM — Reliable Communications & Research Platform  
**Repository:** `https://github.com/PriyalSingh23/Final-Project`  

---

## 1. Radio & Transport Interoperability Adapters

**Unified Transport Broker (`integration/manager.py`):**
- Capability declaration, readiness filtering, and priority-based message routing via `BaseTransportAdapter`.

**1. LPI-CGAN Neural Transceiver Adapter (`integration/lpi_cgan/adapter.py`):**
- Bridges the software-defined neural generator and decoder into the unified messaging transport layer.
- Framing: Reed-Solomon $RS(42,34)$ + CRC-8 integrity checksum.
- Physical Layer: Keyed Zadoff-Chu preambles, 8x spreading ($9.03\text{ dB}$ processing gain), and coarse/fine Carrier Frequency Offset (CFO) compensation.
- Readiness: `READY` / `SIMULATION_ONLY`.

**2. Motorola MOTOTRBO / APX Adapter (`integration/motorola/adapter.py`):**
- Text Messaging Service (TMS) over XCMP protocol simulation.
- Enforces strict 280-byte Digital Mobile Radio (DMR) packet size ceiling.
- Readiness: `SIMULATION_ONLY` (physical transmission prohibited during controlled pilot).

**3. STAR-V Tactical SDR Adapter (`integration/starv/adapter.py`):**
- STARS-V Mk III tactical radio simulation interface.
- Permanent software safety lockout enforced. Physical transmission strictly disabled until official vendor Interface Control Document (ICD) is verified.
- Readiness: `LOCKED_OUT`.

**4. Decoupled Ground & Mobile Relay Manager (`integration/relay_nodes/manager.py`):**
- Manages autonomous store-and-forward relay nodes.
- Telemetry reporting: Battery level %, Temperature °C, Storage usage %, and Queued bundle count.
- Independent payload failsafes ensuring flight safety decoupling from radio payloads.

**5. SDR RF Hardware Driver (`lpi_v4/uhd_io.py`, `lpi_v4/tx_usrp.py`, `lpi_v4/rx_usrp.py`):**
- Ettus Research USRP B200/B210 over-the-air complex IQ transmission and reception via UHD driver.

---

## 2. Data Storage & Persistence

**1. Relational Database (Backend):**
- **SQLite 3 with Write-Ahead Logging (WAL)** (`messaging/db.py`, `shadowcomm_messaging.db`).
- Pragmas enforced on connection:
  - `PRAGMA journal_mode=WAL` (concurrent read/write without locks)
  - `PRAGMA synchronous=NORMAL`
  - `PRAGMA busy_timeout=5000` (resilience against busy locks)
  - `PRAGMA foreign_keys=ON`
- Schema Tables: `users`, `user_sessions`, `security_audit_logs`, `endpoints`, `messages`, `inbox`, `acknowledgements`, `delivery_attempts`, `message_events`.
- Safe automatic column migrations for `endpoints.auth_token`, `messages.incident_id`, and `messages.signed_ack_receipt`.

**2. Client-Side Offline Database (Browser):**
- **IndexedDB (`shadowcomm_outbox_db`)** via `frontend/src/services/outboxDb.ts`.
- Stores unsent client messages when network or transport link is severed.
- Auto-syncs to backend using preserved `client_idempotency_key` upon reconnection.

**3. File Storage:**
- PyTorch Checkpoints: `lpi_v4/run/lpi_v4.best.pt`, `generator_lpi.pt`, `decoder_lpi.pt`.
- Manifest Digest: `lpi_v4/run/export_manifest.json` (SHA-256 integrity matched).
- Empirical Benchmarks: `lpi_v4/run/eval.json`, `lpi_v4/run/eval.md`, `lpi_v4/run/lpi_v4.csv`.

---

## 3. Authentication & Security

**1. Enterprise User Authentication (`messaging/auth_service.py`):**
- PBKDF2-HMAC-SHA256 password hashing (100,000 iterations + 16-byte cryptographically secure salt).
- Role-Based Access Control (RBAC): `ADMINISTRATOR`, `OPERATOR`, `VIEWER`.
- 60-minute session TTL with automatic revocation.
- Automatic 5-attempt brute-force lockout with 15-minute cooldown.
- Complete security event audit trail in `security_audit_logs`.

**2. Versioned Authenticated Payload Encryption (`messaging/crypto_v2.py`):**
- Versioned envelope (`0x02`) utilizing `AES-256-GCM`.
- Cryptographically fresh 96-bit random nonces (`os.urandom(12)`) per message.
- 128-bit authentication tag protecting against message tampering or keystream reuse.

**3. Endpoint Pre-Shared Token Authentication:**
- `X-Endpoint-Token` or Bearer header verification for autonomous station nodes (`endpoint-a`, `endpoint-b`).

---

## 4. REST API & Endpoint Contracts

**Canonical API Blueprint (`/api/v1` in `messaging/api.py`):**

| Route | Method | Purpose |
|---|---|---|
| `/api/v1/health` | GET | Subsystem health, version, transport status |
| `/api/v1/auth/login` | POST | Operator login (returns session token & RBAC role) |
| `/api/v1/auth/logout` | POST | Session revocation |
| `/api/v1/auth/me` | GET | Active session verification and profile |
| `/api/v1/security/audit-logs` | GET | Confidential audit trail (admin role required) |
| `/api/v1/messages` | GET/POST | List messages or submit idempotent payload |
| `/api/v1/messages/<id>` | GET | Message status, payload, signed ACK |
| `/api/v1/messages/<id>/events` | GET | Chronological audit transition timeline |
| `/api/v1/messages/<id>/retry` | POST | Manual retry of failed message |
| `/api/v1/messages/<id>/cancel` | POST | Cancel pending message |
| `/api/v1/endpoints` | GET | List configured stations |
| `/api/v1/endpoints/<id>/inbox` | GET | Received messages for endpoint |
| `/api/v1/endpoints/<id>/outbox` | GET | Submitted messages from endpoint |
| `/api/v1/queue/stats` | GET | Real-time queue counters & transport state |
| `/api/v1/sim/transport` | GET/POST | Query or configure RF link impairments |
| `/api/v1/sim/faults` | POST | Inject drop/error faults for testing |
| `/api/v1/transports` | GET | Registered transport adapters & readiness |
| `/api/v1/relays` | GET | Relay nodes and telemetry |
| `/api/v1/research/status` | GET | LPI-CGAN parameters & checkpoints audit |
| `/api/v1/research/checkpoints`| GET | Checkpoint SHA-256 digest validation |
| `/api/v1/research/training-history`| GET | 75-epoch training logs (`lpi_v4.csv`) |
| `/api/v1/research/evaluation` | GET | Empirical stealth & BER benchmark report |
| `/api/v1/research/signal-sample`| GET | Complex baseband IQ & PSD samples |
| `/api/v1/research/environment`| GET | macOS hardware, MPS & CPU detection |
| `/api/v1/research/eval/run` | POST | Controlled evaluation execution |

---

*Integration audit refreshed: 2026-10-16*
