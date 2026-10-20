---
phase: "04"
slug: "tactical-multi-transport-broker-hardware-safety-lockout"
status: draft
nyquist_compliant: true
wave_0_complete: false
created: "2026-10-19"
---

# Phase 04 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution of Phase 04: Tactical Multi-Transport Broker & Hardware Safety Lockout.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | Pytest 9.x (Python backend) + Vite / TypeScript 5.x / Oxlint (Frontend) |
| **Config file** | `Final-Project/frontend/package.json` & `Final-Project/frontend/.oxlintrc.json` |
| **Quick run command** | `pytest Final-Project/tests/integration/test_adapters.py -v` |
| **Full suite command** | `pytest Final-Project/tests/integration/test_adapters.py Final-Project/tests/integration/test_relay_nodes.py Final-Project/tests/test_offline_messaging.py -v && cd Final-Project/frontend && npm run build && npm run lint` |
| **Estimated runtime** | ~12 seconds |

---

## Sampling Rate

- **After every task commit:** Run task-specific automated check
- **After every plan wave:** Run full regression suite (`pytest` + `npm run build` + `npm run lint`)
- **Before `/gsd-verify-work`:** Full suite must be green (100% pass)
- **Max feedback latency:** 15 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|--------|
| 04-01-01 | 01 | 1 | TRN-01 | T-04-01 | Operator-pinned transport routing with auto-failover and durable queue hold on route unavailable | unit/int | `pytest Final-Project/tests/integration/test_adapters.py -k "test_transport_manager" -v` | ⬜ pending |
| 04-01-02 | 01 | 1 | TRN-02 | T-04-02 | Motorola DMR 280-byte chunking (<uint16 total><uint16 idx>) and atomic frame re-transmission | unit/int | `pytest Final-Project/tests/integration/test_adapters.py -k "test_motorola" -v` | ⬜ pending |
| 04-01-03 | 01 | 1 | TRN-03 | T-04-03 | STAR-V permanent software safety lockout refusal, command_transmit exception, and audit event logging | unit/int | `pytest Final-Project/tests/integration/test_adapters.py -k "test_starv" -v` | ⬜ pending |
| 04-01-04 | 01 | 1 | TRN-04 | T-04-04 | Relay node battery (<=5%) and storage (>=98%) autonomous cutoff with aerial flight safety isolation | unit/int | `pytest Final-Project/tests/integration/test_relay_nodes.py -v` | ⬜ pending |
| 04-01-05 | 01 | 1 | TRN-01..04 | — | Backend automated test suite expansion and regression verification | unit/int | `pytest Final-Project/tests/integration/test_adapters.py Final-Project/tests/integration/test_relay_nodes.py -v` | ⬜ pending |
| 04-02-01 | 02 | 2 | TRN-01..04 | — | Frontend types, API client methods for transports, failover, STAR-V test, and relays | frontend | `cd Final-Project/frontend && npm run build` | ⬜ pending |
| 04-02-02 | 02 | 2 | TRN-02 | — | Quick composer live DMR burst counter HUD (`DMR Bursts: N chunks • XXX B budget`) | frontend | `cd Final-Project/frontend && npm run build && npm run lint` | ⬜ pending |
| 04-02-03 | 02 | 2 | TRN-03 | T-04-03 | Interactive StarVLockoutDossierModal in DevicesView with 4 ICD prerequisites and dry-run tests | frontend | `cd Final-Project/frontend && npm run build && npm run lint` | ⬜ pending |
| 04-02-04 | 02 | 2 | TRN-04 | T-04-04 | Tactical Relay Nodes Telemetry Panel in DevicesView with battery/storage gauges and failsafe cutoff badges | frontend | `cd Final-Project/frontend && npm run build && npm run lint` | ⬜ pending |
| 04-02-05 | 02 | 2 | TRN-04 | — | 3D Relay Nodes and live path connectivity indicators in LinkTopologyView | frontend | `cd Final-Project/frontend && npm run build` | ⬜ pending |
| 04-02-06 | 02 | 2 | TRN-03 | — | MessageTelemetryDrawer illuminated crimson STAR-V Lockout seal and DMR burst telemetry metadata | frontend | `cd Final-Project/frontend && npm run build && npm run lint` | ⬜ pending |
| 04-02-07 | 02 | 2 | TRN-01..04 | — | Full platform-wide regression verification across backend and frontend | integration | `pytest Final-Project/tests/integration/test_adapters.py Final-Project/tests/integration/test_relay_nodes.py Final-Project/tests/test_offline_messaging.py -v && cd Final-Project/frontend && npm run build && npm run lint` | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify commands
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Mac dynamic linker safety preserved across all tests
- [x] Feedback latency < 15s
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** verified 2026-10-19
