# Phase 8: Multi-Hop Ad-Hoc Mesh Routing & Relay Protocol - Context

**Gathered:** 2026-10-20  
**Status:** Ready for planning  

<domain>
## Phase Boundary

Phase 8 implements dynamic opportunistic bundle routing, hop TTL control, and interactive 3D visual routing paths across > 5 mobile and aerial relay nodes (`relay-ground-01`, `relay-ground-02`, `relay-uav-alpha`, `relay-uav-bravo`, `relay-convoy-01`) connecting Station Alpha and Station Bravo. It delivers an ad-hoc mesh routing engine with multi-factor Dijkstra cost optimization, cleartext outer mesh bundle framing wrapping post-quantum Envelope v3 payloads, per-hop store-and-forward custody handshakes, loop prevention via visited node sets, real-time 3D tactical visualization with animated laser path vectors, and an interactive impairment test bench supporting instant route re-convergence upon intermediate relay failure.

</domain>

<decisions>
## Implementation Decisions

### 1. Mesh Topology & Dynamic Routing Algorithm (MSH-01, MSH-04)
- **D-01:** **Routing Algorithm & Cost Metric:** Multi-Factor Weighted Dijkstra. Cost function combines hop count, link latency, remaining battery, and queue depth so depleted (<10%) or congested nodes are avoided. — **Reversibility:** one-way — core mesh routing graph algorithm and state representation.
- **D-02:** **Node Adjacency & Range Model:** Tiered RF Range & Elevation Adjacency. Realistic RF ranges based on node altitude (Ground-to-Ground 15km, Ground-to-UAV 23km, UAV-to-UAV 60km) with automatic bidirectional link formation across all 5+ named nodes (`relay-ground-01`, `relay-ground-02`, `relay-uav-alpha`, `relay-uav-bravo`, `relay-convoy-01`). — **Reversibility:** costly — defines network graph topology construction and proximity calculation.
- **D-03:** **Station Alpha & Bravo Network Roles:** Dual Edge Gateways. Alpha and Bravo act as tactical edge stations that connect to nearby relays and can route multi-hop through the entire mesh to each other. — **Reversibility:** costly — touches addressing and routing dispatch interfaces.
- **D-04:** **Route Convergence & Update Frequency:** Hybrid Reactive Reroute + 5s Topology Heartbeat. Fast reactive path recalculation on packet drop/outage backed by lightweight 5s beacon polling. — **Reversibility:** reversible.

### 2. Bundle Header Framing, Hop TTL & Custody Transfer (MSH-02)
- **D-05:** **Bundle Framing Format:** Outer Mesh Header Framing. Cleartext binary outer header `[0x4D 0x53 0x48 ('MSH')][1B Flags][1B Initial TTL][1B Remaining TTL][1B Hop Count][2B Visited Node Bitmask][16B Bundle UUID][Payload: Envelope v3/v2]`. Relays inspect and update routing headers without decrypting the payload. — **Reversibility:** one-way — wire framing protocol specification.
- **D-06:** **Hop TTL & Loop Prevention:** Strict Decrement & Visited Set Guard. Remaining TTL decrements at each hop (drops on `TTL == 0` with audit event `BUNDLE_TTL_EXPIRED`); visited node ID set prevents loops (drops immediately if node already visited with audit event `ROUTING_LOOP_DETECTED`). — **Reversibility:** costly — affects packet lifecycle and drop handling across nodes.
- **D-07:** **Custody Transfer & Per-Hop Acknowledgement:** Per-Hop Custody Handshake + End-to-End Signed Receipt. Upstream relay clears buffer upon receiving a 16-byte signed custody ACK token `CUSTODY_ACK:<node_id>:<bundle_id>` from the downstream node; originating station holds queue lease until the final Bravo signed receipt reconciles. — **Reversibility:** costly — reliability state machine and buffer management.
- **D-08:** **Queue Prioritization & Congestion Handling:** Multi-Tier Tactical Priority Queue. `FLASH` (Emergency) > `IMMEDIATE` > `ROUTINE`; when relay storage exceeds 90%, lowest priority expired bundles are dropped first. — **Reversibility:** reversible.

