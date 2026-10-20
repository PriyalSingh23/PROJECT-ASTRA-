# Phase 08: Multi-Hop Ad-Hoc Mesh Routing & Relay Protocol - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-10-20  
**Phase:** 08-multi-hop-ad-hoc-mesh-routing-relay-protocol  
**Areas discussed:** Mesh Topology & Dynamic Routing Algorithm, Bundle Header Framing, Hop TTL & Custody Transfer, 3D LinkTopologyView Visuals & Path Vectors, Relay Impairment & Dynamic Rerouting Test Bench  

---

## 1. Mesh Topology & Dynamic Routing Algorithm

| Option | Description | Selected |
|--------|-------------|:--------:|
| Multi-Factor Weighted Dijkstra | Cost function combines hop count, link latency, remaining battery, and queue depth so depleted or congested nodes are avoided | ✓ |
| Pure Minimum-Hop Shortest Path | Standard AODV/Bellman-Ford shortest path picking route with fewest intermediate hops regardless of telemetry | |
| Opportunistic Spray-and-Wait DTN | Bundle is replicated to multi-carrier relays within range until a custody ACK is returned | |

**User's choice:** Multi-Factor Weighted Dijkstra  
**Notes:** User chose multi-factor cost to prevent routing through nodes with low battery or overflowing buffers.

| Option | Description | Selected |
|--------|-------------|:--------:|
| Tiered RF Range & Elevation Adjacency | Realistic RF ranges based on node altitude (Ground-Ground 15km, Ground-UAV 40km, UAV-UAV 60km) with automatic bidirectional link formation | ✓ |
| Explicit Configured Tactical Matrix | Fixed adjacency list for the 5 named nodes with operator-configurable link states in settings | |
| Dynamic SNR / Link Budget Horizon | Links form dynamically only when calculated path loss yields SNR >= 3 dB based on coordinates | |

**User's choice:** Tiered RF Range & Elevation Adjacency  
**Notes:** Elevation-aware RF horizons match realistic tactical field operations across ground and UAV relay assets.

| Option | Description | Selected |
|--------|-------------|:--------:|
| Dual Edge Gateways | Alpha and Bravo are tactical edge stations that connect to nearby relays and can route multi-hop through the entire mesh to each other | ✓ |
| Dedicated Local Access Ingress | Alpha connects strictly to relay-ground-01; Bravo connects strictly to relay-ground-02; all cross-traffic must traverse mesh interior | |
| Full Peer Mesh Participants | Alpha and Bravo are full mesh routers that can also forward third-party transit bundles if needed | |

**User's choice:** Dual Edge Gateways  
**Notes:** Endpoints act as gateways originating and receiving operational messages.

| Option | Description | Selected |
|--------|-------------|:--------:|
| Hybrid Reactive Reroute + 5s Topology Heartbeat | Fast reactive path recalculation on packet drop/outage backed by lightweight 5s beacon polling | ✓ |
| Pure Reactive On-Demand Discovery | Path recalculated solely when a dispatch occurs or link fails, with zero idle background traffic | |
| Strict Periodic Proactive Convergence (2s) | Nodes continuously exchange link-state vectors every 2 seconds with immediate broadcast flooding | |

**User's choice:** Hybrid Reactive Reroute + 5s Topology Heartbeat  
**Notes:** Combines instant outage re-routing with background telemetry sync.

---

## 2. Bundle Header Framing, Hop TTL & Custody Transfer

| Option | Description | Selected |
|--------|-------------|:--------:|
| Outer Mesh Header Framing | Cleartext binary outer header `[0x4D 0x53 0x48 ('MSH')][Flags][TTL][HopCount][VisitedNodes][Payload]` wrapping encrypted Envelope v3 payload so relays route without decrypting | ✓ |
| CBOR / JSON Structured Bundle | Standard RFC 9171 DTN bundle format with structured JSON headers and base64 envelope body | |
| Integrated Envelope v3 Extension | Extend the internal Envelope v3 layout with dedicated routing TLV (Type-Length-Value) blocks | |

**User's choice:** Outer Mesh Header Framing  
**Notes:** Encapsulates encrypted Envelope v3 so transit nodes do not require cryptographic private keys.

