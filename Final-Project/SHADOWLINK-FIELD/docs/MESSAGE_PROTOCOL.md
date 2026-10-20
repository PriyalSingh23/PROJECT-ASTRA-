# SHADOWLINK FIELD: Message Protocol & Wire Specification

## 1. Protocol Overview

The **SHADOWLINK Field Communication Protocol (SL-FCP v1.0)** is an application-level framing and acknowledgement format designed for high reliability over unreliable, low-bandwidth, and intermittent communication links.

### Core Principles
1. **Idempotency by Design**: Every message carries a globally unique `message_id` and a client-assigned `client_idempotency_key`. Retries reuse the exact same keys.
2. **At-Least-Once Delivery**: The transport layer may deliver messages multiple times. The receiver deduplicates based on `(recipient_endpoint_id, message_id)`.
3. **Durable-Receipt Acknowledgements**: A message is not considered `DELIVERED` until the receiver has committed the payload to disk and returned a cryptographically verifiable or signed receipt.
4. **Decoupled Application and Transport States**: Application status tracks operational validity; transport status tracks link-level transmission progress.

---

## 2. Message Envelope Specification

A message payload adheres to the following JSON schema:

```json
{
  "protocol_version": "1.0",
  "message_id": "550e8400-e29b-41d4-a716-446655440000",
  "client_idempotency_key": "nodeA-1729000000-abcd1234",
  "sender_endpoint_id": "endpoint-alpha",
  "recipient_endpoint_id": "endpoint-bravo",
  "message_type": "TACTICAL_TEXT",
  "priority": 2,
  "created_at": "2026-10-15T10:00:00.000Z",
  "expires_at": "2026-10-16T10:00:00.000Z",
  "payload_encoding": "UTF8",
  "payload": "ALERT: Route 4 obstructed. Divert convoy to checkpoint Bravo.",
  "payload_digest": "sha256:7f83b1657ff1fc53b92dc18148a1d65dfc2d4b1fa3d677284addd200126d9069",
  "transport_hint": "BEST_AVAILABLE"
}
```

### Fields Definition
- `protocol_version` (`string`, required): Currently `"1.0"`.
- `message_id` (`UUIDv4`, required): Authoritative backend-generated or preserved identifier.
- `client_idempotency_key` (`string`, required): Client-generated key preventing duplicate insertion during HTTP retries.
- `sender_endpoint_id` (`string`, required): Identity of the originating node.
- `recipient_endpoint_id` (`string`, required): Target node or broadcast group ID.
- `message_type` (`string`): Categorization (`TACTICAL_TEXT`, `STATUS_UPDATE`, `TELEMETRY`, `INCIDENT_REPORT`, `ACK`).
- `priority` (`integer`, 1-5):
  - `1`: Routine / Low
  - `2`: Standard
  - `3`: Priority
  - `4`: Urgent
  - `5`: Flash / Emergency
- `created_at` (`ISO-8601 UTC`): Submission timestamp.
- `expires_at` (`ISO-8601 UTC`): Strict expiration deadline after which transmission ceases.
- `payload`: The content string (up to 64 KB).
- `payload_digest`: Cryptographic SHA-256 hash verifying integrity.

---

## 3. Acknowledgement (ACK) Envelope

When an endpoint persists an incoming message to its inbox, it produces an ACK envelope:

```json
{
  "ack_id": "6ba7b810-9dad-11d1-80b4-00c04fd430c8",
  "original_message_id": "550e8400-e29b-41d4-a716-446655440000",
  "ack_type": "RECEIVED",
  "origin_endpoint": "endpoint-bravo",
  "destination_endpoint": "endpoint-alpha",
  "timestamp": "2026-10-15T10:00:02.150Z",
  "integrity_verified": true,
  "inbox_stored_status": "COMMITTED",
  "signature": "ed25519:3b92dc18148a1d65dfc2d4b1fa3d677284addd200126d90697f83b1657ff1fc5"
}
```

### Validation Rules
The sender accepts an ACK only if:
1. `original_message_id` matches an existing message originated by the sender.
2. `origin_endpoint` matches the intended `recipient_endpoint_id`.
3. `destination_endpoint` matches the sender's own identity.
4. `integrity_verified` is true and signature (if enabled) verifies.

---

## 4. Message State Machine

```
[DRAFT] -> [LOCAL_QUEUED] -> [QUEUED] -> [SENDING] -> [AWAITING_ACK] -> [DELIVERED]
                                |            |               |
                                v            v               v
                           [CANCELLED]  [FAILED_RETRY]   [FAILED_RETRY]
                                             |               |
                                             v               v
                                      [FAILED_FINAL]  [FAILED_FINAL]
                                      (Limit Reached) (Limit Reached)
```

1. **`LOCAL_QUEUED`**: Stored in client IndexedDB; not yet ingested by backend API.
2. **`QUEUED`**: Committed to backend SQLite queue; awaiting worker dispatch.
3. **`SENDING`**: Worker holds active lease; transmission in progress.
4. **`AWAITING_ACK`**: Forward delivery succeeded; waiting for return receipt.
5. **`DELIVERED`**: Durable receipt received and validated at originating sender.
6. **`FAILED_RETRYABLE`**: Transient error; worker scheduled backoff retry.
7. **`FAILED_FINAL`**: Max retry attempts exceeded; requires human intervention.
8. **`EXPIRED`**: Message TTL exceeded before delivery confirmation.
9. **`CANCELLED`**: Canceled by operator before terminal state.
