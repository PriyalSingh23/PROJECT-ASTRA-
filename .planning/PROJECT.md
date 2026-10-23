# ASTRA — Reliable Communications, LPI Research & Field Platform

## What This Is

ASTRA is a reliable communications platform and LPI research workspace evolved from experimental LPI-CGAN and SDR work. It provides persistent offline messaging, tamper-resistant cryptographic framing, multi-transport interoperability across local IP, simulated wireless links, DMR radio adapters, and neural spread-spectrum waveforms. The platform features an Apple Silicon-optimized React 19 operator console, dynamic network impairment injection, and rigorous model checkpoint governance.



**Monorepo ownership:** `Final-Project/` owns the LPI-CGAN/DSP research path and its legacy Flask messaging/application code. Root `SHADOWLINK-FIELD/` is the operational field-operator application. `Final-Project/SHADOWLINK-FIELD/` is an identical mirror at the audited revision; keep it frozen until local uncommitted changes, launchers and relative paths are checked, then consider consolidation in a separate reviewed change. Root `.planning/` is the monorepo ASTRA planning context; `Final-Project/.planning/` remains historical/research context and is not auto-synchronized.

## Core Value

Deliver reliable, verified, and tamper-resistant messages between operational endpoints (Station Alpha and Station Bravo) through persistent offline queues, signed acknowledgements, and crash-resilient store-and-forward architecture with zero data loss.

## Last completed milestone: v2.0 Advanced Tactical Mesh, Cryptography & Hardware Field Suite

**Status boundary (2026-10-23):** root GSD files mark phases 1–9 complete in the software/test scope. This does not imply successful physical-radio acceptance, formal PQC certification, or the absence of local-only changes. The next ASTRA reintegration milestone is proposed but not initialized yet.

**Goal:** Deliver a decentralized, post-quantum secure multi-hop tactical communications network with physically isolated station databases, ML-KEM hybrid encryption, ad-hoc bundle routing across > 5 nodes, and live spectrum diagnostics.

**Target features:**
- **Multi-Database Physical Isolation:** Dedicated `alpha.db` and `bravo.db` running across distinct daemon ports with zero shared memory or SQLite locks.
- **Post-Quantum Cryptography (PQC):** Hybrid ML-KEM-768 (Kyber) + AES-256-GCM authenticated envelope encryption.
- **Multi-Hop Ad-Hoc Mesh Routing:** Dynamic bundle routing, store-and-forward relaying across > 5 mobile and aerial nodes, and TTL hop management.
- **Advanced RF Field Tools:** Live spectrum waterfall visualizer, raw PCAP packet capture export, and real-time RF link budget calculator.

## Requirements

### Validated

<!-- Shipped and verified capabilities (78 automated tests passing, score 1.0) -->

