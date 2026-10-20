# Reliable Offline Messaging Subsystem (ShadowComm / ShadowLink)

## 1. System Overview

The **Reliable Offline Messaging Subsystem** provides store-and-forward, guaranteed-delivery messaging between distributed operational endpoints (`endpoint-a` and `endpoint-b`). Designed to function over intermittent, unreliable, and delay-prone tactical communication channels, it guarantees at-least-once message delivery, client-side idempotency, deduplication at the receiver, durable-receipt acknowledgements (ACKs), exponential backoff retries with jitter, and comprehensive audit timeline logging.

This subsystem runs independently of real RF hardware (USRP / GNU Radio / CGAN waveform generation) while maintaining a modular interface that permits future binding to authorized physical layer transports without requiring changes to the core queue, database schema, or state machine.

```
+-----------------------------------------------------------------------------------------+
|                                    ENDPOINT ALPHA (A)                                   |
|                                                                                         |
|  +--------------------+         +------------------------+                              |
|  | Browser IndexedDB  | ------> |  REST Ingestion API    |                              |
|  |  (Local Outbox)    |  Sync   |  POST /api/v1/messages |                              |
|  +--------------------+         +-----------+------------+                              |
|                                             |                                           |
|                                             v                                           |
|                                 +------------------------+                              |
|                                 |    SQLite DB (WAL)     |                              |
|                                 |    messages (QUEUED)   |                              |
|                                 +-----------+------------+                              |
|                                             ^                                           |
|                                             | Atomic Lease                              |
|                                             v                                           |
|                                 +------------------------+                              |
|                                 |   Queue Delivery       |                              |
|                                 |   Worker Process       |                              |
|                                 +-----------+------------+                              |
+---------------------------------------------|-------------------------------------------+
                                              |
                   +--------------------------v---------------------------+
                   |               SIMULATED TRANSPORT LINK               |
                   |   - Online/Offline Toggle   - Fault Injection        |
                   |   - Artificial Latency      - Packet/ACK Drop Rates  |
                   +--------------------------+---------------------------+
                                              |
+---------------------------------------------|-------------------------------------------+
|                                             v                                           |
|                                    ENDPOINT BRAVO (B)                                   |
|                                                                                         |
|                                 +------------------------+                              |
|                                 |   Receiver Inbox       |                              |
|                                 | (Deduplication Check)  |                              |
|                                 +-----------+------------+                              |
|                                             |                                           |
|                                             | Creates Durable Receipt                   |
|                                             v                                           |
|                                 +------------------------+                              |
|                                 | Acknowledgement Record |                              |
|                                 |   (ack_type: RECEIVED) |                              |
|                                 +-----------+------------+                              |
|                                             |                                           |
|                                             v (ACK Return Transport)                    |
|  +--------------------+         +-----------+------------+                              |
|  | Message DELIVERED  | <====== | Sender Receives &      |                              |
|  | Sender ACK stored  |         | Validates ACK          |                              |
|  +--------------------+         +------------------------+                              |
+-----------------------------------------------------------------------------------------+
```

---

## 2. Architecture & Components

### A. Client-Side Durable Outbox (`IndexedDB`)
Implemented in browser storage (`ShadowCommLocalOutboxDB`, object store `local_outbox`):
- Keys: `client_idempotency_key` (UUID + timestamp prefix).
- When a user drafts and hits send, the payload and metadata are saved to IndexedDB **before** any network dispatch is attempted.
- State defaults to `LOCAL_QUEUED`.
- If the backend is offline or network fails, messages remain stored locally and survive page reloads, browser restarts, and device crashes.
- The **Sync Manager** listens to `window.online` and checks backend health (`GET /api/v1/health`). When reachable, it synchronizes pending items using the preserved `client_idempotency_key`, preventing duplicate submissions.

### B. Backend Message Ingestion API (`POST /api/v1/messages`)
- Validates payload length (bounded by `MAX_PAYLOAD_BYTES = 65,536`), recipient existence, and required idempotency key.
- Idempotent insertion: If a message with the same `(sender_endpoint_id, client_idempotency_key)` is re-sent, the existing message record is returned (HTTP 200) instead of creating a second row (HTTP 201).
- Inserts audit event `MESSAGE_ENQUEUED` into `message_events`.

