<!-- refreshed: 2026-10-16 -->
# Codebase Structure

**Analysis Date:** 2026-10-16  
**System:** SHADOWCOMM — Reliable Communications & Research Platform  
**Repository:** `https://github.com/PriyalSingh23/Final-Project`  

---

## 1. Directory Layout

```
PROJECT 13OCT/
├── .planning/                                  # GSD project roadmap and codebase intelligence
│   └── codebase/                               # Structured codebase intelligence maps (STACK, ARCH, etc.)
├── Final-Project/                              # Primary production & research codebase
│   ├── docs/                                   # Platform documentation & audit guides
│   │   ├── APP_AUDIT.md                        # Complete audit of legacy vs modern platform
│   │   └── MACOS_RUN_GUIDE.md                  # Comprehensive macOS setup and operational guide
│   ├── frontend/                               # SHADOWCOMM Modern Web Application (React 19 + Vite)
│   │   ├── dist/                               # Production compiled SPA bundle (served by Flask at `/`)
│   │   │   ├── assets/                         # Compiled JavaScript chunks and CSS bundles
│   │   │   └── index.html                      # Single-page application entry point
│   │   ├── src/                                # Source TypeScript & React application code
│   │   │   ├── components/                     # Reusable UI widgets, layout navigation, modals
│   │   │   │   ├── Layout.tsx                  # Spotify/WhatsApp-caliber sidebar navigation layout
│   │   │   │   ├── SecurityModal.tsx           # Authentication modal and session login
│   │   │   │   └── StatusIndicator.tsx         # Real-time connectivity and status pills
│   │   │   ├── services/                       # API clients and browser persistence
│   │   │   │   ├── api.ts                      # REST API client with Bearer auth headers
│   │   │   │   └── outboxDb.ts                 # Browser IndexedDB offline outbox client
│   │   │   ├── views/                          # 5 primary application views
│   │   │   │   ├── MessagesView.tsx            # 3-panel messaging console with verified signed ACKs
│   │   │   │   ├── ResearchLabView.tsx         # Checkpoint SHA-256 verifier, training & BER charts
│   │   │   │   ├── ConnectivityView.tsx        # Public/Local/Worker/RF outage simulator & controls
│   │   │   │   ├── DevicesView.tsx             # Motorola DMR, STAR-V lockout, LPI transceiver cards
│   │   │   │   └── SecurityView.tsx            # RBAC user management, PBKDF2 auth, security audit
│   │   │   ├── App.tsx                         # Root reactive application controller & tab router
│   │   │   ├── index.css                       # Tailwind CSS v4 directives and typography
│   │   │   └── main.tsx                        # React DOM client entry point
│   │   ├── package.json                        # Frontend dependencies and build scripts
│   │   ├── tsconfig.json                       # TypeScript compiler options
│   │   └── vite.config.ts                      # Vite 8 configuration with Tailwind CSS v4 plugin
│   ├── integration/                            # Multi-Transport Interoperability Adapters
│   │   ├── lpi_cgan/                           # LPI-CGAN neural transceiver bridge adapter
│   │   │   └── adapter.py                      # RS(42,34) framing, CRC8, neural spreading modulation
│   │   ├── motorola/                           # Motorola MOTOTRBO / APX TMS adapter
│   │   │   └── adapter.py                      # 280-byte DMR packet ceiling, XCMP simulation
│   │   ├── relay_nodes/                        # Ground and aerial store-and-forward relay manager
│   │   │   └── manager.py                      # Telemetry monitoring, queue buffer, failsafe decoupling
│   │   ├── sdr_research/                       # SDR research integration service
│   │   │   └── service.py                      # Checkpoint digest validation, training curves, BER sweeps
│   │   ├── starv/                              # STAR-V tactical SDR radio adapter
│   │   │   └── adapter.py                      # Strict software safety lockout until ICD verification
│   │   └── manager.py                          # Unified Transport Broker (capabilities & routing)
│   ├── lpi_research/                           # Modular legacy research framework
│   │   ├── crypto/                             # Crypto primitives
│   │   ├── datasets/                           # RadioML and synthetic modulation sets
│   │   ├── fec/                                # Reed-Solomon coding routines
│   │   ├── gan/                                # Early experimental GAN architectures
│   │   ├── sdr/                                # SDR script wrappers
│   │   └── signal_processing/                  # Baseband filters and FFT utilities
│   ├── lpi_v4/                                 # Gen 2 LPI Waveform Synthesis & Hardware Drivers
│   │   ├── run/                                # Checkpoints, evaluation reports, and manifests
│   │   │   ├── eval.json                       # Empirical evaluation metrics and BER summaries
│   │   │   ├── eval.md                         # Markdown report of EW detection batteries
│   │   │   ├── export_manifest.json            # SHA-256 digest validation manifest for models
│   │   │   └── lpi_v4.best.pt                  # Production-grade trained PyTorch model checkpoint
│   │   ├── lpi_core.py                         # LPIGenerator, LPIDecoder, Warden, Zadoff-Chu preambles
│   │   ├── lpi_crypto.py                       # FrameCodec: AES-128-GCM, CRC-8, RS(42,34)
│   │   ├── lpi_eval.py                         # Evaluation runner for 8-domain EW statistics
│   │   ├── lpi_stats.py                        # KS tests, spectral flatness, kurtosis, C42 statistics
│   │   ├── lpi_train.py                        # Adversarial training harness for LPI models
│   │   ├── rx_usrp.py                          # Over-the-air USRP receiver execution script
│   │   ├── tx_usrp.py                          # Over-the-air USRP transmitter execution script
│   │   └── uhd_io.py                           # Ettus USRP B200/B210 streaming wrapper
│   ├── messaging/                              # Reliable Offline Messaging Subsystem
│   │   ├── ack_manager.py                      # Durable signed receipt tracking & reconciliation
│   │   ├── api.py                              # Flask Blueprint registering canonical `/api/v1` routes
│   │   ├── auth_service.py                     # PBKDF2 hashing, RBAC, session state, brute-force lockout
│   │   ├── crypto_v2.py                        # Authenticated AES-256-GCM v2 envelope encryption
│   │   ├── db.py                               # SQLite connection pooling, WAL pragmas, auto-migrations
│   │   ├── models.py                           # SQLAlchemy models (users, sessions, messages, events, etc.)
│   │   ├── retry_policy.py                     # Exponential backoff calculation and attempt tracking
│   │   ├── server.py                           # Unified Web & API Server (Port 5050)
│   │   ├── service.py                          # MessagingService lifecycle orchestration and deduplication
│   │   ├── state_machine.py                    # Deterministic state machine and valid transition rules
│   │   ├── transport.py                        # Abstract transport link and simulated channel impairment
│   │   └── worker.py                           # Persistent background queue worker with atomic leases
│   ├── scripts/                                # macOS Automation and Lifecycle Scripts
│   │   ├── dev.sh                              # Unified single-command launcher for backend and frontend
│   │   ├── setup_macos.sh                      # Dependency installation and environment check
│   │   └── stop_dev.sh                         # Graceful shutdown script for all running processes
│   ├── tests/                                  # Comprehensive 55-Test Pytest Suite
│   │   ├── integration/                        # Hardware and adapter integration tests
│   │   │   ├── test_adapters.py                # Motorola, STAR-V, LPI-CGAN adapter tests (5 tests)
│   │   │   └── test_relay_nodes.py             # Relay telemetry and payload failsafes (4 tests)
│   │   ├── test_lpi_v4.py                      # LPI physical waveform and PyTorch unit tests (22 tests)
│   │   ├── test_offline_messaging.py           # Concurrency, idempotency, retry, timeout tests (14 tests)
│   │   ├── test_security_auth.py               # PBKDF2 auth, RBAC, AES-256-GCM v2 tests (9 tests)
│   │   └── test_simulation_1000_messages.py    # 1,050-message outage and crash recovery test (1 test)
│   ├── app.py                                  # Canonical root launcher forwarding to `messaging.server`
│   ├── pytest.ini                              # Pytest configuration with pythonpath discovery
│   └── requirements.txt                        # Python backend dependencies
└── SHADOWLINK-FIELD/                           # Field Pilot Specifications & Decoupled Scaffold
    ├── backend/                                # FastAPI field backend skeleton
    └── docs/                                   # Field operational procedures and specifications
```

