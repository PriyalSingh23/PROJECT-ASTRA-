---
gsd_state_version: "1.0"
milestone: v2.0
milestone_name: Advanced Tactical Mesh, Cryptography & Hardware Field Suite
current_phase: 9
current_phase_name: Advanced RF Field Tools, Live Waterfall & Diagnostic Bench
status: complete
stopped_at: Milestone v2.0 complete (all 9 phases verified)
last_updated: "2026-10-23T12:10:00.000Z"
last_activity: 2026-10-20
last_activity_desc: Reconciled root GSD phase status with ROADMAP; v2.0 software scope remains complete; next ASTRA reintegration milestone awaits a stable local-agent checkpoint
progress:
  total_phases: 4
  completed_phases: 4
  total_plans: 8
  completed_plans: 8
  percent: 100
---

# Project State

## Project Reference

See: `.planning/PROJECT.md` (updated 2026-10-20)

**Core value:** Deliver reliable, verified, and tamper-resistant messages between operational endpoints (Station Alpha and Station Bravo) through persistent offline queues, signed acknowledgements, and crash-resilient store-and-forward architecture with zero data loss.  
**Current focus:** v2.0 software scope completed; create the next ASTRA reintegration milestone only after the local agent reaches a stable checkpoint.

---

## Current Position

Phase: 9 (Advanced RF Field Tools, Live Waterfall & Diagnostic Bench) — COMPLETE
Status: Complete
Last activity: 2026-10-20 — Phase 9 goal-backward verification completed (score: 1.0, 291/291 automated tests green, Vite build 100% clean)

## Monorepo validation boundary (2026-10-23)

- The 291-test figure above is the historical v2.0 GSD milestone result reported on 2026-10-20; it is not a repo-wide test total.
- The latest completed draft PR #1 CI run (#39951110358) passed: 387 tests in `Final-Project/`, 26 tests in root `SHADOWLINK-FIELD/`, 26 tests from the nested mirror, 5 baseline-tool tests, and all three frontend builds. Inventory shows 132/132 matching field-tree entries. This is Linux CI for PR head `deec42bfca837d5f79ee95df34c99fe13c16352c`, not local Mac/unpushed changes or hardware validation.
- The root and nested field-app trees are byte-identical in the audited Git snapshot (132 entries including the added dependency manifests). Do not remove the nested copy until local dirty files, launchers and deployment assumptions have been reviewed.
- No physical Motorola radio, Raspberry Pi, sound card or USRP was operated by the repo-wide CI. Physical-radio and over-the-air acceptance remains pending; software tests must not be presented as hardware results.

## Performance Metrics

**Velocity:**
- Total plans completed: 18 / 18 (v1.0: 10/10, v2.0: 8/8)
- Total tasks completed: 86
- Historical v2.0 GSD test run: 291 passed (100%) on 2026-10-20; scope differs from the current monorepo baseline
- Average duration: ~5 min / plan

**By Phase:**

| Phase | Plans | Status | Verification Score |
|---|:---:|:---:|:---:|
| Phase 1: Dual-Endpoint Messaging & Signed ACKs | 2/2 | Complete | 1.0 |
| Phase 2: Dual-Station Experience & Inbox Check | 2/2 | Complete | 1.0 |
| Phase 3: Fault Injection & Client Re-Sync | 2/2 | Complete | 1.0 |
| Phase 4: Tactical Broker & Safety Lockout | 2/2 | Complete | 1.0 |
| Phase 5: Research Lab & SDR Physical Layer | 2/2 | Complete | 1.0 |
| Phase 6: Multi-Database Physical Isolation | 2/2 | Complete | 1.0 |
| Phase 7: Post-Quantum Hybrid Cryptography | 2/2 | Complete | 1.0 |
| Phase 8: Multi-Hop Ad-Hoc Mesh Routing | 2/2 | Complete | 1.0 |
| Phase 9: Advanced RF Field Tools & Live Waterfall | 2/2 | Complete | 1.0 |


---

## Accumulated Context

### Decisions

- Full decision log archived in `.planning/PROJECT.md` and `.planning/milestones/v1.0-ROADMAP.md`.
- Phase 6 Decisions: D-01 (Multi-port architecture), D-02 (Peer REST ingest transport), D-03 (Local node anti-spoofing guard), D-04 (Multi-station launcher with signal trap).

