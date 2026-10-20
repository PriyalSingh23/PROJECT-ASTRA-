# Architecture Research: Tactical Communications & LPI Platform

**Domain:** Tactical Store-and-Forward Messaging & Neural Spread-Spectrum Physical Layer  
**Researched:** 2026-10-16  
**Confidence:** HIGH  

---

## 1. Architectural Patterns for Resilient Communications

### Pattern 1: Asynchronous Store-and-Forward Decoupling
- **Principle:** The operator presentation layer (React UI) and API router (Flask) must never block on physical RF hardware buffers, channel synchronization, or wireless propagation delays.
- **Mechanism:** When a message is submitted, it is immediately persisted in SQLite in the `SUBMITTED` state, promoted to `QUEUED`, and returned to the caller with a `202 Accepted` status and unique `message_id`.
- **Worker Execution:** A decoupled background worker daemon (`QueueWorker`) polls the persistence layer, acquires an atomic lease, and handles transmission over the selected transport adapter.

### Pattern 2: Isolated Dual-Database Architecture (Zero In-Memory Leakage)
- **Principle:** In simulated multi-station environments, testing endpoints must not share database connections, table spaces, or in-memory cache objects.
- **Topology:**
  ```text
  ┌───────────────────────────────┐               ┌───────────────────────────────┐
  │         Station Alpha         │               │         Station Bravo         │
  │  Flask Instance / Port 5050   │               │  Flask Instance / Port 5051   │
  ├───────────────────────────────┤               ├───────────────────────────────┤
  │  Isolated DB: `alpha.db`      │               │  Isolated DB: `bravo.db`      │
  │  - Outbox: Queued Messages    │               │  - Inbox: Delivered Messages  │
  │  - Worker: Alpha Lease Queue  │               │  - ACKs: Durable Receipts     │
  └───────────────┬───────────────┘               └───────────────▲───────────────┘
                  │                                               │
                  │        Simulated Impaired Transport Link      │
                  └───────────────────────────────────────────────┘
  ```
- **Verification:** Ensures that receipt acknowledgements, deduplication, and retry policies are proven across authentic network boundaries rather than in-process shortcuts.

### Pattern 3: Deterministic State Machine with Audit Event Trails
- **States:**
  - `SUBMITTED`: Persisted locally; awaiting queue assignment.
  - `QUEUED`: Enqueued in worker backlog; ready for lease acquisition.
  - `IN_TRANSIT`: Actively leased by worker process; transmission in progress.
  - `DELIVERED`: Terminal state; cryptographic receipt confirmed by recipient.
  - `EXPIRED`: Terminal state; exceeded TTL deadline before ACK received.
  - `FAILED`: Terminal state; exceeded max retry count or unrecoverable error.
- **Audit Traceability:** Every state transition triggers an immutable insert into `message_events`, recording timestamp, actor, previous state, and transition rationale.

### Pattern 4: Authenticated Cryptographic Envelope v2
- **Framing:**
  ```text
  [Version: 1 Byte (0x02)] || [Nonce: 12 Bytes] || [Ciphertext: N Bytes] || [Tag: 16 Bytes]
  ```
- **Integrity Guarantee:** Uses AES-256-GCM authenticated encryption. Fresh 96-bit random nonces generated via OS entropy eliminate the legacy fixed-counter keystream reuse flaw.

### Pattern 5: Dual-Station Side-by-Side Presentation Architecture
- **Layout:** Two responsive tactical columns rendered in React 19:
  - **Left Panel (Station Alpha):** Message composer, priority selector, local outbox queue, lease activity indicator.
  - **Right Panel (Station Bravo):** Recipient inbox, verified signed ACK receipts, real-time event timeline.
  - **Center Control Strip:** Channel impairment controls (latency injection 0–5000ms, packet drop rate 0–100%, link kill switch).
- **Client Resilience:** IndexedDB (`shadowcomm_outbox_db`) buffers user drafts locally in browser memory if HTTP connection to backend drops, auto-syncing upon reconnect.

---

*Refreshed: 2026-10-16*
