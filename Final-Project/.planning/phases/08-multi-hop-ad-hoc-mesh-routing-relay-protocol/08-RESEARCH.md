# Phase 8: Multi-Hop Ad-Hoc Mesh Routing & Relay Protocol - Research

**Researched:** 2026-10-20  
**Phase:** 08-multi-hop-ad-hoc-mesh-routing-relay-protocol  
**Target:** SHADOWCOMM v2.0 Tactical Communications Platform  
**Author:** GSD Phase Researcher (Subagent)

---

## Executive Summary

Phase 8 expands the SHADOWCOMM communications architecture from point-to-point and single-relay transports into a resilient, decentralized **Multi-Hop Ad-Hoc Mesh Routing & Relay Protocol**. In tactical operating environments, operational endpoints (Station Alpha at port 5051 and Station Bravo at port 5052) frequently lack direct line-of-sight RF connectivity due to terrain, electronic warfare, or extreme standoff distances. Phase 8 solves this by deploying a dynamic mesh network across > 5 mobile and aerial relay nodes (`relay-ground-01`, `relay-ground-02`, `relay-uav-alpha`, `relay-uav-bravo`, `relay-convoy-01`), delivering autonomous path discovery, opportunistic store-and-forward bundle transmission, strict loop prevention, and real-time 3D tactical situational awareness.

Key research findings and architectural decisions:
1. **Routing Algorithm**: A Multi-Factor Weighted Dijkstra engine balances hop counts, physical link latencies, battery reserves, queue depths, and storage thresholds. Depleted (<10%) or congested nodes are penalized, steering traffic toward healthy flight corridors or vehicular relays.
2. **RF Elevation Model**: Realistic tiered RF horizon constraints govern link formation (Ground-to-Ground: 15 km; Ground-to-UAV: 40 km; UAV-to-UAV: 60 km). In theater coordinates, Station Alpha and Station Bravo are separated by 45 km, mathematically proving that multi-hop relaying is mandatory for inter-station communication.
3. **Wire Framing Protocol**: A compact 24-byte cleartext outer binary header (`[0x4D 0x53 0x48 ('MSH')][Flags][Initial TTL][Remaining TTL][Hop Count][Visited Bitmask][Bundle UUID]`) encapsulates post-quantum Envelope v3 (and legacy v2) payloads. Transit relays forward bundles based strictly on outer header telemetry without decrypting quantum-resistant ciphertext.
4. **Reliability & Loop Prevention**: Strict per-hop TTL decrementing drops expired bundles (`BUNDLE_TTL_EXPIRED`), while a 16-bit visited node bitmask prevents cyclic packet storms (`ROUTING_LOOP_DETECTED`). Hop-by-hop custody transfer tokens (`CUSTODY_ACK`) free upstream node buffers, while the originating station holds its durable queue lease until Station Bravo issues the final end-to-end signed receipt.
5. **Interactive 3D Tactical Console**: Upgrading React Three Fiber `LinkTopologyView` to render a stratified 3D theater (ground plane $Y=0$, aerial corridors $Y=+4.5$ and $Y=+6.0$ with orbital drift), dual-layer mesh links (dormant vs glowing neon cyan active forwarding vectors), floating tactical HUD pills, a slide-over inspector drawer, and one-click camera presets.
6. **Impairment Test Bench & Fast Recovery**: An interactive test bench ribbon with direct 3D toggles and 3 pre-canned tactical drill scenarios ("UAV-Alpha Signal Lost", "Ground Relays Jammed", "Convoy Mobile Breakout"). Upstream relays detect unacknowledged hops within 1.5 seconds and trigger local alternate Dijkstra recalculation, converging in < 300 ms with an illuminated amber route diversion banner.

---

## Key Technical Requirements & Constraints

### Requirements Traceability Matrix

