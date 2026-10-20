---
phase: "07"
slug: "post-quantum-hybrid-cryptography-ml-kem-kyber-aes-256-gcm"
status: verified
nyquist_compliant: true
wave_0_complete: true
created: "2026-10-20"
verified: "2026-10-20"
---

# Phase 07 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.1.1 (Python 3.12, torch pre-import for Apple Silicon arm64) + Vitest / TypeScript 5.6.3 |
| **Config file** | `Final-Project/pytest.ini` / `Final-Project/frontend/vite.config.ts` |
| **Quick run command** | `pytest Final-Project/tests/test_pqc_crypto.py -k "test_mlkem768 or test_hybrid" -v` |
| **Full suite command** | `pytest Final-Project/tests/test_pqc_crypto.py Final-Project/tests/test_multi_database_isolation.py Final-Project/tests/test_offline_messaging.py -v && cd Final-Project/frontend && npx tsc -b && npm run build` |
| **Estimated runtime** | ~15 seconds |

---

## Sampling Rate

- **After every task commit:** Run quick unit test or frontend lint command
- **After every plan wave:** Run full test suite (`test_pqc_crypto.py` + regression tests + frontend build)
- **Before `/gsd-verify-work`:** Full suite must be green (100% pass rate, 0 TypeScript errors)
- **Max feedback latency:** 20 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 07-01-01 | 01 | 1 | PQC-01 | T-07-01 | FIPS 203 ML-KEM-768 Core implementation passing mathematical KAT vectors | unit | `pytest Final-Project/tests/test_pqc_crypto.py -k "TestMLKEM768Core" -v` | ✅ | ✅ green |
| 07-01-02 | 01 | 1 | PQC-01 | T-07-02 | Ephemeral X25519 + ML-KEM-768 HKDF-SHA256 hybrid derivation & Envelope v3 binary layout | unit | `pytest Final-Project/tests/test_pqc_crypto.py -k "TestHybridEnvelopeV3" -v` | ✅ | ✅ green |
| 07-01-03 | 01 | 1 | PQC-02 | T-07-03 | Inbound dual-stack auto-negotiation, classical v2 fallback warning & tamper rejection | integration | `pytest Final-Project/tests/test_pqc_crypto.py -k "TestBackwardCompatibility" -v` | ✅ | ✅ green |
| 07-01-04 | 01 | 1 | PQC-01 | T-07-04 | Keyring storage on disk, SQLite endpoints mirror, key rotation & zeroize APIs | integration | `pytest Final-Project/tests/test_pqc_crypto.py -k "TestKeyringLifecycle" -v` | ✅ | ✅ green |
| 07-01-05 | 01 | 1 | PQC-01, PQC-02 | T-07-05 | DMR 280-byte burst fragmentation (<HH> chunks) with full envelope v3 delivery | integration | `pytest Final-Project/tests/test_pqc_crypto.py -k "test_dmr_pqc_chunking" -v` | ✅ | ✅ green |
| 07-02-01 | 02 | 2 | PQC-03 | — | TypeScript type definitions & API client methods for PQC keys, rotation, and telemetry | typecheck | `cd Final-Project/frontend && npx tsc -b` | ✅ | ✅ green |
| 07-02-02 | 02 | 2 | PQC-03 | — | MessageTelemetryDrawer illuminated cyan PQC seal & encapsulation breakdown card | build | `cd Final-Project/frontend && npm run build` | ✅ | ✅ green |
| 07-02-03 | 02 | 2 | PQC-02, PQC-03 | — | Message card PQC badges, amber v2 downgrade alerts & composer DMR burst counter HUD | build | `cd Final-Project/frontend && npm run lint` | ✅ | ✅ green |
| 07-02-04 | 02 | 2 | PQC-03 | T-07-04 | Header PQC readiness pill & DiagnosticsView interactive Keyring & COMSEC Inspector | build | `cd Final-Project/frontend && npm run build` | ✅ | ✅ green |
| 07-02-05 | 02 | 2 | PQC-01, PQC-02, PQC-03 | ALL | End-to-end multi-daemon PQC message dispatch, tamper simulation & regression check | e2e | `pytest Final-Project/tests/test_pqc_crypto.py Final-Project/tests/test_multi_database_isolation.py -v && cd Final-Project/frontend && npm run build` | ✅ | ✅ green |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [x] `Final-Project/tests/test_pqc_crypto.py` — Wave 0 test scaffold containing test cases for ML-KEM-768 NTT, sampling, encapsulation, hybrid HKDF, envelope v3, fallback, and keyrings.

---

## Manual-Only Verifications

*All phase behaviors have automated verification.*

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references (`test_pqc_crypto.py`)
- [x] No watch-mode flags
- [x] Feedback latency < 20s
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** verified 2026-10-20
