# Phase 04: Tactical Multi-Transport Broker & Hardware Safety Lockout - Context

**Gathered:** 2026-10-19  
**Status:** Ready for planning  

<domain>
## Phase Boundary

Phase 04 establishes a hardened, unified tactical multi-transport routing broker for SHADOWCOMM. It enforces rigorous transport readiness validation (`READY`, `SIMULATION_ONLY`, `LOCKED_OUT`, `OFFLINE`), transparent Motorola MOTOTRBO 280-byte DMR Tier-II payload chunking and XCMP protocol simulation, permanent software safety lockout for the STAR-V tactical SDR adapter with security audit logging, and dual-view relay node store-and-forward telemetry monitoring (battery %, temperature, storage %, forwarding counts) with decoupled aerial flight safety failsafes.

</domain>

<decisions>
## Implementation Decisions

### 1. Multi-Transport Routing & Fallback Policy (TRN-01)
- **D-01 (Routing Mode):** Operator-Pinned with Auto-Failover Toggle: Operator selects an active primary transport (e.g., Motorola MOTOTRBO, Simulated RF, or Relay Gateway), with an interactive toggle switch to permit automatic failover to operational secondary transports if the primary transport is offline or disconnected.
- **D-02 (Unroutable Queueing):** Durable Queue Hold (`FAILED_RETRYABLE`): When no authorized or operational transport is available (e.g. active transport is offline or locked out and failover is disabled/exhausted), outbound messages are safely preserved in the SQLite durable queue with an illuminated `ROUTE_UNAVAILABLE` telemetry status, retrying under exponential backoff rather than dropping.

### 2. Motorola DMR 280-Byte Ceiling & Fragmentation UX (TRN-02)
- **D-03 (DMR Chunking UX):** Transparent Tactical Fragmentation with Live Chunk HUD: Payloads exceeding the 280-byte DMR Tier-II burst limit are automatically chunked into ordered self-describing packets (`<uint16 total><uint16 index><data>`), while the station composer displays a real-time `DMR Bursts: N chunks • XXX B wire budget` telemetry badge so operators have full visibility into burst transmission costs.
- **D-04 (Retry Coordination):** Atomic Frame Retries: If any chunk in a multi-burst transmission fails or drops across a lossy channel, the adapter marks the delivery attempt failed, and all chunks are re-transmitted together on the subsequent backoff retry window to maintain deterministic ordering.

### 3. STAR-V Tactical SDR Safety Lockout & Audit Logging (TRN-03)
- **D-05 (Lockout Presentation):** Interactive Tactical Lockout Dossier: Clicking the STAR-V card in `DevicesView` opens an inspection modal displaying the permanent safety lockout rationale, the 4 statutory/regulatory prerequisites (Vendor ICD, official defense authorization, station license, COMSEC protocol key), and simulated dry-run safety verification test buttons (`Test Soft Refusal` and `Test Hard Command Lockout`).
- **D-06 (Security Audit Event):** High-Severity Security Audit Event: Outbound transmission attempts targeting or forced onto the locked-out STAR-V adapter log an explicit `STARV_SAFETY_LOCKOUT_BLOCKED` event in SQLite, surfaced in the Message Telemetry Drawer with an illuminated crimson lockout seal.

### 4. Relay Node Telemetry & Decoupled Failsafes (TRN-04)
- **D-07 (Dual-View Tactical Monitoring):** Surface detailed relay telemetry cards in `DevicesView` (battery gauges, temperature, queue depth, forwarding counters) and render interactive relay nodes in `LinkTopologyView` showing real-time path connectivity between Station Alpha, Station Bravo, and intermediate relay gateways.
- **D-08 (Autonomous Failsafe Cutoff):** Relays automatically suspend forwarding and reroute to direct station links when battery $\le 5\%$ or storage $\ge 98\%$. Aerial relays prominently render a `[FLIGHT SAFETY ISOLATION: ACTIVE]` badge verifying payload communications are strictly isolated from vehicle flight safety controls.

### The Agent's Discretion
- Visual styling of DMR chunk badges and relay telemetry gauges matching the existing dark tactical `#0B0F17` / `#131B2E` aesthetic with 3D directional depth.
- Database storage schema for relay node telemetry updates and transport settings persistence.
- REST endpoints for transport selection (`POST /api/v1/transports/active`), failover settings (`POST /api/v1/transports/failover`), and relay health querying (`GET /api/v1/relays`).

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Transport Adapter Architecture & Contracts
- `Final-Project/integration/base.py` — `BaseTransportAdapter`, `TransportReadiness` enum, `TransportConnectionState` enum, base error history recording.
- `Final-Project/integration/manager.py` — `TransportManager` singleton, adapter registration, priority routing, readiness checks.
- `Final-Project/messaging/dispatch.py` — Dispatch router, active transport persistence (`system_settings`), DMR 280-byte `chunk_frame` and envelope serialization.