---

## 2. Key File Locations & Entry Points

### Primary Application Entry Points
- **Single-Command Launcher:** `Final-Project/scripts/dev.sh` (launches Flask backend on port 5050, checks frontend dist, monitors worker daemon).
- **Graceful Shutdown:** `Final-Project/scripts/stop_dev.sh` (identifies and cleanly shuts down processes on port 5050, 5173, and active queue workers).
- **Backend & Web Server:** `Final-Project/messaging/server.py` (CLI: `python -m messaging.server --port 5050`).
- **Background Queue Worker:** `Final-Project/messaging/worker.py` (CLI: `python -m messaging.worker`).
- **Frontend Source Directory:** `Final-Project/frontend/` (Build: `npm run build`; Dev: `npm run dev` on port 5173).
- **Canonical Root Forwarder:** `Final-Project/app.py` (CLI: `python app.py` -> launches `messaging.server` on port 5050).

### Core Business Logic
- **Lifecycle Orchestration:** `Final-Project/messaging/service.py` (`submit_message()`, `receive_message()`).
- **Deterministic State Transition:** `Final-Project/messaging/state_machine.py` (`transition()`).
- **Lease Queue Dispatch:** `Final-Project/messaging/worker.py` (`acquire_next_message()`, `process_message()`).
- **Cryptographic Security:** `Final-Project/messaging/crypto_v2.py` (`encrypt_payload_v2()`, `decrypt_payload_v2()`).
- **Enterprise Authentication:** `Final-Project/messaging/auth_service.py` (`authenticate_user()`, `verify_session()`).
- **Multi-Transport Routing:** `Final-Project/integration/manager.py` (`TransportManager`).

