# Requirements: SHADOWCOMM v2.0 — Advanced Tactical Mesh, Cryptography & Hardware Field Suite

**Defined:** 2026-10-20  
**Core Value:** Deliver a decentralized, post-quantum secure multi-hop tactical communications network with physically isolated station databases, ML-KEM hybrid encryption, ad-hoc bundle routing across > 5 nodes, and live spectrum diagnostics.

---

## v2 Requirements

### 1. Multi-Database Physical Isolation (MDB)

- [ ] **MDB-01**: Backend supports running independent Station Alpha and Station Bravo database processes (`alpha.db` on port 5051 and `bravo.db` on port 5052) with zero shared in-memory variables or filesystem locks.
- [ ] **MDB-02**: Message transmission between isolated stations occurs strictly over simulated IP/REST transport endpoints with independent queue leasing and status persistence on each node.
- [ ] **MDB-03**: React UI console supports connecting to both independent station daemon ports with live connection state and independent health diagnostics.

### 2. Post-Quantum Cryptography (PQC)

- [ ] **PQC-01**: Cryptographic subsystem implements hybrid post-quantum key encapsulation mechanism combining ML-KEM-768 (Kyber) with ephemeral X25519 for symmetric AES-256-GCM session key derivation.
- [ ] **PQC-02**: Message envelope format v3 incorporates post-quantum ciphertext encapsulation block with backward-compatible fallback negotiation for legacy v2 envelopes.
- [ ] **PQC-03**: React UI and message telemetry drawer render an illuminated cyan "PQC SECURED (ML-KEM-768)" seal displaying key exchange metadata and hybrid encapsulation parameters.

### 3. Multi-Hop Ad-Hoc Mesh Routing (MSH)

- [ ] **MSH-01**: Mesh routing engine implements dynamic bundle routing across > 5 named mobile and aerial relay nodes (`relay-ground-01`, `relay-ground-02`, `relay-uav-alpha`, `relay-uav-bravo`, `relay-convoy-01`).
- [ ] **MSH-02**: Payloads include hop-by-hop TTL (Time-To-Live) decrements, loop prevention checks, and store-and-forward custody transfer acknowledgements.
- [ ] **MSH-03**: React Link Topology View renders interactive multi-hop routing paths, real-time node hop counts, and active bundle forwarding vectors across the 3D topology canvas.
- [ ] **MSH-04**: Simulated node link dropouts automatically trigger dynamic route discovery and reroute pending message bundles through surviving intermediary relays.

### 4. Advanced RF Field Tools & Diagnostics (FLD)

- [ ] **FLD-01**: Research Lab includes a high-framerate WebGL/Canvas live spectrum waterfall visualizer streaming simulated and recorded I/Q signal power spectra.
- [ ] **FLD-02**: Diagnostics view supports single-click raw PCAP / PCAPNG packet export of all transmitted radio frames and TMS bursts for external Wireshark analysis.
- [ ] **FLD-03**: Tactical RF Link Budget HUD computes real-time Free Space Path Loss (FSPL), fade margin, and received power ($P_{\text{rx}}$) based on node distance and carrier frequency.

---

## Future Requirements (Deferred)

- **FUT-01**: Live hardware over-the-air validation on verified Motorola APX / MOTOTRBO hardware with physical radio keying.
- **FUT-02**: Hardware Interface Control Document (ICD) compliance verification for STAR-V SDR physical keying.
- **FUT-03**: Direct satellite uplink integration (Iridium SBD modem adapter).

---

## Out of Scope

| Feature | Reason |
|---|---|
| Complete framework rewrite | Current Flask + SQLite + React 19 + PyTorch architecture is verified with 78 passing tests. |
| Live RF broadcast on unverified hardware | Strictly prohibited for regulatory compliance and equipment safety. |
| Automatic Git operations | Git commits, pushes, merges, and resets require explicit user authorization. |

---

## Traceability Matrix

| Requirement | Phase | Status |
|---|---|---|
| MDB-01 | Phase 6 | Pending |
| MDB-02 | Phase 6 | Pending |
| MDB-03 | Phase 6 | Pending |
| PQC-01 | Phase 7 | Pending |
| PQC-02 | Phase 7 | Pending |
| PQC-03 | Phase 7 | Pending |
| MSH-01 | Phase 8 | Pending |
| MSH-02 | Phase 8 | Pending |
| MSH-03 | Phase 8 | Pending |
| MSH-04 | Phase 8 | Pending |
| FLD-01 | Phase 9 | Pending |
| FLD-02 | Phase 9 | Pending |
| FLD-03 | Phase 9 | Pending |

**Coverage:**
- v2 requirements: 13 total
- Mapped to phases: 13
- Unmapped: 0

---
*Requirements defined: 2026-10-20*