- ✓ Asynchronous store-and-forward message engine with atomic leasing and exponential backoff (`messaging/worker.py`) — v1.0
- ✓ Deterministic message lifecycle state machine (`SUBMITTED` → `QUEUED` → `IN_TRANSIT` → `DELIVERED` / `EXPIRED` / `FAILED`) (`messaging/state_machine.py`) — v1.0
- ✓ SQLite WAL database with connection pooling, 5000ms busy timeout, and schema auto-migrations (`messaging/db.py`) — v1.0
- ✓ Authenticated AES-256-GCM v2 envelope encryption with fresh 96-bit nonces, AAD binding, and MAC tags (`messaging/crypto_v2.py`) — v1.0
- ✓ Enterprise user authentication with PBKDF2-HMAC-SHA256 (100k iters), RBAC (`ADMINISTRATOR`, `OPERATOR`, `VIEWER`), and security audit logging (`messaging/auth_service.py`) — v1.0
- ✓ Unified Transport Broker with modular adapter interfaces and capability declarations (`integration/manager.py`) — v1.0
- ✓ LPI-CGAN neural transceiver bridge with RS(42,34) forward error correction and CRC-8 integrity checksum (`integration/lpi_cgan/adapter.py`) — v1.0
- ✓ Motorola MOTOTRBO TMS adapter enforcing 280-byte DMR packet ceiling under XCMP simulation (`integration/motorola/adapter.py`) — v1.0
- ✓ STAR-V tactical radio safety lockout adapter preventing unauthorized physical RF transmission (`integration/starv/adapter.py`) — v1.0
- ✓ Ground and aerial relay node manager with telemetry monitoring and flight-decoupled payload failsafes (`integration/relay_nodes/manager.py`) — v1.0
- ✓ Modern React 19 + TypeScript + Vite + Tailwind CSS v4 tactical web console (`frontend/`) served by Flask on port 5050 — v1.0
- ✓ PyTorch Gen 2 LPI waveform core (`LPIGenerator`, `LPIDecoder`) with 8-domain EW statistics battery and SHA-256 manifest verification — v1.0
- ✓ Verifiable signed ACK receipt reconciliation, model serialization, embedded worker daemon, and green "ACK Verified" UI rendering — v1.0 (Phase 1)
- ✓ Dual-Station Side-by-Side Console: Add dual-station operator view in React UI allowing simultaneous real-time monitoring of Station Alpha and Station Bravo — v1.0 (Phase 2)
- ✓ Recipient True Inbox Persistence: Validate against recipient inbox (`/api/v1/endpoints/:id/inbox`) with physical SQLite proof — v1.0 (Phase 2)
- ✓ Real-Time Message Audit Timeline: 4-stage event timeline (`MESSAGE_ENQUEUED` -> `LEASE_ACQUIRED` -> `INBOX_PERSISTED` -> `ACK_VALIDATED_DELIVERED`) with microsecond timestamps — v1.0 (Phase 2)
- ✓ Tactical Impairment Injection: Nominal, Urban Jamming, Air-Gap, Satellite presets, single-shot fault arming, synthesized audio squelch — v1.0 (Phase 3)
- ✓ Client-Side Outbox Re-Sync: Browser IndexedDB (`shadowcomm_outbox_db`) with 500-message ceiling and Web Locks leader auto-flush — v1.0 (Phase 3)
- ✓ Duplicate Submission & Idempotency Key Deduplication: Client idempotency keys deduplicate submissions with HTTP 200 and cyan card glow — v1.0 (Phase 3)
- ✓ Stale Lease Reclamation & Stranded Sweep: Worker stale lease recovery with exponential backoff and server startup sweep — v1.0 (Phase 3)
- ✓ Multi-Transport Broker & Auto-Failover: Pinned active transport with auto-failover, route unavailable queue hold — v1.0 (Phase 4)
- ✓ Motorola MOTOTRBO 280-byte DMR Chunking: Transparent frame splitting and atomic batch retries — v1.0 (Phase 4)
- ✓ STAR-V SDR Software Safety Lockout: Permanent safety lockout, inspection dossier modal, audit logging — v1.0 (Phase 4)
- ✓ Relay Node Telemetry & Flight Safety: Ground/aerial relay telemetry with autonomous cutoff and flight isolation — v1.0 (Phase 4)
- ✓ Checkpoint SHA-256 Manifest Governance: PyTorch model integrity seal with analytical fallback — v1.0 (Phase 5)
- ✓ Apple Silicon MPS Acceleration & Fallback: Automatic Metal detection with real-valued blind phase CPU fallback — v1.0 (Phase 5)
- ✓ Scientific Research Console: Recharts semi-logarithmic BER vs SNR (10^0 to 10^-5), 74-epoch convergence viewer, 8-cell EW matrix — v1.0 (Phase 5)
- ✓ SDR Flowgraph Harmonization: GNU Radio flowgraphs and UHD drivers tuned to 2.484 GHz and 245.76 kS/s — v1.0 (Phase 5)

### Outstanding validation and reintegration work

These are evidence/acceptance gaps; an unchecked item does not imply that the related software module is absent.