| Requirement | Description | Architectural Solution | Verification Plan |
|---|---|---|---|
| **MSH-01** | Mesh routing engine implements dynamic bundle routing across > 5 named mobile and aerial relay nodes (`relay-ground-01`, `relay-ground-02`, `relay-uav-alpha`, `relay-uav-bravo`, `relay-convoy-01`). | `MeshRouter` service in `integration/relay_nodes/mesh_router.py` with multi-factor Dijkstra and tiered RF adjacency graph across all 5+ named nodes. | Unit tests in `test_mesh_routing.py` verifying path discovery across all node types and coordinates. |
| **MSH-02** | Payloads include hop-by-hop TTL decrements, loop prevention checks, and store-and-forward custody transfer acknowledgements. | 24-byte `MSH` binary outer header framing; uint8 TTL decrement; uint16 visited node bitmask check; 16-byte HMAC `CUSTODY_ACK` token generation. | Automated tests verifying TTL expiration drops, duplicate bitmask loop drops, and custody handshake verification. |
| **MSH-03** | React Link Topology View renders interactive multi-hop routing paths, real-time node hop counts, and active bundle forwarding vectors across 3D canvas. | Stratified 3D scene in `LinkTopologyView.tsx` with dual-layer mesh lines, glowing cyan laser vectors, animated packet pulses, and floating HUD pills. | Frontend typecheck and build (`tsc -b && vite build`) and visual inspection of 3D canvas elements. |
| **MSH-04** | Simulated node link dropouts automatically trigger dynamic route discovery and reroute pending message bundles through surviving intermediary relays. | Fast 1.5s hop custody timeout with local alternate Dijkstra forwarding; test bench scenario injection; < 300ms route re-convergence. | Automated simulation tests verifying rerouting upon node failure without originator retransmission. |

### Technical Constraints & Guidelines

1. **Dynamic Linker Safety on Apple Silicon (CRITICAL)**:
   - `import torch` MUST precede any import of `numpy` or `scipy` across all Python test modules, background daemons, and services (`Final-Project/tests/conftest.py` convention). Missing this ordering causes a macOS OpenBLAS symbol collision `SIGSEGV 139`.
2. **Strict Cryptographic Integrity (Phase 7 Envelope v3 Compatibility)**:
   - Envelope v3 payloads utilize AES-256-GCM authenticated encryption with strict Associated Authenticated Data (AAD) binding to `sender_endpoint_id:recipient_endpoint_id:message_id`.
   - Relay nodes in the mesh are transit brokers and do NOT possess the private keys of Station Bravo. Therefore, relays must never attempt to decrypt or modify the inner ciphertext payload. Any payload byte mutation will fail GCM authentication and trigger an HTTP 422 `CRYPTO_AUTHENTICATION_FAILED` error at the destination.
3. **Database Concurrency & Physical Isolation (Phase 6 Compatibility)**:
   - Station Alpha (`alpha.db` on port 5051) and Station Bravo (`bravo.db` on port 5052) run as isolated SQLite processes. All SQLite connections must execute `PRAGMA busy_timeout=5000` before `PRAGMA journal_mode=WAL`.
4. **Zero Automated Git Operations**:
   - All files must be written directly to disk. Automated git commits, pushes, and resets are strictly prohibited.
5. **Backwards Compatibility with Existing Tests**:
   - Existing integration test `Final-Project/tests/integration/test_relay_nodes.py` expects `relay-ground-01` and `relay-aerial-sim-01` to be registered. The `RelayNodeManager` must seed both legacy and newly required named nodes without breaking existing test assertions.

---

## Architecture & Component Design

### 1. Spatial Theater Layout & Tiered RF Adjacency Model

The operational area is represented in a unified 3D coordinate system where 1 theater unit corresponds to $2.5\text{ km}$ ground distance.

```
                  [relay-uav-bravo] (Y=+6.0)
                        ▲
                        │ UAV-UAV (15.7 km <= 60 km)
                        ▼
    [relay-uav-alpha] (Y=+4.5)
       ▲                                 ▲
       │ Ground-UAV                      │ Ground-UAV
       ▼                                 ▼
[Station Alpha] ───> [relay-ground-01] ───> [relay-convoy-01] ───> [relay-ground-02] ───> [Station Bravo]
   (-9, 0, 0)           (-5, 0, -1.5)             (0, 0, 2.0)            (+5, 0, -1.5)           (+9, 0, 0)
                          (Y=0)                     (Y=0)                    (Y=0)
```

#### Node Positioning Table

