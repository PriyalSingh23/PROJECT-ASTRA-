# Milestones

## v1.0 SHADOWCOMM Tactical Communications & Research Platform (Shipped: 2026-10-20)

**Phases completed:** 5 phases, 10 plans, 36 tasks

**Key accomplishments:**
- **Durable Store-and-Forward Messaging:** Added `signed_ack_receipt` to Message ORM model, connected AckManager cryptographic signature reconciliation in SQLite, and verified with passing regression test suite.
- **Dual-Station Operator Experience:** Built dual split-screen console with live recipient inbox querying against `GET /api/v1/endpoints/:id/inbox` and slide-out 4-stage event timeline drawer with microsecond precision.
- **Fault Injection & Air-Gap Resilience:** Built dynamic link impairment engine (Nominal, Urban Jamming, Air-Gap, Satellite), browser IndexedDB offline outbox with Web Locks auto-flush, and background worker stale lease recovery with startup sweep.
- **Multi-Transport Broker & Hardware Safety Lockout:** Built active transport pinning with auto-failover, transparent 280-byte Motorola DMR chunking with atomic retries, statutory STAR-V SDR software safety lockout with audit logging, and flight-isolated relay node telemetry.
- **Research Lab Governance & Physical Layer Harmonization:** Added SHA-256 model checkpoint manifest seal with analytical fallback, Apple Silicon MPS acceleration with trigonometric CPU fallback, semi-logarithmic Recharts BER vs SNR plot ($10^0$ to $10^{-5}$), 74-epoch convergence viewer, 8-cell EW gate matrix, and GNU Radio flowgraphs synchronized to $2.484\text{ GHz}$ and $245.76\text{ kS/s}$.

---