- Phase 7 Decisions: D-01 (Disk keyrings with SQLite mirror), D-02 (Automatic REST key discovery), D-03 (Self-contained FIPS 203 ML-KEM-768), D-04 (Operator key rotation & zeroize APIs), D-05 (Envelope v3 strict binary framing), D-06 (NIST HKDF hybrid key derivation), D-07 (Per-message forward secrecy with DMR chunking), D-08 (Strict AAD header binding), D-09 (Dual-stack auto-negotiation), D-10 (PQC-preferred outbound), D-11 (Dedicated Message SQLite columns), D-12 (HTTP 422 tamper rejection), D-13 (Dual-tier cyan PQC seals), D-14 (Amber v2 downgrade alert), D-15 (Header PQC readiness pill), D-16 (DiagnosticsView COMSEC inspector).

- Phase 8 Decisions: D-01 (Multi-factor weighted Dijkstra), D-02 (Tiered RF range and elevation adjacency), D-03 (Dual edge gateways), D-04 (Hybrid reactive reroute + 5s topology heartbeat), D-05 (Outer binary mesh header framing), D-06 (Strict TTL decrement & visited set guard), D-07 (Per-hop custody handshake + end-to-end signed receipt), D-08 (Multi-tier tactical priority queue), D-09 (Stratified multi-elevation 3D tactical map), D-10 (Dual-layer mesh & active neon laser vectors), D-11 (Floating 3D node pills + click-to-inspect drawer), D-12 (Smooth OrbitControls + 4 tactical quick-view presets), D-13 (Hybrid direct 3D toggle + test bench ribbon), D-14 (Fast hop custody timeout 1.5s & local alternate forwarding), D-15 (3 tactical drill scenario buttons), D-16 (Pulsing alert toast + strikethrough red link + instant path re-light).

- Motorola LPI integration decisions (2026-10-21): D-01 (Motorola is the application, not a parallel path — LPI protocol/statistics are transported at audio scale, 1650 Hz subcarrier, 2700 Hz occupied). D-02 (Same AES-128-CTR + CRC-8 + RS(42,34) stack and same keyed ZC pilot as the wideband path). D-03 (LPI mode is env-driven and off by default; `MOTOROLA_RADIO_APPROVED` lockout preserved). D-04 (Live burst exposed as `motorola_track` sibling key, not inside the stabilised two-key `tracks` contract). D-05 (SDR join via `sdr_usrp` backend — same burst, analytic single-sideband upconversion, exact 48000×512/100=245760 resample; never selected by `auto`). D-06 (EW report carries raw + normalised views; entropy/wvd are channel-limited and measured against a closed-form ceiling and a shaper-matched noise floor, never relaxed). D-07 (Inter-frame gap sized to RRC memory, `2*span+1` = 13 symbols, replacing a duplicated 4 ms magic number in three places).

### Pending Todos

No v2.0 phase todos remain in the recorded software milestone. ASTRA reintegration and physical acceptance are proposed follow-up work, not completed v2.0 requirements.

### Blockers/Concerns

- No hardware on this host: no Motorola radio, no Raspberry Pi 5, no USB sound card, no USRP (`uhd_find_devices` reports none). All over-the-air figures remain unclaimed; only software-loopback measurements are reported.
- The Motorola LPI waveform is validated in software loopback only. `docs/LPI_MOTOROLA_SYSTEM.md` §7 separates `measured_here` from `needs_hardware` explicitly.

---

## Operator Next Steps

- After the active local coding agent reaches a stable checkpoint, run `/gsd-progress` and `/gsd-health` from the repository root.
- Then run `/gsd-new-milestone` from the repository root for ASTRA reintegration and field validation. Do not start a duplicate GSD project inside the nested field-app copy.
- Keep the `Final-Project/` and field-app owners separate; any nested-mirror removal must be its own reviewed change.

## Session

**Last planning reconciliation:** 2026-10-23
**Stopped at:** v2.0 software milestone complete; next ASTRA milestone not yet initialized
**Resume file:** `.planning/ROADMAP.md`