| Option | Description | Selected |
|--------|-------------|:--------:|
| Strict Decrement & Visited Set Guard | TTL decrements at each hop (drops on TTL=0 as BUNDLE_TTL_EXPIRED); visited node ID set prevents loops (drops immediate if node already visited as ROUTING_LOOP_DETECTED) | ✓ |
| Time-Based Unix Epoch Expiry | Bundles carry an absolute UTC expiration timestamp (e.g. 120s TTL) rather than a hop count counter | |
| Lenient Hop Ceiling | TTL warning is logged when TTL=0, but bundle continues forwarding until hitting an emergency hard stop of 16 hops | |

**User's choice:** Strict Decrement & Visited Set Guard  
**Notes:** Guaranteed loop prevention and strict hop bounded life.

| Option | Description | Selected |
|--------|-------------|:--------:|
| Per-Hop Custody Handshake + End-to-End Signed Receipt | Upstream relay clears buffer upon receiving CUSTODY_ACK from downstream node; originating station holds lease until final Bravo signed receipt reconciles | ✓ |
| Fire-and-Forget Store-and-Forward | Relays immediately clear transit buffer after dispatching downstream without per-hop custody acknowledgements | |
| Cumulative Path Receipt | Every relay appends its signature to a transit receipt block returned along the reverse path | |

**User's choice:** Per-Hop Custody Handshake + End-to-End Signed Receipt  
**Notes:** True DTN custody transfer ensuring hop-by-hop reliability.

| Option | Description | Selected |
|--------|-------------|:--------:|
| Multi-Tier Tactical Priority Queue | FLASH (Emergency) > IMMEDIATE > ROUTINE; when relay storage exceeds 90%, lowest priority expired bundles are dropped first | ✓ |
| Simple FIFO with Head Drop | Standard First-In-First-Out queue; drops oldest bundle when queue reaches max depth (e.g. 100 bundles) | |
| Non-Destructive Backpressure | Downstream relay returns HTTP 429 BUSY, causing upstream node to hold and retry without dropping any bundles | |

**User's choice:** Multi-Tier Tactical Priority Queue  
**Notes:** Ensures emergency tactical traffic survives during network congestion.

---

## 3. 3D LinkTopologyView Visuals & Path Vectors

| Option | Description | Selected |
|--------|-------------|:--------:|
| Stratified Multi-Elevation Tactical Map | Ground relays and mobile convoy at Y=0; aerial UAVs at elevated Y=+4.5 and Y=+6.0 flight corridors with subtle orbital drift; Alpha at [-9, 0, 0] and Bravo at [+9, 0, 0] | ✓ |
| Flat Planar Tactical Hex Grid | All nodes positioned on the ground plane (Y=0) with geometric hexagonal spacing | |
| Concentric Tactical Ring | Fixed circular perimeter with stations at opposite poles and relays distributed symmetrically | |

**User's choice:** Stratified Multi-Elevation Tactical Map  
**Notes:** Realistic 3D tactical altitude visualization for ground vs airborne assets.

| Option | Description | Selected |
|--------|-------------|:--------:|
| Dual-Layer Mesh & Active Neon Laser Vectors | Potential mesh links rendered as subtle translucent zinc lines; active multi-hop route lights up in glowing cyan with moving particle pulses traveling hop-by-hop | ✓ |
| Dynamic Link Quality Heatmap | All links rendered with color-coded gradients (green/amber/crimson) based on real-time link latency and congestion | |
| Static Highlighted Polyline | Solid bold line along the active path with directional arrowheads and no animated particles | |

**User's choice:** Dual-Layer Mesh & Active Neon Laser Vectors  
**Notes:** Clearly differentiates dormant available links from active forwarding vectors.

| Option | Description | Selected |
|--------|-------------|:--------:|
| Floating 3D Node Pills + Click-to-Inspect Drawer | Floating tactical labels with battery, storage, and status; clicking any node or link segment opens a rich slide-over inspector drawer with live metrics and hop logs | ✓ |
| Persistent 2D Matrix Sidebar | A fixed side panel listing all 5+ nodes with real-time gauges alongside the 3D canvas | |
| Minimalist Top Banner Only | Summary HUD showing active hop count (e.g., "[ROUTE: 3 HOPS via UAV-ALPHA]") and total path latency | |