### Data Persistence & Schemas
- **Database Engine & Connection Pool:** `Final-Project/messaging/db.py` (`get_session()`, `init_db()`).
- **ORM Table Schemas:** `Final-Project/messaging/models.py` (`Message`, `Endpoint`, `User`, `UserSession`, `SecurityAuditLog`, `MessageEvent`, `DeliveryAttempt`, `Acknowledgement`).
- **Client Offline Storage:** `Final-Project/frontend/src/services/outboxDb.ts` (`IndexedDB` outbox table).

### Research, Waveform & RF Core
- **Neural Waveform Models:** `Final-Project/lpi_v4/lpi_core.py` (`LPIGenerator`, `LPIDecoder`, `Warden`).
- **Forward Error Correction & Framing:** `Final-Project/lpi_v4/lpi_crypto.py` (`FrameCodec`).
- **Electronic Warfare Statistics:** `Final-Project/lpi_v4/lpi_stats.py` (`EWStatistics`).
- **Hardware Drivers:** `Final-Project/lpi_v4/uhd_io.py` (`UHDWrapper`).

---

## 3. Naming Conventions

### File & Directory Naming
- **Python Modules:** `snake_case.py` (e.g., `ack_manager.py`, `crypto_v2.py`, `lpi_core.py`).
- **React Components & Views:** `PascalCase.tsx` (e.g., `MessagesView.tsx`, `SecurityModal.tsx`, `StatusIndicator.tsx`).
- **TypeScript Utilities & Services:** `camelCase.ts` (e.g., `outboxDb.ts`, `api.ts`).
- **Shell Automation Scripts:** `snake_case.sh` (e.g., `dev.sh`, `setup_macos.sh`, `stop_dev.sh`).
- **Documentation:** `UPPER_SNAKE_CASE.md` (e.g., `MACOS_RUN_GUIDE.md`, `APP_AUDIT.md`).

### Code Identifiers
- **Classes:** `PascalCase` (e.g., `MessagingService`, `QueueWorker`, `FrameCodec`, `BaseTransportAdapter`).
- **Functions & Methods:** `snake_case()` (Python) / `camelCase()` (TypeScript).
- **Constants & Enums:** `UPPER_SNAKE_CASE` (e.g., `MessageStatus.QUEUED`, `UserRole.ADMINISTRATOR`).
- **Database Tables:** `snake_case_plural` (e.g., `messages`, `endpoints`, `security_audit_logs`).

---

## 4. Development Workflow & Adding Code

### Where to Add New Features

| Feature Type | Target Directory | Key Files to Update |
|---|---|---|
| **New API Route** | `Final-Project/messaging/` | Add endpoint in `api.py`, declare handler in `service.py`. |
| **New DB Column / Table** | `Final-Project/messaging/` | Update `models.py`, add migration statement in `db.py:init_db()`. |
| **New UI View / Tab** | `Final-Project/frontend/src/` | Create view in `views/`, add navigation in `components/Layout.tsx`, route in `App.tsx`. |
| **New Hardware / Radio Adapter** | `Final-Project/integration/` | Inherit from `BaseTransportAdapter` in new subdirectory, register in `integration/manager.py`. |
| **New Research Waveform / DSP** | `Final-Project/lpi_v4/` | Extend `lpi_core.py` or `lpi_crypto.py`, add test in `tests/test_lpi_v4.py`. |
| **New Automated Test** | `Final-Project/tests/` | Add test functions to relevant module in `tests/`. |

### Execution Commands
- **Run Full Automated Test Suite:**
  ```bash
  cd Final-Project && pytest -v
  ```
- **Launch Development Environment:**
  ```bash
  cd Final-Project && ./scripts/dev.sh
  ```
- **Graceful Shutdown:**
  ```bash
  cd Final-Project && ./scripts/stop_dev.sh
  ```

---

*Refreshed: 2026-10-16*