| Node ID | Display Name | Node Type | Theater Pos $(X, Y, Z)$ | Elevation | Sector |
|---|---|---|---|---|---|
| `endpoint-a` | Station Alpha Gateway | Fixed Station | `[-9.0, 0.0, 0.0]` | Ground ($0\text{ m}$) | West Edge |
| `relay-ground-01` | Portable Ground Relay Alpha | `PORTABLE_GROUND` | `[-5.0, 0.0, -1.5]` | Ground ($0\text{ m}$) | Alpha Sector |
| `relay-uav-alpha` | Loitering Tactical Drone Alpha | `AERIAL_PAYLOAD_SIMULATED` | `[-3.0, 4.5, 0.5]` | High ($11.25\text{ km}$) | West Airborne |
| `relay-convoy-01` | Tactical Mobile Convoy 01 | `VEHICLE_GATEWAY` | `[0.0, 0.0, 2.0]` | Ground ($0\text{ m}$) | Central Axis |
| `relay-uav-bravo` | High-Altitude UAV Relay Bravo | `AERIAL_PAYLOAD_SIMULATED` | `[+3.0, 6.0, -0.5]` | Stratospheric ($15.0\text{ km}$) | East Airborne |
| `relay-ground-02` | Portable Ground Relay Bravo | `PORTABLE_GROUND` | `[+5.0, 0.0, -1.5]` | Ground ($0\text{ m}$) | Bravo Sector |
| `endpoint-b` | Station Bravo Gateway | Fixed Station | `[+9.0, 0.0, 0.0]` | Ground ($0\text{ m}$) | East Edge |
| `relay-aerial-sim-01` | Simulated Aerial Relay (Legacy) | `AERIAL_PAYLOAD_SIMULATED` | `[0.0, 5.0, 0.0]` | High ($12.5\text{ km}$) | Center Airborne |

#### Tiered RF Horizon Limits

Adjacency between any two nodes $u$ and $v$ is determined by Euclidean distance $d(u, v)$ in kilometers:
$$d(u, v) = 2.5 \times \sqrt{(x_u - x_v)^2 + (y_u - y_v)^2 + (z_u - z_v)^2}$$

- **Ground-to-Ground Link**: Maximum range $R_{\text{GG}} = 15.0\text{ km}$ ($6.0\text{ units}$).
- **Ground-to-UAV Link**: Maximum range $R_{\text{GU}} = 40.0\text{ km}$ ($16.0\text{ units}$).
- **UAV-to-UAV Link**: Maximum range $R_{\text{UU}} = 60.0\text{ km}$ ($24.0\text{ units}$).

#### Adjacency & Link Budget Analysis

1. **Station Alpha $\leftrightarrow$ Station Bravo**:
   Distance $= 2.5 \times |9 - (-9)| = 45.0\text{ km} > 15.0\text{ km}$. Direct link is physically impossible. Multi-hop traversal is required.
2. **Primary Aerial Path**:
   - Alpha $\to$ `relay-uav-alpha`: $\text{dist} = 2.5 \times \sqrt{6^2 + 4.5^2 + 0.5^2} = 18.8\text{ km} \le 40\text{ km}$ (Connected)
   - `relay-uav-alpha` $\to$ `relay-uav-bravo`: $\text{dist} = 2.5 \times \sqrt{6^2 + 1.5^2 + 1.0^2} = 15.7\text{ km} \le 60\text{ km}$ (Connected)
   - `relay-uav-bravo` $\to$ Bravo: $\text{dist} = 2.5 \times \sqrt{6^2 + 6^2 + 0.5^2} = 21.25\text{ km} \le 40\text{ km}$ (Connected)
   - *Total hops: 3. Optimal latency: ~35 ms.*
3. **Primary Ground Path**:
   - Alpha $\to$ `relay-ground-01`: $\text{dist} = 2.5 \times \sqrt{4^2 + 1.5^2} = 10.7\text{ km} \le 15\text{ km}$ (Connected)
   - `relay-ground-01` $\to$ `relay-convoy-01`: $\text{dist} = 2.5 \times \sqrt{5^2 + 3.5^2} = 15.25\text{ km}$ (adjust convoy to $Z=1.0 \implies 14.0\text{ km} \le 15\text{ km}$) (Connected)
   - `relay-convoy-01` $\to$ `relay-ground-02`: $\text{dist} = 14.0\text{ km} \le 15\text{ km}$ (Connected)
   - `relay-ground-02` $\to$ Bravo: $\text{dist} = 10.7\text{ km} \le 15\text{ km}$ (Connected)
   - *Total hops: 4. Optimal latency: ~85 ms.*

---

### 2. Multi-Factor Weighted Dijkstra Algorithm

To prevent routing through battery-depleted or congested relays, each candidate directed edge $(u, v)$ is evaluated with a cost function $C(u, v)$.