### 3. 3D LinkTopologyView Visuals & Path Vectors (MSH-03)
- **D-09:** **3D Spatial Layout:** Stratified Multi-Elevation Tactical Map. Ground relays (`relay-ground-01`, `relay-ground-02`) and mobile convoy (`relay-convoy-01`) at $Y=0$ (`relay-convoy-01` at `[0, 0, 1.0]`); aerial UAVs (`relay-uav-alpha`, `relay-uav-bravo`) at elevated flight corridors ($Y=+4.5$ and $Y=+6.0$) with subtle orbital drift; Station Alpha at `[-9, 0, 0]` and Station Bravo at `[+9, 0, 0]`. — **Reversibility:** costly — 3D scene coordinate graph and Three.js node positioning.
- **D-10:** **Active Forwarding Route Visualization:** Dual-Layer Mesh & Active Neon Laser Vectors. Potential mesh links rendered as subtle translucent zinc lines; active multi-hop route lights up in glowing neon cyan with moving particle pulses traveling hop-by-hop. — **Reversibility:** reversible.
- **D-11:** **Per-Hop Telemetry & HUD Overlay:** Floating 3D Node Pills + Click-to-Inspect Drawer. Floating tactical labels displaying battery %, storage %, queue depth, and status; clicking any node or link segment opens a rich slide-over inspector drawer with live metrics and hop logs. — **Reversibility:** reversible.
- **D-12:** **Camera Navigation & Presets:** Smooth OrbitControls + 4 Tactical Quick-View Presets. Free 360° mouse navigation plus one-click preset buttons: 'Theater Overview', 'Focus UAV Flight Corridors', 'Forwarding Vector Tracking', and 'Ground Axis'. — **Reversibility:** reversible.

### 4. Relay Impairment & Dynamic Rerouting Test Bench (MSH-04)
- **D-13:** **Operator Impairment Controls:** Hybrid Direct 3D Toggle + Test Bench Ribbon. Operators can toggle node state directly from the 3D node drawer or test ribbon (`ONLINE`, `FORCE_OFFLINE`, `BATTERY_CRITICAL`, `STORAGE_FULL`, `RF_JAMMED`). — **Reversibility:** reversible.
- **D-14:** **Dynamic Rerouting Trigger & In-Flight Recovery:** Fast Hop Custody Timeout (1.5s) & Local Alternate Forwarding. Upstream relay detects unacknowledged custody hop, queries mesh Dijkstra for next best alternate path, and reroutes without originator re-transmission. — **Reversibility:** costly — decentralized error recovery and next-hop selection.
- **D-15:** **Pre-Canned Tactical Failure Scenarios:** 3 Tactical Drill Scenario Buttons: "Scenario 1: UAV-Alpha Signal Lost", "Scenario 2: Ground Relays Jammed (All-Aerial Corridor)", "Scenario 3: Convoy Mobile Breakout & Extended Hop" + "Reset All to Nominal". — **Reversibility:** reversible.
- **D-16:** **Telemetry Visualization of Rerouting Event:** Pulsing Alert Toast + Strikethrough Red Link + Instant Path Re-Light. Failed node turns pulsing red, broken link shows red strikethrough, new path lights up in cyan within <300ms, and an amber alert banner displays route diversion telemetry (`[MESH REROUTE: Bypassed relay-uav-alpha -> Diverted via relay-ground-02 -> Delivered]`). — **Reversibility:** reversible.

### the agent's Discretion
- Exact coordinate offsets and orbital speed formulas for UAV visual motion.
- Styling details for 3D link shaders and particle pulse geometry.
- Selection of default TTL (e.g., initial TTL=8 hops).
- Internal SQLite schema details for persisting relay transit custody states.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Requirements & Roadmap
- `.planning/REQUIREMENTS.md` §3 (Multi-Hop Ad-Hoc Mesh Routing: MSH-01, MSH-02, MSH-03, MSH-04)
- `.planning/ROADMAP.md` §Phase 8 (Goal and success criteria for multi-hop mesh)