### C. Persistent Backend Delivery Queue (SQLite with WAL Mode)
- Engine configured in `messaging/db.py`:
  - `PRAGMA journal_mode=WAL` (Write-Ahead Logging for high concurrency).
  - `PRAGMA busy_timeout=5000` (5-second lock wait before timing out).
  - `PRAGMA synchronous=NORMAL` (Durability balanced with disk I/O performance).
  - `PRAGMA foreign_keys=ON` (Referential integrity enforcement).
- Normalized database schema:
  - `endpoints`: Identifies valid communication nodes (`endpoint-a`, `endpoint-b`).
  - `messages`: Authoritative state, timestamps, error records, attempt counts, and worker leases.
  - `inbox`: Destination persistence with `UniqueConstraint("recipient_endpoint_id", "message_id")`.
  - `delivery_attempts`: Historical audit records of each transmission attempt.
  - `acknowledgements`: Durable-receipt acknowledgements with `UniqueConstraint("original_message_id", "ack_type")`.
  - `message_events`: Structured diagnostic timeline events.

### D. Background Delivery Worker (`messaging/worker.py`)
- Executed as an independent process (`python -m messaging.worker`).
- Polling loop with atomic conditional update leasing:
  ```sql
  UPDATE messages 
  SET current_state = 'SENDING', worker_lease_id = :wid, lease_expires_at = :expiry
  WHERE message_id = :mid 
    AND current_state IN ('QUEUED', 'FAILED_RETRYABLE', 'AWAITING_ACK')
    AND (worker_lease_id IS NULL OR lease_expires_at <= :now)
  ```
- Prevents double-leasing, race conditions, and duplicate processing across concurrent worker processes.
- Automatically claims expired leases left by crashed workers (`RetryPolicy.reclaim_stale_leases`).
- Handles graceful shutdown on `SIGINT` / `SIGTERM`.

### E. Simulated Transport (`messaging/transport.py`)
- Clean separation from hardware and CGAN/SDR routines.
- Features:
  - Online/offline link toggling.
  - Artificial latency emulation (e.g. 0ms, 500ms satellite relay, 1500ms deep delay).
  - Configurable message packet drop probability (0.0 to 1.0).
  - Configurable ACK packet drop probability (0.0 to 1.0).
  - Deterministic single-message and ACK drop triggers for automated testing.
  - Distinct `SIMULATION` indicator displayed in logs and headers.

### F. Receiver-Side Durable Inbox & Deduplication
- Sequence enforced by `AckManager.process_incoming_at_receiver`:
  1. Verify message integrity and recipient alignment.
  2. Query `inbox` table for `(recipient_endpoint_id, message_id)`.
  3. If not present: insert new `inbox` record with `integrity_status='VALID'`, update `message.receiver_stored_at`, and log `INBOX_PERSISTED`.
  4. If already present: log `DUPLICATE_DELIVERY_IGNORED`, bypass re-insertion, and regenerate/fetch the existing durable ACK.
  5. Commit receiver transaction before acknowledging.

### G. Acknowledgement (ACK) Protocol
- An application-layer receipt structure:
  ```json
  {
    "ack_id": "uuid-v4",
    "message_id": "canonical-message-id",
    "ack_type": "RECEIVED",
    "sender_endpoint_id": "endpoint-b",
    "recipient_endpoint_id": "endpoint-a",
    "timestamp": "2026-10-15T09:30:00Z",
    "integrity_verified": true,
    "delivery_status": "DELIVERED"
  }
  ```
- Validated on origin, destination, message ID, and supported ACK type.
- Sender marks `current_state = 'DELIVERED'` and sets `sender_acknowledged_at` only after validating the returned ACK.

### H. Retry Policy & Expiry Scheduler (`messaging/retry_policy.py`)
- Exponential backoff with random jitter:
  $$\text{delay} = \min(\text{max\_delay}, \text{base\_delay} \times 2^{\text{attempt}-1}) + \text{jitter}$$
- Default delays: 2s, 4s, 8s, 16s... up to 60s ceiling.
- Differentiates retryable errors (`TRANSPORT_OFFLINE`, `PACKET_DROPPED`, `ACK_LOST`, `LEASE_EXPIRED`) from permanent errors (`RECIPIENT_NOT_FOUND`, `PAYLOAD_TOO_LARGE`).
- Transitions to `FAILED_FINAL` when `max_attempts` is reached.
- Enforces message expiry (`EXPIRED` state) if the `expires_at` deadline passes before delivery.

---

## 3. Message State Machine

Transitions are strictly validated via `messaging/state_machine.py`. Illegal transitions raise `InvalidStateTransitionError`.

