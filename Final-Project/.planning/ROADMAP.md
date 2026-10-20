# Roadmap: SHADOWCOMM — Reliable Tactical Communications & Research Platform

## Milestones

- ✅ **v1.0 MVP** — Phases 1-5 (shipped 2026-10-20)
- 🚧 **v2.0 Advanced Tactical Mesh, Cryptography & Hardware Field Suite** — Phases 6-9 (in planning)

---

## Phases

<details>
<summary>✅ v1.0 MVP (Phases 1-5) — SHIPPED 2026-10-20</summary>

- [x] Phase 1: Dual-Endpoint Reliable Messaging & Verified Receipt Reconciliation (2/2 plans) — completed 2026-10-16
- [x] Phase 2: Dual-Station Operator Experience & Recipient Inbox Verification (2/2 plans) — completed 2026-10-19
- [x] Phase 3: Fault Injection, Offline Outages & Client Re-Sync (2/2 plans) — completed 2026-10-19
- [x] Phase 4: Tactical Multi-Transport Broker & Hardware Safety Lockout (2/2 plans) — completed 2026-10-19
- [x] Phase 5: Research Lab Model Governance & SDR Physical Layer (2/2 plans) — completed 2026-10-20

</details>

### Milestone v2.0 Phases

- [x] **Phase 6: Multi-Database Physical Isolation & Dedicated Daemon Endpoints** (2/2 plans) — completed 2026-10-20
- [x] **Phase 7: Post-Quantum Hybrid Cryptography (ML-KEM / Kyber + AES-256-GCM)** (2/2 plans) — completed 2026-10-20
- [ ] **Phase 8: Multi-Hop Ad-Hoc Mesh Routing & Relay Protocol** - Implement dynamic opportunistic bundle routing, hop TTL control, and 3D visual routing paths across > 5 mobile and aerial relay nodes.
- [ ] **Phase 9: Advanced RF Field Tools, Live Waterfall & Diagnostic Bench** - Build high-performance WebGL spectrum waterfall streaming, raw PCAP export for Wireshark inspection, and real-time RF link budget computation.

---

## Phase Details

### Phase 6: Multi-Database Physical Isolation & Dedicated Daemon Endpoints

**Goal**: Run Station Alpha and Station Bravo as physically distinct SQLite database instances (`alpha.db` and `bravo.db`) on dedicated ports with zero shared state and verified network-only message delivery.  
**Depends on**: Milestone 1 complete  
**Requirements**: MDB-01, MDB-02, MDB-03  
**Success Criteria** (what must be TRUE):
1. `alpha.db` and `bravo.db` are created as separate SQLite WAL databases with independent schema migrations and zero shared memory handles.
2. Station Alpha daemon (port 5051) and Station Bravo daemon (port 5052) run concurrently without database lock collisions.
3. Outbound messages from Alpha to Bravo transmit strictly over HTTP/REST transport with local outbox leasing on Alpha and separate recipient inbox insertion on Bravo.
4. React UI supports switching active daemon targets or monitoring both daemon status streams simultaneously.

---

### Phase 7: Post-Quantum Hybrid Cryptography (ML-KEM / Kyber + AES-256-GCM)

**Goal**: Secure tactical messaging against quantum decryption using hybrid ML-KEM-768 key encapsulation with authenticated AES-256-GCM v3 envelopes.  
**Depends on**: Phase 6  
**Requirements**: PQC-01, PQC-02, PQC-03  
**Success Criteria** (what must be TRUE):
1. Cryptographic layer generates hybrid ML-KEM-768 + X25519 shared secrets for AES-256-GCM payload encryption.
2. Envelope v3 serialization parses and validates post-quantum ciphertext headers with automated fallback negotiation for legacy v2 envelopes.
3. Message Telemetry Drawer renders an illuminated cyan "PQC SECURED (ML-KEM-768)" seal with key exchange parameters.
4. Unit and regression tests verify quantum-resistant key exchange and tamper detection across round-trip message delivery.

---

### Phase 8: Multi-Hop Ad-Hoc Mesh Routing & Relay Protocol

**Goal**: Implement dynamic opportunistic bundle routing, hop TTL control, and 3D visual routing paths across > 5 mobile and aerial relay nodes.  
**Depends on**: Phase 7  
**Requirements**: MSH-01, MSH-02, MSH-03, MSH-04  
**Success Criteria** (what must be TRUE):
1. Bundle routing protocol dynamically forwards messages across 5+ named relay nodes (`relay-ground-01`, `relay-ground-02`, `relay-uav-alpha`, `relay-uav-bravo`, `relay-convoy-01`).
2. Hop-by-hop TTL decrement prevents routing loops and discards expired message bundles.
3. LinkTopologyView renders live multi-hop paths, active forwarding vectors, and per-hop latency on the 3D canvas.
4. Simulating intermediate relay failure causes messages to automatically discover alternate viable paths to destination.

---

### Phase 9: Advanced RF Field Tools, Live Waterfall & Diagnostic Bench

**Goal**: Build high-performance WebGL spectrum waterfall streaming, raw PCAP export for Wireshark inspection, and real-time RF link budget computation.  
**Depends on**: Phase 8  
**Requirements**: FLD-01, FLD-02, FLD-03  
**Success Criteria** (what must be TRUE):
1. Research Lab includes a 60 FPS WebGL/Canvas spectrum waterfall display rendering live and recorded I/Q data.
2. Diagnostics console exports captured radio frames as standard `.pcap` files compatible with Wireshark.
3. Tactical RF Link Budget HUD dynamically computes Free Space Path Loss (FSPL) and received power based on node distance and carrier frequency.

---

## Backlog

(No backlog items currently pending)