#### Mathematical Formulation

$$C(u, v) = W_{\text{hop}} + W_{\text{latency}} \cdot \left(\frac{L_{uv}}{50.0}\right) + \text{Pen}_{\text{queue}}(Q_v) + \text{Pen}_{\text{battery}}(B_v) + \text{Pen}_{\text{storage}}(S_v)$$

Where:
- $W_{\text{hop}} = 1.0$ (Base hop cost).
- $W_{\text{latency}} = 0.5$; $L_{uv}$ is estimated RF link latency in milliseconds (typically 10ms for aerial links, 25ms for ground links).
- $Q_v$ is current queue depth of node $v$:
  $$\text{Pen}_{\text{queue}}(Q_v) = 1.5 \cdot \left(\frac{Q_v}{10.0}\right)^{1.5}$$
- $B_v \in [0.0, 100.0]$ is remaining battery percentage:
  $$\text{Pen}_{\text{battery}}(B_v) = \begin{cases}
  0.0 & \text{if } B_v > 50.0 \\
  2.0 \cdot \left(\frac{50.0 - B_v}{40.0}\right) & \text{if } 10.0 < B_v \le 50.0 \\
  10.0 + 4.0 \cdot \left(\frac{10.0 - B_v}{5.0}\right) & \text{if } 5.0 < B_v \le 10.0 \\
  \infty & \text{if } B_v \le 5.0 \text{ (Failsafe Cutoff Active)}
  \end{cases}$$
- $S_v \in [0.0, 100.0]$ is storage usage percentage:
  $$\text{Pen}_{\text{storage}}(S_v) = \begin{cases}
  0.0 & \text{if } S_v \le 80.0 \\
  3.0 \cdot \left(\frac{S_v - 80.0}{18.0}\right)^2 & \text{if } 80.0 < S_v < 98.0 \\
  \infty & \text{if } S_v \ge 98.0 \text{ (Storage Exhausted)}
  \end{cases}$$
- Node Status Barrier: If node $v$ status is `OFFLINE`, `FORCE_OFFLINE`, or `RF_JAMMED`, then $C(u, v) = \infty$.

#### Dynamic Rerouting Demonstration

1. **Nominal State**:
   - Aerial Corridor cost: $(1.0 + 0.1) + (1.0 + 0.1) + (1.0 + 0.1) = 3.3$.
   - Ground Convoy cost: $(1.0 + 0.25) \times 4 = 5.0$.
   - *Result*: Aerial path chosen (3 hops).
2. **Impairment State (`relay-uav-alpha` depleted to 8% battery)**:
   - `relay-uav-alpha` cost penalty: $10.0 + 4.0 \times \frac{2}{5} = 11.6$.
   - Total Aerial Corridor cost: $3.3 + 11.6 = 14.9$.
   - Ground Convoy cost remains $5.0$.
   - *Result*: Dijkstra automatically diverts around UAV-Alpha via `relay-ground-01` $\to$ `relay-convoy-01` $\to$ `relay-ground-02` $\to$ Station Bravo without dropping packets.

---

### 3. Binary Mesh Header Framing & Custody Protocol

#### 24-Byte Binary Header Layout

```
 0                   1                   2                   3
 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1
+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
|       'M'     |       'S'     |       'H'     |     Flags     |
+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
|  Initial TTL  | Remaining TTL |   Hop Count   |               |
+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+               +
|                       Visited Bitmask                         |
+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
|                                                               |
+                                                               +
|                                                               |
+                          Bundle UUID                          +
|                           (16 Bytes)                          |
+                                                               +
|                                                               |
+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
|                 Encrypted Payload (Envelope v3/v2)            |
|                              ...                              |
+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
```

#### Field Specifications

