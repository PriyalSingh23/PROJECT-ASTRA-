---
phase: "08"
slug: "multi-hop-ad-hoc-mesh-routing-relay-protocol"
status: approved
shadcn_initialized: false
preset: none
created: "2026-10-20"
---

# Phase 08 — UI Design Contract: Multi-Hop Ad-Hoc Mesh Routing & Relay Protocol

> Visual, component, and 3D interaction design contract for Phase 08: Multi-Hop Ad-Hoc Mesh Routing & Relay Protocol.

---

## 1. Design System & Brand Geometry

| Property | Value |
|---|---|
| Component library | custom React 19 + Tailwind CSS v4 |
| 3D Engine | Three.js (`three@^0.174.0`) + React Three Fiber (`@react-three/fiber@^9.0.0`) + `@react-three/drei@^10.0.0` |
| Icon library | `lucide-react@^1.57.0` (`Radio`, `Orbit`, `Compass`, `Zap`, `Activity`, `AlertTriangle`, `Layers`, `Send`, `Eye`, `RotateCcw`) |
| Font | JetBrains Mono / Inter system fallback |
| Styling Theme | Tactical Dark Obsidian (`#0B0F17`) with illuminated Cyan (`#06b6d4`), Emerald (`#10b981`), Amber (`#f59e0b`), Rose (`#f43f5e`), and Zinc (`#27272a`) accents |

---

## 2. Component Inventory

| Component | File Path | Phase 8 Enhancement |
|---|---|---|
| `types/index.ts` | `frontend/src/types/index.ts` | Added `MeshNode`, `MeshLink`, `MeshPath`, `MeshTopologyData`, `MeshScenarioResponse`, `CustodyAckResponse` |
| `services/api.ts` | `frontend/src/services/api.ts` | Added `getMeshTopology()`, `setRelayTelemetry()`, `triggerMeshScenario()`, `simulateRoute()` methods bound to Station Alpha and Bravo daemons |
| `topology/model.ts` | `frontend/src/components/topology/model.ts` | Upgraded to stratified 3D coordinates, multi-node mesh graph derivation, edge weights, and active forwarding vector derivation |
| `LinkTopologyView` | `frontend/src/components/topology/LinkTopologyView.tsx` | Stratified multi-elevation 3D canvas, dual-layer mesh links (dormant zinc / active cyan laser), animated particle pulses, floating HTML node pills, 4 quick-view camera preset buttons |
| `RelayInspectorDrawer` | `frontend/src/components/topology/RelayInspectorDrawer.tsx` | Slide-over inspector drawer for clicked node/link with battery/storage gauges, queue depth, per-hop latency, and direct impairment toggle switches |
| `MeshTestBenchRibbon` | `frontend/src/components/topology/MeshTestBenchRibbon.tsx` | Tactical test bench ribbon with 3 operational drill buttons ("Scenario 1: UAV-Alpha Signal Lost", "Scenario 2: Ground Relays Jammed", "Scenario 3: Convoy Mobile Breakout" + "Reset Nominal") and route diversion alert banner |
| `Header` | `frontend/src/components/Header.tsx` | Top-level illuminated cyan `[MESH: 5 NODES ACTIVE • MULTI-HOP]` status pill with soft pulse |

---

## 3. 3D Spatial Layout & Theater Coordinates

The tactical coordinate system maps $1\text{ unit} = 2.5\text{ km}$:

| Node ID | Role | Position $(X, Y, Z)$ | Altitude / Stratum | Visual Geometry | Color Accent |
|---|---|:---:|---|---|---|
| `endpoint-a` | Station Alpha (Base) | `[-9.0, 0.0, 0.0]` | Ground ($Y=0$) | Pulsing sphere ($r=0.65$) + radar ring | Cyan (`#06b6d4`) |
| `endpoint-b` | Station Bravo (Base) | `[+9.0, 0.0, 0.0]` | Ground ($Y=0$) | Pulsing sphere ($r=0.65$) + radar ring | Emerald (`#10b981`) |
| `relay-ground-01` | Portable Ground Relay | `[-5.0, 0.0, -1.5]` | Ground ($Y=0$) | Hexagonal prism / octahedron | Emerald (`#10b981`) |
| `relay-convoy-01` | Mobile Vehicle Gateway | `[0.0, 0.0, 1.0]` | Ground Mobile ($Y=0$) | Tactical box prism + mobile beacon | Amber (`#f59e0b`) |
| `relay-ground-02` | Portable Ground Relay | `[+5.0, 0.0, -1.5]` | Ground ($Y=0$) | Hexagonal prism / octahedron | Emerald (`#10b981`) |
| `relay-uav-alpha` | Aerial Tactical Payload | `[-3.0, 4.5, 0.5]` | Elevated ($Y=+4.5$) | Double-pyramid with orbital drift | Cyan (`#38bdf8`) |
| `relay-uav-bravo` | High-Altitude Relay | `[+3.0, 6.0, -0.5]` | Elevated ($Y=+6.0$) | Double-pyramid with orbital drift | Sky Blue (`#0284c7`) |