```
                  [ DRAFT ]
                      |
                      v
             [ LOCAL_QUEUED ]  (Stored in Client IndexedDB)
                      |
                      v  (HTTP Ingestion)
                 [ QUEUED ] <--------------------------+
                      |                                | Manual Retry
                      v  (Worker Atomic Lease)         |
                [ SENDING ]                            |
               /     |     \                           |
              /      |      \                          |
  (Drop/Err) /       |       \ (Receiver Stores)       |
            v        |        v                        |
  [ FAILED_RETRYABLE ]|   [ AWAITING_ACK ]             |
         |           |        |                        |
         | (Max Att.)|        | (ACK Arrives)          |
         v           |        v                        |
  [ FAILED_FINAL ]   |   [ DELIVERED ]                 |
         |           |                                 |
         +-----------+---------------------------------+
```

### State Semantics
| State | Location | Meaning |
|---|---|---|
| `DRAFT` | Client Memory | Message is being composed by the user. |
| `LOCAL_QUEUED` | Client IndexedDB | Persisted locally on client device; awaiting backend ingestion. |
| `QUEUED` | Backend SQLite | Durably ingested by backend queue; awaiting worker dispatch. |
| `SENDING` | Backend SQLite | Worker holds active lease; transmission in-flight. |
| `ACCEPTED` | Intermediate | Accepted by intermediate transport relay. |
| `AWAITING_ACK` | Backend SQLite | Message stored by receiver, but return ACK has not yet reached sender. |
| `RECEIVED` | Receiver DB | Receiver has durably committed the payload to inbox. |
| `DELIVERED` | Backend SQLite | Sender has received, validated, and recorded the durable receipt ACK. |
| `FAILED_RETRYABLE` | Backend SQLite | Transmission encountered transient fault; retry backoff scheduled. |
| `FAILED_FINAL` | Backend SQLite | Maximum attempts reached without success; requires user intervention. |
| `EXPIRED` | Backend SQLite | Message deadline passed before successful delivery. |
| `CANCELLED` | Backend SQLite | User requested cancellation before delivery completion. |

---

## 4. API Specification

All offline messaging endpoints are prefixed under `/api/v1`.

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/v1/health` | Service health status and transport mode confirmation |
| `GET` | `/api/v1/endpoints` | Lists all registered endpoints (`endpoint-a`, `endpoint-b`) |
| `GET` | `/api/v1/messages` | Lists messages with optional query filters (`sender`, `recipient`, `state`) |
| `POST` | `/api/v1/messages` | Ingests a new message into the queue (Idempotent by client key) |
| `GET` | `/api/v1/messages/<msg_id>` | Detailed status and metadata for a specific message |
| `GET` | `/api/v1/messages/<msg_id>/events` | Structured audit history and diagnostic event timeline |
| `POST` | `/api/v1/messages/<msg_id>/retry` | Manually transitions a failed message back to `QUEUED` |
| `POST` | `/api/v1/messages/<msg_id>/cancel` | Cancels a queued message |
| `GET` | `/api/v1/endpoints/<ep_id>/inbox` | Durable inbox items for a specific recipient endpoint |
| `GET` | `/api/v1/endpoints/<ep_id>/outbox` | Sent and pending messages originating from an endpoint |
| `GET` | `/api/v1/queue/stats` | Aggregated queue counts, pending counts, and last delivery time |
| `GET` | `/api/v1/sim/transport` | Current simulation transport link status and knobs |
| `POST` | `/api/v1/sim/transport` | Updates simulation knobs (online, latency, drop rates) |
| `POST` | `/api/v1/sim/faults` | Injects deterministic single-packet faults for testing |

---

## 5. Security Architecture & Boundaries

1. **Development Simulation Isolation**:
   The current milestone operates in a simulated local test environment. Operational traffic or real secret keys must not be transmitted.
2. **Audit Timeline Protection**:
   `MessageEvent.safe_metadata` strictly records structural identifiers, timestamps, and error codes. Plaintext message bodies, passwords, and cryptographic keys are excluded from audit event logs.
3. **Payload Sanitization & Bounding**:
   Message payloads are checked for character encoding, maximum size (64 KB ceiling), and SQL injection protection through SQLAlchemy parameterized queries.
4. **Legacy Cryptography Decoupling**:
   The legacy AES-CTR implementation in `app.py` used a hard-coded key and static nonce counter. The messaging queue is fully decoupled from that legacy module. Future deployment will wrap approved authenticated encryption (e.g. AES-256-GCM / ChaCha20-Poly1305 with distinct ephemeral nonces).
