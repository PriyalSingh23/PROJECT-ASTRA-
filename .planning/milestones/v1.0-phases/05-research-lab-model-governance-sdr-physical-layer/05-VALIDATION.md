---
phase: "05"
slug: "research-lab-model-governance-sdr-physical-layer"
status: draft
nyquist_compliant: true
wave_0_complete: false
created: "2026-10-20"
---

# Phase 05 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.x + Vite / TypeScript / Oxlint |
| **Config file** | `Final-Project/pytest.ini` / `Final-Project/frontend/package.json` |
| **Quick run command** | `pytest Final-Project/tests/test_research_governance.py -v` |
| **Full suite command** | `pytest Final-Project/tests/test_research_governance.py Final-Project/tests/test_lpi_v4.py -v && cd Final-Project/frontend && npm run build && npm run lint` |
| **Estimated runtime** | ~18 seconds |

---

## Sampling Rate

- **After every task commit:** Run quick run command
- **After every plan wave:** Run full suite command
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 25 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 05-01-01 | 01 | 1 | RSH-01 | T-05-01 | Verify model SHA-256 matches manifest; reject corrupted weights with analytical fallback | unit | `pytest Final-Project/tests/test_research_governance.py -k "test_checkpoint" -v` | ❌ W0 | ⬜ pending |
| 05-01-02 | 01 | 1 | RSH-01 | T-05-02 | Tamper simulation logs HIGH severity security audit and activates fallback | unit | `pytest Final-Project/tests/test_research_governance.py -k "test_tamper" -v` | ❌ W0 | ⬜ pending |
| 05-01-03 | 01 | 1 | RSH-02 | T-05-03 | Detect Apple Silicon MPS and fallback to CPU without ComplexFloat crash | unit | `pytest Final-Project/tests/test_research_governance.py -k "test_mps" -v` | ❌ W0 | ⬜ pending |
| 05-01-04 | 01 | 1 | RSH-02 | — | Comparative benchmark endpoint returns positive acceleration factor | unit | `pytest Final-Project/tests/test_research_governance.py -k "test_benchmark" -v` | ❌ W0 | ⬜ pending |
| 05-01-05 | 01 | 1 | RSH-04 | T-05-04 | GRC flowgraphs operate at exact 245.76 kS/s and 2.484 GHz carrier frequency | unit | `pytest Final-Project/tests/test_research_governance.py -k "test_flowgraph" -v` | ❌ W0 | ⬜ pending |
| 05-02-01 | 02 | 2 | RSH-01, RSH-02 | — | Frontend types & API client methods for verify, tamper, benchmark | build | `cd Final-Project/frontend && npm run build` | ✅ | ⬜ pending |
| 05-02-02 | 02 | 2 | RSH-01 | T-05-01 | Governance Panel, live hash seal, re-verify button, dry-run tamper button | build | `cd Final-Project/frontend && npm run build && npm run lint` | ✅ | ⬜ pending |
| 05-02-03 | 02 | 2 | RSH-02 | — | Apple Silicon MPS status pill, hardware matrix, comparative benchmark card | build | `cd Final-Project/frontend && npm run build && npm run lint` | ✅ | ⬜ pending |
| 05-02-04 | 02 | 2 | RSH-03 | — | Semi-logarithmic BER vs SNR curve with 95% CI bands and FER toggle | build | `cd Final-Project/frontend && npm run build && npm run lint` | ✅ | ⬜ pending |
| 05-02-05 | 02 | 2 | RSH-03 | — | 74-epoch multi-trace convergence viewer and 8-cell tactical EW matrix | build | `cd Final-Project/frontend && npm run build && npm run lint` | ✅ | ⬜ pending |
| 05-02-06 | 02 | 2 | RSH-03 | — | Interactive sample generator (128/256/512/1024), crosshairs, JSON/CSV export | build | `cd Final-Project/frontend && npm run build && npm run lint` | ✅ | ⬜ pending |
| 05-02-07 | 02 | 2 | RSH-03, RSH-04 | — | 2.0s fast polling with 10.0s background tab throttling & flowgraph topology view | build | `cd Final-Project/frontend && npm run build && npm run lint` | ✅ | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `Final-Project/tests/test_research_governance.py` — New test suite validating RSH-01, RSH-02, and RSH-04.

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Web Audio squelch & hover crosshairs | RSH-03 | Browser audio/interaction context | Hover over constellation/spectrogram and verify tooltip coordinates. |

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references
- [x] No watch-mode flags
- [x] Feedback latency < 25s
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** approved 2026-10-20