---

## 4. Visual Design Contracts & Styling Specifications

### 1. Dual-Layer Mesh Links & Active Neon Laser Vectors (`LinkTopologyView.tsx`)
```tsx
// Dormant / Available Mesh Links
<Line
  points={[nodeA.pos, nodeB.pos]}
  color="#27272a"
  lineWidth={1.2}
  dashed
  dashSize={0.4}
  gapSize={0.3}
  transparent
  opacity={0.35}
/>

// Active Multi-Hop Forwarding Route (Illuminated Neon Laser)
<Line
  points={activePathPoints}
  color="#06b6d4"
  lineWidth={3.8}
  transparent
  opacity={0.95}
/>
```

### 2. Animated Traveling Packet Pulses along Active Vector
- Render 3 to 6 glowing particle spheres (`#38bdf8`, radius `0.14`) interpolating along `activePathPoints` at constant speed ($2.5\text{ units/sec}$).
- Each hop emits subtle concentric pulse waves on arrival.

### 3. Floating 3D Node HUD Pills
- Centered HTML element (`<Html center distanceFactor={15}>`) above each relay:
  - Top line: Node Name (e.g. `UAV-ALPHA [4.5km Alt]`)
  - Bottom line: Battery % (`text-emerald-400`), Storage % (`text-zinc-400`), Queue depth (`text-cyan-400`)
  - If failsafe cutoff or forced offline: Crimson badge `[OFFLINE: CUTOFF]` (`text-rose-400 font-bold animate-pulse`)

### 4. 4 Tactical Camera Quick-View Presets
- Buttons rendered in top-right overlay ribbon:
  1. `Theater Overview`: Camera at `[0, 18, 22]`, target `[0, 0, 0]` (full battlefield perspective).
  2. `Focus UAV Flight Corridors`: Camera at `[0, 9, 8]`, target `[0, 5, 0]` (elevated orbit view).
  3. `Forwarding Vector Tracking`: Smooth lerp to center of active path bounding box.
  4. `Ground Axis`: Camera at `[0, 2, 16]`, target `[0, 0, 0]` (low-angle ground relay perspective).

### 5. Slide-Over Relay Inspector Drawer (`RelayInspectorDrawer.tsx`)
- Triggered by clicking any node in the 3D scene.
- Width: `w-96`, sliding from right edge with dark obsidian backdrop blur (`bg-slate-950/90 border-l border-zinc-800`).
- Content:
  - Status Badge (`ONLINE`, `STANDBY`, `OFFLINE`, `CUTOFF`)
  - Real-time battery gauge bar with warning threshold at 10%
  - Storage buffer utilization bar (0-100%)
  - Queue depth counter with priority breakdown (`FLASH`, `IMMEDIATE`, `ROUTINE`)
  - Per-Hop Latency to adjacent neighbors
  - Interactive Impairment Switches: "Force Offline", "Drain Battery (3%)", "Fill Storage (99%)", "Simulate RF Jamming"

### 6. Tactical Test Bench Ribbon & Alert Banner (`MeshTestBenchRibbon.tsx`)
- Horizontal ribbon docked at top of LinkTopologyView:
  - Scenario 1 Button: `UAV-Alpha Signal Lost` (simulates immediate dropout of `relay-uav-alpha`)
  - Scenario 2 Button: `Ground Relays Jammed` (forces `relay-ground-01` and `relay-ground-02` offline, compelling all-aerial flight corridor routing)
  - Scenario 3 Button: `Convoy Mobile Breakout` (relocates convoy to extended periphery)
  - Reset Button: `Reset All Nominal`
- Alert Banner (appears upon dynamic rerouting in <300ms):
  `[MESH REROUTE: Bypassed relay-uav-alpha -> Diverted via relay-ground-02 + convoy -> Delivered (3 Hops • 74ms Latency)]` with illuminated amber border and pulsing alert icon.
