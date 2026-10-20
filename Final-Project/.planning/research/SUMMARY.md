# Project Research Summary

**Project:** SHADOWCOMM — Existing LPI Communications Platform  
**Domain:** Tactical Store-and-Forward Messaging & Neural Spread-Spectrum Physical Layer  
**Researched:** 2026-10-16  
**Confidence:** HIGH  

---

## Executive Summary

SHADOWCOMM is an existing brownfield tactical communications application designed to ensure structured, tamper-resistant message delivery over lossy and interrupted communication links. The system integrates a decoupled store-and-forward architecture with SQLite WAL persistence, an atomic lease queue worker daemon, authenticated AES-256-GCM v2 cryptographic framing, and a PyTorch-based neural spread-spectrum physical layer (LPI-CGAN).

The recommended technical approach centers on **strict process and database isolation**. To reliably evaluate message preservation, retry policies, and signed receipt reconciliation without cheating, simulated endpoints (Station Alpha and Station Bravo) must operate over separate, dedicated SQLite database files (`alpha.db` and `bravo.db`) communicating exclusively through the REST API and transport adapters. Furthermore, the UI console will feature a side-by-side dual-station interface giving operators real-time visual feedback of simultaneous outbox, inbox, and transport states.

The primary operational risk is confusing simulated link measurements with physical RF hardware readiness. This risk is mitigated through explicit transport readiness declarations (`READY`, `SIMULATION_ONLY`, `LOCKED_OUT`), an absolute safety lockout on unverified tactical radios (STAR-V), and clear separation of synthetic benchmarks from physical USRP SDR measurements.

---

## Key Findings

### Recommended Stack
- **Backend:** Flask 3.x WSGI on canonical port 5050; SQLAlchemy 2.0 ORM with atomic conditional updates; SQLite 3 WAL mode with 5000ms busy timeout.
- **Frontend:** React 19.2.8 + TypeScript 6.0 + Vite 8.3.4 + Tailwind CSS v4; IndexedDB offline outbox client (`shadowcomm_outbox_db`).
- **Security:** PyCryptodome authenticated AES-256-GCM v2 with fresh 96-bit nonces; PBKDF2-HMAC-SHA256 user authentication (100k iters).
- **Physical/DSP:** PyTorch 2.2+ with Apple Metal (MPS) detection and CPU fallback; Reed-Solomon RS(42,34) forward error correction; Ettus UHD drivers.

### Expected Features
- **Table Stakes:** Persistent outbox/inbox queues, atomic worker leases, exponential retry with jitter, client idempotency deduplication, durable signed ACKs, dual-station side-by-side UI console.
- **Differentiators:** Isolated dual-database architecture (`alpha.db`/`bravo.db`), versioned AES-256-GCM v2 envelopes, neural LPI waveform synthesis, 8-domain EW statistics battery, modular transport adapter safety lockouts.
- **Anti-Features:** Fabricated physical RF receipts, live unverified tactical radio transmissions, in-memory cheating in multi-endpoint simulations, marketing claims of "undetectability."

### Critical Pitfalls to Avoid
1. **Shared In-Memory State in Multi-Endpoint Simulation:** Prevented by enforcing separate SQLite databases (`alpha.db` and `bravo.db`) communicating strictly over HTTP/transport adapters.
2. **Stream Cipher Keystream Reuse (Two-Time Pad):** Prevented by versioned AES-256-GCM v2 with fresh 96-bit random nonces per packet.
3. **macOS Port Collisions:** Prevented by standardizing on canonical port 5050 and eliminating ports 5000 and 5001.
4. **OpenBLAS Dynamic Linker Crash (SIGSEGV 139):** Prevented by enforcing `import torch` before `numpy`/`scipy` across all scripts.
5. **Simulated Transmissions Claimed as Hardware RF:** Prevented by strict capability labeling and empirical gate verifications.

---

## Implications for Roadmap

Based on the user's priority order and research findings, the suggested phase structure is:

### Phase 1: Dual-Station Side-by-Side Console & UI Refinement
**Rationale:** The operator must have real-time visibility into both Alpha (sender) and Bravo (recipient) endpoints simultaneously to observe queueing, transit, and delivery events on one screen.  
**Delivers:** React 19 side-by-side dual-station layout with independent outbox/inbox panels, message drafting, and shared link impairment controls.  
**Avoids:** UI opacity and manual page reloads.

### Phase 2: Isolated Dual-Database Architecture & Transport Bridge
**Rationale:** Verifying message delivery without in-memory shortcuts requires physical database partitioning.  
**Delivers:** Dual SQLite WAL engines (`alpha.db` and `bravo.db`), separate endpoint worker processes or distinct storage adapters, and simulated transport routing.  
**Avoids:** In-memory cheating and shared state pitfalls.

### Phase 3: Offline Queueing, Fault Injection & Crash Recovery Testing
**Rationale:** The core value proposition of SHADOWCOMM is zero message loss under network dropouts and system crashes.  
**Delivers:** Automated test harness for link disconnection, process kill/restart recovery, idempotency deduplication, and ACK timeout retries.  
**Avoids:** Infinite retry loops and silent message loss.

### Phase 4: Cryptographic Review, Envelope Verification & Frame Compatibility
**Rationale:** Ensure all payload encryption adheres to versioned AES-256-GCM v2 standards without breaking tactical radio frame size ceilings.  
**Delivers:** Strict nonce freshness validation, tamper detection tests, and 280-byte DMR / RS(42,34) packet alignment checks.  
**Avoids:** Two-time pad vulnerabilities and frame truncation errors.

### Phase 5: CGAN/CNN Research Reproducibility & Model Gate Verification
**Rationale:** Preserve the scientific integrity of the experimental LPI waveform physical layer.  
**Delivers:** Checkpoint SHA-256 digest validation, training curve verification, BER vs SNR sweeps, and Apple Metal MPS hardware acceleration audits.  
**Avoids:** Corrupted model weights and uncalibrated EW statistics.

### Phase 6: Multi-Transport Interoperability & SDR Hardware Validation
**Rationale:** Validate external radio adapters and prepare the system for controlled field pilots.  
**Delivers:** Motorola DMR TMS simulation tests, STAR-V safety lockout enforcement, relay node telemetry monitoring, and Ettus USRP UHD flowgraph verification.  
**Avoids:** Unauthorized RF emissions and hardware damage.

---

## Confidence Assessment

| Area | Confidence | Notes |
|---|:---:|---|
| Stack | HIGH | Verified directly against running codebase, dependencies, and test suite. |
| Features | HIGH | Directly aligned with user priorities and tactical operational standards. |
| Architecture | HIGH | Proven store-and-forward patterns and SQLite WAL concurrency. |
| Pitfalls | HIGH | Historical bugs and platform-specific macOS quirks identified and mitigated. |

**Overall confidence:** HIGH  
*Ready for requirements and roadmap.*