- [ ] Capture the local Mac/Git baseline after the active coding agent reaches a stable checkpoint; record uncommitted changes before any cleanup.
- [ ] Reconcile root GSD state and start the next ASTRA reintegration milestone only after a stable checkpoint.
- [ ] Validate multi-hop behavior across more than five nodes using documented software tests, then separately record any physical-field result.
- [ ] Perform authorized over-the-air validation on the exact supported Motorola APX/MOTOTRBO model and firmware; software loopback is not an RF result.
- [ ] Verify the applicable STAR-V Hardware Interface Control Document and approved hardware interface before any physical operation.
- [ ] Review the end-to-end PQC path and run official ML-KEM/FIPS 203 known-answer tests; module presence and unit tests alone are not a complete security review.
- [ ] Reproduce multi-database isolation on the intended local deployment with separate processes, ports and databases.
- [ ] Decide whether to remove the byte-identical nested field-app mirror only after the local agent's unpushed state and all launcher/import references are reviewed.
- [ ] Accept further CGAN/CNN training only when held-out benchmark results improve agreed BER/FER, goodput and latency metrics against a conventional baseline.

### Out of Scope

<!-- Explicit boundaries to prevent scope creep -->

- Wholesale application rewrite or framework replacement — preserve both existing domains: the field app under root `SHADOWLINK-FIELD/` and the LPI/legacy application under `Final-Project/`.
- Live RF broadcast on unverified hardware — Strictly prohibited for regulatory compliance and equipment safety.
- Marketing claims of invisibility or undetectability — Research must remain empirically grounded with factual EW detection statistics.
- Automatic Git operations — Never commit, push, merge, reset, or alter git state without explicit user authorization.

## Context

- **Current State:** root GSD marks v2.0 phases 1–9 complete as of 2026-10-20. The latest completed Linux baseline run for PR #1 head `deec42bfca837d5f79ee95df34c99fe13c16352c` passed on 2026-10-23: 387 `Final-Project` tests, 26 tests from each field-app path, 5 baseline-tool tests, and all three frontend builds. A newer run is pending for PR #1 head `123cdbcde0c235d6b04436314ebcc1e2cc666aaa` after a CI path-filter adjustment. These are pushed-source CI results, not local Mac changes or physical-hardware validation.
- **Source of Truth:** this is a monorepo with domain-specific owners as defined above. Do not treat `Final-Project/` alone as the whole ASTRA system.
- **Development Environment:** macOS (Darwin / Apple Silicon `arm64`) with Python 3.12 (`radioconda`), Node.js v24, npm 11.
- **Port Strategy:** Port 5050 is the unified canonical port for Flask REST API and static React UI distribution.
- **Hardware Acceleration:** Apple Metal (MPS) detected automatically for PyTorch tensor operations with deterministic CPU fallback for unsupported operations.
- **Dynamic Linker Safety:** `import torch` must precede `numpy` and `scipy` imports across all entry points to prevent OpenBLAS dynamic linker crashes (`SIGSEGV 139`).

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Side-by-Side Dual Station UI | Provides immediate visual feedback of simultaneous Alpha outbox and Bravo inbox states on one screen | ✓ Good |
| Pinned Active Transport with Failover | Operator controls primary dispatch while system falls back automatically if primary is offline | ✓ Good |
| 280-byte DMR Framing | Complies with MOTOTRBO Tier-II XCMP payload constraints with transparent chunking | ✓ Good |
| STAR-V Software Lockout | Prevents unauthorized physical RF keying without vendor ICD and defense licensing | ✓ Good |
| MPS Real-Valued Phase Fallback | Eliminates ComplexFloat MPS kernel crashes on Apple Silicon during blind phase synchronization | ✓ Good |
| Canonical Port 5050 | Eliminates macOS AirPlay Receiver collision on port 5000 and replaces legacy port 5001 | ✓ Good |
| Versioned AES-256-GCM v2 | Fresh 96-bit random nonces prevent two-time pad vulnerability of legacy fixed-counter AES-CTR | ✓ Good |
| SQLite WAL with 5000ms Timeout | Enables concurrent worker leases and API reads without `database is locked` errors | ✓ Good |
| Preserve Research Core (`lpi_v4/`) | Keeps physical layer signal processing intact and available for SDR evaluation | ✓ Good |

---
*Last updated: 2026-10-23 during ASTRA monorepo/GSD reconciliation*