### Tactical Radio Adapters
- `Final-Project/integration/motorola/adapter.py` — `MotorolaMOTOTRBOAdapter`, DMR 280-byte burst ceiling, TMS simulation, `MotorolaHardwareBridge`.
- `Final-Project/integration/starv/adapter.py` — `StarVAdapter`, `StarVSafetyLockoutError`, permanent software safety lockout enforcement.

### Relay Nodes & Ground/Aerial Gateways
- `Final-Project/integration/relay_nodes/manager.py` — `RelayNode`, `RelayNodeManager`, `RelayNodeType`, `RelayStatus`, battery/storage thresholds, flight failsafe independence.
- `Final-Project/tests/integration/test_adapters.py` — Unit & integration tests for Motorola, StarV, and TransportManager.
- `Final-Project/tests/integration/test_relay_nodes.py` — Unit tests for relay telemetry, thresholds, and aerial flight failsafe decoupling.

### Frontend Tactical Views
- `Final-Project/frontend/src/components/DevicesView.tsx` — Configured station endpoints and radio adapters (Motorola, STAR-V, LPI-CGAN).
- `Final-Project/frontend/src/components/topology/LinkTopologyView.tsx` — 3D Three.js tactical network topology, stations, and relay links.
- `Final-Project/frontend/src/components/StationConsoleColumn.tsx` — Tactical station console, composer RF budget HUD, and packet transmission CTA.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `integration.manager.transport_manager`: Ready singleton with priority sorting, adapter registry, and readiness filtering (`READY`, `SIMULATION_ONLY`).
- `messaging.dispatch.chunk_frame`: Already provides 280-byte DMR frame splitting with 4-byte index header (`<uint16 total><uint16 index>`).
- `integration.relay_nodes.manager.RelayNodeManager`: Full implementation of ground and simulated aerial relay nodes with battery, temperature, storage, and forwarding counters.
- `frontend/src/components/DevicesView.tsx`: Established tactical card layout for radio adapters and station endpoints.

### Established Patterns
- **Safety First:** Strict hardware boundary isolation. Untrusted physical RF broadcast is prohibited (`LOCKED_OUT` for STAR-V, `SIMULATION_ONLY` by default for Motorola without explicit `MOTOROLA_RADIO_APPROVED=true`).
- **Tactical C2 Aesthetic:** Dark `#0B0F17` / `#131B2E` panels, cyan/emerald station accents, glowing status pills, and microsecond timestamps.
- **Mac Dynamic Linker Order:** `import torch` strictly precedes `numpy` and `scipy` across all Python entry points and test modules.

### Integration Points
- `messaging/worker.py`: Wire delivery attempts through `dispatch_router` or `transport_manager` to enforce active transport selection, failover, and chunking.
- `messaging/api.py`: Expose REST endpoints for transport listing, active transport configuration, failover toggle, and relay node telemetry.
- `frontend/src/services/api.ts`: Add client methods for `getActiveTransport()`, `setActiveTransport()`, `getRelayNodes()`, and `triggerStarVSafetyTest()`.
- `frontend/src/components/DevicesView.tsx`: Integrate interactive relay cards and STAR-V lockout dossier modal.
- `frontend/src/components/StationConsoleColumn.tsx`: Integrate live DMR burst counter HUD into quick composer when Motorola transport is active.

</code_context>

<specifics>
## Specific Ideas

- **DMR Chunking HUD:** In the quick composer, if the active transport is `motorola-mototrbo-01` and payload bytes exceed 276 bytes (280 - 4), render a tactical badge: `[DMR: 2 Bursts (560B Budget)]` right next to the GCM envelope and RS codeword calculation.
- **STAR-V Lockout Dossier Modal:** A high-tech slide-over or modal with red hazard striping, displaying the 4 prerequisites (ICD, Defense Auth, Station License, COMSEC Key) with red `[RESTRICTED]` padlocks, plus test buttons to verify that software safety lockout cleanly blocks keying.
- **Relay Node Telemetry HUD:** Progress bars for battery (green > 20%, amber $\le 20\%$, red $\le 5\%$) and storage (green < 80%, amber $\ge 80\%$, red $\ge 98\%$), with temperature in Celsius.

</specifics>

<deferred>
## Deferred Ideas

- **V2-01:** Multi-hop ad-hoc mesh routing protocol across > 5 mobile endpoints (deferred to v2 milestone).
- **V2-02:** Live hardware over-the-air validation on physical Motorola APX / MOTOTRBO hardware (requires physical radio bench setup).
- **V2-03:** Hardware Interface Control Document (ICD) compliance verification for STAR-V SDR (requires authorized defense vendor ICD).

</deferred>

---

*Phase: 04-Tactical Multi-Transport Broker & Hardware Safety Lockout*  
*Context gathered: 2026-10-19*  