### Prior Phase Decisions & Infrastructure
- `.planning/phases/04-tactical-multi-transport-broker-hardware-safety-lockout/04-CONTEXT.md` — Relay node manager and independent failsafe cutoffs
- `.planning/phases/06-multi-database-physical-isolation-dedicated-daemon-endpoints/06-CONTEXT.md` — Multi-daemon peer incoming ingest on 5051/5052
- `.planning/phases/07-post-quantum-hybrid-cryptography-ml-kem-kyber-aes-256-gcm/07-CONTEXT.md` — Envelope v3 binary layout with 1150B overhead and DMR chunking

### Source Code References
- `Final-Project/integration/relay_nodes/manager.py` — Current RelayNode and RelayNodeManager implementation
- `Final-Project/messaging/dispatch.py` — Message dispatching and DMR burst framing
- `Final-Project/messaging/transport.py` — Transport transmission pipeline
- `Final-Project/messaging/crypto_pqc.py` — Envelope v3 cryptographic layout
- `Final-Project/frontend/src/components/topology/model.ts` — 3D scene topology model derivation
- `Final-Project/frontend/src/components/topology/LinkTopologyView.tsx` — Three.js React Three Fiber 3D scene

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `RelayNode` & `RelayNodeManager` in `Final-Project/integration/relay_nodes/manager.py`: Established telemetry fields, status enums, battery/storage cutoffs, and `to_dict()` serialization. Can be extended to support 5+ nodes, dynamic neighbor lists, bundle queues, and Dijkstra routing.
- `LinkTopologyView.tsx` & `model.ts` in `Final-Project/frontend/src/components/topology/`: Three.js R3F canvas with camera, stations, and relay markers. Can be upgraded from simple single-line linking to stratified 3D coordinates, dynamic dual-layer mesh links, and animated laser pulses.
- `SecurityAuditLog` in `Final-Project/messaging/models.py`: Audit logging for mesh events (`BUNDLE_TTL_EXPIRED`, `ROUTING_LOOP_DETECTED`, `MESH_REROUTE_DIVERTED`, `CUSTODY_TRANSFERRED`).

### Established Patterns
- **Apple Silicon Linker Safety:** `import torch` strictly before `numpy`/`scipy` imports across all Python entry points.
- **SQLite WAL Concurrency:** Connections strictly execute `PRAGMA busy_timeout=5000` before `PRAGMA journal_mode=WAL`.
- **Zero Automated Git Operations:** Write directly to disk; no git commits or pushes.

### Integration Points
- `RelayNodeManager.seed_default_relays()`: Expand from 2 to 5+ named nodes (`relay-ground-01`, `relay-ground-02`, `relay-uav-alpha`, `relay-uav-bravo`, `relay-convoy-01`).
- `DispatchRouter`: When mesh transport is selected, wrap Envelope v3 with outer binary mesh header, compute Dijkstra path, and route through next-hop relay.
- `GET /api/v1/topology/mesh`: New endpoint returning full mesh state (nodes, links, active forwarding vectors, per-hop latency, route paths).
- `POST /api/v1/relays/{id}/telemetry` & `POST /api/v1/relays/scenario`: Endpoints for operator impairment injection and tactical scenario triggers.

</code_context>

<specifics>
## Specific Ideas

- **Stratified Altitude:** UAVs floating at $Y=+4.5$ and $Y=+6.0$ with slow orbital circle animation, creating visual tactical depth above ground units.
- **Laser Forwarding Vectors:** Active route illuminated in glowing neon cyan with moving particle pulses traveling hop-by-hop.
- **Instant Route Convergence:** When UAV Alpha is clicked to disable, the route instantly pivots through Ground-02/Convoy within <300ms, displaying a tactical amber alert banner.

</specifics>

<deferred>
## Deferred Ideas

- None — discussion stayed strictly within the Phase 8 scope boundary.

</deferred>

---

*Phase: 08-Multi-Hop Ad-Hoc Mesh Routing & Relay Protocol*