| Field | Offset | Length | Format | Semantics |
|---|---|---|---|---|
| Magic | `0x00` | 3 B | `bytes` | Fixed identifier: `0x4D 0x53 0x48` (`b"MSH"`). |
| Flags | `0x03` | 1 B | `uint8` | Bitfield: `0x01`=FLASH, `0x02`=IMMEDIATE, `0x00`=ROUTINE, `0x80`=CUSTODY_REQ. |
| Initial TTL | `0x04` | 1 B | `uint8` | Configured initial maximum hop allowance (default: 8). |
| Remaining TTL | `0x05` | 1 B | `uint8` | Decremented by 1 at each forwarding hop. Drop on 0. |
| Hop Count | `0x06` | 1 B | `uint8` | Incremented by 1 at each forwarding hop (starts at 0). |
| Visited Bitmask | `0x07` | 2 B | `uint16` (BE) | Bitmask representing visited nodes. Up to 16 nodes. |
| Bundle UUID | `0x09` | 16 B | `bytes[16]` | Binary representation of UUIDv4 (`uuid.UUID.bytes`). |
| Payload | `0x19` | Variable | Binary | Raw Envelope v3 (starts with `0x03`) or Envelope v2. |

**Python struct string**: `"!3sBBBBH16s"` (exactly 24 bytes).

#### Node Bitmask Index Assignments

| Node Identifier | Bit Index | Bitmask Hex |
|---|---|---|
| `endpoint-a` | 0 | `0x0001` |
| `relay-ground-01` | 1 | `0x0002` |
| `relay-convoy-01` | 2 | `0x0004` |
| `relay-ground-02` | 3 | `0x0008` |
| `relay-uav-alpha` | 4 | `0x0010` |
| `relay-uav-bravo` | 5 | `0x0020` |
| `endpoint-b` | 6 | `0x0040` |
| `relay-aerial-sim-01` (Legacy) | 7 | `0x0080` |

#### Loop Prevention & TTL Drop Rules

1. **Loop Check**: When node $k$ receives bundle:
   $$\text{is\_loop} = (\text{visited\_bitmask} \ \& \ (1 \ll \text{bit\_index}(k))) \ne 0$$
   If `is_loop` is true:
   - Packet is discarded immediately.
   - Record `MessageEvent(event_type="ROUTING_LOOP_DETECTED", error_code="ROUTING_LOOP_DETECTED")`.
   - Record `SecurityAuditLog(action="ROUTING_LOOP_DETECTED", severity="HIGH")`.
2. **TTL Decrement**:
   $$\text{remaining\_ttl} = \text{remaining\_ttl} - 1$$
   $$\text{hop\_count} = \text{hop\_count} + 1$$
   $$\text{visited\_bitmask} = \text{visited\_bitmask} \ | \ (1 \ll \text{bit\_index}(k))$$
   If $\text{remaining\_ttl} == 0$:
   - Packet is discarded immediately.
   - Record `MessageEvent(event_type="BUNDLE_TTL_EXPIRED", error_code="BUNDLE_TTL_EXPIRED")`.
   - Record `SecurityAuditLog(action="BUNDLE_TTL_EXPIRED", severity="MEDIUM")`.

#### Custody Transfer Protocol (D-07, D-14)

```
[Originator: Alpha]        [Relay-01]               [Relay-02]            [Recipient: Bravo]
         │                     │                         │                        │
         ├─── MSH Bundle ─────>│                         │                        │
         │                     │── Verify Header         │                        │
         │                     │── Enqueue In Storage    │                        │
         │<── CUSTODY_ACK ─────┤                         │                        │
         │    (Releases Alpha  │                         │                        │
         │     local lease)    ├─── MSH Bundle ─────────>│                        │
         │                     │                         │── Verify & Enqueue     │
         │                     │<── CUSTODY_ACK ─────────┤                        │
         │                     │    (Releases Relay-01   │                        │
         │                     │     storage buffer)     ├─── MSH Bundle ────────>│
         │                     │                         │                        │── Verify PQC
         │                     │                         │<── Signed Delivery ────┤── Store in Inbox
         │<────────────────────┴─────────────────────────┴──── Receipt ──────────┤
         │                                                                        │
```

- **Custody Token Formulation**:
  $$\text{token} = \text{HMAC-SHA256}_{K_{\text{custody}}}(\text{node\_id} \parallel \text{bundle\_id} \parallel \text{hop\_count})[0:16]$$
- **Fast Timeout & Local Alternate Forwarding**:
  - Upstream relay waits at most $1.5\text{ seconds}$ for downstream `CUSTODY_ACK`.
  - If timeout fires without ACK, downstream node is assumed lost.
  - Upstream relay queries `MeshRouter.compute_route(current_node, destination, exclude=[downstream_node])`.
  - Upstream relay immediately retransmits the bundle to the new next-hop without needing to signal Station Alpha for an end-to-end retry.

---

### 4. 3D LinkTopologyView Visual Architecture

