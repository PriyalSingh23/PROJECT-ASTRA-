---
phase: "08"
slug: "multi-hop-ad-hoc-mesh-routing-relay-protocol"
status: draft
nyquist_compliant: true
wave_0_complete: false
created: "2026-10-20"
---

# Phase 08 — Validation Strategy: Multi-Hop Ad-Hoc Mesh Routing & Relay Protocol

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.1.1 (Python 3.12, torch pre-import for Apple Silicon arm64) + TypeScript 5.6.3 / Vite |
| **Config file** | `Final-Project/pytest.ini` / `Final-Project/frontend/vite.config.ts` |
| **Quick run command** | `pytest Final-Project/tests/test_mesh_routing.py -k "test_dijkstra or test_bundle" -v` |
| **Full suite command** | `pytest Final-Project/tests/test_mesh_routing.py Final-Project/tests/test_pqc_crypto.py Final-Project/tests/test_multi_database_isolation.py -v && cd Final-Project/frontend && npx tsc -b && npm run build` |
| **Estimated runtime** | ~18 seconds |

---

## Sampling Rate

- **After every task commit:** Run quick unit test or frontend lint command
- **After every plan wave:** Run full test suite (`test_mesh_routing.py` + regression tests + frontend build)
- **Before `/gsd-verify-work`:** Full suite must be green (100% pass rate, 0 TypeScript errors)
- **Max feedback latency:** 20 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 08-01-01 | 01 | 1 | MSH-01, MSH-02 | T-08-01 | Wave 0 mesh test scaffolding with Dijkstra, framing, and custody tests | unit | `pytest Final-Project/tests/test_mesh_routing.py -v` | ❌ W0 | ⬜ pending |
| 08-01-02 | 01 | 1 | MSH-01 | T-08-02 | 5+ named nodes, spatial coordinates, tiered RF adjacency & Multi-Factor Dijkstra | unit | `pytest Final-Project/tests/test_mesh_routing.py -k "TestDijkstraRouting" -v` | ❌ W0 | ⬜ pending |
| 08-01-03 | 01 | 1 | MSH-02 | T-08-03 | Binary Mesh Bundle Header framing, TTL decrement & visited bitmask loop prevention | unit | `pytest Final-Project/tests/test_mesh_routing.py -k "TestBundleFramingAndLoopPrevention" -v` | ❌ W0 | ⬜ pending |
| 08-01-04 | 01 | 1 | MSH-02 | T-08-04 | Per-hop custody transfer handshake, buffer clearance & multi-tier priority queue | unit | `pytest Final-Project/tests/test_mesh_routing.py -k "TestCustodyTransferAndPriorityQueue" -v` | ❌ W0 | ⬜ pending |
| 08-01-05 | 01 | 1 | MSH-01, MSH-04 | T-08-05 | Dynamic route rediscovery upon node drop, custody timeout recovery & REST endpoints | integration | `pytest Final-Project/tests/test_mesh_routing.py -k "TestDynamicReroutingAndApi" -v` | ❌ W0 | ⬜ pending |
| 08-02-01 | 02 | 2 | MSH-01, MSH-03 | — | TypeScript type definitions & API client methods for mesh topology and scenarios | typecheck | `cd Final-Project/frontend && npx tsc -b` | ✅ | ⬜ pending |
| 08-02-02 | 02 | 2 | MSH-03 | — | 3D topology model stratified coordinates, multi-node mesh links & active route derivation | build | `cd Final-Project/frontend && npm run build` | ✅ | ⬜ pending |
| 08-02-03 | 02 | 2 | MSH-03 | — | LinkTopologyView 3D scene: dual-layer mesh, neon laser vector & particle pulse animation | build | `cd Final-Project/frontend && npm run lint` | ✅ | ⬜ pending |
| 08-02-04 | 02 | 2 | MSH-03 | — | Slide-over RelayInspectorDrawer with real-time gauges, hop logs & direct impairment toggle | build | `cd Final-Project/frontend && npm run build` | ✅ | ⬜ pending |
| 08-02-05 | 02 | 2 | MSH-04 | T-08-05 | MeshTestBenchRibbon with 3 drill scenario buttons, reset action & <300ms route diversion banner | build | `cd Final-Project/frontend && npm run lint` | ✅ | ⬜ pending |
| 08-02-06 | 02 | 2 | MSH-01, MSH-02, MSH-03, MSH-04 | ALL | Full platform regression suite across mesh, PQC crypto, multi-database isolation & frontend build | e2e | `pytest Final-Project/tests/test_mesh_routing.py Final-Project/tests/test_pqc_crypto.py Final-Project/tests/test_multi_database_isolation.py -v && cd Final-Project/frontend && npm run build` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `Final-Project/tests/test_mesh_routing.py` — Wave 0 test scaffold containing test cases for Multi-Factor Dijkstra, RF adjacency, binary mesh bundle framing, TTL decrement, loop prevention, custody transfer handshakes, dynamic failover rerouting, and mesh REST endpoints.

---

## Manual-Only Verifications

*All phase behaviors have automated verification.*

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references (`test_mesh_routing.py`)
- [x] No watch-mode flags
- [x] Feedback latency < 20s
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** verified 2026-10-20
