# SHADOWLINK FIELD: Diagnostics & Troubleshooting Guide

**Document Version:** 1.0.0  
**Target:** Field Technicians, Systems Administrators

---

## 1. Structured Error Code Reference

| Error Code | Classification | Operator Summary | Recommended Remediation |
|---|---|---|---|
| `ERR_TRANSPORT_OFFLINE` | Recoverable | Transport link is currently severed or unreachable. | Check physical antenna cables, power to radio gateway, or restore virtual link in simulation panel. |
| `ERR_ACK_TIMEOUT` | Recoverable | Forward message sent, but return receipt timed out. | Message automatically enters backoff retry. Verify receiver is powered on and within range. |
| `ERR_RETRY_LIMIT_EXHAUSTED` | Action Required | Configured maximum delivery attempts reached. | Investigate path propagation. Use manual RETRY once channel is restored, or CANCEL. |
| `ERR_MESSAGE_EXPIRED` | Non-Recoverable | Expiry TTL passed before delivery could be achieved. | Draft a new tactical message with current information. Expired messages cannot be transmitted. |
| `ERR_PAYLOAD_TOO_LARGE` | Non-Recoverable | Message exceeded 64 KB limit for tactical channel. | Shorten message content or split into multiple dispatches. |
| `STARV_UNCONFIGURED_SAFETY_LOCKOUT` | Safety Guard | STAR-V radio operation blocked by policy. | Furnish verified manufacturer interface documentation and authorization. |
| `ERR_UNSUPPORTED_ADAPTER_CAPABILITY` | Configuration | Requested operation not supported by adapter profile. | Verify device profile (e.g., attempting digital data on audio-only PTT profile). |
| `ERR_LEASE_EXPIRED` | Recoverable | Worker process crashed during delivery attempt. | Background recovery daemon reclaims lease automatically within 30 seconds. |

---

## 2. Common Operational Symptoms & Solutions

### 2.1 Messages Stay in "QUEUED" and Are Never Sent
- **Root Cause**: The background worker process (`app.services.worker`) is not running.
- **Diagnostic Step**: Check the dashboard header for "Queue Worker Active" or run:
  ```bash
  ps aux | grep "app.services.worker"
  ```
- **Resolution**: Start the worker process:
  ```bash
  python3 -m app.services.worker --interval 1.0
  ```

### 2.2 Messages Stuck in "AWAITING_ACK"
- **Root Cause**: The receiving endpoint persisted the message, but the return RF channel dropped the ACK packet.
- **Diagnostic Step**: Check the receiver's inbox; if the message is visible there, the payload arrived safely.
- **Resolution**: Click **RETRY** on the sender card. The receiver will recognize the duplicate `message_id`, suppress re-display, and regenerate the durable receipt back to the sender.

### 2.3 Database Lock / SQLite Timeout
- **Root Cause**: SQLite accessed by multiple uncoordinated processes without WAL mode.
- **Resolution**: Verify that the database connection initializes `PRAGMA journal_mode=WAL` and `PRAGMA busy_timeout=5000`. This is handled automatically by `app/core/database.py`.

### 2.4 STAR-V Adapter Displays Lockout
- **Root Cause**: This is deliberate platform behavior. As documented in `docs/STARV_FEASIBILITY.md`, STAR-V cannot be armed without certified documentation.
- **Resolution**: Do not attempt to force transmission. Use the simulated transport or verified Motorola adapter for operational drills.