```
+-----------------------------------------------------------------------------------------+
| [3D LINK TOPOLOGY]  West Edge (Alpha) <── Multi-Hop Mesh ──> East Edge (Bravo)          |
| [Presets: Theater Overview | Focus UAV Corridors | Forwarding Vector | Ground Axis]     |
+-----------------------------------------------------------------------------------------+
|                                                                                         |
|       [UAV-Alpha Pill]                           [UAV-Bravo Pill]                       |
|       (Batt: 98% | Q: 0)                         (Batt: 92% | Q: 0)                     |
|           ◆ (Y=+4.5)                                  ◆ (Y=+6.0)                        |
|          / \                                         / \                                |
|         /   \========= Glowing Neon Cyan Vector ====/   \                               |
|        /     \                                     /     \                              |
|       ▼       ▼                                   ▼       ▼                             |
|  [Alpha] ── [Ground-01] ────── [Convoy-01] ─── [Ground-02] ─── [Bravo]                 |
|  (-9,0,0)   (-5,0,-1.5)         (0,0,2.0)      (+5,0,-1.5)     (+9,0,0)                 |
|                                                                                         |
+-----------------------------------------------------------------------------------------+
| [Test Bench: Scenario 1: UAV-Alpha Lost | Scenario 2: Ground Jammed | Reset Nominal]    |
| Telemetry: [MESH REROUTE: Bypassed relay-uav-alpha -> Diverted via relay-convoy-01]    |
+-----------------------------------------------------------------------------------------+
```

#### Visual Component Breakdown

1. **Stratified Elevation**:
   - Ground nodes at $Y=0$.
   - `relay-uav-alpha` at $Y=+4.5$ with slow circular drift:
     $$x(t) = -3.0 + 0.35 \cos(0.4 t), \quad z(t) = 0.5 + 0.35 \sin(0.4 t)$$
   - `relay-uav-bravo` at $Y=+6.0$ with counter-rotational drift:
     $$x(t) = +3.0 + 0.45 \cos(-0.3 t), \quad z(t) = -0.5 + 0.45 \sin(-0.3 t)$$
2. **Dual-Layer Mesh Links**:
   - *Dormant Links*: Rendered using Three.js `Line` in subtle translucent zinc (`#27272a`, opacity 0.35, linewidth 1).
   - *Active Forwarding Vectors*: Rendered in glowing cyan (`#06b6d4` / `#22d3ee`, opacity 0.95, linewidth 3.5) with animated photon particle pulses travelling hop-by-hop.
   - *Impaired/Broken Links*: Rendered in dashed red (`#ef4444`) with pulsing strikethrough.
3. **Floating HUD Pills (HTML Overlay)**:
   - Floating `<Html center>` components above each node displaying display name, battery %, queue depth, and status pill (`ONLINE`, `STANDBY`, `JAMMED`, `CRITICAL`).
4. **Slide-Over Inspector Drawer**:
   - Clicking any node opens a right-hand tactical drawer displaying:
     - Battery health gauge & temperature.
     - Storage utilization gauge & queue depth.
     - Connected RF neighbors and RSSI/distance.
     - Forwarding count and hop history log.
     - Direct impairment toggle buttons (`FORCE_OFFLINE`, `BATTERY_CRITICAL`, `RF_JAMMED`, `ONLINE`).

---

## API & Data Flow Analysis

### 1. New & Extended Backend Endpoints

#### `GET /api/v1/topology/mesh`
Returns full mesh topology, RF links, and the currently active forwarding path.

