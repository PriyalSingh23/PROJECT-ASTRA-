# Project Retrospective: SHADOWCOMM

*A living document updated after each milestone. Lessons feed forward into future planning.*

## Milestone: v1.0 — SHADOWCOMM Tactical Communications & Research Platform

**Shipped:** 2026-10-20  
**Phases:** 5 | **Plans:** 10 | **Tasks:** 44 completed | **Automated Tests:** 78 passed (100%)

### What Was Built
- **Durable Store-and-Forward Messaging:** End-to-end reliable delivery between Station Alpha and Bravo with SQLite persistence, embedded background worker supervision, and cryptographic HMAC signed receipt reconciliation (`signed_ack_receipt`).
- **Dual-Station Operator Experience:** Split-screen side-by-side console, live recipient inbox verification (`GET /api/v1/endpoints/:id/inbox`), and slide-out 4-stage event timeline drawer with microsecond precision.
- **Tactical Fault Injection & Air-Gap Resilience:** Dynamic link impairment engine (Nominal, Urban Jamming, Air-Gap, Satellite), browser IndexedDB offline outbox with Web Locks multi-tab leader auto-flush, and background worker stale lease recovery with startup sweep.
- **Multi-Transport Broker & Hardware Safety Lockout:** Active transport pinning with auto-failover, transparent 280-byte Motorola DMR chunking with atomic retries, statutory STAR-V SDR software safety lockout with audit logging, and flight-isolated relay node telemetry.
- **Research Lab Governance & Physical Layer Harmonization:** SHA-256 model checkpoint manifest seal with analytical fallback, Apple Silicon MPS acceleration with trigonometric CPU fallback, semi-logarithmic Recharts BER vs SNR plot ($10^0$ to $10^{-5}$), 74-epoch convergence viewer, 8-cell EW gate matrix, and GNU Radio flowgraphs synchronized to $2.484\text{ GHz}$ and $245.76\text{ kS/s}$.

### What Worked
- **Goal-Backward Verification & Wave Decomposition:** Splitting each phase into Wave 1 (Backend/Logic/Data) and Wave 2 (UI/Telemetry/Full Integration) resulted in 100% first-pass verification scores (1.0 across all 5 phases).
- **Dynamic Linker Discipline:** Strictly enforcing `import torch` before `numpy`/`scipy` imports on macOS Apple Silicon prevented fatal `SIGSEGV 139` crashes across all 78 tests.
- **Defensive MPS Fallback:** Decomposing complex-float blind phase calculations into real-valued trigonometric components eliminated Apple Silicon MPS kernel failures while preserving hardware acceleration for neural generator inference.

### What Was Inefficient
- Initial phase summaries did not all include standard `one_liner` fields in their frontmatter, requiring manual polish of the extracted milestone accomplishments.
- Subagent definition discrepancies (e.g. `glob` tool in `gsd-integration-checker` not matching the runtime registry) required manual fallback to direct orchestrator test execution.

### Patterns Established
- **Microsecond Timestamp Tracking:** Recording sub-second timestamps (`YYYY-MM-DD HH:MM:SS.ffffff`) in audit logs and rendering them in UI telemetry drawers provides unambiguous verification of event sequence.
- **Multi-Tab Web Locks Synchronization:** Using `navigator.locks.request('shadowcomm_outbox_sync')` ensures client-side IndexedDB outbox flushes never conflict across duplicate browser tabs.
- **Statutory Hardware Lockout:** Permanent software lockouts for unlicenced military/tactical radios must log high-severity security audit events and provide interactive inspection dossiers explaining missing ICD / COMSEC prerequisites.

### Key Lessons
1. **Never Share In-Memory State Between Simulated Stations:** Querying true recipient SQLite inbox endpoints (`/api/v1/endpoints/:id/inbox`) is essential for authentic verification of store-and-forward architectures.
2. **Always Clamp Logarithmic Charts on Zero:** For Recharts semi-log BER vs SNR plots, zero bit-error rates must be clamped to $10^{-5}$ with dedicated zero-BER indicators to avoid SVG rendering NaN artifacts.

---

## Cross-Milestone Trends

### Process Evolution

| Milestone | Phases | Plans | Automated Tests | Key Change |
|-----------|:------:|:-----:|:---------------:|------------|
| v1.0 | 5 | 10 | 78 passed | Initial brownfield modernization to verified dual-station tactical communications platform |

### Cumulative Quality

| Milestone | Tests | Coverage | Zero-Dep Additions |
|-----------|:-----:|:--------:|:------------------:|
| v1.0 | 78 | 100% of defined requirements | Web Locks sync, Audio squelch synthesis, MPS fallback |

### Top Lessons (Verified Across Milestones)

1. Verify observable behavior at each boundary: model persistence, REST transmission, background leasing, and UI rendering.
2. Hardware safety controls must fail closed and record tamper-evident audit logs.
