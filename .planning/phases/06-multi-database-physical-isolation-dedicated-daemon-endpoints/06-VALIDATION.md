---
phase: "06"
slug: "multi-database-physical-isolation-dedicated-daemon-endpoints"
status: draft
nyquist_compliant: true
wave_0_complete: false
created: "2026-10-20"
---

# Phase 06 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.1.1 + anyio-4.15.1 + Vite/tsc 8.3.4 |
| **Config file** | `Final-Project/pytest.ini` / `Final-Project/frontend/package.json` |
| **Quick run command** | `pytest Final-Project/tests/test_multi_database_isolation.py -v` |
| **Full suite command** | `pytest Final-Project/tests/test_multi_database_isolation.py Final-Project/tests/test_offline_messaging.py -v && cd Final-Project/frontend && npm run build && npm run lint` |
| **Estimated runtime** | ~12 seconds |

---

## Sampling Rate

- **After every task commit:** Run `pytest Final-Project/tests/test_multi_database_isolation.py -v`
- **After every plan wave:** Run full suite command
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 15 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 06-01-01 | 01 | 1 | MDB-01 | T-06-01 | DB isolation & separate connection pools | unit | `pytest Final-Project/tests/test_multi_database_isolation.py -k "test_database_physical_isolation" -v` | ❌ W0 | ⬜ pending |
| 06-01-02 | 01 | 1 | MDB-01, MDB-02 | T-06-02 | Station identity check & spoofing rejection | unit | `pytest Final-Project/tests/test_multi_database_isolation.py -k "test_identity_spoofing_rejection" -v` | ❌ W0 | ⬜ pending |
| 06-01-03 | 01 | 1 | MDB-02 | T-06-03 | Incoming peer endpoint packet ingest & HMAC signature | unit | `pytest Final-Project/tests/test_multi_database_isolation.py -k "test_peer_incoming_ingest or test_peer_incoming_duplicate_replay" -v` | ❌ W0 | ⬜ pending |
| 06-01-04 | 01 | 1 | MDB-02 | T-06-04 | Peer forwarding transport across simulated network | integration | `pytest Final-Project/tests/test_multi_database_isolation.py -k "test_peer_cross_station_delivery or test_peer_air_gap_outage_handling" -v` | ❌ W0 | ⬜ pending |
| 06-02-01 | 02 | 2 | MDB-03 | T-06-05 | Multi-endpoint API service client & health polling | unit/build | `cd Final-Project/frontend && npm run build && npm run lint` | ✅ | ⬜ pending |
| 06-02-02 | 02 | 2 | MDB-03 | T-06-06 | Dual-station console wiring & port connection badges | build | `cd Final-Project/frontend && npm run build` | ✅ | ⬜ pending |
| 06-02-03 | 02 | 2 | MDB-01, MDB-03 | T-06-07 | Multi-daemon developer launcher & trap lifecycle | smoke | `bash Final-Project/scripts/verify_dual_station.sh` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `Final-Project/tests/test_multi_database_isolation.py` — Test suite scaffolding for physical DB isolation, identity spoofing rejection, peer ingest, and cross-station delivery.
- [ ] `Final-Project/scripts/verify_dual_station.sh` — Smoke verification test script asserting ports 5051, 5052, and 5050 respond cleanly.

---

## Manual-Only Verifications

*All phase behaviors have automated verification.*

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references
- [x] No watch-mode flags
- [x] Feedback latency < 15s
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** verified 2026-10-20