*Response Schema (200 OK)*:
```json
{
  "nodes": [
    {
      "id": "relay-ground-01",
      "display_name": "Portable Ground Relay Alpha",
      "node_type": "PORTABLE_GROUND",
      "status": "ONLINE",
      "battery_percentage": 94.5,
      "storage_used_pct": 15.4,
      "queue_depth": 0,
      "position": [-5.0, 0.0, -1.5],
      "is_approved": true,
      "failsafe_cutoff_active": false
    },
    {
      "id": "relay-uav-alpha",
      "display_name": "Tactical Drone Alpha",
      "node_type": "AERIAL_PAYLOAD_SIMULATED",
      "status": "ONLINE",
      "battery_percentage": 98.0,
      "storage_used_pct": 8.0,
      "queue_depth": 0,
      "position": [-3.0, 4.5, 0.5],
      "is_approved": true,
      "failsafe_cutoff_active": false
    }
  ],
  "links": [
    {
      "source": "endpoint-a",
      "target": "relay-uav-alpha",
      "distance_km": 18.8,
      "max_range_km": 40.0,
      "rf_tier": "GROUND_UAV",
      "latency_ms": 12.5,
      "is_active_route": true
    },
    {
      "source": "relay-uav-alpha",
      "target": "relay-uav-bravo",
      "distance_km": 15.7,
      "max_range_km": 60.0,
      "rf_tier": "UAV_UAV",
      "latency_ms": 8.0,
      "is_active_route": true
    }
  ],
  "active_route": {
    "source": "endpoint-a",
    "destination": "endpoint-b",
    "path": ["endpoint-a", "relay-uav-alpha", "relay-uav-bravo", "endpoint-b"],
    "total_hops": 3,
    "estimated_latency_ms": 35.5,
    "route_status": "OPTIMAL"
  }
}
```

#### `POST /api/v1/relays/<relay_id>/telemetry`
Operator manual impairment or telemetry update.

*Request Body*:
```json
{
  "battery": 4.0,
  "status": "FORCE_OFFLINE",
  "queue_depth": 25,
  "storage_pct": 45.0
}
```

*Response Schema (200 OK)*: Returns updated `RelayNode.to_dict()` with `failsafe_cutoff_active=true` and newly calculated route.

#### `POST /api/v1/relays/scenario`
Triggers one of 3 tactical drill scenarios (D-15).

*Request Body*:
```json
{
  "scenario": "scenario_1_uav_signal_lost"
}
```
*Supported Scenarios*:
- `scenario_1_uav_signal_lost`: Sets `relay-uav-alpha` to `FORCE_OFFLINE`. Path shifts instantly to ground convoy.
- `scenario_2_ground_relays_jammed`: Sets `relay-ground-01`, `relay-convoy-01`, `relay-ground-02` to `RF_JAMMED`. Forces all-aerial corridor.
- `scenario_3_convoy_breakout`: Sets both UAVs to `OFFLINE`. Forces traffic strictly through `relay-convoy-01`.
- `reset_nominal`: Restores all relays to nominal online states.

*Response Schema (200 OK)*:
```json
{
  "scenario": "scenario_1_uav_signal_lost",
  "previous_path": ["endpoint-a", "relay-uav-alpha", "relay-uav-bravo", "endpoint-b"],
  "new_path": ["endpoint-a", "relay-ground-01", "relay-convoy-01", "relay-ground-02", "endpoint-b"],
  "reroute_event": "[MESH REROUTE: Bypassed relay-uav-alpha -> Diverted via relay-convoy-01 -> Delivered]",
  "convergence_latency_ms": 42.0,
  "status": "CONVERGED"
}
```

#### `POST /api/v1/mesh/route/simulate`
Simulates hop-by-hop bundle dispatch from Station Alpha to Station Bravo, recording custody transfers and verifying loop and TTL protections.

---

## Validation Architecture

### 1. Test Suite Layout

```
Final-Project/tests/
├── test_mesh_routing.py               <-- Core Phase 8 tests (Routing, Dijkstra, Framing, Rerouting)
├── test_pqc_crypto.py                 <-- Phase 7 verified tests (Must stay 100% green)
├── test_multi_database_isolation.py   <-- Phase 6 verified tests (Must stay 100% green)
└── integration/
    └── test_relay_nodes.py            <-- Phase 4 relay tests (Must stay 100% green)
```

### 2. Comprehensive Test Cases for `test_mesh_routing.py`

1. **`test_mesh_topology_and_named_relays`**:
   - Verifies `RelayNodeManager` initializes $> 5$ named nodes: `relay-ground-01`, `relay-ground-02`, `relay-uav-alpha`, `relay-uav-bravo`, `relay-convoy-01` and legacy `relay-aerial-sim-01`.
   - Validates coordinates and altitude tiers.
2. **`test_rf_range_model_adjacency`**:
   - Verifies Ground-to-Ground connections are formed $\le 15\text{ km}$ and rejected $> 15\text{ km}$.
   - Verifies Ground-to-UAV connections are formed $\le 40\text{ km}$ and rejected $> 40\text{ km}$.
   - Verifies UAV-to-UAV connections are formed $\le 60\text{ km}$ and rejected $> 60\text{ km}$.
   - Confirms Station Alpha cannot link directly to Station Bravo.
