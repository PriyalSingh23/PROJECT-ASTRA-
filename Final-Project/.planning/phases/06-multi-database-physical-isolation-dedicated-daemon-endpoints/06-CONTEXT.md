# Phase 6: Multi-Database Physical Isolation & Dedicated Daemon Endpoints - Context

**Gathered:** 2026-10-20  
**Status:** Ready for planning

<domain>
## Phase Boundary

Phase 6 isolates Station Alpha and Station Bravo into physically distinct SQLite databases (`alpha.db` and `bravo.db`) running on dedicated server ports (5051 for Station Alpha, 5052 for Station Bravo) with zero shared in-memory variables or filesystem locks. Cross-station communication transitions from local database updates to authentic HTTP/REST peer forwarding across simulated channel impairments, verified from an updated dual-feed React web console.

</domain>

<decisions>
## Implementation Decisions

### 1. Port & Console Topography
- **D-01:** **Unified Gateway + Direct Access.** The canonical web interface runs on port 5050 (or Vite dev 5173/5050) providing a side-by-side dual-feed monitoring dashboard connected to both Station Alpha (`http://127.0.0.1:5051/api/v1`) and Station Bravo (`http://127.0.0.1:5052/api/v1`). Additionally, each daemon independently serves its own standalone tactical console directly at its dedicated port (`:5051` or `:5052`).
  — **Reversibility:** costly — Affects frontend API client baseUrl configuration, reverse proxy routing, and dual-station feed listeners.

### 2. Cross-Station Transport Protocol
- **D-02:** **REST Peer-to-Peer Transport with Impairment Pipeline.** When Station Alpha dispatches a message addressed to Station Bravo, Alpha's background delivery worker makes an HTTP POST request to Station Bravo's incoming ingest endpoint (`http://127.0.0.1:5052/api/v1/endpoints/incoming`) routed through the tactical impairment engine (latency, drop rates, air-gap outage simulation). Station Bravo persists the message in `bravo.db`, issues a signed HMAC ACK back over HTTP, and Alpha reconciles `signed_ack_receipt` in `alpha.db`.
  — **Reversibility:** costly — Changes the simulated transport layer from direct SQLite updates to remote HTTP transmission.

### 3. Database & Identity Enforcement
- **D-03:** **Strict Local Node Identity.** `alpha.db` is initialized with Station Alpha (`endpoint-a`) designated as the local node; submissions attempting to author messages as `endpoint-b` directly into `alpha.db` are rejected with HTTP 403 `IDENTITY_SPOOFING_BLOCKED`. Station Bravo (`bravo.db`) enforces the identical rule for `endpoint-b`. Local drafts cannot forge remote identities.
  — **Reversibility:** one-way — Enforces database schema and API route validation contracts preventing node impersonation.

### 4. Developer Launcher & Multi-Daemon Orchestration
- **D-04:** **Unified Multi-Station Launcher.** `scripts/dev.sh` supports a `--dual-station` flag (enabled by default) that spins up Station Alpha on port 5051 (`alpha.db`), Station Bravo on port 5052 (`bravo.db`), and the unified frontend console on port 5050 with single-command `trap cleanup INT TERM EXIT` process lifecycle management. Standalone single-station mode is supported via `--station alpha` or `--station bravo`.
  — **Reversibility:** reversible — Shell script wrapper managing background Python daemon processes.

### the agent's Discretion
- Port selection defaults: 5051 for Alpha, 5052 for Bravo, 5050 for Gateway/Frontend UI.
- Database file locations: `Final-Project/data/alpha.db` and `Final-Project/data/bravo.db` (auto-created on startup).
- Health check endpoints: `GET /api/v1/health` reports node identity (`station_id`, `station_name`, `db_path`, `port`, `worker_status`).

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Architecture & Requirements
- `.planning/REQUIREMENTS.md` § 1 — Requirements `MDB-01`, `MDB-02`, `MDB-03`.
- `.planning/ROADMAP.md` § Phase 6 — Phase goals and acceptance criteria.
- `.planning/milestones/v1.0-ROADMAP.md` — Verified Milestone 1 baseline.

### Core Implementation Files
- `Final-Project/messaging/db.py` — Engine creation, SQLite WAL pragmas, connection pooling, and multi-DB path support.
- `Final-Project/messaging/server.py` — Flask application factory `create_app(db_path, station_id, port)` and `--with-worker` supervisor.
- `Final-Project/messaging/worker.py` — Background queue leasing and dispatch integration.
- `Final-Project/messaging/transport.py` — Impairment pipeline and peer forwarding adapter.
- `Final-Project/messaging/api.py` — Ingest endpoints (`POST /api/v1/endpoints/incoming`) and identity validation.
- `Final-Project/frontend/src/services/api.ts` — Multi-endpoint baseUrl routing for Alpha (5051) and Bravo (5052).
- `Final-Project/scripts/dev.sh` — Multi-daemon process launcher and trap handler.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `create_app(db_path: str = None)` in `messaging/server.py`: Already accepts dynamic `db_path`, easily extensible with `station_id` and `station_port`.
- `QueueWorker(worker_id, db_path)` in `messaging/worker.py`: Already parameterizes `db_path`, enabling isolated worker processes per database.
- `MessagesView.tsx` & `StationConsoleColumn.tsx`: Already structure Alpha and Bravo columns cleanly; easily parameterized to query port 5051 and 5052 endpoints.

### Established Patterns
- **SQLite WAL Concurrency:** `busy_timeout=5000` before `journal_mode=WAL` prevents database locking during simultaneous API and worker access.
- **Dynamic Linker Safety:** `import torch` strictly precedes `numpy` and `scipy` on macOS Apple Silicon.
- **Microsecond Timestamps:** Microsecond-precision ISO timestamps on all message events.

### Integration Points
- `messaging/api.py`: Add `POST /api/v1/endpoints/incoming` endpoint for cross-station peer packet delivery.
- `messaging/transport.py`: Route peer transmissions to remote station port via HTTP requests with impairment wrapper.
- `frontend/src/services/api.ts`: Add station-aware client routing (`api.forStation('alpha')` / `api.forStation('bravo')`).

</code_context>

<specifics>
## Specific Ideas

- Launching `./scripts/dev.sh` boots both daemons:
  - Station Alpha: `http://127.0.0.1:5051` (DB: `alpha.db`)
  - Station Bravo: `http://127.0.0.1:5052` (DB: `bravo.db`)
  - Web Console: `http://127.0.0.1:5050`
- If Station Bravo's daemon is shut down, Station Alpha's transmissions enter `FAILED_RETRYABLE` in `alpha.db`, demonstrating true physical network air-gap isolation.

</specifics>

<deferred>
## Deferred Ideas

- Post-Quantum Cryptography (ML-KEM / Kyber hybrid encryption) — Deferred to Phase 7.
- Multi-Hop Ad-Hoc Mesh Routing across > 5 nodes — Deferred to Phase 8.
- Live WebGL Spectrum Waterfall & PCAP Export — Deferred to Phase 9.

</deferred>

---

*Phase: 06-multi-database-physical-isolation-dedicated-daemon-endpoints*  
*Context gathered: 2026-10-20*