**User's choice:** Floating 3D Node Pills + Click-to-Inspect Drawer  
**Notes:** Clean immersion in 3D canvas with on-demand detailed diagnostics.

| Option | Description | Selected |
|--------|-------------|:--------:|
| Smooth OrbitControls + 4 Tactical Quick-View Presets | Free 360° mouse navigation plus one-click preset buttons: 'Theater Overview', 'Focus UAV Flight Corridors', 'Forwarding Vector Tracking', and 'Ground Axis' | ✓ |
| Pure Free 3D Orbit | Standard Three.js OrbitControls without preset buttons, maximizing viewport space | |
| Locked Isometric Tactical Angle | Fixed military isometric camera angle with pan and zoom only | |

**User's choice:** Smooth OrbitControls + 4 Tactical Quick-View Presets  
**Notes:** Quick-view presets speed up tactical situation assessment.

---

## 4. Relay Impairment & Dynamic Rerouting Test Bench

| Option | Description | Selected |
|--------|-------------|:--------:|
| Hybrid Direct 3D Toggle + Test Bench Ribbon | Operators can toggle node state directly from the 3D node drawer or test ribbon (ONLINE, FORCE_OFFLINE, BATTERY_CRITICAL, STORAGE_FULL, RF_JAMMED) | ✓ |
| Dedicated Tactical Test Bench Modal | Full-screen or modal dialog containing simulated impairment sliders and switches for all 5+ nodes | |
| Diagnostics View Controls Only | Keep all impairment injection located strictly in the existing DiagnosticsView tab | |

**User's choice:** Hybrid Direct 3D Toggle + Test Bench Ribbon  
**Notes:** Immediate operator control without losing context of the 3D mesh.

| Option | Description | Selected |
|--------|-------------|:--------:|
| Fast Hop Custody Timeout (1.5s) & Local Alternate Forwarding | Upstream relay detects unacknowledged custody hop, queries mesh Dijkstra for next best alternate path, and reroutes without originator re-transmission | ✓ |
| Originator End-to-End Fallback | Originating station waits for delivery timeout (5.0s), recalculates an alternate route excluding the failed node, and dispatches a fresh attempt | |
| Store-and-Wait Indefinite Buffering | Upstream relay holds the bundle in memory until the offline node comes back online or TTL expires | |

**User's choice:** Fast Hop Custody Timeout (1.5s) & Local Alternate Forwarding  
**Notes:** Decentralized hop-level recovery provides seamless resilience.

| Option | Description | Selected |
|--------|-------------|:--------:|
| 3 Tactical Drill Scenario Buttons | 'Scenario 1: UAV-Alpha Signal Lost', 'Scenario 2: Ground Relays Jammed (All-Aerial Corridor)', 'Scenario 3: Convoy Mobile Breakout & Extended Hop' + 'Reset All to Nominal' | ✓ |
| Single Random Node Knockout Button | Randomly kills one active node currently along the transmission path | |
| Manual State Toggles Only | No pre-canned scenarios; operators manually configure individual node states | |

**User's choice:** 3 Tactical Drill Scenario Buttons  
**Notes:** Standardized operational drills for repeatable testing and demonstrations.

| Option | Description | Selected |
|--------|-------------|:--------:|
| Pulsing Alert Toast + Strikethrough Red Link + Instant Path Re-Light | Failed node turns pulsing red, broken link shows red strikethrough, new path lights up in cyan within <300ms, and an amber alert banner displays route diversion telemetry | ✓ |
| Quiet Visual Transition | Links re-route smoothly in 3D without popup banners or toasts, reflecting in status indicators only | |
| Modal Interruption Dialog | Modal pops up requiring operator acknowledgment of the dynamic route diversion | |

**User's choice:** Pulsing Alert Toast + Strikethrough Red Link + Instant Path Re-Light  
**Notes:** High visual impact and clear operational feedback for dynamic re-routing events.

---

## Discretionary Technical Decisions
- Exact coordinate offsets and orbital speed formulas for UAV visual motion.
- Three.js particle pulse animation geometries and materials.
- Default TTL configured to 8 hops.

## Deferred Ideas
- None.
