---
phase: "02"
slug: "dual-station-operator-experience-recipient-inbox-verification"
status: draft
nyquist_compliant: true
wave_0_complete: true
created: "2026-10-19"
---

# Phase 02 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 7.4.x (Backend) + TypeScript / Vite / Oxlint (Frontend) |
| **Config file** | `Final-Project/tests/conftest.py` & `Final-Project/frontend/tsconfig.json` |
| **Quick run command** | `pytest Final-Project/tests/test_offline_messaging.py -k "test_22" -v` |
| **Full suite command** | `pytest Final-Project/tests/test_offline_messaging.py -v && cd Final-Project/frontend && npm run build && npm run lint` |
| **Estimated runtime** | ~12 seconds |

---

## Sampling Rate

- **After every task commit:** Run `pytest Final-Project/tests/test_offline_messaging.py -k "test_22" -v`
- **After every plan wave:** Run `npm run build && npm run lint` in `Final-Project/frontend/`
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 15 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 02-01-01 | 01 | 1 | UI-03 | T-02-01 | Sanitized audit event serialization without secret leakage | unit | `pytest Final-Project/tests/test_offline_messaging.py -k "test_22" -v` | ✅ | ⬜ pending |
| 02-01-02 | 01 | 1 | UI-03 | — | N/A | compile | `cd Final-Project/frontend && npm run build` | ✅ | ⬜ pending |
| 02-02-01 | 02 | 2 | UI-01 | — | N/A | compile | `cd Final-Project/frontend && npm run build` | ✅ | ⬜ pending |
| 02-02-02 | 02 | 2 | UI-02 | T-02-02 | Recipient inbox query bounded by authenticated endpoint ID | integration | `pytest Final-Project/tests/test_offline_messaging.py -k "test_22" -v` | ✅ | ⬜ pending |
| 02-02-03 | 02 | 2 | UI-01, UI-02 | — | N/A | lint | `cd Final-Project/frontend && npm run lint` | ✅ | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

Existing infrastructure covers all phase requirements.
- `Final-Project/tests/test_offline_messaging.py` already includes `test_22_recipient_inbox_and_timeline_events`.
- `Final-Project/frontend/` build toolchain (`tsc -b && vite build`) and `oxlint` are installed and operational.

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| 3D Adaptive Single/Dual Viewport Toggle | UI-01 | Visual layout inspection and draft state preservation across DOM grid changes | Click 'Dual Split-Screen' toggle; verify Alpha (left) and Bravo (right) render side-by-side. Type in Alpha composer, toggle to Single and back, verify draft text preserved. |
| Slide-Out Tactical Telemetry Drawer | UI-03 | Visual verification of glassmorphic slide animation and vertical 3D illuminated event ladder | Click delivered message card; verify right-hand drawer slides out smoothly without horizontal viewport layout distortion. Verify microsecond timestamps and copyable HMAC receipt chip. |
| 1.5s Adaptive Polling & Tab Throttling | UI-01, UI-02 | Browser event loop and `visibilitychange` interaction | Monitor network tab: verify 1.5s poll rate when active, switch tabs and verify throttling to 5.0s, return and verify instantaneous 1.5s resumption. |

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references
- [x] No watch-mode flags
- [x] Feedback latency < 15s
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** approved 2026-10-19
