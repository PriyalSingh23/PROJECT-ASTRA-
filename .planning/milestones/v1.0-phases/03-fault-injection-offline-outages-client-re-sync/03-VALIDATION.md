---
phase: "03"
slug: "fault-injection-offline-outages-client-re-sync"
status: draft
nyquist_compliant: true
wave_0_complete: false
created: "2026-10-19"
---

# Phase 03 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution of Phase 03: Fault Injection, Offline Outages & Client Re-Sync.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | Pytest 9.x (Python backend) + Vite / TypeScript 5.x / Oxlint (Frontend) |
| **Config file** | `Final-Project/frontend/package.json` & `Final-Project/frontend/.oxlintrc.json` |
| **Quick run command** | `pytest Final-Project/tests/test_offline_messaging.py -k "test_23" -v` |
| **Full suite command** | `pytest Final-Project/tests/test_offline_messaging.py -v && cd Final-Project/frontend && npm run build && npm run lint` |
| **Estimated runtime** | ~10 seconds |

---

## Sampling Rate

- **After every task commit:** Run task-specific automated check
- **After every plan wave:** Run full regression suite (`pytest` + `npm run build` + `npm run lint`)
- **Before `/gsd-verify-work`:** Full suite must be green (100% pass)
- **Max feedback latency:** 15 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 03-01-01 | 01 | 1 | FLT-01, FLT-04 | T-03-01 | Simulated transport disarms single-shot faults after firing; startup sweep clears dead worker leases safely | unit / int | `pytest Final-Project/tests/test_offline_messaging.py -k "test_23" -v` | ✅ | ⬜ pending |
| 03-01-02 | 01 | 1 | FLT-01, FLT-04 | T-03-01 | Expose preset application, armed fault actions, and manual lease reclaim REST endpoints | int | `pytest Final-Project/tests/test_offline_messaging.py -k "test_23_endpoints" -v` | ✅ | ⬜ pending |
| 03-01-03 | 01 | 1 | FLT-01 | — | ConnectivityView renders tactical presets, armed chips, and backoff profile toggle | frontend | `cd Final-Project/frontend && npm run build` | ✅ | ⬜ pending |
| 03-02-01 | 02 | 2 | FLT-02 | T-03-02 | Browser IndexedDB enforces 500-item ceiling and multi-tab Web Lock flush synchronization | frontend | `cd Final-Project/frontend && npm run build` | ✅ | ⬜ pending |
| 03-02-02 | 02 | 2 | FLT-02, FLT-03 | T-03-03 | MessagesView renders 3D Local Outbox cards, header outbox badge, CTA double-click lockout, and dedup glow | frontend | `cd Final-Project/frontend && npm run build && npm run lint` | ✅ | ⬜ pending |
| 03-02-03 | 02 | 2 | FLT-03, FLT-04 | — | MessageTelemetryDrawer renders Idempotency Seal chip, WORKER_LEASE_RECLAIMED node, and active Retry HUD | frontend | `cd Final-Project/frontend && npm run build` | ✅ | ⬜ pending |
| 03-02-04 | 02 | 2 | FLT-01..04 | — | Full regression verification across Python backend and React frontend | integration | `pytest Final-Project/tests/test_offline_messaging.py -v && cd Final-Project/frontend && npm run build && npm run lint` | ✅ | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `Final-Project/tests/test_offline_messaging.py` — add test case 23 asserting tactical presets, single-shot armed drops, idempotency HTTP 200 verification, and startup stranded lease reclamation.

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Web Audio Radio Squelch / Beep | FLT-01 | Browser audio synthesis requires human auditory check and user interaction trigger | Toggle link between ONLINE and SEVERED in ConnectivityView or Header; listen for subtle ~60ms radio chirp. |

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all test stub references
- [x] No watch-mode flags
- [x] Feedback latency < 15s
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** verified 2026-10-19