3. **`test_multi_factor_dijkstra_cost_metric`**:
   - In nominal conditions, selects optimal 3-hop aerial corridor (`Alpha -> UAV-Alpha -> UAV-Bravo -> Bravo`).
   - Injects battery depletion ($B < 10\%$) on `relay-uav-alpha`: verifies Dijkstra re-routes around it.
   - Injects queue congestion ($Q > 30$) on `relay-convoy-01`: verifies Dijkstra chooses higher-cost alternate route.
   - Injects failsafe cutoff ($B \le 5\%$ or $S \ge 98\%$): verifies node is assigned cost $\infty$.
4. **`test_binary_mesh_header_framing`**:
   - Verifies 24-byte header encoding and decoding (`!3sBBBBH16s`).
   - Verifies inner payload bytes (Envelope v3) are untouched.
   - Verifies priority flags (`FLASH`, `IMMEDIATE`, `ROUTINE`).
5. **`test_hop_ttl_decrement_and_expiration`**:
   - Verifies TTL decrements by 1 on each hop.
   - When bundle arrives with `remaining_ttl == 1`, next hop drops with `BUNDLE_TTL_EXPIRED`.
   - Verifies `MessageEvent` and `SecurityAuditLog` are recorded.
6. **`test_visited_bitmask_loop_detection`**:
   - Forges a packet where `visited_bitmask` already has the bit of the current node set.
   - Verifies packet is dropped immediately with `ROUTING_LOOP_DETECTED`.
7. **`test_custody_transfer_handshake`**:
   - Downstream node returns valid 16-byte HMAC `CUSTODY_ACK`.
   - Upstream node releases its local queue buffer upon receipt.
8. **`test_priority_queue_shedding`**:
   - When node storage reaches $90\%$, `ROUTINE` bundles are dropped first. `FLASH` bundles are preserved.
9. **`test_dynamic_reroute_failure_recovery`**:
   - Simulates node dropout midway through forwarding.
   - Verifies local alternate forwarding discovers surviving path and delivers bundle.
10. **`test_rest_api_mesh_topology_and_scenarios`**:
    - Full end-to-end REST test of `/api/v1/topology/mesh`, `/api/v1/relays/scenario`, and `/api/v1/mesh/route/simulate`.

### 3. Frontend Validation

1. **TypeScript Compilation**: `npm run build` (`tsc -b && vite build`) in `Final-Project/frontend/` must complete with 0 errors.
2. **Visual Inspection**:
   - Canvas loads with stratified altitude planes.
   - Dormant links render as zinc lines; active route renders as neon cyan laser with moving particles.
   - Clicking Scenario 1 instantly updates node to pulsing red, strikes through link, and re-lights ground path in < 300 ms with amber alert toast.

---

## Implementation Pitfalls & Mitigation Strategies

| Pitfall | Impact | Mitigation Strategy |
|---|---|---|
| **Apple Silicon Linker Collision** | `import torch` after `numpy` causes `SIGSEGV 139` crash during test execution. | Strictly place `import torch` at line 1 of all Python scripts and test files. |
| **Tampered Ciphertext Rejection** | Modifying inner payload bytes inside relays causes Station Bravo to reject packet with HTTP 422. | Relays operate strictly on the outer 24-byte `MSH` binary framing. The inner payload is treated as opaque binary data and forwarded unchanged. |
| **Breaking Phase 4 Relay Tests** | `test_relay_nodes.py` checks for `relay-ground-01` and `relay-aerial-sim-01`. Removing them causes regression failures. | Seed both legacy relays alongside the new 5 named nodes in `RelayNodeManager._seed_default_relays()`. |
| **Route Oscillation / Flapping** | Small queue fluctuations cause Dijkstra to flip routes back and forth rapidly. | Apply hysteresis smoothing to queue depth metrics and enforce a minimum route hold duration (or 5s heartbeat interval). |
| **WebGL Context Exhaustion** | Re-mounting React Three Fiber `<Canvas>` on tab switches crashes the browser tab. | Keep the `<Canvas>` component mounted and drive updates entirely through reactive model props and lightweight Three.js hooks. |

---

## RESEARCH COMPLETE
This research provides the complete mathematical, wire-framing, spatial, and API specifications required for `gsd-planner` to generate phase plans for Phase 08.
